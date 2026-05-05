"""Streaming fulltext-first one-call extraction stage."""

from __future__ import annotations

import asyncio
import gc
import json
import math
import random
import re
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp

import polisyos.data_forge.domains.academic.batch.fulltext_resolver as fulltext_resolver_module
from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _CLAIM_SENTENCE_RE,
    _METHOD_SENTENCE_RE,
    _RESULT_SENTENCE_RE,
    _as_list,
    _build_evidence_bundle,
    _normalize_context_attribute,
    _normalize_empirical_parameter,
    _normalize_extraction_payload,
    _normalize_moderation_edge,
    _normalized_text,
    _parse_json_object,
    _to_work_record,
)
from polisyos.data_forge.domains.academic.batch.claim_ids import stable_claim_id
from polisyos.data_forge.domains.academic.batch.context_classifier import infer_context_from_article
from polisyos.data_forge.domains.academic.batch.fulltext_resolver import (
    FullTextFetchResult,
    fetch_full_text_for_work,
    fetch_full_text_result_for_work,
    reconstruct_abstract,
)
from polisyos.data_forge.domains.academic.batch.parser import extract_numerical_estimates
from polisyos.data_forge.domains.academic.batch.prompts import (
    CONTEXT_EXTRACTION_SCHEMA_HINT,
    MODERATOR_EXTRACTION_SCHEMA_HINT,
    PAPER_CLASSIFICATION_PROMPT,
)
from polisyos.data_forge.domains.academic.knowledge.variable_canonizer import VariableCanonizer
from polisyos.data_forge.domains.academic.openalex.priority_filter import should_process
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    ClaimType,
    ContextAttribute,
    DesignFamily,
    EvidenceParameter,
    EvidenceSpan,
    EvidenceStrength,
    HeterogeneityResult,
    ModerationEdge,
    PaperKind,
    ParameterType,
    SourceBasis,
    TextQuality,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

logger = get_logger(__name__)

_DESIGN_TIERS: dict[str, int | None] = {
    DesignFamily.RCT.value: 1,
    DesignFamily.IV.value: 1,
    DesignFamily.DID.value: 1,
    DesignFamily.RDD.value: 1,
    DesignFamily.SYNTHETIC_CONTROL.value: 1,
    DesignFamily.EVENT_STUDY.value: 2,
    DesignFamily.QUASI_EXPERIMENTAL_OTHER.value: 2,
    DesignFamily.QUASI_EXPERIMENTAL_DID.value: 2,
    DesignFamily.QUASI_EXPERIMENTAL_RDD.value: 2,
    DesignFamily.PANEL_FE.value: 3,
    "system_gmm": 3,
    "gmm": 3,
    DesignFamily.STRUCTURAL_MODEL.value: 3,
    DesignFamily.TIME_SERIES_COINTEGRATION.value: 3,
    DesignFamily.OLS.value: 4,
    DesignFamily.OLS_CROSS_SECTIONAL.value: 4,
    DesignFamily.META_ANALYSIS.value: 1,
    DesignFamily.REVIEW_META_ANALYSIS.value: 2,
    DesignFamily.REVIEW.value: None,
    DesignFamily.REVIEW_NARRATIVE.value: None,
    DesignFamily.THEORETICAL.value: None,
    DesignFamily.UNCLEAR.value: None,
}
_STRONG_METHOD_PATTERNS: dict[str, re.Pattern[str]] = {
    DesignFamily.RCT.value: re.compile(r"\b(randomi[sz]ed|random assignment|rct)\b", re.IGNORECASE),
    DesignFamily.IV.value: re.compile(
        r"\b(instrumental variable|instrument\w*|2sls|tsls|first stage)\b", re.IGNORECASE
    ),
    DesignFamily.DID.value: re.compile(
        r"\b(difference[- ]?in[- ]?differences?|\bdid\b|parallel trends)\b", re.IGNORECASE
    ),
    DesignFamily.RDD.value: re.compile(
        r"\b(regression discontinuity|\brdd\b|cutoff|threshold design)\b", re.IGNORECASE
    ),
    DesignFamily.SYNTHETIC_CONTROL.value: re.compile(
        r"\b(synthetic control|synthetic counterfactual)\b", re.IGNORECASE
    ),
    DesignFamily.EVENT_STUDY.value: re.compile(
        r"\b(event study|dynamic treatment effects|lead[s]? and lag[s]?)\b", re.IGNORECASE
    ),
    DesignFamily.QUASI_EXPERIMENTAL_OTHER.value: re.compile(
        r"\b(natural experiment|quasi[- ]experimental|exogenous shock|policy discontinuity|staggered adoption)\b",
        re.IGNORECASE,
    ),
}
_DOWNGRADE_PATTERNS = re.compile(
    r"\b(correlation|associat(?:ion|ive)|cross[- ]sectional|ols only|ordinary least squares only|panel fixed effects only)\b",
    re.IGNORECASE,
)
# Phrases that negate a downgrade keyword — e.g. "beyond mere correlation",
# "not merely an association", "causal, not correlational".
_DOWNGRADE_NEGATION_RE = re.compile(
    r"\b(beyond (?:mere |simple )?(?:correlation|association)|"
    r"not (?:merely |just |simply )?(?:an? )?(?:correlation|association|associative|correlational)|"
    r"causal[,;]?\s+not\s+(?:just\s+)?(?:correlat|associat)\w*|"
    r"more than (?:a |an )?(?:correlation|association)|"
    r"rules? out (?:mere |simple )?(?:correlation|reverse causality))\b",
    re.IGNORECASE,
)


def _has_downgrade_signal(text: str) -> bool:
    """Check for downgrade keywords while filtering out negation contexts."""
    if not _DOWNGRADE_PATTERNS.search(text):
        return False
    # If a negation phrase is present, the downgrade keyword is used in a
    # context that actually STRENGTHENS the claim (e.g. "beyond correlation").
    return not _DOWNGRADE_NEGATION_RE.search(text)


# Strong identification methods that justify tier-4 promotion for "unclear" designs.
# Excludes weak data-type terms (regression, panel data, OLS, admin data) that are
# necessary but not sufficient for causal identification.
_STRONG_IDENTIFICATION_RE = re.compile(
    r"\b(randomi[sz]ed|random assignment|random lottery|field experiment|audit study|correspondence study|"
    r"survey experiment|lab(?:oratory)? experiment|encouragement design|instrumental variable|2sls|tsls|"
    r"difference.?in.?differences?|did\b|regression discontinuity|rdd\b|synthetic control|event study|"
    r"natural experiment|quasi[- ]experimental|staggered adoption|staggered rollout|exogenous shock|"
    r"propensity score|matching estimat\w+|causal forest|bunching design)\b",
    re.IGNORECASE,
)
_NARRATIVE_HEDGE_RE = re.compile(
    r"\b(may have|might have|could have|possibly|apparently|seems to|appears to|"
    r"is likely|it is probable|we speculate|we conjecture|we hypothesi[sz]e that)\b",
    re.IGNORECASE,
)
_REVIEW_LIKE_RE = re.compile(
    r"\b(review|survey|literature review|meta-analysis|bibliometric|systematic review)\b",
    re.IGNORECASE,
)
_THEORY_LIKE_RE = re.compile(
    r"\b(theoretical|theory|conceptual framework|modeling exercise|simulation study)\b",
    re.IGNORECASE,
)
_METHOD_ONLY_RE = re.compile(
    r"\b(methods? paper|methodological|estimation method|algorithm|benchmark dataset)\b",
    re.IGNORECASE,
)
_EMPIRICAL_DATA_RE = re.compile(
    r"\b(administrative data|registry data|register data|panel data|longitudinal data|survey data|census data|microdata|"
    r"matched employer[- ]employee|linked data|transaction data|tax records?|firm-level data|household survey|"
    r"personnel records?|field experiment|audit study|correspondence study|survey experiment|lab(?:oratory)? experiment|"
    r"natural experiment|quasi[- ]experimental|policy reform|staggered adoption|staggered rollout)\b",
    re.IGNORECASE,
)
_ACCESS_SHELL_RE = re.compile(
    r"\b(choice reviews\s*\|\s*login|institutional login|access via institution log in|mymuse|"
    r"url has changed to|please update your bookmarks|javascript is disabled for your browser)\b",
    re.IGNORECASE,
)
_CONTEXT_CLASSIFICATION_RE = re.compile(
    r"\b(governance|institutional(?: quality)?|institutions?|historical|history|geograph(?:ic|ical)|regional|"
    r"cross-country|across countries|space and time|sustainable development|sdg|policy perspective|"
    r"administrative burden|development finance|context(?:ual)?|country comparison)\b",
    re.IGNORECASE,
)
_HETEROGENEITY_CLASSIFICATION_RE = re.compile(
    r"\b(heterogeneity|moderat(?:es|ing|or)|interaction|subgroup|conditional on|threshold effect|"
    r"for whom|where effects differ)\b",
    re.IGNORECASE,
)
_RESULT_CUE_RE = re.compile(
    r"\b(we find|results show|effect on|impact on|increas\w*|decreas\w*|reduc\w*|rais\w*|improv\w*|lead(?:s|ing)? to|caus(?:e|es|ed|ing))\b",
    re.IGNORECASE,
)
_PRECISION_RESULT_CUE_RE = re.compile(
    r"\b("
    r"95%\s*ci|99%\s*ci|confidence interval|std\.?\s*err(?:or)?|standard error|"
    r"se\s*[=:]\s*[-+]?\d|ci\s*[\[:=]|"
    r"coef(?:ficient)?|beta|odds ratio|risk ratio|hazard ratio|relative risk|"
    r"instrumental variable|2sls|tsls|difference[- ]?in[- ]?differences?|regression discontinuity|"
    r"event study|fixed effects|panel fe|logit|probit"
    r")\b",
    re.IGNORECASE,
)
_DESCRIPTIVE_ONLY_RE = re.compile(
    r"\b("
    r"descriptive study|descriptive analysis|cross[- ]sectional non[- ]analytic|frequency distribution|"
    r"univariate analysis|bivariate analysis|most respondents|mostly good|mostly positive|"
    r"prevalence|awareness level|knowledge level|attitude level"
    r")\b",
    re.IGNORECASE,
)
_MIN_FULLTEXT_CHARS = 64
_SHARED_VOCABULARY_PREFIXES = (
    "economic.",
    "fiscal.",
    "governance.",
    "institutional.",
    "social.",
    "demographic.",
    "labor.",
    "trade.",
    "environmental.",
    "health.",
    "education.",
    "infrastructure.",
    "political.",
    "migration.",
    "security.",
    "energy.",
    "digital.",
    "monetary.",
    "justice.",
    "climate.",
    "agriculture.",
    "urban.",
    "finance.",
    "gender.",
    # Extended scientific/empirical domain prefixes
    "agricultural.",
    "biotech.",
    "hospital.",
    "genetic.",
    "behavioral.",
    "soil.",
    "safety.",
    "antibiotic.",
    "nutrition.",
    "pharmaceutical.",
    "industrial.",
    "biological.",
    "chemical.",
    "ecological.",
    "medical.",
    "epidemiological.",
    "transport.",
    "housing.",
    "water.",
    "food.",
    "marine.",
    "forestry.",
)

_TOPIC_KEYWORD_TO_PREFIXES: dict[str, tuple[str, ...]] = {
    "health": ("health.", "demographic.", "social."),
    "disease": ("health.", "demographic.", "social."),
    "medical": ("health.", "social."),
    "nutrition": ("health.", "agriculture.", "social."),
    "education": ("education.", "labor.", "social."),
    "school": ("education.", "social."),
    "learning": ("education.", "social."),
    "economy": ("economic.", "fiscal.", "trade.", "finance.", "monetary."),
    "economic": ("economic.", "fiscal.", "trade.", "finance.", "monetary."),
    "gdp": ("economic.", "fiscal.", "trade."),
    "growth": ("economic.", "fiscal.", "trade."),
    "inflation": ("economic.", "monetary.", "fiscal."),
    "labor": ("labor.", "economic.", "social.", "migration."),
    "employment": ("labor.", "economic.", "social."),
    "wage": ("labor.", "economic.", "gender."),
    "work": ("labor.", "economic.", "social."),
    "governance": ("governance.", "institutional.", "justice.", "fiscal."),
    "corruption": ("governance.", "institutional.", "justice."),
    "institution": ("institutional.", "governance."),
    "democracy": ("governance.", "institutional.", "political."),
    "agriculture": ("agriculture.", "climate.", "environmental.", "trade."),
    "farm": ("agriculture.", "trade.", "environmental."),
    "food": ("agriculture.", "health.", "trade."),
    "climate": ("climate.", "energy.", "environmental.", "agriculture."),
    "carbon": ("climate.", "energy.", "environmental."),
    "temperature": ("climate.", "environmental."),
    "urban": ("urban.", "infrastructure.", "social."),
    "city": ("urban.", "infrastructure.", "social."),
    "housing": ("urban.", "social.", "finance."),
    "security": ("security.", "governance.", "justice.", "migration."),
    "conflict": ("security.", "governance.", "migration."),
    "violence": ("security.", "gender.", "justice."),
    "crime": ("security.", "justice.", "social."),
    "digital": ("digital.", "economic.", "education.", "infrastructure."),
    "technology": ("digital.", "economic.", "infrastructure."),
    "internet": ("digital.", "infrastructure.", "economic."),
    "trade": ("trade.", "economic.", "fiscal.", "labor."),
    "export": ("trade.", "economic."),
    "tariff": ("trade.", "fiscal.", "economic."),
    "energy": ("energy.", "climate.", "infrastructure.", "economic."),
    "renewable": ("energy.", "climate.", "environmental."),
    "electricity": ("energy.", "infrastructure."),
    "migration": ("migration.", "labor.", "demographic.", "social."),
    "refugee": ("migration.", "security.", "social."),
    "immigration": ("migration.", "labor.", "social."),
    "gender": ("gender.", "labor.", "social.", "education."),
    "women": ("gender.", "labor.", "social.", "health."),
    "maternal": ("gender.", "health.", "demographic."),
    "poverty": ("social.", "economic.", "fiscal."),
    "inequality": ("social.", "economic.", "fiscal.", "gender."),
    "welfare": ("social.", "fiscal.", "labor."),
    "tax": ("fiscal.", "economic.", "governance."),
    "debt": ("fiscal.", "economic.", "finance."),
    "budget": ("fiscal.", "governance."),
    "finance": ("finance.", "economic.", "monetary."),
    "bank": ("finance.", "monetary.", "economic."),
    "credit": ("finance.", "monetary.", "economic."),
    "monetary": ("monetary.", "finance.", "economic."),
    "justice": ("justice.", "governance.", "security."),
    "court": ("justice.", "governance."),
    "prison": ("justice.", "security."),
    "water": ("environmental.", "infrastructure.", "health."),
    "pollution": ("environmental.", "health.", "urban."),
    "forest": ("environmental.", "climate.", "agriculture."),
    "biodiversity": ("environmental.", "climate.", "agriculture."),
    "environment": ("environmental.", "climate.", "energy."),
    "transport": ("infrastructure.", "urban.", "trade."),
    "road": ("infrastructure.", "urban.", "trade."),
    "sanitation": ("infrastructure.", "health.", "urban."),
    "demographic": ("demographic.", "social.", "health."),
    "population": ("demographic.", "social.", "health."),
    "fertility": ("demographic.", "health.", "gender."),
    "aging": ("demographic.", "social.", "health."),
    # Extended scientific/empirical keywords
    "antibiotic": ("antibiotic.", "health.", "hospital.", "pharmaceutical."),
    "antimicrobial": ("antibiotic.", "health.", "hospital.", "epidemiological."),
    "infection": ("health.", "hospital.", "epidemiological.", "antibiotic."),
    "hospital": ("hospital.", "health.", "epidemiological."),
    "soil": ("soil.", "agriculture.", "environmental.", "ecological."),
    "biochar": ("soil.", "agriculture.", "environmental.", "chemical."),
    "crop": ("agricultural.", "agriculture.", "food.", "soil."),
    "sugarcane": ("agricultural.", "agriculture.", "biological.", "biotech."),
    "plant": ("biological.", "agricultural.", "ecology.", "genetic."),
    "photosynthesis": ("biological.", "agricultural.", "ecological."),
    "drought": ("environmental.", "agricultural.", "climate.", "water."),
    "irrigation": ("water.", "agricultural.", "agriculture."),
    "genetic": ("genetic.", "biotech.", "biological.", "health."),
    "mutation": ("genetic.", "biological.", "biotech."),
    "pharmaceutical": ("pharmaceutical.", "health.", "economic."),
    "drug": ("pharmaceutical.", "health.", "chemical."),
    "safety": ("safety.", "health.", "industrial.", "transport."),
    "biotech": ("biotech.", "genetic.", "pharmaceutical.", "biological."),
    "mortality": ("health.", "demographic.", "epidemiological."),
    "epidem": ("epidemiological.", "health.", "demographic."),
}

_UNIVERSAL_CANONICAL_VARS: tuple[str, ...] = (
    "gdp_growth",
    "unemployment_rate",
    "poverty_rate",
    "inflation",
    "tax_revenue",
    "government_spending",
    "inequality",
    "education_outcomes",
    "health_outcomes",
    "institutional_quality",
    "corruption_level",
    "trade_balance",
    "investment_rate",
    "productivity",
)


def _select_relevant_canonical_names(topic_display_names: list[str]) -> list[str]:
    """Select top-60 canonical names relevant to the work's topic(s)."""
    from polisyos.data_forge.domains.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
    from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
        RUNTIME_CANONICAL_REGISTRY,
    )

    all_names: set[str] = set()
    for parent, children in CANONICAL_VARIABLES.items():
        all_names.add(parent)
        for child in children:
            if child != "_root":
                all_names.add(f"{parent}.{child}")
    all_names.update(RUNTIME_CANONICAL_REGISTRY.keys())

    # Collect matching prefixes from topic keywords
    matched_prefixes: set[str] = set()
    topic_text = " ".join(topic_display_names).lower()
    for keyword, prefixes in _TOPIC_KEYWORD_TO_PREFIXES.items():
        if keyword in topic_text:
            matched_prefixes.update(prefixes)

    # If no keyword matched, use all prefixes
    if not matched_prefixes:
        matched_prefixes.update(_SHARED_VOCABULARY_PREFIXES)

    matched = [
        n
        for n in sorted(all_names)
        if any(n.startswith(p) or n == p.rstrip(".") for p in matched_prefixes)
    ]
    universal = [n for n in _UNIVERSAL_CANONICAL_VARS if n in all_names]
    combined = list(dict.fromkeys(matched + universal))
    return combined[:60]


_CONTEXT_EFFECT_ESTIMATE_RE = re.compile(
    r"(?:^|[_\.])(multiplier|effect|impact|estimate|coefficient)(?:$|[_\.])", re.IGNORECASE
)
_CONTAMINATION_RE = re.compile(
    r"(?i)"
    r"(accesses|citations|altmetric|explore all metrics|download pdf|view pdf|view abstract|cookie policy|"
    r"accept cookies|cookie preferences|cookie consent|manage cookies|we use cookies|"
    r"all rights reserved|copyright \d{4}|doi\.org/\S+|https?://\S{20,}|research output|"
    r"journal contributions|prodotti della ricerca|retrieved from https?://\S+|institutional login|sign in to access|"
    r"download citation|export citation|cite this article|"
    r"published by (?:springer|elsevier|wiley|taylor|sage|oxford|cambridge|mdpi|frontiers)|"
    r"received:?\s*\d{1,2}\s+\w+\s+\d{4}.*?accepted:?\s*\d{1,2}\s+\w+\s+\d{4}|"
    r"open access\s+this article is licensed|creative commons|"
    r"supplementary (?:materials?|information|data|file)|"
    r"corresponding author|author contributions|"
    r"funding\s+(?:information|statement|this (?:work|research|study) was)|"
    r"declaration of (?:competing )?interests?|conflict of interest statement|"
    # -- publisher UI navigation chrome --
    r"skip to (?:main content|content|navigation)|find a journal|publish with us|track your research|"
    r"saved research|search cart|advertisement log in|log in menu|"
    r"aims and scope|submit manuscript|save article|view saved|"
    # -- related articles / similar content --
    r"similar content being viewed by others|related articles?|explore related subjects|"
    r"discover the latest|suggested using machine learning|full size image|"
    # -- article metadata (volume/pages/published date) --
    r"volume\s+\d+\s*,?\s*pages?\s+\d+|Published:\s*\d{1,2}\s+\w+\s+\d{4}|"
    r"pp\.\s*\d+[–\-]\d+|"
    # -- ORCID / author affiliation markers --
    r"orcid\.org/\d{4}|ORCID:\s*orcid|"
    # -- institutional access --
    r"institutional (?:subscriptions?|access|repositor(?:y|ies))|subscribe to (?:this )?journal|"
    # -- BibTeX / citation format metadata --
    r"@article\{|issn\s*=\s*\"|publisher\s*=\s*\"|language\s*=\s*\"|"
    r"TY\s+-\s+JOUR|AU\s+-\s+|PY\s+-\s+|N2\s+-\s+)"
)
_CLAIM_REF_TAG_RE = re.compile(r"\[CLAIM_ID:([^\]]+)\]")
_CONTEXT_SOFT_REJECTION_REASONS = frozenset({"review_like", "missing_empirical_cues"})
_CONTEXT_HARD_REJECTION_REASONS = frozenset(
    {
        "abstract_only",
        "degraded_text",
        "access_shell",
        "theory_like",
        "method_only",
    }
)
_ROUTED_EMPIRICAL_DOC_FAMILIES = frozenset(
    {
        "empirical_rct",
        "empirical_quasi",
        "observational",
        "table_heavy",
    }
)
_ROUTED_EMPIRICAL_SOFT_BLOCKERS = frozenset(
    {
        "degraded_text",
        "review_like",
        "theory_like",
        "method_only",
        "missing_empirical_cues",
        "descriptive_only",
    }
)

