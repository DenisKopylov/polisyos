from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from polisyos.scientist.governance.report_currentness import (
    GOVERNANCE_REPORT_SOURCE_BASIS_ID,
    GOVERNANCE_REPORT_SOURCE_READ_PATHS,
    _state_read_projection,
    resolve_current_governance_report,
)

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.lex import ComplianceIssue
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.scientist.governance.pipeline import ValidationPipeline
from polisyos.scientist.governance.profiles import ValidationProfile
from polisyos.scientist.nodes.builtins.governance import run_governance
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.orchestration.engine.state import ExperimentState


class _Span:
    def set_attribute(self, _name: str, _value: object) -> None:
        return None

    def set_status(self, _status: object) -> None:
        return None


class _Tracer:
    @contextmanager
    def start_as_current_span(self, _name: str, *, attributes=None, kind=None):
        _ = attributes, kind
        yield _Span()


class _Timer:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        return None


class _Metrics:
    def time_governance_pass(self, _labels: dict[str, object]) -> _Timer:
        return _Timer()

    def record_validation_issue(self, **_kwargs: object) -> None:
        return None


class _PluginPassReadsPreviouslyUnlistedParam(ValidatorPass):
    seen_value: str | None = None

    @property
    def pass_id(self) -> str:
        return "strategic_response"

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        self.seen_value = str(ctx.state["params"]["plugin_owned_policy_input"])
        return []


def test_full_pass_context_basis_reconciles_actual_unlisted_param_consumption(
    tmp_path, monkeypatch
) -> None:
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    selected_pass = _PluginPassReadsPreviouslyUnlistedParam()
    monkeypatch.setattr(
        run_governance,
        "_RUNTIME_PIPELINE",
        ValidationPipeline([selected_pass], tracer=_Tracer(), metrics=_Metrics()),
    )
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="governance-currentness-test",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.governance.pass_context"),
    )
    producer_input = ExperimentState(
        run_id="governance-currentness-test",
        params={"plugin_owned_policy_input": "source-a"},
    )

    checks = run_governance._run_governance_checks(
        ctx, producer_input, ValidationProfile.mvp(), pii_scan_results=None
    )

    assert selected_pass.seen_value == "source-a"
    assert checks.pass_state["params"]["plugin_owned_policy_input"] == "source-a"
    assert GOVERNANCE_REPORT_SOURCE_BASIS_ID == "governance-pass-context-v2"
    assert tuple(RunGovernanceNode().spec.state_reads) == GOVERNANCE_REPORT_SOURCE_READ_PATHS
    assert {"params", "artifacts_index", "inputs", "reports_index"}.issubset(
        GOVERNANCE_REPORT_SOURCE_READ_PATHS
    )

    producer_output = producer_input.model_copy(deep=True)
    unchanged = producer_input.model_copy(deep=True)
    changed = producer_input.model_copy(deep=True)
    changed.params["plugin_owned_policy_input"] = "source-b"

    assert _state_read_projection(
        producer_input, producer_output, unchanged, RunGovernanceNode().spec
    )
    assert not _state_read_projection(
        producer_input, producer_output, changed, RunGovernanceNode().spec
    )

    # Removal probe: keep the pass consuming the value and the basis identifier,
    # but remove the full params map from the read contract. That proxy basis misses
    # the actual consumed input and incorrectly admits the changed state.
    narrowed_paths = tuple(
        path for path in RunGovernanceNode().spec.state_reads if path != "params"
    )
    narrowed_spec = RunGovernanceNode().spec.model_copy(
        update={"state_reads": list(narrowed_paths)}
    )
    assert _state_read_projection(
        producer_input,
        producer_output,
        changed,
        narrowed_spec,
        read_paths=narrowed_paths,
    )


