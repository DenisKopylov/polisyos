from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.governance.pipeline import ValidationPipeline
from polisyos.scientist.governance.report_currentness import resolve_current_governance_report
from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.governance import run_governance
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EVALUATOR_REPORT_REF,
    ARTIFACT_ITERATION_STATE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import (
    ExecutionContext,
    _EngineInvocationBinding,
    _load_engine_owned_invocation_input_state,
)
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec
from polisyos.scientist.orchestration.workflows.causal_full import causal_full_workflow_spec
from polisyos.scientist.orchestration.workflows.default import default_workflow_spec


class _EvaluatorSensitivePass(ValidatorPass):
    """Exercise a real pass that reads the source and newly produced evaluation."""

    def __init__(self) -> None:
        self.seen: list[tuple[int, str | None]] = []

    @property
    def pass_id(self) -> str:
        return "strategic_response"

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        params = ctx.state["params"]
        evaluation = params.get("evaluator_verdict")
        self.seen.append((params["random_seed"], evaluation))
        if evaluation is None:
            return []
        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["params", "evaluator_verdict"],
                message="Controlled pass rejects after evaluation is present.",
                severity=IssueSeverity.BLOCKER,
                code="TEST_EVALUATION_BLOCKER",
            )
        ]


@pytest.mark.parametrize(
    ("spec_factory", "require_gate", "use_async"),
    [
        (default_workflow_spec, False, False),
        (causal_full_workflow_spec, False, False),
        (default_workflow_spec, True, False),
        (causal_full_workflow_spec, True, False),
        (default_workflow_spec, False, True),
        (causal_full_workflow_spec, True, True),
    ],
)
def test_evaluator_is_followed_by_fresh_governance_before_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec_factory: Callable[[], WorkflowSpec],
    require_gate: bool,
    use_async: bool,
) -> None:
    selected_pass = _EvaluatorSensitivePass()
    monkeypatch.setattr(run_governance, "_RUNTIME_PIPELINE", ValidationPipeline([selected_pass]))
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "governance-evaluator-currentness"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    registry = NodeRegistry()
    for node in (RunGovernanceNode(), RunEvaluatorNode(), BuildDecisionPacketNode()):
        registry.register(node)

    selected = spec_factory()
    invocations = {item.alias: item for item in selected.nodes}
    # Preserve each selected workflow's real governance/evaluator/reissue/packet
    # invocations; remove unrelated upstream producers from this bounded slice.
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["run_evaluator"],
                invocations["refresh_governance"],
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    initial = ExperimentState(
        run_id=run_id, params={"random_seed": 123, "require_human_gate": require_gate}
    )
    if use_async:
        result = asyncio.run(AsyncWorkflowExecutor(ctx, registry).execute(workflow, initial))
    else:
        result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    records = {item.alias: item for item in result.report.nodes}
    assert {alias: record.status for alias, record in records.items()} == {
        "run_governance": "ok",
        "run_evaluator": "ok",
        "refresh_governance": "ok",
        "build_decision_packet": "fail" if require_gate else "ok",
    }
    if require_gate:
        assert records["build_decision_packet"].error is not None
        assert records["build_decision_packet"].error.code == "human_review_validation_failed"
        assert "decision_packet_ref" not in result.state.artifacts_index
    attempts = {item.basis.node_alias: item for item in run.read_runtime_invocation_attempts()}

    def input_state(alias: str) -> ExperimentState:
        attempt = attempts[alias]
        bound_ctx = replace(
            ctx,
            _engine_invocation=_EngineInvocationBinding(
                run_id=attempt.basis.run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                require_successful_completion=records[alias].status == "ok",
            ),
        )
        state = _load_engine_owned_invocation_input_state(bound_ctx, result.state)
        assert state is not None
        return state

    evaluator_input = input_state("run_evaluator")
    first_ref = evaluator_input.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    first_admission = resolve_current_governance_report(ctx, evaluator_input, first_ref)
    assert first_admission.is_current
    assert first_admission.report is not None
    assert first_admission.report.verdict == ("human_gate" if require_gate else "approve")

    refresh_input = input_state("refresh_governance")
    evaluator_verdict = "REPLAN_METHOD" if require_gate else "APPROVE"
    assert refresh_input.params["evaluator_verdict"] == evaluator_verdict
    evaluator_ref = refresh_input.artifacts_index[ARTIFACT_EVALUATOR_REPORT_REF]
    iteration_ref = refresh_input.artifacts_index[ARTIFACT_ITERATION_STATE_REF]
    assert evaluator_ref.manifest_profile_sha256 is not None
    assert iteration_ref.manifest_profile_sha256 is not None
    evaluator_manifest = store.get_manifest(evaluator_ref)
    governance_input = next(
        item for item in evaluator_manifest.inputs if item.role == "governance_report"
    )
    assert governance_input.artifact_id == first_ref.artifact_id
    assert governance_input.manifest_profile_sha256 == first_ref.manifest_profile_sha256
    stale = resolve_current_governance_report(ctx, refresh_input, first_ref)
    assert (stale.status, stale.reason_code) == ("stale", "producer_source_projection_changed")

    packet_input = input_state("build_decision_packet")
    latest_ref = packet_input.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    latest = resolve_current_governance_report(ctx, packet_input, latest_ref)
    assert latest.is_current
    assert latest.report is not None
    assert latest.report.invocation_binding is not None
    assert latest.report.invocation_binding.node_alias == "refresh_governance"
    latest_verdict = "human_gate" if require_gate else "reject"
    assert latest.report.verdict == latest_verdict
    assert selected_pass.seen == [(123, None), (123, evaluator_verdict)]
    assert any(issue["code"] == "TEST_EVALUATION_BLOCKER" for issue in latest.report.issues)
    if not require_gate:
        packet = json.loads(store.get_bytes(result.state.artifacts_index["decision_packet_ref"]))
        assert packet["governance"]["currentness"] == "current"
        assert packet["governance"]["verdict"] == latest_verdict
        assert any(
            issue["code"] == "TEST_EVALUATION_BLOCKER" for issue in packet["governance"]["issues"]
        )

    # Change a value the pass actually consumed while retaining both report and
    # producer markers. The real packet consumer must still fail closed.
    changed = packet_input.model_copy(deep=True)
    changed.params["random_seed"] = 124
    changed_admission = resolve_current_governance_report(ctx, changed, latest_ref)
    assert (changed_admission.status, changed_admission.reason_code) == (
        "stale",
        "producer_source_projection_changed",
    )
    refused = BuildDecisionPacketNode().execute(ctx, changed)
    assert refused.status == "fail"
    assert refused.error is not None
    assert refused.error.code == "governance_report_not_established"
    assert (
        refused.error.details["governance_report_refusal_code"]
        == "producer_source_projection_changed"
    )


