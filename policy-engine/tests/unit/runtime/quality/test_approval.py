from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.control import (
    ProductionApprovalOverrideRequest,
    ProductionApprovalPacket,
)
from polisyos.runtime.quality.approval import (
    ProductionApprovalCurrentnessProjection,
    ProductionApprovalPacketResolver,
    ProductionApprovalResolutionError,
    build_production_approval_packet,
    persist_production_approval_packet,
    resolve_production_approval_currentness_receipt,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _scorecard(**overrides: object) -> dict[str, object]:
    scorecard: dict[str, object] = {
        "schema_version": "policyos.quality_scorecard.v1",
        "generated_at": "2026-05-13T09:00:00+00:00",
        "canary_kind": "production",
        "job_id": "job-approval",
        "run_id": "R_approval",
        "execution_status": "completed",
        "quality_status": "pass",
        "performance_status": "pass",
        "conflict_status": "pass",
        "approval_state": "approval_ready",
        "quality_gates": [
            {
                "name": "conflict_check_present",
                "code": "conflict_check_present",
                "status": "pass",
                "layer": "normative_conflict",
                "phase": "quality_evidence",
                "message": "Policy conflict check is present.",
                "evidence_ref": "quality_evidence/conflict_check.json",
                "blocking": True,
            }
        ],
        "blocking_quality_failures": [],
        "warnings": [],
        "evidence_refs": {
            "quality_scorecard": _sha("a"),
            "conflict_check_ref": _sha("b"),
            "performance_summary": "performance.json",
        },
        "quality_scorecard_ref": _sha("a"),
        "scorecard_identity_ref": _sha("a"),
        "scorecard_identity_verified": True,
    }
    scorecard.update(overrides)
    return scorecard


def _sealed_currentness_result(*, now: datetime, packet_ref: str):
    from polisyos.runtime.http.services.human_decisions import (
        ResolvedProductionApprovalInputs,
        ResolvedProductionApprovalPacket,
    )
    from polisyos.runtime.quality import approval

    valid_until = now + timedelta(minutes=5)
    packet = ProductionApprovalPacket.model_construct(
        schema_version="policyos.production_approval_packet.v2",
        tenant_id="tenant-approval",
        run_id="run-approval-currentness",
        expected_consumer="polisyos.scientist.decision_compiler",
        expected_audience="polisyos-runtime",
        valid_from=now - timedelta(minutes=1),
        valid_until=valid_until,
        verifier_epoch="deployment-epoch-1",
        decision="approved",
    )
    inputs = ResolvedProductionApprovalInputs(
        scorecard={},
        scorecard_ref=_sha("a"),
        scorecard_digest=_sha("b"),
        scorecard_signer_identity="scorecard-signer",
        basis=object(),  # type: ignore[arg-type]
        basis_ref=_sha("c"),
        basis_signer_identity="basis-signer",
        record=object(),  # type: ignore[arg-type]
        record_ref=_sha("d"),
        valid_from=now - timedelta(minutes=1),
        valid_until=valid_until,
        verifier_epoch="deployment-epoch-1",
    )
    resolved_packet = ResolvedProductionApprovalPacket(
        packet=packet,
        packet_ref=packet_ref,
        inputs=inputs,
    )
    return approval._ResolvedProductionApprovalCurrentness(
        packet=resolved_packet,
        expected_consumer="polisyos.scientist.decision_compiler",
        expected_audience="polisyos-runtime",
        evaluated_at=now,
        _seal=approval._RESOLVER_SEAL,
    )


def test_runtime_resolver_mints_content_bound_scientist_currentness_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.contracts.control import (
        ProductionApprovalCurrentnessReceipt,
        require_production_approval_currentness_receipt,
    )

    packet_ref = _sha("8")
    now = datetime.now(UTC)
    resolved = _sealed_currentness_result(now=now, packet_ref=packet_ref)
    resolver = object.__new__(ProductionApprovalPacketResolver)
    captured: dict[str, object] = {}

    def _require_currentness(_self, **bindings: object):
        captured.update(bindings)
        return resolved

    monkeypatch.setattr(
        ProductionApprovalPacketResolver,
        "require_currentness",
        _require_currentness,
    )

    receipt = resolve_production_approval_currentness_receipt(
        resolver=resolver,
        packet_ref=packet_ref,
        tenant_id="tenant-approval",
        run_id="run-approval-currentness",
        expected_consumer="polisyos.scientist.decision_compiler",
        expected_audience="polisyos-runtime",
        evaluated_at=now,
    )

    assert type(receipt) is ProductionApprovalCurrentnessReceipt
    assert captured == {
        "packet_ref": packet_ref,
        "tenant_id": "tenant-approval",
        "run_id": "run-approval-currentness",
        "expected_consumer": "polisyos.scientist.decision_compiler",
        "expected_audience": "polisyos-runtime",
        "evaluated_at": now,
    }
    assert (
        require_production_approval_currentness_receipt(
            receipt,
            packet_ref=packet_ref,
            tenant_id="tenant-approval",
            run_id="run-approval-currentness",
            expected_consumer="polisyos.scientist.decision_compiler",
            expected_audience="polisyos-runtime",
        )
        is receipt
    )


@pytest.mark.parametrize(
    "candidate",
    [
        {},
        lambda **_kwargs: True,
        ProductionApprovalCurrentnessProjection(
            status="current",
            packet_ref=_sha("8"),
            checked_at=datetime(2026, 8, 30, tzinfo=UTC),
            expected_consumer="polisyos.scientist.decision_compiler",
            expected_audience="polisyos-runtime",
        ),
    ],
)
def test_runtime_currentness_receipt_rejects_non_exact_resolver(candidate: object) -> None:
    with pytest.raises(ProductionApprovalResolutionError) as exc_info:
        resolve_production_approval_currentness_receipt(
            resolver=candidate,
            packet_ref=_sha("8"),
            tenant_id="tenant-approval",
            run_id="run-approval-currentness",
            expected_consumer="polisyos.scientist.decision_compiler",
            expected_audience="polisyos-runtime",
        )

    assert exc_info.value.code == "DS9-RAW-APPROVAL-NOT-AUTHORITY"


def test_currentness_receipt_cannot_be_constructed_with_a_forged_seal() -> None:
    from polisyos.core.contracts.control import ProductionApprovalCurrentnessReceipt

    now = datetime.now(UTC)
    with pytest.raises(TypeError, match="runtime resolver only"):
        ProductionApprovalCurrentnessReceipt(
            schema_version="policyos.production_approval_currentness_receipt.v1",
            packet_ref=_sha("8"),
            tenant_id="tenant-approval",
            run_id="run-approval-currentness",
            expected_consumer="polisyos.scientist.decision_compiler",
            expected_audience="polisyos-runtime",
            evaluated_at=now,
            valid_until=now + timedelta(minutes=5),
            verifier_epoch="deployment-epoch-1",
            binding_digest=_sha("9"),
            _seal=object(),
        )


def test_clean_scorecard_builds_and_persists_approval_packet(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    evidence_bundle = tmp_path / "evidence"
    scorecard = _scorecard(quality_evidence_bundle_path=str(evidence_bundle))
    original_scorecard = copy.deepcopy(scorecard)

    packet = build_production_approval_packet(
        scorecard=scorecard,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "approved"
    assert packet.eligibility.eligible is True
    assert packet.eligibility.execution_completed is True
    assert packet.eligibility.quality_passed is True
    assert packet.eligibility.performance_blocking is False
    assert packet.eligibility.conflict_blocking is False
    assert packet.override is None
    assert packet.operational_authority is False
    assert packet.historical_only is True
    assert scorecard == original_scorecard

    persisted = persist_production_approval_packet(
        packet,
        store=store,
        evidence_bundle_path=evidence_bundle,
    )

    assert store.has(persisted.approval_packet_ref.artifact_id)
    stored_payload = json.loads(store.get_bytes(persisted.approval_packet_ref.artifact_id))
    assert stored_payload["decision"] == "approved"
    assert stored_payload["scorecard_digest"].startswith("sha256:")

    bundle_payload = json.loads(persisted.evidence_bundle_packet_path.read_text("utf-8"))
    assert bundle_payload["approval_packet_ref"] == str(persisted.approval_packet_ref.artifact_id)
    assert bundle_payload["packet"]["decision"] == "approved"


def test_blocking_quality_performance_and_conflict_status_reject_approval() -> None:
    scorecard = _scorecard(
        quality_status="fail",
        performance_status="over_budget",
        conflict_status="blocked",
        blocking_quality_failures=[
            {
                "gate": "policy_grounding_matrix_present",
                "code": "major_claim_missing_grounding",
                "layer": "scientist_policy_artifacts",
                "phase": "policy_grounding",
                "message": "Unsupported policy claim.",
                "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
            }
        ],
    )

    packet = build_production_approval_packet(
        scorecard=scorecard,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.eligible is False
    assert packet.eligibility.quality_passed is False
    assert packet.eligibility.performance_blocking is True
    assert packet.eligibility.conflict_blocking is True
    assert packet.eligibility.blocking_failure_count == 1
    assert packet.eligibility.reasons == [
        "blocking_quality_failures",
        "conflict_blocking",
        "performance_budget_blocking",
        "quality_not_passing",
    ]


def test_legacy_scorecard_schema_is_quarantined_from_production_approval() -> None:
    packet = build_production_approval_packet(
        scorecard=_scorecard(schema_version="policyos.quality_scorecard.v0"),
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.eligible is False
    assert "legacy_quarantined" in packet.eligibility.reasons


def test_source_truth_conflict_records_block_approval_even_if_projection_says_pass() -> None:
    scorecard = _scorecard(
        source_truth_conflicts=[
            {
                "record_schema": "policyos.runtime.quality.losing_authority_record.v1",
                "field_family": "final_claims",
                "authoritative_surface": "runtime.canary_bundle",
                "losing_surface": "runtime.scorecard",
                "lost_fields": ["claim_sets"],
                "failure_code": "hds_final_claim_authority_conflict",
                "owner": "team-policy-semantics",
                "next_diagnostic_command": (
                    "uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q"
                ),
            }
        ],
    )

    packet = build_production_approval_packet(
        scorecard=scorecard,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.conflict_blocking is True
    assert "conflict_blocking" in packet.eligibility.reasons


def test_redacted_derived_scorecard_projection_cannot_approve() -> None:
    packet = build_production_approval_packet(
        scorecard=_scorecard(
            evidence_class="redacted_derived",
            authority_role="producer_authority",
            provenance_kind="runtime_projection",
        ),
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.eligible is False
    assert "scorecard_projection_not_authority" in packet.eligibility.reasons


def test_api_projection_readiness_conflict_blocks_approval() -> None:
    packet = build_production_approval_packet(
        scorecard=_scorecard(
            readiness_result={
                "readiness": "blocked",
                "approval_state": "quality_failed",
                "runtime_event_ref": "evt:readiness",
            },
            api_projection={
                "readiness": "pass",
                "approval_state": "approval_ready",
                "runtime_event_ref": "evt:api",
            },
        ),
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.conflict_blocking is True
    assert "conflict_blocking" in packet.eligibility.reasons


def test_dashboard_projection_persisted_packet_conflict_blocks_approval() -> None:
    packet = build_production_approval_packet(
        scorecard=_scorecard(
            approval_packet={
                "approval_packet_ref": _sha("d"),
                "decision": "blocked",
                "runtime_event_ref": "evt:approval",
            },
            dashboard_approval_projection={
                "approval_packet_ref": _sha("e"),
                "decision": "approved",
                "runtime_event_ref": "evt:dashboard",
            },
        ),
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.conflict_blocking is True
    assert "conflict_blocking" in packet.eligibility.reasons


def test_unexplained_replay_drift_blocks_approval_even_when_scorecard_files_exist() -> None:
    scorecard = _scorecard(
        drift_explanation={
            "schema_version": "policyos.drift_explanation.v1",
            "status": "unexplained_drift",
            "production_readiness": "fail",
            "summary": {
                "difference_count": 1,
                "unexplained_difference_count": 1,
                "drift_sources": ["norm"],
                "max_impact": "high",
            },
        },
        evidence_refs={
            "quality_scorecard": _sha("a"),
            "replay_manifest": _sha("r"),
            "drift_explanation": _sha("d"),
            "conflict_check_ref": _sha("b"),
        },
    )

    packet = build_production_approval_packet(
        scorecard=scorecard,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.eligible is False
    assert "replay_drift_unexplained" in packet.eligibility.reasons


def test_accepted_non_ready_replay_drift_blocks_approval_even_when_scorecard_passes() -> None:
    scorecard = _scorecard(
        drift_explanation={
            "schema_version": "policyos.drift_explanation.v1",
            "status": "accepted_drift_non_ready",
            "production_readiness": "fail",
            "summary": {
                "difference_count": 2,
                "accepted_difference_count": 2,
                "unexplained_difference_count": 0,
                "drift_sources": ["registry"],
                "max_impact": "high",
            },
            "blocking_failure": {
                "code": "authority_replay_drift_unbounded",
            },
        },
        evidence_refs={
            "quality_scorecard": _sha("a"),
            "replay_manifest": _sha("r"),
            "drift_explanation": _sha("d"),
            "conflict_check_ref": _sha("b"),
        },
    )

    packet = build_production_approval_packet(
        scorecard=scorecard,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.eligible is False
    assert "replay_drift_unbounded" in packet.eligibility.reasons


def test_unverified_scorecard_identity_blocks_production_approval_even_with_override() -> None:
    override = ProductionApprovalOverrideRequest(
        reviewer_identity="qa.lead@example.test",
        reason=(
            "Emergency production canary accepted after manual budget review with "
            "documented rollback and owner acknowledgement."
        ),
        scope="run:R_approval",
        expires_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        evidence_refs=[_sha("c"), "incident://INC-identity"],
    )

    packet = build_production_approval_packet(
        scorecard=_scorecard(
            performance_status="over_budget",
            scorecard_identity_verified=False,
            scorecard_identity_ref=None,
        ),
        override=override,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.override is None
    assert "scorecard_identity_not_verified" in packet.eligibility.reasons
    assert "non_overridable_blocker" in packet.eligibility.reasons


def test_non_overridable_authority_blocker_cannot_be_bypassed_by_override() -> None:
    override = ProductionApprovalOverrideRequest(
        reviewer_identity="qa.lead@example.test",
        reason=(
            "Emergency production canary accepted after manual authority review with "
            "documented rollback and owner acknowledgement."
        ),
        scope="run:R_approval",
        expires_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        evidence_refs=[_sha("c"), "incident://INC-authority"],
    )

    packet = build_production_approval_packet(
        scorecard=_scorecard(
            quality_status="fail",
            blocking_quality_failures=[
                {
                    "gate": "runtime_authority_refs_present",
                    "code": "authority_cas_missing",
                    "layer": "runtime_authority",
                    "phase": "quality_evidence",
                    "message": "Required runtime CAS authority is missing.",
                    "evidence_ref": None,
                }
            ],
        ),
        override=override,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.override is None
    assert "non_overridable_blocker" in packet.eligibility.reasons
    assert "authority_cas_missing" in packet.eligibility.reasons


def test_missing_performance_evidence_rejects_production_approval() -> None:
    packet = build_production_approval_packet(
        scorecard=_scorecard(performance_status="missing"),
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.eligible is False
    assert packet.eligibility.performance_blocking is True
    assert "performance_budget_blocking" in packet.eligibility.reasons


def test_quality_completed_is_not_a_passing_quality_status() -> None:
    packet = build_production_approval_packet(
        scorecard=_scorecard(quality_status="completed"),
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.quality_passed is False
    assert "quality_not_passing" in packet.eligibility.reasons


def test_override_approves_exception_with_attribution_signature_and_scope() -> None:
    scorecard = _scorecard(
        performance_status="over_budget",
        conflict_status="pass",
    )
    original_scorecard = copy.deepcopy(scorecard)
    override = ProductionApprovalOverrideRequest(
        reviewer_identity="qa.lead@example.test",
        reason="Emergency production canary accepted after manual budget review.",
        scope="run:R_approval",
        expires_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        evidence_refs=[_sha("c"), "incident://INC-42"],
    )

    packet = build_production_approval_packet(
        scorecard=scorecard,
        override=override,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "approved_with_override"
    assert packet.eligibility.eligible is False
    assert packet.override is not None
    assert packet.override.reviewer_identity == "qa.lead@example.test"
    assert packet.override.scope == "run:R_approval"
    assert packet.override.signature.startswith("sha256:")
    assert packet.override.evidence_refs == [_sha("c"), "incident://INC-42"]
    assert scorecard == original_scorecard


def test_expired_override_does_not_approve_blocked_packet() -> None:
    override = ProductionApprovalOverrideRequest(
        reviewer_identity="qa.lead@example.test",
        reason="Expired manual override.",
        scope="run:R_approval",
        expires_at=datetime(2026, 5, 13, 9, 59, tzinfo=UTC),
        evidence_refs=[_sha("c")],
    )

    packet = build_production_approval_packet(
        scorecard=_scorecard(performance_status="over_budget"),
        override=override,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.override is None
    assert "override_expired" in packet.eligibility.reasons


def test_blocking_quality_failures_require_scoped_override_with_strong_rationale() -> None:
    override = ProductionApprovalOverrideRequest(
        reviewer_identity="qa.lead@example.test",
        reason="OK.",
        scope="run:somewhere_else",
        expires_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        evidence_refs=[_sha("c")],
    )

    packet = build_production_approval_packet(
        scorecard=_scorecard(
            quality_status="fail",
            blocking_quality_failures=[
                {
                    "gate": "policy_grounding_matrix_present",
                    "code": "major_claim_missing_grounding",
                    "layer": "scientist_policy_artifacts",
                    "phase": "policy_grounding",
                    "message": "Unsupported policy claim.",
                    "evidence_ref": "quality_evidence/policy_grounding_matrix.json",
                }
            ],
        ),
        override=override,
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.override is None
    assert "override_scope_mismatch" in packet.eligibility.reasons
    assert "override_rationale_weak" in packet.eligibility.reasons


def test_human_review_calibration_report_ref_is_carried_in_approval_packet() -> None:
    packet = build_production_approval_packet(
        scorecard=_scorecard(),
        human_review_calibration_report_ref=_sha("h"),
        now=datetime(2026, 5, 13, 10, 0, tzinfo=UTC),
    )

    assert packet.evidence_refs["human_review_calibration_report"] == _sha("h")


@pytest.mark.parametrize(
    "field",
    ["reviewer_identity", "reason", "scope", "expires_at", "evidence_refs"],
)
def test_override_requires_reviewer_reason_scope_expiry_and_evidence_refs(field: str) -> None:
    payload: dict[str, object] = {
        "reviewer_identity": "qa.lead@example.test",
        "reason": "Manual approval with attached evidence.",
        "scope": "run:R_approval",
        "expires_at": datetime.now(UTC) + timedelta(days=1),
        "evidence_refs": [_sha("d")],
    }
    payload.pop(field)

    with pytest.raises(ValidationError):
        ProductionApprovalOverrideRequest.model_validate(payload)