def test_top_level_iteration_ref_is_outside_the_pass_context_basis() -> None:
    producer_input = ExperimentState(run_id="governance-currentness-iteration-test")
    producer_output = producer_input.model_copy(deep=True)
    later = producer_input.model_copy(deep=True)
    later.iteration_state_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "a" * 64),
        kind="scientist.iteration_state",
        media_type="application/json",
    )

    assert "iteration_state_ref" not in GOVERNANCE_REPORT_SOURCE_READ_PATHS
    assert _state_read_projection(producer_input, producer_output, later, RunGovernanceNode().spec)


def test_engine_emitted_report_recomputes_full_selected_pass_context_basis(
    tmp_path, monkeypatch
) -> None:
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.governance import report_currentness
    from polisyos.scientist.governance.pipeline import ValidationPipeline
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_RESEARCH_DAG_REF,
        REPORT_GOVERNANCE_REPORT_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.workflows.policy_design import (
        policy_design_workflow_spec,
    )

    selected_pass = _PluginPassReadsPreviouslyUnlistedParam()
    monkeypatch.setattr(
        run_governance,
        "_RUNTIME_PIPELINE",
        ValidationPipeline([selected_pass], tracer=_Tracer(), metrics=_Metrics()),
    )
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "R_governance_report_source_currentness"
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.governance.report_currentness"),
    )
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )

    node = RunGovernanceNode()
    packet_node = BuildDecisionPacketNode()
    packet_put_kinds: list[str] = []
    original_put_json = ctx.store.put_json

    def track_packet_put(obj, options, *args, **kwargs):
        packet_put_kinds.append(options.kind)
        return original_put_json(obj, options, *args, **kwargs)

    registry = NodeRegistry()
    registry.register(node)
    registry.register(packet_node)
    selected_workflow = policy_design_workflow_spec()
    selected_invocations = {item.alias: item for item in selected_workflow.nodes}
    governance_invocation = selected_invocations["run_governance"].model_copy(
        update={"depends_on": []}
    )
    packet_invocation = selected_invocations["build_decision_packet"].model_copy(
        update={"depends_on": ["run_governance"]}
    )
    # Keep the real selected-workflow invocations and feature gate while trimming
    # unrelated upstream producers from this portable producer-to-consumer slice.
    workflow = selected_workflow.model_copy(
        update={
            "nodes": [governance_invocation, packet_invocation],
            # The bounded workflow removes default input-producing nodes; keep
            # the real default invocations while requiring only its supplied bind.
            "required_binds": ["run_id"],
        }
    )
    producer_input = ExperimentState(
        run_id=run_id,
        params={"plugin_owned_policy_input": "source-a", "research_dag_enabled": True},
    )

    result = WorkflowExecutor(ctx, registry).execute(workflow, producer_input)
    report_ref = result.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    packet_record = next(
        record for record in result.report.nodes if record.alias == "build_decision_packet"
    )
    assert packet_record.status == "ok"
    decision_packet_ref = result.state.artifacts_index["decision_packet_ref"]
    workflow_packet = json.loads(store.get_bytes(decision_packet_ref))
    assert workflow_packet["governance"]["currentness"] == "current"
    assert selected_pass.seen_value == "source-a"

    # Reopen the exact engine-recorded packet input, which is the source state the
    # real BuildDecisionPacketNode consumed before adding its own output artifacts.
    from dataclasses import replace

    from polisyos.scientist.orchestration.engine.context import (
        _EngineInvocationBinding,
        _load_engine_owned_invocation_input_state,
    )

    packet_attempt = next(
        item
        for item in run.read_runtime_invocation_attempts()
        if item.basis.node_alias == "build_decision_packet"
    )
    packet_input_ctx = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id=packet_attempt.basis.run_id,
            attempt_id=packet_attempt.basis.attempt_id,
            basis_ref=packet_attempt.basis_ref,
            require_successful_completion=True,
        ),
    )
    packet_input_state = _load_engine_owned_invocation_input_state(packet_input_ctx, result.state)
    assert packet_input_state is not None
    assert "decision_packet_ref" not in packet_input_state.artifacts_index
    packet_input_admission = resolve_current_governance_report(ctx, packet_input_state, report_ref)
    assert packet_input_admission.status == "current", packet_input_admission.reason_code

    # Keep the report/pass markers and add a reference that no engine descendant
    # emitted. Full-map reconciliation must reject this present-but-unowned value.
    injected_state = packet_input_state.model_copy(deep=True)
    injected_state.artifacts_index["unowned_injected_ref"] = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "d" * 64),
        kind="scientist.unowned_currentness_injection",
        media_type="application/json",
    )
    injected_admission = resolve_current_governance_report(ctx, injected_state, report_ref)
    assert injected_admission.status == "stale"
    assert tuple(node.spec.state_reads) == GOVERNANCE_REPORT_SOURCE_READ_PATHS
    attempt = run.read_runtime_invocation_attempts()[0]
    assert attempt.basis.implementation_identity is not None
    assert attempt.outcome is not None
    assert attempt.outcome.outcome_state_ref is not None
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        _verified_finalization_predecessor,
        engine_invocation_identity_is_current,
    )

    assert engine_invocation_identity_is_current(
        ctx,
        attempt.basis,
        expected_component_id=str(node.spec.metadata.component_id),
    )
    assert result.state.reports_index["workflow_report"] is not None
    assert result.state.model_dump(mode="json")["reports_index"]["workflow_report"]
    assert ARTIFACT_RESEARCH_DAG_REF in result.state.artifacts_index
    finalization_ref = next(
        ref
        for ref in run.run_manifest.outputs
        if ref.kind == "scientist.workflow_state_finalization"
    )
    from polisyos.scientist.orchestration.engine.finalization import WorkflowStateFinalization

    finalization = WorkflowStateFinalization.model_validate_json(store.get_bytes(finalization_ref))
    assert finalization.workflow_spec_ref in run.run_manifest.inputs
    assert _verified_finalization_predecessor(ctx, result.state) is not None
    # The producer's full-map basis includes the maps as supplied to its pass. The
    # completed workflow has since added a packet (and finalizer sidecars) to those
    # same maps, so under the existing contract the post-workflow report is stale.
    # The packet itself correctly preserved the report's currentness at its exact
    # engine-recorded input above; no source-vs-derived exception is inferred here.
    current_admission = resolve_current_governance_report(ctx, result.state, report_ref)
    assert current_admission.status == "stale"
    assert current_admission.reason_code == "producer_source_projection_changed"

    # A live NodeSpec change after capture must not be hidden by the cached import-time
    # descriptor when the state_reads basis happens to remain unchanged.
    import inspect

    original_spec_descriptor = inspect.getattr_static(RunGovernanceNode, "spec")
    assert isinstance(original_spec_descriptor, property)

    def altered_spec(instance):
        original_spec = original_spec_descriptor.fget(instance)
        return original_spec.model_copy(
            update={"produces": [*original_spec.produces, "candidate_only.unowned_output"]}
        )

    with monkeypatch.context() as patcher:
        patcher.setattr(RunGovernanceNode, "spec", property(altered_spec))
        live_spec = RunGovernanceNode().spec
        assert live_spec.state_reads == list(GOVERNANCE_REPORT_SOURCE_READ_PATHS)
        assert "candidate_only.unowned_output" in live_spec.produces
        changed_owner = resolve_current_governance_report(ctx, result.state, report_ref)
        assert changed_owner.status != "current"

    from polisyos.core.artifacts.manifest import artifact_ref_identity_key

    owner_output_refs = run.read_runtime_owner_output_refs()
    owner_output_keys = {artifact_ref_identity_key(ref) for ref in owner_output_refs}
    assert artifact_ref_identity_key(finalization_ref) in owner_output_keys
    dag_ref = result.state.artifacts_index[ARTIFACT_RESEARCH_DAG_REF]
    assert artifact_ref_identity_key(dag_ref) in owner_output_keys

    # The finalization receipt and its CAS bytes remain present. Removing only the
    # persisted owner output event must make both the event replay and consumer stale.
    trace_path = run.trace_path
    assert trace_path is not None
    original_trace = trace_path.read_bytes()
    for target_ref in (finalization_ref, dag_ref):
        target_key = artifact_ref_identity_key(target_ref)
        retained: list[bytes] = []
        removed = 0
        for line in original_trace.splitlines(keepends=True):
            row = json.loads(line)
            outputs = row.get("refs", {}).get("outputs", [])
            matches_ref = any(
                artifact_ref_identity_key(ArtifactRef.model_validate(value)) == target_key
                for value in outputs
            )
            if row.get("event") == "RUN_OUTPUT_ADDED" and matches_ref:
                removed += 1
            else:
                retained.append(line)
        assert removed == 1
        try:
            trace_path.write_bytes(b"".join(retained))
            with pytest.raises(ValueError):
                run.read_runtime_owner_output_refs()
            without_owner_event = resolve_current_governance_report(ctx, result.state, report_ref)
            assert without_owner_event.status != "current"
        finally:
            trace_path.write_bytes(original_trace)

    packet_node = BuildDecisionPacketNode()

    # Keep all manifest and CAS markers intact while removing only the persisted
    # terminal owner event. A candidate cannot self-recover that missing event.
    terminal_rows = [
        json.loads(line)
        for line in original_trace.splitlines()
        if json.loads(line).get("phase") == "core"
        and json.loads(line).get("event") == "RUN_FINALIZED"
    ]
    assert len(terminal_rows) == 1
    assert finalization_ref in run.run_manifest.outputs
    assert store.verify(finalization_ref).ok
    assert store.verify(report_ref).ok
    trace_without_terminal = b"".join(
        line
        for line in original_trace.splitlines(keepends=True)
        if not (
            json.loads(line).get("phase") == "core"
            and json.loads(line).get("event") == "RUN_FINALIZED"
        )
    )
    try:
        trace_path.write_bytes(trace_without_terminal)
        with pytest.raises(ValueError, match="run_workflow_finalization_terminal_not_established"):
            run.read_runtime_workflow_finalization_ref()
        missing_terminal = resolve_current_governance_report(ctx, result.state, report_ref)
        assert missing_terminal.status != "current"

        packet_put_kinds.clear()
        with monkeypatch.context() as patcher:
            patcher.setattr(ctx.store, "put_json", track_packet_put)
            terminalless_packet = packet_node.execute(ctx, result.state)
        assert terminalless_packet.status == "fail"
        assert terminalless_packet.error is not None
        assert terminalless_packet.error.code == "governance_report_not_established"
        assert "scientist.decision_packet" not in packet_put_kinds
    finally:
        trace_path.write_bytes(original_trace)

    original_outputs = list(run.run_manifest.outputs)
    try:
        run.run_manifest.outputs[:] = [
            ref for ref in original_outputs if ref.kind != "scientist.workflow_state_finalization"
        ]
        missing_transition = resolve_current_governance_report(ctx, result.state, report_ref)
        assert missing_transition.status != "current"
        original_inputs = list(run.run_manifest.inputs)
        try:
            workflow_key = finalization.workflow_spec_ref
            run.run_manifest.inputs[:] = [ref for ref in original_inputs if ref != workflow_key]
            unlinked_transition = resolve_current_governance_report(ctx, result.state, report_ref)
            assert unlinked_transition.status != "current"
        finally:
            run.run_manifest.inputs[:] = original_inputs
    finally:
        run.run_manifest.outputs[:] = original_outputs

    changed_state = packet_input_state.model_copy(deep=True)
    changed_state.params["plugin_owned_policy_input"] = "source-b"
    admission = resolve_current_governance_report(ctx, changed_state, report_ref)

    assert admission.status == "stale"
    assert admission.reason_code == "producer_source_projection_changed"

    with monkeypatch.context() as patcher:
        patcher.setattr(ctx.store, "put_json", track_packet_put)
        stale_packet = packet_node.execute(ctx, changed_state)
    assert stale_packet.status == "fail"
    assert stale_packet.error is not None
    assert stale_packet.error.code == "governance_report_not_established"
    assert "scientist.decision_packet" not in packet_put_kinds

    # The current report also reaches the actual packet payload consumer with a
    # currentness projection, without requiring a later publication gate to pass.
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        __build_packet_payload__,
        _build_decision_packet_request,
    )

    current_payload, current_governance = __build_packet_payload__(
        ctx, packet_input_state, _build_decision_packet_request(ctx, packet_input_state)
    )
    assert current_governance is not None
    assert current_governance.__class__.__name__ == "GovernanceReport"
    assert current_payload["governance"]["currentness"] == "current"

    # The real workflow already exercised the public node, persisted its packet,
    # and read it back above. Reusing the report against the completed state now
    # fails closed because that state adds artifacts to a full-map source basis.
    packet_put_kinds.clear()
    with monkeypatch.context() as patcher:
        patcher.setattr(ctx.store, "put_json", track_packet_put)
        completed_state_packet = packet_node.execute(ctx, result.state)
    assert completed_state_packet.status == "fail"
    assert completed_state_packet.error is not None
    assert completed_state_packet.error.code == "governance_report_not_established"
    assert "scientist.decision_packet" not in packet_put_kinds

    # Removing one full map from only the resolver contract while the registered
    # node still supplies it is rejected by the real admission path. The pass read
    # and source-basis id remain intact.
    with monkeypatch.context() as patcher:
        patcher.setattr(
            report_currentness,
            "GOVERNANCE_REPORT_SOURCE_READ_PATHS",
            tuple(path for path in GOVERNANCE_REPORT_SOURCE_READ_PATHS if path != "params"),
        )
        narrowed_admission = resolve_current_governance_report(ctx, changed_state, report_ref)

    assert narrowed_admission.status == "not_established"
    assert narrowed_admission.reason_code == "producer_source_basis_contract_mismatch"


