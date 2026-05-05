"""Tests for adversarial scenario generation."""

from __future__ import annotations

import math

import numpy as np
from polisyos.scientist.backtesting.adversarial import AdversarialGenerator


def _sample_data() -> dict[str, list[float]]:
    return {"metric_a": [1.0, 2.0, 3.0, 4.0, 5.0] * 4}


class TestAdversarialGenerator:
    def test_shift(self):
        gen = AdversarialGenerator(seed=42)
        scenario = gen.generate_shift(_sample_data(), shift_fraction=0.2)
        assert scenario.perturbation_type == "level_shift"
        orig = np.array(scenario.original_metrics["metric_a"])
        pert = np.array(scenario.perturbed_metrics["metric_a"])
        assert np.all(pert > orig)

    def test_noise(self):
        gen = AdversarialGenerator(seed=42)
        scenario = gen.generate_noise(_sample_data(), noise_scale=0.5)
        assert scenario.perturbation_type == "gaussian_noise"
        orig = np.array(scenario.original_metrics["metric_a"])
        pert = np.array(scenario.perturbed_metrics["metric_a"])
        assert not np.allclose(orig, pert)

    def test_outliers(self):
        gen = AdversarialGenerator(seed=42)
        data = _sample_data()
        scenario = gen.generate_outliers(data, outlier_fraction=0.2, outlier_magnitude=10.0)
        assert scenario.perturbation_type == "outlier_injection"
        orig = np.array(data["metric_a"])
        pert = np.array(scenario.perturbed_metrics["metric_a"])
        n_changed = np.sum(np.abs(pert - orig) > 0.01)
        assert n_changed > 0

    def test_missing(self):
        gen = AdversarialGenerator(seed=42)
        scenario = gen.generate_missing(_sample_data(), missing_fraction=0.3)
        assert scenario.perturbation_type == "missing_data"
        pert = scenario.perturbed_metrics["metric_a"]
        n_nan = sum(1 for v in pert if math.isnan(v))
        assert n_nan > 0

    def test_reproducibility(self):
        s1 = AdversarialGenerator(seed=42).generate_noise(_sample_data())
        s2 = AdversarialGenerator(seed=42).generate_noise(_sample_data())
        assert s1.perturbed_metrics == s2.perturbed_metrics
