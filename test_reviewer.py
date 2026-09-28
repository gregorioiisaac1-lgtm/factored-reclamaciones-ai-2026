"""Role separation and committed receipt for the fictitious review queue."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from handoff_store import TicketStore
from intent import make_model
from service import (CaseRepository, Conversation, SessionAuthority, SessionError,
                     create_handoff_ticket, read_handoff_review, respond,
                     review_handoff_ticket, reviewer_inbox)


class ReviewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = make_model()

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = TicketStore(Path(self.tmp.name) / "review.sqlite3")
        self.authority = SessionAuthority(b"review-test-key-0123456789-abcdefgh")
        self.customer = self.authority.issue("Alicia (prueba)", "1379", now=1000)
        self.reviewer = self.authority.issue_reviewer("8642", now=1000)
        self.repo = CaseRepository()

    def handoff(self):
        convo = Conversation()
        reply = respond("Estado de R-101", self.customer, convo, self.authority,
                        self.repo, self.model, now=1001)
        self.assertEqual(reply.kind, "resolved")
        reply = respond("Quiero una persona que explique el motivo", self.customer,
                        convo, self.authority, self.repo, self.model, now=1001)
        self.assertEqual(reply.kind, "handoff")
        return create_handoff_ticket(self.customer, convo, self.authority,
                                     self.repo, self.store, now=1002), convo

    def test_role_boundaries_and_expiry(self):
        with self.assertRaises(SessionError):
            self.authority.issue_reviewer("wrong", now=1000)
        with self.assertRaises(SessionError):
            reviewer_inbox(self.customer, self.authority, self.store, now=1001)
        self.assertEqual(respond("Estado de R-101", self.reviewer, Conversation(),
                                 self.authority, self.repo, self.model, now=1001).kind,
                         "auth_required")
        with self.assertRaises(SessionError):
            reviewer_inbox(self.reviewer, self.authority, self.store, now=1600)

    def test_sanitized_handoff_received_and_reviewed_once(self):
        saved, convo = self.handoff()
        self.assertEqual(saved.kind, "created")
        items = reviewer_inbox(self.reviewer, self.authority, self.store, now=1003)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["ticket_id"], saved.ticket_id)
        self.assertEqual(items[0]["packet"], saved.packet)
        self.assertIsNone(items[0]["reviewed_at"])
        self.assertNotIn("Quiero una persona", str(items[0]))
        with self.assertRaises(SessionError):
            review_handoff_ticket(self.customer, self.authority,
                                  self.store, saved.ticket_id, now=1003)
        receipt = review_handoff_ticket(self.reviewer, self.authority,
                                        self.store, saved.ticket_id, now=1003)
        self.assertEqual(receipt, {"ticket_id": saved.ticket_id,
                                   "reviewer": "test-reviewer", "reviewed_at": 1003})
        self.assertEqual(review_handoff_ticket(self.reviewer, self.authority,
                                                self.store, saved.ticket_id, now=1004), receipt)
        self.assertEqual(reviewer_inbox(self.reviewer, self.authority,
                                        self.store, now=1004)[0]["reviewed_at"], 1003)
        self.assertEqual(read_handoff_review(self.customer, convo, self.authority,
                                             self.repo, self.store, saved.ticket_id, now=1004), receipt)
        other = self.authority.issue("Bruno (prueba)", "2468", now=1000)
        self.assertIsNone(read_handoff_review(other, convo, self.authority,
                                               self.repo, self.store, saved.ticket_id, now=1004))

    def test_unknown_and_expired_tickets_cannot_be_acknowledged(self):
        saved, _ = self.handoff()
        self.assertIsNone(review_handoff_ticket(self.reviewer, self.authority,
                                                self.store, "T-missing", now=1003))
        reviewer_later = self.authority.issue_reviewer("8642", now=100000)
        self.assertIsNone(review_handoff_ticket(reviewer_later, self.authority,
                                                self.store, saved.ticket_id, now=100001))
        self.assertEqual(reviewer_inbox(reviewer_later, self.authority,
                                        self.store, now=100001), [])


if __name__ == "__main__":
    unittest.main()
