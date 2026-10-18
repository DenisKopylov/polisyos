"""Serious-run phase barrier ledger contracts.

ADR-0148 makes phase barriers runtime authority, not bundle-local narration.
This module keeps the barrier records small and explicit so scorecard,
readiness, artifact compilation, and canary closeout can all consume the same
fail-closed evidence.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SERIOUS_PROFILES = frozenset({"research", "governed", "production"})


class PhaseBarrierError(ValueError):
    """Raised when a serious-run phase barrier cannot satisfy ADR-0148."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        barrier_id: str | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.barrier_id = barrier_id
        self.field = field


class PhaseBarrierId(StrEnum):
    """Named ADR-0148 barriers used by serious runtime guards."""

    POLICY_INTENT_CANONICALIZATION = "policy_intent_canonicalization"
    LEX_LEGAL_COMPATIBILITY = "lex_legal_compatibility"
    FABRIC_DATA_BACKING = "fabric_data_backing"
    FOUNDRY_METHOD_BACKING = "foundry_method_backing"
    SCIENTIST_WORKFLOW = "scientist_workflow"
    FINAL_DECISION_ARTIFACT = "final_decision_artifact"
    RUNTIME_REFS_FOR_SCORECARD = "runtime_refs_for_scorecard"
    SCORECARD_IDENTITY_VERIFIED = "scorecard_identity_verified"
    FINAL_COMPILER_GATES = "final_compiler_gates"
    CANARY_BUNDLE_CLOSEOUT = "canary_bundle_closeout"

    @classmethod
    def scorecard_required(cls) -> tuple[PhaseBarrierId, ...]:
        """Barriers that must pass before `ready_for_scorecard`."""

        return (
            cls.POLICY_INTENT_CANONICALIZATION,
            cls.LEX_LEGAL_COMPATIBILITY,
            cls.FABRIC_DATA_BACKING,
            cls.FOUNDRY_METHOD_BACKING,
            cls.SCIENTIST_WORKFLOW,
            cls.RUNTIME_REFS_FOR_SCORECARD,
        )

    @classmethod
    def final_artifact_required(cls) -> tuple[PhaseBarrierId, ...]:
        """Barriers required before final decision artifact compilation."""

        return (
            cls.LEX_LEGAL_COMPATIBILITY,
            cls.FABRIC_DATA_BACKING,
            cls.FOUNDRY_METHOD_BACKING,
            cls.SCIENTIST_WORKFLOW,
            cls.FINAL_DECISION_ARTIFACT,
        )

    @classmethod
    def public_artifact_required(cls) -> tuple[PhaseBarrierId, ...]:
        """Barriers required before public or exportable artifacts."""

        return (
            cls.FINAL_DECISION_ARTIFACT,
            cls.SCORECARD_IDENTITY_VERIFIED,
            cls.FINAL_COMPILER_GATES,
        )


class PhaseBarrierStatus(StrEnum):
    """Barrier closure state."""

    PASSED = "pass"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


