from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.interference import (
    InteractionComplex,
    InterferenceCertificate,
    MAUPInvarianceCertificate,
    MAUPPartitionCheck,
    SpatialHodgeDiagnostics,
    SpatialHodgeScaleProfile,
    SpatialResult,
    load_interaction_complex,
    load_interference_certificate,
    load_maup_invariance_certificate,
    load_spatial_hodge_diagnostics,
    persist_interaction_complex,
    persist_interference_certificate,
    persist_maup_invariance_certificate,
    persist_spatial_hodge_diagnostics,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    InteractionComplexRef,
    InterferenceCertificateRef,
    MAUPInvarianceCertificateRef,
    SpatialHodgeDiagnosticsRef,
)
from pydantic import ValidationError


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _interaction_complex(
    *,
    reduction_policy: str = "cluster_projection",
) -> InteractionComplex:
    return InteractionComplex(
        nodes=("A__0", "Y__0", "A__1", "Y__1"),
        hyperedges=(("A__0", "Y__0"), ("A__1", "Y__1")),
        simplices=(),
        exposure_operator_ref=_artifact_ref("a", kind="ir.interference_exposure_operator"),
        reduction_policy=reduction_policy,
    )


def test_interaction_complex_rejects_duplicate_or_undeclared_nodes() -> None:
    with pytest.raises(ValidationError, match="nodes must be unique"):
        InteractionComplex(
            nodes=("A__0", "A__0"),
            hyperedges=(),
            simplices=(),
            exposure_operator_ref=_artifact_ref("a", kind="ir.interference_exposure_operator"),
            reduction_policy="pairwise_projection",
        )

    with pytest.raises(ValidationError, match="references undeclared nodes"):
        InteractionComplex(
            nodes=("A__0", "Y__0"),
            hyperedges=(("A__0", "Y__1"),),
            simplices=(),
            exposure_operator_ref=_artifact_ref("a", kind="ir.interference_exposure_operator"),
            reduction_policy="cluster_projection",
        )


def test_interference_certificate_rejects_blank_assumptions_and_nonfinite_bound() -> None:
    with pytest.raises(ValidationError, match="exposure_assumptions must be a list/tuple"):
        InterferenceCertificate(
            supported_query_family="pairwise_projection_queries",
            exposure_assumptions="not-a-sequence",
            reduction_error_bound=None,
            fallback_mode="pairwise",
        )

    with pytest.raises(ValidationError, match="reduction_error_bound must be finite"):
        InterferenceCertificate(
            supported_query_family="cluster_projection_queries",
            exposure_assumptions=("cluster_partition_used_as_topology_proxy",),
            reduction_error_bound=float("inf"),
            fallback_mode="clustered",
        )

    with pytest.raises(ValidationError, match="fallback_reason_codes must be non-empty"):
        InterferenceCertificate(
            supported_query_family="pairwise_projection_queries",
            reduction_error_bound=None,
            fallback_mode="pairwise",
            mode_requested="complex",
            mode_used="pairwise",
            fallback_triggered=True,
            fallback_reason_codes=(),
        )

    with pytest.raises(ValidationError, match="mode_requested must equal mode_used"):
        InterferenceCertificate(
            supported_query_family="simplicial_star_local_queries",
            reduction_error_bound=None,
            fallback_mode="unsupported",
            mode_requested="complex",
            mode_used="pairwise",
            fallback_triggered=False,
            fallback_reason_codes=(),
        )

    with pytest.raises(
        ValidationError, match="fallback_mode must be unsupported when mode_used is complex"
    ):
        InterferenceCertificate(
            supported_query_family="simplicial_star_local_queries",
            reduction_error_bound=None,
            fallback_mode="pairwise",
            mode_requested="complex",
            mode_used="complex",
            fallback_triggered=False,
            fallback_reason_codes=(),
            estimability_checks={
                "topology_evidence": "pass",
                "simplicial_closure": "pass",
                "exposure_positivity": "pass",
                "higher_order_separability": "pass",
                "inference_regime": "pass",
                "pre_outcome_selection": "pass",
            },
        )


def test_phase_f_contracts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    interaction_complex = _interaction_complex()
    certificate = InterferenceCertificate(
        supported_query_family="cluster_projection_queries",
        exposure_assumptions=(
            "exposure_mapping:fractional",
            "support_limited_to_pairwise_or_cluster_reduction",
        ),
        reduction_error_bound=None,
        fallback_mode="clustered",
        mode_requested="complex",
        mode_used="clustered",
        fallback_triggered=True,
        fallback_reason_codes=("higher_order_separability_failed",),
        estimability_checks={
            "topology_evidence": "pass",
            "simplicial_closure": "pass",
            "exposure_positivity": "pass",
            "higher_order_separability": "fail",
            "inference_regime": "pass",
            "pre_outcome_selection": "pass",
        },
    )

    interaction_complex_ref = persist_interaction_complex(store, interaction_complex)
    certificate_ref = persist_interference_certificate(store, certificate)

    assert isinstance(interaction_complex_ref, InteractionComplexRef)
    assert isinstance(certificate_ref, InterferenceCertificateRef)
    assert load_interaction_complex(store, interaction_complex_ref) == interaction_complex
    assert load_interference_certificate(store, certificate_ref) == certificate


def test_reduction_error_bound_none_is_honest_default() -> None:
    certificate = InterferenceCertificate(
        supported_query_family="pairwise_projection_queries",
        exposure_assumptions=("hypergraph_identification_not_claimed",),
        reduction_error_bound=None,
        fallback_mode="pairwise",
        mode_requested="complex",
        mode_used="pairwise",
        fallback_triggered=True,
        fallback_reason_codes=("higher_order_separability_failed",),
    )

    assert certificate.reduction_error_bound is None
    assert certificate.fallback_mode == "pairwise"
    assert certificate.mode_used == "pairwise"


