"""Stage: selective LLM enrichment for parsed academic abstracts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.knowledge.types import (
    ClaimOccurrenceVocabularyTransport,
    EstimateCandidate,
    WorkRecord,
    adapt_jsonl_work_record_claims,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest
from polisyos.ir.analytics import (
    ClaimVocabularyAxisStatus,
    SourceBasis,
    VersionedClaimVocabularyEnvelope,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

logger = get_logger(__name__)


def _candidate_status(value: object) -> ClaimVocabularyAxisStatus:
    """Return the only status available for a future extractor observation."""

    if value is None:
        return ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    return ClaimVocabularyAxisStatus.CANDIDATE


def serialize_llm_claim_occurrence_vocabulary(
    occurrence: Mapping[str, Any],
    *,
    record_extraction_mode: str | None = "llm_enriched",
) -> ClaimOccurrenceVocabularyTransport:
    """Build the v2 composite from separately named LLM candidate axes.

    This serializer deliberately accepts no generic ``strength`` mapping.  A
    replayed five-field occurrence must use the explicit historical adapter,
    while the LLM's named candidate values remain independent observations.
    """

    retained = dict(occurrence)
    if "strength" in retained:
        raise ValueError("LLM vocabulary input must not contain generic strength")
    values = {
        "design_family_hint": retained.pop("design_family_hint", None),
        "evidence_strength": retained.pop("evidence_strength", None),
        "claim_extraction_confidence": retained.pop("claim_extraction_confidence", None),
    }
    for key in (
        "source_basis",
        "design_family_hint_status",
        "evidence_strength_status",
        "claim_extraction_confidence_status",
        "source_basis_status",
        "legacy_strength_label",
        "record_extraction_mode",
    ):
        if key in retained:
            raise ValueError(f"LLM vocabulary input must not contain {key}")
    return ClaimOccurrenceVocabularyTransport(
        occurrence=retained,
        vocabulary=VersionedClaimVocabularyEnvelope(
            cause=str(retained.get("cause", "")),
            effect=str(retained.get("effect", "")),
            direction=str(retained.get("direction", "")),
            mechanism=str(retained.get("mechanism", "")),
            design_family_hint=values["design_family_hint"],
            design_family_hint_status=_candidate_status(values["design_family_hint"]),
            evidence_strength=values["evidence_strength"],
            evidence_strength_status=_candidate_status(values["evidence_strength"]),
            claim_extraction_confidence=values["claim_extraction_confidence"],
            claim_extraction_confidence_status=_candidate_status(
                values["claim_extraction_confidence"]
            ),
            source_basis=SourceBasis.ABSTRACT_ONLY,
            source_basis_status=ClaimVocabularyAxisStatus.CANDIDATE,
            record_extraction_mode=record_extraction_mode,
        ),
    )

EXTRACTION_PROMPT = """Extract causal and quantitative evidence from this abstract.

Return strict JSON object with fields:
{
  "estimates": [
    {
      "value": <number>,
      "unit": "percent|ratio|level|index|pp",
      "ci_low": <number or null>,
      "ci_high": <number or null>,
      "std_error": <number or null>,
      "context": "<brief description>",
      "variable_hint": "<canonical-like variable name>"
    }
  ],
  "study_design": "RCT|IV|DiD|RDD|FE|OLS|meta-analysis|descriptive|other",
  "sample_size": <number or null>,
  "causal_claims": [
    {
      "cause": "<concept>",
      "effect": "<concept>",
      "direction": "positive|negative|null|mixed",
      "design_family_hint": "one design family (rct, iv, did, rdd, synthetic_control, event_study,
        quasi_experimental_other, quasi_experimental_did, quasi_experimental_rdd, panel_fe, ols,
        ols_cross_sectional, meta_analysis, review, review_narrative, review_meta_analysis,
        theoretical, structural_model, time_series_cointegration, unclear) or null",
      "evidence_strength": "one evidence class (rct, quasi_natural, quasi_natural_event,
        meta_analysis, panel_fe, structural, observational, cross_sectional, theoretical,
        unknown) or null",
      "claim_extraction_confidence": <number from 0 to 1 or null>,
      "mechanism": "<short text>"
    }
  ],
  "boundary_conditions": [
    {
      "variable": "<name>",
      "operator": "<op>",
      "threshold_value": "<value>",
      "scope_text": "<condition text>",
      "confidence": <0..1>
    }
  ]
}