PHASE_BARRIER_REQUIRED_EVIDENCE: Mapping[PhaseBarrierId, tuple[str, ...]] = {
    PhaseBarrierId.POLICY_INTENT_CANONICALIZATION: (
        "tenant_id",
        "requested_profile",
        "run_id",
        "time_context_ref",
        "same_input_closure_ref",
    ),
    PhaseBarrierId.LEX_LEGAL_COMPATIBILITY: (
        "lex_retrieval",
        "candidate_norms",
        "selected_norms",
        "rejected_norms",
        "legal_snapshot",
        "jurisdiction_filters",
        "time_filters",
        "conflict_checks",
    ),
    PhaseBarrierId.FABRIC_DATA_BACKING: (
        "fabric_source_selection",
        "candidate_datasets",
        "selected_datasets",
        "rejected_datasets",
        "data_quality",
        "lineage",
        "freshness",
        "semantic_binding",
    ),
    PhaseBarrierId.FOUNDRY_METHOD_BACKING: (
        "foundry_method_selection",
        "rejected_methods",
        "assumptions",
        "input_coverage",
        "power_sample_adequacy",
        "sensitivity",
        "uncertainty",
        "method_compatibility",
    ),
    PhaseBarrierId.SCIENTIST_WORKFLOW: (
        "skipped_nodes",
        "claim_ledger",
        "grounding",
        "citation_faithfulness",
        "claim_refs",
    ),
    PhaseBarrierId.FINAL_DECISION_ARTIFACT: (
        "legal_evidence",
        "data_evidence",
        "method_evidence",
        "grounding_evidence",
        "conflict_evidence",
        "security_evidence",
        "privacy_evidence",
        "licensing_evidence",
        "retention_evidence",
        "export_evidence",
        "ownership_evidence",
        "replay_evidence",
        "resilience_evidence",
        "performance_evidence",
        "human_review_evidence",
    ),
    PhaseBarrierId.RUNTIME_REFS_FOR_SCORECARD: (
        "authority_runtime_refs",
        "diagnostic_event_refs",
        "cas_artifact_refs",
    ),
    PhaseBarrierId.SCORECARD_IDENTITY_VERIFIED: (
        "scorecard_ref_identity",
        "scorecard_payload_identity",
        "scorecard_schema_compatibility",
        "scorecard_gate_semantics",
    ),
    PhaseBarrierId.FINAL_COMPILER_GATES: (
        "final_compiler_gate_report",
        "public_export_policy",
        "redaction_policy",
    ),
    PhaseBarrierId.CANARY_BUNDLE_CLOSEOUT: (
        "runtime_state_not_blocked",
        "runtime_state_not_failed",
        "bundle_packaging_only",
    ),
}


class PhaseBarrierBlocker(BaseModel):
    """Typed blocker that may close a barrier without upgrading authority."""

    model_config = ConfigDict(frozen=True, extra="allow")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(default="high", min_length=1)
    next_action: str = Field(min_length=1)
    blocking: bool = True
    may_satisfy_downstream_authority: bool = False
    non_overridable: bool = True

    @field_validator("code", "message", "severity", "next_action")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)


