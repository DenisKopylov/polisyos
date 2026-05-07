"""Gap-coverage tests for ResolveParametersNode."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
    ResolveParametersNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
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
    assert any(
        "required_parameters" in e.message or "parameter" in e.message.lower()
        for e in outcome.events
    )


def test_ok_when_already_present(execution_context, minimal_state, artifact_ref_factory):
    """If context_adaptive_parameter_bundle_ref already in artifacts_index, short-circuit ok."""
    ref = artifact_ref_factory(kind="ir.context_adaptive_parameter_bundle")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = ref
    outcome = ResolveParametersNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state


def test_target_context_assertion_is_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "target_context": {"country": "US", "year": 2025},
                "required_parameters": ["beta"],
            },
        }
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("context-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ContextProfile.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="context-broken"):
        ResolveParametersNode().execute(execution_context, state)


def test_resolve_parameters_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory, tmp_path
):
    graph_ref = artifact_ref_factory(kind="ir.causal_graph_model")
    bundle_ref = artifact_ref_factory(kind="ir.context_adaptive_parameter_bundle")
    db_path = tmp_path / "skg.duckdb"
    db_path.write_text("", encoding="utf-8")

    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
    state.params.update(
        {
            "target_context": {
                "context_id": "us-2025",
                "countries": ["US"],
                "publication_year": 2025,
            },
            "required_parameters": ["beta"],
            "skg_db_path": str(db_path),
            "nested": {"baseline": True},
        }
    )
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.load_causal_graph_model",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters._resolve_cross_graph_profile",
            return_value=None,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.SKGQuery",
        ) as skg_query_cls,
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterSelector",
        ) as selector_cls,
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ContextAdaptiveParameterBundle",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.persist_context_adaptive_parameter_bundle",
            return_value=bundle_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterTransferData",
            side_effect=lambda **kwargs: kwargs,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_parameters.ParameterTransfer.pure_step",
            return_value={
                "literature_priors": {"beta": {"mean": 1.0}},
                "uncertainty_multipliers": {"beta": 1.1},
                "runtime_backend_used": "numpy",
                "runtime_parameter_intervals": {"beta": [0.8, 1.2]},
                "runtime_ready": True,
            },
        ),
    ):
        skg_query_cls.return_value.latest_skg_version_id.return_value = "v1"
        skg_query_cls.return_value.skg_snapshot_ref.return_value = "snapshot"
        selector_cls.return_value.select_for_context.return_value = (
            {"mean": 1.0},
            MagicMock(),
        )
        outcome = ResolveParametersNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "artifacts_index.context_adaptive_parameter_bundle_ref",
        "params.literature_priors",
        "params.parameter_uncertainty_multipliers",
        "params.phase15_runtime_backend_used",
        "params.phase15_runtime_parameter_intervals",
        "params.phase15_runtime_ready",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF not in state.artifacts_index
    assert (
        outcome.state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] == bundle_ref
    )
    assert outcome.state.params["phase15_runtime_ready"] is True
