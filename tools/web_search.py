"""
Web search tool — retrieves top results via DuckDuckGo Instant Answer API.

No API key required. Falls back gracefully if offline or the
duckduckgo-search package is not installed.

Usage (in agent response):
    TOOL_CALL: web_search(latest news on LLM agents)
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import List

from tools.base import Tool
from utils.logger import log

_DDGS_TIMEOUT = 8  # seconds


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Searches the web using DuckDuckGo and returns a brief summary "
        "of the top results. No API key required. "
        "Example: web_search(open source LLM frameworks 2025)"
    )

    def run(self, input_str: str) -> str:
        query = input_str.strip()
        log("TOOL", f"web_search: '{query}'")

        # Try duckduckgo-search package first (richer results)
        result = self._try_ddgs_package(query)
        if result:
            return result

        # Fallback: DuckDuckGo Instant Answer API
        result = self._try_ddg_instant(query)
        if result:
            return result

        return f"[WebSearch] No results found for: {query}"

    # ──────────────────────────────────────────
    # Strategy 1: duckduckgo-search package
    # ──────────────────────────────────────────

    def _try_ddgs_package(self, query: str) -> str | None:
        try:
            from duckduckgo_search import DDGS  # type: ignore
            with DDGS(timeout=_DDGS_TIMEOUT) as ddgs:
                results: List[dict] = list(ddgs.text(query, max_results=3))
            if not results:
                return None
            lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(
                    f"{i}. {r.get('title','')}\n"
                    f"   {r.get('body','')[:200].strip()}\n"
                    f"   🔗 {r.get('href','')}"
                )
            return "\n".join(lines)
        except ImportError:
            return None
        except Exception as e:
            log("TOOL", f"ddgs package error: {e}")
            return None

    # ──────────────────────────────────────────
    # Strategy 2: DuckDuckGo Instant Answer API
    # ──────────────────────────────────────────

    def _try_ddg_instant(self, query: str) -> str | None:
        try:
            encoded = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1})
            url = f"https://api.duckduckgo.com/?{encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "Essence-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=_DDGS_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            abstract = data.get("AbstractText", "")
            answer   = data.get("Answer", "")
            source   = data.get("AbstractURL", "")
            topics   = data.get("RelatedTopics", [])

            parts = [f"Search results for: {query}\n"]
            if answer:
                parts.append(f"Answer: {answer}")
            if abstract:
                parts.append(f"Summary: {abstract[:300]}")
                if source:
                    parts.append(f"Source: {source}")
            if topics:
                for t in topics[:3]:
                    if isinstance(t, dict) and t.get("Text"):
                        parts.append(f"• {t['Text'][:150]}")

            return "\n".join(parts) if len(parts) > 1 else None
        except Exception as e:
            log("TOOL", f"DDG instant API error: {e}")
            return None
