"""
GitTool — read-only git operations on the Essence project repo.

Operations: status, log, diff, branch info.
All operations are read-only — Forge never commits or pushes.
"""
from __future__ import annotations

import subprocess
from typing import List

from tools.base import Tool
from utils.logger import log


def _run_git(args: List[str], cwd: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True,
            cwd=cwd, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"[git error] {result.stderr.strip()}"
    except FileNotFoundError:
        return "[git not found] Is git installed and on PATH?"
    except subprocess.TimeoutExpired:
        return "[git timeout]"
    except Exception as e:
        return f"[git error] {e}"


class GitStatusTool(Tool):
    name = "git_status"
    description = "Show the current git working tree status of the Essence project."

    def __init__(self, project_path: str = "."):
        self.path = project_path

    def run(self, input_str: str = "") -> str:
        return _run_git(["status", "--short", "--branch"], self.path)


class GitLogTool(Tool):
    name = "git_log"
    description = (
        "Show recent git commit history. "
        "Pass a number to limit results (default 10). "
        "Example: git_log(5)"
    )

    def __init__(self, project_path: str = "."):
        self.path = project_path

    def run(self, input_str: str = "") -> str:
        try:
            n = int(input_str.strip()) if input_str.strip().isdigit() else 10
        except ValueError:
            n = 10
        return _run_git(
            ["log", f"-{n}", "--oneline", "--no-merges",
             "--pretty=format:%h %ad %s (%an)", "--date=short"],
            self.path
        )


class GitDiffTool(Tool):
    name = "git_diff"
    description = (
        "Show a git diff. Pass a file path to diff a specific file, "
        "or leave empty for the latest staged/unstaged changes. "
        "Example: git_diff(src/main.py)"
    )

    def __init__(self, project_path: str = "."):
        self.path = project_path

    def run(self, input_str: str = "") -> str:
        file_arg = input_str.strip()
        if file_arg:
            diff = _run_git(["diff", "HEAD", "--", file_arg], self.path)
        else:
            diff = _run_git(["diff", "HEAD~1", "HEAD"], self.path)
            if not diff or diff.startswith("[git"):
                diff = _run_git(["diff", "--staged"], self.path)
            if not diff or diff.startswith("[git"):
                diff = _run_git(["diff"], self.path)
        return diff[:4000] if diff else "No changes detected."
