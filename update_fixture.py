"""Explicitly fictitious incremental snapshot test; app itself reads static 2025 fixtures."""

from datetime import datetime


VALID_STATUSES = {"En proceso", "Resuelto", "Escalado"}


def merge(existing, incoming):
    if existing["case_id"] != incoming["case_id"] or existing["owner"] != incoming["owner"]:
        raise ValueError("Changing identity or case ownership is forbidden")
    if incoming["status"] not in VALID_STATUSES:
        raise ValueError("Unknown status")
    before = datetime.fromisoformat(existing["updated_at"])
    after = datetime.fromisoformat(incoming["updated_at"])
    if after == before and incoming != existing:
        raise ValueError("Conflicting event at same timestamp")
    return incoming if after > before else existing


def verify_fixture():
    old = {"case_id": "R-TEST", "owner": "test-a", "status": "En proceso", "updated_at": "2025-12-20T10:00:00"}
    new = {"case_id": "R-TEST", "owner": "test-a", "status": "Resuelto", "updated_at": "2026-01-02T10:00:00"}
    assert merge(old, new) == new  # new event is visible
    assert merge(new, new) == new  # replay is idempotent
    assert merge(new, old) == new  # late old event cannot reverse state
    try:
        merge(new, {**old, "owner": "test-b"})
    except ValueError:
        pass
    else:
        raise AssertionError("Owner change was accepted")
    return "Incremental fixture passed: newer status, replay, stale event, ownership"


if __name__ == "__main__":
    print(verify_fixture())