@pytest.mark.asyncio
async def test_async_builtin_governance_report_has_owner_finalization_currentness(
    tmp_path, monkeypatch
) -> None:
    """The async executor preserves the same protected builtin chain and currentness proof."""
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import ComponentId
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.governance import report_currentness
    from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    selected_pass = _PluginPassReadsPreviouslyUnlistedParam()
    monkeypatch.setattr(
        run_governance,
        "_RUNTIME_PIPELINE",
        ValidationPipeline([selected_pass], tracer=_Tracer(), metrics=_Metrics()),
    )
    store = FileSystemCAS(tmp_path / "cas")
    bundle_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "R_async_governance_report_currentness"
    run = RunContext.start(store=store, registry_bundle=bundle_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.governance.async_currentness"),
    )
    node = RunGovernanceNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="scientist_policy_verified",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="governance",
                node_id=ComponentId.parse(str(node.spec.metadata.component_id)),
            )
        ],
    )
    initial = ExperimentState(
        run_id=run_id,
        params={"plugin_owned_policy_input": "source-a", "research_dag_enabled": True},
    )

    result = await AsyncWorkflowExecutor(ctx, registry).execute(workflow, initial)

    report_ref = result.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    assert selected_pass.seen_value == "source-a"
    admission = report_currentness.resolve_current_governance_report(ctx, result.state, report_ref)
    assert admission.status == "current", admission.reason_code
    owner_output_refs = run.read_runtime_owner_output_refs()
    finalization_ref = next(
        ref for ref in owner_output_refs if ref.kind == "scientist.workflow_state_finalization"
    )
    assert artifact_ref_identity_key(finalization_ref) in {
        artifact_ref_identity_key(ref) for ref in owner_output_refs
    }


