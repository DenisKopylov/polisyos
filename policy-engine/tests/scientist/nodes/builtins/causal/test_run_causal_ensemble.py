"""Gap-coverage tests for RunCausalEnsembleNode."""

from __future__ import annotations

import pytest

from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import (
    RunCausalEnsembleNode,
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
                "causal_ensemble_members": [{"structural_causal_model_spec_ref": "sha256:" + "a" * 64}],
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
