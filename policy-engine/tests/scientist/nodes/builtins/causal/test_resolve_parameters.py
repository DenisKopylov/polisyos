"""Gap-coverage tests for ResolveParametersNode."""

from __future__ import annotations

from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
    ResolveParametersNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
)


def test_skip_when_missing_target_context(execution_context, minimal_state):
    """No params.target_context -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "required_parameters": ["param_a"],
            },
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("target_context" in e.message for e in outcome.events)


def test_skip_when_target_context_invalid(execution_context, minimal_state):
    """Invalid target_context payload that cannot parse as ContextProfile -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "target_context": "not_a_dict",
                "required_parameters": ["beta"],
            },
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("target_context" in e.message for e in outcome.events)


def test_skip_when_missing_required_parameters(execution_context, minimal_state):
    """No params.required_parameters -> skip at first guard (target_context absent)."""
    state = minimal_state.model_copy(
        update={
            "params": {},
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    # Without target_context the first guard triggers
    assert len(outcome.events) >= 1


def test_skip_when_required_parameters_empty_list(execution_context, minimal_state):
    """Valid target_context but required_parameters is an empty list -> skip."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "target_context": {"country": "US", "year": 2025},
                "required_parameters": [],
            },
        },
    )
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("required_parameters" in e.message or "parameter" in e.message.lower() for e in outcome.events)


def test_ok_when_already_present(execution_context, minimal_state, artifact_ref_factory):
    """If context_adaptive_parameter_bundle_ref already in artifacts_index, short-circuit ok."""
    ref = artifact_ref_factory(kind="ir.context_adaptive_parameter_bundle")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = ref
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state
