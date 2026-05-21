"""Production approval packet derivation and persistence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.control import (
    ProductionApprovalEligibility,
    ProductionApprovalOverridePacket,
    ProductionApprovalOverrideRequest,
    ProductionApprovalPacket,
)
from polisyos.runtime.quality.human_review import evaluate_review_packet
from polisyos.runtime.quality.invariants import load_production_invariant_registry
from polisyos.runtime.quality.schema_compat import (
    PRODUCTION_CLOSEOUT_BLOCKING_DECISIONS,
    evaluate_schema_compatibility,
)
from polisyos.runtime.quality.source_truth import (
    SourceTruthContractError,
    detect_source_truth_conflict,
    load_source_truth_lattice,
)

APPROVAL_PACKET_KIND = "runtime.production_approval_packet"
APPROVAL_PACKET_SCHEMA = "polisyos.runtime.ProductionApprovalPacket"
APPROVAL_PACKET_FILENAME = "production_approval_packet.json"

_PASS_STATUSES = {"pass", "passed", "ok", "success"}
_PERFORMANCE_BLOCKING_STATUSES = {
    "blocked",
    "degraded",
    "error",
    "fail",
    "failed",
    "missing",
    "over_budget",
    "timeout",
    "warn",
    "warning",
}
_CONFLICT_BLOCKING_STATUSES = {
    "blocked",
    "conflict",
    "error",
    "fail",
    "failed",
    "incompatible",
}
_NON_OVERRIDABLE_SCHEMA_REASONS = set(PRODUCTION_CLOSEOUT_BLOCKING_DECISIONS)
_NON_OVERRIDABLE_IDENTITY_REASONS = {
    "scorecard_identity_not_verified",
    "scorecard_identity_ref_missing",
    "scorecard_identity_ref_mismatch",
    "scorecard_projection_not_authority",
}
_NON_OVERRIDABLE_REPLAY_REASONS = {
    "replay_drift_unbounded",
    "replay_drift_unexplained",
}
_PROJECTION_AUTHORITY_ROLES = {
    "approval_input",
    "diagnostic_only",
    "not_authoritative",
    "packaging_only",
    "projection_only",
    "readiness_input",
    "scorecard_input",
}
_PROJECTION_PROVENANCE_KINDS = {
    "bundle_overlay",
    "bundle_packaged",
    "runtime_projection",
}
_NON_AUTHORITY_SCORECARD_EVIDENCE_CLASSES = {
    "debug_only",
    "diagnostic_supporting",
    "legacy_quarantined",
    "public_exported",
    "redacted_derived",
}


@dataclass(frozen=True)
class ProductionApprovalPersistence:
    """Locations written when a production approval packet is materialized."""

    approval_packet_ref: ArtifactRef
    evidence_bundle_packet_path: Path | None = None


def build_production_approval_packet(
    *,
    scorecard: Mapping[str, Any],
    override: ProductionApprovalOverrideRequest | None = None,
    artifact_ownership: Mapping[str, Any] | None = None,
    human_review_calibration_report_ref: str | None = None,
    now: datetime | None = None,
) -> ProductionApprovalPacket:
    """Derive an immutable production approval packet from one quality scorecard."""

    generated_at = _utc(now)
    scorecard_payload = _scorecard_with_source_truth_conflicts(scorecard)
    scorecard_digest = _digest(scorecard_payload)
    eligibility = _approval_eligibility(scorecard_payload)
    override_packet: ProductionApprovalOverridePacket | None = None
    reasons = list(eligibility.reasons)

    if override is not None:
        if override.expires_at <= generated_at:
            reasons.append("override_expired")
        elif _scorecard_schema_reason(eligibility) in _NON_OVERRIDABLE_SCHEMA_REASONS:
            reasons.append("schema_compatibility_not_overridable")
        elif _has_non_overridable_blocker(eligibility):
            reasons.append("non_overridable_blocker")
        elif eligibility.execution_completed and not eligibility.eligible:
            candidate_override = _build_override_packet(
                override,
                scorecard_digest=scorecard_digest,
                signed_at=generated_at,
            )
            guardrail_reasons = _override_guardrail_reasons(
                scorecard=scorecard_payload,
                override_packet=candidate_override,
                generated_at=generated_at,
            )
            if guardrail_reasons:
                reasons.extend(guardrail_reasons)
            else:
                override_packet = candidate_override

    if override_packet is not None:
        decision = "approved_with_override"
    elif eligibility.eligible:
        decision = "approved"
    else:
        decision = "blocked"

    if reasons != eligibility.reasons:
        eligibility = eligibility.model_copy(update={"reasons": sorted(set(reasons))})

    evidence_refs = {
        str(key): str(value)
        for key, value in _mapping(scorecard_payload.get("evidence_refs")).items()
        if str(key).strip() and str(value).strip()
    }
    _merge_artifact_ownership_refs(evidence_refs, artifact_ownership)
    calibration_ref = _string_or_none(
        human_review_calibration_report_ref
        or scorecard_payload.get("human_review_calibration_report_ref")
        or evidence_refs.get("human_review_calibration_report")
        or evidence_refs.get("human_review_calibration_report_ref")
    )
    if calibration_ref is not None:
        evidence_refs["human_review_calibration_report"] = calibration_ref
    scorecard_ref = _scorecard_ref(scorecard_payload)

    return ProductionApprovalPacket(
        generated_at=generated_at,
        run_id=_string_or_none(scorecard_payload.get("run_id")),
        job_id=_string_or_none(scorecard_payload.get("job_id")),
        canary_kind=_string_or_none(scorecard_payload.get("canary_kind")),
        decision=decision,
        eligibility=eligibility,
        scorecard_ref=scorecard_ref,
        scorecard_digest=scorecard_digest,
        scorecard_generated_at=_string_or_none(scorecard_payload.get("generated_at")),
        evidence_refs=evidence_refs,
        override=override_packet,
    )


def persist_production_approval_packet(
    packet: ProductionApprovalPacket,
    *,
    store: Any,
    evidence_bundle_path: str | Path | None = None,
    artifact_ownership: Mapping[str, Any] | None = None,
) -> ProductionApprovalPersistence:
    """Persist an approval packet in CAS and, when provided, in an evidence bundle."""

    packet_payload = packet.model_dump(mode="json", exclude_none=True)
    ref = store.put_json(
        packet_payload,
        ArtifactWriteOptions(
            kind=APPROVAL_PACKET_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=APPROVAL_PACKET_SCHEMA, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    bundle_packet_path = _write_evidence_bundle_packet(
        packet_payload=packet_payload,
        approval_packet_ref=ref,
        evidence_bundle_path=evidence_bundle_path,
        artifact_ownership=artifact_ownership,
    )
    return ProductionApprovalPersistence(
        approval_packet_ref=ref,
        evidence_bundle_packet_path=bundle_packet_path,
    )


def _scorecard_with_source_truth_conflicts(
    scorecard: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(scorecard)
    derived_conflicts = _approval_reader_source_truth_conflicts(payload)
    if not derived_conflicts:
        return payload
    existing = [
        dict(item)
        for item in _list(payload.get("source_truth_conflicts"))
        if isinstance(item, Mapping)
    ]
    payload["source_truth_conflicts"] = [*existing, *derived_conflicts]
    evidence_refs = dict(_mapping(payload.get("evidence_refs")))
    evidence_refs.setdefault(
        "source_truth_conflicts",
        "quality_evidence/source_truth_conflicts.json",
    )
    payload["evidence_refs"] = evidence_refs
    return payload


def _approval_reader_source_truth_conflicts(
    scorecard: Mapping[str, Any],
) -> list[dict[str, Any]]:
    try:
        lattice = load_source_truth_lattice()
    except SourceTruthContractError:
        return []
    conflicts: list[dict[str, Any]] = []
    readiness = scorecard.get("readiness_result")
    api_projection = scorecard.get("api_projection")
    if isinstance(readiness, Mapping) and isinstance(api_projection, Mapping):
        fields = tuple(
            field
            for field in ("readiness", "approval_state", "publishable")
            if readiness.get(field) is not None or api_projection.get(field) is not None
        )
        if fields:
            conflict = detect_source_truth_conflict(
                field_family="approval_readiness_public_status",
                authoritative_source="runtime.readiness",
                authoritative_surface="runtime.readiness",
                authoritative_values=dict(readiness),
                conflicting_source="runtime.api",
                conflicting_surface="runtime.api",
                conflicting_values=dict(api_projection),
                fields=fields,
                downstream_impact="Approval would accept an API projection over readiness.",
                lattice=lattice,
            )
            if conflict is not None:
                conflicts.append(conflict)

    approval_packet = scorecard.get("approval_packet") or scorecard.get(
        "persisted_approval_packet"
    )
    dashboard_projection = scorecard.get("dashboard_approval_projection") or scorecard.get(
        "dashboard_projection"
    )
    if isinstance(approval_packet, Mapping) and isinstance(dashboard_projection, Mapping):
        fields = tuple(
            field
            for field in ("approval_packet_ref", "decision", "approval_state")
            if approval_packet.get(field) is not None or dashboard_projection.get(field) is not None
        )
        if fields:
            conflict = detect_source_truth_conflict(
                field_family="approval_readiness_public_status",
                authoritative_source="runtime.approval_packet",
                authoritative_surface="runtime.approval",
                authoritative_values=dict(approval_packet),
                conflicting_source="runtime.dashboard",
                conflicting_surface="runtime.dashboard",
                conflicting_values=dict(dashboard_projection),
                fields=fields,
                downstream_impact=(
                    "Dashboard projection would publish approval over the persisted packet."
                ),
                lattice=lattice,
            )
            if conflict is not None:
                conflicts.append(conflict)
    return conflicts


def _approval_eligibility(scorecard: Mapping[str, Any]) -> ProductionApprovalEligibility:
    schema_compatibility = evaluate_schema_compatibility(
        scorecard,
        reader="approval_packet_builder",
        expected_schema_family="policyos.quality_scorecard",
    )
    execution_status = _normalized_status(scorecard.get("execution_status"))
    quality_status = _normalized_status(scorecard.get("quality_status"))
    performance_status = _normalized_status(
        scorecard.get("performance_status")
        or _mapping(scorecard.get("approval_eligibility")).get("performance_status")
    )
    conflict_status = _conflict_status(scorecard)

    blocking_failures = _list(scorecard.get("blocking_quality_failures"))
    scorecard_ref = _scorecard_ref(scorecard)
    identity_reasons = _scorecard_identity_reasons(scorecard, scorecard_ref=scorecard_ref)
    replay_reasons = _replay_drift_reasons(scorecard)
    non_overridable_codes = _non_overridable_blocking_codes(scorecard)
    execution_completed = execution_status == "completed"
    quality_passed = quality_status in _PASS_STATUSES
    performance_blocking = performance_status in _PERFORMANCE_BLOCKING_STATUSES
    conflict_blocking = conflict_status in _CONFLICT_BLOCKING_STATUSES

    reasons: list[str] = []
    if not execution_completed:
        reasons.append("execution_not_completed")
    if not quality_passed:
        reasons.append("quality_not_passing")
    if blocking_failures:
        reasons.append("blocking_quality_failures")
    if performance_blocking:
        reasons.append("performance_budget_blocking")
    if conflict_blocking:
        reasons.append("conflict_blocking")
    if not schema_compatibility.production_closeout_allowed:
        reasons.append(schema_compatibility.decision)
    reasons.extend(identity_reasons)
    reasons.extend(replay_reasons)
    if identity_reasons or replay_reasons or non_overridable_codes:
        reasons.append("non_overridable_blocker")
        reasons.extend(non_overridable_codes)

    return ProductionApprovalEligibility(
        eligible=not reasons,
        execution_completed=execution_completed,
        quality_passed=quality_passed,
        blocking_failure_count=len(blocking_failures),
        performance_status=performance_status or None,
        performance_blocking=performance_blocking,
        conflict_status=conflict_status or None,
        conflict_blocking=conflict_blocking,
        reasons=sorted(set(reasons)),
    )


def _scorecard_schema_reason(eligibility: ProductionApprovalEligibility) -> str | None:
    for reason in eligibility.reasons:
        if reason in _NON_OVERRIDABLE_SCHEMA_REASONS:
            return reason
    return None


def _has_non_overridable_blocker(eligibility: ProductionApprovalEligibility) -> bool:
    non_overridable = _non_overridable_blocker_codes()
    return any(
        reason == "non_overridable_blocker"
        or reason in _NON_OVERRIDABLE_IDENTITY_REASONS
        or reason in _NON_OVERRIDABLE_REPLAY_REASONS
        or reason in non_overridable
        for reason in eligibility.reasons
    )


def _replay_drift_reasons(scorecard: Mapping[str, Any]) -> list[str]:
    candidates = [
        scorecard.get("drift_explanation"),
        scorecard.get("replay_drift_explanation"),
        scorecard.get("replay_drift"),
    ]
    quality_evidence = scorecard.get("quality_evidence")
    if isinstance(quality_evidence, Mapping):
        candidates.extend(
            [
                quality_evidence.get("drift_explanation"),
                quality_evidence.get("replay_drift_explanation"),
            ]
        )
    reasons: list[str] = []
    if any(_has_unexplained_replay_drift(candidate) for candidate in candidates):
        reasons.append("replay_drift_unexplained")
    if any(_has_unbounded_replay_drift(candidate) for candidate in candidates):
        reasons.append("replay_drift_unbounded")
    return reasons
    return []


def _has_unexplained_replay_drift(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    status = str(value.get("status") or value.get("drift_status") or "").casefold()
    if status == "unexplained_drift":
        return True
    production_readiness = str(value.get("production_readiness") or "").casefold()
    summary = _mapping(value.get("summary"))
    unexplained_count = _int_value(summary.get("unexplained_difference_count"))
    if production_readiness == "fail" and unexplained_count > 0:
        return True
    for difference in _list(value.get("differences")):
        difference_map = _mapping(difference)
        if str(difference_map.get("status") or "").casefold() == "unexplained":
            return True
    return False


def _has_unbounded_replay_drift(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    status = str(value.get("status") or value.get("drift_status") or "").casefold()
    if status == "accepted_drift_non_ready":
        return True
    production_readiness = str(value.get("production_readiness") or "").casefold()
    summary = _mapping(value.get("summary"))
    max_impact = str(summary.get("max_impact") or "").casefold()
    if production_readiness == "fail" and max_impact in {"medium", "high"}:
        return True
    blocker = _mapping(value.get("blocking_failure"))
    return blocker.get("code") == "authority_replay_drift_unbounded"


def _build_override_packet(
    override: ProductionApprovalOverrideRequest,
    *,
    scorecard_digest: str,
    signed_at: datetime,
) -> ProductionApprovalOverridePacket:
    signature = override.signature or _digest(
        {
            "reviewer_identity": override.reviewer_identity,
            "reason": override.reason,
            "scope": override.scope,
            "expires_at": override.expires_at.isoformat(),
            "evidence_refs": list(override.evidence_refs),
            "scorecard_digest": scorecard_digest,
            "signed_at": signed_at.isoformat(),
        }
    )
    return ProductionApprovalOverridePacket(
        reviewer_identity=override.reviewer_identity,
        reason=override.reason,
        scope=override.scope,
        expires_at=override.expires_at,
        evidence_refs=list(override.evidence_refs),
        signed_at=signed_at,
        signature=signature,
        metadata=dict(override.metadata),
    )


def _override_guardrail_reasons(
    *,
    scorecard: Mapping[str, Any],
    override_packet: ProductionApprovalOverridePacket,
    generated_at: datetime,
) -> list[str]:
    evaluation = evaluate_review_packet(
        {
            "schema_version": "policyos.production_approval_packet.v1",
            "generated_at": generated_at.isoformat(),
            "run_id": _string_or_none(scorecard.get("run_id")),
            "job_id": _string_or_none(scorecard.get("job_id")),
            "decision": "approved_with_override",
            "override": override_packet.model_dump(mode="json", exclude_none=True),
        },
        expected_scope=_expected_override_scope(scorecard),
        now=generated_at,
    )
    if evaluation.get("status") != "fail":
        return []
    reason_map = {
        "reviewer_attribution": "override_reviewer_attribution_missing",
        "packet_completeness": "override_packet_incomplete",
        "override_expiry": "override_expired",
        "override_scope": "override_scope_mismatch",
        "rationale_quality": "override_rationale_weak",
    }
    return [
        reason_map.get(str(check.get("code")), f"override_{check.get('code')}")
        for check in _list(evaluation.get("checks"))
        if _mapping(check).get("status") == "fail"
    ]


def _expected_override_scope(scorecard: Mapping[str, Any]) -> str | None:
    run_id = _string_or_none(scorecard.get("run_id"))
    if run_id is not None:
        return f"run:{run_id}"
    job_id = _string_or_none(scorecard.get("job_id"))
    if job_id is not None:
        return f"job:{job_id}"
    return None


def _write_evidence_bundle_packet(
    *,
    packet_payload: dict[str, Any],
    approval_packet_ref: ArtifactRef,
    evidence_bundle_path: str | Path | None,
    artifact_ownership: Mapping[str, Any] | None,
) -> Path | None:
    if evidence_bundle_path is None:
        return None
    bundle_path = Path(evidence_bundle_path)
    packet_path = (
        bundle_path
        if bundle_path.suffix.lower() == ".json"
        else bundle_path / APPROVAL_PACKET_FILENAME
    )
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_payload = {
        "schema_version": "policyos.production_approval_bundle_entry.v1",
        "approval_packet_ref": str(approval_packet_ref.artifact_id),
        "packet": packet_payload,
    }
    if artifact_ownership is not None:
        bundle_payload["artifact_ownership"] = dict(artifact_ownership)
    packet_path.write_text(
        json.dumps(bundle_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return packet_path


def _conflict_status(scorecard: Mapping[str, Any]) -> str:
    if _list(scorecard.get("source_truth_conflicts")):
        return "blocked"
    if _projection_authority_conflict(scorecard):
        return "blocked"

    explicit = _normalized_status(
        scorecard.get("conflict_status")
        or scorecard.get("policy_conflict_status")
        or scorecard.get("normative_conflict_status")
    )
    if explicit:
        return explicit

    saw_pass = False
    saw_warn = False
    for raw_gate in _list(scorecard.get("quality_gates")):
        gate = _mapping(raw_gate)
        if not _gate_mentions_conflict(gate):
            continue
        status = _normalized_status(gate.get("status"))
        blocking = bool(gate.get("blocking", True))
        if blocking and status in _CONFLICT_BLOCKING_STATUSES:
            return "blocked"
        if status in {"warn", "warning", "degraded"}:
            saw_warn = True
        if status in _PASS_STATUSES:
            saw_pass = True
    if saw_warn:
        return "warn"
    if saw_pass:
        return "pass"
    return "unknown"


def _projection_authority_conflict(scorecard: Mapping[str, Any]) -> bool:
    readiness = _mapping(scorecard.get("readiness_result"))
    api_projection = _mapping(scorecard.get("api_projection"))
    if readiness and api_projection:
        for key in ("readiness", "approval_state", "decision"):
            left = _string_or_none(readiness.get(key))
            right = _string_or_none(api_projection.get(key))
            if left is not None and right is not None and left != right:
                return True

    approval_packet = _mapping(scorecard.get("approval_packet"))
    dashboard_projection = _mapping(scorecard.get("dashboard_approval_projection"))
    if approval_packet and dashboard_projection:
        for key in ("approval_packet_ref", "decision"):
            left = _string_or_none(approval_packet.get(key))
            right = _string_or_none(dashboard_projection.get(key))
            if left is not None and right is not None and left != right:
                return True
    return False


def _scorecard_ref(scorecard: Mapping[str, Any]) -> str | None:
    evidence_refs = scorecard.get("evidence_refs")
    if not isinstance(evidence_refs, Mapping):
        evidence_refs = {}
    return _string_or_none(
        scorecard.get("quality_scorecard_ref")
        or scorecard.get("scorecard_ref")
        or evidence_refs.get("quality_scorecard")
    )


def _scorecard_identity_reasons(
    scorecard: Mapping[str, Any],
    *,
    scorecard_ref: str | None,
) -> list[str]:
    reasons: list[str] = []
    if scorecard_ref is None:
        reasons.append("scorecard_identity_ref_missing")

    evidence_refs = scorecard.get("evidence_refs")
    if isinstance(evidence_refs, Mapping):
        evidence_scorecard_ref = _string_or_none(evidence_refs.get("quality_scorecard"))
        if (
            scorecard_ref is not None
            and evidence_scorecard_ref is not None
            and evidence_scorecard_ref != scorecard_ref
        ):
            reasons.append("scorecard_identity_ref_mismatch")

    identity_ref = _string_or_none(
        scorecard.get("scorecard_identity_ref")
        or scorecard.get("authoritative_scorecard_ref")
    )
    if scorecard_ref is not None and identity_ref is not None and identity_ref != scorecard_ref:
        reasons.append("scorecard_identity_ref_mismatch")

    verified = scorecard.get("scorecard_identity_verified")
    if verified is not True:
        reasons.append("scorecard_identity_not_verified")
    elif scorecard_ref is not None and identity_ref is None:
        reasons.append("scorecard_identity_ref_missing")

    authority_role = str(scorecard.get("authority_role") or "").strip().casefold()
    provenance_kind = str(scorecard.get("provenance_kind") or "").strip().casefold()
    evidence_class = str(scorecard.get("evidence_class") or "").strip().casefold()
    projection_source = str(scorecard.get("projection_source") or "").strip()
    if (
        evidence_class in _NON_AUTHORITY_SCORECARD_EVIDENCE_CLASSES
        or authority_role in _PROJECTION_AUTHORITY_ROLES
        or provenance_kind in _PROJECTION_PROVENANCE_KINDS
        or projection_source
    ):
        reasons.append("scorecard_projection_not_authority")

    return sorted(set(reasons))


@lru_cache(maxsize=1)
def _non_overridable_blocker_codes() -> frozenset[str]:
    codes: set[str] = set()
    try:
        registry = load_production_invariant_registry(strict=False)
    except Exception:
        registry = None
    if registry is not None:
        for invariant in registry.invariants:
            codes.update(invariant.non_overridable_blockers)
    codes.update(_NON_OVERRIDABLE_SCHEMA_REASONS)
    codes.update(_NON_OVERRIDABLE_IDENTITY_REASONS)
    return frozenset(code for code in codes if code)


def _non_overridable_blocking_codes(scorecard: Mapping[str, Any]) -> list[str]:
    non_overridable = _non_overridable_blocker_codes()
    codes: set[str] = set()
    for failure in _list(scorecard.get("blocking_quality_failures")):
        failure_map = _mapping(failure)
        for key in ("code", "gate", "name"):
            code = _string_or_none(failure_map.get(key))
            if code in non_overridable:
                codes.add(code)
    for gate in _list(scorecard.get("quality_gates")):
        gate_map = _mapping(gate)
        if not bool(gate_map.get("blocking", True)):
            continue
        status = _normalized_status(gate_map.get("status"))
        if status not in _CONFLICT_BLOCKING_STATUSES and status not in {"fail", "blocked"}:
            continue
        for key in ("code", "name"):
            code = _string_or_none(gate_map.get(key))
            if code in non_overridable:
                codes.add(code)
    return sorted(codes)


def _gate_mentions_conflict(gate: Mapping[str, Any]) -> bool:
    haystack = " ".join(
        str(gate.get(key) or "")
        for key in ("name", "code", "layer", "phase", "message")
    ).casefold()
    return "conflict" in haystack


def _digest(payload: Any) -> str:
    data = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalized_status(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return {
        "passed": "pass",
        "success": "pass",
        "ok": "pass",
        "warning": "warn",
        "failed": "fail",
    }.get(text, text)


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _merge_artifact_ownership_refs(
    evidence_refs: dict[str, str],
    artifact_ownership: Mapping[str, Any] | None,
) -> None:
    if artifact_ownership is None:
        return
    index_digest = _string_or_none(artifact_ownership.get("ownership_index_digest"))
    if index_digest is not None:
        evidence_refs["artifact_ownership_index"] = index_digest
    signature_digest = _string_or_none(
        artifact_ownership.get("ownership_index_signature_digest")
    )
    if signature_digest is not None:
        evidence_refs["artifact_ownership_index_signature"] = signature_digest


__all__ = [
    "APPROVAL_PACKET_FILENAME",
    "APPROVAL_PACKET_KIND",
    "APPROVAL_PACKET_SCHEMA",
    "ProductionApprovalPersistence",
    "build_production_approval_packet",
    "persist_production_approval_packet",
]
