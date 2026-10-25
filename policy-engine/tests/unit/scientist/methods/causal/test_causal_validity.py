from __future__ import annotations

import logging
from types import SimpleNamespace

from polisyos.core.artifacts import (
    InputRef,
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.interference import (
    MAUPInvarianceCertificate,
    MAUPPartitionCheck,
    SpatialHodgeDiagnostics,
    SpatialHodgeScaleProfile,
)
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.runtime.http.resilience import guard_runtime_cas
from polisyos.scientist.methods.causal import validity as validity_module
from polisyos.scientist.methods.causal.validity import (
    _build_spatial_interference_check,
    persist_causal_validity_bundle,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _bound_test_input(store: FileSystemCAS, *, label: str) -> InputRef:
    source_ref = store.put_json(
        {"label": label},
        PutOptions(kind="test.selected_profile_anchor", media_type="application/json"),
    )
    return input_ref_from_artifact_ref(
        profile_bound_ref(store, source_ref), role="selected_profile_anchor"
    )


def test_causal_validity_bundle_records_ownerless_claim_limitation(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_validity_ownerless",
    )
    context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.validity.ownerless"),
    )
    state = ExperimentState(run_id="R_causal_validity_ownerless")

    monkeypatch.setattr(validity_module, "_coerce_graph_validity_data", lambda **_: None)
    monkeypatch.setattr(validity_module, "_build_confidence_surface", lambda **_: {})
    for helper in (
        "_build_sensitivity_check",
        "_build_spatial_interference_check",
        "_run_icp_check",
        "_run_proximal_check",
        "_run_recoverability_check",
        "_run_pag_refinement_check",
    ):
        monkeypatch.setattr(
            validity_module,
            helper,
            lambda **_: {"status": "not_applicable"},
        )
    monkeypatch.setattr(validity_module, "_collect_bundle_warnings", lambda _: [])
    monkeypatch.setattr(validity_module, "_build_capability_matrix", lambda **_: {})
    monkeypatch.setattr(
        validity_module,
        "project_causal_validity_bundle_claims",
        lambda *_, **__: object(),
    )

    ref = persist_causal_validity_bundle(
        ctx=context,
        state=state,
        report=SimpleNamespace(
            method=SimpleNamespace(value="synthetic_control"),
            status=SimpleNamespace(value="success"),
        ),
        method_fqn="causal.inference.synthetic_control@1.0.0",
        method_params={},
        observational_data=SimpleNamespace(metadata={}),
        seed=7,
        sensitivity_ref=None,
        sensitivity_auto={},
        inputs=(),
    )

    assert ref is not None
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    assert payload["claim_ledger_status"] == "not_established"
    assert payload["claim_ledger_limitation_code"] == "claim_ledger_owner_not_established"
    assert "claims_ref" not in payload


def test_pag_refinement_preserves_selected_graph_profile_in_output_lineage(
    monkeypatch,
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_causal_validity_profiled_pag",
    )
    context = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.causal.validity.profiled_pag"),
    )
    ir_store = _ensure_ir_artifact_store(store)
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
    )
    graph_ref = persist_causal_graph_model(
        ir_store,
        graph,
        inputs=[_bound_test_input(store, label="producer-input-selected")],
        return_selected_profile=True,
    )
    latest_graph_ref = persist_causal_graph_model(
        ir_store,
        graph,
        inputs=[_bound_test_input(store, label="producer-input-alternative")],
        return_selected_profile=True,
    )
    current_default_graph_ref = profile_bound_ref(
        store, graph_ref.model_copy(update={"manifest_profile_sha256": None})
    )
    assert str(graph_ref.artifact_id) == str(latest_graph_ref.artifact_id)
    assert store.get_bytes(graph_ref) == store.get_bytes(latest_graph_ref)
    assert graph_ref.manifest_profile_sha256 is not None
    assert latest_graph_ref.manifest_profile_sha256 is not None
    assert graph_ref.manifest_profile_sha256 != latest_graph_ref.manifest_profile_sha256
    selected_graph_ref = next(
        candidate_ref
        for candidate_ref in (graph_ref, latest_graph_ref)
        if candidate_ref.manifest_profile_sha256
        != current_default_graph_ref.manifest_profile_sha256
    )
    assert selected_graph_ref.manifest_profile_sha256 is not None
    assert (
        selected_graph_ref.manifest_profile_sha256
        != current_default_graph_ref.manifest_profile_sha256
    )
    graph_ref = selected_graph_ref
    state = ExperimentState(
        run_id="R_causal_validity_profiled_pag",
        artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref},
        params={
            "causal_validity": {
                "enable_icp_invariance": False,
                "enable_proximal": False,
                "enable_recoverability": False,
                "enable_pag_refinement": True,
            }
        },
    )
    monkeypatch.setattr(validity_module, "_coerce_graph_validity_data", lambda **_: None)
    monkeypatch.setattr(validity_module, "_build_confidence_surface", lambda **_: {})
    for helper in (
        "_build_sensitivity_check",
        "_build_spatial_interference_check",
        "_run_icp_check",
        "_run_proximal_check",
        "_run_recoverability_check",
    ):
        monkeypatch.setattr(
            validity_module,
            helper,
            lambda **_: {"status": "not_applicable"},
        )
    monkeypatch.setattr(validity_module, "_collect_bundle_warnings", lambda _: [])
    monkeypatch.setattr(validity_module, "_build_capability_matrix", lambda **_: {})
    monkeypatch.setattr(
        validity_module,
        "project_causal_validity_bundle_claims",
        lambda *_, **__: object(),
    )

    bundle_ref = persist_causal_validity_bundle(
        ctx=context,
        state=state,
        report=SimpleNamespace(
            method=SimpleNamespace(value="synthetic_control"),
            status=SimpleNamespace(value="success"),
        ),
        method_fqn="causal.inference.synthetic_control@1.0.0",
        method_params={},
        observational_data=SimpleNamespace(metadata={}),
        seed=7,
        sensitivity_ref=None,
        sensitivity_auto={},
        inputs=(),
    )

    assert bundle_ref is not None
    assert load_causal_graph_model(ir_store, graph_ref) == graph
    bundle_inputs = store.get_manifest(bundle_ref).inputs
    refined_edge = next(
        edge for edge in bundle_inputs if edge.role == "causal_validity_refined_pag_graph"
    )
    refined_ref = CausalGraphModelRef.model_validate(
        {
            "artifact_id": str(refined_edge.artifact_id),
            "kind": "ir.causal_graph_model",
            "media_type": "application/json",
            "manifest_profile_sha256": refined_edge.manifest_profile_sha256,
        }
    )
    refined_inputs = store.get_manifest(refined_ref).inputs
    source_edge = next(
        edge for edge in refined_inputs if edge.role == "causal_validity_input_graph"
    )
    assert str(source_edge.artifact_id) == str(graph_ref.artifact_id)
    assert str(source_edge.artifact_id) == str(current_default_graph_ref.artifact_id)
    assert source_edge.manifest_profile_sha256 is not None
    assert source_edge.manifest_profile_sha256 == graph_ref.manifest_profile_sha256
    assert source_edge.manifest_profile_sha256 != current_default_graph_ref.manifest_profile_sha256
    assert load_causal_graph_model(ir_store, refined_ref).graph_type is GraphType.PAG


