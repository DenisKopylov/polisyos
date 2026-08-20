"""Longitudinal calibration ledger and historical-prior influence firewall."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    SchemaInfo,
)
from polisyos.core.artifacts import (
    PutOptions as ArtifactWriteOptions,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality.memory_influence import (
    CLAIM_EVIDENCE_SLOT_KEYS as CLAIM_EVIDENCE_SLOT_KEYS,
)
from polisyos.runtime.quality.memory_influence import (
    _payload_provenance_values,
    _ProvenancePayloadError,
)

CALIBRATION_LEDGER_SCHEMA_VERSION = "policyos.runtime.calibration_ledger.v1"
HISTORICAL_PRIOR_INFLUENCE_SCHEMA_VERSION = (
    "policyos.runtime.historical_prior_influence.v1"
)
CALIBRATION_LEDGER_KIND = "runtime.calibration_ledger"
CALIBRATION_LEDGER_SCHEMA = "polisyos.runtime.CalibrationLedger"
CALIBRATION_LEDGER_FILENAME = "calibration_ledger.json"
CALIBRATION_LEDGER_CONTRACT_ID = "policyos.runtime.calibration_ledger"

CALIBRATION_LEDGER_PDC_REFS = ("E20", "C25", "C35", "C41")
CALIBRATION_LEDGER_PATTERN_REFS = ("P07", "P09", "P10", "P15")
CALIBRATION_MATURE_HISTORY_GATE_FEATURE_FLAG = (
    "policy_design_case.calibration_mature_history_gates"
)
DEFAULT_CALIBRATION_BEHAVIOR_TTL_SECONDS = 7 * 24 * 60 * 60

FUTURE_INFLUENCE_EFFECTS = (
    "routing_adjustment",
    "review_depth_increase",
    "uncertainty_widening",
    "evidence_budget_increase",
    "provider_model_selection",
    "authority_cap",
    "default_enablement_disable",
    "benchmark_priority",
    "scoped_high_authority_block",
)
HISTORICAL_PRIOR_FORBIDDEN_EFFECTS = (
    "current_run_evidence_closure",
    "satisfying_claim_evidence",
    "refuting_current_evidence",
    "minting_legal_authority",
    "minting_data_authority",
    "minting_method_authority",
    "minting_participation_authority",
    "hiding_current_run_deficits",
)
class CalibrationLedgerContractError(ValueError):
    """Raised when calibration ledger evidence violates its authority boundary."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.field = field


class CalibrationScope(BaseModel):
    """Bucket key used for longitudinal calibration and future influence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    data_class: str = Field(min_length=1)
    evidence_mode: str = Field(min_length=1)
    authority_level: str = Field(min_length=1)
    provider: str | None = None
    claim_family: str | None = None
    group_keys: tuple[str, ...] = Field(default=())

    @field_validator(
        "domain",
        "method_family",
        "jurisdiction",
        "data_class",
        "evidence_mode",
        "authority_level",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("provider", "claim_family")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("group_keys", mode="before")
    @classmethod
    def _coerce_group_keys(cls, values: object) -> tuple[str, ...]:
        return _text_tuple(values)

    @property
    def bucket_key(self) -> str:
        """Return a deterministic string key for scope matching."""

        parts = [
            self.domain,
            self.method_family,
            self.jurisdiction,
            self.data_class,
            self.evidence_mode,
            self.authority_level,
            self.provider or "*",
            self.claim_family or "*",
            ",".join(self.group_keys) or "*",
        ]
        return "|".join(parts)


class CalibrationMetricSnapshot(BaseModel):
    """Per-entry calibration metrics observed after outcome realization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nominal_coverage: float | None = None
    empirical_coverage: float | None = None
    signed_bias: float | None = None
    absolute_error: float | None = None
    brier_score: float | None = None
    log_score: float | None = None
    reliability_error: float | None = None
    expected_normalized_calibration_error: float | None = None
    interval_width: float | None = None
    false_pass: bool = False
    false_block: bool = False
    reversal: bool = False
    retraction: bool = False
    blocker_precision_observation: bool | None = None
    blocker_recall_observation: bool | None = None
    evidence_class_reliability: float | None = None
    group_calibration_gap: float | None = None
    risk_overprediction: float | None = None
    opportunity_suppression: float | None = None
    excessive_blocker_rate: float | None = None
    under_selection_of_ambitious_policies: float | None = None
    domain_imbalance: float | None = None


