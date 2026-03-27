"""Spatial domain accuracy benchmarks.

Spatial methods require SpatialData Pydantic model.
Structural placeholders for Phase 10b.
"""
from __future__ import annotations

import pytest


@pytest.mark.benchmark
class TestSpatialAccuracy:

    def test_moran_i_placeholder(self):
        """Placeholder: Moran I requires SpatialData."""
        pytest.skip("Requires SpatialData model — deferred to Phase 10b")

    def test_gravity_model_placeholder(self):
        """Placeholder: Gravity model requires FlowData."""
        pytest.skip("Requires FlowData model — deferred to Phase 10b")

    def test_idw_interpolation_placeholder(self):
        """Placeholder: IDW requires SpatialData with query points."""
        pytest.skip("Requires SpatialData model — deferred to Phase 10b")

    def test_gwr_placeholder(self):
        """Placeholder: GWR requires SpatialData with features."""
        pytest.skip("Requires SpatialData model — deferred to Phase 10b")

    def test_two_step_fca_placeholder(self):
        """Placeholder: 2SFCA requires AccessibilityData."""
        pytest.skip("Requires AccessibilityData model — deferred to Phase 10b")
