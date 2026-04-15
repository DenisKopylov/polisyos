"""Gap-coverage tests for RunABMConsistencyCheckNode."""

from __future__ import annotations

import pytest

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
