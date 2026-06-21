"""
SprintStore — sprint lifecycle management.

Supports: create, start, close, list, item management, velocity tracking.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from sdlc.models import Sprint, SPRINT_STATUSES
from utils.logger import log


class SprintStore:

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_table()

    def _init_table(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sprints (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                goal       TEXT    DEFAULT '',
                status     TEXT    NOT NULL DEFAULT 'planned',
                start_date TEXT    DEFAULT '',
                end_date   TEXT    DEFAULT '',
                velocity   INTEGER DEFAULT 0,
                created_at TEXT    NOT NULL
            )
        """)
        self.conn.commit()

    # ──────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────

    def create(self, name: str, goal: str = "", end_date: str = "") -> Sprint:
        now = datetime.utcnow().isoformat()
        cur = self.conn.execute("""
            INSERT INTO sprints (name, goal, status, end_date, created_at)
            VALUES (?, ?, 'planned', ?, ?)
        """, (name, goal, end_date, now))
        self.conn.commit()
        sprint = self.get(cur.lastrowid)
        log("SDLC", f"Sprint created: [{sprint.id}] {name!r}")
        return sprint

    def start(self, sprint_id: int) -> bool:
        """Activate a sprint. Only one sprint can be active at a time."""
        active = self.active()
        if active and active.id != sprint_id:
            log("SDLC", f"Cannot start sprint {sprint_id}: sprint {active.id} is already active")
            return False
        now = datetime.utcnow().isoformat()
        self.conn.execute("""
            UPDATE sprints SET status='active', start_date=? WHERE id=?
        """, (now, sprint_id))
        self.conn.commit()
        log("SDLC", f"Sprint [{sprint_id}] started")
        return True

    def close(self, sprint_id: int) -> Sprint:
        """Mark sprint as completed and tally velocity."""
        # Count done items in this sprint
        cur = self.conn.execute("""
            SELECT COUNT(*) as n FROM backlog_items
            WHERE sprint_id=? AND status='done'
        """, (sprint_id,))
        velocity = cur.fetchone()["n"]
        self.conn.execute("""
            UPDATE sprints SET status='completed', velocity=? WHERE id=?
        """, (velocity, sprint_id))
        self.conn.commit()
        sprint = self.get(sprint_id)
        log("SDLC", f"Sprint [{sprint_id}] closed — velocity={velocity}")
        return sprint

    def update_goal(self, sprint_id: int, goal: str) -> None:
        self.conn.execute("UPDATE sprints SET goal=? WHERE id=?", (goal, sprint_id))
        self.conn.commit()

    # ──────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────

    def get(self, sprint_id: int) -> Optional[Sprint]:
        cur = self.conn.execute("SELECT * FROM sprints WHERE id=?", (sprint_id,))
        row = cur.fetchone()
        return Sprint.from_row(dict(row)) if row else None

    def active(self) -> Optional[Sprint]:
        cur = self.conn.execute("SELECT * FROM sprints WHERE status='active' LIMIT 1")
        row = cur.fetchone()
        return Sprint.from_row(dict(row)) if row else None

    def list(self, status: Optional[str] = None, limit: int = 20) -> List[Sprint]:
        if status:
            cur = self.conn.execute(
                "SELECT * FROM sprints WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit)
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM sprints ORDER BY id DESC LIMIT ?", (limit,)
            )
        return [Sprint.from_row(dict(r)) for r in cur.fetchall()]

    def items_in_sprint(self, sprint_id: int) -> List[dict]:
        cur = self.conn.execute("""
            SELECT id, title, type, priority, status FROM backlog_items
            WHERE sprint_id=?
            ORDER BY CASE status
              WHEN 'in_progress' THEN 0 WHEN 'review' THEN 1
              WHEN 'ready' THEN 2 WHEN 'done' THEN 3 ELSE 4 END
        """, (sprint_id,))
        return [dict(r) for r in cur.fetchall()]

    def burndown(self, sprint_id: int) -> dict:
        """Return a simple burndown summary for the sprint."""
        items = self.items_in_sprint(sprint_id)
        total = len(items)
        done  = sum(1 for i in items if i["status"] == "done")
        remaining = total - done
        pct = round(done / total * 100) if total else 0
        return {
            "total": total,
            "done": done,
            "remaining": remaining,
            "pct_complete": pct,
        }
