from __future__ import annotations

from types import SimpleNamespace

from polisyos.ir.analytics.interference import (
    MAUPInvarianceCertificate,
    MAUPPartitionCheck,
    SpatialHodgeDiagnostics,
    SpatialHodgeScaleProfile,
)
from polisyos.scientist.causal.validity import _build_spatial_interference_check


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
