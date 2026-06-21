"""
CodeReviewer — sends git diffs or code snippets to the LLM for structured review.

Review output schema:
  summary, concerns[], suggestions[], severity, verdict
"""
from __future__ import annotations

import sqlite3
import subprocess
from datetime import datetime
from hashlib import md5
from typing import Optional

from utils.logger import log


REVIEW_PROMPT = """You are a senior code reviewer for the Essence project.

Review the following code diff and provide a structured response with exactly these sections:

## Summary
One paragraph describing what the change does.

## Concerns
Bullet list of potential problems: bugs, security issues, missing error handling,
broken tests, bad patterns. If none, write "None identified."

## Suggestions
Bullet list of concrete improvements. If none, write "None."

## Severity
One of: CRITICAL | HIGH | MEDIUM | LOW | APPROVED
- CRITICAL: blocking bugs or security holes
- HIGH: significant issues that should be fixed before merge
- MEDIUM: improvements recommended but not blocking
- LOW: minor style/naming issues
- APPROVED: looks good, ready to merge

## Verdict
One sentence: approve, request changes, or block.
"""


class CodeReviewer:

    def __init__(self, conn: sqlite3.Connection, llm_caller, project_path: str = "."):
        """
        Args:
            llm_caller:    Callable(prompt: str) -> str — wraps the LLM agent call
            project_path:  Path to the Essence repo for git operations
        """
        self.conn = conn
        self.llm  = llm_caller
        self.path = project_path
        self._init_table()

    def _init_table(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                diff_hash TEXT,
                summary   TEXT,
                concerns  TEXT,
                suggestions TEXT,
                severity  TEXT,
                verdict   TEXT,
                raw       TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        self.conn.commit()

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def review_diff(self, diff: str, context: str = "") -> dict:
        """Review an arbitrary diff string."""
        diff_hash = md5(diff.encode()).hexdigest()[:12]
        prompt = f"{REVIEW_PROMPT}\n\n```diff\n{diff[:6000]}\n```"
        if context:
            prompt += f"\n\nContext: {context}"
        raw = self.llm(prompt)
        result = self._parse_review(raw)
        self._store(diff_hash, result, raw)
        log("SDLC", f"Review complete: severity={result.get('severity','?')}")
        return result

    def review_latest_git(self, n_commits: int = 1) -> dict:
        """Review the latest N commit diffs from the Essence repo."""
        diff = self._git_diff(n_commits)
        if not diff:
            return {"error": "No git diff available — is ESSENCE_PATH set correctly?"}
        return self.review_diff(diff)

    def review_file(self, file_path: str) -> dict:
        """Review the full content of a specific file."""
        try:
            with open(file_path, "r") as f:
                content = f.read()
            return self.review_diff(f"# File: {file_path}\n{content}")
        except FileNotFoundError:
            return {"error": f"File not found: {file_path}"}

    def last_reviews(self, limit: int = 5) -> list:
        cur = self.conn.execute("""
            SELECT id, severity, verdict, timestamp FROM reviews
            ORDER BY id DESC LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]

    # ──────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────

    def _git_diff(self, n: int) -> str:
        try:
            result = subprocess.run(
                ["git", "diff", f"HEAD~{n}", "HEAD"],
                capture_output=True, text=True,
                cwd=self.path, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
            # Fallback: staged changes
            result = subprocess.run(
                ["git", "diff", "--staged"],
                capture_output=True, text=True,
                cwd=self.path, timeout=5
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            log("SDLC", f"git diff error: {e}")
            return ""

    def _parse_review(self, raw: str) -> dict:
        sections = {"summary": "", "concerns": "", "suggestions": "", "severity": "MEDIUM", "verdict": ""}
        current = None
        lines = raw.splitlines()
        buf = []
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            if "## summary" in lower:
                if current: sections[current] = "\n".join(buf).strip()
                current, buf = "summary", []
            elif "## concerns" in lower:
                if current: sections[current] = "\n".join(buf).strip()
                current, buf = "concerns", []
            elif "## suggestions" in lower:
                if current: sections[current] = "\n".join(buf).strip()
                current, buf = "suggestions", []
            elif "## severity" in lower:
                if current: sections[current] = "\n".join(buf).strip()
                current, buf = "severity", []
            elif "## verdict" in lower:
                if current: sections[current] = "\n".join(buf).strip()
                current, buf = "verdict", []
            else:
                if current:
                    buf.append(line)
        if current:
            sections[current] = "\n".join(buf).strip()

        # Clean severity to enum value
        sev = sections.get("severity", "").upper()
        for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "APPROVED"):
            if s in sev:
                sections["severity"] = s
                break
        sections["raw"] = raw
        return sections

    def _store(self, diff_hash: str, result: dict, raw: str) -> None:
        now = datetime.utcnow().isoformat()
        self.conn.execute("""
            INSERT INTO reviews (diff_hash, summary, concerns, suggestions, severity, verdict, raw, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            diff_hash,
            result.get("summary", ""),
            result.get("concerns", ""),
            result.get("suggestions", ""),
            result.get("severity", ""),
            result.get("verdict", ""),
            raw, now,
        ))
        self.conn.commit()