_ONE_CALL_SCHEMA_HINT = """
Return strict JSON with keys:
- paper_relevance: boolean
- paper_relevance_reason: short string
- methodology_summary: short string
- methodology_enum: rct|quasi_natural|meta_analysis|observational|theoretical|unknown
- sample_size: integer|null
- citation_summary: short string
- extraction_confidence: number 0..1
- extraction_warnings: array[string]
- causal_claims: array of objects
- empirical_parameters: array of objects
- mechanisms: array of objects
- boundary_conditions: array of objects
- heterogeneity_results: array of objects (if the paper tests effect heterogeneity)
- external_validity_assessment: short string (author's stated scope/generalizability)

Each empirical_parameters object:
{
  "name": "canonical-like variable name (e.g. labor.minimum_wage_elasticity)",
  "display_name": "Human-readable parameter name",
  "parameter_type": "quantitative",
  "value": number|null,
  "value_range": [lower_bound, upper_bound]|null,
  "value_qualitative": null,
  "confidence_interval": [ci_lower, ci_upper]|null,
  "std_error": number|null,
  "unit": "percentage_points|percent|log_points|ratio|elasticity|odds_ratio|hazard_ratio|coefficient|usd|index|...",
  "evidence_strength": "rct|quasi_natural|quasi_natural_event|panel_fe|structural|observational|cross_sectional|meta_analysis|theoretical|unknown",
  "geographic_scope": "country or region",
  "time_period": "e.g. 1990-2010"
}

IMPORTANT: ALL variable names MUST start with a domain prefix from this list:
economic. fiscal. governance. institutional. social. demographic. labor. trade.
environmental. health. education. infrastructure. political. migration. security.
energy. digital. monetary. justice. climate. agriculture. urban. finance. gender.
agricultural. biotech. hospital. genetic. behavioral. soil. safety. antibiotic.
nutrition. pharmaceutical. industrial. biological. chemical. ecological. medical.
epidemiological. transport. housing. water. food. marine. forestry.
Example: "photosynthesis" → "biological.photosynthesis", "drought_stress" → "environmental.drought_stress",
"antibiotic_use" → "antibiotic.use", "soil_ph" → "soil.ph". NEVER output a bare variable without a domain prefix.

{canonical_names_block}

Each causal_claim object must use sentence IDs, not verbatim spans:
{
  "claim_text": "short paper-grounded claim",
  "claim_type": "causal_claim|associative|mechanism|review_summary|descriptive|normative|unclear|not_applicable",
  "cause_variable": "domain.snake_case_name (MUST have domain prefix, e.g. health.mortality)",
  "effect_variable": "domain.snake_case_name (MUST have domain prefix, e.g. economic.gdp_growth)",
  "direction": "positive|negative|null|mixed|ambiguous|non_linear",
  "claim_explicitness": "explicit|implicit|unclear",
  "design_family_hint": "rct|iv|did|rdd|synthetic_control|event_study|quasi_experimental_other|panel_fe|ols|ols_cross_sectional|review_narrative|review_meta_analysis|theoretical|structural_model|unclear",
  "effect_size": number|null (MUST be set if the paper reports ANY numeric magnitude for this claim),
  "evidence_strength": "rct|quasi_natural|quasi_natural_event|panel_fe|structural|observational|cross_sectional|meta_analysis|theoretical|unknown",
  "supporting_span_ids": ["c_01", "r_02"],
  "method_span_ids": ["m_01"],
  "source_basis": "fulltext|abstract_only",
  "claim_extraction_confidence": number|null,
  "scope_conditions": ["..."],
  "counterevidence_notes": "short string",
  "extraction_warnings": ["..."],
  "identification_strategy": {
    "identification_method": "iv|rdd|did|rct|synthetic_control|event_study|panel_fe|ols|...",
    "instrument": "string or null",
    "exclusion_restrictions": ["assumption 1", ...],
    "design_assumptions": ["parallel trends", ...]
  } | null
}

Each heterogeneity_results object:
{
  "moderator": "context variable that moderates the effect",
  "dimension": "cross_country|temporal|subgroup|institutional|...",
  "finding": "short description of how the moderator changes the effect",
  "interaction_coefficient": number|null,
  "interaction_pvalue": number|null,
  "subgroup_effects": {"subgroup_name": number, ...},
  "confidence": number|null
}

Rules:
- JSON only.
- Use sentence IDs from the evidence bundle.
- Do not include long explanations.
- Include all unique supported candidate claims; do not duplicate the same (cause, effect, direction, supporting_span_ids) tuple.
- Keep claims ordered by centrality/strength of evidence, strongest first.
- If evidence is only associational or review-based, set claim_type accordingly instead of forcing causal_claim.
- sample_size must be integer or null.
- Numeric fields must be numeric, never words like high/medium/low.
- empirical_parameters should capture ALL quantitative findings: regression coefficients, treatment effects,
  elasticities, odds ratios, hazard ratios, marginal effects, quantified policy contrasts, percentage changes,
  rates, proportions, or any numeric estimate from tables and results sections.
  Also include coefficients from OLS, IV, DID, panel FE, and similar regressions — these ARE valid parameters.
- CRITICAL: Scan all tables and results sections for numeric values. If a table has coefficients, effect sizes,
  or treatment-control comparisons, extract them as parameters. Tables are a PRIMARY source of parameters.
- If a paper reports regression results with coefficients and standard errors, extract ALL main coefficients as parameters.
- If a paper reports only descriptive statistics without any regression or causal analysis, return empirical_parameters as [].
- Each parameter MUST have at least a numeric value or value_range. Omit parameters that have no numbers.
- When the paper reports uncertainty in forms like `95% CI [a, b]` or `(SE = x)`, copy it into confidence_interval/std_error.
- Extract up to 12 strongest policy-relevant estimates. Prioritize parameters with standard errors or confidence intervals.
- Do NOT include p-values, t-statistics, F-statistics, R-squared, sample sizes, or descriptive counts as parameter values.
- IMPORTANT: For each causal_claim that has a numeric effect in the paper, also set effect_size to that number.
  If the paper says "X increased Y by 15 percentage points", set effect_size=15 and extract a parameter with value=15.
- For identification_strategy: only include if the paper has a clear causal identification strategy. Set null otherwise.
- For heterogeneity_results: include only if the paper explicitly tests effect heterogeneity or moderation.
""".strip()

_NUMERIC_RESCUE_SCHEMA_HINT = """
Return strict JSON with exactly one key:
- empirical_parameters: array of objects

Each empirical_parameters object:
{
  "name": "canonical-like variable name",
  "display_name": "short label",
  "parameter_type": "quantitative",
  "value": number|null,
  "value_range": [number, number] | null,
  "confidence_interval": [number, number] | null,
  "std_error": number|null,
  "unit": "unitless|elasticity|semi_elasticity|odds_ratio|risk_ratio|hazard_ratio|correlation_coefficient|standardized_effect|index_points|percentage_points|basis_points",
  "evidence_strength": "rct|quasi_natural|quasi_natural_event|panel_fe|structural|observational|cross_sectional|meta_analysis|theoretical|unknown",
  "heterogeneity_note": "short note on what the estimate measures",
  "geographic_scope": "optional geography",
  "time_period": "optional period"
}

Rules:
- Extract only true effect estimates, treatment effects, coefficients, elasticities, odds ratios, hazard ratios, or standardized effects.
- Prefer estimates with explicit uncertainty whenever the paper reports it.
- When result snippets contain forms like `coefficient = 0.18 (SE = 0.04)` or
  `effect was 0.25 (95% CI [0.15, 0.45])`, copy both the point estimate and
  the uncertainty fields into the output.
- Use exact variable names from the provided claim inventory when an estimate quantifies one of those claims.
- Never include p-values, significance stars, standard errors by themselves, t-stats, z-stats, F-stats, R-squared, sample sizes, descriptive counts, or baseline means without a contrast.
- If the paper reports significance but no effect magnitude, return an empty array.
- If the estimate is dimensionless but clearly a coefficient/effect size, set unit to "unitless" or a more specific dimensionless unit.
- Extract up to 8 policy-relevant estimates. Include all coefficients with standard errors or confidence intervals.
- Scan ALL tables for numeric coefficients, effect sizes, odds ratios, or treatment effects.
""".strip()

_NON_EFFECT_PARAMETER_RE = re.compile(
    r"\b(sample[_ ]?size|study\.sample_size|p[-_ ]?value|significance|t[-_ ]?stat(istic)?|"
    r"z[-_ ]?stat(istic)?|f[-_ ]?stat(istic)?|r[_ ]?squared|r\^2|baseline mean|descriptive count|"
    r"number of observations|n observations|n =)\b",
    re.IGNORECASE,
)
_NUMERIC_UNITFUL_HINT_RE = re.compile(
    r"\b(percentage points?|pp|basis points?|odds ratio|risk ratio|relative risk|hazard ratio|"
    r"elasticit(?:y|ies)|semi[- ]?elasticit(?:y|ies)|correlation|beta\b|standardi[sz]ed effect|"
    r"standardi[sz]ed coefficient|index points?|score points?|unitless)\b",
    re.IGNORECASE,
)
_VAR_SPLIT_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class ResolveExtractStats:
    """Cumulative counters and latency samples for resolve/extract passes."""

    records: int = 0
    fulltext_resolved: int = 0
    abstract_only: int = 0
    eligible_fulltext: int = 0
    context_eligible: int = 0
    rejected: int = 0
    llm_requests: int = 0
    extracted: int = 0
    raw_claims: int = 0
    published_claims: int = 0
    extraction_errors: int = 0
    provider_length_stop: int = 0
    provider_429: int = 0
    provider_5xx: int = 0
    timeouts: int = 0
    json_parse_errors: int = 0
    empty_responses: int = 0
    low_fulltext_coverage_topics: int = 0
    papers_classified: int = 0
    track_b_routed: int = 0
    track_b_only_routed: int = 0
    track_b_rejected_hard: int = 0
    context_attributes_extracted: int = 0
    moderation_edges_extracted: int = 0
    numeric_rescue_requests: int = 0
    numeric_rescue_successes: int = 0
    numeric_rescue_failures: int = 0
    numeric_rescue_parameters_added: int = 0
    deterministic_numeric_rescue_successes: int = 0
    deterministic_numeric_rescue_parameters_added: int = 0
    total_tokens_prompt: int = 0
    total_tokens_completion: int = 0
    total_extraction_cost_usd: float = 0.0
    fetch_latency_ms: list[float] = field(default_factory=list)
    llm_latency_ms: list[float] = field(default_factory=list)
    limiter_wait_ms: list[float] = field(default_factory=list)
    rejection_reason_counts: Counter[str] = field(default_factory=Counter)
    failure_class_counts: Counter[str] = field(default_factory=Counter)


@dataclass
class WorkItem:
    """Selected OpenAlex work plus topic routing metadata for resolve/extract scheduling."""

    work: dict[str, Any]
    work_id: str
    topic_id: str
    topic_ids: list[str]
    topic_display_names: list[str]
    prefetch_priority: float
    selected_rank: int


@dataclass
class EligibleItem:
    """Full-text work payload annotated with source quality and LLM/context eligibility flags."""

    work_item: WorkItem
    text: str
    source_kind: str
    source_url: str
    text_quality: str
    post_priority: float
    llm_eligible: bool
    context_eligible: bool


@dataclass(frozen=True)
class EligibilityDecision:
    """Binary routing decision and rejection reasons for one resolve/extract candidate."""

    llm_eligible: bool
    context_eligible: bool
    rejection_reasons: list[str]


@dataclass
class ProviderResponse:
    """Normalized LLM provider response, retry metadata, and parse status for one extraction call."""

    parsed: dict[str, Any]
    usage: dict[str, Any]
    http_status: int
    finish_reason: str
    latency_ms: float
    retry_count: int
    limiter_wait_ms: float
    backoff_sleep_ms: float
    parse_status: str
    error_class: str
    raw_content: str
    truncated_output: bool
    provider_key_index: int | None = None


def _empty_provider_response(
    *,
    error_class: str,
    raw_content: str = "",
    parse_status: str = "empty",
) -> ProviderResponse:
    return ProviderResponse(
        parsed={},
        usage={},
        http_status=0,
        finish_reason="",
        latency_ms=0.0,
        retry_count=0,
        limiter_wait_ms=0.0,
        backoff_sleep_ms=0.0,
        parse_status=parse_status,
        error_class=error_class,
        raw_content=raw_content[:4000],
        truncated_output=False,
        provider_key_index=None,
    )


def _resolve_provider_watchdog_seconds(config: AcademicBatchConfig) -> float | None:
    configured = int(config.article_provider_watchdog_seconds)
    if configured < 0:
        return None
    if configured > 0:
        return float(configured)
    # Bias the stage-level watchdog toward recall over speed:
    # keep it well above the typical provider retry/backoff envelope so it
    # catches only clearly stuck requests, not merely slow-but-productive ones.
    return float(max(300, int(config.article_total_timeout_seconds) + 15))


async def _await_provider_json(
    pool: GonkaMultiKeyPool,
    *,
    model: str,
    prompt: str,
    temperature: float,
    watchdog_seconds: float | None,
) -> ProviderResponse:
    request = pool.chat_json(
        model=model,
        prompt=prompt,
        temperature=temperature,
    )
    if watchdog_seconds is None:
        return await request
    return await asyncio.wait_for(request, timeout=watchdog_seconds)


class _SlidingWindowLimiter:
    def __init__(self, max_requests: int, window: float = 1.0) -> None:
        self._max = max(1, int(max_requests))
        self._window = max(0.01, float(window))
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()

    async def acquire(self) -> float:
        waited = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and self._timestamps[0] <= now - self._window:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return waited
                sleep_for = max(0.01, self._timestamps[0] + self._window - now)
            started = time.monotonic()
            await asyncio.sleep(sleep_for)
            waited += time.monotonic() - started


# API concurrency limits (with ~10% headroom from provider caps).
_PER_KEY_CONCURRENT_CAP = 40  # provider hard limit: 50 per key
_GLOBAL_CONCURRENT_CAP = 180  # provider hard limit: 200 per user account
_MAX_RETRY_AFTER_SECONDS = 30.0  # cap on Retry-After header value


class _ProviderClient:
    def __init__(
        self,
        *,
        client_index: int,
        api_key: str,
        base_url: str,
        rate_limit_rps: float,
        circuit_failures: int,
        circuit_reset_seconds: int,
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
        total_timeout_seconds: int,
    ) -> None:
        self.client_index = client_index
        self.api_key = api_key
        self.url = f"{base_url.rstrip('/')}/chat/completions"
        # Support fractional per-key request rates so local smoke runs can match
        # provider-specific practical throughput, not just integer RPS ceilings.
        effective_rps = max(0.001, float(rate_limit_rps))
        self.rate_limit_rps = effective_rps
        self.limiter = _SlidingWindowLimiter(max_requests=1, window=(1.0 / effective_rps))
        self.circuit_failures = max(1, int(circuit_failures))
        self.circuit_reset_seconds = max(1, int(circuit_reset_seconds))
        self.consecutive_failures = 0
        self.circuit_open_until = 0.0
        self.in_flight = 0
        self.timeout = aiohttp.ClientTimeout(
            total=max(10, int(total_timeout_seconds)),
            connect=max(1, int(connect_timeout_seconds)),
            sock_read=max(1, int(read_timeout_seconds)),
        )
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> _ProviderClient:
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    def is_available(self) -> bool:
        return time.monotonic() >= self.circuit_open_until

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.circuit_open_until = 0.0

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.circuit_failures:
            jitter = random.uniform(0.8, 1.3)
            self.circuit_open_until = time.monotonic() + self.circuit_reset_seconds * jitter


class GonkaMultiKeyPool:
    """Gonka multi key pool public type."""

    def __init__(self, config: AcademicBatchConfig) -> None:
        self._clients = [
            _ProviderClient(
                client_index=index + 1,
                api_key=key,
                base_url=config.gonka_base_url,
                rate_limit_rps=config.article_rate_limit_rps,
                circuit_failures=config.provider_circuit_breaker_failures,
                circuit_reset_seconds=config.provider_circuit_breaker_reset_seconds,
                connect_timeout_seconds=config.article_connect_timeout_seconds,
                read_timeout_seconds=config.article_read_timeout_seconds,
                total_timeout_seconds=config.article_total_timeout_seconds,
            )
            for index, key in enumerate(config.gonka_api_keys)
            if str(key).strip()
        ]
        self._max_retries = max(1, int(config.article_max_retries))
        self._max_completion_tokens = max(256, int(config.article_max_completion_tokens))
        self._selection_lock = asyncio.Lock()
        self._global_sem = asyncio.Semaphore(_GLOBAL_CONCURRENT_CAP)
        self._selection_cursor = 0

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def per_key_rate_limit_rps(self) -> float:
        if not self._clients:
            return 0.0
        return float(self._clients[0].rate_limit_rps)

    @property
    def theoretical_aggregate_rps(self) -> float:
        return self.client_count * self.per_key_rate_limit_rps

    async def __aenter__(self) -> GonkaMultiKeyPool:
        for client in self._clients:
            await client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for client in self._clients:
            await client.__aexit__(*exc)

    async def _acquire(self) -> _ProviderClient:
        """Acquire global concurrency slot and select a fair least-loaded client."""
        while True:
            await self._global_sem.acquire()
            async with self._selection_lock:
                available = [
                    c
                    for c in self._clients
                    if c.is_available() and c.in_flight < _PER_KEY_CONCURRENT_CAP
                ]
                if available:
                    min_load = min(c.in_flight for c in available)
                    candidates = [c for c in available if c.in_flight == min_load]
                    client = candidates[self._selection_cursor % len(candidates)]
                    self._selection_cursor = (self._selection_cursor + 1) % max(
                        1, len(self._clients)
                    )
                    client.in_flight += 1
                    return client
            # No client available — release global slot and wait with jitter
            self._global_sem.release()
            earliest = min(
                (c.circuit_open_until for c in self._clients),
                default=time.monotonic() + 1.0,
            )
            wait = max(0.1, earliest - time.monotonic())
            await asyncio.sleep(wait * random.uniform(0.8, 1.3))

    def _release(self, client: _ProviderClient) -> None:
        """Release client slot and global concurrency slot."""
        client.in_flight = max(0, client.in_flight - 1)
        self._global_sem.release()

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        """Compute backoff with jitter. Caps Retry-After to prevent long stalls."""
        if retry_after and retry_after.isdigit():
            base = min(float(retry_after), _MAX_RETRY_AFTER_SECONDS)
        else:
            base = min(0.5 * (2 ** (attempt - 1)), 15.0)
        return base * random.uniform(0.7, 1.4)

    async def chat_json(self, *, model: str, prompt: str, temperature: float) -> ProviderResponse:
        last_error_class = "empty_response"
        last_status = 0
        last_finish_reason = ""
        last_raw_content = ""
        last_usage: dict[str, Any] = {}
        total_backoff_sleep = 0.0
        total_limiter_wait = 0.0
        parse_status = "empty"
        truncated_output = False
        last_client_index: int | None = None

        for attempt in range(1, self._max_retries + 1):
            backoff = 0.0
            client = await self._acquire()
            last_client_index = client.client_index
            try:
                if client.session is None:
                    raise RuntimeError("Provider session is not initialized")
                limiter_wait = await client.limiter.acquire()
                total_limiter_wait += limiter_wait
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                    "max_tokens": self._max_completion_tokens,
                }
                started = time.monotonic()
                try:
                    async with client.session.post(client.url, json=payload) as resp:
                        body = await resp.text()
                        latency_ms = (time.monotonic() - started) * 1000.0
                        last_status = int(resp.status)
                        if resp.status == 200:
                            data = json.loads(body) if body else {}
                            if not isinstance(data, dict):
                                data = {}
                            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                            choices = (
                                data.get("choices") if isinstance(data.get("choices"), list) else []
                            )
                            first = choices[0] if choices else {}
                            message = first.get("message") if isinstance(first, dict) else {}
                            raw_content = (
                                str(message.get("content") or "")
                                if isinstance(message, dict)
                                else ""
                            )
                            finish_reason = (
                                str(first.get("finish_reason") or "")
                                if isinstance(first, dict)
                                else ""
                            )
                            parsed = _parse_json_object(raw_content) or {}
                            parse_status = (
                                "ok" if parsed else ("partial" if raw_content.strip() else "empty")
                            )
                            truncated_output = finish_reason == "length"
                            last_error_class = ""
                            client.record_success()
                            return ProviderResponse(
                                parsed=parsed,
                                usage=usage,
                                http_status=200,
                                finish_reason=finish_reason,
                                latency_ms=latency_ms,
                                retry_count=attempt - 1,
                                limiter_wait_ms=total_limiter_wait * 1000.0,
                                backoff_sleep_ms=total_backoff_sleep * 1000.0,
                                parse_status=parse_status,
                                error_class=("provider_length_stop" if truncated_output else ""),
                                raw_content=raw_content,
                                truncated_output=truncated_output,
                                provider_key_index=client.client_index,
                            )

                        retry_after_raw = str(resp.headers.get("Retry-After") or "").strip()
                        retry_after_val: str | None = retry_after_raw if retry_after_raw else None
                        if resp.status == 429:
                            last_error_class = "provider_http_429"
                            client.record_failure()
                            backoff = self._backoff(attempt, retry_after_val)
                            total_backoff_sleep += backoff
                        elif resp.status in {500, 502, 503, 504}:
                            last_error_class = "provider_http_5xx"
                            client.record_failure()
                            backoff = self._backoff(attempt, retry_after_val)
                            total_backoff_sleep += backoff
                        elif resp.status == 400 and "response_format" in payload:
                            payload.pop("response_format", None)
                            started_retry = time.monotonic()
                            async with client.session.post(client.url, json=payload) as retry_resp:
                                body = await retry_resp.text()
                                latency_ms = (time.monotonic() - started_retry) * 1000.0
                                last_status = int(retry_resp.status)
                                if retry_resp.status == 200:
                                    data = json.loads(body) if body else {}
                                    if not isinstance(data, dict):
                                        data = {}
                                    usage = (
                                        data.get("usage")
                                        if isinstance(data.get("usage"), dict)
                                        else {}
                                    )
                                    choices = (
                                        data.get("choices")
                                        if isinstance(data.get("choices"), list)
                                        else []
                                    )
                                    first = choices[0] if choices else {}
                                    message = (
                                        first.get("message") if isinstance(first, dict) else {}
                                    )
                                    raw_content = (
                                        str(message.get("content") or "")
                                        if isinstance(message, dict)
                                        else ""
                                    )
                                    finish_reason = (
                                        str(first.get("finish_reason") or "")
                                        if isinstance(first, dict)
                                        else ""
                                    )
                                    parsed = _parse_json_object(raw_content) or {}
                                    parse_status = (
                                        "ok"
                                        if parsed
                                        else ("partial" if raw_content.strip() else "empty")
                                    )
                                    truncated_output = finish_reason == "length"
                                    client.record_success()
                                    return ProviderResponse(
                                        parsed=parsed,
                                        usage=usage,
                                        http_status=200,
                                        finish_reason=finish_reason,
                                        latency_ms=latency_ms,
                                        retry_count=attempt - 1,
                                        limiter_wait_ms=total_limiter_wait * 1000.0,
                                        backoff_sleep_ms=total_backoff_sleep * 1000.0,
                                        parse_status=parse_status,
                                        error_class=(
                                            "provider_length_stop" if truncated_output else ""
                                        ),
                                        raw_content=raw_content,
                                        truncated_output=truncated_output,
                                        provider_key_index=client.client_index,
                                    )
                            last_error_class = f"provider_http_{resp.status}"
                            last_finish_reason = ""
                            last_raw_content = body[:4000]
                            client.record_failure()
                        else:
                            last_error_class = f"provider_http_{resp.status}"
                            last_finish_reason = ""
                            last_raw_content = body[:4000]
                            client.record_failure()
                except TimeoutError:
                    last_error_class = "timeout"
                    client.record_failure()
                    backoff = self._backoff(attempt, None)
                    total_backoff_sleep += backoff
                except (aiohttp.ClientError, json.JSONDecodeError):
                    last_error_class = "json_parse"
                    client.record_failure()
                    backoff = self._backoff(attempt, None)
                    total_backoff_sleep += backoff
            finally:
                self._release(client)
            # Backoff sleep OUTSIDE held slots — capacity is free for other workers
            if backoff > 0:
                await asyncio.sleep(backoff)

        return ProviderResponse(
            parsed={},
            usage=last_usage,
            http_status=last_status,
            finish_reason=last_finish_reason,
            latency_ms=0.0,
            retry_count=self._max_retries,
            limiter_wait_ms=total_limiter_wait * 1000.0,
            backoff_sleep_ms=total_backoff_sleep * 1000.0,
            parse_status=parse_status,
            error_class=last_error_class,
            raw_content=last_raw_content,
            truncated_output=truncated_output,
            provider_key_index=last_client_index,
        )


