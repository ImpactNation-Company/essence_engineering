"""Database bootstrap helpers for SDLC tables."""
from __future__ import annotations

import sqlite3

from sdlc.backlog import BacklogStore
from sdlc.issues import IssueStore
from sdlc.sprint import SprintStore


def initialize_sdlc(conn: sqlite3.Connection) -> None:
    """Create all SDLC tables required by commands and reports."""
    BacklogStore(conn)
    SprintStore(conn)
    IssueStore(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            diff_hash   TEXT,
            summary     TEXT,
            concerns    TEXT,
            suggestions TEXT,
            severity    TEXT,
            verdict     TEXT,
            raw         TEXT,
            timestamp   TEXT NOT NULL
        )
    """)
    conn.commit()
