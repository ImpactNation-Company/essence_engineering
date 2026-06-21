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
        self.client   = settings.get_llm_client()
        self.provider = settings.provider
        self.model    = settings.get_model()
        if self.client:
            log("AGENT", f"LLMAgent ready — provider={self.provider}, model={self.model}")
        else:
            log("AGENT", "No LLM configured — stub mode. Set GROQ_API_KEY in .env (free at console.groq.com)")

    def execute(
        self,
        query: str,
        reasoning: Dict[str, Any],
        context: List[Dict] = None,
        tools_available: List[Dict] = None,
    ) -> str:
        if not self.client:
            from agents.stub import StubAgent
            return StubAgent().execute(query, reasoning, context)

        messages = self._build_messages(query, reasoning, context, tools_available)
        try:
            if self.provider in ("groq", "openai", "ollama"):
                return self._call_openai_compat(messages)
            elif self.provider == "gemini":
                return self._call_gemini(messages)
            elif self.provider == "anthropic":
                return self._call_anthropic(messages)
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
            if self.provider in ("groq", "openai", "ollama"):
                return self._call_openai_compat(messages)
            elif self.provider == "gemini":
                return self._call_gemini(messages)
            elif self.provider == "anthropic":
                return self._call_anthropic(messages)
        except Exception as e:
            log("ERROR", f"LLM raw call failed: {e}")
            return f"[LLM Error] {e}"
        return ""

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
