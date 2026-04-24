"""Gap-coverage tests for ReconcileCausalGraphNode."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
    ReconcileCausalGraphNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)


def test_skip_when_no_data_causal_graph(execution_context, minimal_state):
    """No data_causal_graph in params and no method result -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = ReconcileCausalGraphNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No data causal graph" in e.message for e in outcome.events)


def test_already_reconciled_returns_ok(execution_context, minimal_state, artifact_ref_factory):
    """If reconciled graph already in artifacts_index, short-circuit ok."""
    ref = artifact_ref_factory(kind="ir.causal_graph_model")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = ref
    outcome = ReconcileCausalGraphNode().execute(execution_context, state)
    assert outcome.status == "ok"


def test_fail_when_reconcile_pure_step_returns_incomplete(execution_context, minimal_state):
    """When pure_step returns missing reconciled_graph or diagnostics, fail."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "data_causal_graph": {
                    "graph_type": "dag",
                    "nodes": ["X", "Y"],
                    "edges": [{"src": "X", "dst": "Y"}],
                },
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph.ReconcileCausalGraph.pure_step",
        return_value={"reconciled_graph": None, "diagnostics": None},
    ):
        outcome = ReconcileCausalGraphNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE


def test_fail_when_pure_step_raises(execution_context, minimal_state):
    """When ReconcileCausalGraph.pure_step raises, node returns fail."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "data_causal_graph": {
                    "graph_type": "dag",
                    "nodes": ["X", "Y"],
                    "edges": [{"src": "X", "dst": "Y"}],
                },
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph.ReconcileCausalGraph.pure_step",
        side_effect=RuntimeError("reconciliation engine crashed"),
    ):
        outcome = ReconcileCausalGraphNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED
    assert "reconciliation engine crashed" in outcome.error.message


def test_fail_when_pure_step_returns_graph_but_no_diagnostics(execution_context, minimal_state):
    """When pure_step returns reconciled_graph but diagnostics is None, fail."""
    from unittest.mock import MagicMock

    state = minimal_state.model_copy(
        update={
            "params": {
                "data_causal_graph": {
                    "graph_type": "dag",
                    "nodes": ["A", "B"],
                    "edges": [{"src": "A", "dst": "B"}],
                },
            },
        },
    )
    mock_graph = MagicMock()
    with patch(
        "polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph.ReconcileCausalGraph.pure_step",
        return_value={"reconciled_graph": mock_graph, "diagnostics": None},
    ):
        outcome = ReconcileCausalGraphNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE
    assert "did not return graph and diagnostics" in outcome.error.message


def test_reconcile_fragment_load_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "scm_fragment_refs": [str(artifact_ref_factory(kind="ir.scm_fragment").artifact_id)]
            }
        },
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("fragment loader invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph.load_scm_fragment",
        _boom,
    )

    with pytest.raises(AssertionError, match="fragment loader invariant"):
        ReconcileCausalGraphNode().execute(execution_context, state)


def test_reconcile_literature_prior_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    state = minimal_state.model_copy(deep=True)
    state.params["data_causal_graph"] = {
        "graph_type": "dag",
        "nodes": ["X", "Y"],
        "edges": [{"src": "X", "dst": "Y"}],
    }
    state.artifacts_index[ARTIFACT_LITERATURE_PRIOR_REF] = artifact_ref_factory(
        kind="ir.literature_causal_prior"
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("literature prior invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph.load_literature_causal_prior",
        _boom,
    )

    with pytest.raises(AssertionError, match="literature prior invariant"):
        ReconcileCausalGraphNode().execute(execution_context, state)


def test_reconcile_causal_graph_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "data_causal_graph": {
                    "graph_type": "dag",
                    "nodes": ["X", "Y"],
                    "edges": [{"src": "X", "dst": "Y"}],
                },
            },
        }
    )
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}
    reconciled_graph = CausalGraphModel.model_validate(
        {
            "graph_type": "dag",
            "nodes": ["X", "Y"],
            "edges": [{"src": "X", "dst": "Y"}],
        }
    )

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph.ReconcileCausalGraph.pure_step",
            return_value={
                "reconciled_graph": reconciled_graph,
                "diagnostics": type(
                    "_Diagnostics",
                    (),
                    {"model_dump": staticmethod(lambda mode="json": {"status": "ok"})},
                )(),
                "needs_expert_review": False,
                "warnings": [],
            },
        ),
    ):
        outcome = ReconcileCausalGraphNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "artifacts_index.reconciled_causal_graph_ref",
        "artifacts_index.alignment_report_ref",
        "artifacts_index.interface_mapping_ref",
        "artifacts_index.composition_certificate_ref",
        "artifacts_index.composition_failure_card_bundle_ref",
        "params.needs_expert_review",
        "params.reconciliation_diagnostics",
        "params.reconciliation_warnings",
        "params.composition_blocking_reasons",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF not in state.artifacts_index
    assert ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in outcome.state.artifacts_index