def test_finalization_does_not_hide_later_engine_source_mutation(tmp_path, monkeypatch) -> None:
    """A real later node source write remains stale beside terminal engine outputs."""
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import (
        Capability,
        ComponentId,
        ComponentKind,
        ComponentMetadata,
    )
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.governance.pipeline import ValidationPipeline
    from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    class LaterSourceMutationNode:
        def __init__(self) -> None:
            metadata = ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_mutate_governance_source@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Mutate governance source",
                description="Mutates a consumed source after governance",
                capabilities=Capability.SCIENTIST_NODE,
            )
            self._spec = NodeSpec(
                metadata=metadata,
                state_reads=["params.plugin_owned_policy_input"],
                state_writes=["params"],
            )

        @property
        def spec(self) -> NodeSpec:
            return self._spec

        def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            state.params["plugin_owned_policy_input"] = "source-b"
            return NodeOutcome(status="ok", state=state)

    selected_pass = _PluginPassReadsPreviouslyUnlistedParam()
    monkeypatch.setattr(
        run_governance,
        "_RUNTIME_PIPELINE",
        ValidationPipeline([selected_pass], tracer=_Tracer(), metrics=_Metrics()),
    )
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "R_governance_report_after_source_write"
    run = RunContext.start(store=store, registry_bundle=bundle, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.governance.report_currentness_after_write"),
    )
    governance = RunGovernanceNode()
    mutation = LaterSourceMutationNode()
    registry = NodeRegistry()
    registry.register(governance)
    registry.register(mutation)
    workflow = WorkflowSpec(
        workflow_id="governance_report_after_source_write",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="governance",
                node_id=ComponentId.parse(str(governance.spec.metadata.component_id)),
            ),
            NodeInvocation(
                alias="mutate_source",
                node_id=ComponentId.parse(str(mutation.spec.metadata.component_id)),
                depends_on=["governance"],
            ),
        ],
    )
    initial = ExperimentState(
        run_id=run_id,
        params={"plugin_owned_policy_input": "source-a"},
    )

    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    report_ref = result.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    assert result.state.params["plugin_owned_policy_input"] == "source-b"
    assert result.state.reports_index["workflow_report"] is not None
    admission = resolve_current_governance_report(ctx, result.state, report_ref)

    assert admission.status == "stale"
    assert admission.reason_code == "producer_source_projection_changed"