@pytest.mark.parametrize("spec_factory", [default_workflow_spec, causal_full_workflow_spec])
def test_all_pre_packet_producers_are_governance_ancestors(
    spec_factory: Callable[[], WorkflowSpec],
) -> None:
    by_alias = {node.alias: node for node in spec_factory().nodes}
    ancestors: set[str] = set()
    pending = list(by_alias["run_governance"].depends_on)
    while pending:
        alias = pending.pop()
        if alias not in ancestors:
            ancestors.add(alias)
            pending.extend(by_alias[alias].depends_on)

    # The initial governance pass must see every preceding state writer even
    # when the engine schedules unrelated DAG branches in parallel.
    preceding = set(by_alias) - {
        "run_governance",
        "run_evaluator",
        "refresh_governance",
        "build_decision_packet",
    }
    assert preceding <= ancestors


@pytest.mark.parametrize("spec_factory", [default_workflow_spec, causal_full_workflow_spec])
@pytest.mark.parametrize("invalid_config", [False, True])
def test_metric_dependency_skip_continues_but_failure_blocks_governance(
    tmp_path: Path, spec_factory: Callable[[], WorkflowSpec], invalid_config: bool
) -> None:
    from polisyos.scientist.nodes.builtins.simulate.run_metric_validation import (
        RunMetricValidationNode,
    )

    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "governance-metric-dependency"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    registry = NodeRegistry()
    for node in (
        RunMetricValidationNode(),
        RunGovernanceNode(),
        RunEvaluatorNode(),
        BuildDecisionPacketNode(),
    ):
        registry.register(node)
    selected = spec_factory()
    invocations = {item.alias: item for item in selected.nodes}
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_metric_validation"].model_copy(update={"depends_on": []}),
                invocations["run_governance"].model_copy(
                    update={"depends_on": ["run_metric_validation"]}
                ),
                invocations["run_evaluator"],
                invocations["refresh_governance"],
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    metric_config: object = "invalid" if invalid_config else {"enabled": False}
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id=run_id, params={"metric_validation": metric_config})
    )
    records = {item.alias: item for item in result.report.nodes}
    if invalid_config:
        assert records["run_metric_validation"].status == "fail"
        for alias in (
            "run_governance",
            "run_evaluator",
            "refresh_governance",
            "build_decision_packet",
        ):
            assert records[alias].status == "skip"
            assert records[alias].skip_reason == "upstream_failed"
        assert REPORT_GOVERNANCE_REPORT_REF not in result.state.reports_index
        assert "decision_packet_ref" not in result.state.artifacts_index
    else:
        assert records["run_metric_validation"].status == "skip"
        for alias in (
            "run_governance",
            "run_evaluator",
            "refresh_governance",
            "build_decision_packet",
        ):
            assert records[alias].status == "ok"
        packet = json.loads(store.get_bytes(result.state.artifacts_index["decision_packet_ref"]))
        assert packet["governance"]["currentness"] == "current"


