"""Metrics for bounded explanation reliability."""

from __future__ import annotations

from polisyos.berl.metrics.analytical import (
    AnalyticalBoundResult,
    linear_exact_infidelity_bound,
    taylor_curvature_infidelity_bound,
)
from polisyos.berl.metrics.disagreement import (
    AttributionVector,
    MethodDisagreementSummary,
    compare_attribution_vectors,
)
from polisyos.berl.metrics.empirical_bounds import (
    BoundType,
    EmpiricalBoundResult,
    adjust_confidence_for_union,
    empirical_bernstein_upper_bound,
    hoeffding_upper_bound,
)
from polisyos.berl.metrics.infidelity import (
    PerturbationRecord,
    additive_reconstruct_delta,
    estimate_local_infidelity,
    reconstruction_residuals,
)
from polisyos.berl.metrics.redundancy import (
    FeatureInterval,
    RedundancyCluster,
    ambiguity_intervals,
    detect_redundancy_clusters,
    group_attributions,
    is_allocation_identifiable,
)

__all__ = [
    "AnalyticalBoundResult",
    "AttributionVector",
    "BoundType",
    "EmpiricalBoundResult",
    "FeatureInterval",
    "MethodDisagreementSummary",
    "PerturbationRecord",
    "RedundancyCluster",
    "additive_reconstruct_delta",
    "adjust_confidence_for_union",
    "ambiguity_intervals",
    "compare_attribution_vectors",
    "detect_redundancy_clusters",
    "empirical_bernstein_upper_bound",
    "estimate_local_infidelity",
    "group_attributions",
    "hoeffding_upper_bound",
    "is_allocation_identifiable",
    "linear_exact_infidelity_bound",
    "reconstruction_residuals",
    "taylor_curvature_infidelity_bound",
]
