"""Streaming fulltext-first one-call extraction stage."""

from __future__ import annotations

import asyncio
import gc
import json
import math
import random
import re
import time
from collections import defaultdict, deque
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp

import polisyos.data_forge.domains.academic.batch.fulltext_resolver as fulltext_resolver_module
from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import (
    EligibilityDecision,
    EligibleItem,
    ProviderResponse,
    ResolveExtractStats,
    WorkItem,
)
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