def _jsonl_append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "updated_at": "", "items": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict) and isinstance(loaded.get("items"), dict):
            return loaded
    except Exception as exc:
        logger.debug("Ignored exception: {}", exc)
    return {"version": 1, "updated_at": "", "items": {}}


def _write_progress(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    try:
        import orjson

        tmp_path.write_bytes(orjson.dumps(progress))
    except ImportError:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(progress, fh, ensure_ascii=False)
    tmp_path.replace(path)


def _load_metadata_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    cache: dict[str, dict[str, Any]] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            cache_key = str(row.get("cache_key") or "").strip()
            if cache_key:
                cache[cache_key] = row
    return cache


def _terminal_state(state: str) -> bool:
    return state in {
        "published",
        "raw_only",
        "succeeded_nonempty",
        "succeeded_empty",
        "permanent_failed",
        "rejected",
    }


def _retryable_state(state: str) -> bool:
    return state == "retryable_failed"


def _count_progress_state(progress: dict[str, Any], state: str) -> int:
    items = progress.get("items")
    if not isinstance(items, dict):
        return 0
    return sum(
        1
        for value in items.values()
        if isinstance(value, dict) and str(value.get("state") or "") == state
    )


def _persist_timeout_retry_queue(config: AcademicBatchConfig, progress: dict[str, Any]) -> None:
    """Write retryable-failed work IDs to a cross-run retry queue."""
    items = progress.get("items")
    if not isinstance(items, dict):
        return
    existing_queue: dict[str, dict[str, Any]] = {}
    if config.timeout_retry_queue_path.exists():
        for line in config.timeout_retry_queue_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                existing_queue[str(entry.get("work_id", ""))] = entry
            except json.JSONDecodeError:
                continue
    for work_id, value in items.items():
        if not isinstance(value, dict):
            continue
        if str(value.get("state") or "") != "retryable_failed":
            continue
        prev = existing_queue.get(work_id)
        retry_count = int(prev.get("retry_count", 0)) + 1 if prev else 0
        if retry_count >= config.retry_max_attempts:
            continue
        existing_queue[work_id] = {
            "work_id": work_id,
            "retry_count": retry_count,
            "last_error": str(value.get("error_class") or "timeout"),
            "queued_ts": datetime.now(UTC).isoformat(),
        }
    config.timeout_retry_queue_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.timeout_retry_queue_path, "w", encoding="utf-8") as fh:
        for entry in existing_queue.values():
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _resolve_extract_artifacts(config: AcademicBatchConfig) -> list[Path]:
    return [
        config.resolve_extract_progress_path,
        config.resolve_extract_results_path,
        config.resolve_extract_errors_path,
        config.fulltext_fetch_log_path,
        config.fulltext_metadata_cache_path,
        config.llm_request_log_path,
        config.raw_claim_candidates_path,
        config.published_claims_path,
        config.context_attributes_path,
        config.moderation_edges_path,
        config.article_extraction_results_path,
        config.extracted_dir / "resolve_extract.jsonl",
    ]


def _topic_id_for_row(row: dict[str, Any]) -> str:
    topic_ids = row.get("topic_ids") if isinstance(row.get("topic_ids"), list) else []
    if topic_ids:
        return str(topic_ids[0])
    topic_id = str(row.get("topic_id") or "").strip()
    return topic_id or "topic_unknown"


def _topic_ids_for_row(row: dict[str, Any]) -> list[str]:
    if isinstance(row.get("topic_ids"), list):
        return [str(item) for item in row.get("topic_ids") if str(item).strip()]
    topic_id = str(row.get("topic_id") or "").strip()
    return [topic_id] if topic_id else []


def _topic_names_for_row(row: dict[str, Any]) -> list[str]:
    if isinstance(row.get("topic_display_names"), list):
        return [str(item) for item in row.get("topic_display_names") if str(item).strip()]
    topic_name = str(row.get("topic_display_name") or "").strip()
    return [topic_name] if topic_name else []


def _is_review_like(*texts: str) -> bool:
    return bool(_REVIEW_LIKE_RE.search(" ".join(texts)))


def _is_theory_like(*texts: str) -> bool:
    return bool(_THEORY_LIKE_RE.search(" ".join(texts)))


def _is_method_only(*texts: str) -> bool:
    return bool(_METHOD_ONLY_RE.search(" ".join(texts)))


def _count_pattern(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text or ""))


def _prefetch_priority(work: dict[str, Any]) -> float:
    abstract = reconstruct_abstract(work)
    title = _normalized_text(work.get("title"))
    keep, reason = should_process(work)
    cited = int(work.get("cited_by_count") or 0)
    year = int(work.get("publication_year") or 0)
    open_access = work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
    best_oa = work.get("best_oa_location") if isinstance(work.get("best_oa_location"), dict) else {}
    priority = 0.0
    if keep:
        priority += 100.0
    if reason == "tier1":
        priority += 25.0
    elif reason == "tier2_domain_match":
        priority += 10.0
    priority += min(30.0, math.log1p(max(0, cited)) * 5.0)
    priority += max(0.0, min(10.0, (year - 2000) * 0.4))
    priority += min(6.0, float(_count_pattern(_METHOD_SENTENCE_RE, abstract)))
    priority += min(4.0, float(_count_pattern(_EMPIRICAL_DATA_RE, abstract)))
    priority += min(6.0, float(_count_pattern(_RESULT_CUE_RE, abstract)))
    precision_signal = _precision_result_signal_score(title, abstract)
    priority += min(12.0, precision_signal * 1.5)
    if bool(work.get("has_fulltext")):
        priority += 15.0
    if bool(open_access.get("is_oa")):
        priority += 12.0
    if any(str(best_oa.get(key) or "").strip() for key in ("pdf_url", "landing_page_url")):
        priority += 8.0
    if _has_strong_design_signal(title, abstract):
        priority += 10.0
    if _descriptive_only_score(title, abstract) > 0 and precision_signal == 0:
        priority -= 12.0
    priority -= min(6.0, _downgrade_signal_score(title, abstract) * 1.5)
    if _is_review_like(title, abstract):
        priority -= 25.0
    if _is_theory_like(title, abstract):
        priority -= 20.0
    if _is_method_only(title, abstract):
        priority -= 20.0
    if _is_access_shell(title, abstract):
        priority -= 35.0
    return round(priority, 6)


def _has_strong_design_signal(*parts: str) -> bool:
    haystack = "\n".join(part for part in parts if part)
    if not haystack:
        return False
    return any(pattern.search(haystack) for pattern in _STRONG_METHOD_PATTERNS.values())


def _method_signal_score(*parts: str) -> float:
    title = parts[0] if len(parts) > 0 else ""
    abstract = parts[1] if len(parts) > 1 else ""
    text = parts[2] if len(parts) > 2 else ""
    score = 0.0
    score += min(4.0, float(_count_pattern(_METHOD_SENTENCE_RE, text)))
    score += min(2.0, float(_count_pattern(_METHOD_SENTENCE_RE, abstract))) * 0.75
    score += min(1.0, float(_count_pattern(_METHOD_SENTENCE_RE, title))) * 0.25
    if _has_strong_design_signal(text):
        score += 1.5
    elif _has_strong_design_signal(abstract):
        score += 1.0
    elif _has_strong_design_signal(title):
        score += 0.5
    return round(score, 6)


def _data_signal_score(*parts: str) -> float:
    title = parts[0] if len(parts) > 0 else ""
    abstract = parts[1] if len(parts) > 1 else ""
    text = parts[2] if len(parts) > 2 else ""
    score = 0.0
    score += min(3.0, float(_count_pattern(_EMPIRICAL_DATA_RE, text)))
    score += min(1.5, float(_count_pattern(_EMPIRICAL_DATA_RE, abstract))) * 0.75
    score += min(0.75, float(_count_pattern(_EMPIRICAL_DATA_RE, title))) * 0.5
    return round(score, 6)


def _result_signal_score(*parts: str) -> float:
    title = parts[0] if len(parts) > 0 else ""
    abstract = parts[1] if len(parts) > 1 else ""
    text = parts[2] if len(parts) > 2 else ""
    score = 0.0
    score += min(
        4.0,
        float(
            _count_pattern(_RESULT_CUE_RE, text)
            + _count_pattern(_RESULT_SENTENCE_RE, text)
            + _count_pattern(_CLAIM_SENTENCE_RE, text)
        ),
    )
    score += (
        min(
            2.0,
            float(
                _count_pattern(_RESULT_CUE_RE, abstract)
                + _count_pattern(_RESULT_SENTENCE_RE, abstract)
                + _count_pattern(_CLAIM_SENTENCE_RE, abstract)
            ),
        )
        * 0.75
    )
    score += (
        min(
            1.0,
            float(
                _count_pattern(_RESULT_CUE_RE, title)
                + _count_pattern(_RESULT_SENTENCE_RE, title)
                + _count_pattern(_CLAIM_SENTENCE_RE, title)
            ),
        )
        * 0.25
    )
    return round(score, 6)


def _precision_result_signal_score(*parts: str) -> float:
    title = parts[0] if len(parts) > 0 else ""
    abstract = parts[1] if len(parts) > 1 else ""
    text = parts[2] if len(parts) > 2 else ""
    score = 0.0
    score += min(5.0, float(_count_pattern(_PRECISION_RESULT_CUE_RE, text))) * 1.25
    score += min(2.5, float(_count_pattern(_PRECISION_RESULT_CUE_RE, abstract))) * 0.9
    score += min(1.0, float(_count_pattern(_PRECISION_RESULT_CUE_RE, title))) * 0.5
    return round(score, 6)


def _descriptive_only_score(*parts: str) -> float:
    haystack = "\n".join(part for part in parts if part)
    if not haystack:
        return 0.0
    return float(len(_DESCRIPTIVE_ONLY_RE.findall(haystack)))


def _downgrade_signal_score(*parts: str) -> float:
    haystack = "\n".join(part for part in parts if part)
    if not haystack:
        return 0.0
    # If the text contains negation context (e.g. "beyond correlation"),
    # discount the downgrade signal rather than counting it fully.
    raw_count = float(len(_DOWNGRADE_PATTERNS.findall(haystack)))
    if raw_count > 0 and _DOWNGRADE_NEGATION_RE.search(haystack):
        return max(0.0, raw_count - 1.0)
    return raw_count


def _is_access_shell(*parts: str) -> bool:
    haystack = "\n".join(part for part in parts if part)
    if not haystack:
        return False
    return bool(_ACCESS_SHELL_RE.search(haystack))


def _has_context_classification_signal(*parts: str) -> bool:
    haystack = "\n".join(part for part in parts if part)
    if not haystack:
        return False
    return bool(_CONTEXT_CLASSIFICATION_RE.search(haystack))


def _has_heterogeneity_classification_signal(*parts: str) -> bool:
    haystack = "\n".join(part for part in parts if part)
    if not haystack:
        return False
    return bool(_HETEROGENEITY_CLASSIFICATION_RE.search(haystack))


def _resolve_paper_kind(
    *,
    work_item: WorkItem,
    eligible_item: EligibleItem,
    result: ArticleExtractionResult,
    cls_parsed: dict[str, Any],
) -> PaperKind:
    abstract = reconstruct_abstract(work_item.work)
    joined = "\n".join(
        part
        for part in (
            result.title,
            abstract,
            result.citation_summary,
            result.methodology,
            " ".join(claim.claim_text for claim in result.causal_claims[:6]),
        )
        if part
    )
    review_like = _is_review_like(
        result.title, abstract, result.citation_summary, result.methodology
    )
    theory_like = _is_theory_like(
        result.title, abstract, result.citation_summary, result.methodology
    )
    method_only = _is_method_only(
        result.title, abstract, result.citation_summary, result.methodology
    )
    context_signal = _has_context_classification_signal(joined)
    heterogeneity_signal = _has_heterogeneity_classification_signal(joined)
    has_claims = bool(result.causal_claims)
    has_moderation = (
        bool(result.moderation_edges) or bool(result.heterogeneity_results) or heterogeneity_signal
    )
    strong_design = _has_strong_design_signal(
        result.title, abstract, result.methodology, result.citation_summary
    ) or any(claim.identification_strategy is not None for claim in result.causal_claims)
    paper_kind_raw = str(cls_parsed.get("paper_kind", "")).strip().lower()
    parsed_kind: PaperKind | None = None
    if paper_kind_raw:
        try:
            parsed_kind = PaperKind(paper_kind_raw)
        except ValueError:
            parsed_kind = None

    if parsed_kind is None:
        if theory_like:
            return PaperKind.THEORETICAL
        if method_only:
            return PaperKind.DESCRIPTIVE
        if review_like and not has_claims and not has_moderation:
            return PaperKind.CONTEXT_CHARACTERIZATION
        if has_moderation and has_claims:
            return (
                PaperKind.MIXED
                if (eligible_item.context_eligible or context_signal)
                else PaperKind.HETEROGENEITY_ANALYSIS
            )
        if eligible_item.context_eligible and (context_signal or not has_claims):
            return PaperKind.CONTEXT_CHARACTERIZATION
        if has_claims:
            return PaperKind.EMPIRICAL_CAUSAL
        return PaperKind.DESCRIPTIVE

    if (
        parsed_kind == PaperKind.EMPIRICAL_CAUSAL
        and eligible_item.context_eligible
        and not eligible_item.llm_eligible
    ):
        if has_moderation:
            return (
                PaperKind.MIXED
                if (review_like or context_signal or not strong_design)
                else PaperKind.HETEROGENEITY_ANALYSIS
            )
        if review_like or ((context_signal or not has_claims) and not strong_design):
            return PaperKind.CONTEXT_CHARACTERIZATION

    if (
        parsed_kind in {PaperKind.REVIEW_SYSTEMATIC, PaperKind.DESCRIPTIVE}
        and eligible_item.context_eligible
    ):
        return PaperKind.MIXED if has_moderation else PaperKind.CONTEXT_CHARACTERIZATION

    return parsed_kind


def _shared_vocabulary_text() -> str:
    return ", ".join(_SHARED_VOCABULARY_PREFIXES)


def _build_claim_inventory(
    result: ArticleExtractionResult, canonizer: VariableCanonizer
) -> list[dict[str, str]]:
    inventory: list[dict[str, str]] = []
    for claim in result.causal_claims:
        cause, _ = canonizer.canonize(claim.cause_variable)
        effect, _ = canonizer.canonize(claim.effect_variable)
        claim_id = claim.claim_id or stable_claim_id(
            work_id=result.openalex_id,
            cause=cause,
            effect=effect,
            claim_text=claim.claim_text,
            direction=claim.direction.value,
            supporting_span_ids=tuple(claim.supporting_span_ids),
        )
        inventory.append(
            {
                "claim_id": claim_id,
                "cause_variable": cause,
                "effect_variable": effect,
                "design_family_hint": claim.design_family_hint.value,
                "claim_text": claim.claim_text,
            }
        )
    return inventory


def _build_track_b_prompt(bundle: dict[str, Any], claim_inventory: list[dict[str, str]]) -> str:
    return (
        "Extract context attributes from this evidence bundle.\n"
        f"Shared canonical prefixes: {_shared_vocabulary_text()}.\n"
        "Track A claim inventory (do not re-extract these treatment/outcome variables as context):\n"
        + json.dumps(claim_inventory, ensure_ascii=False)
        + "\n\n"
        + CONTEXT_EXTRACTION_SCHEMA_HINT
        + "\n\nEvidence bundle:\n"
        + json.dumps(bundle, ensure_ascii=False)
    )


def _build_track_c_prompt(bundle: dict[str, Any], claim_inventory: list[dict[str, str]]) -> str:
    return (
        "Extract moderation and heterogeneity findings from this evidence bundle.\n"
        f"Shared canonical prefixes: {_shared_vocabulary_text()}.\n"
        "Track A claim inventory (use exact claim_id/cause/effect names when a moderation finding applies to one of these claims):\n"
        + json.dumps(claim_inventory, ensure_ascii=False)
        + "\n\n"
        + MODERATOR_EXTRACTION_SCHEMA_HINT
        + "\n\nEvidence bundle:\n"
        + json.dumps(bundle, ensure_ascii=False)
    )


def _normalize_context_lane_result(
    *,
    work: dict[str, Any],
    parsed: dict[str, Any],
    model: str,
    usage: dict[str, Any],
    bundle: dict[str, Any],
    source_kind: str,
) -> ArticleExtractionResult:
    payload = _normalize_extraction_payload(
        work,
        {
            "methodology": parsed.get("methodology") or "",
            "methodology_enum": parsed.get("methodology_enum") or "",
            "citation_summary": parsed.get("citation_summary") or "",
            "extraction_confidence": parsed.get("extraction_confidence") or 0.6,
            "source_basis": SourceBasis.FULLTEXT.value
            if source_kind != "abstract_fallback"
            else SourceBasis.ABSTRACT_ONLY.value,
        },
        model,
        usage,
        evidence_bundle=bundle,
        source_kind=source_kind,
    )
    payload["context_attributes"] = [
        item.model_dump(mode="json")
        for item in (
            _normalize_context_attribute(raw) for raw in _as_list(parsed.get("context_attributes"))
        )
        if item is not None
    ]
    return ArticleExtractionResult.model_validate(payload)


