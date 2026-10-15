"""Streaming fulltext-first one-call extraction stage."""

from __future__ import annotations

import gc as gc
import json
import math
import random as random
import re
import time as time
from collections import defaultdict
from collections import deque as deque
from dataclasses import replace as replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import aiohttp as aiohttp

from polisyos.common import serialization as common_serialization
from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import (
    EligibilityDecision as EligibilityDecision,
)
from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import (
    ProviderResponse as ProviderResponse,
)
from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import (
    ResolveExtractStats as ResolveExtractStats,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _CLAIM_SENTENCE_RE,
    _METHOD_SENTENCE_RE,
    _RESULT_SENTENCE_RE,
    _normalized_text,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _as_list as _as_list,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _build_evidence_bundle as _build_evidence_bundle,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _normalize_context_attribute as _normalize_context_attribute,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _normalize_empirical_parameter as _normalize_empirical_parameter,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _normalize_extraction_payload as _normalize_extraction_payload,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _normalize_moderation_edge as _normalize_moderation_edge,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _parse_json_object as _parse_json_object,
)
from polisyos.data_forge.domains.academic.batch.article_extractor import (
    _to_work_record as _to_work_record,
)
from polisyos.data_forge.domains.academic.batch.claim_ids import (
    stable_claim_id as stable_claim_id,
)
from polisyos.data_forge.domains.academic.batch.context_classifier import (
    infer_context_from_article as infer_context_from_article,
)
from polisyos.data_forge.domains.academic.batch.fulltext_resolver import (
    FullTextFetchResult as FullTextFetchResult,
)
from polisyos.data_forge.domains.academic.batch.fulltext_resolver import (
    fetch_full_text_for_work as fetch_full_text_for_work,
)
from polisyos.data_forge.domains.academic.batch.fulltext_resolver import (
    fetch_full_text_result_for_work as fetch_full_text_result_for_work,
)
from polisyos.data_forge.domains.academic.batch.fulltext_resolver import (
    reconstruct_abstract,
)
from polisyos.data_forge.domains.academic.batch.parser import (
    extract_numerical_estimates as extract_numerical_estimates,
)
from polisyos.data_forge.domains.academic.batch.prompts import (
    CONTEXT_EXTRACTION_SCHEMA_HINT as CONTEXT_EXTRACTION_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts import (
    MODERATOR_EXTRACTION_SCHEMA_HINT as MODERATOR_EXTRACTION_SCHEMA_HINT,
)
from polisyos.data_forge.domains.academic.batch.prompts import (
    PAPER_CLASSIFICATION_PROMPT as PAPER_CLASSIFICATION_PROMPT,
)
from polisyos.data_forge.domains.academic.knowledge.variable_canonizer import (
    VariableCanonizer as VariableCanonizer,
)
from polisyos.data_forge.domains.academic.openalex.priority_filter import should_process
from polisyos.data_forge.kernel.pipeline.manifests import (
    write_stage_manifest as write_stage_manifest,
)
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    DesignFamily,
    PaperKind,
)
from polisyos.ir.analytics.literature import (
    CausalClaim as CausalClaim,
)
from polisyos.ir.analytics.literature import (
    ClaimType as ClaimType,
)
from polisyos.ir.analytics.literature import (
    ContextAttribute as ContextAttribute,
)
from polisyos.ir.analytics.literature import (
    EvidenceParameter as EvidenceParameter,
)
from polisyos.ir.analytics.literature import (
    EvidenceSpan as EvidenceSpan,
)
from polisyos.ir.analytics.literature import (
    EvidenceStrength as EvidenceStrength,
)
from polisyos.ir.analytics.literature import (
    HeterogeneityResult as HeterogeneityResult,
)
from polisyos.ir.analytics.literature import (
    ModerationEdge as ModerationEdge,
)
from polisyos.ir.analytics.literature import (
    ParameterType as ParameterType,
)
from polisyos.ir.analytics.literature import (
    SourceBasis as SourceBasis,
)
from polisyos.ir.analytics.literature import (
    TextQuality as TextQuality,
)

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Iterator
    from pathlib import Path

    from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import (
        EligibleItem,
        WorkItem,
    )
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
        r"\b(instrumental variable|instrument\w*|2sls|tsls|first stage)\b",
        re.IGNORECASE,
    ),
    DesignFamily.DID.value: re.compile(
        r"\b(difference[- ]?in[- ]?differences?|\bdid\b|parallel trends)\b",
        re.IGNORECASE,
    ),
    DesignFamily.RDD.value: re.compile(
        r"\b(regression discontinuity|\brdd\b|cutoff|threshold design)\b", re.IGNORECASE
    ),
    DesignFamily.SYNTHETIC_CONTROL.value: re.compile(
        r"\b(synthetic control|synthetic counterfactual)\b", re.IGNORECASE
    ),
    DesignFamily.EVENT_STUDY.value: re.compile(
        r"\b(event study|dynamic treatment effects|lead[s]? and lag[s]?)\b",
        re.IGNORECASE,
    ),
    DesignFamily.QUASI_EXPERIMENTAL_OTHER.value: re.compile(
        (
            "\\b(natural experiment|quasi[- ]experimental|exogenous shock|policy d"
            "iscontinuity|staggered adoption)\\b"
        ),
        re.IGNORECASE,
    ),
}
_DOWNGRADE_PATTERNS = re.compile(
    (
        "\\b(correlation|associat(?:ion|ive)|cross[- ]sectional|ols only|ordinary least s"
        "quares only|panel fixed effects only)\\b"
    ),
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
    (
        "\\b(randomi[sz]ed|random assignment|random lottery|field experiment|audit s"
        "tudy|correspondence study|survey experiment|lab(?:oratory)? e"
        "xperiment|encouragement design|instrumental v"
        "ariable|2sls|tsls|difference.?in.?differences?|did\\b|regression d"
        "iscontinuity|rdd\\b|synthetic control|event study|natural experiment|quasi[- ]"
        "experimental|staggered adoption|staggered rollout|exogenous shock|propensity s"
        "core|matching estimat\\w+|causal forest|bunching design)\\b"
    ),
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
    (
        "\\b(administrative data|registry data|register data|panel data|longitudinal d"
        "ata|survey data|census data|microdata|matched employer[- ]employee|linked d"
        "ata|transaction data|tax records?|firm-level data|household survey|personnel r"
        "ecords?|field experiment|audit study|correspondence study|survey e"
        "xperiment|lab(?:oratory)? experiment|natural experiment|quasi[- ]"
        "experimental|policy reform|staggered adoption|staggered rollout)\\b"
    ),
    re.IGNORECASE,
)
_ACCESS_SHELL_RE = re.compile(
    r"\b(choice reviews\s*\|\s*login|institutional login|access via institution log in|mymuse|"
    r"url has changed to|please update your bookmarks|javascript is disabled for your browser)\b",
    re.IGNORECASE,
)
_CONTEXT_CLASSIFICATION_RE = re.compile(
    (
        "\\b(governance|institutional(?: q"
        "uality)?|institutions?|historical|history|geograph(?:ic|ical)|regional|cross-cou"
        "ntry|across countries|space and time|sustainable development|sdg|policy p"
        "erspective|administrative burden|development finance|context(?:ual)?|country c"
        "omparison)\\b"
    ),
    re.IGNORECASE,
)
_HETEROGENEITY_CLASSIFICATION_RE = re.compile(
    r"\b(heterogeneity|moderat(?:es|ing|or)|interaction|subgroup|conditional on|threshold effect|"
    r"for whom|where effects differ)\b",
    re.IGNORECASE,
)
_RESULT_CUE_RE = re.compile(
    (
        "\\b(we find|results show|effect on|impact o"
        "n|increas\\w*|decreas\\w*|reduc\\w*|rais\\w*|improv\\w*|lead(?:s|ing)? t"
        "o|caus(?:e|es|ed|ing))\\b"
    ),
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
    (
        "\\b(descriptive study|descriptive analysis|cross[- ]sectional non[- ]"
        "analytic|frequency distribution|univariate analysis|bivariate analysis|most r"
        "espondents|mostly good|mostly positive|prevalence|awareness level|knowledge l"
        "evel|attitude level)\\b"
    ),
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
    from polisyos.data_forge.domains.academic.knowledge.canonical_seed import (
        CANONICAL_VARIABLES,
    )
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
    r"(?:^|[_\.])(multiplier|effect|impact|estimate|coefficient)(?:$|[_\.])",
    re.IGNORECASE,
)
_CONTAMINATION_RE = re.compile(
    "(?i)(accesses|citations|altmetric|explore all metrics|download pdf|view p"
    "df|view abstract|cookie policy|accept cookies|cookie preferences|cookie c"
    "onsent|manage cookies|we use cookies|all rights reserved|copyright \\"
    "d{4}|doi\\.org/\\S+|https?://\\S{20,}|research output|journal c"
    "ontributions|prodotti della ricerca|retrieved from https?://\\S+|institutional l"
    "ogin|sign in to access|download citation|export citation|cite this a"
    "rticle|published by ("
    "?:springer|elsevier|wiley|taylor|sage|oxford|cambridge|mdpi|frontiers)|received:"
    "?\\s*\\d{1,2}\\s+\\w+\\s+\\d{4}.*?accepted:?\\s*\\d{1,2}\\s+\\w+\\s+\\d{4}|open a"
    "ccess\\s+this article is licensed|creative commons|supplementary ("
    "?:materials?|information|data|file)|corresponding author|author c"
    "ontributions|funding\\s+(?:information|statement|this (?:work|research|study) w"
    "as)|declaration of (?:competing )?interests?|conflict of interest s"
    "tatement|skip to (?:main content|content|navigation)|find a journal|publish w"
    "ith us|track your research|saved research|search cart|advertisement log in|log i"
    "n menu|aims and scope|submit manuscript|save article|view saved|similar content b"
    "eing viewed by others|related articles?|explore related subjects|discover the l"
    "atest|suggested using machine learning|full size i"
    "mage|volume\\s+\\d+\\s*,?\\s*pages?\\s+\\d+|Published:\\s*\\d{1,2}\\s+\\w+\\s+\\d{4}|p"
    "p\\.\\s*\\d+[–\\-]\\d+|orcid\\.org/\\d{4}|ORCID:\\s*orcid|institutional ("
    "?:subscriptions?|access|repositor(?:y|ies))|subscribe to (?:this )"
    '?journal|@article\\{|issn\\s*=\\s*\\"|publisher\\s*=\\s*\\"|language\\s*=\\s*\\"|TY\\s'
    "+-\\s+JOUR|AU\\s+-\\s+|PY\\s+-\\s+|N2\\s+-\\s+)"
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
  "unit": "percentage_points|percent|log_points|ratio|elasticity|odds_ratio|hazard_ratio|coefficie\
nt|usd|index|...",
  "evidence_strength": \
"rct|quasi_natural|quasi_natural_event|panel_fe|structural|observational|cross_sectional|meta_anal\
ysis|theoretical|unknown",
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
Example: "photosynthesis" → "biological.photosynthesis", "drought_stress" → \
"environmental.drought_stress",
"antibiotic_use" → "antibiotic.use", "soil_ph" → "soil.ph". NEVER output a bare variable without \
a domain prefix.

{canonical_names_block}

Each causal_claim object must use sentence IDs, not verbatim spans:
{
  "claim_text": "short paper-grounded claim",
  "claim_type": \
"causal_claim|associative|mechanism|review_summary|descriptive|normative|unclear|not_applicable",
  "cause_variable": "domain.snake_case_name (MUST have domain prefix, e.g. health.mortality)",
  "effect_variable": "domain.snake_case_name (MUST have domain prefix, e.g. economic.gdp_growth)",
  "direction": "positive|negative|null|mixed|ambiguous|non_linear",
  "claim_explicitness": "explicit|implicit|unclear",
  "design_family_hint": \
"rct|iv|did|rdd|synthetic_control|event_study|quasi_experimental_other|panel_fe|ols|ols_cross_sect\
ional|review_narrative|review_meta_analysis|theoretical|structural_model|unclear",
  "effect_size": number|null (MUST be set if the paper reports ANY numeric magnitude for this \
claim),
  "evidence_strength": \
"rct|quasi_natural|quasi_natural_event|panel_fe|structural|observational|cross_sectional|meta_anal\
ysis|theoretical|unknown",
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
- Include all unique supported candidate claims; do not duplicate the same (cause, effect, \
direction, supporting_span_ids) tuple.
- Keep claims ordered by centrality/strength of evidence, strongest first.
- If evidence is only associational or review-based, set claim_type accordingly instead of \
forcing causal_claim.
- sample_size must be integer or null.
- Numeric fields must be numeric, never words like high/medium/low.
- empirical_parameters should capture ALL quantitative findings: regression coefficients, \
treatment effects,
  elasticities, odds ratios, hazard ratios, marginal effects, quantified policy contrasts, \
percentage changes,
  rates, proportions, or any numeric estimate from tables and results sections.
  Also include coefficients from OLS, IV, DID, panel FE, and similar regressions — these ARE \
valid parameters.
- CRITICAL: Scan all tables and results sections for numeric values. If a table has coefficients, \
effect sizes,
  or treatment-control comparisons, extract them as parameters. Tables are a PRIMARY source of \
parameters.
- If a paper reports regression results with coefficients and standard errors, extract ALL main \
coefficients as parameters.
- If a paper reports only descriptive statistics without any regression or causal analysis, \
return empirical_parameters as [].
- Each parameter MUST have at least a numeric value or value_range. Omit parameters that have no \
numbers.
- When the paper reports uncertainty in forms like `95% CI [a, b]` or `(SE = x)`, copy it into \
confidence_interval/std_error.
- Extract up to 12 strongest policy-relevant estimates. Prioritize parameters with standard \
errors or confidence intervals.
- Do NOT include p-values, t-statistics, F-statistics, R-squared, sample sizes, or descriptive \
counts as parameter values.
- IMPORTANT: For each causal_claim that has a numeric effect in the paper, also set effect_size \
to that number.
  If the paper says "X increased Y by 15 percentage points", set effect_size=15 and extract a \
parameter with value=15.
- For identification_strategy: only include if the paper has a clear causal identification \
strategy. Set null otherwise.
- For heterogeneity_results: include only if the paper explicitly tests effect heterogeneity or \
moderation.
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
  "unit": "unitless|elasticity|semi_elasticity|odds_ratio|risk_ratio|hazard_ratio|correlation_coef\
ficient|standardized_effect|index_points|percentage_points|basis_points",
  "evidence_strength": \
"rct|quasi_natural|quasi_natural_event|panel_fe|structural|observational|cross_sectional|meta_anal\
ysis|theoretical|unknown",
  "heterogeneity_note": "short note on what the estimate measures",
  "geographic_scope": "optional geography",
  "time_period": "optional period"
}

Rules:
- Extract only true effect estimates, treatment effects, coefficients, elasticities, odds ratios, \
hazard ratios, or standardized effects.
- Prefer estimates with explicit uncertainty whenever the paper reports it.
- When result snippets contain forms like `coefficient = 0.18 (SE = 0.04)` or
  `effect was 0.25 (95% CI [0.15, 0.45])`, copy both the point estimate and
  the uncertainty fields into the output.
- Use exact variable names from the provided claim inventory when an estimate quantifies one of \
those claims.
- Never include p-values, significance stars, standard errors by themselves, t-stats, z-stats, \
F-stats, R-squared, sample sizes, descriptive counts, or baseline means without a contrast.
- If the paper reports significance but no effect magnitude, return an empty array.
- If the estimate is dimensionless but clearly a coefficient/effect size, set unit to "unitless" \
or a more specific dimensionless unit.
- Extract up to 8 policy-relevant estimates. Include all coefficients with standard errors or \
confidence intervals.
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


def _jsonl_append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "updated_at": "", "items": {}}
    _key, loaded = _decode_json_object(
        path.read_bytes(),
        path=path,
        location=f"{path} (progress document)",
        kind="progress JSON document",
    )
    items = loaded.get("items")
    if not isinstance(items, dict):
        raise ValueError(f"Progress JSON document at {path} must contain an items object")
    for work_id, item in items.items():
        if not isinstance(item, dict):
            raise ValueError(
                f"Progress JSON document at {path} contains non-object item for {work_id!r}"
            )
    return loaded


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
    cache: dict[str, dict[str, Any]] = {}
    for _offset, _line_number, cache_key, row in _iter_keyed_jsonl_rows(path, key="cache_key"):
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
    for _offset, _line_number, work_id, entry in _iter_keyed_jsonl_rows(
        config.timeout_retry_queue_path, key="work_id"
    ):
        existing_queue[work_id] = entry
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


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]


