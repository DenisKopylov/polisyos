from __future__ import annotations

import numpy.testing as npt
import pytest

from polisyos.foundry.uncertainty.covariance import (
    CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
    CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
    build_covariance_matrix,
    calibration_covariance_blocks_agree_v1,
    extract_std,
    preserve_singular_covariance,
)
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

    def test_build_covariance_preserves_declared_singular_tied_block(self) -> None:
        names = ["A.rate", "B.rate"]
        envelopes = {
            "A.rate": _normal_env(
                0.25,
                0.05,
                covariance_row=[0.0025, 0.0025],
                covariance_params=names,
            ),
            "B.rate": _normal_env(
                0.25,
                0.05,
                covariance_row=[0.0025, 0.0025],
                covariance_params=names,
            ),
        }

        covariance = build_covariance_matrix(
            names,
            envelopes,
            use_full_covariance=True,
            jitter=1e-6,
            preserve_singular=True,
        )

        npt.assert_allclose(
            covariance,
            [[0.0025, 0.0025], [0.0025, 0.0025]],
            rtol=1e-6,
            atol=1e-9,
        )


def test_singular_preservation_rejects_indefinite_matrix_even_with_large_jitter() -> None:
    names = ["x", "y"]
    envelopes = {
        "x": _normal_env(
            0.0,
            1.0,
            covariance_row=[1.0, 1.1],
            covariance_params=names,
        ),
        "y": _normal_env(
            0.0,
            1.0,
            covariance_row=[1.1, 1.0],
            covariance_params=names,
        ),
    }

    with pytest.raises(ValueError, match="positive semidefinite"):
        build_covariance_matrix(
            names,
            envelopes,
            use_full_covariance=True,
            jitter=100.0,
            preserve_singular=True,
        )


def test_calibration_covariance_reconciliation_uses_versioned_float64_tolerance() -> None:
    assert CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1 == 1e-7
    assert CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1 == 1e-10
    expected = [[0.0025, 0.0025], [0.0025, 0.0025]]
    within_tolerance = [[0.0025, 0.0025 + 2e-10], [0.0025, 0.0025]]
    outside_tolerance = [[0.0025, 0.0025 + 1e-8], [0.0025, 0.0025]]

    assert calibration_covariance_blocks_agree_v1(expected, within_tolerance)
    assert not calibration_covariance_blocks_agree_v1(expected, outside_tolerance)


def test_preserve_singular_covariance_retains_tied_nullspace() -> None:
    covariance = preserve_singular_covariance([[0.0025, 0.0025], [0.0025, 0.0025]])

    npt.assert_array_equal(covariance[0], covariance[1])
    npt.assert_allclose(covariance @ [1.0, -1.0], [0.0, 0.0], atol=1e-15, rtol=0)


def test_preserve_singular_covariance_rejects_indefinite_matrix() -> None:
    with pytest.raises(ValueError, match="positive semidefinite"):
        preserve_singular_covariance([[1.0, 1.1], [1.1, 1.0]])
