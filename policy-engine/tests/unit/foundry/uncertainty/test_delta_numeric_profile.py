"""Native delta invocation and numeric-profile boundary controls."""

from __future__ import annotations

import jax
import pytest

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal(point: float) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - 19.6, point + 19.6),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=False,
    )


@pytest.mark.parametrize("method", ["auto", "delta"])
@pytest.mark.parametrize("requested", [100_000_000.0, 100_000_001.0])
def test_nominal_probe_and_delta_use_one_declared_float32_domain(
    method: str, requested: float
) -> None:
    """The callback sees the same representable coordinate at every nominal stage."""
    seen: list[tuple[float, float]] = []

    def evaluate(*, x: float, scale: float) -> dict[str, float]:
        if not isinstance(x, jax.core.Tracer):
            seen.append((float(x), scale))
        return {"y": (x - 100_000_000.0) * scale}

    result = PropagationDispatcher(
        PropagationConfig(preferred_method=method, delta_covariance_jitter=0.0)
    ).propagate(
        evaluate,
        {"x": requested, "scale": 2.0},
        {"x": _normal(requested)},
        ["y"],
    )[0]

    assert result.method_used is PropagationMethod.DELTA_METHOD
    assert result.envelope.point_estimate == 0.0
    assert seen and all(value == 100_000_000.0 and scale == 2.0 for value, scale in seen)
    profile = result.envelope.metadata["delta_numeric_profile"]
    assert profile["varying_coordinate_dtype"] == "float32"
    assert profile["lossy_nominal_coordinates"] == (["x"] if requested == 100_000_001.0 else [])


@pytest.mark.parametrize("method", ["auto", "delta"])
def test_output_roster_is_evaluated_at_the_same_rounded_nominal(method: str) -> None:
    """A Python-only precheck must not hide an output present at the native point."""

    def evaluate(*, x: float) -> dict[str, float]:
        if isinstance(x, jax.core.Tracer) or float(x) == 100_000_000.0:
            return {"y": x - 100_000_000.0}
        return {"other": 1.0}

    result = PropagationDispatcher(
        PropagationConfig(preferred_method=method, delta_covariance_jitter=0.0)
    ).propagate(evaluate, {"x": 100_000_001.0}, {"x": _normal(100_000_001.0)}, ["y"])[0]

    assert result.method_used is PropagationMethod.DELTA_METHOD
    assert result.envelope.distribution_family is DistributionFamily.NORMAL
    assert result.envelope.point_estimate == 0.0


@pytest.mark.parametrize("method", ["auto", "delta"])
def test_nonfinite_float32_coordinate_refuses_before_any_evaluation(method: str) -> None:
    """A failed numeric admission cannot silently fall back to an unbound MC call."""
    calls: list[float] = []

    def evaluate(*, x: float) -> dict[str, float]:
        calls.append(float(x))
        return {"y": 0.0}

    with pytest.raises(ValueError, match="float32"):
        PropagationDispatcher(
            PropagationConfig(preferred_method=method, delta_covariance_jitter=0.0)
        ).propagate(evaluate, {"x": 1e40}, {"x": _normal(1e40)}, ["y"])
    assert calls == []
