"""The four named workflow regressions plus non-inference and readback invariants."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from handoff_store import TicketStore
from service import (CaseRepository, Conversation, SessionAuthority,
                     create_handoff_ticket, respond)


class NeverCallModel:
    def predict_proba(self, texts: list[str]) -> None:
        raise AssertionError("A deterministic route must not call the model")


class RequiredWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authority = SessionAuthority(b"wf-v13-test-secret-with-32-bytes!!")
        self.alicia = self.authority.issue("Alicia (prueba)", "1379", now=1000)
        self.bruno = self.authority.issue("Bruno (prueba)", "2468", now=1000)
        self.repository = CaseRepository()
        self.model = NeverCallModel()

    def ask(self, message: str, conversation: Conversation, *, token: str | None = None,
            language: str = "es", ticket_store: TicketStore | None = None):
        return respond(message, token or self.alicia, conversation, self.authority,
                       self.repository, self.model, router="learned", language=language,
                       ticket_store=ticket_store, now=1001)

    def test_wf01_folio_routes_to_owned_case_before_model(self) -> None:
        reply = self.ask("¿Podrías decirme si se movió el trámite R-101?", Conversation())
        self.assertEqual((reply.kind, reply.intent, reply.case_id),
                         ("resolved", "status", "R-101"))
        self.assertEqual(reply.case_view["status"], "En proceso")
        self.assertIn("lookup_checked", reply.trace)

    def test_wf05_foreign_and_missing_are_indistinguishable_403_without_model(self) -> None:
        foreign = self.ask("Cuéntame en qué quedó el R-201.", Conversation())
        missing = self.ask("Cuéntame en qué quedó el R-999.", Conversation())
        for reply in (foreign, missing):
            self.assertEqual((reply.kind, reply.status_code), ("denied", 403))
            self.assertEqual(reply.error["code"], "FORBIDDEN")
            self.assertEqual(reply.error["status"], 403)
            self.assertIsNone(reply.case_view)
            self.assertIsNone(reply.handoff)
            self.assertEqual(reply.evidence, "")
        self.assertEqual(foreign.error, missing.error)
        self.assertEqual(foreign.text, missing.text)

    def test_wf16_general_products_abstain_without_model_or_ticket(self) -> None:
        samples = (("Onde posso mudar o endereço do meu cadastro?", "pt", self.bruno),
                   ("¿Qué comisión cobra el cajero?", "es", self.alicia),
                   ("Onde consulto tarifas do cartão?", "pt", self.bruno),
                   ("¿Cómo cambio mis tarjetas?", "es", self.alicia),
                   ("¿Cuánto cuestan las comisiones?", "es", self.alicia))
        for message, language, token in samples:
            with self.subTest(message=message):
                reply = self.ask(message, Conversation(), token=token, language=language)
                self.assertEqual((reply.kind, reply.intent), ("unsupported", "other"))
                self.assertIsNone(reply.handoff)
                self.assertNotIn("ask_question", reply.trace)

    def test_wf18_clarification_then_owned_status_without_model(self) -> None:
        conversation = Conversation()
        first = self.ask("Tenho uma reclamação em aberto, pode conferir?",
                         conversation, language="pt")
        self.assertEqual((first.kind, first.intent), ("clarify", "status"))
        self.assertTrue(conversation.waiting_for_case)
        second = self.ask("R-102", conversation, language="pt")
        self.assertEqual((second.kind, second.case_id), ("resolved", "R-102"))
        self.assertEqual(second.case_view["status"], "Resuelto")

    def test_verified_escalation_packet_has_id_and_no_raw_transcript(self) -> None:
        with TemporaryDirectory() as directory:
            tickets = TicketStore(Path(directory) / "tickets.sqlite3")
            conversation = Conversation()
            self.ask("Estado de R-101", conversation)
            phrase = "Necesito un agente, estoy preocupado por una clave secreta particular"
            handoff = self.ask(phrase, conversation)
            self.assertEqual(handoff.kind, "handoff")
            self.assertIsNone(handoff.handoff["ticket_id"])
            self.assertEqual(handoff.handoff["sentiment"], "expressed_concern")
            self.assertNotIn("clave secreta particular", str(handoff.handoff))
            result = create_handoff_ticket(self.alicia, conversation, self.authority,
                                           self.repository, tickets, now=1002)
            self.assertEqual(result.kind, "created")
            self.assertEqual(result.packet["ticket_id"], result.ticket_id)
            self.assertEqual(result.packet["customer_id"], "test-a")
            self.assertEqual(result.packet["verified_facts"]["case_id"], "R-101")
            self.assertEqual(result.packet["reason_for_escalation"], "requested")
            self.assertTrue(result.packet["open_questions"])
            self.assertNotIn("clave secreta particular", str(result.packet))
            status = self.ask(result.ticket_id, conversation, ticket_store=tickets)
            self.assertEqual(status.kind, "ticket_status")
            self.assertIn("ticket_read_back", status.trace)
            foreign = self.ask(result.ticket_id, Conversation(), token=self.bruno,
                               ticket_store=tickets)
            self.assertEqual((foreign.kind, foreign.status_code), ("denied", 403))

    def test_folio_overrides_other_intent_with_safe_read_only_action(self) -> None:
        reply = self.ask("Quiero disputar R-101 y hablar con alguien", Conversation())
        self.assertEqual((reply.kind, reply.intent), ("resolved", "status"))
        self.assertIsNone(reply.handoff)


if __name__ == "__main__":
    unittest.main()
