from __future__ import annotations

from polisyos.berl.benchmarks.correlation_sweep import build_correlation_sweep
from polisyos.berl.benchmarks.interaction_tests import interaction_suite
from polisyos.berl.benchmarks.policy_tabular_suite import eligibility_rows
from polisyos.berl.benchmarks.synthetic_redundancy import proxy_feature_rows


def test_correlation_sweep_contains_three_regimes() -> None:
    sweep = build_correlation_sweep()

    assert [case.rho for case in sweep] == [0.0, 0.5, 0.95]
    assert sweep[-1].redundancy_detected


def test_benchmark_suite_covers_proxy_interaction_and_policy_data() -> None:
    assert proxy_feature_rows()
    suite = interaction_suite()
    assert {"xor_interaction", "threshold_tree", "out_of_support_masking"} <= set(suite)
    assert eligibility_rows()