@pytest.mark.parametrize(
    ("field_name",),
    [("policy_output_bundle_ref",), ("policy_brief_ref",), ("champion_policy_dossier_ref",)],
)
def test_governance_currentness_binds_top_level_policy_projection_refs(field_name: str) -> None:
    source = ExperimentState(run_id="governance-top-level-ref-test")
    output = source.model_copy(deep=True)
    changed = source.model_copy(deep=True)
    setattr(
        changed,
        field_name,
        ArtifactRef(
            artifact_id=ArtifactID("sha256:" + "c" * 64),
            kind="scientist.policy_projection_test",
            media_type="application/json",
        ),
    )

    assert field_name in GOVERNANCE_REPORT_SOURCE_READ_PATHS
    assert not _state_read_projection(source, output, changed, RunGovernanceNode().spec)


class _SameIdReplacementRunGovernanceNode(RunGovernanceNode):
    def execute(self, ctx, state):
        return super().execute(ctx, state)


def test_same_component_id_replacement_does_not_prove_canonical_report_producer(
    tmp_path, monkeypatch
) -> None:
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import ComponentId
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.governance.pipeline import ValidationPipeline
    from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    selected_pass = _PluginPassReadsPreviouslyUnlistedParam()
    monkeypatch.setattr(
        run_governance,
        "_RUNTIME_PIPELINE",
        ValidationPipeline([selected_pass], tracer=_Tracer(), metrics=_Metrics()),
    )
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "R_governance_same_id_replacement"
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    ctx = ExecutionContext(
        store=store, run=run, logger=logging.getLogger("test.governance.same_id_replacement")
    )
    node = _SameIdReplacementRunGovernanceNode()
    registry = NodeRegistry()
    registry.register(node, override=True)
    workflow = WorkflowSpec(
        workflow_id="governance_same_id_replacement",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="governance",
                node_id=ComponentId.parse(str(node.spec.metadata.component_id)),
            )
        ],
    )
    source = ExperimentState(run_id=run_id, params={"plugin_owned_policy_input": "source-a"})

    result = WorkflowExecutor(ctx, registry).execute(workflow, source)
    report_ref = result.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    assert selected_pass.seen_value == "source-a"
    admission = resolve_current_governance_report(ctx, result.state, report_ref)

    assert admission.status == "not_established"
    assert admission.reason_code == "producer_implementation_identity_not_established"


