"""Prompt for cheap relevance screening before full extraction."""

from __future__ import annotations

SCREENING_PROMPT = """
You are screening an academic abstract for policy-causal extraction.
Return strict JSON: {{"relevant": true|false, "reason": "short"}}.
Mark relevant=true only if the abstract contains empirical policy effects,
quantitative estimates, or explicit causal claims applicable to policy analysis.

Abstract:
{abstract}
""".strip()

__all__ = ["SCREENING_PROMPT"]
