"""
IssueStore — bug/blocker/risk tracking linked to backlog items.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from sdlc.models import Issue, ISSUE_TYPES, SEVERITIES, ISSUE_STATUSES
from utils.logger import log


class IssueStore:

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_table()

    def _init_table(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT    NOT NULL,
                type            TEXT    NOT NULL DEFAULT 'bug',
                severity        TEXT    NOT NULL DEFAULT 'medium',
                status          TEXT    NOT NULL DEFAULT 'open',
                description     TEXT    DEFAULT '',
                backlog_item_id INTEGER,
                notes           TEXT    DEFAULT '',
                created_at      TEXT    NOT NULL,
                resolved_at     TEXT    DEFAULT ''
            )
        """)
        self.conn.commit()

    # ──────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────

    def report(
        self,
        title: str,
        type: str = "bug",
        severity: str = "medium",
        description: str = "",
        backlog_item_id: Optional[int] = None,
    ) -> Issue:
        type     = type     if type     in ISSUE_TYPES else "bug"
        severity = severity if severity in SEVERITIES  else "medium"
        now = datetime.utcnow().isoformat()
        cur = self.conn.execute("""
            INSERT INTO issues (title, type, severity, description, backlog_item_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, type, severity, description, backlog_item_id, now))
        self.conn.commit()
        issue = self.get(cur.lastrowid)
        log("SDLC", f"Issue [{issue.id:03d}] reported: {severity}/{type} — {title!r}")
        return issue

    def resolve(self, issue_id: int, notes: str = "") -> bool:
        now = datetime.utcnow().isoformat()
        self.conn.execute("""
            UPDATE issues SET status='resolved', resolved_at=?, notes=? WHERE id=?
        """, (now, notes, issue_id))
        self.conn.commit()
        log("SDLC", f"Issue [{issue_id:03d}] resolved")
        return True

    def update_status(self, issue_id: int, status: str) -> bool:
        if status not in ISSUE_STATUSES:
            return False
        now = datetime.utcnow().isoformat()
        resolved_at = now if status == "resolved" else ""
        self.conn.execute("""
            UPDATE issues SET status=?, resolved_at=? WHERE id=?
        """, (status, resolved_at, issue_id))
        self.conn.commit()
        return True

    def add_note(self, issue_id: int, note: str) -> None:
        cur = self.conn.execute("SELECT notes FROM issues WHERE id=?", (issue_id,))
        row = cur.fetchone()
        if row:
            existing = row["notes"] or ""
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            new_notes = f"{existing}\n[{ts}] {note}".strip()
            self.conn.execute("UPDATE issues SET notes=? WHERE id=?", (new_notes, issue_id))
            self.conn.commit()

    # ──────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────

    def get(self, issue_id: int) -> Optional[Issue]:
        cur = self.conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,))
        row = cur.fetchone()
        return Issue.from_row(dict(row)) if row else None

    def list(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Issue]:
        conditions, params = [], []
        if status:   conditions.append("status=?");   params.append(status)
        if severity: conditions.append("severity=?"); params.append(severity)
        if type:     conditions.append("type=?");     params.append(type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur = self.conn.execute(f"""
            SELECT * FROM issues {where}
            ORDER BY
              CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                            WHEN 'medium'   THEN 2 WHEN 'low'  THEN 3 ELSE 4 END,
              created_at DESC
            LIMIT ?
        """, params + [limit])
        return [Issue.from_row(dict(r)) for r in cur.fetchall()]

    def open_issues(self) -> List[Issue]:
        return self.list(status="open")

    def critical_issues(self) -> List[Issue]:
        return self.list(severity="critical", status="open")

    def count_by_status(self) -> dict:
        cur = self.conn.execute("SELECT status, COUNT(*) as n FROM issues GROUP BY status")
        return {row["status"]: row["n"] for row in cur.fetchall()}