def test_builtin_code_object_is_pinned_before_attempt_capture(monkeypatch) -> None:
    """Mutating the selected builtin callable before capture cannot rebind its owner."""
    from polisyos.scientist.orchestration.engine.component_identity import (
        capture_engine_component_identity,
    )

    from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
        BuildVerifiedPolicyReportNode,
    )

    node = BuildVerifiedPolicyReportNode()
    replacement_code = (lambda self, _ctx, _state: None).__code__
    monkeypatch.setattr(BuildVerifiedPolicyReportNode.execute, "__code__", replacement_code)

    assert (
        capture_engine_component_identity(
            node,
            str(node.spec.metadata.component_id),
            {},
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("executor_kind", ["sync", "async"])
async def test_engine_node_context_cannot_emit_core_owner_events_or_mutate_live_manifest(
    tmp_path, executor_kind: str
) -> None:
    """Node-facing context cannot mint lifecycle evidence; executor still owns it."""
    import logging

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    spoof_ref = ArtifactRef(
        artifact_id=ArtifactID("sha256:" + "b" * 64),
        kind="scientist.forged_owner_output",
        media_type="application/json",
    )
    observations: dict[str, bool] = {}

    class CoreEventForgeryNode:
        @property
        def spec(self):
            return NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse("scientist.node_core_event_forgery@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name="Core event forgery control",
                    description="Attempts forbidden Core writes through the node context.",
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                state_reads=[],
                state_writes=[],
                produces=[],
            )

        def _exercise(self, ctx, state):
            observations["run_context_type_preserved"] = isinstance(ctx.run, RunContext)
            for name, operation in (
                ("add_input", lambda: ctx.run.add_input(spoof_ref)),
                ("add_output", lambda: ctx.run.add_output(spoof_ref)),
                ("finalize", lambda: ctx.run.finalize(status="ok")),
                ("emit", lambda: ctx.run.emit("core", "RUN_OUTPUT_ADDED", outputs=[spoof_ref])),
            ):
                try:
                    operation()
                except (AttributeError, ValueError):
                    observations[name] = True
                else:
                    observations[name] = False

            # The manifest view is an isolated read snapshot. Mutating that snapshot
            # cannot change the engine-owned RunManifest or its persisted trace.
            ctx.run.run_manifest.outputs.append(spoof_ref)
            return NodeOutcome(status="ok", state=state)

        def execute(self, ctx, state):
            return self._exercise(ctx, state)

        async def execute_async(self, ctx, state):
            return self._exercise(ctx, state)

    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = f"R_node_cannot_forge_core_events_{executor_kind}"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store, run=run, logger=logging.getLogger("test.core_event_forgery")
    )
    node = CoreEventForgeryNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="node_core_event_forgery",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="forgery",
                node_id=ComponentId.parse(str(node.spec.metadata.component_id)),
            )
        ],
    )

    if executor_kind == "sync":
        result = WorkflowExecutor(ctx, registry).execute(workflow, ExperimentState(run_id=run_id))
    else:
        from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor

        result = await AsyncWorkflowExecutor(ctx, registry).execute(
            workflow, ExperimentState(run_id=run_id)
        )

    assert result.report.nodes[0].status == "ok"
    assert observations == {
        "run_context_type_preserved": True,
        "add_input": True,
        "add_output": True,
        "finalize": True,
        "emit": True,
    }
    owner_outputs = run.read_runtime_owner_output_refs()
    assert spoof_ref not in owner_outputs
    assert run.read_runtime_workflow_finalization_ref() == next(
        ref for ref in owner_outputs if ref.kind == "scientist.workflow_state_finalization"
    )