class DecisionMetricSnapshot(BaseModel):
    """Decision-quality metrics used to calibrate blockers and review posture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed_gate: bool | None = None
    material_failure: bool | None = None
    false_pass: bool = False
    false_block: bool = False
    error_opportunity: bool = True
    blocker_outcome: Literal[
        "true_positive",
        "false_positive",
        "false_negative",
        "true_negative",
    ] | None = None
    override_correct: bool | None = None
    escalation_necessary: bool | None = None


class CalibrationLedgerEntry(BaseModel):
    """One realized-outcome calibration event from a previous case or run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ledger_entry_id: str = Field(min_length=1)
    source_case_id: str | None = None
    run_id: str = Field(min_length=1)
    claim_id: str | None = None
    event_kind: Literal[
        "forecast_realized",
        "claim_confirmed",
        "claim_refuted",
        "case_superseded",
        "case_withdrawn",
        "case_retracted",
        "ddm_shift",
        "post_release_incident",
        "review_override_confirmed",
        "review_override_reversed",
    ]
    domain: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    data_class: str = Field(min_length=1)
    evidence_mode: str = Field(min_length=1)
    authority_level: str = Field(min_length=1)
    provider: str | None = None
    claim_family: str | None = None
    group_keys: tuple[str, ...] = Field(default=())
    forecast_horizon: str | None = None
    observation_window: str | None = None
    predicted_object: dict[str, Any] = Field(default_factory=dict)
    realized_object: dict[str, Any] = Field(default_factory=dict)
    calibration_metrics: CalibrationMetricSnapshot = Field(
        default_factory=CalibrationMetricSnapshot
    )
    decision_metrics: DecisionMetricSnapshot = Field(default_factory=DecisionMetricSnapshot)
    evidence_portfolio_signature: str = Field(min_length=1)
    exchangeability_signature: str = Field(min_length=1)
    status: Literal["active", "revoked", "contested", "superseded"] = "active"
    provenance_refs: tuple[str, ...] = Field(default=())
    expiry_at: datetime | None = None
    review_after: datetime | None = None

    @field_validator(
        "ledger_entry_id",
        "run_id",
        "domain",
        "method_family",
        "jurisdiction",
        "data_class",
        "evidence_mode",
        "authority_level",
        "evidence_portfolio_signature",
        "exchangeability_signature",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "source_case_id",
        "claim_id",
        "provider",
        "claim_family",
        "forecast_horizon",
        "observation_window",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("group_keys", "provenance_refs", mode="before")
    @classmethod
    def _coerce_text_tuple(cls, values: object) -> tuple[str, ...]:
        return _text_tuple(values)

    @property
    def scope(self) -> CalibrationScope:
        """Return the C25 calibration bucket for this entry."""

        return CalibrationScope(
            domain=self.domain,
            method_family=self.method_family,
            jurisdiction=self.jurisdiction,
            data_class=self.data_class,
            evidence_mode=self.evidence_mode,
            authority_level=self.authority_level,
            provider=self.provider,
            claim_family=self.claim_family,
            group_keys=self.group_keys,
        )


class CalibrationHistoryPolicy(BaseModel):
    """Governed sparse-history and mature-blocking policy for calibration influence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    maturity: str = "early_advisory"
    blocking_enabled: bool = False
    policy_ref: str | None = None
    longitudinal_evidence_ref: str | None = None
    insufficient_resolved_cases: int = Field(default=30, ge=1)
    insufficient_error_opportunities: int = Field(default=10, ge=1)
    thin_resolved_cases: int = Field(default=100, ge=1)
    thin_error_opportunities: int = Field(default=20, ge=1)
    mature_resolved_cases: int = Field(default=200, ge=1)
    mature_error_opportunities: int = Field(default=50, ge=1)
    false_pass_warn: float = 0.05
    false_pass_review: float = 0.08
    false_pass_cap: float = 0.10
    false_pass_block: float = 0.10
    undercoverage_warn_gap: float = 0.05
    undercoverage_review_gap: float = 0.08
    undercoverage_cap_gap: float = 0.10
    group_gap_warn: float = 0.05
    group_gap_review: float = 0.08
    group_gap_cap: float = 0.10
    reversal_warn: float = 0.02
    reversal_review: float = 0.04
    reversal_cap: float = 0.05
    retraction_review: float = 0.02
    retraction_cap: float = 0.03

    @property
    def permits_mature_blocking(self) -> bool:
        """Return whether longitudinal history may block a future authority path."""

        return (
            self.maturity == "mature_governed"
            and self.blocking_enabled
            and _optional_text(self.policy_ref) is not None
            and _optional_text(self.longitudinal_evidence_ref) is not None
        )

    def to_public_dict(self) -> dict[str, Any]:
        """Project policy posture without hidden defaults."""

        payload = self.model_dump(mode="json", exclude_none=True)
        payload["blocking_permitted"] = self.permits_mature_blocking
        payload["governance_boundary"] = {
            "thresholds_are_governed_config": True,
            "historical_calibration_is_current_run_evidence": False,
        }
        return payload


class CalibrationBehaviorPolicy(BaseModel):
    """Consumer-side policy for applying calibration influence to future posture.

    The ledger can identify mature adverse history, but scorecard/readiness
    consumers only turn it into a blocking gate when this governed feature flag
    posture is explicitly enabled.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mature_gate_feature_flag: str = Field(
        default=CALIBRATION_MATURE_HISTORY_GATE_FEATURE_FLAG,
        min_length=1,
    )
    mature_gate_enabled: bool = False
    governed_config_ref: str | None = None
    owner: str = Field(default="team-runtime-quality", min_length=1)
    version: str = Field(default="2026-05-23.provisional", min_length=1)
    rollback_path: str = Field(
        default=(
            "Disable policy_design_case.calibration_mature_history_gates and "
            "return calibration to advisory review posture."
        ),
        min_length=1,
    )
    ttl_seconds: int = Field(default=DEFAULT_CALIBRATION_BEHAVIOR_TTL_SECONDS, ge=1)

    @field_validator(
        "mature_gate_feature_flag",
        "owner",
        "version",
        "rollback_path",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("governed_config_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    def to_public_dict(self) -> dict[str, Any]:
        """Project the consumer policy into gate metadata."""

        return self.model_dump(mode="json", exclude_none=True)


class CalibrationBucketSummary(BaseModel):
    """Aggregated calibration posture for one longitudinal bucket."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: CalibrationScope
    history_state: Literal[
        "insufficient_history",
        "thin_history",
        "emerging_history",
        "mature_history",
    ]
    resolved_case_count: int = Field(ge=0)
    error_opportunity_count: int = Field(ge=0)
    active_entry_count: int = Field(ge=0)
    revoked_entry_count: int = Field(ge=0)
    contested_entry_count: int = Field(ge=0)
    superseded_entry_count: int = Field(ge=0)
    false_pass_rate: float | None = None
    false_block_rate: float | None = None
    reversal_rate: float | None = None
    retraction_rate: float | None = None
    average_undercoverage_gap: float | None = None
    average_group_calibration_gap: float | None = None
    average_signed_bias: float | None = None
    average_absolute_error: float | None = None
    evidence_portfolio_signatures: tuple[str, ...] = Field(default=())
    exchangeability_signatures: tuple[str, ...] = Field(default=())
    adverse_metric_codes: tuple[str, ...] = Field(default=())


class HistoricalPriorInfluenceRecord(BaseModel):
    """Authority-safe influence record produced from calibration history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.historical_prior_influence.v1"]
    influence_id: str = Field(min_length=1)
    source_ledger_ref: str | None = None
    source_entry_refs: tuple[str, ...] = Field(default=())
    target_run_id: str | None = None
    target_claim_id: str | None = None
    scope: CalibrationScope
    history_state: str = Field(min_length=1)
    influence_status: Literal[
        "no_effect",
        "warn",
        "mandatory_review",
        "readiness_capped",
        "scoped_block",
    ]
    sparse_history_non_blocking: bool
    blocking_permitted: bool
    blocking_basis: Literal["none", "governed_mature_history"]
    authority_cap: str | None = None
    review_depth: Literal["none", "standard", "heightened", "mandatory"] = "none"
    uncertainty_multiplier: float = 1.0
    evidence_budget_multiplier: float = 1.0
    provider_model_routing: Literal["unchanged", "prefer_alternative", "review_only"] = (
        "unchanged"
    )
    permitted_effects: tuple[str, ...] = Field(default=())
    forbidden_effects: tuple[str, ...] = Field(
        default=HISTORICAL_PRIOR_FORBIDDEN_EFFECTS
    )
    current_run_evidence_effect: Literal["none"] = "none"
    current_run_evidence_refs: tuple[str, ...] = Field(default=())
    claim_evidence_admissible: bool = False
    reason_codes: tuple[str, ...] = Field(default=())
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    traceability: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "source_entry_refs",
        "current_run_evidence_refs",
        "reason_codes",
        mode="before",
    )
    @classmethod
    def _coerce_text_tuple(cls, values: object) -> tuple[str, ...]:
        return _text_tuple(values)

    @field_validator("current_run_evidence_refs")
    @classmethod
    def _reject_current_run_evidence_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if values:
            raise ValueError(
                "historical_prior_current_run_evidence_refs_forbidden: "
                "Calibration influence records cannot cite current-run evidence refs."
            )
        return values

    @field_validator("claim_evidence_admissible")
    @classmethod
    def _reject_claim_evidence_admissible(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "historical_prior_claim_evidence_admissible_forbidden: "
                "Calibration influence records are never claim evidence."
            )
        return value


class CalibrationLedger(BaseModel):
    """Longitudinal calibration ledger payload plus future influence records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.calibration_ledger.v1"]
    ledger_kind: Literal["runtime.calibration_ledger"]
    contract_id: Literal["policyos.runtime.calibration_ledger"]
    generated_at: datetime
    status: Literal["pass", "warn", "blocked"]
    calibration_ledger_ref: str | None = None
    entries: tuple[CalibrationLedgerEntry, ...]
    bucket_summaries: tuple[CalibrationBucketSummary, ...]
    influence_records: tuple[HistoricalPriorInfluenceRecord, ...]
    policy: dict[str, Any]
    authority_boundary: dict[str, Any]
    capability_trace: dict[str, Any]


@dataclass(frozen=True)
class CalibrationLedgerPersistence:
    """Locations written when a calibration ledger is materialized."""

    calibration_ledger_ref: ArtifactRef
    evidence_bundle_ledger_path: Path | None = None


class CalibrationLedgerStore(Protocol):
    """Minimal CAS-like store interface needed by calibration ledger persistence."""

    def put_json(
        self,
        payload: Mapping[str, Any],
        options: ArtifactWriteOptions,
        **kwargs: object,
    ) -> ArtifactRef:
        """Persist JSON payload and return its artifact ref."""


DEFAULT_CALIBRATION_HISTORY_POLICY = CalibrationHistoryPolicy()
DEFAULT_CALIBRATION_BEHAVIOR_POLICY = CalibrationBehaviorPolicy()


def build_calibration_ledger(
    *,
    entries: Sequence[Mapping[str, Any] | CalibrationLedgerEntry],
    target_scope: Mapping[str, Any] | CalibrationScope | None = None,
    target_run_id: str | None = None,
    target_claim_id: str | None = None,
    generated_at: datetime | None = None,
    policy: CalibrationHistoryPolicy = DEFAULT_CALIBRATION_HISTORY_POLICY,
    ledger_ref: str | None = None,
) -> dict[str, Any]:
    """Build a runtime-owned longitudinal calibration ledger.

    Historical calibration is deliberately projected as future influence. The
    resulting ledger never emits current-run evidence refs and cannot satisfy or
    refute a claim by itself.
    """

    generated = _utc(generated_at)
    validated_entries = tuple(
        entry
        if isinstance(entry, CalibrationLedgerEntry)
        else CalibrationLedgerEntry.model_validate(dict(entry))
        for entry in entries
    )
    summaries = _bucket_summaries(validated_entries, policy=policy)
    influence_records = _influence_records(
        summaries,
        entries=validated_entries,
        target_scope=_scope_from(target_scope) if target_scope is not None else None,
        target_run_id=target_run_id,
        target_claim_id=target_claim_id,
        ledger_ref=ledger_ref,
        policy=policy,
    )
    status = _ledger_status(influence_records)
    ledger = CalibrationLedger(
        schema_version=CALIBRATION_LEDGER_SCHEMA_VERSION,
        ledger_kind=CALIBRATION_LEDGER_KIND,
        contract_id=CALIBRATION_LEDGER_CONTRACT_ID,
        generated_at=generated,
        status=status,
        calibration_ledger_ref=_optional_text(ledger_ref),
        entries=validated_entries,
        bucket_summaries=tuple(summaries),
        influence_records=tuple(influence_records),
        policy=policy.to_public_dict(),
        authority_boundary=_authority_boundary(),
        capability_trace={
            "research_refs": list(CALIBRATION_LEDGER_PDC_REFS),
            "pattern_refs": list(CALIBRATION_LEDGER_PATTERN_REFS),
            "reuse_classification": "extend_existing",
            "producer": "polisyos.runtime.quality.calibration_ledger.build_calibration_ledger",
            "consumer": [
                "polisyos.runtime.quality.calibration_ledger.calibration_influence_for_scope",
                "polisyos.runtime.quality.claim_registry.normalize_runtime_claim_registry",
            ],
            "semantic_test": (
                "tests/unit/runtime/quality/test_calibration_ledger.py::"
                "test_historical_prior_refs_fail_claim_registry_evidence_slots"
            ),
            "surface": "calibration_ledger_ref and evidence bundle calibration_ledger.json",
        },
    )
    return ledger.model_dump(mode="json", exclude_none=True)


def calibration_influence_for_scope(
    ledger: Mapping[str, Any] | CalibrationLedger,
    *,
    scope: Mapping[str, Any] | CalibrationScope,
    target_run_id: str | None = None,
    target_claim_id: str | None = None,
) -> dict[str, Any]:
    """Return the first influence record matching a target scope and run."""

    payload = (
        ledger.model_dump(mode="json", exclude_none=True)
        if isinstance(ledger, CalibrationLedger)
        else dict(ledger)
    )
    expected_scope = _scope_from(scope)
    for record in payload.get("influence_records") or []:
        if not isinstance(record, Mapping):
            continue
        record_scope = _scope_from(record.get("scope") or {})
        if not _scope_matches(record_scope, expected_scope):
            continue
        if target_run_id is not None and record.get("target_run_id") != target_run_id:
            continue
        if target_claim_id is not None and record.get("target_claim_id") != target_claim_id:
            continue
        return dict(record)
    raise CalibrationLedgerContractError(
        "calibration_influence_record_missing",
        "No historical-prior influence record matched the requested scope.",
        field="influence_records",
    )


def persist_calibration_ledger(
    ledger: Mapping[str, Any] | CalibrationLedger,
    *,
    store: CalibrationLedgerStore,
    evidence_bundle_path: str | Path | None = None,
) -> CalibrationLedgerPersistence:
    """Persist a calibration ledger in CAS and, when provided, an evidence bundle."""

    ledger_payload = calibration_ledger_public_export(ledger)
    ref = store.put_json(
        ledger_payload,
        ArtifactWriteOptions(
            kind=CALIBRATION_LEDGER_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=CALIBRATION_LEDGER_SCHEMA, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ledger_path = _write_evidence_bundle_ledger(
        ledger_payload=ledger_payload,
        ledger_ref=ref,
        evidence_bundle_path=evidence_bundle_path,
    )
    return CalibrationLedgerPersistence(
        calibration_ledger_ref=ref,
        evidence_bundle_ledger_path=ledger_path,
    )


def calibration_ledger_public_export(
    ledger: Mapping[str, Any] | CalibrationLedger,
) -> dict[str, Any]:
    """Return a JSON-safe, authority-boundary-preserving ledger payload."""

    if isinstance(ledger, CalibrationLedger):
        return ledger.model_dump(mode="json", exclude_none=True)
    return CalibrationLedger.model_validate(dict(ledger)).model_dump(
        mode="json",
        exclude_none=True,
    )


def calibration_behavior_scorecard_gates(
    quality_evidence: Mapping[str, Any],
    *,
    canary_kind: str,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Project calibration influence into scorecard gates without evidence closure.

    Sparse history and disabled mature gates remain non-blocking review posture.
    Mature scoped blocks become scorecard failures only when the consumer-side
    calibration behavior feature flag is enabled.
    """

    del canary_kind
    policy = _behavior_policy_from_quality_evidence(quality_evidence)
    now = _utc(generated_at)
    records, error = _calibration_behavior_records(quality_evidence)
    if error is not None:
        return [_calibration_boundary_failure_gate(error, policy=policy, generated_at=now)]
    gates: list[dict[str, Any]] = []
    for record in records:
        gates.append(
            _calibration_behavior_gate(record, policy=policy, generated_at=now)
        )
        provider_gate = _calibration_provider_gate(
            record,
            policy=policy,
            generated_at=now,
        )
        if provider_gate is not None:
            gates.append(provider_gate)
    return gates


def calibration_behavior_deficit_records(
    quality_evidence: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Project calibration readiness caps into status-deficit records.

    Sparse history intentionally emits no deficit. Readiness-cap and scoped-block
    records cap future posture while preserving the current-run evidence firewall.
    """

    policy = _behavior_policy_from_quality_evidence(quality_evidence)
    now = _utc(generated_at)
    records, error = _calibration_behavior_records(quality_evidence)
    if error is not None:
        return []
    rows: list[dict[str, Any]] = []
    for record in records:
        row = _calibration_deficit_record(record, policy=policy, generated_at=now)
        if row is not None:
            rows.append(row)
    return rows


def is_historical_prior_ref(ref: object) -> bool:
    """Return whether a ref names historical calibration or prior influence."""

    text = str(ref or "").strip().casefold()
    if not text:
        return False
    return (
        text.startswith("historical-prior-influence:")
        or text.startswith("runtime.calibration_ledger:")
        or text.startswith("calibration-ledger:")
        or "historical_prior_influence" in text
        or "historical-prior-influence" in text
        or "calibration_ledger" in text
    )


def historical_prior_claim_evidence_issues(
    row: Mapping[str, Any],
    *,
    claim_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return claim-registry issues for historical provenance anywhere in a claim."""

    try:
        provenance_values = _payload_provenance_values(row)
    except _ProvenancePayloadError as exc:
        return [
            {
                "code": "historical_prior_payload_provenance_unknown",
                "severity": "fail",
                "layer": "runtime_quality",
                "phase": "historical_priors_firewall",
                "claim_id": claim_id,
                "evidence_slot": exc.path[0] if exc.path else "$",
                "payload_path": _payload_path(exc.path) if exc.path else "$",
                "unsupported_value_type": exc.value_type,
                "message": (
                    "Historical-prior admission cannot classify a non-canonical "
                    "payload value and therefore fails closed."
                ),
                "next_action": (
                    "Resolve the value through the destination contract's canonical "
                    "payload grammar before claim-evidence admission."
                ),
                "authority_boundary": _authority_boundary(),
            }
        ]

    issues: list[dict[str, Any]] = []
    for path, ref in provenance_values:
        if not is_historical_prior_ref(ref):
            continue
        issues.append(
            {
                "code": "historical_prior_ref_not_admissible_as_claim_evidence",
                "severity": "fail",
                "layer": "runtime_quality",
                "phase": "historical_priors_firewall",
                "claim_id": claim_id,
                "evidence_slot": path[0],
                "payload_path": _payload_path(path),
                "historical_prior_ref": ref,
                "message": (
                    "Historical calibration and prior influence records may adjust "
                    "future routing, review, uncertainty, and authority caps, but "
                    "they cannot satisfy or refute current-run claim evidence."
                ),
                "next_action": (
                    "Move the historical prior ref to an influence surface and bind "
                    "the claim to current-run producer evidence, typed blockers, "
                    "limitations, or accepted deficits."
                ),
                "authority_boundary": _authority_boundary(),
            }
        )
    return issues


def _behavior_policy_from_quality_evidence(
    quality_evidence: Mapping[str, Any],
) -> CalibrationBehaviorPolicy:
    raw = (
        quality_evidence.get("calibration_behavior_policy")
        or quality_evidence.get("calibration_consumer_policy")
    )
    if isinstance(raw, CalibrationBehaviorPolicy):
        return raw
    if isinstance(raw, Mapping):
        return CalibrationBehaviorPolicy.model_validate(dict(raw))
    return DEFAULT_CALIBRATION_BEHAVIOR_POLICY


def _calibration_behavior_records(
    quality_evidence: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], Exception | None]:
    ledger = quality_evidence.get("calibration_ledger")
    if ledger is None:
        ledger = quality_evidence.get("longitudinal_calibration_ledger")
    raw_records = quality_evidence.get("historical_prior_influence_records")
    if raw_records is None:
        raw_records = quality_evidence.get("calibration_influence_records")

    try:
        if isinstance(ledger, CalibrationLedger):
            payload = ledger.model_dump(mode="json", exclude_none=True)
        elif isinstance(ledger, Mapping):
            payload = CalibrationLedger.model_validate(dict(ledger)).model_dump(
                mode="json",
                exclude_none=True,
            )
        else:
            payload = {}

        records: list[dict[str, Any]] = []
        for record in _mapping_rows(payload.get("influence_records")):
            normalized = HistoricalPriorInfluenceRecord.model_validate(record).model_dump(
                mode="json",
                exclude_none=True,
            )
            if normalized.get("source_ledger_ref") is None:
                source_ref = _optional_text(payload.get("calibration_ledger_ref"))
                if source_ref is not None:
                    normalized["source_ledger_ref"] = source_ref
            records.append(normalized)
        for record in _mapping_rows(raw_records):
            records.append(
                HistoricalPriorInfluenceRecord.model_validate(record).model_dump(
                    mode="json",
                    exclude_none=True,
                )
            )
        return records, None
    except (TypeError, ValueError) as exc:
        return [], exc


def _calibration_behavior_gate(
    record: Mapping[str, Any],
    *,
    policy: CalibrationBehaviorPolicy,
    generated_at: datetime,
) -> dict[str, Any]:
    status = _optional_text(record.get("influence_status")) or "no_effect"
    history_state = _optional_text(record.get("history_state")) or "unknown_history"
    blocking_permitted = bool(record.get("blocking_permitted"))
    cap = _optional_text(record.get("authority_cap"))
    if status == "scoped_block" and blocking_permitted and policy.mature_gate_enabled:
        code = "calibration_mature_history_scoped_block"
        gate_status = "fail"
        blocking = True
        closeout_effect = "closeout_blocked"
        review_action = "mandatory_review"
        message = "Mature governed calibration history caps this future authority path."
    elif status == "scoped_block":
        code = "calibration_mature_history_gate_feature_flag_disabled"
        gate_status = "pass"
        blocking = False
        closeout_effect = "advisory_review_not_blocking"
        review_action = "mandatory_review"
        message = (
            "Mature calibration history is adverse, but blocking gates are disabled by "
            "consumer policy."
        )
    elif status == "readiness_capped":
        code = "calibration_readiness_capped"
        gate_status = "pass"
        blocking = False
        closeout_effect = "readiness_capped_not_evidence"
        review_action = "mandatory_review"
        message = "Calibration history caps future readiness without supplying evidence."
    elif history_state in {"insufficient_history", "thin_history"}:
        code = "calibration_sparse_history_review"
        gate_status = "pass"
        blocking = False
        closeout_effect = "advisory_review_not_blocking"
        review_action = (
            "mandatory_review" if history_state == "thin_history" else "heightened_review"
        )
        message = "Sparse calibration history requires review but cannot block closeout."
    elif status == "mandatory_review":
        code = "calibration_history_mandatory_review"
        gate_status = "pass"
        blocking = False
        closeout_effect = "advisory_review_not_blocking"
        review_action = "mandatory_review"
        message = "Calibration history requests future review without evidence closure."
    else:
        code = "calibration_behavior_no_effect"
        gate_status = "pass"
        blocking = False
        closeout_effect = "none"
        review_action = "none"
        message = "Calibration history has no current future-posture effect."

    return _calibration_gate_payload(
        record,
        policy=policy,
        generated_at=generated_at,
        code=code,
        status=gate_status,
        blocking=blocking,
        stage="ops",
        layer="calibration_behavior",
        phase="longitudinal_calibration",
        message=message,
        review_action=review_action,
        closeout_effect=closeout_effect,
        readiness_cap=cap,
    )


def _calibration_provider_gate(
    record: Mapping[str, Any],
    *,
    policy: CalibrationBehaviorPolicy,
    generated_at: datetime,
) -> dict[str, Any] | None:
    routing = _optional_text(record.get("provider_model_routing")) or "unchanged"
    if routing == "unchanged":
        return None
    status = _optional_text(record.get("influence_status")) or "no_effect"
    blocking = (
        status == "scoped_block"
        and bool(record.get("blocking_permitted"))
        and policy.mature_gate_enabled
    )
    code = (
        "calibration_provider_model_review_only"
        if routing == "review_only"
        else "calibration_provider_model_alternative_preferred"
    )
    return _calibration_gate_payload(
        record,
        policy=policy,
        generated_at=generated_at,
        code=code,
        status="fail" if blocking else "pass",
        blocking=blocking,
        stage="llm",
        layer="llm_provider_quality",
        phase="calibration_behavior",
        message=(
            "Longitudinal calibration influences future provider/model routing "
            "without becoming current-run evidence."
        ),
        review_action="mandatory_review",
        closeout_effect="closeout_blocked" if blocking else "provider_review_not_blocking",
        readiness_cap=_optional_text(record.get("authority_cap")),
    )


def _calibration_gate_payload(
    record: Mapping[str, Any],
    *,
    policy: CalibrationBehaviorPolicy,
    generated_at: datetime,
    code: str,
    status: str,
    blocking: bool,
    stage: str,
    layer: str,
    phase: str,
    message: str,
    review_action: str,
    closeout_effect: str,
    readiness_cap: str | None,
) -> dict[str, Any]:
    authority_boundary = _authority_boundary_from_record(record)
    payload = {
        "name": "calibration_behavior_future_posture",
        "stage": stage,
        "code": code,
        "status": status,
        "layer": layer,
        "phase": phase,
        "message": message,
        "evidence_ref": _calibration_record_evidence_ref(record),
        "next_action": _calibration_next_action(code, policy),
        "blocking": blocking,
        "owner": policy.owner,
        "first_observed_at": generated_at.isoformat(),
        "ttl_seconds": policy.ttl_seconds,
        "feature_flag": policy.mature_gate_feature_flag,
        "feature_flag_enabled": policy.mature_gate_enabled,
        "governed_config_ref": policy.governed_config_ref,
        "rollback_path": policy.rollback_path,
        "history_state": _optional_text(record.get("history_state")),
        "influence_status": _optional_text(record.get("influence_status")),
        "sparse_history_non_blocking": bool(record.get("sparse_history_non_blocking")),
        "blocking_permitted": bool(record.get("blocking_permitted")),
        "review_action": review_action,
        "closeout_effect": closeout_effect,
        "readiness_cap": readiness_cap,
        "authority_cap": readiness_cap,
        "provider_model_routing": _optional_text(record.get("provider_model_routing")),
        "current_run_evidence_effect": "none",
        "claim_evidence_admissible": False,
        "reason_codes": list(_text_tuple(record.get("reason_codes"))),
        "authority_boundary": authority_boundary,
        "pattern_refs": ["P07", "P09", "P10"],
        "capability_state": "implemented",
        "surface": "quality_scorecard.calibration_behavior",
    }
    if readiness_cap is None:
        payload.pop("readiness_cap")
        payload.pop("authority_cap")
    if policy.governed_config_ref is None:
        payload.pop("governed_config_ref")
    claim_id = _optional_text(record.get("target_claim_id"))
    if claim_id is not None:
        payload["affected_claim"] = claim_id
    return payload


def _calibration_boundary_failure_gate(
    error: Exception,
    *,
    policy: CalibrationBehaviorPolicy,
    generated_at: datetime,
) -> dict[str, Any]:
    return {
        "name": "calibration_behavior_future_posture",
        "stage": "ops",
        "code": "calibration_influence_authority_boundary_invalid",
        "status": "fail",
        "layer": "calibration_behavior",
        "phase": "historical_priors_firewall",
        "message": (
            "Calibration influence records must preserve the historical-prior "
            f"authority boundary. {error}"
        ),
        "evidence_ref": "quality_evidence/calibration_ledger.json",
        "next_action": (
            "Remove current-run evidence refs and keep calibration influence on future "
            "routing, review, uncertainty, provider/model, or authority-cap surfaces."
        ),
        "blocking": True,
        "owner": policy.owner,
        "first_observed_at": generated_at.isoformat(),
        "ttl_seconds": policy.ttl_seconds,
        "authority_boundary": _authority_boundary(),
        "current_run_evidence_effect": "none",
        "claim_evidence_admissible": False,
        "pattern_refs": ["P07", "P09", "P10"],
    }


def _calibration_deficit_record(
    record: Mapping[str, Any],
    *,
    policy: CalibrationBehaviorPolicy,
    generated_at: datetime,
) -> dict[str, Any] | None:
    status = _optional_text(record.get("influence_status")) or "no_effect"
    if status not in {"readiness_capped", "scoped_block"}:
        return None
    cap = _optional_text(record.get("authority_cap"))
    if cap is None:
        return None
    scoped_block_enabled = (
        status == "scoped_block"
        and bool(record.get("blocking_permitted"))
        and policy.mature_gate_enabled
    )
    scope = _scope_from(record.get("scope") or {})
    claim_id = _optional_text(record.get("target_claim_id"))
    deficit_id = _calibration_deficit_id(record)
    return {
        "deficit_id": deficit_id,
        "deficit_family": "longitudinal_calibration",
        "deficit_code": status,
        "claim_ids": [claim_id] if claim_id is not None else [],
        "authority_level": scope.authority_level,
        "audience_scope": "public",
        "disposition": "hard_block" if scoped_block_enabled else "publish_with_limitation",
        "readiness_cap": cap,
        "max_audience": cap,
        "owner": policy.owner,
        "ttl_expires_at": (generated_at + timedelta(seconds=policy.ttl_seconds)).isoformat(),
        "runtime_event_ref": (
            f"event://runtime/calibration-behavior/"
            f"{_slug(deficit_id.removeprefix('calibration:'))}"
        ),
        "evidence_ref": _calibration_record_evidence_ref(record),
        "public_limitation_note": (
            "Longitudinal calibration history may cap future readiness, but "
            "cannot satisfy or refute current-run claim evidence."
        ),
        "review_refs": list(_text_tuple(record.get("source_entry_refs")))[:1],
    }


def _calibration_deficit_id(record: Mapping[str, Any]) -> str:
    run = _optional_text(record.get("target_run_id")) or "unspecified-run"
    claim = _optional_text(record.get("target_claim_id")) or "all-claims"
    return f"calibration:historical-prior:{_slug_token(run)}:{_slug_token(claim)}"


def _calibration_record_evidence_ref(record: Mapping[str, Any]) -> str:
    return (
        _optional_text(record.get("source_ledger_ref"))
        or "quality_evidence/calibration_ledger.json"
    )


def _authority_boundary_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    boundary = record.get("authority_boundary")
    if isinstance(boundary, Mapping):
        payload = dict(boundary)
        payload.setdefault("may_not_use_for", list(HISTORICAL_PRIOR_FORBIDDEN_EFFECTS))
        payload.setdefault("authoritative_for", _authority_boundary()["authoritative_for"])
        return payload
    return _authority_boundary()


def _calibration_next_action(code: str, policy: CalibrationBehaviorPolicy) -> str:
    if code == "calibration_mature_history_scoped_block":
        return (
            "Select an alternative provider/model, reduce authority, reissue with "
            "fresh evidence, or disable the governed calibration gate via rollback."
        )
    if code == "calibration_mature_history_gate_feature_flag_disabled":
        return (
            "Keep calibration advisory until "
            f"{policy.mature_gate_feature_flag} is enabled with governed config."
        )
    if code == "calibration_sparse_history_review":
        return (
            "Treat calibration as sparse-history review posture and continue to use "
            "current-run producer evidence for claim closure."
        )
    return (
        "Apply calibration only to future routing, review, provider/model choice, "
        "uncertainty posture, or authority cap."
    )


def _bucket_summaries(
    entries: Sequence[CalibrationLedgerEntry],
    *,
    policy: CalibrationHistoryPolicy,
) -> list[CalibrationBucketSummary]:
    buckets: dict[str, list[CalibrationLedgerEntry]] = defaultdict(list)
    scopes: dict[str, CalibrationScope] = {}
    for entry in entries:
        key = entry.scope.bucket_key
        buckets[key].append(entry)
        scopes[key] = entry.scope
    summaries: list[CalibrationBucketSummary] = []
    for key in sorted(buckets):
        bucket_entries = buckets[key]
        active_entries = [entry for entry in bucket_entries if entry.status == "active"]
        resolved_count = len(active_entries)
        error_count = sum(
            1 for entry in active_entries if entry.decision_metrics.error_opportunity
        )
        false_pass_count = sum(
            1
            for entry in active_entries
            if entry.decision_metrics.false_pass or entry.calibration_metrics.false_pass
        )
        false_block_count = sum(
            1
            for entry in active_entries
            if entry.decision_metrics.false_block or entry.calibration_metrics.false_block
        )
        reversal_count = sum(
            1
            for entry in active_entries
            if entry.event_kind in {"case_superseded", "review_override_reversed"}
            or entry.calibration_metrics.reversal
        )
        retraction_count = sum(
            1
            for entry in active_entries
            if entry.event_kind in {"case_withdrawn", "case_retracted"}
            or entry.calibration_metrics.retraction
        )
        undercoverage_gaps = [
            max(0.0, nominal - empirical)
            for nominal, empirical in (
                (
                    entry.calibration_metrics.nominal_coverage,
                    entry.calibration_metrics.empirical_coverage,
                )
                for entry in active_entries
            )
            if nominal is not None and empirical is not None
        ]
        group_gaps = [
            entry.calibration_metrics.group_calibration_gap
            for entry in active_entries
            if entry.calibration_metrics.group_calibration_gap is not None
        ]
        signed_bias = [
            entry.calibration_metrics.signed_bias
            for entry in active_entries
            if entry.calibration_metrics.signed_bias is not None
        ]
        absolute_error = [
            entry.calibration_metrics.absolute_error
            for entry in active_entries
            if entry.calibration_metrics.absolute_error is not None
        ]
        false_pass_rate = _rate(false_pass_count, error_count)
        false_block_rate = _rate(false_block_count, error_count)
        reversal_rate = _rate(reversal_count, resolved_count)
        retraction_rate = _rate(retraction_count, resolved_count)
        undercoverage_gap = _average(undercoverage_gaps)
        group_gap = _average(group_gaps)
        adverse_codes = _adverse_metric_codes(
            false_pass_rate=false_pass_rate,
            false_block_rate=false_block_rate,
            reversal_rate=reversal_rate,
            retraction_rate=retraction_rate,
            undercoverage_gap=undercoverage_gap,
            group_gap=group_gap,
            policy=policy,
        )
        summaries.append(
            CalibrationBucketSummary(
                scope=scopes[key],
                history_state=_history_state(
                    resolved_count,
                    error_count,
                    policy=policy,
                ),
                resolved_case_count=resolved_count,
                error_opportunity_count=error_count,
                active_entry_count=resolved_count,
                revoked_entry_count=sum(1 for entry in bucket_entries if entry.status == "revoked"),
                contested_entry_count=sum(
                    1 for entry in bucket_entries if entry.status == "contested"
                ),
                superseded_entry_count=sum(
                    1 for entry in bucket_entries if entry.status == "superseded"
                ),
                false_pass_rate=false_pass_rate,
                false_block_rate=false_block_rate,
                reversal_rate=reversal_rate,
                retraction_rate=retraction_rate,
                average_undercoverage_gap=undercoverage_gap,
                average_group_calibration_gap=group_gap,
                average_signed_bias=_average(signed_bias),
                average_absolute_error=_average(absolute_error),
                evidence_portfolio_signatures=tuple(
                    sorted(
                        {
                            entry.evidence_portfolio_signature
                            for entry in active_entries
                            if entry.evidence_portfolio_signature
                        }
                    )
                ),
                exchangeability_signatures=tuple(
                    sorted(
                        {
                            entry.exchangeability_signature
                            for entry in active_entries
                            if entry.exchangeability_signature
                        }
                    )
                ),
                adverse_metric_codes=tuple(adverse_codes),
            )
        )
    return summaries


def _influence_records(
    summaries: Sequence[CalibrationBucketSummary],
    *,
    entries: Sequence[CalibrationLedgerEntry],
    target_scope: CalibrationScope | None,
    target_run_id: str | None,
    target_claim_id: str | None,
    ledger_ref: str | None,
    policy: CalibrationHistoryPolicy,
) -> list[HistoricalPriorInfluenceRecord]:
    records: list[HistoricalPriorInfluenceRecord] = []
    entries_by_key: dict[str, list[CalibrationLedgerEntry]] = defaultdict(list)
    for entry in entries:
        entries_by_key[entry.scope.bucket_key].append(entry)
    for summary in summaries:
        if target_scope is not None and not _scope_matches(summary.scope, target_scope):
            continue
        records.append(
            _influence_record(
                summary,
                entries=entries_by_key[summary.scope.bucket_key],
                target_run_id=target_run_id,
                target_claim_id=target_claim_id,
                ledger_ref=ledger_ref,
                policy=policy,
            )
        )
    return records


def _influence_record(
    summary: CalibrationBucketSummary,
    *,
    entries: Sequence[CalibrationLedgerEntry],
    target_run_id: str | None,
    target_claim_id: str | None,
    ledger_ref: str | None,
    policy: CalibrationHistoryPolicy,
) -> HistoricalPriorInfluenceRecord:
    reason_codes = list(summary.adverse_metric_codes)
    sparse = summary.history_state in {"insufficient_history", "thin_history"}
    if summary.history_state == "insufficient_history":
        reason_codes.insert(0, "insufficient_calibration_history")
        status: Literal[
            "no_effect",
            "warn",
            "mandatory_review",
            "readiness_capped",
            "scoped_block",
        ] = "warn"
        permitted = (
            "routing_adjustment",
            "review_depth_increase",
            "uncertainty_widening",
            "evidence_budget_increase",
        )
        review_depth: Literal["none", "standard", "heightened", "mandatory"] = "heightened"
        uncertainty_multiplier = 1.15
        evidence_budget_multiplier = 1.15
        authority_cap = None
        provider_model_routing: Literal["unchanged", "prefer_alternative", "review_only"] = (
            "unchanged"
        )
    elif summary.history_state == "thin_history":
        reason_codes.insert(0, "thin_calibration_history")
        status = "mandatory_review"
        permitted = (
            "routing_adjustment",
            "review_depth_increase",
            "uncertainty_widening",
            "evidence_budget_increase",
        )
        review_depth = "mandatory"
        uncertainty_multiplier = 1.25
        evidence_budget_multiplier = 1.25
        authority_cap = None
        provider_model_routing = "unchanged"
    elif _has_cap_or_block_code(reason_codes):
        if summary.history_state == "mature_history" and policy.permits_mature_blocking:
            status = "scoped_block"
            permitted = (
                "routing_adjustment",
                "review_depth_increase",
                "uncertainty_widening",
                "evidence_budget_increase",
                "provider_model_selection",
                "authority_cap",
                "default_enablement_disable",
                "scoped_high_authority_block",
            )
            provider_model_routing = "review_only"
        else:
            status = "readiness_capped"
            permitted = (
                "routing_adjustment",
                "review_depth_increase",
                "uncertainty_widening",
                "evidence_budget_increase",
                "provider_model_selection",
                "authority_cap",
                "default_enablement_disable",
            )
            provider_model_routing = "prefer_alternative"
        review_depth = "mandatory"
        uncertainty_multiplier = 1.5
        evidence_budget_multiplier = 1.5
        authority_cap = _authority_cap_for(summary.scope.authority_level)
    elif reason_codes:
        status = "mandatory_review"
        permitted = (
            "routing_adjustment",
            "review_depth_increase",
            "uncertainty_widening",
            "evidence_budget_increase",
            "provider_model_selection",
        )
        review_depth = "mandatory"
        uncertainty_multiplier = 1.25
        evidence_budget_multiplier = 1.25
        authority_cap = None
        provider_model_routing = "prefer_alternative"
    else:
        status = "no_effect"
        permitted = ("routing_adjustment", "benchmark_priority")
        review_depth = "standard"
        uncertainty_multiplier = 1.0
        evidence_budget_multiplier = 1.0
        authority_cap = None
        provider_model_routing = "unchanged"

    blocking_permitted = status == "scoped_block" and policy.permits_mature_blocking
    return HistoricalPriorInfluenceRecord(
        schema_version=HISTORICAL_PRIOR_INFLUENCE_SCHEMA_VERSION,
        influence_id=_influence_id(summary.scope, target_run_id, target_claim_id),
        source_ledger_ref=_optional_text(ledger_ref),
        source_entry_refs=tuple(
            entry.ledger_entry_id for entry in entries if entry.status == "active"
        ),
        target_run_id=_optional_text(target_run_id),
        target_claim_id=_optional_text(target_claim_id),
        scope=summary.scope,
        history_state=summary.history_state,
        influence_status=status,
        sparse_history_non_blocking=sparse,
        blocking_permitted=blocking_permitted,
        blocking_basis="governed_mature_history" if blocking_permitted else "none",
        authority_cap=authority_cap,
        review_depth=review_depth,
        uncertainty_multiplier=uncertainty_multiplier,
        evidence_budget_multiplier=evidence_budget_multiplier,
        provider_model_routing=provider_model_routing,
        permitted_effects=permitted,
        current_run_evidence_refs=(),
        claim_evidence_admissible=False,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        authority_boundary=_authority_boundary(),
        traceability={
            "research_refs": list(CALIBRATION_LEDGER_PDC_REFS),
            "pattern_refs": list(CALIBRATION_LEDGER_PATTERN_REFS),
            "blocking_threshold_source": (
                "governed_config" if blocking_permitted else "non_blocking_or_cap_only"
            ),
            "current_run_evidence_boundary": "never_admissible",
        },
    )


def _history_state(
    resolved_count: int,
    error_count: int,
    *,
    policy: CalibrationHistoryPolicy,
) -> Literal["insufficient_history", "thin_history", "emerging_history", "mature_history"]:
    if (
        resolved_count < policy.insufficient_resolved_cases
        or error_count < policy.insufficient_error_opportunities
    ):
        return "insufficient_history"
    if resolved_count < policy.thin_resolved_cases or error_count < policy.thin_error_opportunities:
        return "thin_history"
    if (
        resolved_count < policy.mature_resolved_cases
        or error_count < policy.mature_error_opportunities
    ):
        return "emerging_history"
    return "mature_history"


def _adverse_metric_codes(
    *,
    false_pass_rate: float | None,
    false_block_rate: float | None,
    reversal_rate: float | None,
    retraction_rate: float | None,
    undercoverage_gap: float | None,
    group_gap: float | None,
    policy: CalibrationHistoryPolicy,
) -> list[str]:
    codes: list[str] = []
    if false_pass_rate is not None:
        if false_pass_rate > policy.false_pass_block:
            codes.append("false_pass_rate_above_block_threshold")
        elif false_pass_rate > policy.false_pass_cap:
            codes.append("false_pass_rate_above_cap_threshold")
        elif false_pass_rate > policy.false_pass_review:
            codes.append("false_pass_rate_above_review_threshold")
        elif false_pass_rate > policy.false_pass_warn:
            codes.append("false_pass_rate_above_warn_threshold")
    if undercoverage_gap is not None:
        if undercoverage_gap > policy.undercoverage_cap_gap:
            codes.append("interval_undercoverage_above_cap_threshold")
        elif undercoverage_gap > policy.undercoverage_review_gap:
            codes.append("interval_undercoverage_above_review_threshold")
        elif undercoverage_gap > policy.undercoverage_warn_gap:
            codes.append("interval_undercoverage_above_warn_threshold")
    if group_gap is not None:
        if group_gap > policy.group_gap_cap:
            codes.append("group_calibration_gap_above_cap_threshold")
        elif group_gap > policy.group_gap_review:
            codes.append("group_calibration_gap_above_review_threshold")
        elif group_gap > policy.group_gap_warn:
            codes.append("group_calibration_gap_above_warn_threshold")
    if reversal_rate is not None:
        if reversal_rate > policy.reversal_cap:
            codes.append("reversal_rate_above_cap_threshold")
        elif reversal_rate > policy.reversal_review:
            codes.append("reversal_rate_above_review_threshold")
        elif reversal_rate > policy.reversal_warn:
            codes.append("reversal_rate_above_warn_threshold")
    if retraction_rate is not None:
        if retraction_rate > policy.retraction_cap:
            codes.append("retraction_rate_above_cap_threshold")
        elif retraction_rate > policy.retraction_review:
            codes.append("retraction_rate_above_review_threshold")
        elif retraction_rate > 0:
            codes.append("retraction_series_observed")
    if false_block_rate is not None and false_block_rate > 0.25:
        codes.append("false_block_rate_requires_control_layer_review")
    return codes


def _has_cap_or_block_code(reason_codes: Sequence[str]) -> bool:
    return any(
        "block_threshold" in code
        or "cap_threshold" in code
        or code == "retraction_series_observed"
        for code in reason_codes
    )


def _ledger_status(records: Sequence[HistoricalPriorInfluenceRecord]) -> Literal[
    "pass",
    "warn",
    "blocked",
]:
    statuses = {record.influence_status for record in records}
    if "scoped_block" in statuses:
        return "blocked"
    if statuses - {"no_effect"}:
        return "warn"
    return "pass"


def _authority_cap_for(authority_level: str) -> str:
    normalized = authority_level.strip().casefold()
    if normalized in {"publication", "public", "production", "high_authority"}:
        return "below_publication"
    if normalized in {"governed", "serious_runtime"}:
        return "below_governed"
    return "advisory_only"


def _authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": [
            "future_routing",
            "future_review_depth",
            "future_uncertainty_posture",
            "future_evidence_budget",
            "future_provider_model_selection",
            "future_authority_cap",
        ],
        "may_not_use_for": list(HISTORICAL_PRIOR_FORBIDDEN_EFFECTS),
    }


