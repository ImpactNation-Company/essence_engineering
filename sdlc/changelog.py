"""
ChangelogGenerator — auto-generates CHANGELOG.md from backlog + git history.

Output format: Keep a Changelog (https://keepachangelog.com)
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
from datetime import datetime
from typing import List, Optional

from sdlc.database import initialize_sdlc
from utils.logger import log


class ChangelogGenerator:

    def __init__(self, conn: sqlite3.Connection, project_path: str = "."):
        self.conn = conn
        self.project_path = project_path
        initialize_sdlc(conn)

    def generate(
        self,
        version: str = "Unreleased",
        since_sprint_id: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a CHANGELOG entry.

        Args:
            version:          Version string (e.g. "0.1.0") or "Unreleased"
            since_sprint_id:  Include items completed in this sprint
            output_path:      If set, append to CHANGELOG.md at this path

        Returns:
            The generated changelog string.
        """
        added, changed, fixed, removed = self._gather_items(since_sprint_id)
        git_entries = self._get_git_log()

        today = datetime.utcnow().strftime("%Y-%m-%d")
        lines = [
            f"## [{version}] — {today}",
            "",
        ]

        if added:
            lines += ["### Added"] + [f"- {t}" for t in added] + [""]
        if changed:
            lines += ["### Changed"] + [f"- {t}" for t in changed] + [""]
        if fixed:
            lines += ["### Fixed"] + [f"- {t}" for t in fixed] + [""]
        if removed:
            lines += ["### Removed"] + [f"- {t}" for t in removed] + [""]

        if git_entries:
            lines += ["### Commits"]
            lines += [f"- {e}" for e in git_entries[:10]]
            lines += [""]

        content = "\n".join(lines)

        if output_path:
            self._prepend_to_file(output_path, content)
            log("SDLC", f"Changelog written to {output_path}")

        return content

    # ──────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────

    def _gather_items(self, sprint_id: Optional[int]) -> tuple:
        added, changed, fixed, removed = [], [], [], []

        if sprint_id is not None:
            cur = self.conn.execute("""
                SELECT title, type FROM backlog_items
                WHERE sprint_id=? AND status='done'
            """, (sprint_id,))
        else:
            cur = self.conn.execute("""
                SELECT title, type FROM backlog_items WHERE status='done'
            """)

        for row in cur.fetchall():
            t, typ = row["title"], row["type"]
            if typ == "feature":  added.append(t)
            elif typ == "debt":   changed.append(t)
            elif typ == "bug":    fixed.append(t)
            else:                 changed.append(t)

        return added, changed, fixed, removed

    def _get_git_log(self, n: int = 15) -> List[str]:
        try:
            result = subprocess.run(
                ["git", "log", f"-{n}", "--oneline", "--no-merges"],
                capture_output=True, text=True,
                cwd=self.project_path, timeout=5
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        except Exception:
            pass
        return []

    def _prepend_to_file(self, path: str, content: str) -> None:
        header = "# Changelog\nAll notable changes to the Essence project.\n\n"
        existing = ""
        if os.path.exists(path):
            with open(path, "r") as f:
                existing = f.read()
            # Remove the header if it already exists
            if existing.startswith("# Changelog"):
                existing = existing[existing.find("\n## "):] if "\n## " in existing else ""

        with open(path, "w") as f:
            f.write(header + content + "\n" + existing)
