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
from core.database import open_database
from memory.store import MemoryStore
from reasoning.engine import ReasoningEngine
from reflection.engine import ReflectionEngine
from sdlc.backlog import BacklogStore
from sdlc.changelog import ChangelogGenerator
from sdlc.issues import IssueStore
from sdlc.reporter import ProjectReporter
from sdlc.reviewer import CodeReviewer
from sdlc.sprint import SprintStore
from tools.registry import ToolRegistry
from utils.logger import log


class Orchestrator:

    def __init__(self, db_path: Optional[str] = None):
        db = db_path or settings.db_path
        self.db_path    = db
        self.conn       = open_database(db)
        self.reasoning  = ReasoningEngine()
        self.memory     = MemoryStore(db, conn=self.conn)
        self.reflection = ReflectionEngine()
        self.agent      = LLMAgent()
        self.tools      = ToolRegistry(db_path=db)
        self.backlog    = BacklogStore(self.conn)
        self.sprints    = SprintStore(self.conn)
        self.issues     = IssueStore(self.conn)
        self.reporter   = ProjectReporter(self.conn)
        self.reviewer   = CodeReviewer(self.conn, self.agent.call_raw, settings.essence_path)
        self.changelog  = ChangelogGenerator(self.conn, settings.essence_path)

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

        # 3. Execute agent, including any tool result follow-up turns
        final_response, tools_used = self._execute_with_tools(query, reasoning, context)
        if tools_used:
            log("ORCH", f"Tools used: {[t['tool'] for t in tools_used]}")

        # 4. Reflect, then store the full record in memory
        reflection = self.reflection.evaluate(query, final_response, reasoning)
        self.memory.store(query, final_response, reasoning, reflection=reflection)

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

    # ──────────────────────────────────────────
    # Tool loop
    # ──────────────────────────────────────────

    def _execute_with_tools(
        self,
        query: str,
        reasoning: Dict[str, Any],
        context: List[Dict],
    ) -> tuple[str, List[Dict]]:
        tools_desc = self.tools.list_tools()
        raw_response = self.agent.execute(
            query,
            reasoning,
            context=context,
            tools_available=tools_desc,
        )

        all_tools: List[Dict] = []
        final_response = raw_response

        for _ in range(settings.max_tool_iterations):
            final_response, tools_used = self.tools.parse_and_run(raw_response)
            if not tools_used:
                break

            all_tools.extend(tools_used)
            raw_response = self.agent.continue_with_tool_results(
                query=query,
                reasoning=reasoning,
                context=context,
                previous_response=final_response,
                tools_used=tools_used,
                tools_available=tools_desc,
            )
            final_response = raw_response

        return final_response, all_tools
