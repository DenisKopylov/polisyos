"""Gap-coverage tests for BuildLiteraturePriorNode."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.analytics.literature import LiteratureCausalPrior
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.build_literature_prior import (
    BuildLiteraturePriorNode,
    _optional_float,
    _optional_int,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_LITERATURE_PRIOR_REF


class _AssertionInt:
    def __int__(self) -> int:
        raise AssertionError("int invariant")


class _AssertionFloat:
    def __float__(self) -> float:
        raise AssertionError("float invariant")


def test_skip_when_no_causal_variables(execution_context, minimal_state):
    """No causal_variables and no causal_graph_nodes -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = BuildLiteraturePriorNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No causal variables" in e.message for e in outcome.events)


def test_fail_when_pure_step_raises(execution_context, minimal_state):
    """When BuildLiteraturePrior.pure_step raises, the node returns fail."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_variables": ["X", "Y"],
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        side_effect=RuntimeError("SKG unavailable"),
    ):
        outcome = BuildLiteraturePriorNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_FOUNDRY_EXECUTE_FAILED


def test_fail_when_pure_step_assertion_is_not_swallowed(execution_context, minimal_state):
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_variables": ["X", "Y"],
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        side_effect=AssertionError("literature invariant"),
    ):
        with pytest.raises(AssertionError, match="literature invariant"):
            BuildLiteraturePriorNode().execute(execution_context, state)


def test_fail_when_pure_step_returns_no_prior(execution_context, minimal_state):
    """When pure_step returns empty dict (no prior/graph), the node returns fail."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_variables": ["X", "Y"],
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        return_value={},
    ):
        outcome = BuildLiteraturePriorNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE
    assert "did not return prior and graph" in outcome.error.message


def test_ok_when_already_present(execution_context, minimal_state, artifact_ref_factory):
    """If literature_prior_ref already in artifacts_index, short-circuit ok."""
    ref = artifact_ref_factory(kind="ir.literature_causal_prior")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_LITERATURE_PRIOR_REF] = ref
    outcome = BuildLiteraturePriorNode().execute(execution_context, state)
    assert outcome.status == "ok"
    # State should be returned unchanged (no events)
    assert outcome.state is state


def test_fail_when_pure_step_returns_only_prior_no_graph(execution_context, minimal_state):
    """When pure_step returns prior but no graph, the node returns fail."""
    from unittest.mock import MagicMock

    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_variables": ["A", "B", "C"],
            },
        },
    )
    mock_prior = MagicMock()
    with patch(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        return_value={"literature_prior": mock_prior, "literature_prior_graph": None},
    ):
        outcome = BuildLiteraturePriorNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE


def test_environment_audit_summary_is_written_when_present(execution_context, minimal_state):
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_variables": ["X", "Y"],
                "discovery_data": [[0.0, 1.0], [0.1, 1.1], [2.0, 3.0], [2.1, 3.1]],
                "discovery_variable_names": ["X", "Y"],
                "discovery_environment_labels": ["a", "a", "b", "b"],
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        return_value={
            "literature_prior": LiteratureCausalPrior(),
            "literature_prior_graph": CausalGraphModel(
                graph_type=GraphType.CPDAG,
                nodes=["X", "Y"],
                edges=[],
                discovery_method="literature_prior",
            ),
            "warnings": [],
        },
    ):
        outcome = BuildLiteraturePriorNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert outcome.state.params["environment_audit_status"] == "ok"
    assert outcome.state.params["environment_audit_summary"]["n_environments"] == 2


def test_environment_audit_skips_without_environment_labels(execution_context, minimal_state):
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_variables": ["X", "Y"],
                "discovery_data": [[0.0, 1.0], [0.1, 1.1]],
                "discovery_variable_names": ["X", "Y"],
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        return_value={
            "literature_prior": LiteratureCausalPrior(),
            "literature_prior_graph": CausalGraphModel(
                graph_type=GraphType.CPDAG,
                nodes=["X", "Y"],
                edges=[],
                discovery_method="literature_prior",
            ),
            "warnings": [],
        },
    ):
        outcome = BuildLiteraturePriorNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert outcome.state.params["environment_audit_status"] == "skipped"
    assert (
        "environment_audit_missing_domain_labels"
        in outcome.state.params["environment_audit_summary"]["warnings"]
    )


def test_environment_audit_misconfiguration_does_not_fail_node(execution_context, minimal_state):
    state = minimal_state.model_copy(
        update={
            "params": {
                "causal_variables": ["X", "Y"],
                "discovery_data": [[0.0, 1.0], [0.1, 1.1]],
                "discovery_variable_names": ["X", "Y"],
                "discovery_environment_labels": ["a"],
            },
        },
    )
    with patch(
        "polisyos.scientist.nodes.builtins.causal.build_literature_prior.BuildLiteraturePrior.pure_step",
        return_value={
            "literature_prior": LiteratureCausalPrior(),
            "literature_prior_graph": CausalGraphModel(
                graph_type=GraphType.CPDAG,
                nodes=["X", "Y"],
                edges=[],
                discovery_method="literature_prior",
            ),
            "warnings": [],
        },
    ):
        outcome = BuildLiteraturePriorNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert outcome.state.params["environment_audit_status"] == "degraded"


def test_optional_int_assertion_is_not_swallowed() -> None:
    with pytest.raises(AssertionError, match="int invariant"):
        _optional_int(_AssertionInt(), default=1)


def test_optional_float_assertion_is_not_swallowed() -> None:
    with pytest.raises(AssertionError, match="float invariant"):
        _optional_float(_AssertionFloat(), default=0.5)
