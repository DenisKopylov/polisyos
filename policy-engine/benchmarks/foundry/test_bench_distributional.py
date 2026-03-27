"""Distributional domain accuracy benchmarks."""
from __future__ import annotations

import numpy as np
import pytest

from benchmarks.foundry.conftest import make_distribution, make_two_class_distribution


@pytest.mark.benchmark
class TestDistributionalAccuracy:

    def test_gini_uniform(self, bench_registry):
        """Uniform-ish dist → Gini ≈ 1/3 for linspace."""
        values = np.linspace(1.0, 100.0, 50)
        cls = bench_registry.get("distributional.inequality.lorenz_curve@1.0.0")
        result = cls.pure_step({"values": values}, {})
        gini = result["result"]["gini"]
        # Discrete Gini for linspace(1,100,50) ≈ 0.333
        assert 0.30 < gini < 0.36, f"Gini={gini} outside expected range"

    def test_atkinson_monotone_in_epsilon(self, bench_registry):
        """Atkinson index increases with epsilon for unequal dist."""
        values = {"values": np.array([10.0, 20.0, 30.0, 100.0, 200.0])}
        cls = bench_registry.get("distributional.inequality.atkinson@1.0.0")
        a_low = cls.pure_step(values, {"epsilon": 0.25})["result"]["atkinson_index"]
        a_high = cls.pure_step(values, {"epsilon": 1.5})["result"]["atkinson_index"]
        assert a_high > a_low, "Higher epsilon should yield higher Atkinson"

    def test_fgt_severity_ordering(self, bench_registry):
        """FGT(0) ≤ FGT(1) in normalized terms for alpha=0 vs alpha=2."""
        data = {"values": np.array([10.0, 20.0, 30.0, 60.0, 80.0]), "poverty_line": 50.0}
        cls = bench_registry.get("distributional.poverty.fgt@1.0.0")
        p0 = cls.pure_step(data, {"alpha": 0.0})["result"]["fgt"]
        p2 = cls.pure_step(data, {"alpha": 2.0})["result"]["fgt"]
        assert p0 >= p2, "P0 ≥ P2 for FGT measures"

    def test_theil_nonnegative(self, bench_registry):
        """Theil index should be non-negative."""
        data = make_distribution(n_obs=50, seed=99)
        cls = bench_registry.get("distributional.inequality.theil@1.0.0")
        result = cls.pure_step(data, {})
        assert result["result"]["theil_index"] >= 0.0

    def test_palma_ratio_boundary(self, bench_registry):
        """Equal distribution → Palma = top10share / bottom40share = 0.25."""
        data = {"values": np.full(20, 100.0)}
        cls = bench_registry.get("distributional.inequality.palma_ratio@1.0.0")
        result = cls.pure_step(data, {})
        np.testing.assert_allclose(result["result"]["palma_ratio"], 0.25, atol=0.02)
