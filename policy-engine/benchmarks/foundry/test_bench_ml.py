"""ML domain accuracy benchmarks.

ML methods require TabularData Pydantic model.
Structural placeholders for Phase 10b.
"""

from __future__ import annotations

import pytest


@pytest.mark.benchmark
class TestMLAccuracy:
    def test_elastic_net_placeholder(self):
        """Placeholder: ElasticNet requires TabularData."""
        pytest.skip("Requires TabularData model — deferred to Phase 10b")

    def test_random_forest_placeholder(self):
        """Placeholder: RF requires TabularData."""
        pytest.skip("Requires TabularData model — deferred to Phase 10b")

    def test_kmeans_placeholder(self):
        """Placeholder: KMeans requires TabularData."""
        pytest.skip("Requires TabularData model — deferred to Phase 10b")

    def test_pca_placeholder(self):
        """Placeholder: PCA requires TabularData."""
        pytest.skip("Requires TabularData model — deferred to Phase 10b")

    def test_gradient_boosting_placeholder(self):
        """Placeholder: GBM requires TabularData."""
        pytest.skip("Requires TabularData model — deferred to Phase 10b")
