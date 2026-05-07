from __future__ import annotations

from unittest.mock import patch

import pytest
from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EVALUATOR_REPORT_REF,
    ARTIFACT_ITERATION_STATE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def test_evaluator_success_no_governance(execution_context, minimal_state):
    """Evaluator runs without governance report, produces evaluator + iteration artifacts."""
    outcome = RunEvaluatorNode().execute(execution_context, minimal_state)
    assert outcome.status == "ok"
    assert ARTIFACT_EVALUATOR_REPORT_REF in outcome.state.artifacts_index
    assert ARTIFACT_ITERATION_STATE_REF in outcome.state.artifacts_index
    assert outcome.state.params.get("evaluator_verdict") is not None
    assert len(outcome.artifacts) == 2


def test_evaluator_no_metrics_defaults(execution_context, minimal_state):
    """Without budget or filtered params, evaluator still succeeds with defaults."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunEvaluatorNode().execute(execution_context, state)
    assert outcome.status == "ok"
    evaluator = outcome.state.params.get("evaluator")
    assert evaluator is not None


def test_evaluator_budget_boundary(execution_context, minimal_state):
    """When budget is fully consumed, evaluator still produces a verdict."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "run_budget_usd": 1.0,
                "run_cost_usd": 1.0,
            }
        }
    )
    outcome = RunEvaluatorNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state.params.get("evaluator_verdict") is not None


def test_evaluator_invalid_governance_report_emits_warning(
    execution_context, minimal_state, artifact_ref_factory
):
    governance_ref = artifact_ref_factory(kind="scientist.governance_report")
    state = minimal_state.model_copy(deep=True)
    state.reports_index[REPORT_GOVERNANCE_REPORT_REF] = governance_ref

    outcome = RunEvaluatorNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert any(event.code == "EVALUATOR_GOVERNANCE_REPORT_INVALID" for event in outcome.events)


def test_evaluator_transition_assertion_is_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("transition-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_evaluator.transition",
        _boom,
    )

    with pytest.raises(AssertionError, match="transition-broken"):
        RunEvaluatorNode().execute(execution_context, minimal_state)


def test_evaluator_uses_branch_state_for_declared_outputs(execution_context, minimal_state):
    state = minimal_state.model_copy(deep=True)
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.planning.run_evaluator.branch_state",
        _spy_branch,
    ):
        outcome = RunEvaluatorNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params.evaluator",
        "params.evaluator_verdict",
        "params.iteration_state_ref",
        "artifacts_index.evaluator_report_ref",
        "artifacts_index.iteration_state_ref",
        "evaluator_report_ref",
        "iteration_state_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_EVALUATOR_REPORT_REF not in state.artifacts_index
    assert ARTIFACT_ITERATION_STATE_REF in outcome.state.artifacts_index