Abstract:
{abstract}
"""


@dataclass(frozen=True)
class GateFeatures:
    """Gate features public type."""

    text_len: int
    numeric_hits: int
    ambiguity_hits: int
    deterministic_confidence: float
    estimate_count: int
    has_boundary_signal: bool


@dataclass(frozen=True)
class GateDecision:
    """Gate decision public type."""

    route: str  # auto|llm|deferred|audit_llm
    score: float
    reason_codes: list[str]


@dataclass
class GateRuntime:
    """Gate runtime public type."""

    threshold: float
    mode: str
    max_share: float
    audit_max_miss_rate_pct: float
    circuit_breaker_enabled: bool = True
    safe_pass_active: bool = False
    consecutive_audit_failures: int = 0
    circuit_breaker_hits: int = 0

    @property
    def effective_threshold(self) -> float:
        if self.safe_pass_active:
            return max(0.0, self.threshold - 0.2)
        if self.mode == "aggressive":
            return min(1.0, self.threshold + 0.1)
        return self.threshold

    def register_audit_miss_rate(self, miss_rate_pct: float) -> bool:
        if not self.circuit_breaker_enabled:
            return False
        if miss_rate_pct > self.audit_max_miss_rate_pct:
            self.consecutive_audit_failures += 1
        else:
            self.consecutive_audit_failures = 0
        if self.consecutive_audit_failures >= 2:
            self.safe_pass_active = True
            self.circuit_breaker_hits += 1
            self.consecutive_audit_failures = 0
            return True
        return False


class AcademicLLMClient:
    """OpenAI-compatible async client for abstract extraction."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_concurrent: int,
        max_retries: int,
        rate_limit_rps: float,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._temperature = temperature
        self._max_retries = max(1, int(max_retries))
        self._session: aiohttp.ClientSession | None = None
        self._sem = asyncio.Semaphore(max(1, int(max_concurrent)))
        self._limiter = _SlidingWindowLimiter(max(1, int(rate_limit_rps)))

    async def __aenter__(self) -> AcademicLLMClient:
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=120),
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def chat_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        assert self._session is not None, "Use async context manager"

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            async with self._sem:
                await self._limiter.acquire()
                try:
                    async with self._session.post(self._url, json=payload) as resp:
                        body = await resp.text()
                        if resp.status == 200:
                            data = json.loads(body)
                            content = ""
                            if isinstance(data, dict):
                                choices = data.get("choices")
                                if isinstance(choices, list) and choices:
                                    msg = (
                                        choices[0].get("message")
                                        if isinstance(choices[0], dict)
                                        else {}
                                    )
                                    if isinstance(msg, dict):
                                        content = str(msg.get("content") or "")
                            return {"content": content}

                        if resp.status in {429, 500, 502, 503, 504}:
                            await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 20.0))
                            continue

                        raise RuntimeError(f"LLM non-retryable HTTP {resp.status}: {body[:500]}")
                except (TimeoutError, aiohttp.ClientError, json.JSONDecodeError) as exc:
                    last_error = exc
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 20.0))

        raise RuntimeError("LLM request failed after retries") from last_error


class _SlidingWindowLimiter:
    def __init__(self, max_requests: int, window: float = 1.0) -> None:
        self._max = max_requests
        self._window = window
        self._lock = asyncio.Lock()
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = asyncio.get_running_loop().time()
                self._timestamps = [t for t in self._timestamps if t > now - self._window]
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                wait = self._timestamps[0] + self._window - now
            await asyncio.sleep(max(0.01, wait))


_NUMERIC_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_AMBIGUITY_RE = re.compile(
    r"\b(if|when|unless|may|might|depending on|conditional)\b", re.IGNORECASE
)
_BOUNDARY_SIGNAL_RE = re.compile(
    r"\b(heterogeneous|varies by|only in|conditional on|cross-country|multi-country)\b",
    re.IGNORECASE,
)


def _stable_sample(seed: str, sample_rate: float) -> bool:
    if sample_rate <= 0.0:
        return False
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    value = int(digest, 16) / 0xFFFFFFFF
    return value < sample_rate


