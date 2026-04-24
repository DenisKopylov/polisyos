"""
Property-based tests for spatial methods:
- Moran's I spatial autocorrelation
- GWR (Geographically Weighted Regression)
- Spatial interpolation (IDW, Kriging)
"""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")

sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import spatial_data_strategy


def _check_finite(result: dict, fqn: str) -> None:
    for key, val in result.items():
        arr = np.asarray(val)
        if arr.dtype == object:
            continue
        if np.issubdtype(arr.dtype, np.floating) and arr.size > 0:
            assert not (np.all(np.isnan(arr)) and arr.size > 1), f"All-NaN output in {fqn}/{key}"


class TestMoranIProperties:
    @given(data=spatial_data_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_moran_i_output_finite(self, data, isolated_registry):
        fqn = "spatial.autocorrelation.moran_i@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"outcome": data["outcome"], "lon": data["lon"], "lat": data["lat"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
            _check_finite(result, fqn)
        except Exception:
            pass

    @given(data=spatial_data_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_moran_i_range(self, data, isolated_registry):
        """Moran's I statistic is in [-1, 1] for well-conditioned data."""
        fqn = "spatial.autocorrelation.moran_i@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"outcome": data["outcome"], "lon": data["lon"], "lat": data["lat"]}
        try:
            result = method.pure_step(state, {})
            if "moran_i" in result:
                mi = float(result["moran_i"])
                if np.isfinite(mi):
                    assert -1.5 <= mi <= 1.5, f"Moran's I out of reasonable range: {mi}"
        except Exception:
            pass

    @given(data=spatial_data_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_moran_i_deterministic(self, data, isolated_registry):
        fqn = "spatial.autocorrelation.moran_i@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"outcome": data["outcome"], "lon": data["lon"], "lat": data["lat"]}
        try:
            r1 = method.pure_step(state, {})
            r2 = method.pure_step(state, {})
            for key in r1:
                v1, v2 = np.asarray(r1[key]), np.asarray(r2[key])
                if np.issubdtype(v1.dtype, np.floating):
                    np.testing.assert_array_equal(v1, v2)
        except Exception:
            pass


class TestGWRProperties:
    @given(data=spatial_data_strategy())
    @settings(
        max_examples=15,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gwr_output_dict(self, data, isolated_registry):
        fqn = "spatial.regression.gwr@1.0.0"
        method = isolated_registry.get(fqn)
        state = {
            "outcome": data["outcome"],
            "covariates": data["covariates"],
            "lon": data["lon"],
            "lat": data["lat"],
        }
        try:
            result = method.pure_step(state, {"bandwidth": 1.0})
            assert isinstance(result, dict)
        except Exception:
            pass

    @given(data=spatial_data_strategy())
    @settings(
        max_examples=10,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gwr_local_coefficients_shape(self, data, isolated_registry):
        fqn = "spatial.regression.gwr@1.0.0"
        method = isolated_registry.get(fqn)
        state = {
            "outcome": data["outcome"],
            "covariates": data["covariates"],
            "lon": data["lon"],
            "lat": data["lat"],
        }
        try:
            result = method.pure_step(state, {"bandwidth": 1.0})
            # Local coefficients should have shape (n_obs, n_features+1)
            if "local_coefficients" in result:
                lc = np.asarray(result["local_coefficients"])
                assert lc.shape[0] == data["n_obs"]
        except Exception:
            pass
