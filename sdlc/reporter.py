"""
ProjectReporter — generates sprint status, project health, and standup reports.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from sdlc.models import Sprint
from utils.logger import log


class ProjectReporter:

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ──────────────────────────────────────────
    # Sprint Report
    # ──────────────────────────────────────────

    def sprint_report(self, sprint_id: Optional[int] = None) -> str:
        """Full sprint status report. Uses active sprint if sprint_id is None."""
        sprint = self._get_sprint(sprint_id)
        if not sprint:
            return "⚠️  No active sprint. Start one with: `python main.py sprint start \"Sprint Name\"`"

        items = self._sprint_items(sprint.id)
        burndown = self._burndown(sprint.id)

        lines = [
            f"# Sprint Report: {sprint.name}",
            f"**Goal:** {sprint.goal or 'No goal set'}",
            f"**Status:** {sprint.status.upper()}",
            f"**Started:** {sprint.start_date[:10] if sprint.start_date else 'Not started'}",
            f"**End Date:** {sprint.end_date[:10] if sprint.end_date else 'Not set'}",
            "",
            f"## Progress: {burndown['done']}/{burndown['total']} items complete ({burndown['pct_complete']}%)",
            self._progress_bar(burndown['pct_complete']),
            "",
        ]

        # Group items by status
        groups = {"in_progress": [], "review": [], "ready": [], "done": [], "new": []}
        for item in items:
            groups.setdefault(item["status"], []).append(item)

        icons = {
            "in_progress": "🔄 In Progress",
            "review":      "👀 In Review",
            "ready":       "📋 Ready",
            "done":        "✅ Done",
            "new":         "🆕 New",
        }
        for status, label in icons.items():
            if groups.get(status):
                lines.append(f"### {label}")
                for i in groups[status]:
                    pri = {"critical":"🔴","high":"🟠","medium":"🟡","low":"🟢"}.get(i["priority"],"")
                    lines.append(f"- [{i['id']:03d}] {pri} {i['title']} ({i['type']})")
                lines.append("")

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # Project Summary
    # ──────────────────────────────────────────

    def project_summary(self) -> str:
        backlog_counts = self._count_table("backlog_items", "status")
        issue_counts   = self._count_table("issues", "status")
        sprint_counts  = self._count_table("sprints", "status")
        review_counts  = self._count_table("reviews", "severity")
        total_backlog  = sum(backlog_counts.values())
        open_issues    = issue_counts.get("open", 0) + issue_counts.get("in_progress", 0)
        critical_issues = self._critical_issue_count()
        active_sprint  = self._active_sprint_name()

        lines = [
            "# Essence Project — Health Report",
            f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
            "",
            "## Backlog",
            f"| Status | Count |",
            f"|--------|-------|",
        ]
        for status in ("new", "ready", "in_progress", "review", "done", "cancelled"):
            n = backlog_counts.get(status, 0)
            if n:
                lines.append(f"| {status} | {n} |")
        lines += [
            "",
            f"**Total items:** {total_backlog}",
            "",
            "## Sprints",
            f"- Active: **{active_sprint or 'None'}**",
            f"- Completed: {sprint_counts.get('completed', 0)}",
            f"- Planned: {sprint_counts.get('planned', 0)}",
            "",
            "## Issues",
            f"- 🔴 Open (total): **{open_issues}**",
            f"- 🚨 Critical open: **{critical_issues}**",
            f"- ✅ Resolved: {issue_counts.get('resolved', 0)}",
            "",
            "## Code Reviews",
        ]
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "APPROVED"):
            n = review_counts.get(sev, 0)
            if n:
                lines.append(f"- {sev}: {n}")

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # Daily Standup
    # ──────────────────────────────────────────

    def daily_standup(self) -> str:
        sprint = self._active_sprint()

        done_today    = self._items_by_status_today("done")
        in_progress   = self._items_by_status("in_progress")
        open_blockers = self._critical_issues_list()

        lines = [
            "# Daily Standup",
            f"*{datetime.utcnow().strftime('%A, %B %d %Y')}*",
            "",
            f"**Sprint:** {sprint.name if sprint else 'No active sprint'}",
            "",
            "## ✅ Completed Today",
        ]
        if done_today:
            lines += [f"- {i['title']}" for i in done_today]
        else:
            lines.append("- Nothing marked done today")

        lines += ["", "## 🔄 In Progress"]
        if in_progress:
            lines += [f"- [{i['id']:03d}] {i['title']}" for i in in_progress]
        else:
            lines.append("- Nothing in progress")

        lines += ["", "## 🚨 Blockers / Critical Issues"]
        if open_blockers:
            lines += [f"- [{i['id']:03d}] {i['title']} [{i['severity']}]" for i in open_blockers]
        else:
            lines.append("- No blockers 🎉")

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    def _get_sprint(self, sprint_id: Optional[int]) -> Optional[Sprint]:
        if sprint_id:
            cur = self.conn.execute("SELECT * FROM sprints WHERE id=?", (sprint_id,))
        else:
            cur = self.conn.execute("SELECT * FROM sprints WHERE status='active' LIMIT 1")
        row = cur.fetchone()
        return Sprint.from_row(dict(row)) if row else None

    def _active_sprint(self) -> Optional[Sprint]:
        return self._get_sprint(None)

    def _active_sprint_name(self) -> Optional[str]:
        s = self._active_sprint()
        return s.name if s else None

    def _sprint_items(self, sprint_id: int) -> list:
        cur = self.conn.execute("""
            SELECT id, title, type, priority, status FROM backlog_items WHERE sprint_id=?
        """, (sprint_id,))
        return [dict(r) for r in cur.fetchall()]

    def _burndown(self, sprint_id: int) -> dict:
        items = self._sprint_items(sprint_id)
        total = len(items)
        done  = sum(1 for i in items if i["status"] == "done")
        return {"total": total, "done": done, "pct_complete": round(done/total*100) if total else 0}

    def _count_table(self, table: str, group_col: str) -> dict:
        try:
            cur = self.conn.execute(f"SELECT {group_col}, COUNT(*) as n FROM {table} GROUP BY {group_col}")
            return {row[group_col]: row["n"] for row in cur.fetchall()}
        except Exception:
            return {}

    def _critical_issue_count(self) -> int:
        cur = self.conn.execute(
            "SELECT COUNT(*) as n FROM issues WHERE severity='critical' AND status='open'"
        )
        return cur.fetchone()["n"]

    def _critical_issues_list(self) -> list:
        cur = self.conn.execute("""
            SELECT id, title, severity FROM issues
            WHERE status IN ('open','in_progress') AND severity IN ('critical','high')
            ORDER BY CASE severity WHEN 'critical' THEN 0 ELSE 1 END
            LIMIT 10
        """)
        return [dict(r) for r in cur.fetchall()]

    def _items_by_status(self, status: str) -> list:
        cur = self.conn.execute("""
            SELECT id, title FROM backlog_items WHERE status=? LIMIT 10
        """, (status,))
        return [dict(r) for r in cur.fetchall()]

    def _items_by_status_today(self, status: str) -> list:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cur = self.conn.execute("""
            SELECT id, title FROM backlog_items
            WHERE status=? AND updated_at LIKE ? LIMIT 10
        """, (status, f"{today}%"))
        return [dict(r) for r in cur.fetchall()]

    def _progress_bar(self, pct: int, width: int = 30) -> str:
        filled = round(pct / 100 * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"`[{bar}] {pct}%`"
