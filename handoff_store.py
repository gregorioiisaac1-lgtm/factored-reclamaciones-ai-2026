"""Short-lived SQLite queue for fictitious handoff tickets in the public demo.

This is local instance storage, not a bank system or a human-agent inbox.
"""

import json
from contextlib import closing
from pathlib import Path
import secrets
import sqlite3
import tempfile
import time
from typing import Any


class TicketStoreError(Exception):
    pass


class TicketConflictError(TicketStoreError):
    """The same confirmation key already refers to a different verified packet."""


class TicketStore:
    retention_seconds = 24 * 60 * 60

    def __init__(self, path=None):
        self.path = Path(path) if path else Path(tempfile.gettempdir()) / "factored_demo_tickets.sqlite3"

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            session_scope TEXT NOT NULL,
            request_key TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            packet TEXT NOT NULL,
            UNIQUE(owner, session_scope, request_key)
            )""")
            connection.execute("""CREATE TABLE IF NOT EXISTS reviews (
            ticket_id TEXT PRIMARY KEY,
            reviewer TEXT NOT NULL,
            reviewed_at INTEGER NOT NULL
            )""")
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def create_and_verify(self, owner: str, session_scope: str, request_key: str,
                          packet: dict[str, Any], *, now: float | None = None,
                          fail_write: bool = False, fail_read: bool = False
                          ) -> tuple[str, dict[str, Any]]:
        """Idempotently insert, then read the stored packet before claiming success."""
        timestamp = int(time.time() if now is None else now)
        ticket_id = "T-" + secrets.token_hex(8).upper()
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("DELETE FROM tickets WHERE created_at < ?", (timestamp - self.retention_seconds,))
                connection.execute("DELETE FROM reviews WHERE ticket_id NOT IN (SELECT ticket_id FROM tickets)")
                if fail_write:
                    raise sqlite3.OperationalError("simulated write failure")
                connection.execute(
                    """INSERT INTO tickets (ticket_id, owner, session_scope, request_key, created_at, packet)
                       VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(owner, session_scope, request_key) DO NOTHING""",
                    (ticket_id, owner, session_scope, request_key, timestamp,
                     json.dumps({**packet, "ticket_id": ticket_id}, ensure_ascii=False)),
                )
                row = connection.execute(
                    "SELECT ticket_id FROM tickets WHERE owner = ? AND session_scope = ? AND request_key = ?",
                    (owner, session_scope, request_key),
                ).fetchone()
            if row is None or fail_read:
                raise TicketStoreError("ticket not confirmed")
            # Use a separate connection: a successful read must see committed data.
            confirmed = self.read(owner, session_scope, row[0], now=timestamp)
            if confirmed is None:
                raise TicketStoreError("ticket not confirmed")
            if confirmed.get("ticket_id") != row[0] or {
                key: value for key, value in confirmed.items() if key != "ticket_id"
            } != packet:
                # An idempotent retry must never join an old persisted packet
                # to a newly fetched case view and claim both are current.
                raise TicketConflictError("case changed after ticket confirmation")
            return row[0], confirmed
        except (OSError, sqlite3.Error) as exc:
            raise TicketStoreError("ticket queue unavailable") from exc

    def read(self, owner: str, session_scope: str, ticket_id: str, *,
             now: float | None = None) -> dict[str, Any] | None:
        timestamp = int(time.time() if now is None else now)
        try:
            with closing(self._connect()) as connection, connection:
                row = connection.execute(
                    """SELECT packet FROM tickets WHERE ticket_id = ? AND owner = ?
                       AND session_scope = ? AND created_at >= ?""",
                    (ticket_id, owner, session_scope, timestamp - self.retention_seconds),
                ).fetchone()
            return json.loads(row[0]) if row else None
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise TicketStoreError("ticket queue unavailable") from exc

    def list_recent(self, *, now=None, limit=25):
        """Return the test reviewer's bounded inbox of sanitized packets."""
        timestamp = int(time.time() if now is None else now)
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """SELECT t.ticket_id, t.created_at, t.packet, r.reviewed_at
                       FROM tickets AS t LEFT JOIN reviews AS r ON r.ticket_id = t.ticket_id
                       WHERE t.created_at >= ? ORDER BY t.created_at DESC, t.ticket_id DESC
                       LIMIT ?""",
                    (timestamp - self.retention_seconds, min(max(1, limit), 25)),
                ).fetchall()
            return [{"ticket_id": ticket_id, "created_at": created,
                     "packet": json.loads(packet), "reviewed_at": reviewed}
                    for ticket_id, created, packet, reviewed in rows]
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise TicketStoreError("ticket queue unavailable") from exc

    def acknowledge(self, ticket_id, reviewer, *, now=None):
        """Confirm a review write with a committed readback; never fabricate receipt."""
        timestamp = int(time.time() if now is None else now)
        try:
            with closing(self._connect()) as connection, connection:
                exists = connection.execute(
                    "SELECT 1 FROM tickets WHERE ticket_id = ? AND created_at >= ?",
                    (ticket_id, timestamp - self.retention_seconds),
                ).fetchone()
                if not exists:
                    return None
                connection.execute(
                    """INSERT INTO reviews (ticket_id, reviewer, reviewed_at)
                       VALUES (?, ?, ?) ON CONFLICT(ticket_id) DO NOTHING""",
                    (ticket_id, reviewer, timestamp),
                )
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT reviewer, reviewed_at FROM reviews WHERE ticket_id = ?", (ticket_id,),
                ).fetchone()
            if row is None:
                raise TicketStoreError("review not confirmed")
            return {"ticket_id": ticket_id, "reviewer": row[0], "reviewed_at": row[1]}
        except (OSError, sqlite3.Error) as exc:
            raise TicketStoreError("review queue unavailable") from exc

    def review_status(self, owner, session_scope, ticket_id, *, now=None):
        """Show the owner only a verified receipt for this session's ticket."""
        timestamp = int(time.time() if now is None else now)
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """SELECT r.reviewer, r.reviewed_at FROM tickets AS t
                       JOIN reviews AS r ON r.ticket_id = t.ticket_id
                       WHERE t.ticket_id = ? AND t.owner = ? AND t.session_scope = ?
                       AND t.created_at >= ?""",
                    (ticket_id, owner, session_scope, timestamp - self.retention_seconds),
                ).fetchone()
            return {"ticket_id": ticket_id, "reviewer": row[0], "reviewed_at": row[1]} if row else None
        except (OSError, sqlite3.Error) as exc:
            raise TicketStoreError("review queue unavailable") from exc
