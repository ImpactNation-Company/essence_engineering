"""
Enhanced ReasoningEngine — intent classification, complexity scoring,
context-aware planning, and structured chain-of-thought output.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from utils.logger import log

# ──────────────────────────────────────────────────────────────────────────────
# Intent taxonomy
# ──────────────────────────────────────────────────────────────────────────────
INTENT_PATTERNS = {
    "math":         [r"\b(calculate|compute|solve|what is|=|\+|\-|\*|/|%|sqrt|pow)\b", r"\d+\s*[\+\-\*/]\s*\d+"],
    "code":         [r"\b(code|function|bug|debug|implement|class|refactor|write|script|python|javascript|program)\b"],
    "search":       [r"\b(search|find|look up|who is|what is|when did|where is|news|latest)\b"],
    "analysis":     [r"\b(analyze|analyse|review|evaluate|compare|assess|explain|why|how does)\b"],
    "task":         [r"\b(do|make|create|build|generate|run|execute|set up|configure)\b"],
    "memory":       [r"\b(remember|recall|what did|earlier|before|previous|last time|history)\b"],
    "conversation": [r"\b(hello|hi|hey|thanks|thank you|how are you|what can you|help me)\b"],
}

COMPLEXITY_SIGNALS = {
    "high":   [r"\b(architect|design system|multi-step|complex|advanced|production|scalable)\b"],
    "medium": [r"\b(implement|build|create|analyze|compare)\b"],
    "low":    [r"\b(what is|define|list|show|print|hello)\b"],
}


class ReasoningEngine:

    def process(self, query: str, memory_context: Optional[List[Dict]] = None) -> Dict[str, Any]:
        log("REASON", f"Processing query — length={len(query)}")

        observations = self.observe(query)
        analysis     = self.analyze(observations, memory_context)
        intent       = self.classify_intent(query)
        complexity   = self.score_complexity(query, intent)
        plan         = self.generate_plan(query, intent, complexity, memory_context)
        conclusion   = self.conclude(analysis, intent, plan)

        result = {
            "observations": observations,
            "analysis":     analysis,
            "intent":       intent,
            "complexity":   complexity,
            "plan":         plan,
            "conclusion":   conclusion,
        }

        log("REASON", f"intent={intent}, complexity={complexity}, plan_steps={len(plan)}")
        return result

    # ──────────────────────────────────────────
    # Observation
    # ──────────────────────────────────────────

    def observe(self, query: str) -> Dict[str, Any]:
        sentences = [s.strip() for s in re.split(r'[.!?]+', query) if s.strip()]
        return {
            "input":       query,
            "length":      len(query),
            "word_count":  len(query.split()),
            "sentences":   sentences,
            "has_question": "?" in query,
        }

    # ──────────────────────────────────────────
    # Analysis
    # ──────────────────────────────────────────

    def analyze(self, obs: Dict, memory_context: Optional[List[Dict]]) -> Dict[str, Any]:
        text = obs["input"].lower()
        keywords = self._extract_keywords(text)
        has_memory_ref = bool(memory_context) and any(
            k in text for k in ["remember", "before", "earlier", "previous", "last"]
        )
        return {
            "keywords":        keywords,
            "has_memory_ref":  has_memory_ref,
            "memory_entries":  len(memory_context) if memory_context else 0,
        }

    def _extract_keywords(self, text: str) -> List[str]:
        stopwords = {"the", "a", "an", "is", "it", "in", "on", "at", "to",
                     "and", "or", "but", "of", "for", "with", "how", "what",
                     "can", "you", "i", "my", "me", "do", "did", "does"}
        words = re.findall(r'\b[a-z][a-z0-9_-]{2,}\b', text)
        seen = set()
        unique = []
        for w in words:
            if w not in stopwords and w not in seen:
                seen.add(w)
                unique.append(w)
        return unique[:15]

    # ──────────────────────────────────────────
    # Intent classification
    # ──────────────────────────────────────────

    def classify_intent(self, query: str) -> str:
        ql = query.lower()
        scores: Dict[str, int] = {}
        for intent, patterns in INTENT_PATTERNS.items():
            score = sum(
                len(re.findall(p, ql, re.IGNORECASE))
                for p in patterns
            )
            if score > 0:
                scores[intent] = score
        return max(scores, key=scores.get) if scores else "conversation"

    # ──────────────────────────────────────────
    # Complexity scoring
    # ──────────────────────────────────────────

    def score_complexity(self, query: str, intent: str) -> str:
        ql = query.lower()
        for level, patterns in COMPLEXITY_SIGNALS.items():
            for p in patterns:
                if re.search(p, ql, re.IGNORECASE):
                    return level
        # Fallback: long queries tend to be more complex
        if len(query.split()) > 30:
            return "high"
        if intent in ("task", "code", "analysis"):
            return "medium"
        return "low"

    # ──────────────────────────────────────────
    # Plan generation
    # ──────────────────────────────────────────

    def generate_plan(
        self,
        query: str,
        intent: str,
        complexity: str,
        memory_context: Optional[List[Dict]],
    ) -> List[str]:
        """Generate a step-by-step reasoning plan appropriate to the intent."""
        common_start = ["Understand the query and clarify ambiguity if needed"]
        common_end   = ["Formulate a clear, concise response", "Review response for accuracy"]

        intent_steps = {
            "math": [
                "Identify the mathematical operation or expression",
                "Execute the calculation step-by-step",
                "Verify the result",
            ],
            "code": [
                "Identify the programming language and context",
                "Break down the problem into logical units",
                "Design a solution approach",
                "Write or analyse the code",
                "Check for edge cases and potential bugs",
            ],
            "search": [
                "Identify what information is being requested",
                "Recall any relevant context from memory",
                "Use available tools to retrieve information" if True else "",
                "Synthesize findings into a coherent answer",
            ],
            "analysis": [
                "Decompose the subject into components",
                "Evaluate each component independently",
                "Identify patterns, strengths, and weaknesses",
                "Synthesize insights into actionable conclusions",
            ],
            "task": [
                "Clarify the goal and success criteria",
                "Identify sub-tasks and dependencies",
                "Determine required tools and resources",
                "Execute sub-tasks in order",
                "Validate the outcome",
            ],
            "memory": [
                "Search episodic memory for relevant past interactions",
                "Extract and summarise relevant information",
                "Connect past context to the current query",
            ],
            "conversation": [
                "Determine the conversational intent",
                "Respond warmly and helpfully",
            ],
        }

        steps = (
            common_start
            + [s for s in intent_steps.get(intent, ["Reason through the query"]) if s]
            + common_end
        )

        if complexity == "low" and len(steps) > 4:
            steps = steps[:2] + steps[-1:]

        return steps

    # ──────────────────────────────────────────
    # Conclusion
    # ──────────────────────────────────────────

    def conclude(
        self,
        analysis: Dict,
        intent: str,
        plan: List[str],
    ) -> Dict[str, Any]:
        return {
            "intent_summary": f"Query classified as '{intent}' with {len(plan)} reasoning steps.",
            "top_keywords":   analysis["keywords"][:5],
            "ready_to_act":   True,
        }