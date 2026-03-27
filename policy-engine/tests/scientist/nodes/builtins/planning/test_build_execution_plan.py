from __future__ import annotations

from polisyos.scientist.nodes.builtins.planning.build_execution_plan import BuildExecutionPlanNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXECUTION_PLAN_REF,
    INPUT_EXECUTION_PLAN_REF,
)


def test_plan_generation_default(execution_context, minimal_state):
    """Build a default execution plan when no plan is supplied."""
    outcome = BuildExecutionPlanNode().execute(execution_context, minimal_state)
    assert outcome.status == "ok"
    assert INPUT_EXECUTION_PLAN_REF in outcome.state.inputs
    assert ARTIFACT_EXECUTION_PLAN_REF in outcome.state.artifacts_index
    assert outcome.state.params.get("execution_plan_ref") is not None
    assert len(outcome.artifacts) >= 1


def test_plan_reuses_existing_ref(execution_context, minimal_state):
    """When execution_plan_ref is already set in params, reuse it."""
    plan_id = "sha256:" + "a" * 64
    state = minimal_state.model_copy(
        update={"params": {"execution_plan_ref": plan_id}}
    )
    outcome = BuildExecutionPlanNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert INPUT_EXECUTION_PLAN_REF in outcome.state.inputs
    ref = outcome.state.inputs[INPUT_EXECUTION_PLAN_REF]
    assert str(ref.artifact_id) == plan_id


def test_plan_from_raw_dict_fallback(execution_context, minimal_state):
    """When an invalid execution_plan dict is provided, fall back to default."""
    state = minimal_state.model_copy(
        update={"params": {"execution_plan": {"invalid_field": True}}}
    )
    outcome = BuildExecutionPlanNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert INPUT_EXECUTION_PLAN_REF in outcome.state.inputs
