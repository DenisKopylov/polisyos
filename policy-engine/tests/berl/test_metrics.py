from __future__ import annotations

import pytest

from polisyos.berl.metrics.analytical import (
    linear_exact_infidelity_bound,
    taylor_curvature_infidelity_bound,
)
from polisyos.berl.metrics.disagreement import AttributionVector, compare_attribution_vectors
from polisyos.berl.metrics.empirical_bounds import (
    adjust_confidence_for_union,
    empirical_bernstein_upper_bound,
    hoeffding_upper_bound,
)
from polisyos.berl.metrics.infidelity import (
    PerturbationRecord,
    additive_reconstruct_delta,
    estimate_local_infidelity,
)
from polisyos.berl.metrics.redundancy import (
    ambiguity_intervals,
    detect_redundancy_clusters,
    group_attributions,
    is_allocation_identifiable,
)


def test_bounds_return_zero_point_estimate_for_exact_reconstruction() -> None:
    result = empirical_bernstein_upper_bound([0.0, 0.0, 0.0], confidence=0.95, residual_cap=1.0)

    assert result.point_estimate == 0.0
    assert result.upper_bound > 0.0
    assert result.bound_type == "empirical_bernstein"
    assert result.n == 3


def test_hoeffding_rejects_losses_above_declared_cap() -> None:
    with pytest.raises(ValueError, match="loss exceeds"):
        hoeffding_upper_bound([0.2, 1.2], confidence=0.95, residual_cap=1.0)


def test_union_bound_confidence_adjustment() -> None:
    assert adjust_confidence_for_union(global_confidence=0.95, claim_count=5) == pytest.approx(0.99)


def test_local_infidelity_uses_heldout_residuals_and_weights() -> None:
    records = [
        PerturbationRecord(actual_delta=1.0, reconstructed_delta=0.9, weight=1.0),
        PerturbationRecord(actual_delta=0.5, reconstructed_delta=0.4, weight=0.5),
    ]

    result = estimate_local_infidelity(records, confidence=0.9, residual_cap=1.0)

    assert result.point_estimate == pytest.approx(0.0075)
    assert result.upper_bound >= result.point_estimate


def test_additive_reconstruction_uses_declared_feature_representation() -> None:
    reconstructed = additive_reconstruct_delta(
        {"income": 0.4, "assets": -0.1},
        {"income": 0.5, "assets": 2.0, "ignored": 100.0},
    )

    assert reconstructed == pytest.approx(0.0)


def test_disagreement_surfaces_rank_and_sign_conflicts() -> None:
    summary = compare_attribution_vectors(
        [
            AttributionVector("kernel_shap", {"income": 0.7, "assets": 0.2, "age": 0.1}),
            AttributionVector("lime", {"income": -0.5, "assets": 0.4, "age": 0.1}),
            AttributionVector("ale_local_bin", {"assets": 0.8, "income": 0.1, "age": 0.1}),
        ],
        top_k=1,
        agreement_floor=0.75,
    )

    assert "income" in summary.sign_conflict_features
    assert "methods_disagree_on_rank_order" in summary.flags
    assert summary.top_k_jaccard_median < 1.0


def test_redundancy_clusters_group_duplicate_features_and_intervals() -> None:
    rows = [{"income": 1.0, "assets": 1.0}, {"income": 2.0, "assets": 2.0}]
    clusters = detect_redundancy_clusters(rows, corr_threshold=0.99)

    assert len(clusters) == 1
    assert clusters[0].features == ("assets", "income")
    assert group_attributions({"income": 0.25, "assets": 0.5}, clusters) == {
        "assets_income": 0.75
    }

    intervals = ambiguity_intervals(
        [{"income": 0.1, "assets": 0.3}, {"income": 0.25, "assets": 0.15}],
        clusters[0],
    )

    assert not is_allocation_identifiable(intervals)


def test_analytical_bounds_cover_linear_and_smooth_cases() -> None:
    assert linear_exact_infidelity_bound().upper_bound == 0.0
    assert taylor_curvature_infidelity_bound(
        hessian_operator_bound=2.0,
        fourth_moment_radius=0.25,
    ).upper_bound == pytest.approx(0.25)