@pytest.mark.parametrize(
    ("decision_verdict", "expected_evaluator", "use_async"),
    [
        ("reject", "REPLAN_METHOD", False),
        ("approve", "APPROVE", False),
        ("reject", "REPLAN_METHOD", True),
    ],
)
def test_governance_refresh_replays_only_owner_bound_gate_decisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    decision_verdict: str,
    expected_evaluator: str,
    use_async: bool,
) -> None:
    from polisyos.scientist.nodes.builtins.governance.governance_gate_requests import (
        _create_gate_request,
        _resolve_previous_gate_decision,
        _serialize_gate_request_ref,
    )
    from polisyos.scientist.orchestration.kernel.gate_protocol import HumanGateProtocol

    # A synthetic reviewer/decision exercises the existing gate protocol; it does
    # not establish any real institutional identity or external approval.
    monkeypatch.setattr(run_governance, "_RUNTIME_PIPELINE", ValidationPipeline([]))
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "governance-refresh-gate-rejection"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    initial = ExperimentState(run_id=run_id, params={"require_human_gate": False})
    request, request_ref = _create_gate_request(
        ctx=ctx, protocol=HumanGateProtocol(run), state=initial
    )
    initial.params["gate_request"] = request.model_dump(mode="json")
    initial.params["gate_request_ref"] = _serialize_gate_request_ref(request_ref)
    initial.params["gate_decision"] = {
        "request_id": request.request_id,
        "run_id": run_id,
        "verdict": decision_verdict,
        "approver_id": "synthetic-test-reviewer",
    }

    registry = NodeRegistry()
    for node in (RunGovernanceNode(), RunEvaluatorNode(), BuildDecisionPacketNode()):
        registry.register(node)
    selected = default_workflow_spec()
    invocations = {item.alias: item for item in selected.nodes}
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["run_evaluator"],
                invocations["refresh_governance"],
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    if use_async:
        result = asyncio.run(AsyncWorkflowExecutor(ctx, registry).execute(workflow, initial))
    else:
        result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    attempts = {item.basis.node_alias: item for item in run.read_runtime_invocation_attempts()}

    def input_state(alias: str) -> ExperimentState:
        attempt = attempts[alias]
        bound_ctx = replace(
            ctx,
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                require_successful_completion=True,
            ),
        )
        state = _load_engine_owned_invocation_input_state(bound_ctx, result.state)
        assert state is not None
        return state

    evaluator_input = input_state("run_evaluator")
    initial_report = resolve_current_governance_report(ctx, evaluator_input)
    assert initial_report.is_current
    assert initial_report.report is not None
    assert initial_report.report.verdict == decision_verdict
    assert evaluator_input.params["gate_decision_typed"]["verdict"] == decision_verdict
    assert "gate_decision" not in evaluator_input.params
    from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key

    decision_ref = ArtifactRef.model_validate(evaluator_input.params["gate_decision_ref"])
    selected_request_ref = ArtifactRef.model_validate(evaluator_input.params["gate_request_ref"])
    assert decision_ref.manifest_profile_sha256 is not None
    assert selected_request_ref.manifest_profile_sha256 is not None
    producer_outcome = attempts["run_governance"].outcome
    assert producer_outcome is not None
    assert any(
        artifact_ref_identity_key(ref) == artifact_ref_identity_key(decision_ref)
        for ref in producer_outcome.output_refs
    )
    decision_manifest = store.get_manifest(decision_ref)
    assert len(decision_manifest.inputs) == 1
    assert decision_manifest.inputs[0].manifest_profile_sha256 == (
        selected_request_ref.manifest_profile_sha256
    )

    packet_input = input_state("build_decision_packet")
    assert packet_input.params["evaluator_verdict"] == expected_evaluator
    refreshed = resolve_current_governance_report(ctx, packet_input)
    assert refreshed.is_current
    assert refreshed.report is not None
    assert refreshed.report.verdict == decision_verdict
    packet = json.loads(store.get_bytes(result.state.artifacts_index["decision_packet_ref"]))
    assert packet["governance"]["verdict"] == decision_verdict

    # Replay uses the first producer's exact selected output and request edge,
    # not a typed marker or a same-bytes foreign manifest profile.
    from polisyos.core.artifacts.manifest import (
        ProducerInfo,
        SchemaInfo,
        input_ref_from_artifact_ref,
    )
    from polisyos.core.artifacts.store import PutOptions

    replay_input = input_state("refresh_governance")
    refresh_attempt = attempts["refresh_governance"]
    replay_ctx = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=run_id,
            attempt_id=refresh_attempt.basis.attempt_id,
            basis_ref=refresh_attempt.basis_ref,
            require_successful_completion=True,
        ),
    )
    status, replayed_decision = _resolve_previous_gate_decision(
        ctx=replay_ctx, state=replay_input, request=request, request_ref=selected_request_ref
    )
    assert status == "current"
    assert replayed_decision is not None
    assert replayed_decision.verdict.value == decision_verdict

    def assert_replay_blocked(changed: ExperimentState) -> None:
        status, replayed_decision = _resolve_previous_gate_decision(
            ctx=replay_ctx, state=changed, request=request, request_ref=selected_request_ref
        )
        assert status == "not_established"
        assert replayed_decision is None

    for removed_keys in (
        ("gate_decision_ref",),
        ("gate_decision_typed",),
        ("gate_decision_ref", "gate_decision_typed"),
    ):
        changed = replay_input.model_copy(deep=True)
        for key in removed_keys:
            changed.params.pop(key)
        assert_replay_blocked(changed)

    changed = replay_input.model_copy(deep=True)
    changed.params["gate_decision_typed"]["verdict"] = (
        "approve" if decision_verdict == "reject" else "reject"
    )
    assert_replay_blocked(changed)
    changed = replay_input.model_copy(deep=True)
    changed.params["gate_decision"] = {
        "request_id": request.request_id,
        "run_id": run_id,
        "verdict": "approve",
        "approver_id": "synthetic-injected-reviewer",
    }
    assert_replay_blocked(changed)

    foreign_decision_ref = store.put_json(
        json.loads(store.get_bytes(decision_ref)),
        PutOptions(
            kind="ir.gate_decision",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.GateDecision", version="1.0"),
            producer=ProducerInfo(component="test.foreign_gate_profile", version="1.0.0"),
            inputs=[input_ref_from_artifact_ref(selected_request_ref, role="gate_request")],
        ),
        return_selected_profile=True,
    )
    assert foreign_decision_ref.artifact_id == decision_ref.artifact_id
    assert foreign_decision_ref.manifest_profile_sha256 != decision_ref.manifest_profile_sha256
    changed = replay_input.model_copy(deep=True)
    changed.params["gate_decision_ref"] = foreign_decision_ref.model_dump(mode="json")
    assert_replay_blocked(changed)

    # Isolate the selected-profile comparison after an actual successful Engine
    # replay. The full runtime also rejects the altered state at the transition
    # check; bypassing that one guard here lets this test reach the profile guard.
    from polisyos.scientist.nodes.builtins.governance import governance_gate_requests

    with monkeypatch.context() as isolated:
        isolated.setattr(
            governance_gate_requests, "_gate_replay_follows_exact_evaluator", lambda *_: True
        )
        status, _ = _resolve_previous_gate_decision(
            ctx=replay_ctx, state=changed, request=request, request_ref=selected_request_ref
        )
        assert status == "not_established"
        isolated.setattr(
            governance_gate_requests,
            "artifact_ref_identity_key",
            lambda ref: (str(ref.artifact_id), ref.kind, ref.media_type),
        )
        status, _ = _resolve_previous_gate_decision(
            ctx=replay_ctx, state=changed, request=request, request_ref=selected_request_ref
        )
        assert status == "current"

    foreign_request_ref = store.put_json(
        request.model_dump(mode="json"),
        PutOptions(
            kind="ir.gate_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.GateRequest", version=request.schema_version),
            producer=ProducerInfo(component="test.foreign_request_profile", version="1.0.0"),
        ),
        return_selected_profile=True,
    )
    assert foreign_request_ref.artifact_id == selected_request_ref.artifact_id
    assert (
        foreign_request_ref.manifest_profile_sha256 != selected_request_ref.manifest_profile_sha256
    )
    changed = replay_input.model_copy(deep=True)
    changed.params["gate_request_ref"] = foreign_request_ref.model_dump(mode="json")
    assert_replay_blocked(changed)
    with monkeypatch.context() as isolated:
        isolated.setattr(
            governance_gate_requests, "_gate_replay_follows_exact_evaluator", lambda *_: True
        )
        status, _ = _resolve_previous_gate_decision(
            ctx=replay_ctx, state=changed, request=request, request_ref=foreign_request_ref
        )
        assert status == "not_established"

    changed = replay_input.model_copy(deep=True)
    changed.reports_index.pop(REPORT_GOVERNANCE_REPORT_REF)
    assert_replay_blocked(changed)


