from __future__ import annotations

from datetime import UTC, datetime

from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.scientist.feedback.core import (
    build_monitoring_contract_from_packet,
    build_parameter_override_bundle,
)


def test_build_monitoring_contract_uses_packet_metrics_and_overrides() -> None:
    contract = build_monitoring_contract_from_packet(
        run_id="R_feedback",
        decision_lineage_key="lineage-1",
        anchor_at=datetime(2026, 4, 11, tzinfo=UTC),
        packet_payload={
            "simulation_results": {"policy_cost": 100.0, "benefit": 12.5},
            "backtest": {"overall_mae": 2.0, "overall_rmse": 4.0},
        },
        override={
            "default_window": {"days": 30},
            "metrics": {"policy_cost": {"min_observations": 3, "weight": 2.5}},
        },
    )

    assert contract is not None
    policy_cost = next(item for item in contract.metrics if item.metric_id == "policy_cost")
    assert policy_cost.min_observations == 3
    assert policy_cost.weight == 2.5
    assert policy_cost.confirm_range.lower == 90.0
    assert policy_cost.refute_range.upper == 120.0
    assert policy_cost.metadata == {"window_override": {"days": 30}}


def test_build_parameter_override_bundle_groups_by_node_id() -> None:
    report = CalibrationReport(
        calibrated_params={
            "sim.alpha": 0.1,
            "sim.beta": 0.2,
            "other.gamma": 0.3,
            "malformed": 99.0,
        },
        total_loss=1.0,
    )

    bundle = build_parameter_override_bundle(report)

    assert bundle is not None
    assert bundle.overrides == {
        "sim": {"alpha": 0.1, "beta": 0.2},
        "other": {"gamma": 0.3},
    }
    assert bundle.sources["sim"] == ["sim.alpha", "sim.beta"]
    assert bundle.notes == ["materialized_from_calibration_report"]