def test_spatial_interference_check_prefers_typed_fields_over_metadata() -> None:
    diagnostics = SpatialHodgeDiagnostics(
        declared_scale_id="district",
        declared_zoning_id="admin_v1",
        aggregation_rule="mean",
        weight_spec="queen",
        exposure_mapping="kernel",
        zoning_hash="abc123",
        weight_hash="def456",
        aggregation_hash="ghi789",
        eta_grad=0.6,
        eta_curl=0.2,
        eta_harm=0.2,
        dominant_component="grad",
        profiles=(
            SpatialHodgeScaleProfile(
                scale_id="district",
                zoning_id="admin_v1",
                aggregation_rule="mean",
                weight_spec="queen",
                zoning_hash="abc123",
                weight_hash="def456",
                aggregation_hash="ghi789",
                n_zones=8,
                n_edges=12,
                total_energy=10.0,
                gradient_energy=6.0,
                curl_energy=2.0,
                harmonic_energy=2.0,
                eta_grad=0.6,
                eta_curl=0.2,
                eta_harm=0.2,
                dominant_component="grad",
            ),
        ),
    )
    maup = MAUPInvarianceCertificate(
        status="warn",
        estimand="spillover",
        effect_scale="mean_difference",
        micro_effect=0.42,
        partitions_tested=1,
        recommended_mode="micro_plus_safe_aggregate",
        near_invariance=True,
        partition_checks=(
            MAUPPartitionCheck(
                partition_id="district_v2",
                n_blocks=8,
                lumpability_residual=0.03,
                adjusted_p_value=0.61,
                ess_min=30.0,
            ),
        ),
    )
    report = SimpleNamespace(
        metadata={
            "spatial_hodge_summary": {"declared_scale_id": "metadata_only"},
            "spatial_hodge_diagnostics": {"declared_scale_id": "metadata_only"},
            "maup_invariance_certificate": {"status": "block"},
        },
        spatial_hodge_diagnostics=diagnostics,
        maup_invariance_certificate=maup,
    )
    observational_data = SimpleNamespace(
        metadata={"spatial_interference": {"scale_id": "fallback_scale"}}
    )

    check = _build_spatial_interference_check(
        report=report,
        method_fqn="causal.interference.spatial_kernel@1.0.0",
        method_params={},
        observational_data=observational_data,
    )

    assert check["status"] == "success"
    assert check["declared_scale_id"] == "district"
    assert check["blocker_codes"] == []


def test_local_cas_root_recognizes_guarded_runtime_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    guarded = guard_runtime_cas(store)

    assert validity_module._local_cas_root(SimpleNamespace(store=guarded)) == tmp_path
    assert (
        validity_module._local_cas_root(SimpleNamespace(store=SimpleNamespace(root=tmp_path)))
        is None
    )
