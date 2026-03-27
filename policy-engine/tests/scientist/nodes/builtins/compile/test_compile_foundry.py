from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from polisyos.core.artifacts.manifest import ArtifactRef
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
