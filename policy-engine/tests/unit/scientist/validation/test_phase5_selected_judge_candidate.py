from __future__ import annotations

import logging
import sys

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    artifact_ref_identity_key,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.governance.validation import load_validation_report
from polisyos.ir.registry.refs import ValidationReportRef
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportNode,
)
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.validation.policy_verified.models import (
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceVerificationReport,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


@pytest.mark.parametrize("scenario", ["stable", "drift", "missing", "nonfinite", "missing_entry"])
def test_engine_candidate_runs_real_judges_but_never_establishes_publication(
    tmp_path, monkeypatch, scenario: str
) -> None:
    """A real Engine-selected candidate gives diagnostics, not completed authority."""
    import polisyos.scientist.methods.search.judge_thresholds as threshold_module
    import polisyos.scientist.nodes.builtins.decide.build_verified_policy_report as report_module
    from polisyos.scientist.methods.search.judge_stack import JudgeStack

    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(tmp_path / "registry"))
    live_registry = threshold_module.JudgeThresholdRegistry()
    # Establish an actual fixture registry; an absent registry cannot establish
    # a stable live threshold basis because default timestamps vary per read.
    if scenario != "missing":
        live_registry.record(live_registry.snapshot().entries[0])
    if scenario == "nonfinite":
        import json

        registry_path = tmp_path / "registry" / "judge_thresholds" / "judge_threshold_registry.json"
        snapshot = json.loads(registry_path.read_text(encoding="utf-8"))
        snapshot["entries"][0]["threshold_value"] = float("nan")
        registry_path.write_text(json.dumps(snapshot), encoding="utf-8")
    if scenario == "missing_entry":
        snapshot = live_registry.snapshot()
        live_registry._write_snapshot(
            snapshot.model_copy(
                update={
                    "entries": [
                        entry
                        for entry in snapshot.entries
                        if entry.metric_name != "statistical_uncertainty_level"
                    ]
                }
            )
        )
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "synthetic-phase5-candidate"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    frame_ref = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            request_id="synthetic", policy_question="Synthetic?", jurisdiction="synthetic"
        ),
    )
    verification_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id="synthetic", needs_expert_review=True),
        inputs=[input_ref_from_artifact_ref(frame_ref, role="policy_request_frame")],
    )
    option_ref = persist_policy_option_set(
        store,
        PolicyOptionSet(request_id="synthetic"),
        inputs=[
            input_ref_from_artifact_ref(frame_ref, role="policy_request_frame"),
            input_ref_from_artifact_ref(verification_ref, role="source_verification_report"),
        ],
    )
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": registry_ref},
        params={
            "policy_candidate_schema": _candidate().model_dump(mode="json"),
            "require_human_gate": True,
        },
        policy_request_ref=frame_ref,
        policy_option_set_ref=option_ref,
        source_verification_report_ref=verification_ref,
    )
    captured = []
    original_preflight = report_module.run_phase5_artifact_preflight
    statistical_code = JudgeStack._statistical.__code__
    injected_drift = False

    def observe(frame, event, value):
        nonlocal injected_drift
        # Observe the real return without replacing a protected producer helper.
        if event == "return" and frame.f_code is original_preflight.__code__:
            captured.append(value)
        # Mutate registry data at the actual judge call, not its implementation.
        if scenario == "drift" and not injected_drift and event == "call":
            if frame.f_code is statistical_code:
                injected_drift = True
                live = threshold_module.JudgeThresholdRegistry()
                entry = live.snapshot().entries[0]
                live.record(
                    entry.model_copy(update={"threshold_value": entry.threshold_value + 1}),
                    allow_loosen=True,
                    change_reason="synthetic threshold drift control",
                )

    governance = RunGovernanceNode()
    verified = BuildVerifiedPolicyReportNode()
    nodes = NodeRegistry()
    nodes.register(governance)
    nodes.register(verified)
    workflow = WorkflowSpec(
        workflow_id="synthetic_candidate_diagnostic",
        nodes=[
            NodeInvocation(alias="assessment", node_id=governance.spec.metadata.component_id),
            NodeInvocation(
                alias="verified",
                node_id=verified.spec.metadata.component_id,
                depends_on=["assessment"],
            ),
        ],
    )
    prior_profile = sys.getprofile()
    sys.setprofile(observe)
    try:
        run_result = WorkflowExecutor(ctx, nodes).execute(workflow, state)
    finally:
        sys.setprofile(prior_profile)
    if scenario == "drift":
        assert injected_drift
    assert {item.alias: item.status for item in run_result.report.nodes} == {
        "assessment": "ok",
        "verified": "fail",
    }
    assert len(captured) == 1
    result = captured[0]
    validation_ref = ArtifactRef.model_validate(result.validation_ref.model_dump(mode="json"))
    selected_validation = [
        ref
        for item in run_result.report.nodes
        if item.alias == "verified"
        for ref in item.artifacts
        if ref.kind == "scientist.validation_report"
    ]
    assert len(selected_validation) == 1
    assert artifact_ref_identity_key(selected_validation[0]) == artifact_ref_identity_key(
        validation_ref
    )
    reopened = load_validation_report(
        ensure_ir_artifact_store(store),
        ValidationReportRef.model_validate(validation_ref.model_dump(mode="json")),
    )
    assert reopened == result.validation_report
    assert not result.publishable
    assert result.judge_verdict_ref is None
    assert (
        result.validation_report.normalized_payload["phase5"]["judge_selection_status"]
        == "not_established"
    )
    if scenario in {"drift", "missing", "nonfinite"}:
        assert result.judge_verdict is None
        assert result.judge_verdict_provenance == "not_established"
        expected_reason = {
            "drift": "phase5_threshold_registry_changed",
            "missing": "phase5_threshold_registry_not_established",
            "nonfinite": "phase5_threshold_registry_invalid",
        }[scenario]
        assert expected_reason in result.validation_report.gate_failures
    else:
        assert result.judge_verdict is not None
        assert result.judge_verdict_provenance == "candidate_diagnostic"
        assert len(result.judge_verdict.per_judge) == 6
        assert result.judge_verdict.composite_decision == "defer_to_human"
        assert any(
            card.failure_type == "human_gate_required"
            for card in result.judge_verdict.blocking_failures
        )
        if scenario == "missing_entry":
            assert any(
                failure.startswith("phase5_threshold_requirement_not_established:statistical:")
                for failure in result.validation_report.gate_failures
            )

    if scenario in {"stable", "missing_entry", "drift"}:
        threshold_ref = result.threshold_basis_ref
        assert threshold_ref is not None and threshold_ref.manifest_profile_sha256 is not None
        from polisyos.scientist.methods.search.judge_threshold_basis import (
            load_judge_threshold_basis,
            resolve_judge_threshold_basis,
        )

        captured_basis = load_judge_threshold_basis(store, threshold_ref)
        assert captured_basis.snapshot.entries
        report_ref = ArtifactRef.model_validate(result.validation_ref.model_dump(mode="json"))
        lineage = store.get_manifest(report_ref).inputs
        edges = [edge for edge in lineage if edge.role == "judge_threshold_basis"]
        assert len(edges) == 1
        assert str(edges[0].artifact_id) == str(threshold_ref.artifact_id)
        assert edges[0].manifest_profile_sha256 == threshold_ref.manifest_profile_sha256
        admission = resolve_judge_threshold_basis(store, threshold_ref, live_registry)
        assert admission.status == ("stale" if scenario == "drift" else "current")
        phase5 = result.validation_report.normalized_payload["phase5"]
        assert phase5["judge_threshold_basis_ref"] == threshold_ref.model_dump(mode="json")
        assert phase5["judge_threshold_basis_scope"] == "candidate_diagnostic"
        assert phase5["judge_threshold_basis_status"] == (
            "stale" if scenario == "drift" else "current_at_evaluation"
        )
    else:
        assert result.threshold_basis_ref is None
