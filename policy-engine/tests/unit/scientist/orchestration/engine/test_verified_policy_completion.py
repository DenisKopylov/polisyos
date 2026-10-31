"""Completed diagnostic transitions retain the exact full Engine predecessor."""

from __future__ import annotations

import logging
import sys
import types
from dataclasses import dataclass

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
)
from polisyos.core.components import ComponentId
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.trinity import persist_trinity_bundle_artifact
from polisyos.scientist.governance.report import load_governance_report_artifact
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_body import (
    BuildVerifiedPolicyBodyNode,
)
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportCompositionNode,
)
from polisyos.scientist.nodes.builtins.decide.evaluate_verified_policy_phase5 import (
    EvaluateVerifiedPolicyPhase5Node,
)
from polisyos.scientist.nodes.builtins.decide.select_policy_candidate import (
    SelectPolicyCandidateNode,
)
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.orchestration.engine import component_identity, input_ports
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeInputContract,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.validation.policy_verified import (
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceVerificationReport,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
)
from polisyos.scientist.validation.policy_verified.phase5_candidate import (
    load_phase5_candidate_assessment,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate

_CHANGE_METADATA = RunGovernanceNode().spec.metadata.model_copy(
    update={"component_id": ComponentId.parse("scientist.node_completion_input_change@1.0.0")}
)
_CHANGE_SPEC = NodeSpec(
    metadata=_CHANGE_METADATA,
    state_reads=["params.hidden", "artifacts_index.phase5_candidate_assessment_ref"],
    state_writes=["params.hidden", "artifacts_index.phase5_candidate_assessment_ref"],
)


@dataclass(frozen=True)
class _ChangeCompletionInput:
    mode: str

    @property
    def spec(self) -> NodeSpec:
        return _CHANGE_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        changed = branch_state(state, write_paths=_CHANGE_SPEC.state_writes).state
        if self.mode == "hidden":
            changed.params["hidden"] = {"archive": ["different predecessor"]}
        elif self.mode == "missing":
            del changed.artifacts_index["phase5_candidate_assessment_ref"]
        else:
            ref = state.artifacts_index["phase5_candidate_assessment_ref"]
            manifest = ctx.store.get_manifest(ref)
            foreign = ctx.store.put_bytes(
                ctx.store.get_bytes(ref),
                PutOptions(
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    schema=manifest.artifact_schema,
                    canon=manifest.canon,
                    inputs=[
                        *manifest.inputs,
                        input_ref_from_artifact_ref(ref, role="foreign_attempt"),
                    ],
                ),
                return_selected_profile=True,
            )
            assert foreign.artifact_id == ref.artifact_id
            assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
            changed.artifacts_index["phase5_candidate_assessment_ref"] = foreign
        return NodeOutcome(status="ok", state=changed)


def _transition_case(tmp_path, monkeypatch, mode: str, *, append_composition: bool = False):
    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(tmp_path / "thresholds"))
    thresholds = JudgeThresholdRegistry()
    thresholds.record(thresholds.snapshot().entries[0])
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    candidate = _candidate()
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store), candidate.trinity_bundle
        ).model_dump(mode="json")
    )
    request_ref = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            schema_version="1.1",
            request_id="completed-occurrence",
            policy_question="Synthetic limited composition?",
            jurisdiction="synthetic",
            jurisdiction_source="policy_request_jurisdiction",
        ),
    )
    source_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id="completed-occurrence"),
        inputs=[input_ref_from_artifact_ref(request_ref, role="policy_request_frame")],
    )
    options_ref = persist_policy_option_set(
        store,
        PolicyOptionSet(request_id="completed-occurrence"),
        inputs=[
            input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
            input_ref_from_artifact_ref(source_ref, role="source_verification_report"),
        ],
    )
    state = ExperimentState(
        run_id=f"completed-occurrence-{mode}",
        inputs={"registry_bundle_ref": registry_ref, "trinity_bundle_ref": trinity_ref},
        params={
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "hidden": {"archive": ["preserved original"]},
        },
        policy_request_ref=request_ref,
        policy_option_set_ref=options_ref,
        source_verification_report_ref=source_ref,
    )
    run = RunContext.start(store, registry_ref, run_id=state.run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    body, selected, governance, phase5 = (
        BuildVerifiedPolicyBodyNode(),
        SelectPolicyCandidateNode(),
        RunGovernanceNode(),
        EvaluateVerifiedPolicyPhase5Node(),
    )
    registry = NodeRegistry()
    for node in (body, selected, governance, phase5):
        registry.register(node)
    nodes = [
        NodeInvocation(alias="body", node_id=body.spec.metadata.component_id),
        NodeInvocation(alias="candidate", node_id=selected.spec.metadata.component_id),
        NodeInvocation(
            alias="initial_governance",
            node_id=governance.spec.metadata.component_id,
            depends_on=["body", "candidate"],
        ),
        NodeInvocation(
            alias="phase5",
            node_id=phase5.spec.metadata.component_id,
            depends_on=["initial_governance"],
        ),
    ]
    dependencies = ["phase5"]
    if mode in {"hidden", "missing", "foreign_profile"}:
        registry.register(_ChangeCompletionInput(mode))
        nodes.append(
            NodeInvocation(
                alias="change", node_id=_CHANGE_METADATA.component_id, depends_on=dependencies
            )
        )
        dependencies = ["change"]
    nodes.append(
        NodeInvocation(
            alias="final_governance",
            node_id=governance.spec.metadata.component_id,
            depends_on=dependencies,
        )
    )
    if append_composition:
        composition = BuildVerifiedPolicyReportCompositionNode()
        registry.register(composition)
        nodes.append(
            NodeInvocation(
                alias="completed_report",
                node_id=composition.spec.metadata.component_id,
                depends_on=["final_governance"],
            )
        )
    seen = []
    handles = []
    execute_code = RunGovernanceNode.execute.__code__

    def observe(frame, event, _arg):
        # A call-only observer sees the genuine pending attempt without replacing
        # any protected producer/helper or manufacturing a completion record.
        if event != "call" or frame.f_code is not execute_code:
            return
        active_ctx, active_state = frame.f_locals["ctx"], frame.f_locals["state"]
        binding = active_ctx._engine_invocation
        assert binding is not None
        attempt = next(
            item
            for item in run.read_runtime_invocation_attempts()
            if item.basis_ref == binding.basis_ref
        )
        if attempt.basis.node_alias != "final_governance":
            return
        initial = next(
            item
            for item in run.read_runtime_invocation_attempts()
            if item.basis.node_alias == "initial_governance"
        )
        basis_ref = initial.basis_ref
        if mode == "foreign_initial_attempt":
            basis_ref = next(
                item.basis_ref
                for item in run.read_runtime_invocation_attempts()
                if item.basis.node_alias == "phase5"
            )
        seen.append(
            input_ports.reconcile_verified_policy_phase5_transition(
                active_ctx, active_state, basis_ref
            )
        )
        handles.append((active_ctx, active_state.model_copy(deep=True), initial.basis_ref))
        sys.settrace(previous)

    previous = sys.gettrace()
    sys.settrace(observe)
    try:
        result = WorkflowExecutor(ctx, registry).execute(
            WorkflowSpec(workflow_id="completed_policy_occurrence", nodes=nodes), state
        )
    finally:
        sys.settrace(previous)
    assert next(item for item in result.report.nodes if item.alias == "phase5").status == "ok", [
        (item.alias, item.error) for item in result.report.nodes
    ]
    assert len(seen) == 1
    return ctx, result, seen[0], handles[0]


def test_real_completed_phase5_reconciles_only_its_declared_full_state_transition(
    tmp_path, monkeypatch
):
    ctx, result, admission, handle = _transition_case(tmp_path, monkeypatch, "none")
    assert admission.is_current, admission
    assert result.state.params["hidden"] == {"archive": ["preserved original"]}
    attempts = ctx.run.read_runtime_invocation_attempts()
    phase5 = next(item for item in attempts if item.basis.node_alias == "phase5")
    assert phase5.outcome is not None
    assessment_ref = next(
        ref
        for ref in phase5.outcome.output_refs
        if ref.kind == "scientist.policy_phase5_candidate_assessment"
    )
    assessment = load_phase5_candidate_assessment(ctx.store, assessment_ref)
    initial = load_governance_report_artifact(ctx.store, assessment.governance_ref)
    assert initial.invocation_binding is not None
    assert initial.invocation_binding.attempt_basis_ref == handle[2]
    # An honestly completed occurrence cannot keep acting as a pending consumer.
    assert not input_ports.reconcile_verified_policy_phase5_transition(*handle).is_current


@pytest.mark.parametrize(
    ("mode", "status", "reason"),
    [
        ("hidden", "stale", "phase5_transition_full_state_changed"),
        ("missing", "not_established", "phase5_transition_selected_assessment_absent"),
        ("foreign_profile", "stale", "completed_phase5_occurrence_not_latest"),
        (
            "foreign_initial_attempt",
            "not_established",
            "phase5_transition_initial_governance_mismatch",
        ),
    ],
)
def test_completed_phase5_refuses_changed_state_profile_and_attempt(
    tmp_path, monkeypatch, mode, status, reason
):
    _ctx, _result, admission, _handle = _transition_case(tmp_path, monkeypatch, mode)
    assert (admission.status, admission.reason_code) == (status, reason)


_NESTED_SCALAR = 1


def _nested_pass_helper() -> object:
    return _NESTED_SCALAR


class _NestedPass:
    def evaluate(self) -> None:
        _nested_pass_helper()


_NESTED_PASS_TYPES = (_NestedPass,)
_NESTED_COMPONENT = "scientist.node_nested_definition_probe@1.0.0"
_NESTED_SPEC = InputAwareNodeSpec(
    metadata=_CHANGE_METADATA.model_copy(
        update={"component_id": ComponentId.parse(_NESTED_COMPONENT)}
    ),
    state_reads=["run_id"],
    state_writes=[],
    input_contract=NodeInputContract(
        component_id=_NESTED_COMPONENT,
        contract_id="nested_definition_probe.v1",
        state_paths=("run_id",),
    ),
)


class _NestedDefinitionProbe:
    @property
    def spec(self) -> InputAwareNodeSpec:
        return _NESTED_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        for pass_type in _NESTED_PASS_TYPES:
            pass_type().evaluate()
        return NodeOutcome(status="ok", state=state)


def test_nested_owned_pass_helper_is_reconciled_before_any_callback(tmp_path, monkeypatch):
    monkeypatch.setitem(
        component_identity._OWNERS,
        _NESTED_COMPONENT,
        component_identity._owner(_NestedDefinitionProbe),
    )
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    registry = NodeRegistry()
    registry.register(_NestedDefinitionProbe())
    workflow = WorkflowSpec(
        workflow_id="nested_definition",
        nodes=[NodeInvocation(alias="nested", node_id=_NESTED_SPEC.metadata.component_id)],
    )

    def execute(run_id):
        run = RunContext.start(store, registry_ref, run_id=run_id)
        ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
        return WorkflowExecutor(ctx, registry).execute(workflow, ExperimentState(run_id=run_id))

    assert execute("nested-original").report.nodes[0].status == "ok"
    calls = []

    def counterfeit():
        calls.append("changed nested pass helper")

    monkeypatch.setattr(sys.modules[__name__], "_nested_pass_helper", counterfeit)
    result = execute("nested-replaced")
    assert (result.report.nodes[0].status, calls) == ("fail", [])
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.code == "node.input_port_refused"
    assert calls == []


@pytest.mark.parametrize("replacement", [True, 1.0])
def test_nested_definition_scalar_type_cannot_alias_its_held_value(
    tmp_path, monkeypatch, replacement
):
    monkeypatch.setitem(
        component_identity._OWNERS,
        _NESTED_COMPONENT,
        component_identity._owner(_NestedDefinitionProbe),
    )
    monkeypatch.setattr(sys.modules[__name__], "_NESTED_SCALAR", replacement)
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store, registry_ref, run_id="nested-scalar")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    registry = NodeRegistry()
    registry.register(_NestedDefinitionProbe())
    result = WorkflowExecutor(ctx, registry).execute(
        WorkflowSpec(
            workflow_id="nested_scalar",
            nodes=[NodeInvocation(alias="nested", node_id=_NESTED_SPEC.metadata.component_id)],
        ),
        ExperimentState(run_id=run.run_manifest.run_id),
    )
    assert result.report.nodes[0].status == "fail"
    assert result.report.nodes[0].error.code == "node.input_port_refused"


