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
    EvidenceStrengthOrigin,
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
                    },
                    strength_origin=EvidenceStrengthOrigin.INHERITED,
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
                "evidence_strength_origin": (
                    EvidenceStrengthOrigin.INHERITED
                    if keep.evidence_strength == EvidenceStrength.UNKNOWN
                    and enrich.evidence_strength != EvidenceStrength.UNKNOWN
                    else keep.evidence_strength_origin
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
