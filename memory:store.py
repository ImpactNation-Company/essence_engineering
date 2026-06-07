import sqlite3
import json
from utils.logger import log

class MemoryStore:

    def __init__(self, db_path="essence.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            response TEXT,
            reasoning TEXT
        )
        """)
        self.conn.commit()

    def store(self, query, response, reasoning):
        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO memory (query, response, reasoning)
        VALUES (?, ?, ?)
        """, (
            query,
            json.dumps(response),
            json.dumps(reasoning)
        ))

        self.conn.commit()

        log("MEM", "Stored memory record")