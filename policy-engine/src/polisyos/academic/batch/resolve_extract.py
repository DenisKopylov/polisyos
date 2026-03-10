"""Streaming fulltext-first one-call extraction stage."""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import math
import random
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

from polisyos.batch_common.manifest import write_stage_manifest
import polisyos.academic.batch.fulltext_resolver as fulltext_resolver_module
from polisyos.academic.batch.article_extractor import (
    _CLAIM_SENTENCE_RE,
    _METHOD_SENTENCE_RE,
    _RESULT_SENTENCE_RE,
    _as_list,
    _build_evidence_bundle,
    _normalize_context_attribute,
    _normalize_extraction_payload,
    _normalize_moderation_edge,
    _normalized_text,
    _parse_json_object,
    _to_work_record,
)
from polisyos.academic.batch.claim_ids import stable_claim_id
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.context_classifier import infer_context_from_article
from polisyos.academic.batch.fulltext_resolver import (
    FullTextFetchResult,
    fetch_full_text_for_work,
    fetch_full_text_result_for_work,
    reconstruct_abstract,
)
from polisyos.academic.knowledge.variable_canonizer import VariableCanonizer
from polisyos.academic.openalex.priority_filter import should_process
from polisyos.ir.analytics.literature import (
    ArticleExtractionResult,
    CausalClaim,
    ClaimType,
    ContextAttribute,
    DesignFamily,
    EvidenceSpan,
    HeterogeneityResult,
    ModerationEdge,
    PaperKind,
    SourceBasis,
    TextQuality,
)
from polisyos.academic.batch.prompts import (
    PAPER_CLASSIFICATION_PROMPT,
    CONTEXT_EXTRACTION_SCHEMA_HINT,
    MODERATOR_EXTRACTION_SCHEMA_HINT,
)

logger = logging.getLogger(__name__)

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
    DesignFamily.META_ANALYSIS.value: None,
    DesignFamily.REVIEW.value: None,
    DesignFamily.REVIEW_NARRATIVE.value: None,
    DesignFamily.REVIEW_META_ANALYSIS.value: None,
    DesignFamily.THEORETICAL.value: None,
    DesignFamily.UNCLEAR.value: None,
}
_STRONG_METHOD_PATTERNS: dict[str, re.Pattern[str]] = {
    DesignFamily.RCT.value: re.compile(r"\b(randomi[sz]ed|random assignment|rct)\b", re.IGNORECASE),
    DesignFamily.IV.value: re.compile(r"\b(instrumental variable|instrument\w*|2sls|tsls|first stage)\b", re.IGNORECASE),
    DesignFamily.DID.value: re.compile(r"\b(difference[- ]?in[- ]?differences?|\bdid\b|parallel trends)\b", re.IGNORECASE),
    DesignFamily.RDD.value: re.compile(r"\b(regression discontinuity|\brdd\b|cutoff|threshold design)\b", re.IGNORECASE),
    DesignFamily.SYNTHETIC_CONTROL.value: re.compile(r"\b(synthetic control|synthetic counterfactual)\b", re.IGNORECASE),
    DesignFamily.EVENT_STUDY.value: re.compile(r"\b(event study|dynamic treatment effects|lead[s]? and lag[s]?)\b", re.IGNORECASE),
    DesignFamily.QUASI_EXPERIMENTAL_OTHER.value: re.compile(
        r"\b(natural experiment|quasi[- ]experimental|exogenous shock|policy discontinuity|staggered adoption)\b",
        re.IGNORECASE,
    ),
}
_DOWNGRADE_PATTERNS = re.compile(
    r"\b(correlation|associat(?:ion|ive)|cross[- ]sectional|ols only|ordinary least squares only|panel fixed effects only)\b",
    re.IGNORECASE,
)
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
_REVIEW_LIKE_RE = re.compile(r"\b(review|survey|literature review|meta-analysis|bibliometric|systematic review)\b", re.IGNORECASE)
_THEORY_LIKE_RE = re.compile(r"\b(theoretical|theory|conceptual framework|modeling exercise|simulation study)\b", re.IGNORECASE)
_METHOD_ONLY_RE = re.compile(r"\b(methods? paper|methodological|estimation method|algorithm|benchmark dataset)\b", re.IGNORECASE)
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
)
_CONTEXT_EFFECT_ESTIMATE_RE = re.compile(r"(?:^|[_\.])(multiplier|effect|impact|estimate|coefficient)(?:$|[_\.])", re.IGNORECASE)
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

