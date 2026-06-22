"""Shared SQLite bootstrap for Forge."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from config import settings
from memory.store import MemoryStore
from sdlc.database import initialize_sdlc


def open_database(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open the Forge database and initialize all known schemas."""
    path = str(Path(db_path or settings.db_path))
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    initialize_database(conn)
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    """Initialize memory plus SDLC tables on an existing connection."""
    MemoryStore.init_schema(conn)
    initialize_sdlc(conn)
