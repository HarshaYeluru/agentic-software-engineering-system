from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


class LinkStore:
    """Small SQLite repository used by the local reference service."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)

    def initialize(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS links (
                    code TEXT PRIMARY KEY,
                    destination_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                );
                CREATE TABLE IF NOT EXISTS click_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY (code) REFERENCES links(code)
                );
                CREATE INDEX IF NOT EXISTS idx_click_events_code ON click_events(code);
                """
            )

    def create_link(self, code: str, destination_url: str, expires_at: str | None = None) -> bool:
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute(
                    "INSERT INTO links(code, destination_url, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (code, destination_url, self._now(), expires_at),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def find_active_link(self, code: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT destination_url, expires_at FROM links WHERE code = ?", (code,)
            ).fetchone()
        if row is None or (row["expires_at"] is not None and row["expires_at"] <= self._now()):
            return None
        return str(row["destination_url"])

    def record_click(self, code: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO click_events(code, occurred_at) VALUES (?, ?)", (code, self._now())
            )

    def ping(self) -> bool:
        """Cheap connectivity check used by the readiness probe."""
        try:
            with closing(self._connect()) as connection:
                connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def analytics(self, code: str) -> int | None:
        with closing(self._connect()) as connection:
            link = connection.execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone()
            if link is None:
                return None
            return int(connection.execute("SELECT COUNT(*) FROM click_events WHERE code = ?", (code,)).fetchone()[0])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        # Foreign keys are disabled by default in SQLite, even when declared in the schema.
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