def _decode_json_object(
    raw: bytes | str,
    *,
    path: Path,
    key: str | None = None,
    line_number: int | None = None,
    offset: int | None = None,
    location: str | None = None,
    kind: str = "JSONL record",
) -> tuple[str | None, dict[str, Any]]:
    """Decode one supplied JSON object and require only a caller-declared key."""
    if location is None:
        location = (
            f"{path}:{line_number}"
            if line_number is not None
            else f"{path} at byte offset {offset}"
        )
    payload = common_serialization.decode_json_object(raw, source=location, kind=kind)
    if key is None:
        return None, payload
    row_key = str(payload.get(key) or "").strip()
    if not row_key:
        raise ValueError(f"{kind} at {location} has no non-empty {key!r}")
    return row_key, payload


def _iter_keyed_jsonl_rows(
    path: Path,
    *,
    key: str,
) -> Iterator[tuple[int, int, str, dict[str, Any]]]:
    """Yield validated keyed records; only a missing file and blank rows are empty."""
    if not path.exists():
        return
    with path.open("rb") as fh:
        line_number = 0
        while True:
            offset = fh.tell()
            raw = fh.readline()
            if not raw:
                break
            line_number += 1
            if not raw.strip():
                continue
            row_key, payload = _decode_json_object(
                raw,
                path=path,
                key=key,
                line_number=line_number,
            )
            if row_key is None:
                raise ValueError(f"Keyed JSONL reader for {path} produced no key")
            yield offset, line_number, row_key, payload


