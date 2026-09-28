"""Small UI integration checks for the two judge-facing views."""

import unittest

from streamlit.testing.v1 import AppTest


class StreamlitViewsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = AppTest.from_file("streamlit_app.py").run(timeout=40)
        self.assertFalse(self.app.exception)

    def test_profile_switch_clears_history_and_foreign_trace_is_sanitized(self) -> None:
        self.app.button(key="example_own").click().run(timeout=40)
        self.assertEqual(self.app.session_state["messages"][-1]["kind"], "resolved")
        self.app.selectbox(key="demo_profile").set_value("Bruno (prueba)").run(timeout=40)
        self.assertEqual(self.app.session_state["messages"], [])
        self.assertEqual(self.app.session_state["agent_events"], [])
        self.app.button(key="example_foreign").click().run(timeout=40)
        answer = self.app.session_state["messages"][-1]
        event = self.app.session_state["agent_events"][-1]
        self.assertEqual((answer["kind"], answer["status_code"]), ("denied", 403))
        self.assertEqual(event["security"], "forbidden")
        self.assertEqual(event["tool"]["input"],
                         {"customer_id": "test-b", "reference": "R-101"})
        self.assertNotIn("En proceso", str(event))
        self.assertNotIn("1379", str(event))
        self.assertFalse(self.app.exception)

    def test_portuguese_outside_scope_and_actual_model_score(self) -> None:
        self.app.radio(key="ui_language").set_value("Português").run(timeout=40)
        self.app.chat_input(key="customer_chat").set_value(
            "Onde posso mudar o endereço do meu cadastro?").run(timeout=40)
        event = self.app.session_state["agent_events"][-1]
        self.assertEqual(self.app.session_state["messages"][-1]["kind"], "unsupported")
        self.assertEqual((event["routing"]["source"], event["tool"]["name"]),
                         ("policy", None))
        self.assertIsNone(event["routing"]["confidence"])
        self.app.radio(key="ui_language").set_value("Español").run(timeout=40)
        self.app.chat_input(key="customer_chat").set_value(
            "Tengo algo pendiente, no sé qué hacer").run(timeout=40)
        event = self.app.session_state["agent_events"][-1]
        self.assertEqual(event["routing"]["source"], "model")
        self.assertGreater(event["routing"]["confidence"], 0)
        self.assertLessEqual(event["routing"]["confidence"], 1)
        self.assertEqual((event["llm_tokens"], event["api_cost_usd"]), (0, 0.0))
        self.assertFalse(self.app.exception)

    def test_handoff_ticket_is_committed_and_trace_contains_readback(self) -> None:
        self.app.button(key="example_own").click().run(timeout=40)
        self.app.button(key="guided_human").click().run(timeout=40)
        self.assertEqual(self.app.session_state["messages"][-1]["kind"], "handoff")
        self.assertIsNone(self.app.session_state["agent_events"][-1]["handoff"]["ticket_id"])
        self.app.button(key="create_test_ticket").click().run(timeout=40)
        entry = self.app.session_state["messages"][-1]
        event = self.app.session_state["agent_events"][-1]
        self.assertEqual(entry["kind"], "ticket_created")
        self.assertEqual(event["tool"]["name"], "TicketStore.create_and_verify")
        self.assertTrue(event["tool"]["verified"])
        self.assertEqual(entry["ticket_id"], event["handoff"]["ticket_id"])
        self.assertEqual(event["handoff"]["customer_id"], "test-a")
        self.assertEqual(self.app.session_state["session_metrics"]["calls"], 3)
        self.assertFalse(self.app.exception)


if __name__ == "__main__":
    unittest.main()