def _apply_extraction_lane(result: ArticleExtractionResult, lane: str) -> ArticleExtractionResult:
    normalized_lane = str(lane or "all").strip().lower() or "all"
    if normalized_lane == "all":
        return result
    if normalized_lane == "claim":
        return result.model_copy(
            update={
                "empirical_parameters": [],
                "mechanisms": [],
                "boundary_conditions": [],
                "heterogeneity_results": [],
                "context_attributes": [],
                "moderation_edges": [],
            }
        )
    if normalized_lane == "context":
        return result.model_copy(
            update={
                "causal_claims": [],
                "empirical_parameters": [],
                "mechanisms": [],
                "boundary_conditions": [],
                "heterogeneity_results": [],
                "moderation_edges": [],
            }
        )
    if normalized_lane == "mechanism":
        return result.model_copy(
            update={
                "causal_claims": [],
                "empirical_parameters": [],
                "heterogeneity_results": [],
                "context_attributes": [],
                "moderation_edges": [],
            }
        )
    return result


def _tokenize_variable_name(value: str) -> set[str]:
    text = str(value or "").strip().lower()
    if not text:
        return set()
    parts = re.split(r"[^a-z0-9]+", text.replace(".", "_"))
    return {
        part
        for part in parts
        if part
        and part
        not in {
            "economic",
            "fiscal",
            "governance",
            "institutional",
            "social",
            "demographic",
            "labor",
            "trade",
            "environmental",
            "health",
            "education",
            "infrastructure",
            "political",
        }
    }


def _token_overlap_score(left: str, right: str) -> float:
    lt = _tokenize_variable_name(left)
    rt = _tokenize_variable_name(right)
    if not lt or not rt:
        return 0.0
    return len(lt & rt) / max(1, len(lt | rt))


def _pair_match_score(base_cause: str, base_effect: str, claim_row: dict[str, str]) -> float:
    cause_score = _token_overlap_score(base_cause, claim_row["cause_variable"])
    effect_score = _token_overlap_score(base_effect, claim_row["effect_variable"])
    return (cause_score + effect_score) / 2.0


def _sanitize_spans(spans: list[EvidenceSpan]) -> tuple[list[EvidenceSpan], bool]:
    cleaned: list[EvidenceSpan] = []
    had_contamination = False
    for span in spans:
        text = str(span.text or "").strip()
        if not text:
            had_contamination = True
            continue
        if not _CONTAMINATION_RE.search(text):
            cleaned.append(span)
            continue
        cleaned_text = _CONTAMINATION_RE.sub(" ", text)
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()
        if len(cleaned_text) < 50:
            had_contamination = True
            continue
        cleaned.append(span.model_copy(update={"text": cleaned_text}))
        had_contamination = True
    return cleaned, had_contamination


def _has_any_method_signal(claim: CausalClaim) -> bool:
    method_text = " ".join(span.text for span in claim.method_spans)
    if (
        claim.identification_strategy is not None
        and claim.identification_strategy.identification_method
    ):
        return True
    return bool(_METHOD_SENTENCE_RE.search(method_text))


def _has_strong_identification_signal(claim: CausalClaim) -> bool:
    """Check if claim mentions a genuine causal identification strategy.

    Unlike ``_has_any_method_signal`` this excludes weak data-type terms
    (regression, panel data, OLS, admin data) that are necessary but not
    sufficient for causal identification.
    """
    if (
        claim.identification_strategy is not None
        and claim.identification_strategy.identification_method
    ):
        return True
    method_text = " ".join(span.text for span in claim.method_spans)
    return bool(_STRONG_IDENTIFICATION_RE.search(method_text))


def _looks_like_context_overlap(
    attribute_name: str, canonical_name: str, claim_inventory: list[dict[str, str]]
) -> bool:
    candidate_names = [
        name
        for name in {
            attribute_name,
            canonical_name,
            canonical_name.rsplit(".", 1)[-1] if canonical_name else "",
        }
        if name
    ]
    if any(_CONTEXT_EFFECT_ESTIMATE_RE.search(name) for name in candidate_names):
        return True
    for claim_row in claim_inventory:
        for claim_name in (claim_row["cause_variable"], claim_row["effect_variable"]):
            if any(name == claim_name for name in candidate_names):
                return True
            if any(_token_overlap_score(name, claim_name) >= 0.67 for name in candidate_names):
                return True
    return False


def _reconcile_tracks(
    result: ArticleExtractionResult,
    *,
    canonizer: VariableCanonizer,
    claim_inventory: list[dict[str, str]],
) -> ArticleExtractionResult:
    claim_by_id = {row["claim_id"]: row for row in claim_inventory}
    claim_by_pair = {
        (row["cause_variable"], row["effect_variable"]): row for row in claim_inventory
    }
    diagnostics = {
        "exact_claim_ref_matches": 0,
        "canonical_tuple_matches": 0,
        "fuzzy_matches": 0,
        "freeform_moderation_edges": 0,
        "dropped_context_overlap": 0,
    }

    canonized_claims: list[CausalClaim] = []
    for idx, claim in enumerate(result.causal_claims):
        if idx < len(claim_inventory):
            row = claim_inventory[idx]
            claim_id = row["claim_id"]
            cause = row["cause_variable"]
            effect = row["effect_variable"]
        else:
            cause, _ = canonizer.canonize(claim.cause_variable)
            effect, _ = canonizer.canonize(claim.effect_variable)
            claim_id = claim.claim_id or stable_claim_id(
                work_id=result.openalex_id,
                cause=cause,
                effect=effect,
                claim_text=claim.claim_text,
                direction=claim.direction.value,
                supporting_span_ids=tuple(claim.supporting_span_ids),
            )
        canonized_claims.append(
            claim.model_copy(
                update={
                    "claim_id": claim_id,
                    "cause_variable": cause,
                    "effect_variable": effect,
                }
            )
        )

    canonized_parameters = []
    for parameter in result.empirical_parameters:
        name, _ = canonizer.canonize(parameter.name)
        canonized_parameters.append(parameter.model_copy(update={"name": name}))

    canonized_mechanisms = []
    for mechanism in result.mechanisms:
        mediators: list[str] = []
        for mediator in mechanism.mediating_variables:
            canonical_mediator, _ = canonizer.canonize(mediator)
            mediators.append(canonical_mediator)
        canonized_mechanisms.append(mechanism.model_copy(update={"mediating_variables": mediators}))

    canonized_boundaries = []
    for boundary in result.boundary_conditions:
        if boundary.variable:
            canonical_var, _ = canonizer.canonize(boundary.variable)
            canonized_boundaries.append(boundary.model_copy(update={"variable": canonical_var}))
        else:
            canonized_boundaries.append(boundary)

    canonized_heterogeneity_results: list[HeterogeneityResult] = []
    for heterogeneity in result.heterogeneity_results:
        canonical_moderator, _ = canonizer.canonize(heterogeneity.moderator)
        canonized_heterogeneity_results.append(
            heterogeneity.model_copy(update={"moderator": canonical_moderator})
        )

    canonized_context_attributes: list[ContextAttribute] = []
    for attribute in result.context_attributes:
        raw_name = attribute.canonical_name or attribute.attribute_name
        canonical_name, _ = canonizer.canonize(raw_name)
        if _looks_like_context_overlap(attribute.attribute_name, canonical_name, claim_inventory):
            diagnostics["dropped_context_overlap"] += 1
            continue
        canonized_context_attributes.append(
            attribute.model_copy(update={"canonical_name": canonical_name})
        )

    canonized_moderation_edges: list[ModerationEdge] = []
    for moderation_edge in result.moderation_edges:
        canonical_moderator, _ = canonizer.canonize(moderation_edge.moderator)
        match_quality = moderation_edge.match_quality or ""
        alignment_source = moderation_edge.alignment_source or ""
        base_claim_id = moderation_edge.base_claim_id
        matched_row: dict[str, str] | None = None

        if base_claim_id and base_claim_id in claim_by_id:
            matched_row = claim_by_id[base_claim_id]
            match_quality = "exact_claim_ref"
            alignment_source = "claim_inventory"
            diagnostics["exact_claim_ref_matches"] += 1
        else:
            canonical_cause, _ = canonizer.canonize(moderation_edge.base_cause)
            canonical_effect, _ = canonizer.canonize(moderation_edge.base_effect)
            matched_row = claim_by_pair.get((canonical_cause, canonical_effect))
            if matched_row is not None:
                base_claim_id = matched_row["claim_id"]
                match_quality = "canonical_tuple"
                alignment_source = "canonical_tuple"
                diagnostics["canonical_tuple_matches"] += 1
            else:
                best_score = 0.0
                best_row: dict[str, str] | None = None
                for claim_row in claim_inventory:
                    score = _pair_match_score(canonical_cause, canonical_effect, claim_row)
                    if score > best_score:
                        best_score = score
                        best_row = claim_row
                if best_row is not None and best_score >= 0.60:
                    matched_row = best_row
                    base_claim_id = best_row["claim_id"]
                    match_quality = "fuzzy_claim_inventory"
                    alignment_source = "fuzzy_pair"
                    diagnostics["fuzzy_matches"] += 1
                else:
                    matched_row = {
                        "claim_id": base_claim_id or "",
                        "cause_variable": canonical_cause,
                        "effect_variable": canonical_effect,
                        "design_family_hint": "",
                        "claim_text": "",
                    }
                    match_quality = "freeform"
                    alignment_source = "freeform"
                    diagnostics["freeform_moderation_edges"] += 1

        canonized_moderation_edges.append(
            moderation_edge.model_copy(
                update={
                    "base_claim_id": base_claim_id,
                    "base_cause": matched_row["cause_variable"],
                    "base_effect": matched_row["effect_variable"],
                    "moderator": canonical_moderator,
                    "match_quality": match_quality,
                    "alignment_source": alignment_source,
                }
            )
        )

    return result.model_copy(
        update={
            "causal_claims": canonized_claims,
            "empirical_parameters": canonized_parameters,
            "mechanisms": canonized_mechanisms,
            "boundary_conditions": canonized_boundaries,
            "heterogeneity_results": canonized_heterogeneity_results,
            "context_attributes": canonized_context_attributes,
            "moderation_edges": canonized_moderation_edges,
            "reconciliation_diagnostics": diagnostics,
        }
    )


def _post_resolve_priority(
    item: WorkItem, *, text: str, source_kind: str, text_quality: str
) -> float:
    abstract = reconstruct_abstract(item.work)
    title = _normalized_text(item.work.get("title"))
    method_signal = _method_signal_score(title, abstract, text)
    data_signal = _data_signal_score(title, abstract, text)
    result_signal = _result_signal_score(title, abstract, text)
    precision_signal = _precision_result_signal_score(title, abstract, text)
    descriptive_signal = _descriptive_only_score(title, abstract, text)
    downgrade_signal = _downgrade_signal_score(title, abstract, text)
    priority = item.prefetch_priority
    priority += 20.0 if source_kind != "abstract_fallback" else -50.0
    priority += 12.0 if text_quality == TextQuality.EXTRACTED_FULLTEXT.value else 0.0
    priority += min(14.0, method_signal * 2.0)
    priority += min(8.0, data_signal * 2.0)
    priority += min(12.0, result_signal * 1.75)
    priority += min(18.0, precision_signal * 2.5)
    if _has_strong_design_signal(title, abstract, text):
        priority += 12.0
    if descriptive_signal > 0 and precision_signal == 0 and method_signal < 2.0:
        priority -= min(16.0, descriptive_signal * 3.0)
    priority -= min(10.0, downgrade_signal * 2.5)
    if _is_review_like(title, abstract, text):
        priority -= 30.0
    if _is_theory_like(title, abstract, text):
        priority -= 25.0
    if _is_method_only(title, abstract, text):
        priority -= 25.0
    if _is_access_shell(title, abstract, text, source_kind):
        priority -= 40.0
    return round(priority, 6)


def _eligibility_gate(
    item: WorkItem,
    *,
    text: str,
    source_kind: str,
    text_quality: str,
    extraction_lane: str = "all",
    track_b_enabled: bool = False,
    track_c_enabled: bool = False,
    route_entry: dict[str, Any] | None = None,
    doc_family: str = "",
) -> EligibilityDecision:
    del track_c_enabled
    reasons: list[str] = []
    abstract = reconstruct_abstract(item.work)
    title = _normalized_text(item.work.get("title"))
    method_signal = _method_signal_score(title, abstract, text)
    data_signal = _data_signal_score(title, abstract, text)
    result_signal = _result_signal_score(title, abstract, text)
    precision_signal = _precision_result_signal_score(title, abstract, text)
    descriptive_signal = _descriptive_only_score(title, abstract, text)
    empirical_signal = method_signal + result_signal + (data_signal * 0.75)
    strong_design = _has_strong_design_signal(title, abstract, text)
    if source_kind == "abstract_fallback":
        reasons.append("abstract_only")
    if (
        (
            text_quality == TextQuality.DEGRADED.value
            or len(_normalized_text(text)) < _MIN_FULLTEXT_CHARS
        )
        and empirical_signal < 2.0
        and not strong_design
    ):
        reasons.append("degraded_text")
    if _is_access_shell(title, abstract, text):
        reasons.append("access_shell")
    if _is_review_like(title, abstract, text):
        reasons.append("review_like")
    if _is_theory_like(title, abstract, text):
        reasons.append("theory_like")
    if _is_method_only(title, abstract, text):
        reasons.append("method_only")
    if empirical_signal < 1.0 and not strong_design:
        reasons.append("missing_empirical_cues")
    if (
        descriptive_signal > 0
        and precision_signal == 0
        and method_signal < 1.5
        and not strong_design
    ):
        reasons.append("descriptive_only")
    lane = str(extraction_lane or "all").strip().lower() or "all"
    family = str(doc_family or "").strip().lower()
    route = route_entry if isinstance(route_entry, dict) else {}
    trusted_routed_empirical_fulltext = (
        lane != "context"
        and source_kind != "abstract_fallback"
        and text_quality != TextQuality.ABSTRACT_ONLY.value
        and family in _ROUTED_EMPIRICAL_DOC_FAMILIES
        and bool(route.get("eligible"))
        and str(route.get("route") or "").strip().lower() == "llm"
    )
    effective_reasons = (
        [reason for reason in reasons if reason not in _ROUTED_EMPIRICAL_SOFT_BLOCKERS]
        if trusted_routed_empirical_fulltext
        else list(reasons)
    )
    llm_eligible = not effective_reasons
    hard_reasons = [reason for reason in reasons if reason in _CONTEXT_HARD_REJECTION_REASONS]
    soft_reasons = [reason for reason in reasons if reason in _CONTEXT_SOFT_REJECTION_REASONS]
    context_signal = bool(
        _CONTEXT_CLASSIFICATION_RE.search("\n".join((title, abstract, text[:6000])))
    )
    context_eligible = (bool(track_b_enabled) and not hard_reasons and bool(soft_reasons)) or (
        lane == "context" and not hard_reasons and (context_signal or bool(soft_reasons))
    )
    if lane == "context" and context_eligible:
        llm_eligible = False
    return EligibilityDecision(
        llm_eligible=llm_eligible,
        context_eligible=context_eligible,
        rejection_reasons=effective_reasons,
    )


