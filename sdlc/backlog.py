"""
BacklogStore — persistent CRUD for product backlog items.

Supports: add, update status/priority, list with filters, prioritise,
          assign to sprint, search by keyword.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from sdlc.models import BacklogItem, ITEM_TYPES, PRIORITIES, ITEM_STATUSES
from utils.logger import log


class BacklogStore:

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_table()

    def _init_table(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS backlog_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                type        TEXT    NOT NULL DEFAULT 'task',
                priority    TEXT    NOT NULL DEFAULT 'medium',
                status      TEXT    NOT NULL DEFAULT 'new',
                description TEXT    DEFAULT '',
                sprint_id   INTEGER,
                tags        TEXT    DEFAULT '',
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            )
        """)
        self.conn.commit()

    # ──────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────

    def add(
        self,
        title: str,
        type: str = "task",
        priority: str = "medium",
        description: str = "",
        tags: str = "",
    ) -> BacklogItem:
        type     = type     if type     in ITEM_TYPES  else "task"
        priority = priority if priority in PRIORITIES  else "medium"
        now = datetime.utcnow().isoformat()
        cur = self.conn.execute("""
            INSERT INTO backlog_items (title, type, priority, description, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, type, priority, description, tags, now, now))
        self.conn.commit()
        item = self.get(cur.lastrowid)
        log("SDLC", f"Backlog: added [{item.id:03d}] {type}/{priority} — {title!r}")
        return item

    def update_status(self, item_id: int, status: str) -> bool:
        if status not in ITEM_STATUSES:
            return False
        self.conn.execute("""
            UPDATE backlog_items SET status=?, updated_at=? WHERE id=?
        """, (status, datetime.utcnow().isoformat(), item_id))
        self.conn.commit()
        log("SDLC", f"Backlog [{item_id:03d}]: status → {status}")
        return True

    def update_priority(self, item_id: int, priority: str) -> bool:
        if priority not in PRIORITIES:
            return False
        self.conn.execute("""
            UPDATE backlog_items SET priority=?, updated_at=? WHERE id=?
        """, (priority, datetime.utcnow().isoformat(), item_id))
        self.conn.commit()
        return True

    def assign_sprint(self, item_id: int, sprint_id: int) -> None:
        self.conn.execute("""
            UPDATE backlog_items SET sprint_id=?, status='ready', updated_at=? WHERE id=?
        """, (sprint_id, datetime.utcnow().isoformat(), item_id))
        self.conn.commit()

    def update(self, item_id: int, **kwargs) -> None:
        allowed = {"title", "type", "priority", "status", "description", "tags"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        self.conn.execute(
            f"UPDATE backlog_items SET {set_clause} WHERE id=?",
            list(updates.values()) + [item_id]
        )
        self.conn.commit()

    # ──────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────

    def get(self, item_id: int) -> Optional[BacklogItem]:
        cur = self.conn.execute(
            "SELECT * FROM backlog_items WHERE id=?", (item_id,)
        )
        row = cur.fetchone()
        return BacklogItem.from_row(dict(row)) if row else None

    def list(
        self,
        status: Optional[str] = None,
        type: Optional[str] = None,
        priority: Optional[str] = None,
        sprint_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[BacklogItem]:
        conditions, params = [], []
        if status:    conditions.append("status=?");    params.append(status)
        if type:      conditions.append("type=?");      params.append(type)
        if priority:  conditions.append("priority=?");  params.append(priority)
        if sprint_id is not None:
            conditions.append("sprint_id=?");           params.append(sprint_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur = self.conn.execute(f"""
            SELECT * FROM backlog_items {where}
            ORDER BY
              CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                            WHEN 'medium'   THEN 2 WHEN 'low'  THEN 3 ELSE 4 END,
              created_at DESC
            LIMIT ?
        """, params + [limit])
        return [BacklogItem.from_row(dict(r)) for r in cur.fetchall()]

    def search(self, keyword: str) -> List[BacklogItem]:
        like = f"%{keyword}%"
        cur = self.conn.execute("""
            SELECT * FROM backlog_items
            WHERE title LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY created_at DESC LIMIT 20
        """, (like, like, like))
        return [BacklogItem.from_row(dict(r)) for r in cur.fetchall()]

    def count_by_status(self) -> dict:
        cur = self.conn.execute("""
            SELECT status, COUNT(*) as n FROM backlog_items GROUP BY status
        """)
        return {row["status"]: row["n"] for row in cur.fetchall()}

    def unassigned(self) -> List[BacklogItem]:
        """Items not assigned to any sprint and not done/cancelled."""
        cur = self.conn.execute("""
            SELECT * FROM backlog_items
            WHERE sprint_id IS NULL AND status NOT IN ('done','cancelled')
            ORDER BY
              CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                            WHEN 'medium'   THEN 2 WHEN 'low'  THEN 3 ELSE 4 END
        """)
        return [BacklogItem.from_row(dict(r)) for r in cur.fetchall()]