@pytest.mark.parametrize(
    ("key", "remove_transition_check"),
    [
        ("gate_decision_ref", False),
        ("gate_decision_typed", False),
        ("gate_request_ref", False),
        ("gate_decision", False),
        ("plugin_owned_policy_input", False),
        ("plugin_owned_policy_input", True),
    ],
)
def test_engine_blocks_packet_when_gate_replay_binding_is_corrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, remove_transition_check: bool
) -> None:
    from polisyos.scientist.nodes.builtins.governance import governance_gate_requests
    from polisyos.scientist.nodes.builtins.governance.governance_gate_requests import (
        _create_gate_request,
        _serialize_gate_request_ref,
    )
    from polisyos.scientist.orchestration.engine.builtins.set_state import SetStateNode
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation
    from polisyos.scientist.orchestration.kernel.gate_protocol import HumanGateProtocol

    monkeypatch.setattr(run_governance, "_RUNTIME_PIPELINE", ValidationPipeline([]))
    if remove_transition_check:
        # Removal control: the request does not cover arbitrary plugin-owned
        # state, so only the exact Engine transition prevents this replay.
        monkeypatch.setattr(
            governance_gate_requests, "_gate_replay_follows_exact_evaluator", lambda *_: True
        )
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "governance-gate-replay-corruption"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    initial = ExperimentState(run_id=run_id, params={"plugin_owned_policy_input": "original"})
    request, request_ref = _create_gate_request(
        ctx=ctx, protocol=HumanGateProtocol(run), state=initial
    )
    initial.params["gate_request"] = request.model_dump(mode="json")
    initial.params["gate_request_ref"] = _serialize_gate_request_ref(request_ref)
    initial.params["gate_decision"] = {
        "request_id": request.request_id,
        "run_id": run_id,
        "verdict": "reject",
        "approver_id": "synthetic-test-reviewer",
    }
    registry = NodeRegistry()
    for node in (
        RunGovernanceNode(),
        RunEvaluatorNode(),
        SetStateNode(),
        BuildDecisionPacketNode(),
    ):
        registry.register(node)
    selected = default_workflow_spec()
    invocations = {item.alias: item for item in selected.nodes}
    tamper = NodeInvocation(
        alias="corrupt_gate_binding",
        node_id="scientist.node_set_state@1.0.0",
        params={"key": key, "value": "corrupted"},
        depends_on=["run_evaluator"],
    )
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["run_evaluator"],
                tamper,
                invocations["refresh_governance"].model_copy(
                    update={"depends_on": ["corrupt_gate_binding"]}
                ),
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    records = {item.alias: item for item in result.report.nodes}
    assert records["run_governance"].status == "ok"
    assert records["run_evaluator"].status == "ok"
    assert records["corrupt_gate_binding"].status == "ok"
    assert records["refresh_governance"].status == "ok"
    if remove_transition_check:
        assert records["build_decision_packet"].status == "ok"
        packet = json.loads(store.get_bytes(result.state.artifacts_index["decision_packet_ref"]))
        assert packet["governance"]["verdict"] == "reject"
        return
    assert records["build_decision_packet"].status == "fail"
    assert records["build_decision_packet"].error is not None
    assert records["build_decision_packet"].error.code == "human_review_validation_failed"
    assert "decision_packet_ref" not in result.state.artifacts_index

    packet_attempt = next(
        item
        for item in run.read_runtime_invocation_attempts()
        if item.basis.node_alias == "build_decision_packet"
    )
    bound_ctx = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=run_id,
            attempt_id=packet_attempt.basis.attempt_id,
            basis_ref=packet_attempt.basis_ref,
        ),
    )
    packet_input = _load_engine_owned_invocation_input_state(bound_ctx, result.state)
    assert packet_input is not None
    report = resolve_current_governance_report(ctx, packet_input)
    assert report.is_current
    assert report.report is not None
    assert report.report.verdict == "human_gate"
    assert any(
        issue["code"] == "gate.decision.replay_not_established" for issue in report.report.issues
    )


