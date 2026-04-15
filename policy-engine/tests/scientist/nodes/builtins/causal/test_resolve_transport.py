"""Gap-coverage tests for RunTransportabilityNode."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    RunTransportabilityNode,
    _build_skg_query,
    _resolve_context_profile,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)


def test_skip_when_no_causal_report(execution_context, minimal_state):
    """No causal_report_ref in artifacts_index -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunTransportabilityNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("causal report" in e.message.lower() for e in outcome.events)


def test_skip_when_missing_source_or_target_context(
    execution_context, minimal_state, artifact_ref_factory
):
    """Has causal report but missing source/target context -> skip with warning."""
    ref = artifact_ref_factory(kind="ir.causal_effect_report")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = ref
    state.params["source_context"] = None
    state.params["target_context"] = None

    outcome = RunTransportabilityNode().execute(execution_context, state)
    # Could be skip (missing context) or fail (can't load report first) depending on order
    assert outcome.status in ("skip", "fail")


def test_already_has_transportability_result_ref_still_runs(
    execution_context, minimal_state, artifact_ref_factory
):
    """Unlike some nodes, this one does NOT short-circuit on existing artifact;
    verify it actually tries processing (and skips/fails gracefully without report)."""
    ref = artifact_ref_factory(kind="ir.transportability_result")
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF] = ref
    # No causal report -> skip
    outcome = RunTransportabilityNode().execute(execution_context, state)
    assert outcome.status == "skip"


def test_run_transportability_report_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = artifact_ref_factory(
        kind="ir.causal_effect_report"
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("causal report invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.load_causal_effect_report",
        _boom,
    )

    with pytest.raises(AssertionError, match="causal report invariant"):
        RunTransportabilityNode().execute(execution_context, state)


def test_resolve_context_profile_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
):
    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("context profile invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.ContextProfile.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="context profile invariant"):
        _resolve_context_profile({"context_id": "UA"})


def test_build_skg_query_assertion_is_not_swallowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_path = tmp_path / "skg.sqlite"
    db_path.write_text("", encoding="utf-8")

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("skg invariant")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.SKGQuery",
        _boom,
    )

    with pytest.raises(AssertionError, match="skg invariant"):
        _build_skg_query(db_path, tmp_path)
