"""
ToolRegistry — discovers, registers, and dispatches tool calls.

Default tools registered:
  calculator, web_search, git_status, git_log, git_diff, read_file, list_dir

Tools are auto-parsed from agent output matching:
    TOOL_CALL: <tool_name>(<args>)
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from config import settings
from tools.base import Tool
from utils.logger import log

_TOOL_CALL_RE = re.compile(
    r"^[ \t]*TOOL_CALL:\s*([a-zA-Z_][\w-]*)\((.*)\)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class ToolRegistry:

    def __init__(self, project_path: Optional[str] = None, db_path: Optional[str] = None):
        self._tools: Dict[str, Tool] = {}
        self._register_defaults(project_path or settings.essence_path, db_path or settings.db_path)

    def _register_defaults(self, project_path: str, db_path: str) -> None:
        from tools.calculator import CalculatorTool
        from tools.web_search import WebSearchTool
        from tools.git_tool import GitStatusTool, GitLogTool, GitDiffTool
        from tools.file_tool import ReadFileTool, ListDirTool
        from tools.sdlc_tool import SDLCReportTool

        for tool in [
            CalculatorTool(),
            WebSearchTool(),
            GitStatusTool(project_path),
            GitLogTool(project_path),
            GitDiffTool(project_path),
            ReadFileTool(project_path),
            ListDirTool(project_path),
            SDLCReportTool(db_path),
        ]:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name.lower()] = tool
        log("TOOL", f"Registered: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name.lower())

    def list_tools(self) -> List[Dict]:
        return [t.to_dict() for t in self._tools.values()]

    def dispatch(self, tool_name: str, args: str) -> str:
        tool = self.get(tool_name)
        if not tool:
            available = list(self._tools.keys())
            return f"[ToolRegistry] Unknown tool: '{tool_name}'. Available: {available}"
        log("TOOL", f"Dispatching {tool_name}({args!r})")
        try:
            return tool.run(args)
        except Exception as e:
            return f"[Tool Error] {tool_name}: {e}"

    def parse_and_run(self, text: str) -> tuple[str, List[Dict]]:
        """
        Scan `text` for TOOL_CALL directives, run them, and replace inline.
        Returns (augmented_text, list of call records).
        """
        calls_made = []
        output = text
        for match in _TOOL_CALL_RE.finditer(text):
            tool_name = match.group(1)
            args      = match.group(2).strip()
            result    = self.dispatch(tool_name, args)
            calls_made.append({"tool": tool_name, "args": args, "result": result})
            output = output.replace(match.group(0), f"[{tool_name} → {result[:200]}]")
        return output, calls_made
