"""Re-export Foundry analysis helpers used to interpret simulation outputs."""

from __future__ import annotations

from .attractors import (
    TerminalRegime,
    build_attractor_analysis_result,
    build_attractor_ensemble_analysis_result,
    build_feedback_attractor_analysis_result,
    classify_terminal_regime,
    finite_difference_map_jacobian,
    largest_lyapunov_exponent,
    load_attractor_analysis_result,
    load_basin_map,
    load_continuation_branch,
    persist_attractor_analysis_result,
    persist_basin_map,
    persist_continuation_branch,
)
from .distributional import (
    build_distributional_report,
    build_geography_breakdown,
    build_income_quintile_breakdown,
    build_winners_losers_table,
    compute_gini,
    compute_palma_ratio,
)

__all__ = [
    "TerminalRegime",
    "build_attractor_analysis_result",
    "build_attractor_ensemble_analysis_result",
    "build_distributional_report",
    "build_feedback_attractor_analysis_result",
    "build_geography_breakdown",
    "build_income_quintile_breakdown",
    "build_winners_losers_table",
    "classify_terminal_regime",
    "compute_gini",
    "compute_palma_ratio",
    "finite_difference_map_jacobian",
    "largest_lyapunov_exponent",
    "load_attractor_analysis_result",
    "load_basin_map",
    "load_continuation_branch",
    "persist_attractor_analysis_result",
    "persist_basin_map",
    "persist_continuation_branch",
]
