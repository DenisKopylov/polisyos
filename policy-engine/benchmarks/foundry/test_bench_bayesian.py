"""Bayesian domain accuracy benchmarks.

Bayesian methods require TabularData Pydantic model.
These are structural placeholders for Phase 10b.
"""
from __future__ import annotations

import pytest


@pytest.mark.benchmark
class TestBayesianAccuracy:

    def test_bayesian_linreg_placeholder(self):
        """Placeholder: BayesLinReg requires TabularData."""
        pytest.skip("Requires TabularData model — deferred to Phase 10b")

    def test_gaussian_process_placeholder(self):
        """Placeholder: GP requires TabularData."""
        pytest.skip("Requires TabularData model — deferred to Phase 10b")

    def test_variational_inference_placeholder(self):
        """Placeholder: MFVI requires model spec."""
        pytest.skip("Requires model specification — deferred to Phase 10b")
