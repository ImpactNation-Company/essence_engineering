"""Read-only SDLC tools for Forge."""
from __future__ import annotations

from core.database import open_database
from sdlc.reporter import ProjectReporter
from tools.base import Tool


class SDLCReportTool(Tool):
    name = "sdlc_report"
    description = (
        "Generate an SDLC report from Forge's database. "
        "Args: project, standup, or sprint[:id]. Example: sdlc_report(project)"
    )

    def __init__(self, db_path: str):
        self.db_path = db_path

    def run(self, input_str: str) -> str:
        mode = (input_str or "project").strip().lower()
        conn = open_database(self.db_path)
        try:
            reporter = ProjectReporter(conn)
            if mode in ("project", "summary", "health", ""):
                return reporter.project_summary()
            if mode in ("standup", "daily"):
                return reporter.daily_standup()
            if mode.startswith("sprint"):
                sprint_id = None
                if ":" in mode:
                    _, raw_id = mode.split(":", 1)
                    raw_id = raw_id.strip()
                    sprint_id = int(raw_id) if raw_id.isdigit() else None
                return reporter.sprint_report(sprint_id)
            return "[SDLC] Unknown report type. Use project, standup, or sprint[:id]."
        finally:
            conn.close()
