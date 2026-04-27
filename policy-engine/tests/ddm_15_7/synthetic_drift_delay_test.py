"""Synthetic drift and Track 2.2 adapter tests for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.ddm_15_7.calibration import synthetic_delay_test
from polisyos.ddm_15_7.detectors import adapt_shift_event
from polisyos.ddm_15_7.integration import AffectedSlice, MonitoringWindow, ShiftDetectedEvent


def _window() -> MonitoringWindow:
    return MonitoringWindow(
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 2, tzinfo=UTC),
        n=100,
    )


def test_shift_adapter_requires_calibrated_false_positive_evidence() -> None:
    with pytest.raises(ValueError, match="empirical_fp_rate"):
        ShiftDetectedEvent(
            event_id="shift-1",
            timestamp=datetime(2026, 4, 26, tzinfo=UTC),
            model_id="model",
            model_version="v1",
            detector_id="input_mmd_global_v3",
            detector_family="online_mmd",
            signal="input_shift",
            representation="feature_embedding_v2",
            reference_window=_window(),
            current_window=_window(),
            stationarity_regime_id="SR-1-model-v1",
            calibration_id="calib-1",
            test_statistic=0.2,
            ert=10000,
            shift_severity=0.72,
        )


def test_shift_adapter_preserves_localization_and_risk_level() -> None:
    event = ShiftDetectedEvent(
        event_id="shift-2",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="model",
        model_version="v1",
        detector_id="input_mmd_global_v3",
        detector_family="online_mmd",
        signal="input_shift",
        representation="feature_embedding_v2",
        reference_window=_window(),
        current_window=_window(),
        stationarity_regime_id="SR-1-model-v1",
        calibration_id="calib-1",
        test_statistic=0.2,
        ert=10000,
        empirical_fp_rate=0.001,
        shift_severity=0.72,
        affected_slices=[AffectedSlice(slice="region=west", score=0.44)],
    )

    risk = adapt_shift_event(event)

    assert risk.evidence_kind == "ert"
    assert risk.risk_level == "investigate"
    assert risk.affected_slices[0].slice == "region=west"


def test_synthetic_delay_detects_injected_shift_after_change_point() -> None:
    result = synthetic_delay_test([0.0, 0.0, 0.0, 0.0], threshold=0.2, shift=0.3)

    assert result.min_detectable_shift == 0.3
    assert result.median_delay_windows == 1
