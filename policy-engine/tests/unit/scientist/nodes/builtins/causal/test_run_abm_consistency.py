"""Gap-coverage tests for RunABMConsistencyCheckNode."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import (
    RunABMConsistencyCheckNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
)


def test_skip_when_no_mappings(execution_context, minimal_state):
    """No abm_macro_micro_mappings -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunABMConsistencyCheckNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("No params.abm_macro_micro_mappings" in e.message for e in outcome.events)


def test_fail_when_mappings_invalid(execution_context, minimal_state):
    """abm_macro_micro_mappings is not a list -> fail."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "abm_macro_micro_mappings": "not_a_list",
            },
        },
    )
    outcome = RunABMConsistencyCheckNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_INVALID_STATE


def test_already_has_alignment_report_returns_ok(
    execution_context, minimal_state, artifact_ref_factory
):
    """If alignment report already in artifacts_index, short-circuit ok."""
    ref = artifact_ref_factory(kind="ir.abm_alignment_report")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF] = ref
    outcome = RunABMConsistencyCheckNode().execute(execution_context, state)
    assert outcome.status == "ok"


def test_abm_mapping_assertion_is_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={"params": {"abm_macro_micro_mappings": [{"macro_variable": "gdp"}]}}
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("abm-mapping-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.run_abm_consistency.MacroMicroMapping.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="abm-mapping-broken"):
        RunABMConsistencyCheckNode().execute(execution_context, state)


def test_run_abm_consistency_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state
):
    state = minimal_state.model_copy(deep=True)
    state.params.update(
        {
            "abm_macro_micro_mappings": [
                {
                    "macro_variable": "gdp",
                    "abm_aggregation": "gdp",
                    "aggregation_function": "mean",
                    "agent_property": "firm_output",
                    "tolerance_method": "adaptive",
                }
            ],
            "abm_run_stats": {"gdp": {"effects": [1.0, 1.1, 0.9]}},
            "scm_effects": {"gdp": 1.0},
            "nested": {"baseline": True},
        }
    )
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.causal.run_abm_consistency.branch_state",
        _spy_branch,
    ):
        outcome = RunABMConsistencyCheckNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "artifacts_index.abm_alignment_report_ref",
        "artifacts_index.finite_state_abstraction_map_ref",
        "artifacts_index.abstraction_certificate_ref",
        "params.abm_alignment_overall_consistent",
        "params.abm_alignment_warnings",
        "params.abstraction_preservation_type",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_ABM_ALIGNMENT_REPORT_REF not in state.artifacts_index
    assert ARTIFACT_ABM_ALIGNMENT_REPORT_REF in outcome.state.artifacts_index
