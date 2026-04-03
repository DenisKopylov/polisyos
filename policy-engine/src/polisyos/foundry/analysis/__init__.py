"""Re-export Foundry analysis helpers used to interpret simulation outputs."""
from __future__ import annotations

from .distributional import (
    build_distributional_report,
    build_geography_breakdown,
    build_income_quintile_breakdown,
    build_winners_losers_table,
    compute_gini,
    compute_palma_ratio,
)

__all__ = [
    "build_distributional_report",
    "build_geography_breakdown",
    "build_income_quintile_breakdown",
    "build_winners_losers_table",
    "compute_gini",
    "compute_palma_ratio",
]
