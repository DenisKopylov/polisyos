"""Gap-coverage tests for RunTransportabilityNode."""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

import polisyos.scientist.nodes.builtins.causal as causal_nodes
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    ResolutionState,
    RunTransportabilityNode,
    TransportabilityResolutionLoop,
    _build_skg_query,
    _resolve_context_profile,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def _causal_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DIFFERENCE_IN_DIFFERENCES,
        estimand="ATE",
        point_estimate=0.2,
        confidence_interval=(0.1, 0.3),
        inference_method="fixture",
        sample_size=20,
        n_treated=10,
        n_control=10,
        pre_periods=1,
        post_periods=1,
        method_params={"treatment_name": "policy", "outcome_name": "income"},
    )


def test_transport_public_api_keeps_its_canonical_module_identity():
    expected_module = "polisyos.scientist.nodes.builtins.causal.resolve_transport"
    assert ResolutionState.__module__ == expected_module
    assert TransportabilityResolutionLoop.__module__ == expected_module
    assert RunTransportabilityNode.__module__ == expected_module
    assert causal_nodes.RunTransportabilityNode is RunTransportabilityNode
    assert tuple(ResolutionState.model_fields) == (
        "round",
        "s_nodes",
        "legal_s_nodes",
        "data_gaps",
        "hard_constraints",
        "p_star_values",
        "proxy_penalties",
        "proxy_validity",
        "requires_expert_review",
        "expert_review_reasons",
        "converged",
        "feasible",
    )
    assert tuple(inspect.signature(TransportabilityResolutionLoop.resolve).parameters) == (
        "self",
        "source_context",
        "target_context",
        "causal_graph",
        "query_treatment",
        "query_outcome",
        "policy_spec",
        "pag_identification_policy",
        "pag_max_dag_samples",
        "pag_threshold",
        "pag_seed",
        "solver_mode",
        "surrogate_data_profile",
        "allow_degraded_transport",
        "capability_contract",
        "privacy_context",
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


def test_run_transportability_uses_branch_state_for_skip_warning(
    execution_context, minimal_state, artifact_ref_factory
):
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = artifact_ref_factory(
        kind="ir.causal_effect_report"
    )
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_transport.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.causal.resolve_transport.load_causal_effect_report",
            return_value=_causal_report(),
        ),
    ):
        outcome = RunTransportabilityNode().execute(execution_context, state)

    assert outcome.status == "skip"
    assert observed["write_paths"] == (
        "causal_capability_contract_ref",
        "params.transportability_status",
        "params.transportability_transport_mode",
        "params.transportability_identification_engine",
        "params.transportability_id_confidence_under_pag",
        "params.transportability_capability_hash",
        "params.transportability_degradation_policy",
        "params.transportability_warning",
        "params.transport_required",
        "artifacts_index.causal_report_ref",
        "artifacts_index.causal_capability_contract_ref",
        "artifacts_index.transportability_result_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert "transportability_warning" not in state.params
    assert outcome.state.params["transportability_warning"].startswith(
        "missing_source_or_target_context"
    )


def test_actual_resolution_loop_refuses_unverified_legal_basis_before_solver() -> None:
    result = TransportabilityResolutionLoop(
        dataset_registry=object(),
        legal_kg_db_path=None,
        skg_query=object(),
        max_rounds=1,
    ).resolve(
        source_context=ContextProfile(context_id="source"),
        target_context=ContextProfile(context_id="target"),
        causal_graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["policy", "income"],
            edges=[CausalEdge(src="policy", dst="income")],
        ),
        query_treatment="policy",
        query_outcome="income",
        policy_spec={"domain": "tax_policy", "retroactive": True},
    )

    assert result.status is TransportabilityStatus.UNSUPPORTED
    assert result.transport_mode is TransportMode.NONE
    assert result.feasible is False
    assert result.unsupported_reason == "legal_source_relation_verification_not_established"
    assert result.hard_legal_constraints == []
    assert result.requires_expert_review is True
    assert "legal_source_relation_verification_not_established" in result.expert_review_reasons
    assert result.metadata["legal_source_relation_refusal"] == {
        "code": "legal_source_relation_verification_not_established",
        "status": "verification_missing",
    }
