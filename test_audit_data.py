"""Data semantics, no-invention rules, scenario arithmetic and input validation."""

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from audit_data import Scenario, audit, roi, rows


def write_csv(path: Path, entries: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=entries[0])
        writer.writeheader()
        writer.writerows(entries)


class AuditDataTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.interactions = root / "interactions.csv"
        self.complaints = root / "complaints.csv"
        self.transcripts = root / "transcripts.csv"
        self.customers = root / "customers.csv"
        write_csv(self.interactions, [
            {"interaction_id": "I1", "customer_id": "A", "reason_category": "Queja",
             "channel": "Phone", "was_resolved": "True", "requires_followup": "True",
             "was_escalated": "True", "process_date": "2025-01-01"},
            {"interaction_id": "I2", "customer_id": "B", "reason_category": "Queja",
             "channel": "Phone", "was_resolved": "False", "requires_followup": "True",
             "was_escalated": "False", "process_date": "2025-01-02"},
            {"interaction_id": "I3", "customer_id": "A", "reason_category": "Producto",
             "channel": "Email", "was_resolved": "", "requires_followup": "False",
             "was_escalated": "False", "process_date": "2025-01-03"},
        ])
        write_csv(self.complaints, [
            {"complaint_id": "C1", "customer_id": "A", "category": "Transactions",
             "subcategory": "Cargo no reconocido", "status": "Resolved", "reception_channel": "Call Center",
             "resolution_days": "4", "creation_date": "2025-01-01 00:00:00",
             "resolution_date": "2025-01-05 00:00:00", "origin_interaction_id": ""},
            {"complaint_id": "C2", "customer_id": "B", "category": "Fees",
             "subcategory": "", "status": "Escalated", "reception_channel": "Web",
             "resolution_days": "", "creation_date": "2025-01-03 00:00:00",
             "resolution_date": "", "origin_interaction_id": ""},
            {"complaint_id": "C3", "customer_id": "A", "category": "Service",
             "subcategory": "Calidad", "status": "Closed", "reception_channel": "Web",
             "resolution_days": "", "creation_date": "2025-01-01 00:00:00",
             "resolution_date": "2025-01-03 00:00:00", "origin_interaction_id": ""},
        ])
        write_csv(self.transcripts, [
            {"transcript_id": "T1", "interaction_id": "I1", "customer_id": "A",
             "customer_text": "Mi saldo privado no debe exportarse", "main_topics": "Queja"},
        ])
        write_csv(self.customers, [
            {"customer_id": "A", "country": "Mexico"},
            {"customer_id": "B", "country": "Colombia"},
        ])

    def test_missing_country_and_human_destination_remain_unknown(self) -> None:
        report = audit(self.interactions, self.complaints, self.transcripts)
        self.assertEqual(report["interactions_2025"]["fcr"]["known_fcr_n"], 2)
        self.assertEqual(report["interactions_2025"]["fcr"]["rate_pct"], 50)
        self.assertEqual(report["interactions_2025"]["fcr"]["strict_without_followup_n"], 0)
        self.assertEqual(report["data_quality"]["was_resolved_true_and_requires_followup_true_n"], 1)
        self.assertIsNone(report["interactions_2025"]["fcr"]["by_country"])
        self.assertEqual(report["complaints_2025"]["currently_escalated_status"]["rate_pct"], 33.33)
        self.assertIsNone(report["complaints_2025"]["final_human_escalation"]["rate_pct"])
        self.assertEqual(report["complaints_2025"]["resolution_time"]["overall"]["mean_days"], 3)
        self.assertEqual(report["complaints_2025"]["resolution_time"]["overall"]["derived_from_dates_n"], 1)
        self.assertIsNone(report["roi"]["savings_pct"])
        self.assertEqual(report["roi"]["sampled_complaint_related_interactions_n"], 2)
        self.assertEqual(report["roi"]["contact_scope"].split(";", 1)[0],
                         "interactions with reason_category=Queja")
        self.assertNotIn("Mi saldo privado", json.dumps(report, ensure_ascii=False))

    def test_country_is_only_populated_by_explicit_customer_join(self) -> None:
        report = audit(self.interactions, self.complaints, self.transcripts,
                       customers=self.customers)
        groups = report["interactions_2025"]["fcr"]["by_country"]
        self.assertEqual({r["group"]: r["fcr_rate_pct"] for r in groups},
                         {"Colombia": 0, "Mexico": 100})
        self.assertEqual(report["complaints_2025"]["resolution_time"]["by_country"][0]["group"], "Mexico")

    def test_roi_is_explicit_scenario_not_an_observation(self) -> None:
        result = roi(10, Scenario(5, 1, .5, .8, 12, 1))
        self.assertEqual(result["llm_attempts_n"], 5)
        self.assertEqual(result["automated_resolutions_n"], 4)
        self.assertEqual(result["baseline_cost_usd"], 25)
        self.assertEqual(result["proposed_cost_usd"], 11)
        self.assertEqual(result["savings_pct"], 56)
        self.assertEqual(result["agent_hours_freed"], .8)
        self.assertEqual(result["status"], "assumption_based_scenario_not_observed_savings")
        self.assertEqual(result["sampled_complaint_related_interactions_n"], 10)
        with self.assertRaises(ValueError):
            roi(10, Scenario(5, 1, 1.4, .8, 12, 1))

    def test_bad_reported_duration_falls_back_to_valid_dates(self) -> None:
        from audit_data import resolution_time
        duration, source = resolution_time({"resolution_days": "invalid",
                                            "creation_date": "2025-01-01",
                                            "resolution_date": "2025-01-04"})
        self.assertEqual((duration, source), (3, "derived"))

    def test_zip_table_selection_and_duplicate_rejection(self) -> None:
        archive = self.interactions.parent / "source.zip"
        with ZipFile(archive, "w") as file:
            file.write(self.interactions, "year=2025/call_center_interactions_20250101.csv")
            file.write(self.complaints, "year=2025/complaints_20250101.csv")
        self.assertEqual(len(list(rows(archive, "interactions"))), 3)
        with self.interactions.open(encoding="utf-8", newline="") as file:
            original = list(csv.DictReader(file))
        repeated = self.interactions.parent / "duplicate.csv"
        write_csv(repeated, [*original, original[0]])
        with self.assertRaises(ValueError):
            audit(repeated, self.complaints, self.transcripts)


if __name__ == "__main__":
    unittest.main()
