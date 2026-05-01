from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.scientist.search.voi_models import (
    VOIDecisionRecord,
    VOIDecisionType,
    VOIRunReport,
    stable_voi_decision_id,
    validate_mandatory_gate_policy,
)


def _decision(
    *,
    action: str = "defer",
    expected_value: float = 0.1,
    mandatory_gate_overrides: list[str] | None = None,
) -> VOIDecisionRecord:
    return VOIDecisionRecord(
        decision_id=stable_voi_decision_id(
            run_id="run_voi",
            decision_type=VOIDecisionType.CANDIDATE_EVALUATION,
            subject_id=action,
        ),
        run_id="run_voi",
        decision_type=VOIDecisionType.CANDIDATE_EVALUATION,
        recommended_action=action,
        expected_value=expected_value,
        expected_cost=0.05,
        expected_risk_reduction=0.2,
        mandatory_gate_overrides=mandatory_gate_overrides or [],
        explanation=f"{action} because expected value warrants it.",
    )


def test_voi_decision_and_report_validate() -> None:
    report = VOIRunReport(
        run_id="run_voi",
        decisions=[_decision()],
        total_expected_cost=0.05,
        calibration_status="shadow",
    )

    assert report.decisions[0].decision_type is VOIDecisionType.CANDIDATE_EVALUATION
    assert validate_mandatory_gate_policy(report) == []


def test_report_with_no_explanation_fails_validation() -> None:
    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        VOIDecisionRecord(
            decision_id="decision_1",
            run_id="run_voi",
            decision_type=VOIDecisionType.STOP_SEARCH,
            recommended_action="stop_search",
            expected_value=0.0,
            expected_cost=0.0,
            expected_risk_reduction=0.0,
            explanation="",
        )


def test_negative_expected_value_must_defer_reject_or_stop() -> None:
    with pytest.raises(ValidationError, match="negative expected value"):
        _decision(action="advance", expected_value=-0.1)


def test_mandatory_gate_override_cannot_advance() -> None:
    with pytest.raises(ValidationError, match="mandatory gates"):
        _decision(
            action="advance",
            expected_value=0.5,
            mandatory_gate_overrides=["benchmark_authority_missing"],
        )


def test_report_total_cost_cannot_understate_decision_costs() -> None:
    with pytest.raises(ValidationError, match="total_expected_cost"):
        VOIRunReport(
            run_id="run_voi",
            decisions=[_decision()],
            total_expected_cost=0.0,
            calibration_status="shadow",
        )
