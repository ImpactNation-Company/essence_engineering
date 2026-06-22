"""
LLM-backed agent — Forge's reasoning brain.

Provider support (via config.py):
  groq → Llama 3.3 70B (recommended, free)
  ollama → local models (offline fallback)
  openai, anthropic, gemini → cloud alternatives
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agents.base import Agent
from config import settings, AGENT_NAME, SYSTEM_PROMPT
from utils.logger import log


class LLMAgent(Agent):
    name = AGENT_NAME
    description = f"{AGENT_NAME} — LLM-powered SDLC manager for the Essence project."

    def __init__(self):
        self.client_error: str | None = None
        try:
            self.client = settings.get_llm_client()
        except (ImportError, ValueError) as e:
            self.client = None
            self.client_error = str(e)
            log("ERROR", f"LLM provider setup failed: {e}")
        self.provider = settings.provider
        self.model    = settings.get_model()
        if self.client:
            log("AGENT", f"LLMAgent ready — provider={self.provider}, model={self.model}")
        else:
            log("AGENT", "No LLM configured — stub mode active.")

    def execute(
        self,
        query: str,
        reasoning: Dict[str, Any],
        context: List[Dict] = None,
        tools_available: List[Dict] = None,
    ) -> str:
        if not self.client:
            from agents.stub import StubAgent
            response = StubAgent().execute(query, reasoning, context)
            if self.client_error:
                response += f"\n\n[Provider setup] {self.client_error}"
            return response

        messages = self._build_messages(query, reasoning, context, tools_available)
        try:
            return self._call_messages(messages)
        except Exception as e:
            log("ERROR", f"LLM call failed: {e}")
            return f"[LLM Error] {e}\n\nCheck your API key and network connection."
        return "[Error] Unknown provider."

    def call_raw(self, prompt: str) -> str:
        """Simple single-prompt call — used by CodeReviewer."""
        if not self.client:
            return "[Stub] LLM not configured."
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]
        try:
            return self._call_messages(messages)
        except Exception as e:
            log("ERROR", f"LLM raw call failed: {e}")
            return f"[LLM Error] {e}"
        return ""

    def continue_with_tool_results(
        self,
        query: str,
        reasoning: Dict[str, Any],
        context: List[Dict] = None,
        previous_response: str = "",
        tools_used: List[Dict] = None,
        tools_available: List[Dict] = None,
    ) -> str:
        """Ask the model to synthesize a final answer after tool execution."""
        if not self.client:
            return previous_response

        tool_lines = []
        for call in tools_used or []:
            tool_lines.append(
                f"- {call.get('tool')}({call.get('args', '')}) -> "
                f"{str(call.get('result', ''))[:3000]}"
            )

        follow_up = (
            "Original user request:\n"
            f"{query}\n\n"
            "Previous response after inline tool replacement:\n"
            f"{previous_response}\n\n"
            "Tool results:\n"
            f"{chr(10).join(tool_lines)}\n\n"
            "Use these results to answer the original request directly. "
            "Only emit another TOOL_CALL line if another tool is strictly required."
        )
        messages = self._build_messages(follow_up, reasoning, context, tools_available)
        try:
            return self._call_messages(messages)
        except Exception as e:
            log("ERROR", f"LLM tool follow-up failed: {e}")
            return previous_response

    # ──────────────────────────────────────────
    # Message construction
    # ──────────────────────────────────────────

    def _build_messages(
        self,
        query: str,
        reasoning: Dict[str, Any],
        context: Optional[List[Dict]],
        tools_available: Optional[List[Dict]],
    ) -> List[Dict]:
        parts = [SYSTEM_PROMPT]

        # Memory context
        if context:
            mem_lines = [
                f"  [{i}] Q: {r.get('query','?')[:80]} → A: {str(r.get('response','?'))[:100]}..."
                for i, r in enumerate(context[:4], 1)
            ]
            parts.append("\n## Relevant Memory\n" + "\n".join(mem_lines))

        # Reasoning plan
        if reasoning.get("plan"):
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(reasoning["plan"]))
            parts.append(
                f"\n## Reasoning Plan\n"
                f"Intent: {reasoning.get('intent','?')} | "
                f"Complexity: {reasoning.get('complexity','?')}\n{steps}"
            )

        # Available tools
        if tools_available:
            tool_desc = "\n".join(f"  - {t['name']}: {t['description']}" for t in tools_available)
            parts.append(
                f"\n## Available Tools\n{tool_desc}\n"
                "To use a tool, include on its own line: TOOL_CALL: tool_name(args)"
            )

        return [
            {"role": "system", "content": "\n".join(parts)},
            {"role": "user",   "content": query},
        ]

    # ──────────────────────────────────────────
    # Provider calls
    # ──────────────────────────────────────────

    def _call_openai_compat(self, messages: List[Dict]) -> str:
        """Handles Groq, OpenAI, and Ollama — all use the openai SDK."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,   # Lower temp = more consistent SDLC decisions
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()

    def _call_messages(self, messages: List[Dict]) -> str:
        if self.provider in ("groq", "openai", "ollama"):
            return self._call_openai_compat(messages)
        if self.provider == "gemini":
            return self._call_gemini(messages)
        if self.provider == "anthropic":
            return self._call_anthropic(messages)
        return "[Error] Unknown provider."

    def _call_gemini(self, messages: List[Dict]) -> str:
        import google.generativeai as genai  # type: ignore
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=messages[0]["content"],
        )
        response = model.generate_content(messages[1]["content"])
        return response.text.strip()

    def _call_anthropic(self, messages: List[Dict]) -> str:
        system   = messages[0]["content"]
        user_msgs = [{"role": m["role"], "content": m["content"]} for m in messages[1:]]
        response  = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=user_msgs,
        )
        return response.content[0].text.strip()