def test_capture_cannot_rebaseline_a_changed_nested_helper(tmp_path, monkeypatch):
    original_capture = component_identity._input_definition_bindings
    calls = []

    def changed_helper():
        calls.append("changed after original binding capture")

    def capture_then_change(node_type):
        bindings = original_capture(node_type)
        monkeypatch.setattr(sys.modules[__name__], "_nested_pass_helper", changed_helper)
        return bindings

    monkeypatch.setattr(component_identity, "_input_definition_bindings", capture_then_change)
    monkeypatch.setitem(
        component_identity._OWNERS,
        _NESTED_COMPONENT,
        component_identity._owner(_NestedDefinitionProbe),
    )
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store, registry_ref, run_id="capture_changed")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    registry = NodeRegistry()
    registry.register(_NestedDefinitionProbe())
    result = WorkflowExecutor(ctx, registry).execute(
        WorkflowSpec(
            workflow_id="capture_changed",
            nodes=[NodeInvocation(alias="nested", node_id=_NESTED_SPEC.metadata.component_id)],
        ),
        ExperimentState(run_id=run.run_manifest.run_id),
    )
    assert (result.report.nodes[0].status, calls) == ("fail", [])
    assert result.report.nodes[0].error.code == "node.input_port_refused"


def test_immutable_code_cache_preserves_distinct_code_identity():
    original = _nested_pass_helper.__code__
    first = types.FunctionType(original, globals())
    second = types.FunctionType(original.replace(co_filename="different_source.py"), globals())
    assert first.__code__ is not second.__code__
    assert component_identity._code_sha256(first) != component_identity._code_sha256(second)


