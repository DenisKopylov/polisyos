from __future__ import annotations

import logging
from types import SimpleNamespace

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.interference import (
    MAUPInvarianceCertificate,
    MAUPPartitionCheck,
    SpatialHodgeDiagnostics,
    SpatialHodgeScaleProfile,
)
from polisyos.scientist.methods.causal import validity as validity_module
from polisyos.scientist.methods.causal.validity import (
    _build_spatial_interference_check,
    persist_causal_validity_bundle,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


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
