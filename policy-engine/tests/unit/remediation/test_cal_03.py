"""Test-first witnesses for CAL-03 multi-start lifecycle and selection."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.calibration.calibrator import _calibration_span_context
from polisyos.foundry.calibration.hessian import HessianResult
from polisyos.foundry.calibration.multi_start import SingleRunResult, select_best
from polisyos.ir.analytics.calibration import MultiStartConfig

pytestmark = pytest.mark.unit


def _hessian(condition: float) -> HessianResult:
    """Build the smallest Hessian result needed by selection tests."""
    return HessianResult(
        hessian=np.eye(1),
        covariance=np.eye(1),
        std=np.ones(1),
        eigenvalues=np.array([1.0]),
        condition_number=condition,
        n_repaired=0,
        param_names=["p0"],
        strategy="exact",
    )


class _OneShotContext:
    """Context manager that models an OpenTelemetry context's one-shot entry."""

    def __init__(self) -> None:
        self.entered = False

    def __enter__(self) -> object:
        if self.entered:
            raise AssertionError("a span context was entered more than once")
        self.entered = True
        return object()

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


class _RecordingTracer:
    """Minimal tracer that records each context factory invocation."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def start_as_current_span(self, name: str, *, attributes: dict[str, object]):
        self.calls.append((name, attributes))
        return _OneShotContext()


def test_multi_start_uses_a_fresh_otel_context_for_each_start() -> None:
    """Each restart gets a new context, so one-shot OTel managers are safe."""
    tracer = _RecordingTracer()
    common_attributes = {"calibration.optimizer": "adam"}

    with _calibration_span_context(tracer, common_attributes, start_index=0):
        pass
    with _calibration_span_context(tracer, common_attributes, start_index=1):
        pass

    assert len(tracer.calls) == 2
    assert tracer.calls[0][0] == "calibration.run"
    assert tracer.calls[0][1]["calibration.start_index"] == 0
    assert tracer.calls[1][1]["calibration.start_index"] == 1


def test_multi_start_without_otel_still_gets_fresh_noop_contexts() -> None:
    """The no-observability path remains reusable without sharing a manager."""
    first = _calibration_span_context(None, {}, start_index=0)
    second = _calibration_span_context(None, {}, start_index=1)

    assert first is not second
    with first:
        pass
    with second:
        pass


def test_nan_loss_cannot_win_by_input_order() -> None:
    """Selection ignores a non-finite loss even when it appears first."""
    runs = [
        SingleRunResult(loss=float("nan"), params=[], hessian_result=_hessian(1.0)),
        SingleRunResult(loss=0.5, params=[], hessian_result=_hessian(1.0)),
    ]

    idx, _ = select_best(runs, MultiStartConfig(n_starts=2))

    assert idx == 1


def test_non_numeric_loss_cannot_win_by_input_order() -> None:
    """Malformed loss values are excluded from the candidate set."""
    runs = [
        SingleRunResult(
            loss="not-a-number",  # type: ignore[arg-type]
            params=[],
            hessian_result=_hessian(1.0),
        ),
        SingleRunResult(loss=0.5, params=[], hessian_result=_hessian(1.0)),
    ]

    idx, _ = select_best(runs, MultiStartConfig(n_starts=2))

    assert idx == 1


def test_infinite_condition_is_known_bad_not_missing_hessian() -> None:
    """A known degenerate Hessian cannot use the missing-diagnostic fallback."""
    runs = [
        SingleRunResult(loss=0.1, params=[], hessian_result=_hessian(float("inf"))),
        SingleRunResult(loss=0.5, params=[], hessian_result=_hessian(10.0)),
    ]

    idx, reason = select_best(
        runs,
        MultiStartConfig(n_starts=2, condition_threshold=1e8),
    )

    assert idx == 1
    assert "condition<" in reason


def test_missing_hessian_retains_loss_only_selection() -> None:
    """A genuinely missing Hessian remains distinct and may win by finite loss."""
    runs = [
        SingleRunResult(loss=0.1, params=[], hessian_result=None),
        SingleRunResult(loss=0.5, params=[], hessian_result=_hessian(10.0)),
    ]

    idx, reason = select_best(
        runs,
        MultiStartConfig(n_starts=2, condition_threshold=1e8),
    )

    assert idx == 0
    assert "missing" in reason


def test_finite_large_condition_is_filtered_before_fallback() -> None:
    """A finite condition above threshold is not treated as absent information."""
    runs = [
        SingleRunResult(loss=0.1, params=[], hessian_result=_hessian(1e12)),
        SingleRunResult(loss=0.5, params=[], hessian_result=_hessian(10.0)),
    ]

    idx, _ = select_best(
        runs,
        MultiStartConfig(n_starts=2, condition_threshold=1e8),
    )

    assert idx == 1


def test_equal_finite_losses_keep_input_order() -> None:
    """Selection is deterministic when candidates are otherwise tied."""
    runs = [
        SingleRunResult(loss=0.1, params=[], hessian_result=_hessian(10.0)),
        SingleRunResult(loss=0.1, params=[], hessian_result=_hessian(20.0)),
    ]

    idx, _ = select_best(runs, MultiStartConfig(n_starts=2))

    assert idx == 0


def test_all_condition_limited_runs_keep_finite_loss_and_report_fallback() -> None:
    """When every diagnostic is limited, choose the best finite loss explicitly."""
    runs = [
        SingleRunResult(loss=0.1, params=[], hessian_result=_hessian(float("inf"))),
        SingleRunResult(loss=float("nan"), params=[], hessian_result=_hessian(1e12)),
        SingleRunResult(loss=0.2, params=[], hessian_result=_hessian(1e12)),
    ]

    idx, reason = select_best(
        runs,
        MultiStartConfig(n_starts=3, condition_threshold=1e8),
    )

    assert idx == 0
    assert "fallback" in reason
    assert "inf" in reason


def test_best_identifiability_ignores_nonfinite_loss() -> None:
    """The alternate selection policy also excludes invalid losses."""
    runs = [
        SingleRunResult(loss=float("nan"), params=[], identifiability=None),
        SingleRunResult(loss=0.5, params=[], identifiability=None),
    ]

    idx, _ = select_best(
        runs,
        MultiStartConfig(n_starts=2, selection="best_identifiability"),
    )

    assert idx == 1


def test_single_invalid_loss_is_rejected() -> None:
    """A single invalid run must not be reported as selected."""
    with pytest.raises(ValueError, match="finite loss"):
        select_best(
            [SingleRunResult(loss=float("nan"), params=[])],
            MultiStartConfig(n_starts=1),
        )
