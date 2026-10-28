from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

from polisyos.core.contracts.foundry import DerivedArtifact, MethodMetricBindingRequest
from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_METHOD_METRIC_BINDING_SET_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_COMPILE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def test_compile_success_with_mock_foundry(execution_context, minimal_state, artifact_ref_factory):
    """Compile succeeds when foundry port returns ok=True."""
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")
    compile_report_ref = artifact_ref_factory(kind="foundry.compile_report")
    exec_plan_ref = artifact_ref_factory(kind="foundry.exec_plan")

    mock_foundry = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.compile_report_ref = compile_report_ref
    mock_result.exec_plan_ref = exec_plan_ref
    mock_result.derived_refs = []
    mock_foundry.compile.return_value = mock_result

    ctx = replace(execution_context, foundry=mock_foundry)
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    outcome = CompileFoundryNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert REPORT_COMPILE_REPORT_REF in outcome.state.reports_index
    assert ARTIFACT_EXEC_PLAN_REF in outcome.state.artifacts_index
    mock_foundry.compile.assert_called_once()
    request = mock_foundry.compile.call_args.args[1]
    assert request.return_selected_profile is True


def test_compile_missing_inputs(execution_context, minimal_state):
    """Without foundry port, compile fails with missing port error."""
    outcome = CompileFoundryNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.missing_port"


def test_compile_missing_trinity_ref(execution_context, minimal_state):
    """With foundry port but no trinity ref, compile fails with missing input."""
    mock_foundry = MagicMock()
    ctx = replace(execution_context, foundry=mock_foundry)
    outcome = CompileFoundryNode().execute(ctx, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error.code == "node.missing_input"


def test_compile_error_result(execution_context, minimal_state, artifact_ref_factory):
    """When foundry compile returns ok=False, node outcome is fail."""
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")
    compile_report_ref = artifact_ref_factory(kind="foundry.compile_report")

    mock_foundry = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = False
    mock_result.compile_report_ref = compile_report_ref
    mock_result.exec_plan_ref = None
    mock_result.derived_refs = []
    mock_foundry.compile.return_value = mock_result

    ctx = replace(execution_context, foundry=mock_foundry)
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    outcome = CompileFoundryNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error.code == "foundry.compile_failed"


def test_compile_foundry_uses_branch_state_for_declared_outputs(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")
    compile_report_ref = artifact_ref_factory(kind="foundry.compile_report")
    exec_plan_ref = artifact_ref_factory(kind="foundry.exec_plan")

    mock_foundry = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.compile_report_ref = compile_report_ref
    mock_result.exec_plan_ref = exec_plan_ref
    mock_result.derived_refs = []
    mock_foundry.compile.return_value = mock_result

    ctx = replace(execution_context, foundry=mock_foundry)
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.compile.compile_foundry.branch_state",
        _spy_branch,
    ):
        outcome = CompileFoundryNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "reports_index.compile_report_ref",
        "reports_index.link_report_ref",
        "artifacts_index.exec_plan_ref",
        "artifacts_index.lowered_ir_ref",
        "artifacts_index.method_metric_binding_set_ref",
        "artifacts_index.program_graph_ref",
        "artifacts_index.slot_layout_ref",
        "artifacts_index.treasury_plan_ref",
    )
    assert REPORT_COMPILE_REPORT_REF not in state.reports_index
    assert ARTIFACT_EXEC_PLAN_REF not in state.artifacts_index
    assert outcome.state.reports_index[REPORT_COMPILE_REPORT_REF] == compile_report_ref
    assert outcome.state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] == exec_plan_ref


