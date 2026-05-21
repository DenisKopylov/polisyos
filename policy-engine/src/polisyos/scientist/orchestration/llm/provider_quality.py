"""Provider/model quality ledger for deterministic and quarantined LLM lanes."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "policyos.provider_model_quality_ledger.v1"
CONTROLLED_GROUNDING_TASK_SCHEMA_VERSION = "policyos.provider_controlled_grounding_task.v1"
CONTROLLED_GROUNDING_COMPARISON_SCHEMA_VERSION = (
    "policyos.provider_controlled_grounding_comparison.v1"
)
CONTROLLED_GROUNDING_TASK_ID = "provider_controlled_grounding_task_v1"
DEFAULT_CONTROLLED_GROUNDING_SCENARIO_PACK_ID = "provider_controlled_grounding_pack_v1"
DEFAULT_CONTROLLED_GROUNDING_DATA_REF = "sha256:" + "d" * 64
DEFAULT_CONTROLLED_GROUNDING_NORM_REF = "sha256:" + "e" * 64
DEFAULT_CONTROLLED_GROUNDING_METHOD_REF = "sha256:" + "f" * 64
DEFAULT_CONTROLLED_GROUNDING_CLAIM_REF = "sha256:" + "c" * 64
MIN_CONTROLLED_GROUNDING_SAMPLES_PER_MODEL = 3
MAX_RETAINED_EVIDENCE_SAMPLES = 3
SECRET_KEY_RE = re.compile(
    r"(authorization|api[_-]?key|token|secret|password|credential)",
    re.IGNORECASE,
)
HIDDEN_ANSWER_KEYS = {
    "answer_key",
    "hidden_answer",
    "rubric_secret",
    "sentinel_string",
    "sentinel_strings",
}
_CONTROLLED_GROUNDING_REF_KEYS = ("data_ref", "norm_ref", "method_ref", "claim_ref")
_LANE_KIND_ORDER = {
    "simulated": 0,
    "quarantined_live": 1,
}


class ProviderModelQualityThresholds(BaseModel):
    """Review thresholds for per-provider/model quality drift."""

    model_config = ConfigDict(extra="forbid")

    review_schema_failure_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    demote_schema_failure_rate: float = Field(default=0.15, ge=0.0, le=1.0)
    review_grounding_failure_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    demote_grounding_failure_rate: float = Field(default=0.15, ge=0.0, le=1.0)
    review_citation_faithfulness_failure_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    demote_citation_faithfulness_failure_rate: float = Field(default=0.15, ge=0.0, le=1.0)
    review_disagreement_rate: float = Field(default=0.20, ge=0.0, le=1.0)
    demote_disagreement_rate: float = Field(default=0.40, ge=0.0, le=1.0)
    review_provider_error_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    block_provider_error_rate: float = Field(default=0.20, ge=0.0, le=1.0)
    review_context_pressure: float = Field(default=0.90, ge=0.0, le=1.0)
    block_context_pressure: float = Field(default=0.98, ge=0.0, le=1.0)
    review_selected_variant_quality: float = Field(default=0.75, ge=0.0, le=1.0)
    demote_selected_variant_quality: float = Field(default=0.60, ge=0.0, le=1.0)


class ProviderModelQualityObservation(BaseModel):
    """One lane-level provider/model quality observation."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str | None = None
    lane_id: str
    lane_kind: str = "simulated"
    provider: str
    model_id: str
    model_fingerprint: str
    scenario_pack_id: str
    scenario_id: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_valid: bool = True
    healing_count: int = Field(default=0, ge=0)
    json_valid: bool = True
    tool_call_valid: bool = True
    grounding_valid: bool = True
    citation_faithfulness_valid: bool = True
    disagreement_detected: bool = False
    latency_ms: float | None = Field(default=None, ge=0.0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    context_pressure: float | None = Field(default=None, ge=0.0, le=1.0)
    provider_error_code: str | None = None
    refusal_detected: bool = False
    degradation_behavior: str | None = None
    request_fingerprint: str | None = None
    selected_variant_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    quarantined: bool = False
    system_confounded: bool = False
    confounding_signal: str | None = None
    upstream_spine_blocker_refs: list[str] = Field(default_factory=list)
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize_text_fields(self) -> ProviderModelQualityObservation:
        self.lane_kind = _clean_text(self.lane_kind, fallback="simulated")
        self.provider = _clean_text(self.provider, fallback="unknown_provider")
        self.model_id = _clean_text(self.model_id, fallback="unknown_model")
        self.model_fingerprint = _clean_text(
            self.model_fingerprint,
            fallback="unknown_fingerprint",
        )
        self.scenario_pack_id = _clean_text(
            self.scenario_pack_id,
            fallback="unknown_scenario_pack",
        )
        if self.provider_error_code is not None:
            self.provider_error_code = _clean_text(
                self.provider_error_code,
                fallback="provider_error",
            )
        if self.degradation_behavior is not None:
            self.degradation_behavior = _clean_text(
                self.degradation_behavior,
                fallback="degraded",
            )
        if self.request_fingerprint is not None:
            self.request_fingerprint = _clean_text(
                self.request_fingerprint,
                fallback="unknown_request_fingerprint",
            )
        if self.confounding_signal is not None:
            self.confounding_signal = _clean_text(
                self.confounding_signal,
                fallback="system_confounded",
            )
        self.upstream_spine_blocker_refs = [
            ref
            for ref in (
                _clean_text(item, fallback="")
                for item in self.upstream_spine_blocker_refs
            )
            if ref
        ]
        return self


class ProviderModelQualityMetrics(BaseModel):
    """Aggregated metrics for one provider/model/fingerprint key."""

    model_config = ConfigDict(extra="forbid")

    sample_count: int = 0
    decision_sample_count: int = 0
    simulated_sample_count: int = 0
    quarantined_live_sample_count: int = 0
    system_confounded_sample_count: int = 0
    schema_failure_rate: float = 0.0
    healing_count: int = 0
    healing_count_avg: float = 0.0
    json_validity_rate: float = 1.0
    tool_call_validity_rate: float = 1.0
    grounding_failure_rate: float = 0.0
    citation_faithfulness_failure_rate: float = 0.0
    disagreement_rate: float = 0.0
    latency_ms_avg: float | None = None
    latency_ms_p50: float | None = None
    latency_ms_p95: float | None = None
    cost_usd_total: float = 0.0
    cost_usd_avg: float | None = None
    context_pressure_avg: float | None = None
    context_pressure_max: float | None = None
    provider_error_rate: float = 0.0
    refusal_rate: float = 0.0
    degradation_rate: float = 0.0
    selected_variant_quality_avg: float | None = None
    selected_variant_quality_min: float | None = None


class ProviderModelQualityEntry(BaseModel):
    """A sanitized ledger row keyed by provider/model/fingerprint."""

    model_config = ConfigDict(extra="forbid")

    evidence_key: str
    provider: str
    model_id: str
    model_fingerprint: str
    scenario_pack_ids: list[str]
    evidence_lane_kinds: list[str]
    first_observed_at: datetime
    last_observed_at: datetime
    metrics: ProviderModelQualityMetrics
    drift_action: str = "approve"
    drift_reasons: list[str] = Field(default_factory=list)
    request_fingerprints: list[str] = Field(default_factory=list)
    sanitized_evidence_samples: list[dict[str, Any]] = Field(default_factory=list)


class DefaultProductionModelChoice(BaseModel):
    """One default production model choice that must have fresh evidence."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    model_fingerprint: str
    usage: str


class DefaultModelQualityReview(BaseModel):
    """Review outcome for one default production model choice."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    model_fingerprint: str
    usage: str
    evidence_key: str
    action: str
    reasons: list[str] = Field(default_factory=list)
    last_observed_at: datetime | None = None


class ProviderModelQualityLedger(BaseModel):
    """Provider/model quality drift ledger suitable for canary evidence bundles."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider_model_quality_ledger_ref: str | None = None
    entries: list[ProviderModelQualityEntry] = Field(default_factory=list)
    default_model_reviews: list[DefaultModelQualityReview] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)

    @property
    def entries_by_key(self) -> dict[str, ProviderModelQualityEntry]:
        return {entry.evidence_key: entry for entry in self.entries}


class ProviderModelComparisonRow(BaseModel):
    """A sanitized model-comparison row for one scenario pack."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    model_fingerprint: str
    evidence_key: str
    sample_count: int
    selected_variant_quality_avg: float | None
    schema_failure_rate: float
    grounding_failure_rate: float
    citation_faithfulness_failure_rate: float
    disagreement_rate: float
    refusal_rate: float = 0.0
    degradation_rate: float = 0.0
    latency_ms_avg: float | None
    cost_usd_avg: float | None
    request_fingerprints: list[str] = Field(default_factory=list)
    drift_action: str


class ProviderModelComparison(BaseModel):
    """Scenario-pack scoped comparison that excludes hidden answers."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "policyos.provider_model_quality_comparison.v1"
    scenario_pack_id: str
    generated_at: datetime
    rankings: list[ProviderModelComparisonRow]


class ControlledGroundingTask(BaseModel):
    """Frozen tiny evidence-bound task for provider/model quality decisions."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = CONTROLLED_GROUNDING_TASK_SCHEMA_VERSION
    task_id: str = CONTROLLED_GROUNDING_TASK_ID
    scenario_pack_id: str = DEFAULT_CONTROLLED_GROUNDING_SCENARIO_PACK_ID
    data_ref: str = DEFAULT_CONTROLLED_GROUNDING_DATA_REF
    norm_ref: str = DEFAULT_CONTROLLED_GROUNDING_NORM_REF
    method_ref: str = DEFAULT_CONTROLLED_GROUNDING_METHOD_REF
    claim_ref: str = DEFAULT_CONTROLLED_GROUNDING_CLAIM_REF
    expected_response_schema: dict[str, str] = Field(
        default_factory=lambda: dict.fromkeys(_CONTROLLED_GROUNDING_REF_KEYS, "sha256")
    )

    @property
    def required_evidence_refs(self) -> dict[str, str]:
        return {
            "data_ref": self.data_ref,
            "norm_ref": self.norm_ref,
            "method_ref": self.method_ref,
            "claim_ref": self.claim_ref,
        }


class ControlledProviderModelComparisonRow(BaseModel):
    """Controlled grounding metrics for one candidate provider/model."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    model_fingerprint: str
    evidence_key: str
    sample_count: int
    schema_failure_rate: float
    grounding_failure_rate: float
    refusal_rate: float
    degradation_rate: float
    latency_ms_avg: float | None
    latency_ms_p95: float | None
    cost_usd_total: float
    cost_usd_avg: float | None
    selected_variant_quality_avg: float | None
    request_fingerprints: list[str] = Field(default_factory=list)
    drift_action: str
    drift_reasons: list[str] = Field(default_factory=list)


class ControlledProviderModelComparison(BaseModel):
    """Controlled provider/model comparison over frozen evidence refs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = CONTROLLED_GROUNDING_COMPARISON_SCHEMA_VERSION
    generated_at: datetime
    controlled_task: ControlledGroundingTask
    min_samples_per_model: int
    rows: list[ControlledProviderModelComparisonRow]
    default_model_gate: dict[str, Any]
    summary: dict[str, Any]


def provider_model_evidence_key(
    *,
    provider: str,
    model_id: str,
    model_fingerprint: str,
) -> str:
    """Return the stable ledger key for a provider/model/fingerprint tuple."""
    return (
        f"provider:{_safe_key_part(provider)}"
        f"|model:{_safe_key_part(model_id)}"
        f"|fingerprint:{_safe_key_part(model_fingerprint)}"
    )


def build_provider_model_quality_ledger(
    observations: Iterable[ProviderModelQualityObservation | Mapping[str, Any]],
    *,
    default_model_choices: Iterable[DefaultProductionModelChoice | Mapping[str, Any]]
    | None = None,
    generated_at: datetime | None = None,
    thresholds: ProviderModelQualityThresholds | None = None,
    max_evidence_age_days: int = 14,
    hidden_answer_tokens: Iterable[str] | None = None,
) -> ProviderModelQualityLedger:
    """Aggregate lane observations into a sanitized provider/model quality ledger."""
    generated = _ensure_aware_utc(generated_at or datetime.now(UTC))
    active_thresholds = thresholds or ProviderModelQualityThresholds()
    hidden_tokens = {
        token for token in (str(item) for item in hidden_answer_tokens or []) if token
    }
    grouped: dict[str, list[ProviderModelQualityObservation]] = defaultdict(list)
    parsed_observations = [
        item
        if isinstance(item, ProviderModelQualityObservation)
        else ProviderModelQualityObservation.model_validate(item)
        for item in observations
    ]
    for observation in parsed_observations:
        grouped[
            provider_model_evidence_key(
                provider=observation.provider,
                model_id=observation.model_id,
                model_fingerprint=observation.model_fingerprint,
            )
        ].append(observation)

    entries = [
        _build_entry(
            evidence_key=evidence_key,
            observations=items,
            thresholds=active_thresholds,
            hidden_answer_tokens=hidden_tokens,
        )
        for evidence_key, items in sorted(grouped.items())
    ]
    entry_index = {entry.evidence_key: entry for entry in entries}
    choices = [
        item
        if isinstance(item, DefaultProductionModelChoice)
        else DefaultProductionModelChoice.model_validate(item)
        for item in default_model_choices or []
    ]
    reviews = [
        _review_default_model_choice(
            choice,
            entry_index=entry_index,
            generated_at=generated,
            max_evidence_age_days=max_evidence_age_days,
        )
        for choice in choices
    ]
    summary = _ledger_summary(
        observations=parsed_observations,
        entries=entries,
        reviews=reviews,
    )
    ledger = ProviderModelQualityLedger(
        generated_at=generated,
        entries=entries,
        default_model_reviews=reviews,
        summary=summary,
    )
    ledger.provider_model_quality_ledger_ref = _ledger_ref(ledger)
    return ledger


def compare_provider_models(
    ledger: ProviderModelQualityLedger,
    *,
    scenario_pack_id: str,
) -> ProviderModelComparison:
    """Compare provider/model entries by stable scenario pack id only."""
    rows: list[ProviderModelComparisonRow] = []
    for entry in ledger.entries:
        if scenario_pack_id not in entry.scenario_pack_ids:
            continue
        metrics = entry.metrics
        rows.append(
            ProviderModelComparisonRow(
                provider=entry.provider,
                model_id=entry.model_id,
                model_fingerprint=entry.model_fingerprint,
                evidence_key=entry.evidence_key,
                sample_count=metrics.decision_sample_count,
                selected_variant_quality_avg=metrics.selected_variant_quality_avg,
                schema_failure_rate=metrics.schema_failure_rate,
                grounding_failure_rate=metrics.grounding_failure_rate,
                citation_faithfulness_failure_rate=(
                    metrics.citation_faithfulness_failure_rate
                ),
                disagreement_rate=metrics.disagreement_rate,
                refusal_rate=metrics.refusal_rate,
                degradation_rate=metrics.degradation_rate,
                latency_ms_avg=metrics.latency_ms_avg,
                cost_usd_avg=metrics.cost_usd_avg,
                request_fingerprints=list(entry.request_fingerprints),
                drift_action=entry.drift_action,
            )
        )
    rows.sort(
        key=lambda row: (
            -(
                row.selected_variant_quality_avg
                if row.selected_variant_quality_avg is not None
                else -1
            ),
            row.schema_failure_rate,
            row.grounding_failure_rate,
            row.latency_ms_avg if row.latency_ms_avg is not None else float("inf"),
            row.evidence_key,
        )
    )
    return ProviderModelComparison(
        scenario_pack_id=scenario_pack_id,
        generated_at=ledger.generated_at,
        rankings=rows,
    )


def controlled_grounding_task() -> ControlledGroundingTask:
    """Return the frozen evidence-bound provider quality task."""

    return ControlledGroundingTask()


def build_controlled_grounding_observation(
    *,
    provider: str,
    model_id: str,
    model_fingerprint: str,
    sample_index: int,
    task: ControlledGroundingTask | Mapping[str, Any] | None = None,
    observed_at: datetime | None = None,
    grounding_refs: Mapping[str, str] | None = None,
    schema_valid: bool = True,
    refusal_detected: bool = False,
    degradation_behavior: str | None = None,
    request_fingerprint: str | None = None,
    latency_ms: float | None = None,
    cost_usd: float | None = None,
    raw_evidence: Mapping[str, Any] | None = None,
) -> ProviderModelQualityObservation:
    """Build one observation for the controlled grounding task."""

    resolved_task = _controlled_task(task)
    expected_refs = resolved_task.required_evidence_refs
    observed_refs = dict(grounding_refs or expected_refs)
    refs_complete = all(_clean_text(observed_refs.get(key), fallback="") for key in expected_refs)
    grounding_valid = refs_complete and all(
        observed_refs.get(key) == value for key, value in expected_refs.items()
    )
    request_fp = request_fingerprint or _request_fingerprint(
        provider=provider,
        model_id=model_id,
        model_fingerprint=model_fingerprint,
        task_id=resolved_task.task_id,
        sample_index=sample_index,
    )
    selected_quality = 0.95 if schema_valid and grounding_valid and not refusal_detected else 0.40
    evidence = {
        "controlled_grounding_task": resolved_task.required_evidence_refs,
        "observed_grounding_refs": observed_refs,
        "request_fingerprint": request_fp,
    }
    if raw_evidence:
        evidence.update(dict(raw_evidence))
    return ProviderModelQualityObservation(
        observation_id=f"{resolved_task.task_id}:{_safe_key_part(model_id)}:{sample_index}",
        lane_id=f"controlled-grounding:{_safe_key_part(model_id)}:{sample_index}",
        lane_kind="quarantined_live",
        provider=provider,
        model_id=model_id,
        model_fingerprint=model_fingerprint,
        scenario_pack_id=resolved_task.scenario_pack_id,
        scenario_id=resolved_task.task_id,
        observed_at=observed_at or datetime.now(UTC),
        schema_valid=bool(schema_valid and refs_complete and not refusal_detected),
        healing_count=0,
        json_valid=bool(schema_valid),
        tool_call_valid=True,
        grounding_valid=bool(grounding_valid and not refusal_detected),
        citation_faithfulness_valid=bool(grounding_valid and not refusal_detected),
        disagreement_detected=False,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        context_pressure=0.05,
        provider_error_code=None,
        refusal_detected=refusal_detected,
        degradation_behavior=degradation_behavior,
        request_fingerprint=request_fp,
        selected_variant_quality=selected_quality,
        quarantined=True,
        raw_evidence=evidence,
    )


def build_controlled_provider_model_comparison(
    observations: Iterable[ProviderModelQualityObservation | Mapping[str, Any]],
    *,
    candidate_models: Iterable[DefaultProductionModelChoice | Mapping[str, Any]],
    default_model_choice: DefaultProductionModelChoice | Mapping[str, Any],
    task: ControlledGroundingTask | Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
    thresholds: ProviderModelQualityThresholds | None = None,
    min_samples_per_model: int = MIN_CONTROLLED_GROUNDING_SAMPLES_PER_MODEL,
    hidden_answer_tokens: Iterable[str] | None = None,
) -> ControlledProviderModelComparison:
    """Compare candidate models on the frozen controlled grounding task."""

    resolved_task = _controlled_task(task)
    generated = _ensure_aware_utc(generated_at or datetime.now(UTC))
    candidates: list[DefaultProductionModelChoice] = []
    for item in candidate_models:
        if isinstance(item, DefaultProductionModelChoice):
            candidates.append(item)
            continue
        if isinstance(item, Mapping):
            payload = dict(item)
            payload.setdefault("usage", "candidate")
            candidates.append(DefaultProductionModelChoice.model_validate(payload))
    default_choice = (
        default_model_choice
        if isinstance(default_model_choice, DefaultProductionModelChoice)
        else DefaultProductionModelChoice.model_validate(default_model_choice)
    )
    parsed_observations = [
        item
        if isinstance(item, ProviderModelQualityObservation)
        else ProviderModelQualityObservation.model_validate(item)
        for item in observations
    ]
    controlled_observations = [
        observation
        for observation in parsed_observations
        if observation.scenario_pack_id == resolved_task.scenario_pack_id
    ]
    ledger = build_provider_model_quality_ledger(
        controlled_observations,
        default_model_choices=[default_choice],
        generated_at=generated,
        thresholds=thresholds,
        hidden_answer_tokens=hidden_answer_tokens,
    )
    rows: list[ControlledProviderModelComparisonRow] = []
    entry_index = ledger.entries_by_key
    for candidate in candidates:
        evidence_key = provider_model_evidence_key(
            provider=candidate.provider,
            model_id=candidate.model_id,
            model_fingerprint=candidate.model_fingerprint,
        )
        entry = entry_index.get(evidence_key)
        if entry is None:
            rows.append(
                ControlledProviderModelComparisonRow(
                    provider=candidate.provider,
                    model_id=candidate.model_id,
                    model_fingerprint=candidate.model_fingerprint,
                    evidence_key=evidence_key,
                    sample_count=0,
                    schema_failure_rate=1.0,
                    grounding_failure_rate=1.0,
                    refusal_rate=0.0,
                    degradation_rate=0.0,
                    latency_ms_avg=None,
                    latency_ms_p95=None,
                    cost_usd_total=0.0,
                    cost_usd_avg=None,
                    selected_variant_quality_avg=None,
                    request_fingerprints=[],
                    drift_action="block_production_approval",
                    drift_reasons=["controlled_quality_evidence_missing"],
                )
            )
            continue
        metrics = entry.metrics
        rows.append(
            ControlledProviderModelComparisonRow(
                provider=entry.provider,
                model_id=entry.model_id,
                model_fingerprint=entry.model_fingerprint,
                evidence_key=entry.evidence_key,
                sample_count=metrics.decision_sample_count,
                schema_failure_rate=metrics.schema_failure_rate,
                grounding_failure_rate=metrics.grounding_failure_rate,
                refusal_rate=metrics.refusal_rate,
                degradation_rate=metrics.degradation_rate,
                latency_ms_avg=metrics.latency_ms_avg,
                latency_ms_p95=metrics.latency_ms_p95,
                cost_usd_total=metrics.cost_usd_total,
                cost_usd_avg=metrics.cost_usd_avg,
                selected_variant_quality_avg=metrics.selected_variant_quality_avg,
                request_fingerprints=list(entry.request_fingerprints),
                drift_action=entry.drift_action,
                drift_reasons=list(entry.drift_reasons),
            )
        )
    rows.sort(
        key=lambda row: (
            -row.sample_count,
            row.schema_failure_rate,
            row.grounding_failure_rate,
            row.latency_ms_avg if row.latency_ms_avg is not None else float("inf"),
            row.evidence_key,
        )
    )
    default_gate = _controlled_default_model_gate(
        default_choice=default_choice,
        rows=rows,
        ledger=ledger,
        min_samples_per_model=max(1, int(min_samples_per_model)),
    )
    summary = _controlled_comparison_summary(
        rows=rows,
        default_gate=default_gate,
        min_samples_per_model=max(1, int(min_samples_per_model)),
    )
    return ControlledProviderModelComparison(
        generated_at=generated,
        controlled_task=resolved_task,
        min_samples_per_model=max(1, int(min_samples_per_model)),
        rows=rows,
        default_model_gate=default_gate,
        summary=summary,
    )


def _controlled_default_model_gate(
    *,
    default_choice: DefaultProductionModelChoice,
    rows: list[ControlledProviderModelComparisonRow],
    ledger: ProviderModelQualityLedger,
    min_samples_per_model: int,
) -> dict[str, Any]:
    evidence_key = provider_model_evidence_key(
        provider=default_choice.provider,
        model_id=default_choice.model_id,
        model_fingerprint=default_choice.model_fingerprint,
    )
    row = next((item for item in rows if item.evidence_key == evidence_key), None)
    review = next(
        (
            item
            for item in ledger.default_model_reviews
            if item.evidence_key == evidence_key
        ),
        None,
    )
    reasons: list[str] = []
    if row is None:
        reasons.append("controlled_default_model_evidence_missing")
        sample_count = 0
        drift_action = "block_production_approval"
    else:
        sample_count = row.sample_count
        drift_action = row.drift_action
        if row.sample_count < min_samples_per_model:
            reasons.append("controlled_sample_count_below_minimum")
        if row.drift_action == "demote":
            reasons.append("controlled_default_model_demoted")
        elif row.drift_action == "require_review":
            reasons.append("controlled_default_model_requires_review")
        reasons.extend(row.drift_reasons)
    if review is not None and review.action == "block_production_approval":
        reasons.extend(review.reasons)
    reasons = sorted(set(reasons))
    if not reasons:
        action = "approve"
    elif "controlled_default_model_requires_review" in reasons and all(
        reason == "controlled_default_model_requires_review"
        or reason in (row.drift_reasons if row is not None else [])
        for reason in reasons
    ):
        action = "require_review"
    else:
        action = "block_production_approval"
    return {
        "provider": default_choice.provider,
        "model_id": default_choice.model_id,
        "model_fingerprint": default_choice.model_fingerprint,
        "usage": default_choice.usage,
        "evidence_key": evidence_key,
        "action": action,
        "reasons": reasons,
        "sample_count": sample_count,
        "required_sample_count": min_samples_per_model,
        "drift_action": drift_action,
    }


def _controlled_comparison_summary(
    *,
    rows: list[ControlledProviderModelComparisonRow],
    default_gate: Mapping[str, Any],
    min_samples_per_model: int,
) -> dict[str, Any]:
    under_sampled = [
        row.evidence_key for row in rows if row.sample_count < min_samples_per_model
    ]
    action = str(default_gate.get("action") or "")
    if action == "approve" and not under_sampled:
        status = "pass"
    elif action == "require_review":
        status = "warn"
    else:
        status = "fail"
    return {
        "status": status,
        "candidate_count": len(rows),
        "under_sampled_candidate_count": len(under_sampled),
        "under_sampled_evidence_keys": under_sampled,
        "min_samples_per_model": min_samples_per_model,
        "default_model_action": action,
    }


def _controlled_task(
    task: ControlledGroundingTask | Mapping[str, Any] | None,
) -> ControlledGroundingTask:
    if isinstance(task, ControlledGroundingTask):
        return task
    if isinstance(task, Mapping):
        return ControlledGroundingTask.model_validate(task)
    return controlled_grounding_task()


def _request_fingerprint(
    *,
    provider: str,
    model_id: str,
    model_fingerprint: str,
    task_id: str,
    sample_index: int,
) -> str:
    payload = json.dumps(
        {
            "provider": provider,
            "model_id": model_id,
            "model_fingerprint": model_fingerprint,
            "task_id": task_id,
            "sample_index": sample_index,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitize_provider_quality_payload(
    value: object,
    *,
    hidden_answer_tokens: Iterable[str] | None = None,
    key_hint: str | None = None,
) -> object:
    """Recursively sanitize evidence without preserving credentials or answers."""
    hidden_tokens = set(hidden_answer_tokens or ())
    normalized_key = str(key_hint or "").replace("-", "_").casefold()
    if normalized_key in HIDDEN_ANSWER_KEYS:
        return "[redacted_hidden_answer]"
    if key_hint and SECRET_KEY_RE.search(key_hint):
        return _redacted_secret(value)
    if isinstance(value, Mapping):
        return {
            str(key): sanitize_provider_quality_payload(
                item,
                hidden_answer_tokens=hidden_tokens,
                key_hint=str(key),
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            sanitize_provider_quality_payload(
                item,
                hidden_answer_tokens=hidden_tokens,
                key_hint=key_hint,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            sanitize_provider_quality_payload(
                item,
                hidden_answer_tokens=hidden_tokens,
                key_hint=key_hint,
            )
            for item in value
        ]
    if isinstance(value, str):
        redacted = value
        for token in hidden_tokens:
            if token and token in redacted:
                redacted = redacted.replace(token, "[redacted_hidden_answer]")
        return redacted
    return value


def _build_entry(
    *,
    evidence_key: str,
    observations: list[ProviderModelQualityObservation],
    thresholds: ProviderModelQualityThresholds,
    hidden_answer_tokens: set[str],
) -> ProviderModelQualityEntry:
    observations = sorted(
        observations,
        key=lambda observation: (
            _ensure_aware_utc(observation.observed_at),
            observation.lane_id,
        ),
    )
    first = observations[0]
    metrics = _metrics(observations)
    drift_action, drift_reasons = _drift_decision(metrics, thresholds=thresholds)
    if metrics.system_confounded_sample_count:
        drift_reasons = sorted(
            set([*drift_reasons, "system_confounded_samples_excluded"])
        )
        if metrics.decision_sample_count <= 0:
            drift_action = "require_review"
            drift_reasons = sorted(
                set([*drift_reasons, "controlled_evidence_bound_task_required"])
            )
        elif drift_action == "approve":
            drift_action = "require_review"
    return ProviderModelQualityEntry(
        evidence_key=evidence_key,
        provider=first.provider,
        model_id=first.model_id,
        model_fingerprint=first.model_fingerprint,
        scenario_pack_ids=sorted({item.scenario_pack_id for item in observations}),
        evidence_lane_kinds=sorted(
            {item.lane_kind for item in observations},
            key=lambda item: (_LANE_KIND_ORDER.get(item, 99), item),
        ),
        first_observed_at=_ensure_aware_utc(observations[0].observed_at),
        last_observed_at=_ensure_aware_utc(observations[-1].observed_at),
        metrics=metrics,
        drift_action=drift_action,
        drift_reasons=drift_reasons,
        request_fingerprints=sorted(
            {
                item.request_fingerprint
                for item in observations
                if item.request_fingerprint is not None
            }
        ),
        sanitized_evidence_samples=[
            sanitize_provider_quality_payload(
                _observation_evidence_sample(item),
                hidden_answer_tokens=hidden_answer_tokens,
            )
            for item in observations[:MAX_RETAINED_EVIDENCE_SAMPLES]
            if item.raw_evidence or item.system_confounded
        ],
    )


def _metrics(
    observations: list[ProviderModelQualityObservation],
) -> ProviderModelQualityMetrics:
    count = len(observations)
    decision_observations = [
        item for item in observations if not item.system_confounded
    ]
    decision_count = len(decision_observations)
    latencies = [item.latency_ms for item in decision_observations if item.latency_ms is not None]
    costs = [item.cost_usd for item in decision_observations if item.cost_usd is not None]
    context_pressures = [
        item.context_pressure
        for item in decision_observations
        if item.context_pressure is not None
    ]
    selected_quality = [
        item.selected_variant_quality
        for item in decision_observations
        if item.selected_variant_quality is not None
    ]
    return ProviderModelQualityMetrics(
        sample_count=count,
        decision_sample_count=decision_count,
        simulated_sample_count=sum(1 for item in observations if item.lane_kind == "simulated"),
        quarantined_live_sample_count=sum(
            1
            for item in observations
            if item.lane_kind == "quarantined_live" or item.quarantined
        ),
        system_confounded_sample_count=sum(
            1 for item in observations if item.system_confounded
        ),
        schema_failure_rate=_rate(
            sum(1 for item in decision_observations if not item.schema_valid),
            decision_count,
        ),
        healing_count=sum(item.healing_count for item in decision_observations),
        healing_count_avg=_rate(
            sum(item.healing_count for item in decision_observations),
            decision_count,
        ),
        json_validity_rate=_rate(
            sum(1 for item in decision_observations if item.json_valid),
            decision_count,
        ),
        tool_call_validity_rate=_rate(
            sum(1 for item in decision_observations if item.tool_call_valid),
            decision_count,
        ),
        grounding_failure_rate=_rate(
            sum(1 for item in decision_observations if not item.grounding_valid),
            decision_count,
        ),
        citation_faithfulness_failure_rate=_rate(
            sum(
                1
                for item in decision_observations
                if not item.citation_faithfulness_valid
            ),
            decision_count,
        ),
        disagreement_rate=_rate(
            sum(1 for item in decision_observations if item.disagreement_detected),
            decision_count,
        ),
        latency_ms_avg=_avg(latencies),
        latency_ms_p50=_round_float(median(latencies)) if latencies else None,
        latency_ms_p95=_percentile(latencies, 0.95),
        cost_usd_total=_round_float(sum(costs)) if costs else 0.0,
        cost_usd_avg=_avg(costs),
        context_pressure_avg=_avg(context_pressures),
        context_pressure_max=(
            _round_float(max(context_pressures)) if context_pressures else None
        ),
        provider_error_rate=_rate(
            sum(1 for item in decision_observations if item.provider_error_code),
            decision_count,
        ),
        refusal_rate=_rate(
            sum(1 for item in decision_observations if item.refusal_detected),
            decision_count,
        ),
        degradation_rate=_rate(
            sum(1 for item in decision_observations if item.degradation_behavior),
            decision_count,
        ),
        selected_variant_quality_avg=_avg(selected_quality),
        selected_variant_quality_min=(
            _round_float(min(selected_quality)) if selected_quality else None
        ),
    )


def _drift_decision(
    metrics: ProviderModelQualityMetrics,
    *,
    thresholds: ProviderModelQualityThresholds,
) -> tuple[str, list[str]]:
    demote_reasons: list[str] = []
    review_reasons: list[str] = []
    _append_if(
        demote_reasons,
        "schema_failure_rate",
        metrics.schema_failure_rate >= thresholds.demote_schema_failure_rate,
    )
    _append_if(
        demote_reasons,
        "grounding_failure_rate",
        metrics.grounding_failure_rate >= thresholds.demote_grounding_failure_rate,
    )
    _append_if(
        demote_reasons,
        "citation_faithfulness_failure_rate",
        metrics.citation_faithfulness_failure_rate
        >= thresholds.demote_citation_faithfulness_failure_rate,
    )
    _append_if(
        demote_reasons,
        "disagreement_rate",
        metrics.disagreement_rate >= thresholds.demote_disagreement_rate,
    )
    _append_if(
        demote_reasons,
        "provider_error_rate",
        metrics.provider_error_rate >= thresholds.block_provider_error_rate,
    )
    if metrics.context_pressure_max is not None:
        _append_if(
            demote_reasons,
            "context_pressure",
            metrics.context_pressure_max >= thresholds.block_context_pressure,
        )
    if metrics.selected_variant_quality_avg is not None:
        _append_if(
            demote_reasons,
            "selected_variant_quality",
            metrics.selected_variant_quality_avg
            < thresholds.demote_selected_variant_quality,
        )

    if demote_reasons:
        return "demote", sorted(set(demote_reasons))

    _append_if(
        review_reasons,
        "schema_failure_rate",
        metrics.schema_failure_rate >= thresholds.review_schema_failure_rate,
    )
    _append_if(
        review_reasons,
        "grounding_failure_rate",
        metrics.grounding_failure_rate >= thresholds.review_grounding_failure_rate,
    )
    _append_if(
        review_reasons,
        "citation_faithfulness_failure_rate",
        metrics.citation_faithfulness_failure_rate
        >= thresholds.review_citation_faithfulness_failure_rate,
    )
    _append_if(
        review_reasons,
        "disagreement_rate",
        metrics.disagreement_rate >= thresholds.review_disagreement_rate,
    )
    _append_if(
        review_reasons,
        "provider_error_rate",
        metrics.provider_error_rate >= thresholds.review_provider_error_rate,
    )
    if metrics.context_pressure_max is not None:
        _append_if(
            review_reasons,
            "context_pressure",
            metrics.context_pressure_max >= thresholds.review_context_pressure,
        )
    if metrics.selected_variant_quality_avg is not None:
        _append_if(
            review_reasons,
            "selected_variant_quality",
            metrics.selected_variant_quality_avg
            < thresholds.review_selected_variant_quality,
        )
    if review_reasons:
        return "require_review", sorted(set(review_reasons))
    return "approve", []


def _review_default_model_choice(
    choice: DefaultProductionModelChoice,
    *,
    entry_index: dict[str, ProviderModelQualityEntry],
    generated_at: datetime,
    max_evidence_age_days: int,
) -> DefaultModelQualityReview:
    evidence_key = provider_model_evidence_key(
        provider=choice.provider,
        model_id=choice.model_id,
        model_fingerprint=choice.model_fingerprint,
    )
    entry = entry_index.get(evidence_key)
    if entry is None:
        return DefaultModelQualityReview(
            provider=choice.provider,
            model_id=choice.model_id,
            model_fingerprint=choice.model_fingerprint,
            usage=choice.usage,
            evidence_key=evidence_key,
            action="block_production_approval",
            reasons=["quality_evidence_missing"],
        )

    stale_cutoff = generated_at - timedelta(days=max(0, max_evidence_age_days))
    if entry.last_observed_at < stale_cutoff:
        return DefaultModelQualityReview(
            provider=choice.provider,
            model_id=choice.model_id,
            model_fingerprint=choice.model_fingerprint,
            usage=choice.usage,
            evidence_key=evidence_key,
            action="block_production_approval",
            reasons=["quality_evidence_stale"],
            last_observed_at=entry.last_observed_at,
        )

    return DefaultModelQualityReview(
        provider=choice.provider,
        model_id=choice.model_id,
        model_fingerprint=choice.model_fingerprint,
        usage=choice.usage,
        evidence_key=evidence_key,
        action=entry.drift_action,
        reasons=list(entry.drift_reasons),
        last_observed_at=entry.last_observed_at,
    )


def _ledger_summary(
    *,
    observations: list[ProviderModelQualityObservation],
    entries: list[ProviderModelQualityEntry],
    reviews: list[DefaultModelQualityReview],
) -> dict[str, Any]:
    review_actions = {review.action for review in reviews}
    entry_actions = {entry.drift_action for entry in entries}
    if (
        "block_production_approval" in review_actions
        or "demote" in review_actions
        or "demote" in entry_actions
    ):
        status = "fail"
    elif "require_review" in review_actions or "require_review" in entry_actions:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "observation_count": len(observations),
        "decision_observation_count": sum(
            1 for item in observations if not item.system_confounded
        ),
        "system_confounded_observations": sum(
            1 for item in observations if item.system_confounded
        ),
        "entry_count": len(entries),
        "simulated_observations": sum(
            1 for item in observations if item.lane_kind == "simulated"
        ),
        "quarantined_live_observations": sum(
            1
            for item in observations
            if item.lane_kind == "quarantined_live" or item.quarantined
        ),
        "default_model_review_count": len(reviews),
        "default_model_actions": sorted(review_actions),
        "entry_actions": sorted(entry_actions),
    }


def _observation_evidence_sample(
    observation: ProviderModelQualityObservation,
) -> dict[str, Any]:
    sample = dict(observation.raw_evidence or {})
    if observation.system_confounded:
        sample["system_confounded"] = True
        sample["confounding_signal"] = (
            observation.confounding_signal or "upstream_evidence_spine_incomplete"
        )
        sample["upstream_spine_blocker_refs"] = list(
            observation.upstream_spine_blocker_refs
        )
    return sample


def _ledger_ref(ledger: ProviderModelQualityLedger) -> str:
    payload = ledger.model_dump(mode="json", exclude={"provider_model_quality_ledger_ref"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _rate(numerator: float, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round_float(numerator / denominator)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return _round_float(sum(values) / len(values))


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return _round_float(ordered[index])


def _round_float(value: float) -> float:
    return round(float(value), 6)


def _append_if(items: list[str], value: str, condition: bool) -> None:
    if condition:
        items.append(value)


def _clean_text(value: object, *, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if any(char in text for char in "\r\n\t"):
        return fallback
    lowered = text.casefold()
    if SECRET_KEY_RE.search(text) or lowered.startswith(("sk-", "bearer ")):
        return fallback
    return text[:256]


def _safe_key_part(value: str) -> str:
    text = _clean_text(value, fallback="unknown")
    return text.replace("|", "_").replace("\n", "_").replace("\r", "_")


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _redacted_secret(value: object) -> dict[str, object]:
    if value in (None, "", [], {}):
        return {"present": False}
    return {
        "present": True,
        "fingerprint": "sha256:"
        + hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12],
    }


__all__ = [
    "CONTROLLED_GROUNDING_TASK_ID",
    "DEFAULT_CONTROLLED_GROUNDING_SCENARIO_PACK_ID",
    "MIN_CONTROLLED_GROUNDING_SAMPLES_PER_MODEL",
    "SCHEMA_VERSION",
    "ControlledGroundingTask",
    "ControlledProviderModelComparison",
    "ControlledProviderModelComparisonRow",
    "DefaultModelQualityReview",
    "DefaultProductionModelChoice",
    "ProviderModelComparison",
    "ProviderModelComparisonRow",
    "ProviderModelQualityEntry",
    "ProviderModelQualityLedger",
    "ProviderModelQualityMetrics",
    "ProviderModelQualityObservation",
    "ProviderModelQualityThresholds",
    "build_controlled_grounding_observation",
    "build_controlled_provider_model_comparison",
    "build_provider_model_quality_ledger",
    "compare_provider_models",
    "controlled_grounding_task",
    "provider_model_evidence_key",
    "sanitize_provider_quality_payload",
]
