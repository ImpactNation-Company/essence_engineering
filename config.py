"""
config.py — Central configuration for the Forge SDLC Manager Agent.

Forge manages the Software Development Lifecycle of the Essence project.
It uses Groq (free, no credit card, OpenAI-compatible API) as the default
LLM provider, with Ollama as a local offline fallback.

Provider priority:
  1. LLM_PROVIDER env var (explicit)
  2. Auto-detect: groq → openai → anthropic → ollama → stub

Usage:
    from config import settings
    client = settings.get_llm_client()
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────
# Agent Identity
# ─────────────────────────────────────────────────────────────
AGENT_NAME = "Forge"
AGENT_VERSION = "1.0"

# Edit this to describe what Essence is — Forge uses this as context
# for all SDLC decisions (prioritisation, sprint goals, code review, etc.)
ESSENCE_DESCRIPTION = (
    "Essence is an AI-powered application being built through collaborative "
    "AI coding agents. Its exact domain and feature set are evolving. "
    "Forge's job is to manage the SDLC of Essence: backlog, sprints, "
    "issues, code reviews, changelogs, and project reporting."
)

SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a senior AI engineering manager responsible for
managing the full Software Development Lifecycle (SDLC) of a project called Essence.

## About Essence
{ESSENCE_DESCRIPTION}

## Your Responsibilities
- Maintain and prioritise the product backlog (features, bugs, tasks, technical debt)
- Plan and track sprints: set goals, assign items, report velocity and burndown
- Triage and manage bugs and issues with severity ratings
- Coordinate with AI coding agents: provide clear task specs and acceptance criteria
- Review code changes: identify risks, gaps, and improvements
- Generate changelogs, status reports, and daily standups
- Give opinionated, actionable SDLC recommendations

## Behaviour
- Be concise, structured, and decisive — you are a manager, not a chatbot
- Use numbered lists and markdown tables where helpful
- When something is unclear, ask one focused clarifying question
- Reference memory of past sprint decisions when relevant
- Prioritise ruthlessly: what moves Essence forward the most right now?
"""


# ─────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────
@dataclass
class Settings:
    provider: str = field(default_factory=lambda: (
        os.getenv("LLM_PROVIDER", "").lower() or _detect_provider()
    ))
    groq_api_key:      Optional[str] = field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    gemini_api_key:    Optional[str] = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))
    openai_api_key:    Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    ollama_base_url:   str           = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model:      str           = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.3"))

    model_overrides: dict = field(default_factory=lambda: {
        "groq":      os.getenv("GROQ_MODEL",      "llama-3.3-70b-versatile"),
        "gemini":    os.getenv("GEMINI_MODEL",    "gemini-2.0-flash"),
        "openai":    os.getenv("OPENAI_MODEL",    "gpt-4o-mini"),
        "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
    })

    db_path: str  = field(default_factory=lambda: os.getenv("FORGE_DB", "forge.db"))
    verbose: bool = field(default_factory=lambda: os.getenv("FORGE_VERBOSE", "0") == "1")

    # Path to the Essence project (for git/file tools)
    essence_path: str = field(default_factory=lambda: os.getenv("ESSENCE_PATH", "."))

    def get_model(self) -> str:
        if self.provider == "ollama":
            return self.ollama_model
        return self.model_overrides.get(self.provider, "unknown")

    def get_llm_client(self):
        """Return an initialised LLM client, or None for stub mode."""
        if self.provider == "groq":
            return _get_groq_client(self.groq_api_key)
        if self.provider == "ollama":
            return _get_ollama_client(self.ollama_base_url)
        if self.provider == "gemini":
            return _get_gemini_client(self.gemini_api_key)
        if self.provider == "openai":
            return _get_openai_client(self.openai_api_key)
        if self.provider == "anthropic":
            return _get_anthropic_client(self.anthropic_api_key)
        return None

    def is_llm_enabled(self) -> bool:
        return self.provider in ("groq", "ollama", "gemini", "openai", "anthropic")


# ─────────────────────────────────────────────────────────────
# Provider detection
# ─────────────────────────────────────────────────────────────
def _detect_provider() -> str:
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if _ollama_available():
        return "ollama"
    return "stub"


def _ollama_available() -> bool:
    try:
        import urllib.request
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/tags"
        urllib.request.urlopen(url, timeout=1)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Client factories
# ─────────────────────────────────────────────────────────────
def _get_groq_client(api_key: Optional[str]):
    """
    Groq uses the openai package pointed at the Groq endpoint.
    No separate groq package required.
    """
    try:
        from openai import OpenAI  # type: ignore
        if not api_key:
            raise ValueError("GROQ_API_KEY not set — get a free key at console.groq.com")
        return OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    except ImportError:
        raise ImportError("Install openai: pip install openai")


def _get_ollama_client(base_url: str):
    """Ollama also exposes an OpenAI-compatible /v1 endpoint."""
    try:
        from openai import OpenAI  # type: ignore
        return OpenAI(
            api_key="ollama",   # required by the SDK but ignored by Ollama
            base_url=f"{base_url}/v1",
        )
    except ImportError:
        raise ImportError("Install openai: pip install openai")


def _get_gemini_client(api_key: Optional[str]):
    try:
        import google.generativeai as genai  # type: ignore
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)
        return genai
    except ImportError:
        raise ImportError("Install google-generativeai: pip install google-generativeai")


def _get_openai_client(api_key: Optional[str]):
    try:
        from openai import OpenAI  # type: ignore
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return OpenAI(api_key=api_key)
    except ImportError:
        raise ImportError("Install openai: pip install openai")


def _get_anthropic_client(api_key: Optional[str]):
    try:
        import anthropic  # type: ignore
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        raise ImportError("Install anthropic: pip install anthropic")


# Singleton
settings = Settings()
