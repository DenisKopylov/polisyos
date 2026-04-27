"""Benchmark helpers for BERL stress tests."""

from __future__ import annotations

from polisyos.berl.benchmarks.correlation_sweep import (
    CorrelationSweepCase,
    build_correlation_sweep,
)
from polisyos.berl.benchmarks.interaction_tests import (
    interaction_suite,
    out_of_support_masking_rows,
    threshold_tree_rows,
)
from polisyos.berl.benchmarks.policy_tabular_suite import (
    eligibility_rows,
    eligibility_score_model,
)
from polisyos.berl.benchmarks.synthetic_redundancy import (
    duplicate_feature_rows,
    high_correlation_rows,
    proxy_feature_rows,
    xor_rows,
)

__all__ = [
    "CorrelationSweepCase",
    "build_correlation_sweep",
    "duplicate_feature_rows",
    "eligibility_rows",
    "eligibility_score_model",
    "high_correlation_rows",
    "interaction_suite",
    "out_of_support_masking_rows",
    "proxy_feature_rows",
    "threshold_tree_rows",
    "xor_rows",
]