def test_mutable_code_constant_keeps_a_fresh_legacy_digest():
    def scalar():
        return "constant"

    marker = []
    constants = tuple(
        marker if value == "constant" else value for value in scalar.__code__.co_consts
    )
    function = types.FunctionType(scalar.__code__.replace(co_consts=constants), globals())
    first = component_identity._code_sha256(function)
    marker.append("changed actual returned constant")
    assert function() == ["changed actual returned constant"]
    assert component_identity._code_sha256(function) != first


def test_typed_owner_reference_projection_preserves_full_profile_identity(tmp_path):
    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.core.contracts.scientist import VerifiedPolicyReportRef
    from polisyos.scientist.validation.policy_verified.models import (
        VerifiedPolicyReport,
        load_verified_policy_report,
        persist_verified_policy_report,
    )

    store = FileSystemCAS(tmp_path / "cas")
    body = VerifiedPolicyReport(request_id="typed-reference", executive_summary="Candidate only.")
    typed = persist_verified_policy_report(store, body)
    assert isinstance(typed, VerifiedPolicyReportRef)
    assert load_verified_policy_report(FileSystemCAS(store.root), typed) == body
    state = ExperimentState(run_id="typed-reference", verified_policy_report_ref=typed)
    selected = input_ports._selected_role_ref(state, "verified_policy_report_ref")
    assert type(selected) is ArtifactRef
    assert selected != typed
    assert artifact_ref_identity_key(selected) == artifact_ref_identity_key(typed)
    foreign = persist_verified_policy_report(
        store,
        body,
        inputs=[input_ref_from_artifact_ref(typed, role="different_profile")],
    )
    assert foreign.artifact_id == typed.artifact_id
    assert artifact_ref_identity_key(foreign) != artifact_ref_identity_key(selected)