def test_engine_blocks_gate_replay_when_selected_decision_bytes_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.scientist.nodes.builtins.governance.governance_gate_requests import (
        _create_gate_request,
        _serialize_gate_request_ref,
    )
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation
    from polisyos.scientist.orchestration.kernel.gate_protocol import HumanGateProtocol

    monkeypatch.setattr(run_governance, "_RUNTIME_PIPELINE", ValidationPipeline([]))
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "governance-gate-cas-corruption"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    initial = ExperimentState(run_id=run_id)
    request, request_ref = _create_gate_request(
        ctx=ctx, protocol=HumanGateProtocol(run), state=initial
    )
    initial.params["gate_request"] = request.model_dump(mode="json")
    initial.params["gate_request_ref"] = _serialize_gate_request_ref(request_ref)
    initial.params["gate_decision"] = {
        "request_id": request.request_id,
        "run_id": run_id,
        "verdict": "approve",
        "approver_id": "synthetic-test-reviewer",
    }
    spec = NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_test_corrupt_gate_blob@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Corrupt selected gate decision for test",
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=["params.gate_decision_ref"],
        state_writes=[],
    )

    class _CorruptDecisionBlobNode:
        @property
        def spec(self) -> NodeSpec:
            return spec

        def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            ref = ArtifactRef.model_validate(state.params["gate_decision_ref"])
            assert store.verify(ref).ok
            blob_path, _ = store._paths(ref.artifact_id)
            blob_path.write_bytes(b'{"corrupted":true}')
            return NodeOutcome(status="ok", state=state)

    registry = NodeRegistry()
    for node in (
        RunGovernanceNode(),
        RunEvaluatorNode(),
        _CorruptDecisionBlobNode(),
        BuildDecisionPacketNode(),
    ):
        registry.register(node)
    selected = default_workflow_spec()
    invocations = {item.alias: item for item in selected.nodes}
    corrupt = NodeInvocation(
        alias="corrupt_selected_decision_blob",
        node_id=spec.metadata.component_id,
        depends_on=["run_evaluator"],
    )
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["run_evaluator"],
                corrupt,
                invocations["refresh_governance"].model_copy(
                    update={"depends_on": ["corrupt_selected_decision_blob"]}
                ),
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    records = {item.alias: item for item in result.report.nodes}
    assert records["run_governance"].status == "ok"
    assert records["run_evaluator"].status == "ok"
    assert records["corrupt_selected_decision_blob"].status == "ok"
    # Owner invocation replay verifies the selected CAS output before the gate
    # helper can inspect it. This is an earlier refusal, not evidence that the
    # helper's own byte check executed.
    assert records["refresh_governance"].status == "fail"
    assert records["refresh_governance"].error is not None
    assert records["refresh_governance"].error.code == "node.invalid_state"
    assert (
        records["refresh_governance"].error.details["reason"]
        == "run_invocation_record_linked_cas_invalid"
    )
    assert records["build_decision_packet"].status == "skip"
    assert records["build_decision_packet"].skip_reason == "upstream_failed"
    assert "decision_packet_ref" not in result.state.artifacts_index


