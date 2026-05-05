"""Paper classification prompt for three-track extraction routing."""

PAPER_CLASSIFICATION_PROMPT = """
You are classifying an academic paper for extraction routing.
Given the title, abstract, and method cues, determine the paper's primary contribution type.

Return strict JSON: {{"paper_kind": "<kind>", "confidence": <number 0..1>, "reason": "short string"}}

Paper kinds:
- empirical_causal: Original causal identification study with effect estimates (RCT, IV, DiD, RDD, synthetic control, event study, etc.)
- context_characterization: Describes institutional, cultural, economic, or governance characteristics of countries/regions/periods without primary causal claims
- heterogeneity_analysis: Primarily investigates when, where, or for whom a causal effect varies (effect heterogeneity, moderator analysis, cross-country comparison of effects)
- review_systematic: Systematic review or meta-analysis synthesizing multiple studies
- theoretical: Theoretical or conceptual framework paper
- descriptive: Descriptive statistics, correlational analysis, or data documentation
- mixed: Contains significant elements of both causal estimation AND context/moderator analysis

Rules:
- Choose the SINGLE best category based on the paper's PRIMARY contribution.
- Use "mixed" only when the paper genuinely contributes both original causal estimates AND substantial context characterization or heterogeneity analysis.
- If unsure between empirical_causal and heterogeneity_analysis, prefer heterogeneity_analysis if the main research question is about when/where effects differ.
- Use "empirical_causal" only when the paper's primary contribution is an original causal estimate or explicit causal identification design.
- Review, synthesis, policy-perspective, governance, historical, or cross-country characterization papers should not be labeled "empirical_causal" unless they clearly center an original causal identification strategy.
- JSON only, no explanations outside the JSON.

Examples:

Title: "The Effect of Unemployment Insurance on Job Search: A Regression Discontinuity Approach"
Abstract: "We exploit an age-based eligibility cutoff to estimate the causal effect of UI duration on job-finding rates using a regression discontinuity design. Longer UI duration reduces search intensity by 12%."
{{"paper_kind": "empirical_causal", "confidence": 0.95, "reason": "RDD-based causal estimate of UI duration on job search"}}

Title: "Institutional Quality and Economic Development: Cross-Country Evidence"
Abstract: "Using the World Governance Indicators and Penn World Table, we document how institutional quality metrics differ across 120 countries and examine their correlation with income per capita from 1996-2018."
{{"paper_kind": "context_characterization", "confidence": 0.85, "reason": "Cross-country documentation of institutional quality without causal identification"}}

Title: "When Do Cash Transfers Work? Heterogeneity by Income and Governance Quality"
Abstract: "We pool 15 RCTs of cash transfers across developing countries and test whether effects on consumption vary by recipient income level and local governance quality."
{{"paper_kind": "heterogeneity_analysis", "confidence": 0.90, "reason": "Primary contribution is heterogeneity of effects by moderators, not a single causal estimate"}}

Title: "Fiscal Multipliers: A Meta-Analysis of 98 Studies"
Abstract: "We conduct a systematic meta-analysis pooling 412 multiplier estimates from 98 studies. Our preferred specification yields a multiplier of 1.3 (95% CI: 0.9-1.7)."
{{"paper_kind": "review_systematic", "confidence": 0.95, "reason": "Meta-analysis synthesizing multiple studies"}}

Title: {title}
Abstract: {abstract}
Method cues: {method_cues}
""".strip()

__all__ = ["PAPER_CLASSIFICATION_PROMPT"]
