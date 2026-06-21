"""
Stub agent — deterministic fallback used when no LLM is configured.
Useful for testing the pipeline without API credentials.
"""
from typing import Any, Dict, List
from agents.base import Agent


class StubAgent(Agent):
    name = "StubAgent"
    description = "Deterministic stub — echoes the query with keyword analysis."

    def execute(self, query: str, reasoning: Dict[str, Any], context: List[Dict] = None) -> str:
        intent = reasoning.get("intent", "unknown")
        keywords = reasoning.get("analysis", {}).get("keywords", [])
        kw_str = ", ".join(keywords[:5]) if keywords else "none detected"
        ctx_note = f" (recalling {len(context)} prior interactions)" if context else ""
        return (
            f"[StubAgent{ctx_note}] Processed query with intent='{intent}'. "
            f"Top keywords: {kw_str}. "
            f"Configure an LLM provider in .env to enable real responses."
        )