def test_unmatched_initial_gate_remains_blocked_after_evaluation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No request exists for this caller-supplied decision. The first producer
    # issues one and refuses the decision; refresh must not erase that refusal.
    monkeypatch.setattr(run_governance, "_RUNTIME_PIPELINE", ValidationPipeline([]))
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "unmatched-initial-gate"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    initial = ExperimentState(
        run_id=run_id,
        params={
            "require_human_gate": False,
            "gate_decision": {
                "request_id": "not-a-current-request",
                "run_id": run_id,
                "verdict": "approve",
                "approver_id": "synthetic-test-reviewer",
            },
        },
    )
    registry = NodeRegistry()
    for node in (RunGovernanceNode(), RunEvaluatorNode(), BuildDecisionPacketNode()):
        registry.register(node)
    selected = default_workflow_spec()
    invocations = {item.alias: item for item in selected.nodes}
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["run_evaluator"],
                invocations["refresh_governance"],
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    records = {item.alias: item for item in result.report.nodes}
    attempts = {item.basis.node_alias: item for item in run.read_runtime_invocation_attempts()}

    def input_state(alias: str) -> ExperimentState:
        attempt = attempts[alias]
        bound_ctx = replace(
            ctx,
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id,
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                require_successful_completion=records[alias].status == "ok",
            ),
        )
        snapshot = _load_engine_owned_invocation_input_state(bound_ctx, result.state)
        assert snapshot is not None
        return snapshot

    first_report = resolve_current_governance_report(ctx, input_state("run_evaluator"))
    assert first_report.is_current
    assert first_report.report is not None
    assert first_report.report.verdict == "human_gate"
    assert any(issue["code"] == "gate.request.unverified" for issue in first_report.report.issues)
    final_report = resolve_current_governance_report(ctx, input_state("build_decision_packet"))
    assert final_report.is_current
    assert final_report.report is not None
    assert final_report.report.verdict == "human_gate"
    assert records["build_decision_packet"].status == "fail"
    assert "decision_packet_ref" not in result.state.artifacts_index


@pytest.mark.parametrize(
    "gate_input", ["typed_marker", "unrelated_gate_approval", "unrelated_gate_rejection"]
)
def test_review_request_is_not_satisfied_by_an_unrelated_gate_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate_input: str
) -> None:
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.ir.analytics.causal_graph import (
        CausalEdge,
        CausalGraphModel,
        EdgeSource,
        GraphType,
        persist_causal_graph_model,
    )
    from polisyos.ir.governance.gate import GateDecision, GateVerdict
    from polisyos.scientist.governance.passes.human_review_pass import HumanReviewRequiredPass
    from polisyos.scientist.nodes.builtins.governance.governance_gate_requests import (
        _create_gate_request,
        _serialize_gate_request_ref,
    )
    from polisyos.scientist.orchestration.kernel.gate_protocol import HumanGateProtocol

    monkeypatch.setattr(
        run_governance, "_RUNTIME_PIPELINE", ValidationPipeline([HumanReviewRequiredPass()])
    )
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = f"separate-review-{gate_input}"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tariff", "imports"],
        edges=[
            CausalEdge(
                src="tariff",
                dst="imports",
                sources=[EdgeSource.LLM_PRIOR],
                unsupported_by_evidence=True,
            )
        ],
        discovery_method="unit_test",
    )
    graph_ref = persist_causal_graph_model(
        ensure_ir_artifact_store(store), graph, return_selected_profile=True
    )
    initial = ExperimentState(
        run_id=run_id,
        params={"governance_profile": "strict"},
        artifacts_index={"causal_graph_ref": graph_ref},
    )
    if gate_input != "typed_marker":
        request, request_ref = _create_gate_request(
            ctx=ctx, protocol=HumanGateProtocol(run), state=initial
        )
        assert request_ref is not None
        initial.params["gate_request"] = request.model_dump(mode="json")
        initial.params["gate_request_ref"] = _serialize_gate_request_ref(request_ref)
        initial.params["gate_decision"] = GateDecision(
            request_id=request.request_id,
            run_id=run_id,
            verdict=(
                GateVerdict.REJECT
                if gate_input == "unrelated_gate_rejection"
                else GateVerdict.APPROVE
            ),
            approver_id="synthetic-test-reviewer",
        ).model_dump(mode="json")
    else:
        initial.params["gate_decision_typed"] = GateDecision(
            request_id="forged-request",
            run_id=run_id,
            verdict=GateVerdict.APPROVE,
            approver_id="synthetic-test-reviewer",
        ).model_dump(mode="json")
    registry = NodeRegistry()
    for node in (RunGovernanceNode(), RunEvaluatorNode(), BuildDecisionPacketNode()):
        registry.register(node)
    selected = default_workflow_spec()
    invocations = {item.alias: item for item in selected.nodes}
    workflow = selected.model_copy(
        update={
            "nodes": [
                invocations["run_governance"].model_copy(update={"depends_on": []}),
                invocations["run_evaluator"],
                invocations["refresh_governance"],
                invocations["build_decision_packet"].model_copy(
                    update={"depends_on": ["refresh_governance"]}
                ),
            ],
            "required_binds": ["run_id"],
        }
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    attempts = {item.basis.node_alias: item for item in run.read_runtime_invocation_attempts()}
    evaluator = attempts["run_evaluator"]
    bound_ctx = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=run_id,
            attempt_id=evaluator.basis.attempt_id,
            basis_ref=evaluator.basis_ref,
            require_successful_completion=True,
        ),
    )
    evaluator_input = _load_engine_owned_invocation_input_state(bound_ctx, result.state)
    assert evaluator_input is not None
    report = resolve_current_governance_report(ctx, evaluator_input)
    assert report.is_current
    assert report.report is not None
    assert any(issue["code"] == "HUMAN_REVIEW_REQUESTED" for issue in report.report.issues)
    assert evaluator_input.params["human_review_request_ref"]
    assert report.report.verdict == (
        "reject" if gate_input == "unrelated_gate_rejection" else "human_gate"
    )
    records = {item.alias: item for item in result.report.nodes}
    assert records["build_decision_packet"].status == "fail"
    assert "decision_packet_ref" not in result.state.artifacts_index
