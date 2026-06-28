"""Gap-coverage tests for RunCausalEvaluationNode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
)


def test_skip_when_no_observational_data_ref(execution_context, minimal_state):
    """No observational_data_ref on state -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    assert state.observational_data_ref is None
    outcome = RunCausalEvaluationNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("observational_data_ref" in e.message.lower() for e in outcome.events)
    assert outcome.skip_blocker is not None
    assert outcome.skip_blocker.missing_input == "observational_data_ref"
    assert outcome.skip_blocker.blocker_code == "gy_phase2_blocked_input_producer_missing"


def test_fail_when_observational_data_cannot_be_loaded(
    execution_context, minimal_state, artifact_ref_factory
):
    """observational_data_ref points to invalid artifact -> fail with ERROR_MISSING_INPUT."""
    ref = artifact_ref_factory(kind="ir.observational_data", data={"garbage": True})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )
    outcome = RunCausalEvaluationNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_MISSING_INPUT


def test_skip_with_no_method_fqn_defaults(execution_context, minimal_state):
    """When no method FQN and no observational data, should skip gracefully."""
    state = minimal_state.model_copy(
        update={
            "params": {},
            "causal_method_fqn": None,
        },
    )
    outcome = RunCausalEvaluationNode().execute(execution_context, state)
    assert outcome.status == "skip"


def test_fail_when_method_job_has_issues(execution_context, minimal_state, artifact_ref_factory):
    """When run_job returns issues, node returns fail with ERROR_FOUNDRY_EXECUTE_FAILED."""
    from unittest.mock import MagicMock, patch

    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    mock_job_result = MagicMock()
    mock_job_result.issues = ["convergence failure", "insufficient data"]
    mock_data = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            return_value=mock_data,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            return_value=mock_job_result,
        ),
    ):
        outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED
    assert "Causal method job failed" in outcome.error.message


def test_fail_when_method_output_missing_report(
    execution_context, minimal_state, artifact_ref_factory
):
    """When run_job returns no issues but output has no report, node returns fail."""
    from unittest.mock import MagicMock, patch

    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    mock_job_result = MagicMock()
    mock_job_result.issues = []
    mock_job_result.final_state = {"no_report_key": True}
    mock_data = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            return_value=mock_data,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            return_value=mock_job_result,
        ),
    ):
        outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED
    assert "missing report" in outcome.error.message


def test_assertion_in_observational_data_load_is_not_swallowed(
    execution_context, minimal_state, artifact_ref_factory
):
    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            side_effect=AssertionError("observational invariant"),
        ),
    ):
        with pytest.raises(AssertionError, match="observational invariant"):
            RunCausalEvaluationNode().execute(execution_context, state)


def test_fail_when_method_output_report_is_invalid(
    execution_context, minimal_state, artifact_ref_factory
):
    ref = artifact_ref_factory(kind="ir.observational_data", data={"dummy": 1})
    state = minimal_state.model_copy(
        update={
            "observational_data_ref": ref,
            "params": {
                "causal_method_fqn": "causal.inference.synthetic_control",
            },
        },
    )

    mock_job_result = MagicMock()
    mock_job_result.issues = []
    mock_job_result.final_state = {"report": {"broken": True}}
    mock_job_result.method_result_ref = None
    mock_job_result.method_evidence_ref = None
    mock_data = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation._load_observational_data",
            return_value=mock_data,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.ensure_causal_methods_registered",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.run_job",
            return_value=mock_job_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation.CausalEffectReport.model_validate",
            side_effect=ValueError("bad report"),
        ),
    ):
        outcome = RunCausalEvaluationNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED
    assert "report is invalid" in outcome.error.message
