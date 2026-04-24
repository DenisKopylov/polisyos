"""Gap-coverage tests for RunCausalQueriesNode."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.run_causal_queries import (
    RunCausalQueriesNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)


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


def test_fail_when_causal_query_payload_invalid(
    execution_context, minimal_state, artifact_ref_factory
):
    """Invalid params.causal_query payload -> fail."""
    ref = artifact_ref_factory(kind="ir.structural_causal_model_spec")
    state = minimal_state.model_copy(deep=True)
    state.params["causal_query"] = {"bad_field": "value"}
    state.params["structural_causal_model_ref"] = ref.model_dump(mode="json")

    outcome = RunCausalQueriesNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE


def test_causal_query_assertion_is_not_swallowed(
    execution_context, minimal_state, artifact_ref_factory, monkeypatch: pytest.MonkeyPatch
):
    ref = artifact_ref_factory(kind="ir.structural_causal_model_spec")
    state = minimal_state.model_copy(deep=True)
    state.params["causal_query"] = {
        "query_type": "interventional",
        "treatment_variable": "X",
        "treatment_value": 1.0,
        "outcome_variable": "Y",
        "n_samples": 128,
    }
    state.params["structural_causal_model_ref"] = ref.model_dump(mode="json")

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("query-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_queries.CausalQuery.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="query-broken"):
        RunCausalQueriesNode().execute(execution_context, state)


def test_run_causal_queries_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    scm_ref = artifact_ref_factory(kind="ir.structural_causal_model_spec")
    query_result_ref = artifact_ref_factory(kind="ir.causal_query_result")
    envelope_ref = artifact_ref_factory(kind="ir.uncertainty_envelope")
    method_result_ref = artifact_ref_factory(kind="ir.causal_query_method_result")
    method_evidence_ref = artifact_ref_factory(kind="ir.causal_query_method_evidence")

    query = SimpleNamespace(
        query_type=SimpleNamespace(value="interventional"),
        treatment_variable="X",
        outcome_variable="Y",
    )
    query_result = MagicMock()
    query_result.to_uncertainty_envelope.return_value = MagicMock()

    state = minimal_state.model_copy(deep=True)
    state.params["causal_query"] = {
        "query_type": "interventional",
        "treatment_variable": "X",
        "treatment_value": 1.0,
        "outcome_variable": "Y",
        "n_samples": 128,
    }
    state.params["structural_causal_model_ref"] = scm_ref.model_dump(mode="json")
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.CausalQuery.model_validate",
            return_value=query,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.StructuralCausalModelSpecRef.model_validate",
            return_value=scm_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.load_structural_causal_model_spec",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.SCMQueryData",
            side_effect=lambda **kwargs: kwargs,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.ensure_causal_methods_registered",
            return_value=None,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.run_job",
            return_value=SimpleNamespace(
                issues=[],
                final_state={
                    "query_result": {"ok": True},
                },
                method_result_ref=method_result_ref,
                method_evidence_ref=method_evidence_ref,
            ),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.CausalQueryResult.model_validate",
            return_value=query_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.persist_causal_query_result",
            return_value=query_result_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_queries.persist_uncertainty_envelope",
            return_value=envelope_ref,
        ),
    ):
        outcome = RunCausalQueriesNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params.query_treatment",
        "artifacts_index.structural_causal_model_spec_ref",
        "artifacts_index.causal_query_result_ref",
        "artifacts_index.causal_query_envelope_ref",
        "artifacts_index.causal_query_method_result_ref",
        "artifacts_index.causal_query_method_evidence_ref",
        "artifacts_index.causal_envelope_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_CAUSAL_QUERY_RESULT_REF not in state.artifacts_index
    assert outcome.state.params["query_treatment"] == "X"
    assert outcome.state.artifacts_index[ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF] == scm_ref
    assert outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_RESULT_REF] == query_result_ref
    assert outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF] == envelope_ref
    assert outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] == envelope_ref
    assert (
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF] == method_result_ref
    )
    assert (
        outcome.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF]
        == method_evidence_ref
    )
