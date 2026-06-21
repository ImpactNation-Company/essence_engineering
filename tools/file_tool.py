"""
FileTool — sandboxed read-only file access for the Essence project.

Forge can read Essence source files to provide context for code reviews,
task specs, and architectural decisions — but never modifies them.
"""
from __future__ import annotations

import os
from pathlib import Path

from tools.base import Tool
from utils.logger import log


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the contents of a file in the Essence project. "
        "Pass a relative path from the project root. "
        "Example: read_file(src/main.py)"
    )

    def __init__(self, project_path: str = "."):
        self.root = Path(project_path).resolve()

    def run(self, input_str: str) -> str:
        rel = input_str.strip().lstrip("/")
        target = (self.root / rel).resolve()

        # Safety: stay within root
        if not str(target).startswith(str(self.root)):
            return "[Security] Access denied — path is outside the Essence project directory."

        if not target.exists():
            return f"[Error] File not found: {rel}"
        if not target.is_file():
            return f"[Error] Not a file: {rel}"

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            truncated = len(lines) > 200
            if truncated:
                content = "\n".join(lines[:200]) + f"\n\n[... truncated — {len(lines)} total lines]"
            log("TOOL", f"read_file: {rel} ({len(lines)} lines)")
            return f"# {rel}\n```\n{content}\n```"
        except Exception as e:
            return f"[Error] Could not read {rel}: {e}"


class ListDirTool(Tool):
    name = "list_dir"
    description = (
        "List files and directories in the Essence project. "
        "Pass a relative path (default: project root). "
        "Example: list_dir(src/)"
    )

    def __init__(self, project_path: str = "."):
        self.root = Path(project_path).resolve()

    def run(self, input_str: str = "") -> str:
        rel = input_str.strip().lstrip("/") or "."
        target = (self.root / rel).resolve()

        if not str(target).startswith(str(self.root)):
            return "[Security] Access denied."
        if not target.exists():
            return f"[Error] Path not found: {rel}"
        if not target.is_dir():
            return f"[Error] Not a directory: {rel}"

        try:
            items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
            lines = [f"# Contents of {rel}"]
            for item in items[:100]:
                icon = "📁" if item.is_dir() else "📄"
                size = f" ({item.stat().st_size:,}B)" if item.is_file() else ""
                lines.append(f"  {icon} {item.name}{size}")
            if len(list(target.iterdir())) > 100:
                lines.append("  ... (truncated)")
            return "\n".join(lines)
        except Exception as e:
            return f"[Error] {e}"