def build_gate_features(record: WorkRecord) -> GateFeatures:
    """Build gate features."""
    text = record.abstract or ""
    return GateFeatures(
        text_len=len(text),
        numeric_hits=len(_NUMERIC_RE.findall(text)),
        ambiguity_hits=len(_AMBIGUITY_RE.findall(text)),
        deterministic_confidence=float(record.extraction_confidence or 0.0),
        estimate_count=len(record.estimates),
        has_boundary_signal=bool(_BOUNDARY_SIGNAL_RE.search(text)),
    )


def irreducibility_score(features: GateFeatures) -> float:
    """Irreducibility score helper."""
    length_factor = min(1.0, features.text_len / 2600.0)
    numeric_factor = min(1.0, features.numeric_hits / 12.0)
    ambiguity_factor = min(1.0, features.ambiguity_hits / 5.0)
    low_det_factor = 1.0 - max(0.0, min(1.0, features.deterministic_confidence))
    sparse_est_factor = 1.0 if features.estimate_count == 0 else 0.0
    boundary_factor = 1.0 if features.has_boundary_signal else 0.0
    score = (
        0.30 * low_det_factor
        + 0.22 * ambiguity_factor
        + 0.18 * numeric_factor
        + 0.15 * sparse_est_factor
        + 0.10 * boundary_factor
        + 0.05 * length_factor
    )
    return max(0.0, min(1.0, score))


def decide_route(
    *,
    runtime: GateRuntime,
    gate_enabled: bool,
    llm_available: bool,
    llm_share: float,
    auto_conf_threshold: float,
    min_score_force_llm: float,
    features: GateFeatures,
    audit_sample_rate: float,
    audit_seed: str,
) -> GateDecision:
    """Decide route helper."""
    det_conf = features.deterministic_confidence
    score = irreducibility_score(features)

    if det_conf >= auto_conf_threshold:
        if llm_available and _stable_sample(audit_seed, audit_sample_rate):
            return GateDecision(route="audit_llm", score=score, reason_codes=["audit_sample_auto"])
        return GateDecision(route="auto", score=score, reason_codes=["deterministic_high_conf"])

    if not llm_available:
        return GateDecision(route="deferred", score=score, reason_codes=["llm_unavailable"])

    if not gate_enabled or runtime.mode == "off":
        return GateDecision(route="llm", score=score, reason_codes=["gate_off"])

    if llm_share >= runtime.max_share and not runtime.safe_pass_active:
        if _stable_sample(audit_seed, audit_sample_rate):
            return GateDecision(
                route="audit_llm", score=score, reason_codes=["audit_sample_budget_cap"]
            )
        return GateDecision(route="deferred", score=score, reason_codes=["budget_cap"])

    if score >= min_score_force_llm:
        return GateDecision(route="llm", score=score, reason_codes=["force_llm_high_score"])
    if score >= runtime.effective_threshold:
        return GateDecision(route="llm", score=score, reason_codes=["score_above_threshold"])

    if _stable_sample(audit_seed, audit_sample_rate):
        return GateDecision(route="audit_llm", score=score, reason_codes=["audit_sample"])

    return GateDecision(route="deferred", score=score, reason_codes=["score_below_threshold"])


async def extract_with_llm(
    *, abstract: str, topic: str, work_id: str, client: AcademicLLMClient
) -> dict:
    """Run LLM extraction on a single abstract."""
    # Substitute only the input slot, leaving the JSON literal and abstract braces intact.
    prompt = EXTRACTION_PROMPT.replace("{abstract}", abstract[:4000])
    try:
        response = await client.chat_completion(messages=[{"role": "user", "content": prompt}])
        content = str(response.get("content", ""))
        parsed = _parse_json_object(content)
        if parsed is None:
            return {"estimates": [], "causal_claims": [], "boundary_conditions": []}
        return parsed
    except Exception as exc:
        logger.warning("LLM extraction failed for %s: %s", work_id, exc)
        return {"estimates": [], "causal_claims": [], "boundary_conditions": []}