def test_compile_node_passes_explicit_metric_binding_and_stores_derived_ref(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    cas_store,
    tmp_path,
    monkeypatch,
):
    """Real selected inputs reach the constructor-forwarding seam; no execution is claimed."""
    from unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
        _exercise_public_execute_method_metric_source,
    )

    from polisyos.core.contracts.execution_plan import ExecutionPlan, MethodDagNode
    from polisyos.scientist.nodes.builtins.state_keys import INPUT_REGISTRY_BUNDLE_REF
    from polisyos.scientist.orchestration.llm.cycle import persist_candidate_execution_plan

    prepared = _exercise_public_execute_method_metric_source(
        tmp_path / "selected-inputs", monkeypatch, artifact_store=cas_store, prepare_only=True
    )
    selected_plan = ExecutionPlan(
        plan_id="constructor_forwarding_plan",
        run_id=minimal_state.run_id,
        method_dag=[
            MethodDagNode(
                node_id="ex_ante_node",
                method_fqn=prepared["method_fqn"],
                method_version=prepared["method_version"],
                backend=prepared["method_backend"],
                params={"poverty_line": None},
                reads_slots=["baseline", "scenario"],
                writes_slots=["result"],
            )
        ],
    )
    selected_plan_ref, trinity_ref = persist_candidate_execution_plan(
        cas_store, selected_plan, prepared["trinity_ref"]
    )
    compile_report_ref = artifact_ref_factory(kind="foundry.compile_report")
    exec_plan_ref = artifact_ref_factory(kind="foundry.exec_plan")
    binding_set_ref = artifact_ref_factory(kind="foundry.method_metric_binding_set")
    selection = MethodMetricBindingRequest(
        objective_id="objective_ex_ante_mean_change",
        node_id="ex_ante_node",
        output_slot_id="result",
    )
    mock_foundry = MagicMock()
    mock_foundry.compile.return_value = MagicMock(
        ok=True,
        compile_report_ref=compile_report_ref,
        exec_plan_ref=exec_plan_ref,
        derived_refs=[DerivedArtifact(role="method_metric_binding_set", ref=binding_set_ref)],
    )
    ctx = replace(execution_context, foundry=mock_foundry)
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref
    state.inputs[INPUT_REGISTRY_BUNDLE_REF] = prepared["registry_ref"]
    state.execution_plan_ref = selected_plan_ref

    outcome = CompileFoundryNode(method_metric_bindings=(selection,)).execute(ctx, state)

    assert outcome.status == "ok", outcome.error
    mock_foundry.compile.assert_called_once()
    request = mock_foundry.compile.call_args.args[1]
    assert request.schema_version == "1.2"
    assert request.policy_ref == trinity_ref
    assert request.method_execution_plan_ref == selected_plan_ref
    assert request.policy_ref.manifest_profile_sha256 is not None
    assert request.method_execution_plan_ref.manifest_profile_sha256 is not None
    assert request.method_metric_bindings == [selection]
    assert outcome.state.artifacts_index[ARTIFACT_METHOD_METRIC_BINDING_SET_REF] == binding_set_ref
    assert ARTIFACT_METHOD_METRIC_BINDING_SET_REF not in state.artifacts_index


def test_compile_node_threads_request_selected_metric_binding(
    execution_context, minimal_state, cas_store, artifact_ref_factory
):
    """The workflow-state selection reaches the real compiler request contract."""
    from polisyos.core.artifacts.store import PutOptions

    trinity = cas_store.put_json(
        {"fixture": "trinity"},
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    plan = cas_store.put_json(
        {"fixture": "plan"},
        PutOptions(kind="scientist.execution_plan", media_type="application/json"),
        return_selected_profile=True,
    )
    foundry = MagicMock()
    foundry.compile.return_value = MagicMock(
        ok=True,
        compile_report_ref=artifact_ref_factory(kind="foundry.compile_report"),
        exec_plan_ref=artifact_ref_factory(kind="foundry.exec_plan"),
        derived_refs=[],
    )
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity
    state.execution_plan_ref = plan
    selected = {"objective_id": "objective", "node_id": "method", "output_slot_id": "result"}
    state.params["method_metric_bindings"] = [selected]
    outcome = CompileFoundryNode().execute(replace(execution_context, foundry=foundry), state)
    assert outcome.status == "ok", outcome.error
    request = foundry.compile.call_args.args[1]
    assert request.schema_version == "1.2"
    assert request.method_metric_bindings == [MethodMetricBindingRequest.model_validate(selected)]
    assert "params.method_metric_bindings" in CompileFoundryNode().spec.state_reads


def test_compile_node_rejects_malformed_or_conflicting_metric_binding_before_foundry(
    execution_context, minimal_state, artifact_ref_factory
):
    """Malformed request or competing selected sets cannot reach the compiler."""
    foundry = MagicMock()
    ctx = replace(execution_context, foundry=foundry)
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = artifact_ref_factory(kind="ir.trinity_bundle")
    selection = MethodMetricBindingRequest(objective_id="a", node_id="n", output_slot_id="result")
    for raw in (
        None,
        "unexpected",
        [{"objective_id": "a", "node_id": "n", "output_slot_id": "result", "extra": True}],
        [selection.model_dump()] * 129,
    ):
        state.params["method_metric_bindings"] = raw
        outcome = CompileFoundryNode().execute(ctx, state)
        assert outcome.status == "fail", raw
        assert outcome.error is not None and outcome.error.code == "node.invalid_state"
        foundry.compile.assert_not_called()
    state.params["method_metric_bindings"] = [
        {"objective_id": "b", "node_id": "n", "output_slot_id": "result"}
    ]
    conflict = CompileFoundryNode(method_metric_bindings=(selection,)).execute(ctx, state)
    assert conflict.status == "fail"
    assert conflict.error is not None and "Conflicting" in conflict.error.message
    foundry.compile.assert_not_called()