class PhaseBarrierRecord(BaseModel):
    """One persisted barrier result for a serious run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    barrier_id: PhaseBarrierId
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    status: PhaseBarrierStatus
    required_evidence: tuple[str, ...] = Field(default=())
    satisfied_evidence: tuple[str, ...] = Field(default=())
    missing_evidence: tuple[str, ...] = Field(default=())
    evidence_refs: tuple[str, ...] = Field(default=())
    blocker: PhaseBarrierBlocker | None = None
    runtime_event_ref: str | None = None
    cas_ref: str | None = None
    reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str = "polisyos.runtime.quality.phase_barriers"

    @model_validator(mode="before")
    @classmethod
    def _default_evidence_fields(cls, payload: object) -> object:
        if not isinstance(payload, Mapping):
            return payload
        data = dict(payload)
        barrier = PhaseBarrierId(data["barrier_id"])
        required = tuple(
            str(item)
            for item in data.get("required_evidence") or PHASE_BARRIER_REQUIRED_EVIDENCE[barrier]
        )
        satisfied = tuple(str(item) for item in data.get("satisfied_evidence") or ())
        data["required_evidence"] = required
        data["satisfied_evidence"] = satisfied
        if "missing_evidence" not in data:
            data["missing_evidence"] = tuple(
                item for item in required if item not in set(satisfied)
            )
        return data

    @field_validator("run_id", "tenant_id", "profile", "producer")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "required_evidence",
        "satisfied_evidence",
        "missing_evidence",
        "evidence_refs",
    )
    @classmethod
    def _strip_tuple_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)

    @field_validator("runtime_event_ref", "cas_ref", "reason")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _validate_barrier_semantics(self) -> Self:
        if self.profile in SERIOUS_PROFILES and not self.required_evidence:
            raise ValueError("serious barrier records must declare required evidence")
        if self.status is PhaseBarrierStatus.PASSED and self.missing_evidence:
            missing = ", ".join(self.missing_evidence)
            raise ValueError(f"pass barrier is missing required evidence: {missing}")
        if self.status is PhaseBarrierStatus.BLOCKED and self.blocker is None:
            raise ValueError("blocked barrier records require a typed blocker")
        return self

    @classmethod
    def pass_record(
        cls,
        *,
        barrier_id: PhaseBarrierId | str,
        run_id: str,
        tenant_id: str,
        profile: str,
        evidence_refs: Iterable[str],
        runtime_event_ref: str | None = None,
        cas_ref: str | None = None,
    ) -> PhaseBarrierRecord:
        """Build a passing barrier record with all ADR-required evidence satisfied."""

        barrier = PhaseBarrierId(barrier_id)
        required = PHASE_BARRIER_REQUIRED_EVIDENCE[barrier]
        return cls(
            barrier_id=barrier,
            run_id=run_id,
            tenant_id=tenant_id,
            profile=profile,
            status=PhaseBarrierStatus.PASSED,
            required_evidence=required,
            satisfied_evidence=required,
            missing_evidence=(),
            evidence_refs=tuple(evidence_refs),
            runtime_event_ref=runtime_event_ref,
            cas_ref=cas_ref,
        )

    @classmethod
    def blocked_record(
        cls,
        *,
        barrier_id: PhaseBarrierId | str,
        run_id: str,
        tenant_id: str,
        profile: str,
        missing_evidence: Iterable[str],
        blocker: PhaseBarrierBlocker | Mapping[str, Any],
        evidence_refs: Iterable[str] = (),
        runtime_event_ref: str | None = None,
        cas_ref: str | None = None,
    ) -> PhaseBarrierRecord:
        """Build a typed blocked barrier record."""

        barrier = PhaseBarrierId(barrier_id)
        required = PHASE_BARRIER_REQUIRED_EVIDENCE[barrier]
        missing = tuple(_non_empty(value) for value in missing_evidence)
        blocker_model = (
            blocker
            if isinstance(blocker, PhaseBarrierBlocker)
            else PhaseBarrierBlocker.model_validate(dict(blocker))
        )
        return cls(
            barrier_id=barrier,
            run_id=run_id,
            tenant_id=tenant_id,
            profile=profile,
            status=PhaseBarrierStatus.BLOCKED,
            required_evidence=required,
            satisfied_evidence=tuple(item for item in required if item not in set(missing)),
            missing_evidence=missing,
            evidence_refs=tuple(evidence_refs),
            blocker=blocker_model,
            runtime_event_ref=runtime_event_ref,
            cas_ref=cas_ref,
        )

    @classmethod
    def skipped_record(
        cls,
        *,
        barrier_id: PhaseBarrierId | str,
        run_id: str,
        tenant_id: str,
        profile: str,
        reason: str,
    ) -> PhaseBarrierRecord:
        """Build a skipped record; consumers must treat it as non-authoritative."""

        barrier = PhaseBarrierId(barrier_id)
        return cls(
            barrier_id=barrier,
            run_id=run_id,
            tenant_id=tenant_id,
            profile=profile,
            status=PhaseBarrierStatus.SKIPPED,
            required_evidence=PHASE_BARRIER_REQUIRED_EVIDENCE[barrier],
            satisfied_evidence=(),
            reason=_non_empty(reason),
        )

    def to_payload(self) -> dict[str, Any]:
        """Return a stable JSON-safe ledger payload."""

        return self.model_dump(mode="json")


def _reconcile_phase_barrier_subjects(
    barriers: Iterable[PhaseBarrierRecord],
    *,
    expected_run_id: str | None = None,
    expected_tenant_id: str | None = None,
    expected_profile: str | None = None,
) -> tuple[PhaseBarrierRecord, ...]:
    """Reconcile every candidate to one persisted run, tenant, and profile."""

    records = tuple(barriers)
    if not records:
        return records

    anchor = records[0]
    for field in ("run_id", "tenant_id", "profile"):
        expected = getattr(anchor, field)
        for record in records[1:]:
            if getattr(record, field) != expected:
                raise PhaseBarrierError(
                    "phase_barrier_scope_mismatch",
                    f"Phase barrier candidates disagree on {field}.",
                    field=field,
                )

    for field, expected in (
        ("run_id", expected_run_id),
        ("tenant_id", expected_tenant_id),
        ("profile", expected_profile),
    ):
        if expected is not None and getattr(anchor, field) != expected:
            raise PhaseBarrierError(
                "phase_barrier_scope_mismatch",
                f"Phase barrier candidates do not match the declared {field}.",
                field=field,
            )
    return records


_EXECUTION_OWNER_BINDING_FIELDS = frozenset(
    {
        "job_id",
        "run_id",
        "tenant_id",
        "cell_id",
        "requested_execution_profile",
        "effective_execution_profile",
        "attempt",
        "lease_owner",
    }
)


def _validated_execution_owner_binding(
    value: object,
    *,
    expected: Mapping[str, object] | None = None,
) -> dict[str, object] | None:
    """Validate one owner projection, preserving only an explicit profile omission."""

    if not isinstance(value, Mapping) or not _EXECUTION_OWNER_BINDING_FIELDS.issubset(value):
        return None
    binding = {key: value[key] for key in _EXECUTION_OWNER_BINDING_FIELDS}
    string_fields = _EXECUTION_OWNER_BINDING_FIELDS - {
        "attempt",
        "requested_execution_profile",
    }
    if any(
        not isinstance(binding.get(field), str)
        or not str(binding[field]).strip()
        or str(binding[field]) != str(binding[field]).strip()
        for field in string_fields
    ):
        return None
    requested_profile = binding["requested_execution_profile"]
    if requested_profile is not None and (
        not isinstance(requested_profile, str)
        or not requested_profile.strip()
        or requested_profile != requested_profile.strip()
    ):
        return None
    attempt = binding.get("attempt")
    if type(attempt) is not int or attempt < 1:
        return None
    if expected is not None:
        for field, expected_value in expected.items():
            if field not in _EXECUTION_OWNER_BINDING_FIELDS:
                return None
            actual = binding.get(field)
            if type(actual) is not type(expected_value) or actual != expected_value:
                return None
    return binding


def _execution_owner_binding_from_admission(
    admission: object,
    *,
    expected_job_id: str,
    expected_run_id: str,
    expected_effective_profile: str | None = None,
    expected_scope: Mapping[str, object] | None = None,
) -> dict[str, object] | None:
    """Project one live lease admission after reconciling its persisted owner scope.

    Callers must obtain ``admission`` from the control store's
    ``current_execution_job_admission`` resolver. The resulting mapping is a
    transport projection; it is not accepted as proof without a consumer check.
    """

    job = getattr(admission, "job", None)
    scope = getattr(admission, "scope", None)
    if job is None or scope is None:
        return None
    if getattr(job, "state", None) != "running":
        return None
    if getattr(scope, "status", None) != "established":
        return None
    attempt = getattr(admission, "attempt", None)
    if type(attempt) is not int or attempt < 1 or attempt != getattr(job, "attempt", None):
        return None
    missing_requested_profile = object()
    requested_profile = getattr(job, "requested_execution_profile", missing_requested_profile)
    if requested_profile is missing_requested_profile:
        return None
    raw = {
        "job_id": getattr(job, "job_id", None),
        "run_id": getattr(job, "run_id", None),
        "tenant_id": getattr(scope, "tenant_id", None),
        "cell_id": getattr(scope, "cell_id", None),
        "requested_execution_profile": requested_profile,
        "effective_execution_profile": getattr(job, "effective_execution_profile", None),
        "attempt": attempt,
        "lease_owner": getattr(job, "lease_owner", None),
    }
    expected: dict[str, object] = {
        "job_id": expected_job_id,
        "run_id": expected_run_id,
    }
    if expected_effective_profile is not None:
        expected["effective_execution_profile"] = expected_effective_profile
    for key, value in (expected_scope or {}).items():
        if key in {"tenant_id", "cell_id"}:
            expected[key] = value
        else:
            return None
    return _validated_execution_owner_binding(raw, expected=expected)


def _phase_barrier_owner_scope_not_established() -> PhaseBarrierError:
    """Return the current typed refusal for absent producer-owned scope proof."""

    return PhaseBarrierError(
        "phase_barrier_owner_scope_not_established",
        "No producer-owned phase-barrier scope bridge is established for serious authority.",
        field="owner_scope",
    )


class PhaseBarrierLedger:
    """Append-only JSONL persistence for phase barrier records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: PhaseBarrierRecord) -> None:
        """Append one barrier record to the ledger."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_payload(), sort_keys=True) + "\n")

    def records(self) -> tuple[PhaseBarrierRecord, ...]:
        """Load every record from the ledger."""

        if not self.path.exists():
            return ()
        loaded: list[PhaseBarrierRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            loaded.append(PhaseBarrierRecord.model_validate(json.loads(line)))
        return tuple(loaded)

    def records_for_run(self, run_id: str) -> tuple[PhaseBarrierRecord, ...]:
        """Return all records for a run in append order."""

        normalized = _non_empty(run_id)
        return tuple(record for record in self.records() if record.run_id == normalized)

    def latest(
        self,
        *,
        run_id: str,
        barrier_id: PhaseBarrierId | str,
    ) -> PhaseBarrierRecord | None:
        """Return the latest record for one run/barrier pair."""

        barrier = PhaseBarrierId(barrier_id)
        scoped = _reconcile_phase_barrier_subjects(
            self.records_for_run(run_id),
            expected_run_id=_non_empty(run_id),
        )
        matches = tuple(record for record in scoped if record.barrier_id is barrier)
        return matches[-1] if matches else None


def latest_barrier_record(
    barrier_id: PhaseBarrierId | str,
    *,
    barriers: Iterable[PhaseBarrierRecord],
) -> PhaseBarrierRecord | None:
    """Return the latest candidate after reconciling the complete supplied set."""

    barrier = PhaseBarrierId(barrier_id)
    scoped = _reconcile_phase_barrier_subjects(barriers)
    matches = tuple(record for record in scoped if record.barrier_id is barrier)
    return matches[-1] if matches else None


def assert_barrier_closed(
    barrier_id: PhaseBarrierId | str,
    *,
    barriers: Iterable[PhaseBarrierRecord],
) -> PhaseBarrierRecord:
    """Require a barrier to have either passed or emitted a typed blocker."""

    barrier = PhaseBarrierId(barrier_id)
    record = latest_barrier_record(barrier, barriers=barriers)
    if record is None:
        raise PhaseBarrierError(
            "phase_barrier_missing",
            f"Missing phase barrier record: {barrier.value}.",
            barrier_id=barrier.value,
        )
    if record.status is PhaseBarrierStatus.SKIPPED:
        raise PhaseBarrierError(
            "phase_barrier_skipped",
            f"Skipped phase barrier cannot satisfy serious closeout: {barrier.value}.",
            barrier_id=barrier.value,
        )
    if record.status is PhaseBarrierStatus.BLOCKED and record.blocker is None:
        raise PhaseBarrierError(
            "phase_barrier_blocker_missing",
            f"Blocked phase barrier lacks a typed blocker: {barrier.value}.",
            barrier_id=barrier.value,
        )
    return record


def assert_barrier_passed(
    barrier_id: PhaseBarrierId | str,
    *,
    barriers: Iterable[PhaseBarrierRecord],
) -> PhaseBarrierRecord:
    """Require candidate status to pass; this does not establish owner scope."""

    barrier = PhaseBarrierId(barrier_id)
    record = assert_barrier_closed(barrier, barriers=barriers)
    if record.status is PhaseBarrierStatus.BLOCKED:
        raise PhaseBarrierError(
            "phase_barrier_blocked",
            f"Blocked phase barrier prevents downstream authority: {barrier.value}.",
            barrier_id=barrier.value,
        )
    if record.status is not PhaseBarrierStatus.PASSED:
        raise PhaseBarrierError(
            "phase_barrier_not_passed",
            f"Phase barrier is not pass: {barrier.value}.",
            barrier_id=barrier.value,
        )
    return record


def _non_empty(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("value must be non-empty")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


PhaseBarrierViolation = PhaseBarrierError

__all__ = [
    "PHASE_BARRIER_REQUIRED_EVIDENCE",
    "PhaseBarrierBlocker",
    "PhaseBarrierError",
    "PhaseBarrierId",
    "PhaseBarrierLedger",
    "PhaseBarrierRecord",
    "PhaseBarrierStatus",
    "PhaseBarrierViolation",
    "assert_barrier_closed",
    "assert_barrier_passed",
    "latest_barrier_record",
]
