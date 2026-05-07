from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.voi_calibration import (
    build_voi_calibration_report,
    compare_voi_to_static_baseline,
    validate_voi_default_enable,
)
from polisyos.scientist.methods.search.voi_models import (
    VOIDecisionRecord,
    VOIDecisionType,
    VOIRunReport,
)


def _ref(suffix: str, *, kind: str = "scientist.voi_calibration") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
    )


def _report() -> VOIRunReport:
    decision = VOIDecisionRecord(
        decision_id="voi_decision_1",
        run_id="run_voi",
        decision_type=VOIDecisionType.STOP_SEARCH,
        recommended_action="stop_search",
        expected_value=0.0,
        expected_cost=0.25,
        expected_risk_reduction=0.0,
        explanation="Stop search because marginal improvement is below cost.",
    )
    return VOIRunReport(
        run_id="run_voi",
        decisions=[decision],
        total_expected_cost=0.25,
        calibration_status="shadow",
    )


def test_calibration_reports_baseline_comparison() -> None:
    comparison = compare_voi_to_static_baseline(
        _report(),
        static_expected_cost=1.0,
        static_safety_score=0.95,
        voi_safety_score=0.96,
    )
    calibration = build_voi_calibration_report(_report(), comparison=comparison)

    assert comparison.non_worse_safety is True
    assert comparison.cost_targeting_improved is True
    assert comparison.regret == 0.0
    assert calibration.default_enable_allowed is True


def test_learned_or_shadow_voi_cannot_default_without_calibration_and_regret_refs() -> None:
    comparison = compare_voi_to_static_baseline(
        _report(),
        static_expected_cost=1.0,
        static_safety_score=0.95,
        voi_safety_score=0.96,
    )
    calibration = build_voi_calibration_report(_report(), comparison=comparison)

    violations = validate_voi_default_enable(
        report=_report(),
        calibration_report=calibration,
        calibration_report_ref=None,
        regret_report_ref=None,
        learned_or_shadow=True,
    )

    assert "missing_calibration_report_ref" in violations
    assert "missing_regret_report_ref" in violations
    assert (
        validate_voi_default_enable(
            report=_report(),
            calibration_report=calibration,
            calibration_report_ref=_ref("1"),
            regret_report_ref=_ref("2", kind="scientist.voi_regret"),
            learned_or_shadow=True,
        )
        == []
    )


def test_worse_shadow_regret_blocks_default_enable() -> None:
    comparison = compare_voi_to_static_baseline(
        _report(),
        static_expected_cost=0.1,
        static_safety_score=0.98,
        voi_safety_score=0.9,
    )
    calibration = build_voi_calibration_report(_report(), comparison=comparison)

    violations = validate_voi_default_enable(
        report=_report(),
        calibration_report=calibration,
        calibration_report_ref=_ref("1"),
        regret_report_ref=_ref("2", kind="scientist.voi_regret"),
    )

    assert calibration.default_enable_allowed is False
    assert any(item.startswith("calibration_blocker:") for item in violations)
