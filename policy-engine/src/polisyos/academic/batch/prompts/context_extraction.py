"""Context extraction prompt for Track B papers."""

CONTEXT_EXTRACTION_SCHEMA_HINT = """
Return strict JSON with keys:
- context_attributes: array of objects describing institutional, cultural, economic, or governance characteristics
- cross_context_comparisons: array of objects comparing attributes across countries/regions
- temporal_trends: array of objects describing how attributes changed over time

Each context_attributes object:
{
  "attribute_name": "short canonical name (e.g. institutional_quality, social_trust, corruption_level)",
  "canonical_name": "dotted canonical form (e.g. governance.institutional_quality)",
  "value": number|null,
  "value_qualitative": "string if no numeric value",
  "unit": "measurement unit or index name",
  "country_codes": ["ISO 2-letter codes"],
  "time_period": "year or range (e.g. 2015-2020)",
  "measurement_method": "name of index, survey, or data source",
  "confidence": number 0..1
}

Each cross_context_comparisons object:
{
  "attribute": "attribute being compared",
  "context_a": {"countries": ["XX"], "value": number|null, "label": "string"},
  "context_b": {"countries": ["YY"], "value": number|null, "label": "string"},
  "comparison_finding": "short description of the difference"
}

Each temporal_trends object:
{
  "attribute": "attribute name",
  "country_codes": ["XX"],
  "direction": "increasing|decreasing|stable|non_linear",
  "time_period": "year range",
  "magnitude": "short description"
}

Rules:
- JSON only.
- Extract only study-setting attributes that would remain meaningful even if the paper asked a different causal question.
- Use the claim inventory provided by Track A as the source of truth for the paper's treatment, outcome, and moderator variables.
- DO NOT extract the paper's own treatment variables, outcome variables, control variables, causal estimates, multipliers, impacts, or effect-size objects as context attributes.
- Use ISO 2-letter country codes.
- If no numeric value is given, use value_qualitative.
- For cross_context_comparisons, only include explicit comparisons the paper makes.
- Confidence reflects how precisely the attribute is measured (survey data > expert assessment > author's qualitative description).
- Prefer canonical prefixes from this shared vocabulary:
  economic. fiscal. governance. institutional. social. demographic. labor. trade.
  environmental. health. education. infrastructure. political.

GOOD examples:
- governance.institutional_quality
- social.social_trust
- governance.corruption_level
- economic.gdp_per_capita
- trade.trade_openness
- political.democratic_index

BAD examples when they are part of the paper's own causal claim:
- tax_revenue
- economic_growth
- fiscal_policy_multiplier
- government_expenditure
- labor_market_effect
- policy_impact
""".strip()
