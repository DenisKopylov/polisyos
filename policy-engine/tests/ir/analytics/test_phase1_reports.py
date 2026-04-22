from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.microsim.protocols import (
    ReweightingCompatibilityReason,
    ReweightingCompatibilityStatus,
    ReweightingCompatibilityTestMethod,
    ReweightingTargetCompatibility,
)
from polisyos.ir.analytics.dependence_structure import (
    build_dependence_structure,
    load_dependence_structure,
    persist_dependence_structure,
)
from polisyos.ir.analytics.microsim_calibration import (
    MicrosimCalibrationReport,
    load_microsim_calibration_report,
    persist_microsim_calibration_report,
    report_from_target_compatibility,
)
from polisyos.ir.analytics.mobility import (
    MobilityReport,
    load_mobility_report,
    persist_mobility_report,
)


def test_microsim_calibration_report_round_trips_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = MicrosimCalibrationReport(
        decision="warn",
        can_run_microsim=True,
        compatibility_status="approximately_compatible",
        reason_code="DISTANCE_TOLERANCE",
        exact_feasible=False,
        distance_to_feasibility=0.2,
        normalized_distance=0.05,
        jacobian_rank=2,
        condition_number=12.0,
        max_abs_gap=0.1,
        warnings=["compatibility:approximately_compatible"],
        metadata={"solver": "gmm"},
    )

    ref = persist_microsim_calibration_report(store, report)
    loaded = load_microsim_calibration_report(store, ref)

    assert loaded == report


def test_target_compatibility_maps_into_microsim_gate_report() -> None:
    compatibility = ReweightingTargetCompatibility(
        status=ReweightingCompatibilityStatus.INCOMPATIBLE,
        reason_code=ReweightingCompatibilityReason.BOUNDS_PRECLUDE_TARGETS,
        exact_feasible=False,
        distance_to_feasibility=1.5,
        normalized_distance=0.4,
        test_method=ReweightingCompatibilityTestMethod.HANSEN_J,
        statistic=8.2,
        df=3,
        p_value=0.03,
        n_targets=4,
        n_free_params=2,
        jacobian_rank=2,
        condition_number=25.0,
        warnings=["solver_hit_boundary"],
        solver_status="infeasible",
    )

    report = report_from_target_compatibility(
        compatibility,
        max_abs_gap=0.7,
        metadata={"solver": "bounded_ipf"},
    )

    assert report.decision == "block"
    assert report.can_run_microsim is False
    assert report.reason_code == "BOUNDS_PRECLUDE_TARGETS"
    assert "compatibility:incompatible" in report.blocking_reasons
    assert report.metadata["test_method"] == "hansen_j"
    assert report.metadata["solver"] == "bounded_ipf"


def test_dependence_structure_round_trips_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    structure = build_dependence_structure(
        regime="network_adjacent",
        class_label="graph_local",
        calibrated=True,
        recommended_covariance="network_hac",
        source_method="tests.phase1.network",
        metrics={"moran_i": 0.4},
        metadata={"graph_id": "g1"},
    )

    ref = persist_dependence_structure(store, structure)
    loaded = load_dependence_structure(store, ref)

    assert loaded == structure


def test_mobility_report_round_trips_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = MobilityReport(
        analysis_type="intergenerational_elasticity",
        status="ok",
        summary_metrics={"ige": 0.42, "n": 120},
        sensitivity_envelope={"bootstrap_ci": [0.30, 0.55]},
        upstream_refs=["artifact://demo"],
        metadata={"log_scale": True},
    )

    ref = persist_mobility_report(store, report)
    loaded = load_mobility_report(store, ref)

    assert loaded == report


def test_mobility_report_v2_round_trips_with_typed_blocks(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = MobilityReport(
        analysis_type="transition_matrix_attrition_adjusted",
        estimand_id="mobility.parent_child_income_quintile",
        status="warn",
        population={
            "target_population": "panel baseline cohort",
            "weights_design": "sample_weights",
            "panel_length": 2,
            "waves_used": [1, 2],
            "class_definition": {"type": "quintile", "n_classes": 2},
        },
        attrition={
            "pattern": "monotone_dropout",
            "mechanism_assumed": "mar_given_observables",
            "positivity_floor": 0.05,
            "weight_model": {"family": "weighted_logit", "features": ["x_0"]},
        },
        point_estimate={
            "joint_matrix": [[0.25, 0.25], [0.10, 0.40]],
            "transition_matrix": [[0.5, 0.5], [0.2, 0.8]],
            "row_marginals": [0.5, 0.5],
            "col_marginals": [0.35, 0.65],
            "mobility_stats": {
                "upward_rate": 0.25,
                "downward_rate": 0.10,
                "immobility_rate": 0.65,
            },
        },
        bounds={
            "summary_bounds": {"upward_rate": (0.20, 0.35)},
            "sharpness_status": "sharp_with_known_marginals",
            "method": "sharp_transport_bounds_known_marginals",
        },
        diagnostics={
            "observed_full_cases": 120,
            "effective_sample_size": 89.5,
            "warnings": ["large_ipcw_weights"],
        },
        assumptions=["mar_given_observables", "positivity"],
        upstream_refs=["artifact://demo"],
        metadata={"code_version": "mobility-v2"},
    )

    ref = persist_mobility_report(store, report)
    loaded = load_mobility_report(store, ref)

    assert loaded.schema_version == "2.0"
    assert loaded.artifact_name == "mobility_report_v2.json"
    assert loaded.point_estimate.transition_matrix[1][1] == pytest.approx(0.8)
    assert loaded.summary_metrics["upward_mobility_rate"] == pytest.approx(0.25)
    assert loaded.sensitivity_envelope["summary_bounds"]["upward_rate"] == pytest.approx((0.20, 0.35))


def test_legacy_mobility_payload_is_upgraded_to_phase2_views() -> None:
    report = MobilityReport.model_validate(
        {
            "schema_version": "1.0",
            "artifact_name": "mobility_report_v1.json",
            "analysis_type": "transition_matrix",
            "status": "ok",
            "summary_metrics": {
                "transition_matrix": [[0.75, 0.25], [0.10, 0.90]],
                "upward_mobility_rate": 0.25,
                "downward_mobility_rate": 0.10,
                "immobility_rate": 0.65,
                "n_classes": 2,
                "n_obs": 80,
            },
            "metadata": {"valid_observations": 80},
        }
    )

    assert report.schema_version == "1.0"
    assert report.point_estimate.transition_matrix == [[0.75, 0.25], [0.10, 0.90]]
    assert report.point_estimate.mobility_stats["upward_rate"] == pytest.approx(0.25)
    assert report.diagnostics.observed_full_cases == 80