class _LazyJsonlDict:
    """Memory-efficient JSONL lookup backed by an offset index."""

    def __init__(self, path: Path, *, key: str = "work_id") -> None:
        self._path = path
        self._key = key
        self._index: dict[str, int] = {}
        self._overrides: dict[str, dict[str, Any]] = {}
        self._deleted: set[str] = set()
        for offset, _line_number, row_key, _payload in _iter_keyed_jsonl_rows(
            path,
            key=key,
        ):
            self._index[row_key] = offset

    def _read_at(self, offset: int, key: str) -> dict[str, Any]:
        with self._path.open("rb") as fh:
            fh.seek(offset)
            raw = fh.readline()
        row_key, payload = _decode_json_object(
            raw,
            path=self._path,
            key=self._key,
            offset=offset,
        )
        if row_key != key:
            raise ValueError(
                f"Indexed JSONL record at {self._path} byte offset {offset} "
                f"no longer matches key {key!r}"
            )
        return payload

    def __contains__(self, key: object) -> bool:
        if key in self._deleted:
            return False
        return key in self._overrides or key in self._index

    def get(self, key: str, default: object = None) -> object:
        if key in self._deleted:
            return default
        if key in self._overrides:
            return self._overrides[key]
        offset = self._index.get(key)
        if offset is None:
            return default
        return self._read_at(offset, key)

    def __getitem__(self, key: str) -> dict[str, Any]:
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return cast("dict[str, Any]", result)

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        self._overrides[key] = value
        self._deleted.discard(key)

    def pop(self, key: str, *args: object) -> object:
        if key in self._deleted:
            if args:
                return args[0]
            raise KeyError(key)
        if key in self._overrides:
            value = self._overrides.pop(key)
            self._deleted.add(key)
            return value
        offset = self._index.get(key)
        if offset is None:
            if args:
                return args[0]
            raise KeyError(key)
        value = self._read_at(offset, key)
        self._deleted.add(key)
        return value

    def values(self) -> list[dict[str, Any]]:
        """Not used in hot path; provided for compatibility."""
        result: list[dict[str, Any]] = []
        for key in self._index:
            if key not in self._deleted:
                result.append(self.get(key))
        return result


def _load_jsonl_keyed(path: Path, *, key: str = "work_id") -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for _offset, _line_number, row_key, payload in _iter_keyed_jsonl_rows(path, key=key):
        rows[row_key] = payload
    return rows


def _load_jsonl_lazy(path: Path, *, key: str = "work_id") -> _LazyJsonlDict:
    """Memory-efficient alternative to ``_load_jsonl_keyed`` — builds an offset index."""
    return _LazyJsonlDict(path, key=key)


def _load_jsonl_grouped(
    path: Path,
    *,
    key: str = "work_id",
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _offset, _line_number, row_key, payload in _iter_keyed_jsonl_rows(path, key=key):
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
    with path.open("rb") as fh:
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
    row_offset = offset
    for raw_line in chunk.splitlines(keepends=True):
        if not raw_line.strip():
            row_offset += len(raw_line)
            continue
        _row_key, payload = _decode_json_object(
            raw_line,
            path=path,
            offset=row_offset,
        )
        rows.append(payload)
        row_offset += len(raw_line)
    return rows, new_offset


def _with_work_id(work_id: str, rows: object) -> list[dict[str, Any]]:
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
