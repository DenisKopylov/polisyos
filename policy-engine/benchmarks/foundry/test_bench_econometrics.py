"""Econometrics domain accuracy benchmarks.

Many econometrics methods require Pydantic models (PanelData, etc.)
so these benchmarks test the methods that accept structured model input.
"""
from __future__ import annotations

import pytest

# Econometrics methods require PanelData/CountData models.
# These benchmarks are structural placeholders for Phase 10b integration.


@pytest.mark.benchmark
class TestEconometricsAccuracy:

    def test_quantile_regression_placeholder(self):
        """Placeholder: quantile regression requires QuantileRegressionData."""
        pytest.skip("Requires Pydantic model input — deferred to Phase 10b")

    def test_poisson_count_placeholder(self):
        """Placeholder: Poisson regression requires CountData model."""
        pytest.skip("Requires Pydantic model input — deferred to Phase 10b")

    def test_fixed_effects_placeholder(self):
        """Placeholder: FE requires PanelData model."""
        pytest.skip("Requires PanelData model input — deferred to Phase 10b")

    def test_garch_placeholder(self):
        """Placeholder: GARCH requires TimeSeriesData model."""
        pytest.skip("Requires Pydantic model input — deferred to Phase 10b")

    def test_hausman_test_placeholder(self):
        """Placeholder: Hausman test requires two PanelData estimates."""
        pytest.skip("Requires PanelData model input — deferred to Phase 10b")
