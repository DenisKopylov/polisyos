"""Native causal reports preserve their numerical values through envelope storage."""

from __future__ import annotations

import math

import pytest

from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.analytics.uncertainty import (
    NumericPolicySpec,
    NumericToleranceMode,
    UncertaintyEnvelope,
)


def _report(point: float, interval: tuple[float, float], level: float) -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.REGRESSION_DISCONTINUITY,
        estimand="LATE",
        point_estimate=point,
        confidence_interval=interval,
        confidence_level=level,
        inference_method="asymptotic",
        sample_size=80,
        n_treated=40,
        n_control=40,
        pre_periods=0,
        post_periods=0,
    )


@pytest.mark.parametrize(
    ("point", "interval", "level"),
    [
        (2.0, (1.0, 3.0), math.nextafter(1.0, 0.0)),
        (2.0, (1.0, 3.0), math.nextafter(0.0, 1.0)),
        (1e-20, (0.5e-20, 1.5e-20), 0.95),
        (2.0, (math.nextafter(2.0, 0.0), math.nextafter(2.0, math.inf)), 0.95),
    ],
)
def test_native_projection_preserves_exact_binary64_result_after_json_read(
    point: float, interval: tuple[float, float], level: float
) -> None:
    report = _report(point, interval, level)
    projected = report.to_uncertainty_envelope()
    assert projected is not None
    assert projected.numeric_policy.mode is NumericToleranceMode.DECIMAL_EXACT
    restored = UncertaintyEnvelope.model_validate_json(projected.model_dump_json())
    assert restored.point_estimate == report.point_estimate
    assert restored.confidence_interval == report.confidence_interval
    assert restored.confidence_level == report.confidence_level
    assert restored.confidence_interval[0] < restored.confidence_interval[1]
    assert restored.gate_eligible is False


def test_exactly_represented_report_keeps_existing_default_envelope_policy() -> None:
    projected = _report(2.0, (1.0, 3.0), 0.95).to_uncertainty_envelope()
    assert projected is not None
    assert projected.numeric_policy == NumericPolicySpec()


def test_recorded_default_policy_is_still_respected_by_envelope_reader() -> None:
    projected = _report(2.0, (1.0, 3.0), 0.95).to_uncertainty_envelope()
    assert projected is not None
    old_payload = projected.model_dump(mode="json")
    old_payload["point_estimate"] = 2.12345678901234
    restored = UncertaintyEnvelope.model_validate(old_payload)
    assert restored.point_estimate == round(old_payload["point_estimate"], 12)
    assert restored.numeric_policy == NumericPolicySpec()
