"""
Orchestrator — the central nervous system of the Essence agent.

Pipeline per query:
  1. Recall relevant memory
  2. Reason (intent, plan, complexity)
  3. Execute (LLM agent + tool parsing)
  4. Store result in memory
  5. Reflect on quality
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.llm_agent import LLMAgent
from config import settings
from memory.store import MemoryStore
from reasoning.engine import ReasoningEngine
from reflection.engine import ReflectionEngine
from tools.registry import ToolRegistry
from utils.logger import log


class Orchestrator:

    def __init__(self, db_path: Optional[str] = None):
        db = db_path or settings.db_path
        self.reasoning  = ReasoningEngine()
        self.memory     = MemoryStore(db)
        self.reflection = ReflectionEngine()
        self.agent      = LLMAgent()
        self.tools      = ToolRegistry()

        log("ORCH", f"Orchestrator ready | provider={settings.provider} | db={db}")

    # ──────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────

    def run(self, query: str) -> Dict[str, Any]:
        log("ORCH", f"Query received ({len(query)} chars)")

        # 1. Recall
        context = self.memory.recall(query, limit=5)
        log("ORCH", f"Recalled {len(context)} relevant memories")

        # 2. Reason
        reasoning = self.reasoning.process(query, memory_context=context)

        # 3. Execute agent
        tools_desc = self.tools.list_tools()
        raw_response = self.agent.execute(
            query,
            reasoning,
            context=context,
            tools_available=tools_desc,
        )

        # 4. Parse & run any tool calls embedded in the response
        final_response, tools_used = self.tools.parse_and_run(raw_response)
        if tools_used:
            log("ORCH", f"Tools used: {[t['tool'] for t in tools_used]}")

        # 5. Store in memory
        self.memory.store(query, final_response, reasoning)

        # 6. Reflect
        reflection = self.reflection.evaluate(query, final_response, reasoning)

        return {
            "query":      query,
            "response":   final_response,
            "reasoning":  reasoning,
            "reflection": reflection,
            "tools_used": tools_used,
            "context_len": len(context),
        }

    # ──────────────────────────────────────────
    # Convenience helpers (used by CLI)
    # ──────────────────────────────────────────

    def history(self, limit: int = 20) -> List[Dict]:
        return self.memory.all_records(limit)

    def memory_count(self) -> int:
        return self.memory.count()
