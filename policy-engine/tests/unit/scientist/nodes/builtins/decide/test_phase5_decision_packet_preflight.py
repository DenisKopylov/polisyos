"""Actual packet preflight never promotes an unbound judge marker."""

from __future__ import annotations

from polisyos.core.artifacts import artifact_ref_identity_key, ensure_ir_artifact_store
from polisyos.ir.governance.validation import load_validation_report
from polisyos.ir.registry.refs import ValidationReportRef
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.producer_currentness import (
    _load_invocation_output_state,
)
from tests.unit.scientist.governance.human_review.test_decision_packet_integration import (
    _ctx_and_state,
    _run_governance_and_packet,
)


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def _assert_phase5_blocks_unbound_judges(store, ctx, outcome) -> None:
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "phase5_validation_failed"
    assert all(ref.kind != "scientist.decision_packet" for ref in outcome.artifacts)
    assert all(ref.kind != "scientist.judge_verdict" for ref in outcome.artifacts)
    validation_ref = next(
        ref for ref in outcome.artifacts if ref.kind == "scientist.validation_report"
    )
    assert validation_ref.manifest_profile_sha256 is not None
    attempts = [
        attempt
        for attempt in ctx.run.read_runtime_invocation_attempts()
        if attempt.basis.node_alias == "packet"
    ]
    assert len(attempts) == 1
    completion = attempts[0].outcome
    assert completion is not None and completion.status == "fail"
    assert completion.outcome_state_ref is not None
    attempted_state = _load_invocation_output_state(ctx, completion.outcome_state_ref)
    assert ARTIFACT_DECISION_PACKET_REF not in attempted_state.artifacts_index
    assert artifact_ref_identity_key(
        attempted_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF]
    ) == artifact_ref_identity_key(validation_ref)
    report = load_validation_report(
        ensure_ir_artifact_store(store),
        ValidationReportRef.model_validate(validation_ref.model_dump(mode="json")),
    )
    assert report.verdict == "blocked"
    judges = next(
        component for component in report.phase5_components if component.name == "six_judges"
    )
    assert judges.status == "blocked"
    assert report.judge_verdict_ref is None
    assert report.normalized_payload["phase5"]["judge_selection_status"] == "not_established"


def test_decision_packet_rejects_unbound_passing_judge_marker(tmp_path) -> None:
    store, ctx, state = _ctx_and_state(tmp_path, params={"judge_verdict": _passing_judge_verdict()})
    outcome = _run_governance_and_packet(ctx, state)
    _assert_phase5_blocks_unbound_judges(store, ctx, outcome)


def test_decision_packet_is_not_persisted_when_phase5_blocks(tmp_path) -> None:
    store, ctx, state = _ctx_and_state(tmp_path, params={"phase5_enforce_publication": True})
    outcome = _run_governance_and_packet(ctx, state)
    _assert_phase5_blocks_unbound_judges(store, ctx, outcome)
