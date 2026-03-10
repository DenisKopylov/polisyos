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

Title: {title}
Abstract: {abstract}
Method cues: {method_cues}
""".strip()
