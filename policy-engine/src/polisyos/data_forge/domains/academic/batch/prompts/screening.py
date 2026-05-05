"""Prompt for cheap relevance screening before full extraction."""

from __future__ import annotations

SCREENING_PROMPT = """
You are screening an academic abstract for policy-causal extraction.
Return strict JSON: {{"relevant": true|false, "relevance_score": <number 0..1>, "reason": "short"}}.
Mark relevant=true only if the abstract contains empirical policy effects,
quantitative estimates, or explicit causal claims applicable to policy analysis.

Calibration guide for relevance_score:
- 0.9-1.0: Clear causal identification (RCT, IV, DiD, RDD) with numeric effect estimates
- 0.7-0.9: Quasi-experimental or strong observational study with quantitative results
- 0.5-0.7: Empirical study with policy-relevant correlations or suggestive causal evidence
- 0.3-0.5: Descriptive/correlational study with some policy relevance
- 0.0-0.3: Theoretical, methodological, or not policy-relevant

Examples:

Abstract: "Using a regression discontinuity design around the eligibility threshold, we find that the minimum wage increase of $1 raised employment by 2.3% (95% CI: 0.8-3.8%) in affected sectors."
{{"relevant": true, "relevance_score": 0.95, "reason": "RDD with precise effect estimate and CI for minimum wage policy"}}

Abstract: "We exploit the staggered rollout of a tax reform across Indian states as a natural experiment. Our difference-in-differences estimates suggest the reform increased tax compliance by 15 percentage points."
{{"relevant": true, "relevance_score": 0.92, "reason": "DiD natural experiment with quantitative tax policy effect"}}

Abstract: "Panel data from 45 countries over 1990-2015 show a positive correlation between trade openness and GDP growth, with OLS coefficients ranging from 0.02 to 0.08."
{{"relevant": true, "relevance_score": 0.55, "reason": "Cross-country OLS with numeric coefficients but no causal identification"}}

Abstract: "This paper develops a theoretical model of optimal taxation under heterogeneous agents and derives conditions for Pareto efficiency."
{{"relevant": false, "relevance_score": 0.1, "reason": "Purely theoretical model, no empirical estimates"}}

Abstract: "We review the literature on fiscal multipliers and summarize findings from 42 studies published between 2000 and 2020."
{{"relevant": false, "relevance_score": 0.2, "reason": "Literature review, no original empirical contribution"}}

Abstract:
{abstract}
""".strip()

__all__ = ["SCREENING_PROMPT"]
