"""Moderator/heterogeneity extraction prompt for Track C papers."""

MODERATOR_EXTRACTION_SCHEMA_HINT = """
Return strict JSON with keys:
- moderator_findings: array of objects describing how context variables moderate causal effects
- heterogeneity_mechanisms: array of objects explaining WHY effects differ across contexts

Each moderator_findings object:
{
  "base_claim_id": "claim_id from Track A inventory if the moderation applies to one of those claims, else null",
  "base_cause": "cause variable of the moderated causal relationship",
  "base_effect": "effect variable of the moderated causal relationship",
  "moderator": "context variable that moderates the effect (e.g. institutional_quality, income_level)",
  "direction_of_moderation": "amplifying|dampening|reversing|threshold|null",
  "quantitative_interaction": number|null,
  "interaction_pvalue": number|null,
  "evidence_text": "short verbatim quote supporting the finding",
  "confidence": number 0..1
}

Each heterogeneity_mechanisms object:
{
  "moderator": "context variable name",
  "mechanism_description": "short explanation of WHY this moderator changes the effect",
  "theoretical_basis": "named theory or framework, if any"
}

Rules:
- JSON only.
- For moderator_findings, extract ALL explicit tests of effect heterogeneity.
- Use the Track A claim inventory as the source of truth for cause/effect names whenever the moderation applies to one of those claims.
- If a moderator applies to a Track A claim, return the exact `base_claim_id`, `base_cause`, and `base_effect` from that inventory.
- Only leave `base_claim_id` null when the paper reports a moderation finding that does not align to any listed Track A claim.
- direction_of_moderation: "amplifying" = higher moderator strengthens the causal effect, "dampening" = weakens it, "reversing" = flips sign, "threshold" = effect only exists above/below a cutoff, "null" = moderator tested but no significant interaction.
- quantitative_interaction: the interaction coefficient, marginal effect difference, or ANY numeric measure of how the moderator changes the effect size. Look for: interaction term coefficients, triple-difference estimates, subgroup coefficient differences, slope changes. If the paper reports "the effect is 0.15 for group A and 0.08 for group B", compute and report the difference (0.07). ONLY use null when absolutely no numeric value can be derived.
- interaction_pvalue: the p-value for the interaction term or heterogeneity test. Apply these mappings when the paper uses verbal significance levels:
  "significant at 1%" or "p < 0.01" → 0.01
  "significant at 5%" or "p < 0.05" → 0.05
  "significant" (no level stated) → 0.05
  "marginally significant" or "p < 0.10" → 0.10
  "not significant" or "insignificant" → 0.50
  ONLY use null when the paper says nothing about whether this specific moderation is significant.
- CRITICAL: Do NOT leave BOTH quantitative_interaction AND interaction_pvalue as null when the evidence_text contains any of: "significant", "p-value", "p <", "p=", numeric coefficients, or percentage differences. Extract the best available number.
- Only include moderator_findings where the paper explicitly tests the interaction, not where it merely speculates.
- For heterogeneity_mechanisms, include the paper's explanation of WHY effects differ, even if qualitative.
- Prefer canonical prefixes from this shared vocabulary:
  economic. fiscal. governance. institutional. social. demographic. labor. trade.
  environmental. health. education. infrastructure. political.
""".strip()
