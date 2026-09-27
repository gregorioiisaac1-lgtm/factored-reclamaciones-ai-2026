"""End-to-end tests for consent, authorization, verified writes, and failure paths."""

from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from handoff_store import TicketStore
from intent import make_model
from service import (CaseRepository, Conversation, SessionAuthority, create_handoff_ticket,
                     read_handoff_ticket, respond)


class TicketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = make_model()

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "tickets.sqlite3"
        self.store = TicketStore(self.path)
        self.authority = SessionAuthority(b"test-ticket-key-more-than-32-bytes-long")
        self.a = self.authority.issue("Alicia (prueba)", "1379", now=1000)
        self.b = self.authority.issue("Bruno (prueba)", "2468", now=1000)
        self.repo = CaseRepository()

    def ask(self, message, conversation=None, token=None, *, language="es", repository=None, fail_tool=False):
        conversation = conversation if conversation is not None else Conversation()
        reply = respond(message, token or self.a, conversation, self.authority,
                        repository or self.repo, self.model, language=language,
                        fail_tool=fail_tool, now=1001)
        return reply, conversation

    def create(self, conversation, *, token=None, repository=None, **options):
        return create_handoff_ticket(token or self.a, conversation, self.authority,
                                     repository or self.repo, self.store, now=1002, **options)

    def read(self, conversation, ticket_id, *, token=None, repository=None):
        return read_handoff_ticket(token or self.a, conversation, self.authority,
                                   repository or self.repo, self.store, ticket_id, now=1003)

    def test_no_ticket_until_confirmation_then_committed_readback_and_idempotence(self):
        _, convo = self.ask("Estado de R-101")
        reply, _ = self.ask("Quiero hablar con un agente", convo)
        self.assertEqual(reply.kind, "handoff")
        self.assertFalse(self.path.exists())
        saved = self.create(convo)
        self.assertEqual(saved.kind, "created")
        self.assertEqual(saved.trace, ("ticket_saved", "ticket_read_back"))
        self.assertTrue(saved.ticket_id.startswith("T-"))
        self.assertEqual(saved.packet["verified_case"], "R-101")
        self.assertEqual(saved.packet["verified_status"], "En proceso")
        self.assertEqual(saved.packet["verified_updated"], "15/12/2025")
        self.assertIn("fresh_authorized_lookup", saved.packet["actions"])
        self.assertEqual(self.read(convo, saved.ticket_id), saved.packet)
        self.assertEqual(TicketStore(self.path).read("test-a", convo.ticket_scope, saved.ticket_id, now=1003),
                         saved.packet)
        self.assertEqual(self.create(convo).ticket_id, saved.ticket_id)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0], 1)

    def test_foreign_and_missing_folios_never_get_verified_facts_in_ticket(self):
        packets = []
        for case in ("R-201", "R-999"):
            reply, convo = self.ask("Quiero hablar con un agente sobre " + case)
            self.assertEqual(reply.kind, "handoff")
            result = self.create(convo)
            self.assertEqual(result.kind, "created")
            self.assertIsNone(result.packet["verified_case"])
            self.assertIsNone(result.packet["verified_status"])
            self.assertIsNone(result.packet["source"])
            self.assertNotIn(case, str(result.packet))
            packets.append(result.packet)
        self.assertEqual(packets[0], packets[1])

    def test_source_failure_can_create_safe_ticket_without_case_status(self):
        reply, convo = self.ask("Estado de R-101", fail_tool=True)
        self.assertEqual(reply.handoff["reason"], "tool_failure")
        saved = self.create(convo, fail_tool=True)
        self.assertEqual(saved.kind, "created")
        self.assertIsNone(saved.packet["verified_status"])
        self.assertIsNone(saved.packet["verified_case"])
        self.assertIsNone(saved.case_view)
        self.assertEqual(self.read(convo, saved.ticket_id), saved.packet)

    def test_portuguese_dispute_does_not_inherit_last_case_or_store_raw_text(self):
        _, convo = self.ask("Status do protocolo R-101", language="pt")
        reply, _ = self.ask("Quero um atendente: não reconheço cobrança do meu cartão 1234",
                            convo, language="pt")
        self.assertEqual(reply.kind, "handoff")
        self.assertEqual(reply.handoff["reason"], "new_dispute")
        saved = self.create(convo, language="pt")
        self.assertEqual(saved.kind, "created")
        self.assertIsNone(saved.packet["verified_case"])
        self.assertIn("cobrança", saved.packet["request"])
        self.assertNotIn("1234", str(saved.packet))
        self.assertIn("Não foi enviado", saved.text)

    def test_revocation_or_tool_failure_before_save_blocks_verified_ticket(self):
        class Revoked(CaseRepository):
            def lookup(self, customer, case_id, *, fail=False):
                return None

        _, convo = self.ask("Estado de R-101")
        self.ask("Quiero un agente", convo)
        for opts in ({"repository": Revoked()}, {"fail_tool": True}):
            with self.subTest(opts=opts):
                result = self.create(convo, **opts)
                self.assertEqual(result.kind, "unavailable")
                self.assertFalse(result.ticket_id)
                self.assertFalse(self.path.exists())

    def test_status_is_rechecked_on_save_and_ownership_on_read(self):
        class Mutable(CaseRepository):
            revoked = False

            def lookup(self, customer, case_id, *, fail=False):
                if self.revoked:
                    return None
                record = super().lookup(customer, case_id, fail=fail)
                if record:
                    record.update(status="Resuelto", updated="29/12/2025")
                return record

        _, convo = self.ask("Estado de R-101")
        self.ask("Quiero un agente", convo)
        source = Mutable()
        saved = self.create(convo, repository=source)
        self.assertEqual(saved.packet["verified_status"], "Resuelto")
        self.assertEqual(saved.case_view["updated"], "29/12/2025")
        source.revoked = True
        self.assertIsNone(self.read(convo, saved.ticket_id, repository=source))

    def test_session_switch_and_expiration_cannot_save_or_read_prior_ticket(self):
        self.ask("Estado de R-101", convo := Conversation())
        self.ask("Quiero un agente", convo)
        saved = self.create(convo)
        self.assertEqual(self.create(convo, token=self.b).kind, "auth_required")
        self.assertIsNone(self.read(convo, saved.ticket_id, token=self.b))
        self.assertIsNone(self.read(Conversation(), saved.ticket_id))
        expired = create_handoff_ticket(self.a, convo, self.authority, self.repo,
                                        self.store, now=1601)
        self.assertEqual(expired.kind, "auth_required")
        self.assertIsNone(read_handoff_ticket(self.a, convo, self.authority, self.repo,
                                              self.store, saved.ticket_id, now=1601))

    def test_queue_write_and_readback_failures_never_report_success(self):
        self.ask("Estado de R-101", convo := Conversation())
        self.ask("Quiero un agente", convo)
        self.assertEqual(self.create(convo, fail_write=True).kind, "unavailable")
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0], 0)
        self.assertEqual(self.create(convo, fail_read=True).kind, "unavailable")
        recovered = self.create(convo)
        self.assertEqual(recovered.kind, "created")
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0], 1)
        self.assertIsNone(self.store.read("test-a", convo.ticket_scope, recovered.ticket_id,
                                          now=1002 + TicketStore.retention_seconds + 1))


if __name__ == "__main__":
    unittest.main()
