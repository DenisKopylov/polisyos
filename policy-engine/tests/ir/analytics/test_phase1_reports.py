from __future__ import annotations

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
