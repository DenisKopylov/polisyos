"""Gap-coverage tests for RunCausalQueriesNode."""

from __future__ import annotations

from polisyos.scientist.nodes.builtins.causal.run_causal_queries import (
    RunCausalQueriesNode,
)
from polisyos.scientist.nodes.builtins import errors as node_errors


def test_skip_when_no_causal_query(execution_context, minimal_state):
    """No params.causal_query -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunCausalQueriesNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No params.causal_query" in e.message for e in outcome.events)


def test_skip_when_no_scm_ref(execution_context, minimal_state):
    """Has causal_query but no structural_causal_model_ref -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_query": {
                    "query_type": "ate",
                    "treatment_variable": "X",
                    "outcome_variable": "Y",
                },
            },
        },
    )
    outcome = RunCausalQueriesNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("structural_causal_model_ref" in e.message for e in outcome.events)


def test_fail_when_causal_query_payload_invalid(execution_context, minimal_state, artifact_ref_factory):
    """Invalid params.causal_query payload -> fail."""
    ref = artifact_ref_factory(kind="ir.structural_causal_model_spec")
    state = minimal_state.model_copy(deep=True)
    state.params["causal_query"] = {"bad_field": "value"}
    state.params["structural_causal_model_ref"] = ref.model_dump(mode="json")

    outcome = RunCausalQueriesNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE
