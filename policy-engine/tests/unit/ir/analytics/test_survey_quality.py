from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.missing_data import assess_administrative_missingness
from polisyos.ir.analytics.administrative_missingness import (
    AdministrativeMissingnessClass,
    MissingnessAssessmentStatus,
    build_compliance_based_mgraph,
    build_registration_based_mgraph,
)
from polisyos.ir.analytics.survey_quality import (
    SurveyAssumptionLayer,
    SurveyAssumptionStatus,
    build_survey_quality_certificate,
    load_survey_quality_certificate,
    persist_survey_quality_certificate,
)


def test_survey_quality_certificate_builds_from_recoverable_missingness_assessment() -> None:
    graph = build_registration_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        registration_indicator="registration_flag",
        eligibility_covariates=["eligibility_score"],
        population_frame_observed=True,
        evidence_refs=["artifact://ops/registration_snapshot"],
    )
    assessment = assess_administrative_missingness(graph=graph)

    certificate = build_survey_quality_certificate(
        target_estimand="E[income]",
        estimator_id="survey.dr.design_missingness",
        missingness_assessment=assessment,
    )

    assert (
        certificate.missingness_class is AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED
    )
    assert certificate.missingness_status is MissingnessAssessmentStatus.RECOVERABLE
    assert certificate.overall_pass is True
    assert certificate.evidence_refs == ["artifact://ops/registration_snapshot"]
    assert certificate.missingness_assumptions[0].layer is SurveyAssumptionLayer.MISSINGNESS
    assert certificate.missingness_assumptions[0].status is SurveyAssumptionStatus.PASS


def test_survey_quality_certificate_blocks_not_recoverable_missingness() -> None:
    graph = build_compliance_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        compliance_indicator="filing_complete",
        compliance_driver_covariates=["deadline_pressure"],
        self_censoring_variables=["income"],
    )
    assessment = assess_administrative_missingness(graph=graph)

    certificate = build_survey_quality_certificate(
        target_estimand="E[income]",
        missingness_assessment=assessment,
    )

    assert certificate.missingness_status is MissingnessAssessmentStatus.NOT_RECOVERABLE
    assert certificate.overall_pass is False
    assert "missingness_not_recoverable" in certificate.blocking_reasons
    assert certificate.missingness_assumptions[0].status is SurveyAssumptionStatus.FAIL


def test_survey_quality_certificate_round_trips_via_store(tmp_path) -> None:
    graph = build_registration_based_mgraph(
        substantive_vars=["income", "outcome"],
        directed_edges=[("income", "outcome")],
        target_variables=["income"],
        registration_indicator="registration_flag",
        eligibility_covariates=["eligibility_score"],
        population_frame_observed=True,
    )
    assessment = assess_administrative_missingness(graph=graph)
    certificate = build_survey_quality_certificate(
        target_estimand="E[income]",
        estimator_id="survey.dr.design_missingness",
        missingness_assessment=assessment,
    )

    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_survey_quality_certificate(store, certificate)
    loaded = load_survey_quality_certificate(store, ref)

    assert loaded == certificate
