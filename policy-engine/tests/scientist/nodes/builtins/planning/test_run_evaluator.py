from __future__ import annotations

from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EVALUATOR_REPORT_REF,
    ARTIFACT_ITERATION_STATE_REF,
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
