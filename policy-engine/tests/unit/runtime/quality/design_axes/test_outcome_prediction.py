from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.runtime.quality.design_axes.outcome_prediction import (
    build_forecast_calibration_record,
    build_prediction_authority_boundary,
)


@pytest.mark.parametrize(
    ("kind", "media_type"),
    [
        ("ir.forecast_support", "application/json"),
        ("ir.empirical_calibration_evidence", "text/csv"),
    ],
)
def test_calibration_producer_rejects_wrong_empirical_artifact_profile(
    kind: str,
    media_type: str,
) -> None:
    """A content-address-shaped ref cannot substitute for the calibration artifact profile."""

    timestamp = datetime(2026, 8, 1, tzinfo=UTC)
    with pytest.raises(
        ValueError, match="empirical calibration evidence reference profile mismatch"
    ):
        build_forecast_calibration_record(
            calibration_id="calibration/municipal-bridge/observed-uptake",
            calibration_ref="pdc://municipal-bridge/s10/calibration/observed-uptake",
            case_id="municipal-bridge-pilot",
            forecast_support_ref="pdc://municipal-bridge/s10/support",
            observable_subset_ref="pdc://municipal-bridge/s10/observable-subset",
            prediction_ref="forecast://municipal-bridge/uptake/prediction",
            observed_outcome_ref="outcome://municipal-bridge/uptake/observed",
            historical_implementation_ref="implementation://municipal-bridge/pilot-1",
            evaluation_design_ref="evaluation://municipal-bridge/credible-comparison",
            credible_evaluation_evidence_ref="evidence://municipal-bridge/assignment-audit",
            counterfactual_credibility="credible",
            prediction_time=timestamp,
            observation_time=timestamp,
            policy_effective_time=timestamp,
            data_valid_time=timestamp,
            calibration_window_start=timestamp,
            calibration_window_end=timestamp,
            denominator=2,
            numerator=2,
            pass_rate=1.0,
            calibration_threshold_ref="repo://layer2/floors#s10-calibration",
            floor_passed=True,
            calibration_status="pass",
            empirical_evidence_ref={
                "artifact_id": "sha256:" + "5" * 64,
                "kind": kind,
                "media_type": media_type,
            },
            authority_boundary=build_prediction_authority_boundary(
                authoritative_for=["observable_subset_calibration"]
            ),
        )
