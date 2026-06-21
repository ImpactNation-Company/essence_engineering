"""
Enhanced MemoryStore — persistent episodic memory with recall and search.

Schema (auto-migrated):
  id, query, response, reasoning, reflection, timestamp
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import log


class MemoryStore:

    def __init__(self, db_path: str = "essence.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        log("MEM", f"Connected to DB: {db_path}")

    # ──────────────────────────────────────────
    # Schema
    # ──────────────────────────────────────────

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                query      TEXT    NOT NULL,
                response   TEXT,
                reasoning  TEXT,
                reflection TEXT,
                timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self.conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Add new columns to existing databases without dropping data."""
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(memory)")
        existing_cols = {row["name"] for row in cur.fetchall()}
        additions = {
            "reflection": "TEXT",
            "timestamp":  "TEXT NOT NULL DEFAULT (datetime('now'))",
        }
        for col, typedef in additions.items():
            if col not in existing_cols:
                cur.execute(f"ALTER TABLE memory ADD COLUMN {col} {typedef}")
                log("MEM", f"Migrated DB: added column '{col}'")
        self.conn.commit()

    # ──────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────

    def store(
        self,
        query: str,
        response: Any,
        reasoning: Any,
        reflection: Optional[Any] = None,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO memory (query, response, reasoning, reflection, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            query,
            response if isinstance(response, str) else json.dumps(response),
            json.dumps(reasoning),
            json.dumps(reflection) if reflection else None,
            datetime.utcnow().isoformat(),
        ))
        self.conn.commit()
        record_id = cur.lastrowid
        log("MEM", f"Stored record id={record_id}")
        return record_id

    # ──────────────────────────────────────────
    # Read / Recall
    # ──────────────────────────────────────────

    def recall(self, query: str = "", limit: int = 5) -> List[Dict]:
        """
        Retrieve the most recent memory entries.
        If query is non-empty, score by keyword overlap (basic BM25 approximation).
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, query, response, reasoning, reflection, timestamp
            FROM memory
            ORDER BY id DESC
            LIMIT ?
        """, (limit * 3,))  # Fetch extra so we can re-rank
        rows = cur.fetchall()

        records = [self._row_to_dict(r) for r in rows]

        if query:
            records = self._rank_by_relevance(records, query)

        return records[:limit]

    def search(self, keyword: str, limit: int = 10) -> List[Dict]:
        """Basic keyword search across queries and responses."""
        like = f"%{keyword}%"
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, query, response, reasoning, reflection, timestamp
            FROM memory
            WHERE query LIKE ? OR response LIKE ?
            ORDER BY id DESC
            LIMIT ?
        """, (like, like, limit))
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def all_records(self, limit: int = 50) -> List[Dict]:
        """Fetch all records for history display."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, query, response, timestamp
            FROM memory
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM memory")
        return cur.fetchone()["c"]

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        d = dict(row)
        for key in ("reasoning", "reflection"):
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    def _rank_by_relevance(self, records: List[Dict], query: str) -> List[Dict]:
        """Score records by keyword overlap with current query."""
        qwords = set(query.lower().split())
        def score(rec: Dict) -> int:
            rwords = set((rec.get("query", "") + " " + rec.get("response", "")).lower().split())
            return len(qwords & rwords)
        return sorted(records, key=score, reverse=True)