def test_maup_certificate_rejects_partition_count_mismatch() -> None:
    with pytest.raises(ValidationError, match="partitions_tested must equal len"):
        MAUPInvarianceCertificate(
            status="warn",
            estimand="spillover",
            effect_scale="mean_difference",
            partitions_tested=0,
            recommended_mode="micro_only",
            partition_checks=(
                MAUPPartitionCheck(
                    partition_id="admin_v1",
                    n_blocks=4,
                    lumpability_residual=0.01,
                ),
            ),
        )


def test_maup_certificate_round_trip_and_spatial_result_wrap(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    certificate = MAUPInvarianceCertificate(
        status="warn",
        estimand="spillover",
        effect_scale="mean_difference",
        micro_effect=0.42,
        micro_se=0.08,
        partitions_tested=2,
        max_lumpability_residual=0.013,
        min_adjusted_p_value=0.18,
        min_positivity=0.22,
        min_ess=24.0,
        near_invariance=True,
        recommended_mode="micro_only",
        partition_checks=(
            MAUPPartitionCheck(
                partition_id="admin_v1",
                n_blocks=4,
                lumpability_residual=0.013,
                exact_lumpable=False,
                theta_partition=0.40,
                se_partition=0.09,
                hausman_stat=0.12,
                p_value=0.72,
                adjusted_p_value=0.72,
                ess_min=24.0,
                warnings=("ess_warn",),
            ),
            MAUPPartitionCheck(
                partition_id="hex_2km",
                n_blocks=6,
                lumpability_residual=0.007,
                exact_lumpable=False,
                theta_partition=0.44,
                se_partition=0.07,
                hausman_stat=0.05,
                p_value=0.81,
                adjusted_p_value=0.81,
                ess_min=31.0,
            ),
        ),
        warnings=("maup_probe_covariates_truncated",),
    )

    certificate_ref = persist_maup_invariance_certificate(store, certificate)
    assert isinstance(certificate_ref, MAUPInvarianceCertificateRef)
    assert load_maup_invariance_certificate(store, certificate_ref) == certificate

    report = SpatialResult(
        method="spatial_kernel",
        status="success",
        effects={
            "direct_effect": 1.0,
            "spillover_effect": 0.5,
            "total_effect": 1.5,
            "alpha_high": 0.5,
            "alpha_low": 0.0,
            "n_units": 20,
            "n_treated": 10,
            "confidence_level": 0.95,
            "interference_detected": True,
        },
        exposure_mapping="kernel",
        n_units=20,
        n_treated=10,
        maup_invariance_certificate=certificate,
    )
    assert report.maup_invariance_certificate is not None
    assert report.maup_invariance_certificate.status == "warn"


def test_spatial_hodge_diagnostics_round_trip_and_attach_to_spatial_result(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    diagnostics = SpatialHodgeDiagnostics(
        declared_scale_id="district",
        declared_zoning_id="admin_v1",
        aggregation_rule="mean",
        weight_spec="queen",
        exposure_mapping="kernel",
        zoning_hash="abc123",
        weight_hash="def456",
        aggregation_hash="ghi789",
        eta_grad=0.62,
        eta_curl=0.18,
        eta_harm=0.20,
        dominant_component="grad",
        max_profile_l1_gap=0.31,
        scale_instability=0.31,
        zoning_instability=0.12,
        topology_sensitivity=0.09,
        candidate_partition_ids=("admin_v2", "hex_2km"),
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
                n_triangles=3,
                total_energy=10.0,
                gradient_energy=6.2,
                curl_energy=1.8,
                harmonic_energy=2.0,
                eta_grad=0.62,
                eta_curl=0.18,
                eta_harm=0.20,
                dominant_component="grad",
            ),
            SpatialHodgeScaleProfile(
                scale_id="region",
                zoning_id="hex_2km",
                aggregation_rule="mean",
                weight_spec="queen:aggregate:hex_2km",
                zoning_hash="abc999",
                weight_hash="def999",
                aggregation_hash="ghi789",
                n_zones=4,
                n_edges=5,
                n_triangles=1,
                total_energy=3.0,
                gradient_energy=1.1,
                curl_energy=0.9,
                harmonic_energy=1.0,
                eta_grad=0.3666666667,
                eta_curl=0.3,
                eta_harm=0.3333333333,
                dominant_component="mixed",
                warnings=("hodge_triangle_limit_applied",),
            ),
        ),
        warnings=("topology_probe_unstable",),
    )

    diagnostics_ref = persist_spatial_hodge_diagnostics(store, diagnostics)
    assert isinstance(diagnostics_ref, SpatialHodgeDiagnosticsRef)
    assert load_spatial_hodge_diagnostics(store, diagnostics_ref) == diagnostics

    report = SpatialResult(
        method="spatial_kernel",
        status="success",
        effects={
            "direct_effect": 1.0,
            "spillover_effect": 0.5,
            "total_effect": 1.5,
            "alpha_high": 0.5,
            "alpha_low": 0.0,
            "n_units": 20,
            "n_treated": 10,
            "confidence_level": 0.95,
            "interference_detected": True,
        },
        exposure_mapping="kernel",
        n_units=20,
        n_treated=10,
        spatial_hodge_diagnostics=diagnostics,
    )
    assert report.spatial_hodge_diagnostics is not None
    assert report.spatial_hodge_diagnostics.dominant_component == "grad"