def _parse_json_object(raw_content: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start != -1 and end > start:
        candidate = raw_content[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


def parse_llm_result(
    result: dict,
) -> tuple[list[EstimateCandidate], list[ClaimOccurrenceVocabularyTransport], list[dict]]:
    """Parse LLM extraction result into typed objects."""
    estimates: list[EstimateCandidate] = []
    for est in result.get("estimates", []):
        if not isinstance(est, dict):
            continue
        try:
            value = float(est.get("value", 0))
        except (ValueError, TypeError):
            continue
        estimates.append(
            EstimateCandidate(
                value=value,
                ci_low=_safe_float(est.get("ci_low")),
                ci_high=_safe_float(est.get("ci_high")),
                std_error=_safe_float(est.get("std_error")),
                unit=str(est.get("unit", "")),
                context_snippet=str(est.get("context", "")),
                pattern_name="llm_extraction",
                confidence=0.8,
                variable_hint=str(est.get("variable_hint", "")),
            )
        )

    causal_claim_payloads = result.get("causal_claims", [])
    if not isinstance(causal_claim_payloads, list):
        causal_claim_payloads = []
    causal_claims = [
        serialize_llm_claim_occurrence_vocabulary(claim)
        for claim in causal_claim_payloads
        if isinstance(claim, dict)
    ]

    boundary_conditions = result.get("boundary_conditions", [])
    if not isinstance(boundary_conditions, list):
        boundary_conditions = []

    return estimates, causal_claims, boundary_conditions


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _merge_estimates(
    base: list[EstimateCandidate], extra: list[EstimateCandidate]
) -> list[EstimateCandidate]:
    seen: set[tuple[float, str, str]] = set()
    out: list[EstimateCandidate] = []
    for est in [*base, *extra]:
        key = (round(float(est.value), 8), est.unit, est.variable_hint)
        if key in seen:
            continue
        seen.add(key)
        out.append(est)
    return out


async def run_extract_llm(config: AcademicBatchConfig) -> dict[str, float | int]:
    """Selective LLM enrichment stage.

    Reads parsed/*.jsonl and writes extracted/*.jsonl.
    """
    started_at = datetime.now(UTC).isoformat()

    parsed_files = sorted(config.parsed_dir.glob("*.jsonl"))
    if not parsed_files:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "extract_llm.json",
            stage="extract_llm",
            status="ok",
            metrics={"files": 0, "records": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"records": 0, "llm_sent": 0, "llm_saved_pct": 100.0}

    runtime = GateRuntime(
        threshold=config.llm_gate_threshold,
        mode=config.llm_gate_mode,
        max_share=config.llm_gate_max_share,
        audit_max_miss_rate_pct=config.llm_gate_audit_max_miss_rate_pct,
        circuit_breaker_enabled=config.llm_gate_circuit_breaker_enabled,
    )

    llm_available = bool(config.gonka_api_key)
    stats: dict[str, float | int] = {
        "records": 0,
        "llm_candidate_total": 0,
        "llm_sent": 0,
        "auto": 0,
        "deferred": 0,
        "audit_sample_total": 0,
        "audit_miss_total": 0,
        "circuit_breaker_hits": 0,
    }
    audit_rows: list[dict[str, Any]] = []

    client_cm: Any
    if llm_available:
        client_cm = AcademicLLMClient(
            api_key=config.gonka_api_key,
            base_url=config.gonka_base_url,
            model=config.llm_model,
            temperature=config.llm_temperature,
            max_concurrent=config.max_concurrent_llm,
            max_retries=config.llm_max_retries,
            rate_limit_rps=config.llm_rate_limit_rps,
        )
    else:
        client_cm = _NullAsyncContext()

    async with client_cm as client:
        for parsed_path in parsed_files:
            out_path = config.extracted_dir / parsed_path.name
            rows_out: list[str] = []

            with open(parsed_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = adapt_jsonl_work_record_claims(
                        json.loads(line), provenance="legacy_jsonl"
                    )
                    stats["records"] = int(stats["records"]) + 1

                    features = build_gate_features(rec)
                    llm_candidate_total = int(stats["llm_candidate_total"])
                    llm_sent = int(stats["llm_sent"])
                    llm_share = (llm_sent / llm_candidate_total) if llm_candidate_total > 0 else 0.0

                    decision = decide_route(
                        runtime=runtime,
                        gate_enabled=config.llm_gate_enabled,
                        llm_available=llm_available,
                        llm_share=llm_share,
                        auto_conf_threshold=config.llm_gate_auto_conf_threshold,
                        min_score_force_llm=config.llm_gate_min_score_force_llm,
                        features=features,
                        audit_sample_rate=config.llm_gate_audit_sample_rate,
                        audit_seed=f"{rec.id}:{rec.year}:{rec.cited_by_count}",
                    )

                    if decision.route in {"llm", "audit_llm"}:
                        stats["llm_candidate_total"] = int(stats["llm_candidate_total"]) + 1
                        stats["llm_sent"] = int(stats["llm_sent"]) + 1
                        if decision.route == "audit_llm":
                            stats["audit_sample_total"] = int(stats["audit_sample_total"]) + 1

                        topic_hint = (
                            rec.source_topics[0].topic_display_name
                            if rec.source_topics
                            else "general"
                        )
                        llm_result = await extract_with_llm(
                            abstract=rec.abstract,
                            topic=topic_hint,
                            work_id=rec.id,
                            client=client,
                        )
                        est_extra, claims_extra, boundary_extra = parse_llm_result(llm_result)

                        if decision.route == "audit_llm":
                            deterministic_count = len(rec.estimates)
                            llm_count = len(est_extra)
                            miss = int(llm_count > deterministic_count)
                            if miss:
                                stats["audit_miss_total"] = int(stats["audit_miss_total"]) + 1
                            audit_rows.append(
                                {
                                    "work_id": rec.id,
                                    "route": decision.route,
                                    "gate_score": decision.score,
                                    "deterministic_estimates": deterministic_count,
                                    "llm_estimates": llm_count,
                                    "miss": miss,
                                }
                            )

                        rec.estimates = _merge_estimates(rec.estimates, est_extra)
                        rec.causal_claims = [*rec.causal_claims, *claims_extra]
                        rec.boundary_conditions = [*rec.boundary_conditions, *boundary_extra]
                        rec.extraction_mode = "llm_enriched"
                        rec.extraction_confidence = min(1.0, max(rec.extraction_confidence, 0.8))
                    elif decision.route == "auto":
                        stats["auto"] = int(stats["auto"]) + 1
                    else:
                        stats["deferred"] = int(stats["deferred"]) + 1

                    rec.llm_gate_route = decision.route
                    rec.llm_gate_score = decision.score
                    rec.llm_gate_reasons = decision.reason_codes
                    rows_out.append(rec.model_dump_json())

                    audit_total = int(stats["audit_sample_total"])
                    if audit_total > 0:
                        miss_rate = (int(stats["audit_miss_total"]) * 100.0) / audit_total
                        if runtime.register_audit_miss_rate(miss_rate):
                            stats["circuit_breaker_hits"] = runtime.circuit_breaker_hits

            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as out_fh:
                for row in rows_out:
                    out_fh.write(row + "\n")

    # audit + gate manifests
    config.llm_gate_audit_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.llm_gate_audit_path, "w", encoding="utf-8") as fh:
        for row in audit_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    llm_candidate_total = int(stats["llm_candidate_total"])
    llm_sent = int(stats["llm_sent"])
    llm_saved_pct = 100.0
    if llm_candidate_total > 0:
        llm_saved_pct = max(0.0, ((llm_candidate_total - llm_sent) * 100.0) / llm_candidate_total)
    audit_miss_rate_pct = 0.0
    if int(stats["audit_sample_total"]) > 0:
        audit_miss_rate_pct = (int(stats["audit_miss_total"]) * 100.0) / int(
            stats["audit_sample_total"]
        )

    gate_payload = {
        "kind": "llm_gate",
        "run_id": config.run_id,
        "pass_name": config.pass_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "metrics": {
            **stats,
            "llm_saved_pct": llm_saved_pct,
            "audit_miss_rate_pct": audit_miss_rate_pct,
        },
    }
    config.llm_gate_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.llm_gate_manifest_path, "w", encoding="utf-8") as fh:
        json.dump(gate_payload, fh, ensure_ascii=False, indent=2)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "extract_llm.json",
        stage="extract_llm",
        status="ok",
        metrics={
            **{k: int(v) if isinstance(v, bool | int) else v for k, v in stats.items()},
            "llm_saved_pct": round(llm_saved_pct, 3),
            "audit_miss_rate_pct": round(audit_miss_rate_pct, 3),
            "llm_available": int(llm_available),
        },
        artifacts=[config.llm_gate_audit_path, config.llm_gate_manifest_path],
        started_at=started_at,
    )

    return {
        "records": int(stats["records"]),
        "llm_sent": llm_sent,
        "llm_saved_pct": round(llm_saved_pct, 3),
        "audit_miss_rate_pct": round(audit_miss_rate_pct, 3),
    }


class _NullAsyncContext:
    async def __aenter__(self) -> _NullAsyncContext:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None
