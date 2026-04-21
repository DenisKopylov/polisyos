from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.dependence_structure import (
    build_dependence_structure,
    persist_dependence_structure,
)
from polisyos.ir.analytics.microsim_calibration import (
    build_microsim_calibration_report,
    persist_microsim_calibration_report,
)
from polisyos.ir.analytics.mobility import MobilityReport, persist_mobility_report
from polisyos.ir.analytics.survey_quality import (
    SurveyRequestedRegime,
    SurveyValidatedRegime,
    build_survey_quality_certificate,
    persist_survey_quality_certificate,
)
from polisyos.ir.governance.phase1 import (
    build_phase1_gate_summary,
    load_phase1_flagship_dataset_ids,
)


def _persist_flagship_certificate(store: FileSystemCAS, dataset_id: str) -> None:
    certificate = build_survey_quality_certificate(
        target_estimand="E[Y]",
        estimator_id="survey.dr.design_missingness@1.0.0",
        dataset_id=dataset_id,
        data_origin="government",
        regime_requested=SurveyRequestedRegime.POPULATION_MAR,
        regime_validated=SurveyValidatedRegime.BOTH_VALID,
        estimate=1.0,
        standard_error=0.1,
        overall_pass=True,
    )
    persist_survey_quality_certificate(store, certificate)


def test_phase1_gate_summary_requires_complete_evidence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dataset_ids = load_phase1_flagship_dataset_ids()
    for dataset_id in dataset_ids[:2]:
        _persist_flagship_certificate(store, dataset_id)
    persist_dependence_structure(
        store,
        build_dependence_structure(
            regime="panel",
            class_label="factor",
            calibrated=True,
            recommended_covariance="driscoll_kraay",
            source_method="tests.phase1.panel",
        ),
    )

    summary = build_phase1_gate_summary(store)

    assert summary.overall_passed is False
    assert "phase1_flagship_dataset_coverage_incomplete" in summary.blocking_reasons
    assert "phase1_dependence_regime_coverage_incomplete" in summary.blocking_reasons
    assert "phase1_microsim_gate_unverified" in summary.blocking_reasons
    assert "phase1_mobility_shell_unverified" in summary.blocking_reasons


def test_phase1_gate_summary_passes_with_full_evidence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dataset_ids = load_phase1_flagship_dataset_ids()
    for dataset_id in dataset_ids:
        _persist_flagship_certificate(store, dataset_id)

    for regime, covariance in (
        ("panel", "driscoll_kraay"),
        ("areal", "conley_spatial_hac"),
        ("network_adjacent", "network_hac"),
    ):
        persist_dependence_structure(
            store,
            build_dependence_structure(
                regime=regime,
                class_label="shared",
                calibrated=True,
                recommended_covariance=covariance,
                source_method=f"tests.phase1.{regime}",
            ),
        )

    persist_microsim_calibration_report(
        store,
        build_microsim_calibration_report(
            compatibility_status="compatible",
            exact_feasible=True,
        ),
    )
    persist_mobility_report(
        store,
        MobilityReport(
            analysis_type="transition_matrix",
            status="ok",
            summary_metrics={"n_obs": 100},
        ),
    )

    summary = build_phase1_gate_summary(store)

    assert summary.overall_passed is True
    assert summary.flagship_dataset_coverage_ready is True
    assert summary.dependence_regime_coverage_ready is True
    assert summary.microsim_gate_ready is True
    assert summary.mobility_shell_ready is True
    assert summary.blocking_reasons == []