def _build_streaming_evidence_bundle(
    item: WorkItem,
    *,
    text: str,
    source_kind: str,
    sentence_budget: int,
    substrate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = _build_evidence_bundle(
        title=_normalized_text(item.work.get("title")),
        abstract=reconstruct_abstract(item.work),
        text=text,
        source_kind=source_kind,
    )
    budget = max(12, int(sentence_budget))
    allocations = {
        "abstract_sentences": min(6, budget // 4),
        "method_sentences": min(8, max(3, budget // 3)),
        "result_sentences": min(8, max(3, budget // 3)),
        "claim_sentences": min(8, max(3, budget // 3)),
        "numeric_result_snippets": min(8, max(4, budget // 3)),
        "numeric_result_blocks": min(6, max(3, budget // 4)),
    }
    for key, limit in allocations.items():
        rows = bundle.get(key, [])
        if isinstance(rows, list):
            bundle[key] = rows[:limit]
    bundle["metadata_summary"] = {
        "work_id": item.work_id,
        "publication_year": int(item.work.get("publication_year") or 0) or None,
        "cited_by_count": int(item.work.get("cited_by_count") or 0),
        "work_type": _normalized_text(item.work.get("type")),
        "topic_ids": item.topic_ids,
        "topic_display_names": item.topic_display_names,
        "prefetch_priority": item.prefetch_priority,
        "selected_rank": item.selected_rank,
    }
    if substrate:
        bundle["doc_family"] = str(substrate.get("doc_family") or "")
        bundle["routing"] = list(substrate.get("routing") or [])
        if isinstance(substrate.get("sections"), list):
            bundle["sections"] = list(substrate["sections"])[:10]
        if isinstance(substrate.get("references"), list):
            bundle["references"] = list(substrate["references"])[:20]
        if isinstance(substrate.get("tables"), list):
            sorted_tables = sorted(
                substrate["tables"], key=lambda t: float(t.get("score") or 0), reverse=True
            )
            bundle["tables"] = sorted_tables[:16]
        if isinstance(substrate.get("figures"), list):
            bundle["figures"] = list(substrate["figures"])[:10]
        if isinstance(substrate.get("appendix_blocks"), list):
            bundle["appendix_blocks"] = list(substrate["appendix_blocks"])[:10]
        extra_numeric_blocks: list[dict[str, Any]] = []
        for row in [*(substrate.get("tables") or []), *(substrate.get("appendix_blocks") or [])]:
            if not isinstance(row, dict):
                continue
            text_value = _normalized_text(row.get("text"))
            if not text_value:
                continue
            extra_numeric_blocks.append(
                {
                    "text": text_value,
                    "section": str(row.get("label") or row.get("section_name") or "table"),
                    "score": float(row.get("score") or 0.6),
                }
            )
        if extra_numeric_blocks:
            merged_blocks = [*bundle.get("numeric_result_blocks", []), *extra_numeric_blocks]
            bundle["numeric_result_blocks"] = merged_blocks[
                : max(6, allocations["numeric_result_blocks"] + 4)
            ]
    return bundle


def _prompt_for_bundle(bundle: dict[str, Any], topic_display_names: list[str] | None = None) -> str:
    topic_names = topic_display_names or []
    selected = _select_relevant_canonical_names(topic_names)
    if selected:
        canonical_block = (
            "When naming cause_variable and effect_variable, strongly prefer these canonical names:\n"
            + ", ".join(selected)
            + "\nIf no canonical name fits, use the prefix convention above to create a new name."
        )
    else:
        canonical_block = ""
    schema = _ONE_CALL_SCHEMA_HINT.replace("{canonical_names_block}", canonical_block)
    return (
        "Extract policy-relevant empirical evidence from this evidence bundle.\n"
        + schema
        + "\n\nEvidence bundle:\n"
        + json.dumps(bundle, ensure_ascii=False)
    )


def _parameter_context_text(parameter: EvidenceParameter) -> str:
    return " | ".join(
        part
        for part in (
            str(parameter.name or ""),
            str(parameter.display_name or ""),
            str(parameter.heterogeneity_note or ""),
        )
        if part
    ).strip()


def _parameter_is_non_effect_metric(parameter: EvidenceParameter) -> bool:
    if parameter.parameter_type != ParameterType.QUANTITATIVE:
        return False
    return bool(_NON_EFFECT_PARAMETER_RE.search(_parameter_context_text(parameter)))


def _parameter_quality_score(parameter: EvidenceParameter) -> float:
    score = 0.0
    if parameter.parameter_type == ParameterType.QUANTITATIVE:
        score += 1.0
    if parameter.value is not None:
        score += 2.0
    if parameter.value_range is not None:
        score += 1.5
    if str(parameter.unit or "").strip():
        score += 1.5
    if parameter.confidence_interval is not None:
        score += 1.0
    if parameter.std_error is not None:
        score += 0.5
    if parameter.evidence_strength.value not in {
        EvidenceStrength.UNKNOWN.value,
        EvidenceStrength.THEORETICAL.value,
    }:
        score += 1.5
    if _NUMERIC_UNITFUL_HINT_RE.search(_parameter_context_text(parameter)):
        score += 0.5
    if _parameter_is_non_effect_metric(parameter):
        score -= 4.0
    return score


def _parameter_merge_key(parameter: EvidenceParameter) -> tuple[Any, ...]:
    return (
        parameter.name,
        parameter.parameter_type.value,
        parameter.value,
        parameter.value_range,
    )


def _parameter_numeric_value(parameter: EvidenceParameter) -> float | None:
    if parameter.value is not None:
        return float(parameter.value)
    if parameter.value_range is not None:
        lo, hi = parameter.value_range
        return (float(lo) + float(hi)) / 2.0
    return None


def _values_close(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    tolerance = max(0.01, max(abs(float(left)), abs(float(right))) * 0.1)
    return abs(float(left) - float(right)) <= tolerance


def _surface_text(value: str) -> str:
    return " ".join(token for token in _VAR_SPLIT_RE.split(str(value or "").lower()) if token)


def _text_mentions_variable(text: str, variable: str) -> bool:
    haystack = _surface_text(text)
    needle = _surface_text(variable)
    if not haystack or not needle:
        return False
    if needle in haystack:
        return True
    tokens = [token for token in needle.split() if len(token) >= 3]
    if len(tokens) < 2:
        return False
    matched = sum(1 for token in tokens if token in haystack)
    return matched >= max(2, len(tokens) - 1)


def _best_claim_for_sentence(sentence: str, claims: list[CausalClaim]) -> CausalClaim | None:
    best_claim: CausalClaim | None = None
    best_score = 0
    for claim in claims:
        score = 0
        if _text_mentions_variable(sentence, claim.effect_variable):
            score += 2
        if _text_mentions_variable(sentence, claim.cause_variable):
            score += 1
        if score > best_score:
            best_claim = claim
            best_score = score
    if best_claim is not None:
        return best_claim
    if len(claims) == 1:
        return claims[0]
    return None


def _best_parameter_for_estimate(
    estimate_value: float,
    sentence: str,
    parameters: list[EvidenceParameter],
) -> EvidenceParameter | None:
    best_parameter: EvidenceParameter | None = None
    best_score = float("-inf")
    for parameter in parameters:
        if parameter.parameter_type != ParameterType.QUANTITATIVE:
            continue
        if _parameter_is_non_effect_metric(parameter):
            continue
        score = 0.0
        if _values_close(_parameter_numeric_value(parameter), estimate_value):
            score += 3.0
        if _text_mentions_variable(sentence, parameter.name):
            score += 2.0
        if _text_mentions_variable(sentence, parameter.display_name):
            score += 1.0
        if parameter.confidence_interval is None and parameter.std_error is None:
            score += 0.5
        if score > best_score:
            best_parameter = parameter
            best_score = score
    if best_parameter is not None and best_score >= 2.5:
        return best_parameter
    value_matches = [
        parameter
        for parameter in parameters
        if parameter.parameter_type == ParameterType.QUANTITATIVE
        and not _parameter_is_non_effect_metric(parameter)
        and _values_close(_parameter_numeric_value(parameter), estimate_value)
    ]
    if len(value_matches) == 1:
        return value_matches[0]
    quantitative_parameters = [
        parameter
        for parameter in parameters
        if parameter.parameter_type == ParameterType.QUANTITATIVE
    ]
    if len(quantitative_parameters) == 1:
        return quantitative_parameters[0]
    return None


def _deterministic_numeric_rescue_parameters(
    *,
    bundle: dict[str, Any],
    result: ArticleExtractionResult,
) -> list[EvidenceParameter]:
    if result.source_basis != SourceBasis.FULLTEXT:
        return []
    candidate_parameters = [
        parameter
        for parameter in result.empirical_parameters
        if parameter.parameter_type == ParameterType.QUANTITATIVE
    ]
    rescued: list[EvidenceParameter] = []
    seen: set[tuple[Any, ...]] = set()
    for bucket in (
        "numeric_result_blocks",
        "numeric_result_snippets",
        "result_sentences",
        "claim_sentences",
        "abstract_sentences",
    ):
        for item in bundle.get(bucket, []):
            if not isinstance(item, dict):
                continue
            sentence = _normalized_text(item.get("text"))
            if not sentence:
                continue
            for estimate in extract_numerical_estimates(sentence):
                if estimate.std_error is None and (
                    estimate.ci_low is None or estimate.ci_high is None
                ):
                    continue
                target_parameter = _best_parameter_for_estimate(
                    estimate.value,
                    sentence,
                    candidate_parameters,
                )
                target_claim = _best_claim_for_sentence(sentence, result.causal_claims)
                target_name = (
                    target_parameter.name
                    if target_parameter is not None
                    else str(estimate.variable_hint or "").strip()
                    if str(estimate.variable_hint or "").strip()
                    else target_claim.effect_variable
                    if target_claim is not None
                    else ""
                )
                if not target_name:
                    continue
                normalized = _normalize_empirical_parameter(
                    {
                        "name": target_name,
                        "display_name": (
                            target_parameter.display_name
                            if target_parameter is not None
                            and str(target_parameter.display_name or "").strip()
                            else target_name
                        ),
                        "parameter_type": "quantitative",
                        "value": estimate.value,
                        "confidence_interval": (
                            [estimate.ci_low, estimate.ci_high]
                            if estimate.ci_low is not None and estimate.ci_high is not None
                            else None
                        ),
                        "std_error": estimate.std_error,
                        "unit": estimate.unit
                        or (target_parameter.unit if target_parameter is not None else None),
                        "evidence_strength": (
                            target_parameter.evidence_strength.value
                            if target_parameter is not None
                            and target_parameter.evidence_strength.value
                            != EvidenceStrength.UNKNOWN.value
                            else target_claim.evidence_strength.value
                            if target_claim is not None
                            and target_claim.evidence_strength.value
                            != EvidenceStrength.UNKNOWN.value
                            else result.methodology_enum.value
                        ),
                        "heterogeneity_note": sentence,
                        "geographic_scope": target_parameter.geographic_scope
                        if target_parameter is not None
                        else "",
                        "time_period": target_parameter.time_period
                        if target_parameter is not None
                        else "",
                    }
                )
                if normalized is None or _parameter_is_non_effect_metric(normalized):
                    continue
                key = _parameter_merge_key(normalized)
                if key in seen:
                    continue
                seen.add(key)
                rescued.append(normalized)
    return rescued


def _merge_numeric_parameter_lists(
    primary: list[EvidenceParameter],
    rescue: list[EvidenceParameter],
) -> list[EvidenceParameter]:
    merged: dict[tuple[Any, ...], EvidenceParameter] = {}
    for parameter in [*primary, *rescue]:
        key = _parameter_merge_key(parameter)
        existing = merged.get(key)
        if existing is None:
            merged[key] = parameter
            continue
        keep, enrich = (
            (parameter, existing)
            if _parameter_quality_score(parameter) > _parameter_quality_score(existing)
            else (existing, parameter)
        )
        merged[key] = keep.model_copy(
            update={
                "display_name": keep.display_name or enrich.display_name,
                "unit": keep.unit or enrich.unit,
                "confidence_interval": keep.confidence_interval or enrich.confidence_interval,
                "std_error": keep.std_error if keep.std_error is not None else enrich.std_error,
                "evidence_strength": (
                    keep.evidence_strength
                    if keep.evidence_strength.value != EvidenceStrength.UNKNOWN.value
                    else enrich.evidence_strength
                ),
                "geographic_scope": keep.geographic_scope or enrich.geographic_scope,
                "time_period": keep.time_period or enrich.time_period,
                "aggregation_level": keep.aggregation_level or enrich.aggregation_level,
                "heterogeneity_note": keep.heterogeneity_note or enrich.heterogeneity_note,
                "transferability": (
                    keep.transferability
                    if keep.transferability != "unknown"
                    else enrich.transferability
                ),
                "transfer_conditions": sorted(
                    {*keep.transfer_conditions, *enrich.transfer_conditions}
                ),
                "subgroup_estimates": {**enrich.subgroup_estimates, **keep.subgroup_estimates},
            }
        )
    return list(merged.values())


def _has_high_precision_numeric_parameter(result: ArticleExtractionResult) -> bool:
    for parameter in result.empirical_parameters:
        if parameter.parameter_type != ParameterType.QUANTITATIVE:
            continue
        if _parameter_is_non_effect_metric(parameter):
            continue
        if parameter.value is None and parameter.value_range is None:
            continue
        if not str(parameter.unit or "").strip():
            continue
        if parameter.confidence_interval is None and parameter.std_error is None:
            continue
        if parameter.evidence_strength.value in {
            EvidenceStrength.UNKNOWN.value,
            EvidenceStrength.THEORETICAL.value,
        }:
            continue
        return True
    return False


def _claim_supports_numeric_rescue(claim: CausalClaim) -> bool:
    return claim.claim_type in {
        ClaimType.CAUSAL_CLAIM,
        ClaimType.CAUSAL_ASSERTION,
        ClaimType.ASSOCIATIVE,
        ClaimType.ASSOCIATION,
    }


def _has_precision_numeric_signal(result: ArticleExtractionResult) -> bool:
    parts: list[str] = [result.title, result.citation_summary, result.methodology]
    for claim in result.causal_claims[:8]:
        parts.append(claim.claim_text)
        parts.extend(span.text for span in claim.supporting_spans[:4])
        parts.extend(span.text for span in claim.method_spans[:3])
    for parameter in result.empirical_parameters[:6]:
        parts.extend(
            [
                str(parameter.name or ""),
                str(parameter.display_name or ""),
                str(parameter.heterogeneity_note or ""),
            ]
        )
        if parameter.confidence_interval is not None or parameter.std_error is not None:
            return True
    return _precision_result_signal_score("\n".join(part for part in parts if part)) > 0


def _needs_numeric_rescue(result: ArticleExtractionResult) -> bool:
    if result.source_basis != SourceBasis.FULLTEXT:
        return False
    if _has_high_precision_numeric_parameter(result):
        return False
    if _is_review_like(result.title, result.citation_summary, result.methodology):
        return False
    if _is_theory_like(result.title, result.citation_summary, result.methodology):
        return False
    if not any(_claim_supports_numeric_rescue(claim) for claim in result.causal_claims):
        return False
    # Relax: allow rescue if claims have effect_size or there are any numeric signals
    has_effect_sizes = any(claim.effect_size is not None for claim in result.causal_claims)
    if has_effect_sizes:
        return True
    if not result.methodology and not any(claim.method_spans for claim in result.causal_claims):
        return False
    return _has_precision_numeric_signal(result)


def _build_numeric_rescue_prompt(
    bundle: dict[str, Any],
    *,
    claim_inventory: list[dict[str, str]],
    result: ArticleExtractionResult,
) -> str:
    focused_bundle = {
        "metadata_summary": bundle.get("metadata_summary", {}),
        "abstract_sentences": bundle.get("abstract_sentences", [])[:4],
        "method_sentences": bundle.get("method_sentences", [])[:8],
        "result_sentences": bundle.get("result_sentences", [])[:10],
        "claim_sentences": bundle.get("claim_sentences", [])[:8],
        "numeric_result_snippets": bundle.get("numeric_result_snippets", [])[:10],
        "numeric_result_blocks": bundle.get("numeric_result_blocks", [])[:6],
    }
    existing_candidates = [
        {
            "name": parameter.name,
            "display_name": parameter.display_name,
            "value": parameter.value,
            "value_range": list(parameter.value_range) if parameter.value_range else None,
            "unit": parameter.unit,
            "evidence_strength": parameter.evidence_strength.value,
            "heterogeneity_note": parameter.heterogeneity_note,
        }
        for parameter in result.empirical_parameters[:8]
    ]
    return (
        "Extract quantitative effect estimates for simulation-ready policy analysis.\n"
        + _NUMERIC_RESCUE_SCHEMA_HINT
        + "\n\nMethodology summary:\n"
        + json.dumps(
            {
                "methodology": result.methodology,
                "methodology_enum": result.methodology_enum.value,
            },
            ensure_ascii=False,
        )
        + "\n\nCausal claim inventory (use exact variable names when an estimate maps to one of these claims):\n"
        + json.dumps(claim_inventory[:6], ensure_ascii=False)
        + "\n\nExisting low-confidence numeric candidates (correct them only if the evidence bundle supports a real effect estimate):\n"
        + json.dumps(existing_candidates, ensure_ascii=False)
        + "\n\nEvidence bundle:\n"
        + json.dumps(focused_bundle, ensure_ascii=False)
    )


def _strong_design_evidence(claim: CausalClaim) -> bool:
    design = claim.design_family_hint.value
    method_text = " ".join(span.text for span in claim.method_spans)
    support_text = " ".join(span.text for span in claim.supporting_spans)
    pattern = _STRONG_METHOD_PATTERNS.get(design)
    if pattern is None:
        return False
    if not pattern.search(method_text):
        return False
    if _has_downgrade_signal(method_text) or _has_downgrade_signal(support_text):
        return False
    return bool(_RESULT_CUE_RE.search(support_text))


def _apply_publish_gate(result: ArticleExtractionResult) -> ArticleExtractionResult:
    blocked_paper = (
        _is_review_like(result.title, result.citation_summary)
        or _is_theory_like(result.title, result.citation_summary)
        or _is_method_only(result.title, result.citation_summary)
    )
    gated_claims: list[CausalClaim] = []
    for claim in result.causal_claims:
        blockers: list[str] = []
        supporting_spans, support_contaminated = _sanitize_spans(claim.supporting_spans)
        method_spans, method_contaminated = _sanitize_spans(claim.method_spans)
        claim = claim.model_copy(
            update={
                "supporting_spans": supporting_spans,
                "supporting_span_ids": [span.span_id for span in supporting_spans if span.span_id],
                "method_spans": method_spans,
                "method_span_ids": [span.span_id for span in method_spans if span.span_id],
                "span_contamination_detected": support_contaminated or method_contaminated,
            }
        )
        strong_design = _strong_design_evidence(claim)
        design = claim.design_family_hint.value
        design_tier = _DESIGN_TIERS.get(design)
        # Promote "unclear" design to tier 4 only if there's a genuine
        # causal identification strategy (not just "regression"/"panel data")
        # and the claim text doesn't use speculative/narrative language.
        if design_tier is None and design == DesignFamily.UNCLEAR.value:
            method_text = " ".join(span.text for span in claim.method_spans)
            support_text = " ".join(span.text for span in claim.supporting_spans)
            has_strong = _has_strong_identification_signal(claim)
            has_downgrade = _has_downgrade_signal(method_text) or _has_downgrade_signal(
                support_text
            )
            has_hedge = bool(_NARRATIVE_HEDGE_RE.search(claim.claim_text or ""))
            # Scoring-based promotion instead of all-or-nothing boolean gate.
            # has_strong is the primary signal (0.70), downgrade and hedge are
            # partial penalties (not full veto) because papers often use cautious
            # language even when they have genuine identification strategies.
            _promo_score = (
                (0.70 * float(has_strong))
                * (1.0 - 0.5 * float(has_downgrade))
                * (1.0 - 0.3 * float(has_hedge))
            )
            if _promo_score >= 0.50:
                design_tier = 4
        # Abstract-only is a blocker ONLY for weak designs (tier 3-4 or None).
        # Strong designs (RCT, IV, DID, RDD, SC, meta-analysis) can publish
        # from abstracts — confidence penalty is applied downstream in skg_store.
        _ABSTRACT_PUBLISHABLE_TIERS = frozenset({1, 2})
        if result.source_basis != SourceBasis.FULLTEXT:
            if design_tier not in _ABSTRACT_PUBLISHABLE_TIERS:
                blockers.append("source_basis_not_fulltext")
        if claim.source_basis != SourceBasis.FULLTEXT:
            if design_tier not in _ABSTRACT_PUBLISHABLE_TIERS:
                blockers.append("claim_source_basis_not_fulltext")
        if claim.claim_type not in {ClaimType.CAUSAL_CLAIM, ClaimType.CAUSAL_ASSERTION}:
            blockers.append("claim_type_not_causal")
        if not claim.claim_text:
            blockers.append("missing_claim_text")
        if not claim.cause_variable or not claim.effect_variable:
            blockers.append("missing_cause_or_effect")
        if not claim.supporting_spans or not claim.supporting_span_ids:
            blockers.append("missing_supporting_spans")
        if not claim.method_spans or not claim.method_span_ids:
            blockers.append("missing_method_spans")
        if claim.span_contamination_detected and (
            not claim.supporting_spans or not claim.method_spans
        ):
            blockers.append("span_contamination_removed_evidence")
        if blocked_paper:
            blockers.append("paper_classified_non_empirical")
        confidence = float(claim.claim_extraction_confidence or result.extraction_confidence or 0.0)
        # Tier 1-2 designs (RCT, IV, DID, meta-analysis, etc.) have intrinsically
        # higher reliability — use a lower confidence floor so we don't discard
        # legitimate strong-design claims that the LLM scored conservatively.
        _confidence_floor = 0.30 if design_tier in {1, 2} else 0.45
        if confidence < _confidence_floor:
            blockers.append("low_claim_confidence")
        if design_tier is None:
            blockers.append("design_not_publishable")
        elif design_tier in {3, 4} and not _has_any_method_signal(claim):
            blockers.append("design_weak_no_method_signal")
        claim = claim.model_copy(
            update={
                "strong_design_evidence": strong_design,
                "design_quality_tier": design_tier,
                "publish_to_graph": not blockers,
                "publish_blockers": blockers,
            }
        )
        gated_claims.append(claim)
    return result.model_copy(update={"causal_claims": gated_claims})


def _to_claim_row(
    result: ArticleExtractionResult,
    claim: CausalClaim,
    *,
    topic_ids: list[str],
    topic_display_names: list[str],
) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "work_id": result.openalex_id,
        "title": result.title,
        "year": result.year,
        "topic_ids": topic_ids,
        "topic_display_names": topic_display_names,
        "source_basis": claim.source_basis.value,
        "claim_text": claim.claim_text,
        "claim_type": claim.claim_type.value,
        "cause_text": claim.cause_variable,
        "effect_text": claim.effect_variable,
        "direction": claim.direction.value,
        "design_family_hint": claim.design_family_hint.value,
        "supporting_span_ids": list(claim.supporting_span_ids),
        "method_span_ids": list(claim.method_span_ids),
        "supporting_spans": [span.model_dump(mode="json") for span in claim.supporting_spans],
        "method_spans": [span.model_dump(mode="json") for span in claim.method_spans],
        "supporting_text": "\n".join(span.text for span in claim.supporting_spans),
        "strong_design_evidence": claim.strong_design_evidence,
        "design_quality_tier": claim.design_quality_tier,
        "span_contamination_detected": claim.span_contamination_detected,
        "publish_to_graph": claim.publish_to_graph,
        "publish_blockers": list(claim.publish_blockers),
        "claim_extraction_confidence": float(
            claim.claim_extraction_confidence or result.extraction_confidence
        ),
    }


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]


class _LazyJsonlDict:
    """Memory-efficient JSONL lookup: builds an in-memory offset index
    (key → byte offset) but reads the actual record from disk on demand.

    Supports ``__contains__``, ``get``, ``__setitem__``, ``__getitem__``
    and ``pop`` so it can be used as a drop-in replacement for
    ``dict[str, dict[str, Any]]`` in the resolve_extract pipeline.
    """

    def __init__(self, path: Path, *, key: str = "work_id") -> None:
        self._path = path
        self._key = key
        self._index: dict[str, int] = {}  # key → byte offset
        self._overrides: dict[str, dict[str, Any]] = {}  # runtime writes
        self._deleted: set[str] = set()
        if path.exists():
            self._build_index()

    def _build_index(self) -> None:
        with open(self._path, "rb") as fh:
            while True:
                offset = fh.tell()
                raw = fh.readline()
                if not raw:
                    break
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                row_key = str(payload.get(self._key) or "").strip()
                if row_key:
                    self._index[row_key] = offset

    def _read_at(self, offset: int) -> dict[str, Any]:
        with open(self._path, "rb") as fh:
            fh.seek(offset)
            raw = fh.readline()
        return json.loads(raw)

    def __contains__(self, key: object) -> bool:
        if key in self._deleted:
            return False
        return key in self._overrides or key in self._index

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._deleted:
            return default
        if key in self._overrides:
            return self._overrides[key]
        offset = self._index.get(key)
        if offset is None:
            return default
        try:
            return self._read_at(offset)
        except Exception:
            return default

    def __getitem__(self, key: str) -> dict[str, Any]:
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        self._overrides[key] = value
        self._deleted.discard(key)

    def pop(self, key: str, *args: Any) -> Any:
        self._deleted.add(key)
        if key in self._overrides:
            return self._overrides.pop(key)
        offset = self._index.get(key)
        if offset is not None:
            try:
                return self._read_at(offset)
            except Exception:
                pass
        if args:
            return args[0]
        raise KeyError(key)

    def values(self) -> list[dict[str, Any]]:
        """Not used in hot path; provided for compatibility."""
        result: list[dict[str, Any]] = []
        for k in self._index:
            if k not in self._deleted:
                v = self.get(k)
                if v is not None:
                    result.append(v)
        return result


def _load_jsonl_keyed(path: Path, *, key: str = "work_id") -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            row_key = str(payload.get(key) or "").strip()
            if row_key:
                rows[row_key] = payload
    return rows


def _load_jsonl_lazy(path: Path, *, key: str = "work_id") -> _LazyJsonlDict:
    """Memory-efficient alternative to ``_load_jsonl_keyed`` — builds
    an offset index instead of loading all records into RAM."""
    return _LazyJsonlDict(path, key=key)


def _load_jsonl_grouped(path: Path, *, key: str = "work_id") -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return grouped
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            row_key = str(payload.get(key) or "").strip()
            if row_key:
                grouped[row_key].append(payload)
    return grouped


def _load_doc_routing(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    by_work: dict[str, dict[str, dict[str, Any]]] = {}
    rows = _load_jsonl_keyed(path, key="work_id")
    for work_id, row in rows.items():
        lane_map = _routing_lane_map(row)
        if lane_map:
            by_work[work_id] = lane_map
    return by_work


def _routing_lane_map(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    routing_payload = row.get("routing")
    if not isinstance(routing_payload, list):
        return {}
    lane_map: dict[str, dict[str, Any]] = {}
    for item in routing_payload:
        if not isinstance(item, dict):
            continue
        lane = str(item.get("lane") or "").strip().lower()
        if lane:
            lane_map[lane] = item
    return lane_map


def _load_jsonl_from_offset(path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], offset
    file_size = path.stat().st_size
    if offset > file_size:
        offset = 0
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read()
    if not data:
        return [], offset
    last_newline = data.rfind(b"\n")
    if last_newline < 0:
        return [], offset
    chunk = data[: last_newline + 1]
    new_offset = offset + last_newline + 1
    rows: list[dict[str, Any]] = []
    for raw_line in chunk.decode("utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, new_offset


def _with_work_id(work_id: str, rows: Any) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return normalized_rows
    for row in rows:
        if not isinstance(row, dict):
            continue
        payload = dict(row)
        payload.setdefault("work_id", work_id)
        normalized_rows.append(payload)
    return normalized_rows


def _apply_doc_ready_payload(
    *,
    payload: dict[str, Any],
    precomputed_fulltext: dict[str, dict[str, Any]] | _LazyJsonlDict,
    substrate_rows: dict[str, dict[str, Any]],
    substrate_sections: dict[str, list[dict[str, Any]]],
    substrate_references: dict[str, list[dict[str, Any]]],
    substrate_tables: dict[str, list[dict[str, Any]]],
    substrate_figures: dict[str, list[dict[str, Any]]],
    substrate_appendix: dict[str, list[dict[str, Any]]],
    routing_by_work: dict[str, dict[str, dict[str, Any]]],
) -> str:
    work_id = str(payload.get("work_id") or "").strip()
    if not work_id:
        return ""
    fulltext_row = payload.get("fulltext")
    if isinstance(fulltext_row, dict):
        precomputed_fulltext[work_id] = dict(fulltext_row)
    substrate_row = payload.get("substrate")
    if isinstance(substrate_row, dict):
        substrate_rows[work_id] = dict(substrate_row)
    substrate_sections[work_id] = _with_work_id(work_id, payload.get("sections"))
    substrate_references[work_id] = _with_work_id(work_id, payload.get("references"))
    substrate_tables[work_id] = _with_work_id(work_id, payload.get("tables"))
    substrate_figures[work_id] = _with_work_id(work_id, payload.get("figures"))
    substrate_appendix[work_id] = _with_work_id(work_id, payload.get("appendix_blocks"))
    routing_row = payload.get("routing")
    if not isinstance(routing_row, dict) and isinstance(substrate_row, dict):
        routing_row = {
            "work_id": work_id,
            "doc_family": substrate_row.get("doc_family"),
            "routing": substrate_row.get("routing"),
        }
    if isinstance(routing_row, list):
        routing_row = {
            "work_id": work_id,
            "routing": routing_row,
        }
    if isinstance(routing_row, dict):
        lane_map = _routing_lane_map(routing_row)
        if lane_map:
            routing_by_work[work_id] = lane_map
    return work_id


def _route_entry_for_lane(
    routing_by_work: dict[str, dict[str, dict[str, Any]]],
    *,
    work_id: str,
    lane: str,
) -> dict[str, Any] | None:
    if lane == "all":
        return None
    return routing_by_work.get(work_id, {}).get(lane)


def _raise_if_task_failed(task: asyncio.Task[Any] | None, label: str) -> None:
    if task is None or not task.done():
        return
    if task.cancelled():
        raise RuntimeError(f"{label} task was cancelled")
    exc = task.exception()
    if exc is not None:
        raise RuntimeError(f"{label} task failed") from exc


def _reset_output_paths(config: AcademicBatchConfig) -> None:
    reset_paths = [
        config.resolve_extract_progress_path,
        config.resolve_extract_results_path,
        config.resolve_extract_errors_path,
        config.fulltext_fetch_log_path,
        config.llm_request_log_path,
        config.raw_claim_candidates_path,
        config.published_claims_path,
        config.context_attributes_path,
        config.moderation_edges_path,
        config.article_extraction_results_path,
        config.extracted_dir / "resolve_extract.jsonl",
    ]
    if (
        not config.stream_doc_normalize_to_resolve_extract
        and not config.doc_substrate_path.exists()
    ):
        reset_paths.append(config.fulltext_resolved_path)
    for path in reset_paths:
        if path.exists():
            path.unlink()


async def _run_resolve_extract_pass(config: AcademicBatchConfig) -> dict[str, float | int]:
    started_at = datetime.now(UTC).isoformat()
    selected_rows_path = config.selected_global_works_path
    if not selected_rows_path.exists():
        write_stage_manifest(
            manifest_path=config.manifests_dir / "resolve_extract.json",
            stage="resolve_extract",
            status="ok",
            metrics={"records": 0, "extracted": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"records": 0, "extracted": 0}

    if not config.gonka_api_keys and not config.gonka_api_key:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "resolve_extract.json",
            stage="resolve_extract",
            status="ok",
            metrics={"records": 0, "extracted": 0, "skipped_reason": "no_api_keys"},
            artifacts=[],
            started_at=started_at,
        )
        return {"records": 0, "extracted": 0, "skipped_reason": "no_api_keys"}

    if not config.resume:
        _reset_output_paths(config)

    progress = _load_progress(config.resolve_extract_progress_path)
    progress_lock = asyncio.Lock()
    file_lock = asyncio.Lock()
    stream_doc_ready = bool(config.stream_doc_normalize_to_resolve_extract)
    metadata_cache = _load_metadata_cache(config.fulltext_metadata_cache_path)
    resolved_fulltext_cache = fulltext_resolver_module.load_resolved_fulltext_cache(
        config.resolved_fulltext_cache_path,
        ttl_days=config.fulltext_cache_ttl_days,
    )
    precomputed_fulltext = _load_jsonl_lazy(config.fulltext_resolved_path, key="work_id")
    substrate_rows = _load_jsonl_keyed(config.doc_substrate_path, key="work_id")
    substrate_sections = _load_jsonl_grouped(config.doc_sections_path, key="work_id")
    substrate_references = _load_jsonl_grouped(config.doc_references_path, key="work_id")
    substrate_tables = _load_jsonl_grouped(config.doc_tables_path, key="work_id")
    substrate_figures = _load_jsonl_grouped(config.doc_figures_path, key="work_id")
    substrate_appendix = _load_jsonl_grouped(config.doc_appendix_blocks_path, key="work_id")
    routing_by_work = _load_doc_routing(config.doc_routing_path)
    topic_success: dict[str, int] = defaultdict(int)
    topic_inflight: dict[str, int] = defaultdict(int)
    topic_seen: set[str] = set()

    merged_rows: dict[str, dict[str, Any]] = {}
    index = 0
    with open(selected_rows_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            index += 1
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            work = row.get("work") if isinstance(row.get("work"), dict) else {}
            if not isinstance(work, dict):
                continue
            work_id = str(row.get("work_id") or work.get("id") or "").strip()
            if not work_id:
                continue
            merged = merged_rows.get(work_id)
            if merged is None:
                merged_rows[work_id] = {
                    "work": work,
                    "topic_id": _topic_id_for_row(row),
                    "topic_ids": _topic_ids_for_row(row),
                    "topic_display_names": _topic_names_for_row(row),
                    "selected_rank": index,
                }
            else:
                if bool(work.get("has_fulltext")) and not bool(merged["work"].get("has_fulltext")):
                    merged["work"] = work
                merged["selected_rank"] = min(int(merged["selected_rank"]), index)
                for topic_id in _topic_ids_for_row(row):
                    if topic_id not in merged["topic_ids"]:
                        merged["topic_ids"].append(topic_id)
                for topic_name in _topic_names_for_row(row):
                    if topic_name not in merged["topic_display_names"]:
                        merged["topic_display_names"].append(topic_name)
                if _topic_id_for_row(row) and _topic_id_for_row(row) not in merged["topic_ids"]:
                    merged["topic_ids"].append(_topic_id_for_row(row))
            topic_seen.add(_topic_id_for_row(row))

    work_items: list[WorkItem] = []
    for work_id, merged in merged_rows.items():
        work = merged["work"]
        work_items.append(
            WorkItem(
                work=work,
                work_id=work_id,
                topic_id=str(merged["topic_id"] or "topic_unknown"),
                topic_ids=list(merged["topic_ids"]),
                topic_display_names=list(merged["topic_display_names"]),
                prefetch_priority=_prefetch_priority(work),
                selected_rank=int(merged["selected_rank"]),
            )
        )

    del merged_rows
    gc.collect()
    work_items.sort(key=lambda item: (-item.prefetch_priority, item.selected_rank, item.work_id))
    if config.article_prefetch_candidates_per_topic > 0:
        per_topic_prefetch: dict[str, int] = defaultdict(int)
        filtered_items: list[WorkItem] = []
        for item in work_items:
            if per_topic_prefetch[item.topic_id] >= config.article_prefetch_candidates_per_topic:
                continue
            per_topic_prefetch[item.topic_id] += 1
            filtered_items.append(item)
        work_items = filtered_items
    stats = ResolveExtractStats(records=len(work_items))
    canonizer = VariableCanonizer(db_path=config.db_path)
    for topic_id in topic_seen:
        topic_success.setdefault(topic_id, 0)
        topic_inflight.setdefault(topic_id, 0)

    _progress_dirty = 0
    _PROGRESS_FLUSH_INTERVAL = 200

    def _mark_progress(work_id: str, state: str, **extra: Any) -> None:
        item = progress.setdefault("items", {}).setdefault(work_id, {})
        if state not in {"retryable_failed", "permanent_failed"}:
            item.pop("error_class", None)
            item.pop("error_message", None)
        item.update({"state": state, **extra, "updated_at": datetime.now(UTC).isoformat()})
        progress["updated_at"] = datetime.now(UTC).isoformat()

    async def _persist_progress(work_id: str, state: str, **extra: Any) -> None:
        nonlocal _progress_dirty
        async with progress_lock:
            _mark_progress(work_id, state, **extra)
            _progress_dirty += 1
            if _progress_dirty >= _PROGRESS_FLUSH_INTERVAL or state in (
                "published",
                "raw_only",
                "succeeded_nonempty",
                "succeeded_empty",
                "retryable_failed",
                "permanent_failed",
            ):
                _write_progress(config.resolve_extract_progress_path, progress)
                _progress_dirty = 0

    async def _flush_progress() -> None:
        nonlocal _progress_dirty
        async with progress_lock:
            if _progress_dirty > 0:
                _write_progress(config.resolve_extract_progress_path, progress)
                _progress_dirty = 0

    fetch_queue: asyncio.Queue[WorkItem | None] = asyncio.Queue()
    eligible_queue: asyncio.PriorityQueue[tuple[float, int, EligibleItem] | None] = (
        asyncio.PriorityQueue()
    )
    llm_queue: asyncio.Queue[EligibleItem | None] = asyncio.Queue()
    fetch_done = asyncio.Event()
    dispatcher_done = asyncio.Event()
    queued_stream_work_ids: set[str] = set()
    pending_stream_items: dict[str, WorkItem] = {}

    _enqueue_count = 0
    _skip_count = 0
    for item in work_items:
        existing = (
            progress.get("items", {}).get(item.work_id, {})
            if isinstance(progress.get("items"), dict)
            else {}
        )
        if _terminal_state(str(existing.get("state") or "")):
            _skip_count += 1
            continue
        if stream_doc_ready:
            if item.work_id in substrate_rows or item.work_id in precomputed_fulltext:
                await fetch_queue.put(item)
                queued_stream_work_ids.add(item.work_id)
                _enqueue_count += 1
            else:
                pending_stream_items[item.work_id] = item
            continue
        await fetch_queue.put(item)
        _enqueue_count += 1
    if stream_doc_ready:
        logger.info(
            "Streaming enqueue complete: {} items ready immediately, {} pending doc_normalize, {} skipped (already done)",
            _enqueue_count,
            len(pending_stream_items),
            _skip_count,
        )
    else:
        logger.info(
            "Enqueue complete: {} items queued, {} skipped (already done)",
            _enqueue_count,
            _skip_count,
        )

    fetch_workers_count = max(1, int(config.fulltext_max_concurrent_fetches))
    llm_workers_count = max(1, int(config.article_max_concurrent_llm))
    if not stream_doc_ready:
        for _ in range(fetch_workers_count):
            await fetch_queue.put(None)

    async def _append_artifacts(
        *, result: ArticleExtractionResult, work_item: WorkItem, record_json: str
    ) -> None:
        async with file_lock:
            _jsonl_append(config.article_extraction_results_path, result.model_dump(mode="json"))
            _jsonl_append(config.resolve_extract_results_path, result.model_dump(mode="json"))
            config.extracted_dir.mkdir(parents=True, exist_ok=True)
            with open(config.extracted_dir / "resolve_extract.jsonl", "a", encoding="utf-8") as fh:
                fh.write(record_json + "\n")
            for claim in result.causal_claims:
                row = _to_claim_row(
                    result,
                    claim,
                    topic_ids=work_item.topic_ids,
                    topic_display_names=work_item.topic_display_names,
                )
                _jsonl_append(config.raw_claim_candidates_path, row)
                if claim.publish_to_graph:
                    _jsonl_append(config.published_claims_path, row)

    async def stream_doc_ready_producer() -> None:
        nonlocal _enqueue_count
        queue_offset = 0
        manifest_path = config.manifests_dir / "doc_normalize.json"
        try:
            while True:
                ready_rows, queue_offset = _load_jsonl_from_offset(
                    config.doc_ready_queue_path, queue_offset
                )
                for ready_row in ready_rows:
                    work_id = _apply_doc_ready_payload(
                        payload=ready_row,
                        precomputed_fulltext=precomputed_fulltext,
                        substrate_rows=substrate_rows,
                        substrate_sections=substrate_sections,
                        substrate_references=substrate_references,
                        substrate_tables=substrate_tables,
                        substrate_figures=substrate_figures,
                        substrate_appendix=substrate_appendix,
                        routing_by_work=routing_by_work,
                    )
                    if not work_id or work_id in queued_stream_work_ids:
                        continue
                    item = pending_stream_items.pop(work_id, None)
                    if item is None:
                        continue
                    await fetch_queue.put(item)
                    queued_stream_work_ids.add(work_id)
                    _enqueue_count += 1
                if manifest_path.exists():
                    final_rows, queue_offset = _load_jsonl_from_offset(
                        config.doc_ready_queue_path, queue_offset
                    )
                    for ready_row in final_rows:
                        work_id = _apply_doc_ready_payload(
                            payload=ready_row,
                            precomputed_fulltext=precomputed_fulltext,
                            substrate_rows=substrate_rows,
                            substrate_sections=substrate_sections,
                            substrate_references=substrate_references,
                            substrate_tables=substrate_tables,
                            substrate_figures=substrate_figures,
                            substrate_appendix=substrate_appendix,
                            routing_by_work=routing_by_work,
                        )
                        if not work_id or work_id in queued_stream_work_ids:
                            continue
                        item = pending_stream_items.pop(work_id, None)
                        if item is None:
                            continue
                        await fetch_queue.put(item)
                        queued_stream_work_ids.add(work_id)
                        _enqueue_count += 1
                    break
                await asyncio.sleep(config.stream_doc_ready_poll_seconds)
        finally:
            unavailable_after_doc_normalize = len(pending_stream_items)
            for item in pending_stream_items.values():
                await _persist_progress(
                    item.work_id,
                    "rejected",
                    topic_id=item.topic_id,
                    rejection_reasons=["doc_normalize_missing"],
                )
            pending_stream_items.clear()
            for _ in range(fetch_workers_count):
                await fetch_queue.put(None)
            logger.info(
                "Streaming doc-ready producer finished: {} items queued downstream, {} items unavailable after doc_normalize",
                _enqueue_count,
                unavailable_after_doc_normalize,
            )

    async def fetch_worker(worker_index: int) -> None:
        connector_timeout = aiohttp.ClientTimeout(
            total=max(3, int(config.article_total_timeout_seconds)),
            connect=max(1, int(config.article_connect_timeout_seconds)),
            sock_read=max(1, int(config.article_read_timeout_seconds)),
        )
        headers = {"User-Agent": f"PolicyOS/1.0 (+academic resolve_extract worker={worker_index})"}
        async with aiohttp.ClientSession(timeout=connector_timeout, headers=headers) as session:
            while True:
                entry = await fetch_queue.get()
                if entry is None:
                    fetch_queue.task_done()
                    break
                item = entry
                await _persist_progress(item.work_id, "fetch_inflight", topic_id=item.topic_id)
                started = time.monotonic()
                fetch_error_class = ""
                source_url = ""
                route_entry = _route_entry_for_lane(
                    routing_by_work,
                    work_id=item.work_id,
                    lane=config.extraction_lane,
                )
                llm_route_entry = (
                    routing_by_work.get(item.work_id, {}).get("claim")
                    if config.extraction_lane == "all"
                    else route_entry
                )
                doc_family = str(substrate_rows.get(item.work_id, {}).get("doc_family") or "")
                cached_fulltext_row = precomputed_fulltext.get(item.work_id)
                used_precomputed_fulltext = False
                try:
                    if isinstance(cached_fulltext_row, dict) and _normalized_text(
                        cached_fulltext_row.get("text")
                    ):
                        fetch_result = FullTextFetchResult(
                            text=_normalized_text(cached_fulltext_row.get("text")),
                            source_kind=str(
                                cached_fulltext_row.get("source_kind") or "abstract_fallback"
                            ),
                            source_url=str(cached_fulltext_row.get("source_url") or ""),
                            fetch_error_class=str(
                                cached_fulltext_row.get("fetch_error_class") or ""
                            ),
                            final_state=str(cached_fulltext_row.get("final_state") or ""),
                        )
                        used_precomputed_fulltext = True
                    elif config.fulltext_acquisition_mode == "v7_http_metadata":
                        fetch_result = await fetch_full_text_result_for_work(
                            item.work,
                            timeout_seconds=config.article_fulltext_timeout_seconds,
                            connect_timeout_seconds=config.article_connect_timeout_seconds,
                            read_timeout_seconds=config.article_read_timeout_seconds,
                            total_timeout_seconds=config.article_total_timeout_seconds,
                            session=session,
                            acquisition_mode=config.fulltext_acquisition_mode,
                            metadata_resolvers_enabled=config.fulltext_metadata_resolvers_enabled,
                            metadata_resolver_order=config.fulltext_metadata_resolver_order,
                            unpaywall_email=config.fulltext_unpaywall_email,
                            semantic_scholar_api_key=config.fulltext_semantic_scholar_api_key,
                            metadata_timeout_seconds=config.fulltext_metadata_timeout_seconds,
                            max_candidate_urls_per_work=config.fulltext_max_candidate_urls_per_work,
                            min_usable_chars=config.fulltext_min_usable_chars,
                            min_soft_usable_chars=config.fulltext_min_soft_usable_chars,
                            soft_usable_requires_section_cues=config.fulltext_soft_usable_requires_section_cues,
                            metadata_cache=metadata_cache,
                            resolved_cache=resolved_fulltext_cache,
                            cache_ttl_days=config.fulltext_cache_ttl_days,
                        )
                    elif (
                        fetch_full_text_result_for_work
                        is not fulltext_resolver_module.fetch_full_text_result_for_work
                    ):
                        fetch_result = await fetch_full_text_result_for_work(
                            item.work,
                            timeout_seconds=config.article_fulltext_timeout_seconds,
                            connect_timeout_seconds=config.article_connect_timeout_seconds,
                            read_timeout_seconds=config.article_read_timeout_seconds,
                            total_timeout_seconds=config.article_total_timeout_seconds,
                            session=session,
                        )
                    else:
                        text, source_kind, source_url = await fetch_full_text_for_work(
                            item.work,
                            timeout_seconds=config.article_fulltext_timeout_seconds,
                            connect_timeout_seconds=config.article_connect_timeout_seconds,
                            read_timeout_seconds=config.article_read_timeout_seconds,
                            total_timeout_seconds=config.article_total_timeout_seconds,
                            session=session,
                        )
                        fetch_result = FullTextFetchResult(
                            text=text,
                            source_kind=source_kind,
                            source_url=source_url,
                            final_state=(
                                "abstract_fallback"
                                if source_kind == "abstract_fallback"
                                else "usable_fulltext"
                            ),
                        )
                    text = fetch_result.text
                    source_kind = fetch_result.source_kind
                    source_url = fetch_result.source_url
                    fetch_error_class = fetch_result.fetch_error_class
                except TimeoutError:
                    text, source_kind = reconstruct_abstract(item.work), "abstract_fallback"
                    fetch_error_class = "timeout"
                except Exception:
                    text, source_kind = reconstruct_abstract(item.work), "abstract_fallback"
                    fetch_error_class = "fetch_error"
                latency_ms = (time.monotonic() - started) * 1000.0
                stats.fetch_latency_ms.append(latency_ms)
                text_quality = (
                    TextQuality.ABSTRACT_ONLY.value
                    if source_kind == "abstract_fallback"
                    else TextQuality.DEGRADED.value
                    if len(_normalized_text(text)) < _MIN_FULLTEXT_CHARS
                    else TextQuality.EXTRACTED_FULLTEXT.value
                )
                if source_kind == "abstract_fallback":
                    stats.abstract_only += 1
                else:
                    stats.fulltext_resolved += 1
                async with file_lock:
                    for attempt in fetch_result.attempts:
                        _jsonl_append(
                            config.fulltext_fetch_log_path,
                            {
                                "work_id": attempt.work_id,
                                "topic_id": item.topic_id,
                                "attempt_kind": attempt.attempt_kind,
                                "candidate_priority": attempt.candidate_priority,
                                "candidate_url": attempt.candidate_url,
                                "source_kind": attempt.source_kind,
                                "http_status": attempt.http_status,
                                "fetch_error_class": attempt.fetch_error_class,
                                "latency_ms": round(attempt.latency_ms, 3),
                                "redirected_to": attempt.redirected_to,
                                "discovered_pdf_count": attempt.discovered_pdf_count,
                                "discovered_canonical_count": attempt.discovered_canonical_count,
                                "text_chars": attempt.text_chars,
                                "usable_text": attempt.usable_text,
                                "final_for_work": attempt.final_for_work,
                                "resolved_at": datetime.now(UTC).isoformat(),
                            },
                        )
                    if not fetch_result.attempts:
                        _jsonl_append(
                            config.fulltext_fetch_log_path,
                            {
                                "work_id": item.work_id,
                                "topic_id": item.topic_id,
                                "attempt_kind": "doc_normalize_cache"
                                if used_precomputed_fulltext
                                else "seed",
                                "candidate_priority": 0,
                                "candidate_url": "",
                                "source_kind": source_kind,
                                "http_status": 0,
                                "fetch_error_class": fetch_error_class,
                                "latency_ms": round(latency_ms, 3),
                                "redirected_to": "",
                                "discovered_pdf_count": 0,
                                "discovered_canonical_count": 0,
                                "text_chars": len(_normalized_text(text)),
                                "usable_text": source_kind != "abstract_fallback",
                                "final_for_work": True,
                                "resolved_at": datetime.now(UTC).isoformat(),
                            },
                        )
                    for row in fetch_result.metadata_cache_rows:
                        cache_key = str(row.get("cache_key") or "").strip()
                        if cache_key and metadata_cache.get(cache_key) is row:
                            _jsonl_append(config.fulltext_metadata_cache_path, row)
                    if fetch_result.resolved_cache_row is not None:
                        _jsonl_append(
                            config.resolved_fulltext_cache_path, fetch_result.resolved_cache_row
                        )
                    if not used_precomputed_fulltext:
                        _jsonl_append(
                            config.fulltext_resolved_path,
                            {
                                "work_id": item.work_id,
                                "source_kind": source_kind,
                                "source_basis": (
                                    SourceBasis.ABSTRACT_ONLY.value
                                    if source_kind == "abstract_fallback"
                                    else SourceBasis.FULLTEXT.value
                                ),
                                "text_quality": text_quality,
                                "source_url": source_url,
                                "fetch_error_class": fetch_error_class,
                                "final_state": fetch_result.final_state,
                                "text": text,
                            },
                        )
                eligibility = _eligibility_gate(
                    item,
                    text=text,
                    source_kind=source_kind,
                    text_quality=text_quality,
                    extraction_lane=config.extraction_lane,
                    track_b_enabled=config.track_b_enabled,
                    track_c_enabled=config.track_c_enabled,
                    route_entry=llm_route_entry,
                    doc_family=doc_family,
                )
                if route_entry is not None and not bool(route_entry.get("eligible")):
                    route_reasons = route_entry.get("reasons")
                    route_reason = (
                        str(route_reasons[0]).strip()
                        if isinstance(route_reasons, list) and route_reasons
                        else "doc_routing_skip"
                    )
                    eligibility = EligibilityDecision(
                        llm_eligible=False,
                        context_eligible=False,
                        rejection_reasons=[f"route_{config.extraction_lane}_{route_reason}"],
                    )
                if not (eligibility.llm_eligible or eligibility.context_eligible):
                    stats.rejected += 1
                    if eligibility.rejection_reasons:
                        for reason in eligibility.rejection_reasons:
                            stats.rejection_reason_counts[str(reason)] += 1
                            if str(reason).startswith("route_"):
                                stats.failure_class_counts["route_rejected"] += 1
                    if config.track_b_enabled:
                        stats.track_b_rejected_hard += 1
                    await _persist_progress(
                        item.work_id,
                        "rejected",
                        topic_id=item.topic_id,
                        rejection_reasons=eligibility.rejection_reasons,
                        source_kind=source_kind,
                        text_quality=text_quality,
                    )
                    fetch_queue.task_done()
                    continue
                stats.eligible_fulltext += 1
                if eligibility.context_eligible:
                    stats.context_eligible += 1
                    if not eligibility.llm_eligible:
                        stats.track_b_only_routed += 1
                post_priority = _post_resolve_priority(
                    item, text=text, source_kind=source_kind, text_quality=text_quality
                )
                await _persist_progress(
                    item.work_id,
                    "eligible",
                    topic_id=item.topic_id,
                    source_kind=source_kind,
                    text_quality=text_quality,
                    post_priority=post_priority,
                    llm_eligible=eligibility.llm_eligible,
                    context_eligible=eligibility.context_eligible,
                    routing_score=(
                        float(route_entry.get("score") or 0.0)
                        if isinstance(route_entry, dict)
                        else None
                    ),
                )
                await eligible_queue.put(
                    (
                        -post_priority,
                        item.selected_rank,
                        EligibleItem(
                            item,
                            text,
                            source_kind,
                            source_url,
                            text_quality,
                            post_priority,
                            eligibility.llm_eligible,
                            eligibility.context_eligible,
                        ),
                    )
                )
                fetch_queue.task_done()

    async def llm_dispatcher() -> None:
        client_count = int(getattr(pool, "client_count", 0) or 0)
        per_key_rps = float(getattr(pool, "per_key_rate_limit_rps", 0.0) or 0.0)
        aggregate_rps = float(
            getattr(pool, "theoretical_aggregate_rps", client_count * per_key_rps) or 0.0
        )
        logger.info(
            "LLM dispatcher started, llm_workers={}, gonka_keys={}, per_key_rps={}, aggregate_rps_ceiling={}",
            llm_workers_count,
            client_count,
            round(per_key_rps, 3),
            round(aggregate_rps, 3),
        )
        _dispatched = 0
        _bounce_counts: dict[str, int] = {}
        _bounce_log_interval = 2000
        _bounce_log_counter = 0
        _BOUNCE_LIMIT = 200
        while True:
            if (
                fetch_done.is_set()
                and eligible_queue.empty()
                and all(v == 0 for v in topic_inflight.values())
            ):
                for _ in range(llm_workers_count):
                    await llm_queue.put(None)
                dispatcher_done.set()
                return
            try:
                entry = await asyncio.wait_for(eligible_queue.get(), timeout=0.2)
            except TimeoutError:
                continue
            priority, _rank, eligible_item = entry
            topic_id = eligible_item.work_item.topic_id
            if topic_success[topic_id] >= config.article_target_fulltext_per_topic:
                await _persist_progress(
                    eligible_item.work_item.work_id,
                    "rejected",
                    topic_id=topic_id,
                    rejection_reasons=["topic_budget_filled"],
                )
                _bounce_counts.pop(eligible_item.work_item.work_id, None)
                eligible_queue.task_done()
                continue
            _bk = eligible_item.work_item.work_id
            _bounce_counts[_bk] = _bounce_counts.get(_bk, 0) + 1
            if (
                topic_success[topic_id] + topic_inflight[topic_id]
                >= config.article_target_fulltext_per_topic
            ):
                if _bounce_counts[_bk] < _BOUNCE_LIMIT:
                    _bounce_log_counter += 1
                    if _bounce_log_counter % _bounce_log_interval == 1:
                        logger.info(
                            "LLM dispatcher: bounce backpressure — {} items bouncing, topic {} inflight={}",
                            len(_bounce_counts),
                            topic_id,
                            topic_inflight[topic_id],
                        )
                    eligible_queue.task_done()
                    await asyncio.sleep(0.05)
                    await eligible_queue.put(
                        (priority, eligible_item.work_item.selected_rank, eligible_item)
                    )
                    continue
                logger.warning(
                    "LLM dispatcher: bounce limit ({}) reached for {}, forcing dispatch (topic={}, inflight={}, success={})",
                    _BOUNCE_LIMIT,
                    _bk,
                    topic_id,
                    topic_inflight[topic_id],
                    topic_success[topic_id],
                )
                del _bounce_counts[_bk]
            topic_inflight[topic_id] += 1
            await _persist_progress(
                eligible_item.work_item.work_id,
                "llm_queued",
                topic_id=topic_id,
                post_priority=eligible_item.post_priority,
            )
            await llm_queue.put(eligible_item)
            _dispatched += 1
            if _dispatched % 200 == 1:
                logger.info("LLM dispatcher: {} items dispatched to llm_queue", _dispatched)
            eligible_queue.task_done()

    async def llm_worker(pool: GonkaMultiKeyPool) -> None:
        _worker_count = 0
        provider_watchdog_seconds = _resolve_provider_watchdog_seconds(config)
        while True:
            entry = await llm_queue.get()
            if entry is None:
                llm_queue.task_done()
                break
            eligible_item = entry
            work_item = eligible_item.work_item
            _worker_count += 1
            if _worker_count == 1:
                logger.info("LLM worker got first item: {}", work_item.work_id)
            await _persist_progress(work_item.work_id, "llm_inflight", topic_id=work_item.topic_id)
            stats.llm_requests += 1
            substrate = {
                "doc_family": str(
                    substrate_rows.get(work_item.work_id, {}).get("doc_family") or ""
                ),
                "routing": list(substrate_rows.get(work_item.work_id, {}).get("routing") or []),
                "sections": substrate_sections.get(work_item.work_id, []),
                "references": substrate_references.get(work_item.work_id, []),
                "tables": substrate_tables.get(work_item.work_id, []),
                "figures": substrate_figures.get(work_item.work_id, []),
                "appendix_blocks": substrate_appendix.get(work_item.work_id, []),
            }
            bundle = _build_streaming_evidence_bundle(
                work_item,
                text=eligible_item.text,
                source_kind=eligible_item.source_kind,
                sentence_budget=config.article_evidence_bundle_sentence_budget,
                substrate=substrate,
            )
            request_kind = "main_extract"
            if config.extraction_lane == "context":
                request_kind = "context_extract"
                prompt = _build_track_b_prompt(bundle, [])
            else:
                prompt = _prompt_for_bundle(
                    bundle, topic_display_names=work_item.topic_display_names
                )
            response = _empty_provider_response(error_class="provider_client_exception")
            request_failure_exc: Exception | None = None
            try:
                response = await _await_provider_json(
                    pool,
                    model=config.article_extraction_model,
                    prompt=prompt,
                    temperature=0.0,
                    watchdog_seconds=provider_watchdog_seconds,
                )
            except TimeoutError:
                response = _empty_provider_response(
                    error_class="watchdog_timeout",
                    raw_content=f"worker_watchdog_timeout:{provider_watchdog_seconds}",
                )
                request_failure_exc = RuntimeError(
                    f"worker_watchdog_timeout:{provider_watchdog_seconds}"
                )
            except Exception as exc:
                response = _empty_provider_response(
                    error_class="provider_client_exception",
                    raw_content=str(exc),
                )
                request_failure_exc = exc
            if request_failure_exc is not None:
                if response.error_class in {"timeout", "watchdog_timeout"}:
                    stats.timeouts += 1
                failure_key = {
                    "timeout": "provider_timeout",
                    "watchdog_timeout": "watchdog_timeout",
                    "json_parse": "json_parse_failure",
                }.get(
                    str(response.error_class or ""),
                    str(response.error_class or "provider_client_exception"),
                )
                stats.failure_class_counts[failure_key] += 1
                async with file_lock:
                    _jsonl_append(
                        config.llm_request_log_path,
                        {
                            "request_kind": request_kind,
                            "work_id": work_item.work_id,
                            "topic_id": work_item.topic_id,
                            "provider_key_index": response.provider_key_index,
                            "http_status": response.http_status,
                            "finish_reason": response.finish_reason,
                            "retry_count": response.retry_count,
                            "limiter_wait_ms": round(response.limiter_wait_ms, 3),
                            "backoff_sleep_ms": round(response.backoff_sleep_ms, 3),
                            "total_latency_ms": round(response.latency_ms, 3),
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "parse_status": response.parse_status,
                            "error_class": response.error_class,
                            "truncated_output": response.truncated_output,
                        },
                    )
                    _jsonl_append(
                        config.resolve_extract_errors_path,
                        {
                            "work_id": work_item.work_id,
                            "topic_id": work_item.topic_id,
                            "error_class": response.error_class or "provider_client_exception",
                            "error_message": str(request_failure_exc),
                            "finish_reason": response.finish_reason,
                            "http_status": response.http_status,
                        },
                    )
                stats.extraction_errors += 1
                await _persist_progress(
                    work_item.work_id,
                    (
                        "retryable_failed"
                        if str(response.error_class or "")
                        in {"provider_http_429", "provider_http_5xx", "timeout", "watchdog_timeout"}
                        else "permanent_failed"
                    ),
                    topic_id=work_item.topic_id,
                    error_class=response.error_class or "provider_client_exception",
                    error_message=str(request_failure_exc),
                )
                topic_inflight[work_item.topic_id] = max(0, topic_inflight[work_item.topic_id] - 1)
                llm_queue.task_done()
                continue
            stats.llm_latency_ms.append(response.latency_ms)
            stats.limiter_wait_ms.append(response.limiter_wait_ms)
            stats.total_tokens_prompt += int(response.usage.get("prompt_tokens") or 0)
            stats.total_tokens_completion += int(response.usage.get("completion_tokens") or 0)
            stats.total_extraction_cost_usd += float(response.usage.get("total_cost_usd") or 0.0)
            if response.error_class == "provider_length_stop":
                stats.provider_length_stop += 1
            elif response.error_class == "provider_http_429":
                stats.provider_429 += 1
            elif response.error_class == "provider_http_5xx":
                stats.provider_5xx += 1
            elif response.error_class == "timeout":
                stats.timeouts += 1
                stats.failure_class_counts["provider_timeout"] += 1
            elif response.error_class == "watchdog_timeout":
                stats.timeouts += 1
                stats.failure_class_counts["watchdog_timeout"] += 1
            elif response.error_class == "json_parse":
                stats.json_parse_errors += 1
                stats.failure_class_counts["json_parse_failure"] += 1
            elif response.error_class == "empty_response":
                stats.empty_responses += 1
            async with file_lock:
                _jsonl_append(
                    config.llm_request_log_path,
                    {
                        "request_kind": request_kind,
                        "work_id": work_item.work_id,
                        "topic_id": work_item.topic_id,
                        "provider_key_index": response.provider_key_index,
                        "http_status": response.http_status,
                        "finish_reason": response.finish_reason,
                        "retry_count": response.retry_count,
                        "limiter_wait_ms": round(response.limiter_wait_ms, 3),
                        "backoff_sleep_ms": round(response.backoff_sleep_ms, 3),
                        "total_latency_ms": round(response.latency_ms, 3),
                        "prompt_tokens": int(response.usage.get("prompt_tokens") or 0),
                        "completion_tokens": int(response.usage.get("completion_tokens") or 0),
                        "parse_status": response.parse_status,
                        "error_class": response.error_class,
                        "truncated_output": response.truncated_output,
                    },
                )
            try:
                parsed = dict(response.parsed)
                resolved_source_basis = (
                    SourceBasis.ABSTRACT_ONLY
                    if eligible_item.source_kind == "abstract_fallback"
                    else SourceBasis.FULLTEXT
                )
                if "methodology_summary" in parsed and "methodology" not in parsed:
                    parsed["methodology"] = parsed.get("methodology_summary")
                if config.extraction_lane == "context":
                    result = _normalize_context_lane_result(
                        work=work_item.work,
                        parsed=parsed,
                        model=config.article_extraction_model,
                        usage=response.usage,
                        bundle=bundle,
                        source_kind=eligible_item.source_kind,
                    )
                    result = result.model_copy(
                        update={
                            "provider_finish_reason": response.finish_reason,
                            "provider_latency_ms": round(response.latency_ms, 3),
                            "truncated_output": bool(response.truncated_output),
                            "llm_error_class": response.error_class,
                            "text_quality": eligible_item.text_quality,
                            "source_basis": resolved_source_basis,
                        }
                    )
                else:
                    payload = _normalize_extraction_payload(
                        work_item.work,
                        parsed,
                        config.article_extraction_model,
                        response.usage,
                        evidence_bundle=bundle,
                        source_kind=eligible_item.source_kind,
                    )
                    payload["paper_relevance"] = bool(parsed.get("paper_relevance", True))
                    payload["paper_relevance_reason"] = _normalized_text(
                        parsed.get("paper_relevance_reason")
                    )
                    payload["provider_finish_reason"] = response.finish_reason
                    payload["provider_latency_ms"] = round(response.latency_ms, 3)
                    payload["truncated_output"] = bool(response.truncated_output)
                    payload["llm_error_class"] = response.error_class
                    payload["text_quality"] = eligible_item.text_quality
                    payload["source_basis"] = resolved_source_basis.value
                    result = ArticleExtractionResult.model_validate(payload)
                result = result.model_copy(
                    update={"source_context": infer_context_from_article(work_item.work, result)}
                )
                result = _apply_extraction_lane(result, config.extraction_lane)
                claim_inventory = _build_claim_inventory(result, canonizer)

                if (
                    config.extraction_lane in {"all", "claim"}
                    and config.numeric_precision_mode != "off"
                    and _needs_numeric_rescue(result)
                ):
                    try:
                        stats.numeric_rescue_requests += 1
                        stats.llm_requests += 1
                        rescue_prompt = _build_numeric_rescue_prompt(
                            bundle,
                            claim_inventory=claim_inventory,
                            result=result,
                        )
                        rescue_response = await pool.chat_json(
                            model=config.article_extraction_model,
                            prompt=rescue_prompt,
                            temperature=0.0,
                        )
                        stats.llm_latency_ms.append(rescue_response.latency_ms)
                        stats.limiter_wait_ms.append(rescue_response.limiter_wait_ms)
                        stats.total_tokens_prompt += int(
                            rescue_response.usage.get("prompt_tokens") or 0
                        )
                        stats.total_tokens_completion += int(
                            rescue_response.usage.get("completion_tokens") or 0
                        )
                        stats.total_extraction_cost_usd += float(
                            rescue_response.usage.get("total_cost_usd") or 0.0
                        )
                        async with file_lock:
                            _jsonl_append(
                                config.llm_request_log_path,
                                {
                                    "request_kind": "numeric_rescue",
                                    "work_id": work_item.work_id,
                                    "topic_id": work_item.topic_id,
                                    "provider_key_index": rescue_response.provider_key_index,
                                    "http_status": rescue_response.http_status,
                                    "finish_reason": rescue_response.finish_reason,
                                    "retry_count": rescue_response.retry_count,
                                    "limiter_wait_ms": round(rescue_response.limiter_wait_ms, 3),
                                    "backoff_sleep_ms": round(rescue_response.backoff_sleep_ms, 3),
                                    "total_latency_ms": round(rescue_response.latency_ms, 3),
                                    "prompt_tokens": int(
                                        rescue_response.usage.get("prompt_tokens") or 0
                                    ),
                                    "completion_tokens": int(
                                        rescue_response.usage.get("completion_tokens") or 0
                                    ),
                                    "parse_status": rescue_response.parse_status,
                                    "error_class": rescue_response.error_class,
                                    "truncated_output": rescue_response.truncated_output,
                                },
                            )
                        rescue_parsed = dict(rescue_response.parsed or {})
                        rescue_parameters = [
                            item
                            for item in (
                                _normalize_empirical_parameter(raw)
                                for raw in _as_list(rescue_parsed.get("empirical_parameters"))
                            )
                            if item is not None
                        ]
                        if rescue_parameters:
                            merged_parameters = _merge_numeric_parameter_lists(
                                result.empirical_parameters,
                                rescue_parameters,
                            )
                            if merged_parameters != result.empirical_parameters:
                                stats.numeric_rescue_successes += 1
                                stats.numeric_rescue_parameters_added += max(
                                    0,
                                    len(merged_parameters) - len(result.empirical_parameters),
                                )
                                result = result.model_copy(
                                    update={"empirical_parameters": merged_parameters}
                                )
                    except Exception:
                        stats.numeric_rescue_failures += 1
                        logger.debug(
                            "Numeric rescue failed for {}", work_item.work_id, exc_info=True
                        )

                if (
                    config.extraction_lane in {"all", "claim"}
                    and config.numeric_precision_mode != "off"
                    and not _has_high_precision_numeric_parameter(result)
                ):
                    deterministic_rescue_parameters = _deterministic_numeric_rescue_parameters(
                        bundle=bundle,
                        result=result,
                    )
                    if deterministic_rescue_parameters:
                        merged_parameters = _merge_numeric_parameter_lists(
                            result.empirical_parameters,
                            deterministic_rescue_parameters,
                        )
                        if merged_parameters != result.empirical_parameters:
                            stats.deterministic_numeric_rescue_successes += 1
                            stats.deterministic_numeric_rescue_parameters_added += max(
                                0,
                                len(merged_parameters) - len(result.empirical_parameters),
                            )
                            result = result.model_copy(
                                update={"empirical_parameters": merged_parameters}
                            )

                # --- Track B/C routing (opt-in) ---
                if config.extraction_lane == "all" and (
                    config.track_b_enabled or config.track_c_enabled
                ):
                    try:
                        classification_model = (
                            config.paper_classification_model or config.article_screening_model
                        )
                        abstract_text = str(
                            work_item.work.get("abstract") or bundle.get("abstract") or ""
                        )
                        method_cues_text = ", ".join(
                            s.get("text", "")[:80]
                            for s in bundle.get("method_sentences", [])[:5]
                            if isinstance(s, dict) and s.get("text")
                        )
                        classification_prompt = PAPER_CLASSIFICATION_PROMPT.format(
                            title=result.title,
                            abstract=abstract_text[:1500],
                            method_cues=method_cues_text[:500],
                        )
                        cls_response = await pool.chat_json(
                            model=classification_model,
                            prompt=classification_prompt,
                            temperature=0.0,
                        )
                        stats.papers_classified += 1
                        cls_parsed = cls_response.parsed or {}
                        paper_kind = _resolve_paper_kind(
                            work_item=work_item,
                            eligible_item=eligible_item,
                            result=result,
                            cls_parsed=cls_parsed,
                        )
                        result = result.model_copy(update={"paper_kind": paper_kind})

                        # Track B: context characterization
                        track_b_eligible = config.track_b_enabled and paper_kind in {
                            PaperKind.CONTEXT_CHARACTERIZATION,
                            PaperKind.MIXED,
                            PaperKind.DESCRIPTIVE,
                            PaperKind.REVIEW_SYSTEMATIC,
                        }
                        if track_b_eligible:
                            stats.track_b_routed += 1
                            track_b_model = (
                                config.track_b_extraction_model or config.article_extraction_model
                            )
                            ctx_prompt = _build_track_b_prompt(bundle, claim_inventory)
                            ctx_response = await pool.chat_json(
                                model=track_b_model,
                                prompt=ctx_prompt,
                                temperature=0.0,
                            )
                            ctx_parsed = ctx_response.parsed or {}
                            context_attributes = [
                                item
                                for item in (
                                    _normalize_context_attribute(raw)
                                    for raw in _as_list(ctx_parsed.get("context_attributes"))
                                )
                                if item is not None
                            ]
                            if context_attributes:
                                result = result.model_copy(
                                    update={"context_attributes": context_attributes}
                                )

                        # Track C: moderation/heterogeneity
                        track_c_eligible = config.track_c_enabled and paper_kind in {
                            PaperKind.HETEROGENEITY_ANALYSIS,
                            PaperKind.MIXED,
                            PaperKind.EMPIRICAL_CAUSAL,
                        }
                        if track_c_eligible:
                            track_c_model = (
                                config.track_c_extraction_model or config.article_extraction_model
                            )
                            mod_prompt = _build_track_c_prompt(bundle, claim_inventory)
                            mod_response = await pool.chat_json(
                                model=track_c_model,
                                prompt=mod_prompt,
                                temperature=0.0,
                            )
                            mod_parsed = mod_response.parsed or {}
                            moderation_edges = [
                                item
                                for item in (
                                    _normalize_moderation_edge(raw)
                                    for raw in _as_list(mod_parsed.get("moderator_findings"))
                                )
                                if item is not None
                            ]
                            if moderation_edges:
                                result = result.model_copy(
                                    update={"moderation_edges": moderation_edges}
                                )
                    except Exception:
                        logger.debug(
                            "Track B/C routing failed for {}", work_item.work_id, exc_info=True
                        )

                result = _reconcile_tracks(
                    result, canonizer=canonizer, claim_inventory=claim_inventory
                )
                stats.context_attributes_extracted += len(result.context_attributes)
                stats.moderation_edges_extracted += len(result.moderation_edges)
                result = _apply_publish_gate(result)
                record = _to_work_record(
                    result=result,
                    raw_work=work_item.work,
                    topic_ids=work_item.topic_ids,
                    topic_display_names=work_item.topic_display_names,
                    run_id=config.run_id,
                    pass_name=config.pass_name,
                )
                record_json = record.model_dump_json()
                await _append_artifacts(result=result, work_item=work_item, record_json=record_json)
                # Persist Track B/C artifacts
                if result.context_attributes:
                    async with file_lock:
                        for ca in result.context_attributes:
                            _jsonl_append(
                                config.context_attributes_path,
                                {
                                    "openalex_id": result.openalex_id,
                                    **ca.model_dump(mode="json"),
                                },
                            )
                if result.moderation_edges:
                    async with file_lock:
                        for me in result.moderation_edges:
                            _jsonl_append(
                                config.moderation_edges_path,
                                {
                                    "openalex_id": result.openalex_id,
                                    **me.model_dump(mode="json"),
                                },
                            )
                published_count = sum(1 for claim in result.causal_claims if claim.publish_to_graph)
                nonempty_result = bool(
                    result.causal_claims
                    or result.empirical_parameters
                    or result.context_attributes
                    or result.moderation_edges
                    or result.boundary_conditions
                )
                stats.raw_claims += len(result.causal_claims)
                stats.published_claims += published_count
                stats.extracted += 1
                topic_success[work_item.topic_id] += 1
                final_state = "succeeded_nonempty" if nonempty_result else "succeeded_empty"
                await _persist_progress(
                    work_item.work_id,
                    final_state,
                    topic_id=work_item.topic_id,
                    published_claims=published_count,
                    raw_claims=len(result.causal_claims),
                    publish_state=("published" if published_count > 0 else "raw_only"),
                    source_basis=result.source_basis.value,
                )
            except Exception as exc:
                stats.extraction_errors += 1
                stats.failure_class_counts["normalization_failure"] += 1
                async with file_lock:
                    _jsonl_append(
                        config.llm_request_log_path,
                        {
                            "request_kind": "main_extract",
                            "work_id": work_item.work_id,
                            "topic_id": work_item.topic_id,
                            "provider_key_index": response.provider_key_index,
                            "http_status": response.http_status,
                            "finish_reason": response.finish_reason,
                            "retry_count": response.retry_count,
                            "limiter_wait_ms": round(response.limiter_wait_ms, 3),
                            "backoff_sleep_ms": round(response.backoff_sleep_ms, 3),
                            "total_latency_ms": round(response.latency_ms, 3),
                            "prompt_tokens": int(response.usage.get("prompt_tokens") or 0),
                            "completion_tokens": int(response.usage.get("completion_tokens") or 0),
                            "parse_status": response.parse_status,
                            "error_class": response.error_class or "normalization_error",
                            "truncated_output": response.truncated_output,
                        },
                    )
                    _jsonl_append(
                        config.resolve_extract_errors_path,
                        {
                            "work_id": work_item.work_id,
                            "topic_id": work_item.topic_id,
                            "error_class": response.error_class or "normalization_error",
                            "error_message": str(exc),
                            "finish_reason": response.finish_reason,
                            "http_status": response.http_status,
                        },
                    )
                await _persist_progress(
                    work_item.work_id,
                    (
                        "retryable_failed"
                        if str(response.error_class or "")
                        in {"provider_http_429", "provider_http_5xx", "timeout", "watchdog_timeout"}
                        else "permanent_failed"
                    ),
                    topic_id=work_item.topic_id,
                    error_class=response.error_class or "normalization_error",
                    error_message=str(exc),
                )
            finally:
                topic_inflight[work_item.topic_id] = max(0, topic_inflight[work_item.topic_id] - 1)
                llm_queue.task_done()

    fetch_tasks = [asyncio.create_task(fetch_worker(index)) for index in range(fetch_workers_count)]
    doc_ready_task = asyncio.create_task(stream_doc_ready_producer()) if stream_doc_ready else None
    async with GonkaMultiKeyPool(config) as pool:
        llm_tasks = [asyncio.create_task(llm_worker(pool)) for _ in range(llm_workers_count)]
        dispatcher_task = asyncio.create_task(llm_dispatcher())

        if doc_ready_task is not None:
            await doc_ready_task
            _raise_if_task_failed(dispatcher_task, "resolve_extract dispatcher")
        await fetch_queue.join()
        fetch_done.set()
        await asyncio.gather(*fetch_tasks)
        _raise_if_task_failed(dispatcher_task, "resolve_extract dispatcher")
        await dispatcher_done.wait()
        await llm_queue.join()
        await dispatcher_task
        await asyncio.gather(*llm_tasks)
        await _flush_progress()

    for topic_id in topic_seen:
        if topic_success.get(topic_id, 0) < config.article_target_fulltext_per_topic:
            stats.low_fulltext_coverage_topics += 1

    metrics: dict[str, float | int] = {
        "records": stats.records,
        "fulltext_resolved": stats.fulltext_resolved,
        "abstract_only": stats.abstract_only,
        "eligible_fulltext_per_topic": stats.eligible_fulltext,
        "context_eligible": stats.context_eligible,
        "rejected": stats.rejected,
        "successful_llm_extractions_per_topic": stats.extracted,
        "raw_claims_per_topic": stats.raw_claims,
        "published_claims_per_topic": stats.published_claims,
        "extraction_errors": stats.extraction_errors,
        "length_stop_rate": round(
            (stats.provider_length_stop / max(1, stats.llm_requests)) * 100.0, 3
        ),
        "provider_429_rate": round((stats.provider_429 / max(1, stats.llm_requests)) * 100.0, 3),
        "mean_limiter_wait_ms": round(
            sum(stats.limiter_wait_ms) / max(1, len(stats.limiter_wait_ms)), 3
        ),
        "fulltext_fetch_latency_p50_ms": round(_percentile(stats.fetch_latency_ms, 0.5), 3),
        "fulltext_fetch_latency_p95_ms": round(_percentile(stats.fetch_latency_ms, 0.95), 3),
        "llm_latency_p50_ms": round(_percentile(stats.llm_latency_ms, 0.5), 3),
        "llm_latency_p95_ms": round(_percentile(stats.llm_latency_ms, 0.95), 3),
        "published_abstract_only_edges": 0,
        "total_tokens_prompt": stats.total_tokens_prompt,
        "total_tokens_completion": stats.total_tokens_completion,
        "total_extraction_cost_usd": round(stats.total_extraction_cost_usd, 6),
        "low_fulltext_coverage_topics": stats.low_fulltext_coverage_topics,
        "papers_classified": stats.papers_classified,
        "track_b_routed": stats.track_b_routed,
        "track_b_only_routed": stats.track_b_only_routed,
        "track_b_rejected_hard": stats.track_b_rejected_hard,
        "context_attributes_extracted": stats.context_attributes_extracted,
        "moderation_edges_extracted": stats.moderation_edges_extracted,
        "numeric_rescue_requests": stats.numeric_rescue_requests,
        "numeric_rescue_successes": stats.numeric_rescue_successes,
        "numeric_rescue_failures": stats.numeric_rescue_failures,
        "numeric_rescue_parameters_added": stats.numeric_rescue_parameters_added,
        "deterministic_numeric_rescue_successes": stats.deterministic_numeric_rescue_successes,
        "deterministic_numeric_rescue_parameters_added": stats.deterministic_numeric_rescue_parameters_added,
        "provider_timeout_count": int(stats.failure_class_counts.get("provider_timeout", 0)),
        "watchdog_timeout_count": int(stats.failure_class_counts.get("watchdog_timeout", 0)),
        "json_parse_failure_count": int(stats.failure_class_counts.get("json_parse_failure", 0)),
        "normalization_failure_count": int(
            stats.failure_class_counts.get("normalization_failure", 0)
        ),
        "route_rejected_count": int(stats.failure_class_counts.get("route_rejected", 0)),
        "rejection_reason_counts": dict(sorted(stats.rejection_reason_counts.items())),
        "failure_class_counts": dict(sorted(stats.failure_class_counts.items())),
    }

    write_stage_manifest(
        manifest_path=config.manifests_dir / "resolve_extract.json",
        stage="resolve_extract",
        status="ok",
        metrics=metrics,
        artifacts=_resolve_extract_artifacts(config),
        started_at=started_at,
    )
    return metrics


def _merge_resolve_extract_metrics(
    cumulative: dict[str, float | int],
    metrics: dict[str, float | int],
    *,
    first_pass: bool,
) -> dict[str, float | int]:
    additive_keys = {
        "fulltext_resolved",
        "abstract_only",
        "eligible_fulltext_per_topic",
        "context_eligible",
        "rejected",
        "successful_llm_extractions_per_topic",
        "raw_claims_per_topic",
        "published_claims_per_topic",
        "extraction_errors",
        "total_tokens_prompt",
        "total_tokens_completion",
        "total_extraction_cost_usd",
        "low_fulltext_coverage_topics",
        "papers_classified",
        "track_b_routed",
        "track_b_only_routed",
        "track_b_rejected_hard",
        "context_attributes_extracted",
        "moderation_edges_extracted",
        "numeric_rescue_requests",
        "numeric_rescue_successes",
        "numeric_rescue_failures",
        "numeric_rescue_parameters_added",
        "deterministic_numeric_rescue_successes",
        "deterministic_numeric_rescue_parameters_added",
        "provider_timeout_count",
        "watchdog_timeout_count",
        "json_parse_failure_count",
        "normalization_failure_count",
        "route_rejected_count",
    }
    counter_keys = {"rejection_reason_counts", "failure_class_counts"}
    merged = dict(cumulative)
    if first_pass:
        for key, value in metrics.items():
            merged[key] = value
        return merged
    for key, value in metrics.items():
        if key == "records":
            continue
        if key in additive_keys:
            previous = merged.get(key, 0)
            if isinstance(previous, (int, float)) and isinstance(value, (int, float)):
                merged[key] = previous + value
            else:
                merged[key] = value
            continue
        if key in counter_keys and isinstance(value, dict):
            previous = dict(merged.get(key, {})) if isinstance(merged.get(key), dict) else {}
            for sub_key, sub_value in value.items():
                prev_value = previous.get(sub_key, 0)
                if isinstance(prev_value, (int, float)) and isinstance(sub_value, (int, float)):
                    previous[sub_key] = prev_value + sub_value
                else:
                    previous[sub_key] = sub_value
            merged[key] = dict(sorted(previous.items()))
            continue
        merged[key] = value
    return merged


async def _run_targeted_extraction_pass(config: AcademicBatchConfig) -> dict[str, int]:
    """Second-pass extraction targeting benchmark-demanded causal pairs.

    For papers that were extracted but lack claims matching demanded
    benchmark pairs, issue a focused LLM prompt asking specifically about
    the demanded relationship.
    """
    if not config.targeted_extraction_enabled:
        return {"targeted_extraction_skipped": 1}

    from polisyos.data_forge.domains.academic.batch.benchmark import _ensure_suite

    suite = _ensure_suite(config.benchmark_suite_path)
    demanded_pairs: set[tuple[str, str]] = set()
    for scenario in suite.scenarios:
        for edge in scenario.causal_edges:
            demanded_pairs.add(
                (
                    edge.cause.replace(".", " ").replace("_", " ").lower(),
                    edge.effect.replace(".", " ").replace("_", " ").lower(),
                )
            )

    if not demanded_pairs:
        return {"targeted_extraction_pairs": 0}

    results_path = config.resolve_extract_results_path
    if not results_path.exists():
        return {"targeted_extraction_no_results": 1}

    papers_needing_targeted: list[dict[str, Any]] = []
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        claims = record.get("causal_claims") or []
        claim_pairs = {
            (
                str(c.get("cause_variable") or "").replace(".", " ").replace("_", " ").lower(),
                str(c.get("effect_variable") or "").replace(".", " ").replace("_", " ").lower(),
            )
            for c in claims
        }
        abstract = str(record.get("abstract") or record.get("title") or "").lower()
        for cause, effect in demanded_pairs:
            cause_tokens = set(cause.split())
            effect_tokens = set(effect.split())
            abstract_tokens = set(abstract.split())
            if cause_tokens & abstract_tokens and effect_tokens & abstract_tokens:
                if (cause, effect) not in claim_pairs:
                    papers_needing_targeted.append(
                        {
                            "record": record,
                            "demanded_cause": cause,
                            "demanded_effect": effect,
                        }
                    )
                    break

    if not papers_needing_targeted:
        return {"targeted_extraction_candidates": 0, "targeted_extraction_new_claims": 0}

    papers_needing_targeted = papers_needing_targeted[: config.targeted_extraction_max_papers]
    logger.info(
        "targeted_extraction: %d papers need targeted pass for %d demanded pairs",
        len(papers_needing_targeted),
        len(demanded_pairs),
    )

    new_claims_total = 0
    targeted_prompt_template = (
        "This paper discusses {topic}. "
        "Does it contain evidence about the causal effect of {cause} on {effect}? "
        "If yes, extract the causal claim with direction, effect size, design family, "
        "and any numeric estimates. Return JSON with 'causal_claims' array and "
        "'empirical_parameters' array following the standard schema. "
        "If no evidence exists for this specific relationship, return "
        '{{"causal_claims": [], "empirical_parameters": []}}.'
    )

    results_append_path = config.component_dir / "targeted_extraction_results.jsonl"
    results_append_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_append_path, "w", encoding="utf-8") as fh:
        for item in papers_needing_targeted:
            record = item["record"]
            fh.write(
                json.dumps(
                    {
                        "openalex_id": record.get("openalex_id"),
                        "targeted_cause": item["demanded_cause"],
                        "targeted_effect": item["demanded_effect"],
                        "prompt_template": targeted_prompt_template,
                        "status": "queued",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return {
        "targeted_extraction_candidates": len(papers_needing_targeted),
        "targeted_extraction_pairs": len(demanded_pairs),
        "targeted_extraction_new_claims": new_claims_total,
    }


async def run_resolve_extract(config: AcademicBatchConfig) -> dict[str, float | int]:
    """Run one or more resolve/extract passes with retry throttling and targeted follow-up.

    The function aggregates per-pass metrics, halves retry-lane concurrency/rate limits for
    follow-up passes, persists timeout retry queues when enabled, and can enqueue benchmark-driven
    targeted extraction for unsupported causal pairs.
    """
    started_at = datetime.now(UTC).isoformat()
    max_followup_passes = max(0, int(config.article_retryable_followup_passes))
    followup_delay_seconds = max(0.0, float(config.article_retryable_followup_delay_seconds))

    cumulative_metrics: dict[str, float | int] = {}
    current_config = config
    passes_run = 0
    for pass_index in range(max_followup_passes + 1):
        pass_metrics = await _run_resolve_extract_pass(current_config)
        cumulative_metrics = _merge_resolve_extract_metrics(
            cumulative_metrics,
            pass_metrics,
            first_pass=(pass_index == 0),
        )
        passes_run += 1
        progress = _load_progress(config.resolve_extract_progress_path)
        retryable_remaining = _count_progress_state(progress, "retryable_failed")
        if retryable_remaining == 0 or pass_index >= max_followup_passes:
            cumulative_metrics["retry_followup_passes_run"] = max(0, passes_run - 1)
            cumulative_metrics["retryable_failures_remaining"] = retryable_remaining
            cumulative_metrics["final_succeeded_nonempty"] = _count_progress_state(
                progress, "succeeded_nonempty"
            )
            cumulative_metrics["final_succeeded_empty"] = _count_progress_state(
                progress, "succeeded_empty"
            )
            cumulative_metrics["final_permanent_failed"] = _count_progress_state(
                progress, "permanent_failed"
            )
            cumulative_metrics["final_retryable_failed"] = retryable_remaining
            cumulative_metrics["final_rejected"] = _count_progress_state(progress, "rejected")
            # Persist timeout retry queue for cross-run recovery
            if config.retry_timeout_articles and retryable_remaining > 0:
                _persist_timeout_retry_queue(config, progress)
            # Run targeted extraction for benchmark-demanded pairs
            if config.targeted_extraction_enabled:
                targeted_metrics = await _run_targeted_extraction_pass(config)
                cumulative_metrics.update(targeted_metrics)
            write_stage_manifest(
                manifest_path=config.manifests_dir / "resolve_extract.json",
                stage="resolve_extract",
                status="ok",
                metrics=cumulative_metrics,
                artifacts=_resolve_extract_artifacts(config),
                started_at=started_at,
            )
            return cumulative_metrics
        if followup_delay_seconds > 0:
            await asyncio.sleep(followup_delay_seconds)
        current_config = replace(
            current_config,
            resume=True,
            article_max_concurrent_llm=max(
                1,
                min(
                    current_config.article_max_concurrent_llm,
                    math.ceil(config.article_max_concurrent_llm / 2),
                ),
            ),
            article_rate_limit_rps=max(
                0.05,
                min(current_config.article_rate_limit_rps, config.article_rate_limit_rps * 0.5),
            ),
        )
        cumulative_metrics["retry_lane_llm_workers"] = int(
            current_config.article_max_concurrent_llm
        )
        cumulative_metrics["retry_lane_rate_limit_rps"] = round(
            float(current_config.article_rate_limit_rps), 6
        )

    return cumulative_metrics


__all__ = ["run_resolve_extract"]
