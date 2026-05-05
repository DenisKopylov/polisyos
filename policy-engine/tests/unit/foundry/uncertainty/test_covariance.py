from __future__ import annotations

import numpy.testing as npt
from polisyos.foundry.uncertainty.covariance import build_covariance_matrix, extract_std
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal_env(
    point: float,
    std: float,
    level: float = 0.95,
    **metadata: object,
) -> UncertaintyEnvelope:
    from statistics import NormalDist

    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z * std, point + z * std),
        confidence_level=level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata=dict(metadata) if metadata else {},
    )


class TestExtractStd:
    def test_extract_std_normal_known_level(self) -> None:
        env = _normal_env(10.0, 2.0, level=0.95)
        recovered_std = extract_std(env)
        npt.assert_allclose(recovered_std, 2.0, atol=0.05)

    def test_extract_std_uniform_fallback(self) -> None:
        env = UncertaintyEnvelope(
            point_estimate=5.0,
            confidence_interval=(2.0, 8.0),
            confidence_level=None,
            distribution_family=DistributionFamily.UNIFORM,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            gate_eligible=True,
        )
        std = extract_std(env)
        assert std > 0


class TestBuildCovarianceMatrix:
    def test_build_covariance_diagonal(self) -> None:
        envelopes = {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 1.0)}
        cov = build_covariance_matrix(
            ["x", "z"],
            envelopes,
            use_full_covariance=False,
            jitter=0.0,
        )
        assert cov.shape == (2, 2)
        npt.assert_allclose(float(cov[0, 1]), 0.0, atol=1e-6)
        npt.assert_allclose(float(cov[1, 0]), 0.0, atol=1e-6)
        assert float(cov[0, 0]) > 0
        assert float(cov[1, 1]) > 0

    def test_build_covariance_full_with_metadata(self) -> None:
        cov_row_x = [0.25, 0.1]
        cov_row_z = [0.1, 1.0]
        params_order = ["x", "z"]
        envelopes = {
            "x": _normal_env(1.0, 0.5, covariance_row=cov_row_x, covariance_params=params_order),
            "z": _normal_env(2.0, 1.0, covariance_row=cov_row_z, covariance_params=params_order),
        }
        cov = build_covariance_matrix(
            ["x", "z"],
            envelopes,
            use_full_covariance=True,
            jitter=0.0,
        )
        npt.assert_allclose(float(cov[0, 1]), 0.1, atol=1e-6)

    def test_build_covariance_fallback_on_missing_metadata(self) -> None:
        envelopes = {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 1.0)}
        cov = build_covariance_matrix(
            ["x", "z"],
            envelopes,
            use_full_covariance=True,
            jitter=0.0,
        )
        npt.assert_allclose(float(cov[0, 1]), 0.0, atol=1e-6)
