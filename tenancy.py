"""Deterministic owner check at the record boundary, separate from routing/ML."""

from collections.abc import Mapping
from typing import Any
import hmac


class TenantMiddleware:
    """Return the same absence for a foreign or missing record to avoid enumeration."""

    def __init__(self, records: Mapping[str, Mapping[str, Any]]) -> None:
        self.records = records

    def read_owned(self, customer_id: str, reference: str) -> dict[str, Any] | None:
        row = self.records.get(reference)
        owner = row.get("owner") if row is not None else None
        if (not isinstance(owner, str) or not isinstance(customer_id, str)
                or not hmac.compare_digest(owner, customer_id)):
            return None
        return {field: value for field, value in row.items() if field != "owner"}