Variable names should prefer these canonical prefixes when applicable:
economic. fiscal. governance. institutional. social. demographic. labor. trade.
environmental. health. education. infrastructure. political.

Each causal_claim object must use sentence IDs, not verbatim spans:
{
  "claim_text": "short paper-grounded claim",
  "claim_type": "causal_claim|associative|mechanism|review_summary|descriptive|normative|unclear|not_applicable",
  "cause_variable": "canonical-like text",
  "effect_variable": "canonical-like text",
  "direction": "positive|negative|null|mixed|ambiguous|non_linear",
  "claim_explicitness": "explicit|implicit|unclear",
  "design_family_hint": "rct|iv|did|rdd|synthetic_control|event_study|quasi_experimental_other|panel_fe|ols|ols_cross_sectional|review_narrative|review_meta_analysis|theoretical|structural_model|unclear",
  "effect_size": number|null,
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
- For identification_strategy: only include if the paper has a clear causal identification strategy. Set null otherwise.
- For heterogeneity_results: include only if the paper explicitly tests effect heterogeneity or moderation.
""".strip()


@dataclass
class ResolveExtractStats:
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
    total_tokens_prompt: int = 0
    total_tokens_completion: int = 0
    total_extraction_cost_usd: float = 0.0
    fetch_latency_ms: list[float] = field(default_factory=list)
    llm_latency_ms: list[float] = field(default_factory=list)
    limiter_wait_ms: list[float] = field(default_factory=list)


@dataclass
class WorkItem:
    work: dict[str, Any]
    work_id: str
    topic_id: str
    topic_ids: list[str]
    topic_display_names: list[str]
    prefetch_priority: float
    selected_rank: int


@dataclass
class EligibleItem:
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
    llm_eligible: bool
    context_eligible: bool
    rejection_reasons: list[str]


@dataclass
class ProviderResponse:
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


class _SlidingWindowLimiter:
    def __init__(self, max_requests: int, window: float = 1.0) -> None:
        self._max = max(1, int(max_requests))
        self._window = float(window)
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
_PER_KEY_CONCURRENT_CAP = 40   # provider hard limit: 50 per key
_GLOBAL_CONCURRENT_CAP = 180   # provider hard limit: 200 per user account
_MAX_RETRY_AFTER_SECONDS = 30.0  # cap on Retry-After header value


class _ProviderClient:
    def __init__(self, *, api_key: str, base_url: str, rate_limit_rps: float, circuit_failures: int, circuit_reset_seconds: int, connect_timeout_seconds: int, read_timeout_seconds: int, total_timeout_seconds: int) -> None:
        self.api_key = api_key
        self.url = f"{base_url.rstrip('/')}/chat/completions"
        self.limiter = _SlidingWindowLimiter(max(1, math.ceil(rate_limit_rps)), window=1.0)
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

    async def __aenter__(self) -> "_ProviderClient":
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
    def __init__(self, config: AcademicBatchConfig) -> None:
        self._clients = [
            _ProviderClient(
                api_key=key,
                base_url=config.gonka_base_url,
                rate_limit_rps=config.article_rate_limit_rps,
                circuit_failures=config.provider_circuit_breaker_failures,
                circuit_reset_seconds=config.provider_circuit_breaker_reset_seconds,
                connect_timeout_seconds=config.article_connect_timeout_seconds,
                read_timeout_seconds=config.article_read_timeout_seconds,
                total_timeout_seconds=config.article_total_timeout_seconds,
            )
            for key in config.gonka_api_keys
            if str(key).strip()
        ]
        self._max_retries = max(1, int(config.article_max_retries))
        self._max_completion_tokens = max(256, int(config.article_max_completion_tokens))
        self._selection_lock = asyncio.Lock()
        self._global_sem = asyncio.Semaphore(_GLOBAL_CONCURRENT_CAP)

    async def __aenter__(self) -> "GonkaMultiKeyPool":
        for client in self._clients:
            await client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for client in self._clients:
            await client.__aexit__(*exc)

    async def _acquire(self) -> _ProviderClient:
        """Acquire global concurrency slot and select least-loaded client."""
        while True:
            await self._global_sem.acquire()
            async with self._selection_lock:
                available = [
                    c for c in self._clients
                    if c.is_available() and c.in_flight < _PER_KEY_CONCURRENT_CAP
                ]
                if available:
                    client = min(available, key=lambda c: c.in_flight)
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

        for attempt in range(1, self._max_retries + 1):
            backoff = 0.0
            client = await self._acquire()
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
                            choices = data.get("choices") if isinstance(data.get("choices"), list) else []
                            first = choices[0] if choices else {}
                            message = first.get("message") if isinstance(first, dict) else {}
                            raw_content = str(message.get("content") or "") if isinstance(message, dict) else ""
                            finish_reason = str(first.get("finish_reason") or "") if isinstance(first, dict) else ""
                            parsed = _parse_json_object(raw_content) or {}
                            parse_status = "ok" if parsed else ("partial" if raw_content.strip() else "empty")
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
                                    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                                    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
                                    first = choices[0] if choices else {}
                                    message = first.get("message") if isinstance(first, dict) else {}
                                    raw_content = str(message.get("content") or "") if isinstance(message, dict) else ""
                                    finish_reason = str(first.get("finish_reason") or "") if isinstance(first, dict) else ""
                                    parsed = _parse_json_object(raw_content) or {}
                                    parse_status = "ok" if parsed else ("partial" if raw_content.strip() else "empty")
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
                                        error_class=("provider_length_stop" if truncated_output else ""),
                                        raw_content=raw_content,
                                        truncated_output=truncated_output,
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
                except asyncio.TimeoutError:
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
        )


def _jsonl_append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "updated_at": "", "items": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict) and isinstance(loaded.get("items"), dict):
            return loaded
    except Exception:
        pass
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
    with open(path, "r", encoding="utf-8") as fh:
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
    return state in {"published", "raw_only", "failed", "rejected"}


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
    if bool(work.get("has_fulltext")):
        priority += 15.0
    if bool(open_access.get("is_oa")):
        priority += 12.0
    if any(str(best_oa.get(key) or "").strip() for key in ("pdf_url", "landing_page_url")):
        priority += 8.0
    if _has_strong_design_signal(title, abstract):
        priority += 10.0
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
    score += min(
        2.0,
        float(
            _count_pattern(_RESULT_CUE_RE, abstract)
            + _count_pattern(_RESULT_SENTENCE_RE, abstract)
            + _count_pattern(_CLAIM_SENTENCE_RE, abstract)
        ),
    ) * 0.75
    score += min(
        1.0,
        float(
            _count_pattern(_RESULT_CUE_RE, title)
            + _count_pattern(_RESULT_SENTENCE_RE, title)
            + _count_pattern(_CLAIM_SENTENCE_RE, title)
        ),
    ) * 0.25
    return round(score, 6)


def _downgrade_signal_score(*parts: str) -> float:
    haystack = "\n".join(part for part in parts if part)
    if not haystack:
        return 0.0
    return float(len(_DOWNGRADE_PATTERNS.findall(haystack)))


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
    review_like = _is_review_like(result.title, abstract, result.citation_summary, result.methodology)
    theory_like = _is_theory_like(result.title, abstract, result.citation_summary, result.methodology)
    method_only = _is_method_only(result.title, abstract, result.citation_summary, result.methodology)
    context_signal = _has_context_classification_signal(joined)
    heterogeneity_signal = _has_heterogeneity_classification_signal(joined)
    has_claims = bool(result.causal_claims)
    has_moderation = bool(result.moderation_edges) or bool(result.heterogeneity_results) or heterogeneity_signal
    strong_design = _has_strong_design_signal(result.title, abstract, result.methodology, result.citation_summary) or any(
        claim.identification_strategy is not None for claim in result.causal_claims
    )
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
            return PaperKind.MIXED if (eligible_item.context_eligible or context_signal) else PaperKind.HETEROGENEITY_ANALYSIS
        if eligible_item.context_eligible and (context_signal or not has_claims):
            return PaperKind.CONTEXT_CHARACTERIZATION
        if has_claims:
            return PaperKind.EMPIRICAL_CAUSAL
        return PaperKind.DESCRIPTIVE

    if parsed_kind == PaperKind.EMPIRICAL_CAUSAL and eligible_item.context_eligible and not eligible_item.llm_eligible:
        if has_moderation:
            return PaperKind.MIXED if (review_like or context_signal or not strong_design) else PaperKind.HETEROGENEITY_ANALYSIS
        if review_like or ((context_signal or not has_claims) and not strong_design):
            return PaperKind.CONTEXT_CHARACTERIZATION

    if parsed_kind in {PaperKind.REVIEW_SYSTEMATIC, PaperKind.DESCRIPTIVE} and eligible_item.context_eligible:
        return PaperKind.MIXED if has_moderation else PaperKind.CONTEXT_CHARACTERIZATION

    return parsed_kind


def _shared_vocabulary_text() -> str:
    return ", ".join(_SHARED_VOCABULARY_PREFIXES)


def _build_claim_inventory(result: ArticleExtractionResult, canonizer: VariableCanonizer) -> list[dict[str, str]]:
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


def _tokenize_variable_name(value: str) -> set[str]:
    text = str(value or "").strip().lower()
    if not text:
        return set()
    parts = re.split(r"[^a-z0-9]+", text.replace(".", "_"))
    return {part for part in parts if part and part not in {"economic", "fiscal", "governance", "institutional", "social", "demographic", "labor", "trade", "environmental", "health", "education", "infrastructure", "political"}}


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
    if claim.identification_strategy is not None and claim.identification_strategy.identification_method:
        return True
    return bool(_METHOD_SENTENCE_RE.search(method_text))


def _has_strong_identification_signal(claim: CausalClaim) -> bool:
    """Check if claim mentions a genuine causal identification strategy.

    Unlike ``_has_any_method_signal`` this excludes weak data-type terms
    (regression, panel data, OLS, admin data) that are necessary but not
    sufficient for causal identification.
    """
    if claim.identification_strategy is not None and claim.identification_strategy.identification_method:
        return True
    method_text = " ".join(span.text for span in claim.method_spans)
    return bool(_STRONG_IDENTIFICATION_RE.search(method_text))


def _looks_like_context_overlap(attribute_name: str, canonical_name: str, claim_inventory: list[dict[str, str]]) -> bool:
    candidate_names = [name for name in {attribute_name, canonical_name, canonical_name.rsplit(".", 1)[-1] if canonical_name else ""} if name]
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
    claim_by_pair = {(row["cause_variable"], row["effect_variable"]): row for row in claim_inventory}
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
        canonized_context_attributes.append(attribute.model_copy(update={"canonical_name": canonical_name}))

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


def _post_resolve_priority(item: WorkItem, *, text: str, source_kind: str, text_quality: str) -> float:
    abstract = reconstruct_abstract(item.work)
    title = _normalized_text(item.work.get("title"))
    method_signal = _method_signal_score(title, abstract, text)
    data_signal = _data_signal_score(title, abstract, text)
    result_signal = _result_signal_score(title, abstract, text)
    downgrade_signal = _downgrade_signal_score(title, abstract, text)
    priority = item.prefetch_priority
    priority += 20.0 if source_kind != "abstract_fallback" else -50.0
    priority += 12.0 if text_quality == TextQuality.EXTRACTED_FULLTEXT.value else 0.0
    priority += min(14.0, method_signal * 2.0)
    priority += min(8.0, data_signal * 2.0)
    priority += min(12.0, result_signal * 1.75)
    if _has_strong_design_signal(title, abstract, text):
        priority += 12.0
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
    track_b_enabled: bool = False,
    track_c_enabled: bool = False,
) -> EligibilityDecision:
    del track_c_enabled
    reasons: list[str] = []
    abstract = reconstruct_abstract(item.work)
    title = _normalized_text(item.work.get("title"))
    method_signal = _method_signal_score(title, abstract, text)
    data_signal = _data_signal_score(title, abstract, text)
    result_signal = _result_signal_score(title, abstract, text)
    empirical_signal = method_signal + result_signal + (data_signal * 0.75)
    strong_design = _has_strong_design_signal(title, abstract, text)
    if source_kind == "abstract_fallback":
        reasons.append("abstract_only")
    if (
        text_quality == TextQuality.DEGRADED.value
        or len(_normalized_text(text)) < _MIN_FULLTEXT_CHARS
    ) and empirical_signal < 2.0 and not strong_design:
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
    llm_eligible = not reasons
    hard_reasons = [reason for reason in reasons if reason in _CONTEXT_HARD_REJECTION_REASONS]
    soft_reasons = [reason for reason in reasons if reason in _CONTEXT_SOFT_REJECTION_REASONS]
    context_eligible = bool(track_b_enabled) and not hard_reasons and bool(soft_reasons)
    return EligibilityDecision(
        llm_eligible=llm_eligible,
        context_eligible=context_eligible,
        rejection_reasons=reasons,
    )


def _build_streaming_evidence_bundle(item: WorkItem, *, text: str, source_kind: str, sentence_budget: int) -> dict[str, Any]:
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
    return bundle


def _prompt_for_bundle(bundle: dict[str, Any]) -> str:
    return (
        "Extract policy-relevant empirical evidence from this evidence bundle.\n"
        + _ONE_CALL_SCHEMA_HINT
        + "\n\nEvidence bundle:\n"
        + json.dumps(bundle, ensure_ascii=False)
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
    if _DOWNGRADE_PATTERNS.search(method_text) or _DOWNGRADE_PATTERNS.search(support_text):
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
            has_downgrade = bool(_DOWNGRADE_PATTERNS.search(method_text) or _DOWNGRADE_PATTERNS.search(support_text))
            has_hedge = bool(_NARRATIVE_HEDGE_RE.search(claim.claim_text or ""))
            if has_strong and not has_downgrade and not has_hedge:
                design_tier = 4
        if result.source_basis != SourceBasis.FULLTEXT:
            blockers.append("source_basis_not_fulltext")
        if claim.source_basis != SourceBasis.FULLTEXT:
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
        if claim.span_contamination_detected and (not claim.supporting_spans or not claim.method_spans):
            blockers.append("span_contamination_removed_evidence")
        if blocked_paper:
            blockers.append("paper_classified_non_empirical")
        confidence = float(claim.claim_extraction_confidence or result.extraction_confidence or 0.0)
        if confidence < 0.45:
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


def _to_claim_row(result: ArticleExtractionResult, claim: CausalClaim, *, topic_ids: list[str], topic_display_names: list[str]) -> dict[str, Any]:
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
        "claim_extraction_confidence": float(claim.claim_extraction_confidence or result.extraction_confidence),
    }


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]


def _reset_output_paths(config: AcademicBatchConfig) -> None:
    for path in (
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
        config.fulltext_resolved_path,
        config.extracted_dir / "resolve_extract.jsonl",
    ):
        if path.exists():
            path.unlink()


async def run_resolve_extract(config: AcademicBatchConfig) -> dict[str, float | int]:
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
    metadata_cache = _load_metadata_cache(config.fulltext_metadata_cache_path)
    resolved_fulltext_cache = fulltext_resolver_module.load_resolved_fulltext_cache(
        config.resolved_fulltext_cache_path,
        ttl_days=config.fulltext_cache_ttl_days,
    )
    topic_success: dict[str, int] = defaultdict(int)
    topic_inflight: dict[str, int] = defaultdict(int)
    topic_seen: set[str] = set()

    with open(selected_rows_path, "r", encoding="utf-8") as fh:
        selected_rows = [json.loads(line) for line in fh if line.strip()]

    work_items: list[WorkItem] = []
    for index, row in enumerate(selected_rows, start=1):
        if not isinstance(row, dict):
            continue
        work = row.get("work") if isinstance(row.get("work"), dict) else {}
        if not isinstance(work, dict):
            continue
        work_id = str(row.get("work_id") or work.get("id") or "").strip()
        if not work_id:
            continue
        work_items.append(
            WorkItem(
                work=work,
                work_id=work_id,
                topic_id=_topic_id_for_row(row),
                topic_ids=_topic_ids_for_row(row),
                topic_display_names=_topic_names_for_row(row),
                prefetch_priority=_prefetch_priority(work),
                selected_rank=index,
            )
        )
        topic_seen.add(_topic_id_for_row(row))

    del selected_rows
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
        item.update({"state": state, **extra, "updated_at": datetime.now(UTC).isoformat()})
        progress["updated_at"] = datetime.now(UTC).isoformat()

    async def _persist_progress(work_id: str, state: str, **extra: Any) -> None:
        nonlocal _progress_dirty
        async with progress_lock:
            _mark_progress(work_id, state, **extra)
            _progress_dirty += 1
            if _progress_dirty >= _PROGRESS_FLUSH_INTERVAL or state in ("published", "failed"):
                _write_progress(config.resolve_extract_progress_path, progress)
                _progress_dirty = 0

    async def _flush_progress() -> None:
        nonlocal _progress_dirty
        async with progress_lock:
            if _progress_dirty > 0:
                _write_progress(config.resolve_extract_progress_path, progress)
                _progress_dirty = 0

    fetch_queue: asyncio.Queue[WorkItem | None] = asyncio.Queue()
    eligible_queue: asyncio.PriorityQueue[tuple[float, int, EligibleItem] | None] = asyncio.PriorityQueue()
    llm_queue: asyncio.Queue[EligibleItem | None] = asyncio.Queue()
    fetch_done = asyncio.Event()
    dispatcher_done = asyncio.Event()

    _enqueue_count = 0
    _skip_count = 0
    for item in work_items:
        existing = progress.get("items", {}).get(item.work_id, {}) if isinstance(progress.get("items"), dict) else {}
        if _terminal_state(str(existing.get("state") or "")):
            _skip_count += 1
            continue
        await fetch_queue.put(item)
        _enqueue_count += 1
    logger.info("Enqueue complete: %d items queued, %d skipped (already done)", _enqueue_count, _skip_count)

    fetch_workers_count = max(1, int(config.fulltext_max_concurrent_fetches))
    llm_workers_count = max(1, int(config.article_max_concurrent_llm))
    for _ in range(fetch_workers_count):
        await fetch_queue.put(None)

    async def _append_artifacts(*, result: ArticleExtractionResult, work_item: WorkItem, record_json: str) -> None:
        async with file_lock:
            _jsonl_append(config.article_extraction_results_path, result.model_dump(mode="json"))
            _jsonl_append(config.resolve_extract_results_path, result.model_dump(mode="json"))
            config.extracted_dir.mkdir(parents=True, exist_ok=True)
            with open(config.extracted_dir / "resolve_extract.jsonl", "a", encoding="utf-8") as fh:
                fh.write(record_json + "\n")
            for claim in result.causal_claims:
                row = _to_claim_row(result, claim, topic_ids=work_item.topic_ids, topic_display_names=work_item.topic_display_names)
                _jsonl_append(config.raw_claim_candidates_path, row)
                if claim.publish_to_graph:
                    _jsonl_append(config.published_claims_path, row)

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
                try:
                    if config.fulltext_acquisition_mode == "v7_http_metadata":
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
                    elif fetch_full_text_result_for_work is not fulltext_resolver_module.fetch_full_text_result_for_work:
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
                            final_state=("abstract_fallback" if source_kind == "abstract_fallback" else "usable_fulltext"),
                        )
                    text = fetch_result.text
                    source_kind = fetch_result.source_kind
                    source_url = fetch_result.source_url
                    fetch_error_class = fetch_result.fetch_error_class
                except asyncio.TimeoutError:
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
                                "attempt_kind": "seed",
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
                        _jsonl_append(config.resolved_fulltext_cache_path, fetch_result.resolved_cache_row)
                    _jsonl_append(
                        config.fulltext_resolved_path,
                        {
                            "work_id": item.work_id,
                            "source_kind": source_kind,
                            "source_basis": (SourceBasis.ABSTRACT_ONLY.value if source_kind == "abstract_fallback" else SourceBasis.FULLTEXT.value),
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
                    track_b_enabled=config.track_b_enabled,
                    track_c_enabled=config.track_c_enabled,
                )
                if not (eligibility.llm_eligible or eligibility.context_eligible):
                    stats.rejected += 1
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
                post_priority = _post_resolve_priority(item, text=text, source_kind=source_kind, text_quality=text_quality)
                await _persist_progress(
                    item.work_id,
                    "eligible",
                    topic_id=item.topic_id,
                    source_kind=source_kind,
                    text_quality=text_quality,
                    post_priority=post_priority,
                    llm_eligible=eligibility.llm_eligible,
                    context_eligible=eligibility.context_eligible,
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
        logger.info("LLM dispatcher started, llm_workers=%d", llm_workers_count)
        _dispatched = 0
        while True:
            if fetch_done.is_set() and eligible_queue.empty() and all(v == 0 for v in topic_inflight.values()):
                for _ in range(llm_workers_count):
                    await llm_queue.put(None)
                dispatcher_done.set()
                return
            try:
                entry = await asyncio.wait_for(eligible_queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
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
                eligible_queue.task_done()
                continue
            if topic_success[topic_id] + topic_inflight[topic_id] >= config.article_target_fulltext_per_topic:
                eligible_queue.task_done()
                await asyncio.sleep(0.05)
                await eligible_queue.put((priority, eligible_item.work_item.selected_rank, eligible_item))
                continue
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
                logger.info("LLM dispatcher: %d items dispatched to llm_queue", _dispatched)
            eligible_queue.task_done()

    async def llm_worker(pool: GonkaMultiKeyPool) -> None:
        _worker_count = 0
        while True:
            entry = await llm_queue.get()
            if entry is None:
                llm_queue.task_done()
                break
            eligible_item = entry
            work_item = eligible_item.work_item
            _worker_count += 1
            if _worker_count == 1:
                logger.info("LLM worker got first item: %s", work_item.work_id)
            await _persist_progress(work_item.work_id, "llm_inflight", topic_id=work_item.topic_id)
            stats.llm_requests += 1
            bundle = _build_streaming_evidence_bundle(
                work_item,
                text=eligible_item.text,
                source_kind=eligible_item.source_kind,
                sentence_budget=config.article_evidence_bundle_sentence_budget,
            )
            prompt = _prompt_for_bundle(bundle)
            response = await pool.chat_json(
                model=config.article_extraction_model,
                prompt=prompt,
                temperature=0.0,
            )
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
            elif response.error_class == "json_parse":
                stats.json_parse_errors += 1
            elif response.error_class == "empty_response":
                stats.empty_responses += 1
            async with file_lock:
                _jsonl_append(
                    config.llm_request_log_path,
                    {
                        "work_id": work_item.work_id,
                        "topic_id": work_item.topic_id,
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
                if "methodology_summary" in parsed and "methodology" not in parsed:
                    parsed["methodology"] = parsed.get("methodology_summary")
                payload = _normalize_extraction_payload(
                    work_item.work,
                    parsed,
                    config.article_extraction_model,
                    response.usage,
                    evidence_bundle=bundle,
                    source_kind=eligible_item.source_kind,
                )
                payload["paper_relevance"] = bool(parsed.get("paper_relevance", True))
                payload["paper_relevance_reason"] = _normalized_text(parsed.get("paper_relevance_reason"))
                payload["provider_finish_reason"] = response.finish_reason
                payload["provider_latency_ms"] = round(response.latency_ms, 3)
                payload["truncated_output"] = bool(response.truncated_output)
                payload["llm_error_class"] = response.error_class
                payload["text_quality"] = eligible_item.text_quality
                payload["source_basis"] = SourceBasis.FULLTEXT.value
                result = ArticleExtractionResult.model_validate(payload)
                result = result.model_copy(update={"source_context": infer_context_from_article(work_item.work, result)})
                claim_inventory = _build_claim_inventory(result, canonizer)

                # --- Track B/C routing (opt-in) ---
                if config.track_b_enabled or config.track_c_enabled:
                    try:
                        classification_model = config.paper_classification_model or config.article_screening_model
                        abstract_text = str(work_item.work.get("abstract") or bundle.get("abstract") or "")
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
                            track_b_model = config.track_b_extraction_model or config.article_extraction_model
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
                                result = result.model_copy(update={"context_attributes": context_attributes})

                        # Track C: moderation/heterogeneity
                        track_c_eligible = config.track_c_enabled and paper_kind in {
                            PaperKind.HETEROGENEITY_ANALYSIS,
                            PaperKind.MIXED,
                            PaperKind.EMPIRICAL_CAUSAL,
                        }
                        if track_c_eligible:
                            track_c_model = config.track_c_extraction_model or config.article_extraction_model
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
                                result = result.model_copy(update={"moderation_edges": moderation_edges})
                    except Exception:
                        logger.debug("Track B/C routing failed for %s", work_item.work_id, exc_info=True)

                result = _reconcile_tracks(result, canonizer=canonizer, claim_inventory=claim_inventory)
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
                            _jsonl_append(config.context_attributes_path, {
                                "openalex_id": result.openalex_id,
                                **ca.model_dump(mode="json"),
                            })
                if result.moderation_edges:
                    async with file_lock:
                        for me in result.moderation_edges:
                            _jsonl_append(config.moderation_edges_path, {
                                "openalex_id": result.openalex_id,
                                **me.model_dump(mode="json"),
                            })
                published_count = sum(1 for claim in result.causal_claims if claim.publish_to_graph)
                stats.raw_claims += len(result.causal_claims)
                stats.published_claims += published_count
                stats.extracted += 1
                topic_success[work_item.topic_id] += 1
                final_state = "published" if published_count > 0 else "raw_only"
                await _persist_progress(
                    work_item.work_id,
                    final_state,
                    topic_id=work_item.topic_id,
                    published_claims=published_count,
                    raw_claims=len(result.causal_claims),
                    source_basis=result.source_basis.value,
                )
            except Exception as exc:
                stats.extraction_errors += 1
                async with file_lock:
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
                    "failed",
                    topic_id=work_item.topic_id,
                    error_class=response.error_class or "normalization_error",
                    error_message=str(exc),
                )
            finally:
                topic_inflight[work_item.topic_id] = max(0, topic_inflight[work_item.topic_id] - 1)
                llm_queue.task_done()

    fetch_tasks = [asyncio.create_task(fetch_worker(index)) for index in range(fetch_workers_count)]
    async with GonkaMultiKeyPool(config) as pool:
        llm_tasks = [asyncio.create_task(llm_worker(pool)) for _ in range(llm_workers_count)]
        dispatcher_task = asyncio.create_task(llm_dispatcher())

        await fetch_queue.join()
        fetch_done.set()
        await asyncio.gather(*fetch_tasks)
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
        "length_stop_rate": round((stats.provider_length_stop / max(1, stats.llm_requests)) * 100.0, 3),
        "provider_429_rate": round((stats.provider_429 / max(1, stats.llm_requests)) * 100.0, 3),
        "mean_limiter_wait_ms": round(sum(stats.limiter_wait_ms) / max(1, len(stats.limiter_wait_ms)), 3),
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
    }

    write_stage_manifest(
        manifest_path=config.manifests_dir / "resolve_extract.json",
        stage="resolve_extract",
        status="ok",
        metrics=metrics,
        artifacts=[
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
        ],
        started_at=started_at,
    )
    return metrics


__all__ = ["run_resolve_extract"]
