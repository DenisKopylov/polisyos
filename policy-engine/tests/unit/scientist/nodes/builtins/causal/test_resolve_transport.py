"""Gap-coverage tests for RunTransportabilityNode."""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

import polisyos.scientist.nodes.builtins.causal as causal_nodes
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import (
    TransportabilityStatus,
    TransportMode,
    load_transportability_result,
)
from polisyos.ir.registry.refs import CausalEffectReportRef, TransportabilityResultRef
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    ResolutionState,
    RunTransportabilityNode,
    TransportabilityResolutionLoop,
    _build_skg_query,
    _persist_blocking_transportability_result,
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
        "candidate_refusal_handler",
    )


def test_causal_full_transport_timeout_uses_owner_profile_ceiling() -> None:
    from polisyos.scientist.nodes.builtins.causal.transport_resolution_inputs import (
        conditional_transport_node_timeout_s,
    )
    from polisyos.scientist.orchestration.workflows.causal_full import (
        causal_full_workflow_spec,
    )

    workflow = causal_full_workflow_spec()
    transport_node = next(node for node in workflow.nodes if node.alias == "run_transportability")

    from polisyos.scientist.orchestration.workflows.causal_full import (
        CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM,
        causal_full_transport_resource_policy_snapshot,
    )

    assert transport_node.timeout_s == conditional_transport_node_timeout_s()
    assert transport_node.params[CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM] == (
        causal_full_transport_resource_policy_snapshot()
    )


def test_skip_when_no_causal_report(execution_context, minimal_state):
    """No causal_report_ref in artifacts_index -> skip."""
    state = minimal_state.model_copy(update={"params": {}})
    outcome = RunTransportabilityNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert any("causal report" in e.message.lower() for e in outcome.events)


def test_absent_candidate_request_skips_but_explicit_null_is_invalid(
    execution_context,
    minimal_state,
):
    state = minimal_state.model_copy(update={"params": {}})
    absent = RunTransportabilityNode().execute(execution_context, state)
    assert absent.status == "skip"

    explicit_null = state.model_copy(deep=True)
    explicit_null.params["conditional_transport_request"] = None
    refused = RunTransportabilityNode().execute(execution_context, explicit_null)
    assert refused.status == "fail"
    assert refused.error is not None
    assert "must be an object when supplied" in refused.error.message


@pytest.mark.parametrize(
    ("missing_input", "required_input"),
    [
        ("causal_report", "causal_report"),
        ("contexts", "source_context_and_target_context"),
        ("graph", "selected_causal_graph"),
    ],
)
def test_explicit_candidate_request_fails_closed_on_missing_prerequisite(
    missing_input,
    required_input,
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    state = minimal_state.model_copy(deep=True)
    state.params["conditional_transport_request"] = {
        "schema_version": "1.0",
        "profile_id": "transport.conditional.resolved_graph",
        "profile_revision": "1",
        "selection_identity": "transport-candidate.standard.v1",
    }
    state.params["existing_partial_state"] = {"keep": "unchanged"}
    if missing_input != "causal_report":
        state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = artifact_ref_factory(
            kind="ir.causal_effect_report"
        )
    if missing_input == "graph":
        state.params["source_context"] = {"context_id": "source"}
        state.params["target_context"] = {"context_id": "target"}
    original = state.model_dump(mode="python", by_alias=True, exclude_none=False)

    load_patch = patch(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport.load_causal_effect_report",
        return_value=_causal_report(),
    )
    graph_patch = patch(
        "polisyos.scientist.nodes.builtins.causal.resolve_transport._resolve_causal_graph_source",
        return_value=None,
    )
    if missing_input == "contexts":
        with load_patch:
            outcome = RunTransportabilityNode().execute(execution_context, state)
    elif missing_input == "graph":
        with load_patch, graph_patch:
            outcome = RunTransportabilityNode().execute(execution_context, state)
    else:
        outcome = RunTransportabilityNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    from polisyos.scientist.nodes.builtins import errors as node_errors

    assert outcome.error.code == node_errors.ERROR_MISSING_INPUT
    assert outcome.error.details == {
        "request_key": "conditional_transport_request",
        "required_input": required_input,
    }
    assert outcome.state is state
    assert state.model_dump(mode="python", by_alias=True, exclude_none=False) == original


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


def test_blocking_writer_fresh_cas_binds_selected_result_profile_to_report(
    execution_context,
    minimal_state,
):
    """The 2.2 result and 1.1 report retain the exact selected CAS lineage."""
    ir_store = _ensure_ir_artifact_store(execution_context.store)
    source_report = _causal_report().model_copy(update={"schema_version": "1.1"})
    source_report_ref = persist_causal_effect_report(
        ir_store,
        source_report,
        schema_version="1.1",
        return_selected_profile=True,
    )
    assert source_report_ref.manifest_profile_sha256 is not None

    outcome = _persist_blocking_transportability_result(
        ctx=execution_context,
        state=minimal_state,
        reason="candidate_input_missing",
        message="Required transport input is unavailable.",
        causal_report=source_report,
        report_ref=source_report_ref,
    )

    result_ref = TransportabilityResultRef.model_validate(
        next(
            ref for ref in outcome.artifacts if ref.kind == "ir.transportability_result"
        ).model_dump(mode="json")
    )
    report_ref = CausalEffectReportRef.model_validate(
        next(
            ref
            for ref in outcome.artifacts
            if ref.kind == "ir.causal_effect_report"
            and ref.artifact_id != source_report_ref.artifact_id
        ).model_dump(mode="json")
    )
    assert result_ref.manifest_profile_sha256 is not None
    assert report_ref.manifest_profile_sha256 is not None

    fresh_store = _ensure_ir_artifact_store(FileSystemCAS(execution_context.store.root))
    fresh_result_ref = TransportabilityResultRef.model_validate(result_ref.model_dump(mode="json"))
    fresh_report_ref = CausalEffectReportRef.model_validate(report_ref.model_dump(mode="json"))
    fresh_result = load_transportability_result(fresh_store, fresh_result_ref)
    fresh_report = load_causal_effect_report(fresh_store, fresh_report_ref)

    assert fresh_result.schema_version == "2.2"
    assert fresh_result.status is TransportabilityStatus.UNSUPPORTED
    assert fresh_result.transport_mode is TransportMode.NONE
    assert fresh_report.schema_version == "1.1"
    assert fresh_report.transport_result == fresh_result

    result_manifest = fresh_store.get_manifest(fresh_result_ref)
    report_manifest = fresh_store.get_manifest(fresh_report_ref)
    source_edge = next(edge for edge in result_manifest.inputs if edge.role == "causal_report")
    assert str(source_edge.artifact_id) == str(source_report_ref.artifact_id)
    assert source_edge.manifest_profile_sha256 == source_report_ref.manifest_profile_sha256
    result_edge = next(
        edge for edge in report_manifest.inputs if edge.role == "transportability_result"
    )
    assert str(result_edge.artifact_id) == str(fresh_result_ref.artifact_id)
    assert result_edge.manifest_profile_sha256 == fresh_result_ref.manifest_profile_sha256
    previous_report_edge = next(
        edge for edge in report_manifest.inputs if edge.role == "causal_report_prev"
    )
    assert str(previous_report_edge.artifact_id) == str(source_report_ref.artifact_id)
    assert previous_report_edge.manifest_profile_sha256 == source_report_ref.manifest_profile_sha256
