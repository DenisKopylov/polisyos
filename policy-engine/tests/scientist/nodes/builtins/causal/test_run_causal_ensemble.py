"""Gap-coverage tests for RunCausalEnsembleNode."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import (
    RunCausalEnsembleNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
)


def test_skip_when_ensemble_not_enabled(execution_context, minimal_state):
    """causal_ensemble_enabled not True -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunCausalEnsembleNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("not true" in e.message.lower() for e in outcome.events)


def test_skip_when_no_candidates_and_no_scm(execution_context, minimal_state):
    """Ensemble enabled but no members and no SCM in artifacts_index -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
            },
        },
    )
    outcome = RunCausalEnsembleNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No structural candidates" in e.message for e in outcome.events)


def test_fail_when_members_payload_invalid(execution_context, minimal_state):
    """causal_ensemble_members with invalid content -> fail."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
                # Each member entry must validate as _MemberPayload; a bare int will fail
                "causal_ensemble_members": [42],
            },
        },
    )
    outcome = RunCausalEnsembleNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE


def test_causal_ensemble_member_assertion_is_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_ensemble_enabled": True,
                "causal_ensemble_members": [
                    {"structural_causal_model_spec_ref": "sha256:" + "a" * 64}
                ],
            },
        },
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("ensemble-member-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._MemberPayload.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="ensemble-member-broken"):
        RunCausalEnsembleNode().execute(execution_context, state)


def test_run_causal_ensemble_uses_branch_state_for_success_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    scm_ref = artifact_ref_factory(kind="ir.structural_causal_model_spec")
    graph_ref = artifact_ref_factory(kind="ir.causal_graph_model")
    ensemble_ref = artifact_ref_factory(kind="ir.causal_model_ensemble")
    envelope_ref = artifact_ref_factory(kind="ir.uncertainty_envelope")
    query = SimpleNamespace()
    query_result = SimpleNamespace(result_distribution=[1.0, 1.1], result_mean=1.05)
    graph = CausalGraphModel.model_validate(
        {
            "graph_type": "dag",
            "nodes": ["X", "Y"],
            "edges": [{"src": "X", "dst": "Y"}],
        }
    )
    candidate = SimpleNamespace(
        order=0,
        scm_inline=None,
        scm_ref=scm_ref,
        graph_ref=None,
        query_result_ref=None,
        discovery_report_ref=None,
        discovery_method="pc",
        explicit_weight=0.7,
        bootstrap_stability=0.8,
    )

    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "causal_ensemble_enabled": True,
            "causal_query": {
                "query_type": "ate",
                "treatment_variable": "X",
                "outcome_variable": "Y",
            },
            "nested": {"baseline": True},
        }
    )
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._resolve_members",
            return_value=([candidate], []),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.CausalQuery.model_validate",
            return_value=query,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.ensure_causal_methods_registered",
            return_value=None,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.StructuralCausalModelSpecRef.model_validate",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.load_structural_causal_model_spec",
            return_value=SimpleNamespace(fit_method="pc"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._load_graph_for_candidate",
            return_value=(graph, graph_ref),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._run_member_query",
            return_value=query_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble._build_consensus_graph",
            return_value=(None, []),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.persist_causal_model_ensemble",
            return_value=ensemble_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.run_causal_ensemble.persist_uncertainty_envelope",
            return_value=envelope_ref,
        ),
    ):
        outcome = RunCausalEnsembleNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params.causal_ensemble_member_count",
        "params.causal_ensemble_methods",
        "params.causal_ensemble_warning",
        "artifacts_index.causal_ensemble_ref",
        "artifacts_index.causal_ensemble_envelope_ref",
        "artifacts_index.causal_envelope_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_CAUSAL_ENSEMBLE_REF not in state.artifacts_index
    assert outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_REF] == ensemble_ref
    assert outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENSEMBLE_ENVELOPE_REF] == envelope_ref
    assert outcome.state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] == envelope_ref
