from __future__ import annotations

import numpy as np
import pytest

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_types import (
    _dot_interval,
    _extract_std,
    _matvec_interval,
    _mul_interval,
    _WelfareNodeFailure,
)


def _normal_envelope(std: float) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(8.0, 12.0),
        distribution_family=DistributionFamily.NORMAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"std": std},
        ),
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata={"param_name": "rate"},
    )


def test_signed_interval_arithmetic_contains_all_corner_products() -> None:
    assert _mul_interval(-2.0, 3.0, 4.0, 5.0) == (-10.0, 15.0)

    lower, upper = _matvec_interval(
        np.asarray([[1.0, -2.0]]),
        np.asarray([[3.0, -1.0]]),
        np.asarray([2.0, 4.0]),
        np.asarray([2.0, 4.0]),
    )
    np.testing.assert_allclose(lower, [-6.0])
    np.testing.assert_allclose(upper, [2.0])

    signed = _dot_interval(
        np.asarray([-2.0, 3.0]),
        np.asarray([1.0, 2.0]),
        np.asarray([4.0, 5.0]),
    )
    assert signed == (-2.0, 13.0)
    # Removing the negative-weight corner would produce an invalid lower bound.
    assert (
        signed[0]
        < _dot_interval(
            np.asarray([2.0, 3.0]),
            np.asarray([1.0, 2.0]),
            np.asarray([4.0, 5.0]),
        )[0]
    )


def test_uncertainty_scale_uses_typed_carrier_and_rejects_negative_scale() -> None:
    assert _extract_std(_normal_envelope(1.25)) == 1.25

    with pytest.raises(_WelfareNodeFailure) as failure:
        _extract_std(_normal_envelope(-0.25))

    assert failure.value.error.code == "ERROR_WELFARE_UNCERTAINTY_SCALE_INVALID"
    assert failure.value.error.details["param_name"] == "rate"
