"""Gap-coverage tests for RunSimulationNode."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXEC_PLAN_REF,
    INPUT_INPUT_BINDINGS_REF,
)


def test_fail_when_foundry_port_missing(execution_context, minimal_state, artifact_ref_factory):
    """ctx.foundry is None -> fail with ERROR_FOUNDATION_MISSING."""
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    # execution_context has foundry=None by default
    outcome = RunSimulationNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDATION_MISSING


def test_fail_when_exec_plan_ref_missing(execution_context, minimal_state, artifact_ref_factory):
    """No exec_plan_ref in artifacts_index -> fail with ERROR_MISSING_INPUT."""
    ctx = replace(execution_context, foundry=MagicMock())
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_MISSING_INPUT
    assert "exec_plan_ref" in outcome.error.message


def test_fail_when_input_bindings_missing(execution_context, minimal_state, artifact_ref_factory):
    """Has exec_plan but no input_bindings_ref -> fail with ERROR_MISSING_INPUT."""
    ctx = replace(execution_context, foundry=MagicMock())
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_MISSING_INPUT
    assert "input_bindings_ref" in outcome.error.message


def test_fail_when_foundry_execute_returns_not_ok(
    execution_context, minimal_state, artifact_ref_factory
):
    """When foundry.execute returns ok=False, node returns fail with ERROR_FOUNDRY_EXECUTE_FAILED."""
    mock_foundry = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = False
    mock_result.simulation_result_ref = None
    mock_result.derived_refs = []
    mock_result.notes = ["simulation diverged"]
    mock_foundry.execute.return_value = mock_result

    ctx = replace(execution_context, foundry=mock_foundry)
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED


def test_ok_when_foundry_execute_succeeds(
    execution_context, minimal_state, artifact_ref_factory
):
    """When foundry.execute returns ok=True, node returns ok."""
    mock_foundry = MagicMock()
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.simulation_result_ref = artifact_ref_factory(kind="foundry.simulation_result")
    mock_result.derived_refs = []
    mock_result.notes = []
    mock_foundry.execute.return_value = mock_result

    ctx = replace(execution_context, foundry=mock_foundry)
    ref = artifact_ref_factory(kind="foundry.exec_plan")
    bindings_ref = artifact_ref_factory(kind="foundry.input_bindings")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_EXEC_PLAN_REF] = ref
    state.inputs[INPUT_INPUT_BINDINGS_REF] = bindings_ref

    outcome = RunSimulationNode().execute(ctx, state)
    assert outcome.status == "ok"
