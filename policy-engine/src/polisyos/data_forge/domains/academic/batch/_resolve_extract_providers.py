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
