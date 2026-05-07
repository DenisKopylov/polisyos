from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock, patch

from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_COMPILE_REPORT_REF,
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
        "artifacts_index.program_graph_ref",
        "artifacts_index.slot_layout_ref",
        "artifacts_index.treasury_plan_ref",
    )
    assert REPORT_COMPILE_REPORT_REF not in state.reports_index
    assert ARTIFACT_EXEC_PLAN_REF not in state.artifacts_index
    assert outcome.state.reports_index[REPORT_COMPILE_REPORT_REF] == compile_report_ref
    assert outcome.state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] == exec_plan_ref
