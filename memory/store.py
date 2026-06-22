"""
Enhanced MemoryStore — persistent episodic memory with recall and search.

Schema (auto-migrated):
  id, query, response, reasoning, reflection, timestamp
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.logger import log


class MemoryStore:

    def __init__(self, db_path: str = "essence.db", conn: sqlite3.Connection | None = None):
        self.db_path = db_path
        if conn is None:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        else:
            self.conn = conn
        self.fts_enabled = self.init_schema(self.conn)
        log("MEM", f"Connected to DB: {db_path}")

    # ──────────────────────────────────────────
    # Schema
    # ──────────────────────────────────────────

    @classmethod
    def init_schema(cls, conn: sqlite3.Connection) -> bool:
        cur = conn.cursor()
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
        conn.commit()
        cls._migrate(conn)
        return cls._init_fts(conn)

    @classmethod
    def _migrate(cls, conn: sqlite3.Connection) -> None:
        """Add new columns to existing databases without dropping data."""
        cur = conn.cursor()
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
        conn.commit()

    @classmethod
    def _init_fts(cls, conn: sqlite3.Connection) -> bool:
        """Initialize deterministic full-text recall when SQLite has FTS5."""
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(query, response)
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_ai
                AFTER INSERT ON memory BEGIN
                    INSERT INTO memory_fts(rowid, query, response)
                    VALUES (new.id, new.query, coalesce(new.response, ''));
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_ad
                AFTER DELETE ON memory BEGIN
                    DELETE FROM memory_fts WHERE rowid = old.id;
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_au
                AFTER UPDATE ON memory BEGIN
                    UPDATE memory_fts
                    SET query = new.query, response = coalesce(new.response, '')
                    WHERE rowid = new.id;
                END
            """)
            conn.execute("""
                INSERT INTO memory_fts(rowid, query, response)
                SELECT id, query, coalesce(response, '')
                FROM memory
                WHERE id NOT IN (SELECT rowid FROM memory_fts)
            """)
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            log("MEM", f"FTS recall disabled: {e}")
            return False

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
        Retrieve memory entries.
        If query is non-empty, prefer FTS5 ranking and fall back to keyword overlap.
        """
        if query and self.fts_enabled:
            records = self._recall_fts(query, limit)
            if records:
                return records

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
        qwords = set(_tokenize(query))
        def score(rec: Dict) -> int:
            rwords = set(_tokenize(rec.get("query", "") + " " + rec.get("response", "")))
            return len(qwords & rwords)
        return sorted(records, key=score, reverse=True)

    def _recall_fts(self, query: str, limit: int) -> List[Dict]:
        terms = _tokenize(query)
        if not terms:
            return []
        match_query = " OR ".join(terms[:12])
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT m.id, m.query, m.response, m.reasoning, m.reflection, m.timestamp
                FROM memory_fts
                JOIN memory AS m ON m.id = memory_fts.rowid
                WHERE memory_fts MATCH ?
                ORDER BY bm25(memory_fts), m.id DESC
                LIMIT ?
            """, (match_query, limit))
            return [self._row_to_dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError as e:
            log("MEM", f"FTS recall failed, falling back: {e}")
            return []


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "what", "when",
    "where", "how", "why", "your", "you", "are", "was", "were", "have",
    "has", "had", "into", "about", "can", "could", "would", "should",
}


def _tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    seen = set()
    tokens = []
    for word in words:
        if word in _STOPWORDS or word in seen:
            continue
        seen.add(word)
        tokens.append(word)
    return tokens