def _write_evidence_bundle_ledger(
    *,
    ledger_payload: dict[str, Any],
    ledger_ref: ArtifactRef,
    evidence_bundle_path: str | Path | None,
) -> Path | None:
    if evidence_bundle_path is None:
        return None
    bundle_path = Path(evidence_bundle_path)
    ledger_path = (
        bundle_path
        if bundle_path.suffix.lower() == ".json"
        else bundle_path / CALIBRATION_LEDGER_FILENAME
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_payload = {
        "schema_version": "policyos.runtime.calibration_ledger_bundle_entry.v1",
        "calibration_ledger_ref": str(ledger_ref.artifact_id),
        "ledger": ledger_payload,
    }
    ledger_path.write_text(
        json.dumps(bundle_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ledger_path


def _scope_from(scope: Mapping[str, Any] | CalibrationScope) -> CalibrationScope:
    if isinstance(scope, CalibrationScope):
        return scope
    return CalibrationScope.model_validate(dict(scope))


def _scope_matches(actual: CalibrationScope, requested: CalibrationScope) -> bool:
    required_fields = (
        "domain",
        "method_family",
        "jurisdiction",
        "data_class",
        "evidence_mode",
        "authority_level",
    )
    for field in required_fields:
        if getattr(actual, field) != getattr(requested, field):
            return False
    for field in ("provider", "claim_family"):
        requested_value = getattr(requested, field)
        if requested_value is not None and getattr(actual, field) != requested_value:
            return False
    return not requested.group_keys or actual.group_keys == requested.group_keys


def _influence_id(
    scope: CalibrationScope,
    target_run_id: str | None,
    target_claim_id: str | None,
) -> str:
    suffix = scope.bucket_key.replace("|", ":").replace(",", "+")
    run = _optional_text(target_run_id) or "unspecified-run"
    claim = _optional_text(target_claim_id) or "all-claims"
    return f"historical-prior-influence:{run}:{claim}:{suffix}"


def _rate(count: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return count / denominator


def _average(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("value must not be empty")
    return text


def _text_tuple(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        text = values.strip()
        return (text,) if text else ()
    if isinstance(values, Iterable):
        output = []
        for value in values:
            text = _optional_text(value)
            if text is not None:
                output.append(text)
        return tuple(dict.fromkeys(output))
    return ()


def _payload_path(path: tuple[str, ...]) -> str:
    output = path[0]
    for part in path[1:]:
        output += part if part.startswith("[") else f".{part}"
    return output


def _mapping_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _slug_token(value: object) -> str:
    text = _optional_text(value) or "unknown"
    chars: list[str] = []
    previous_dash = False
    for char in text:
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    return "".join(chars).strip("-") or "unknown"


def _slug(value: object) -> str:
    return _slug_token(value).casefold()


__all__ = [
    "CALIBRATION_LEDGER_CONTRACT_ID",
    "CALIBRATION_LEDGER_KIND",
    "CALIBRATION_LEDGER_SCHEMA_VERSION",
    "CALIBRATION_MATURE_HISTORY_GATE_FEATURE_FLAG",
    "DEFAULT_CALIBRATION_BEHAVIOR_TTL_SECONDS",
    "HISTORICAL_PRIOR_INFLUENCE_SCHEMA_VERSION",
    "CalibrationBehaviorPolicy",
    "CalibrationBucketSummary",
    "CalibrationHistoryPolicy",
    "CalibrationLedger",
    "CalibrationLedgerContractError",
    "CalibrationLedgerEntry",
    "CalibrationLedgerPersistence",
    "CalibrationMetricSnapshot",
    "CalibrationScope",
    "DecisionMetricSnapshot",
    "HistoricalPriorInfluenceRecord",
    "build_calibration_ledger",
    "calibration_behavior_deficit_records",
    "calibration_behavior_scorecard_gates",
    "calibration_influence_for_scope",
    "calibration_ledger_public_export",
    "historical_prior_claim_evidence_issues",
    "is_historical_prior_ref",
    "persist_calibration_ledger",
]
