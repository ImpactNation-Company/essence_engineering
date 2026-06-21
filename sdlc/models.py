"""
Shared dataclasses for SDLC domain entities.
All entities are serialisable to/from dicts for SQLite storage.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List


# ─────────────────────────────────────────────
# Enumerations (stored as strings in DB)
# ─────────────────────────────────────────────
ITEM_TYPES     = ("feature", "bug", "task", "spike", "debt")
PRIORITIES     = ("critical", "high", "medium", "low")
ITEM_STATUSES  = ("new", "ready", "in_progress", "review", "done", "cancelled")
SPRINT_STATUSES = ("planned", "active", "completed", "cancelled")
ISSUE_TYPES    = ("bug", "blocker", "question", "risk", "improvement")
SEVERITIES     = ("critical", "high", "medium", "low", "info")
ISSUE_STATUSES = ("open", "in_progress", "resolved", "wontfix")


def _now() -> str:
    return datetime.utcnow().isoformat()


# ─────────────────────────────────────────────
# Backlog Item
# ─────────────────────────────────────────────
@dataclass
class BacklogItem:
    id:          int
    title:       str
    type:        str       = "task"      # ITEM_TYPES
    priority:    str       = "medium"    # PRIORITIES
    status:      str       = "new"       # ITEM_STATUSES
    description: str       = ""
    sprint_id:   Optional[int] = None
    created_at:  str       = field(default_factory=_now)
    updated_at:  str       = field(default_factory=_now)
    tags:        str       = ""          # comma-separated

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "BacklogItem":
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})

    def short_repr(self) -> str:
        icon = {"feature": "✨", "bug": "🐛", "task": "📋", "spike": "🔬", "debt": "🔧"}.get(self.type, "•")
        pri  = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(self.priority, "")
        return f"[{self.id:03d}] {icon}{pri} {self.title} ({self.status})"


# ─────────────────────────────────────────────
# Sprint
# ─────────────────────────────────────────────
@dataclass
class Sprint:
    id:         int
    name:       str
    goal:       str        = ""
    status:     str        = "planned"   # SPRINT_STATUSES
    start_date: str        = ""
    end_date:   str        = ""
    velocity:   int        = 0           # items completed
    created_at: str        = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "Sprint":
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})


# ─────────────────────────────────────────────
# Issue
# ─────────────────────────────────────────────
@dataclass
class Issue:
    id:              int
    title:           str
    type:            str       = "bug"       # ISSUE_TYPES
    severity:        str       = "medium"    # SEVERITIES
    status:          str       = "open"      # ISSUE_STATUSES
    description:     str       = ""
    backlog_item_id: Optional[int] = None
    created_at:      str       = field(default_factory=_now)
    resolved_at:     str       = ""
    notes:           str       = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "Issue":
        return cls(**{k: v for k, v in row.items() if k in cls.__dataclass_fields__})

    def short_repr(self) -> str:
        sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(self.severity, "")
        return f"[{self.id:03d}] {sev_icon} {self.title} [{self.type}] ({self.status})"
