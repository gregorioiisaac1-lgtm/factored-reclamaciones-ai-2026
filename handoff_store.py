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


class TicketStoreError(Exception):
    pass


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
        except sqlite3.Error:
            connection.close()
            raise
        return connection

    def create_and_verify(self, owner, session_scope, request_key, packet, *, now=None, fail_write=False, fail_read=False):
        """Idempotently insert, then read the stored packet before claiming success."""
        timestamp = int(time.time() if now is None else now)
        ticket_id = "T-" + secrets.token_hex(8).upper()
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("DELETE FROM tickets WHERE created_at < ?", (timestamp - self.retention_seconds,))
                if fail_write:
                    raise sqlite3.OperationalError("simulated write failure")
                connection.execute(
                    """INSERT INTO tickets (ticket_id, owner, session_scope, request_key, created_at, packet)
                       VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(owner, session_scope, request_key) DO NOTHING""",
                    (ticket_id, owner, session_scope, request_key, timestamp, json.dumps(packet, ensure_ascii=False)),
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
            return row[0], confirmed
        except (OSError, sqlite3.Error) as exc:
            raise TicketStoreError("ticket queue unavailable") from exc

    def read(self, owner, session_scope, ticket_id, *, now=None):
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
