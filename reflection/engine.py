"""
Semantic ReflectionEngine — evaluates response quality and generates
structured lessons for the agent to learn from.
"""
from __future__ import annotations

import re
from typing import Any, Dict

from utils.logger import log


# Patterns that signal a weak/failed response
FAILURE_SIGNALS = [
    r"\bi (don'?t|cannot|can'?t) (know|answer|help|tell)\b",
    r"\bI'?m not sure\b",
    r"\bI have no (idea|information|knowledge)\b",
    r"\bsorry,? I (can'?t|cannot|don'?t)\b",
    r"^\s*$",           # empty response
]

QUALITY_SIGNALS = {
    "has_structure":  r"(\n\n|\*\*|##|\d+\.|[-•])",  # lists, headers, bold
    "has_code":       r"```",
    "has_reasoning":  r"\b(because|therefore|since|as a result|consequently|given that)\b",
    "has_examples":   r"\b(for example|e\.g\.|such as|like|instance)\b",
    "appropriate_len": None,  # checked separately
}


class ReflectionEngine:

    def evaluate(self, query: str, response: str, reasoning: Dict[str, Any] = None) -> Dict[str, Any]:

        if not isinstance(response, str):
            response = str(response) if response is not None else ""

        success, failure_flags = self._check_success(response)
        quality_score, quality_breakdown = self._score_quality(response, query)
        confidence = self._compute_confidence(success, quality_score, reasoning)
        lesson = self._derive_lesson(success, failure_flags, quality_score, reasoning)

        reflection = {
            "query":              query,
            "success":            success,
            "confidence":         confidence,
            "quality_score":      quality_score,
            "quality_breakdown":  quality_breakdown,
            "failure_flags":      failure_flags,
            "lesson":             lesson,
            "response_length":    len(response),
        }

        status = "✓ OK" if success else "✗ FAIL"
        log("REFLECT", f"{status} | confidence={confidence:.2f} | quality={quality_score}/5")
        return reflection

    # ──────────────────────────────────────────
    # Success detection
    # ──────────────────────────────────────────

    def _check_success(self, response: str) -> tuple[bool, list[str]]:
        flags = []
        for pattern in FAILURE_SIGNALS:
            if re.search(pattern, response, re.IGNORECASE):
                flags.append(pattern)
        return (len(flags) == 0 and len(response.strip()) > 10), flags

    # ──────────────────────────────────────────
    # Quality scoring (0–5)
    # ──────────────────────────────────────────

    def _score_quality(self, response: str, query: str) -> tuple[int, Dict[str, bool]]:
        breakdown: Dict[str, bool] = {}
        score = 0

        for signal, pattern in QUALITY_SIGNALS.items():
            if signal == "appropriate_len":
                ok = 50 <= len(response) <= 4000
                breakdown[signal] = ok
                if ok:
                    score += 1
            elif pattern and re.search(pattern, response, re.IGNORECASE):
                breakdown[signal] = True
                score += 1
            else:
                breakdown[signal] = False

        # Bonus: response addresses keywords from the query
        q_words = set(re.findall(r'\b[a-z]{4,}\b', query.lower()))
        r_words = set(re.findall(r'\b[a-z]{4,}\b', response.lower()))
        if len(q_words & r_words) >= 2:
            breakdown["relevant_to_query"] = True
            score = min(score + 1, 5)
        else:
            breakdown["relevant_to_query"] = False

        return score, breakdown

    # ──────────────────────────────────────────
    # Confidence
    # ──────────────────────────────────────────

    def _compute_confidence(
        self,
        success: bool,
        quality_score: int,
        reasoning: Dict = None,
    ) -> float:
        base = 0.4 if success else 0.1
        quality_bonus = quality_score * 0.1
        intent_bonus = 0.1 if reasoning and reasoning.get("intent") not in (None, "conversation") else 0.0
        return round(min(base + quality_bonus + intent_bonus, 1.0), 2)

    # ──────────────────────────────────────────
    # Lesson derivation
    # ──────────────────────────────────────────

    def _derive_lesson(
        self,
        success: bool,
        flags: list,
        quality_score: int,
        reasoning: Dict = None,
    ) -> str:
        if not success:
            return "Response indicated uncertainty or failure. Consider retrieving more context or using a tool."
        if quality_score <= 1:
            return "Response was brief and unstructured. Aim for more detailed, organised answers."
        if quality_score == 2:
            return "Response was acceptable but lacked examples or structured reasoning."
        if quality_score >= 4:
            return "High-quality response with good structure and reasoning. Pattern worth reinforcing."
        return "Response was satisfactory. No specific lesson recorded."
