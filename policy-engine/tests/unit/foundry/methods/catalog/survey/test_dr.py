from __future__ import annotations

import numpy as np
import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.administrative_missingness import (
    AdministrativeMissingnessClass,
    AdministrativeMissingnessScenarioFamily,
    MissingnessAssessmentReport,
    MissingnessAssessmentStatus,
)
from polisyos.ir.analytics.survey_quality import (
    SurveyQualityCertificate,
    SurveyRequestedRegime,
    SurveyValidatedRegime,
    SurveyVarianceMode,
    load_survey_quality_certificate,
)
from polisyos.ir.refs import SurveyQualityCertificateRef


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _recoverable_assessment() -> dict[str, object]:
    return MissingnessAssessmentReport(
        status=MissingnessAssessmentStatus.RECOVERABLE,
        scenario_family=AdministrativeMissingnessScenarioFamily.REGISTRATION_BASED,
        scenario_class=AdministrativeMissingnessClass.REGISTRATION_NOT_REGISTERED,
        scenario_confidence=0.92,
    ).model_dump(mode="json")


def _not_recoverable_assessment() -> dict[str, object]:
    return MissingnessAssessmentReport(
        status=MissingnessAssessmentStatus.NOT_RECOVERABLE,
        scenario_family=AdministrativeMissingnessScenarioFamily.COMPLIANCE_BASED,
        scenario_class=AdministrativeMissingnessClass.COMPLIANCE_NOT_COMPLETED,
        scenario_confidence=0.88,
    ).model_dump(mode="json")


def _synthetic_dr_state(
    *, seed: int = 42, assessment: dict[str, object] | None = None
) -> dict[str, np.ndarray | dict[str, object]]:
    rng = np.random.default_rng(seed)
    n = 320
    X = rng.normal(size=(n, 2))
    base_weights = np.exp(rng.normal(0.0, 0.15, size=n))
    logits = -0.35 + 0.9 * X[:, 0] - 0.5 * X[:, 1] + 0.15 * np.log(base_weights)
    response_prob = 1.0 / (1.0 + np.exp(-logits))
    response = rng.binomial(1, response_prob).astype(float)
    Y = 5.0 + 2.0 * X[:, 0] - 1.5 * X[:, 1] + rng.normal(0.0, 0.25, size=n)
    Y = np.where(response > 0.5, Y, 0.0)
    strata = np.where(X[:, 0] > 0.0, "north", "south")
    clusters = np.array([f"c{i % 24}" for i in range(n)], dtype=object)
    replicate_weights = np.vstack(
        [
            np.clip(base_weights * (1.0 + rng.normal(0.0, 0.05, size=n)), 0.05, None)
            for _ in range(6)
        ]
    )
    state: dict[str, np.ndarray | dict[str, object]] = {
        "X": X,
        "Y": Y,
        "response_indicator": response,
        "base_weights": base_weights,
        "strata": strata,
        "clusters": clusters,
        "replicate_weights": replicate_weights,
    }
    if assessment is not None:
        state["missingness_assessment"] = assessment
    return state


def _synthetic_shadow_state() -> dict[str, np.ndarray | dict[str, object]]:
    rng = np.random.default_rng(0)
    n = 320
    X = rng.normal(size=(n, 2))
    shadow = (0.8 * X[:, 0] - 0.3 * X[:, 1] + rng.normal(0.0, 0.5, size=n))[:, None]
    base_weights = np.exp(rng.normal(0.0, 0.10, size=n))
    latent_y = (
        3.0 + 1.4 * X[:, 0] - 0.8 * X[:, 1] + 1.2 * shadow[:, 0] + rng.normal(0.0, 0.3, size=n)
    )
    logits = -0.2 + 0.5 * X[:, 0] + 0.35 * ((latent_y - latent_y.mean()) / latent_y.std())
    response = rng.binomial(1, 1.0 / (1.0 + np.exp(-logits)), size=n).astype(float)
    Y = np.where(response > 0.5, latent_y, 0.0)
    return {
        "X": X,
        "Y": Y,
        "response_indicator": response,
        "base_weights": base_weights,
        "strata": np.where(X[:, 0] > 0.0, "north", "south"),
        "clusters": np.array([f"c{i % 24}" for i in range(n)], dtype=object),
        "shadow_variables": shadow,
        "missingness_assessment": _recoverable_assessment(),
    }


def _synthetic_reference_state() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(1)
    n = 260
    n_ref = 420
    X = rng.normal(size=(n, 2))
    reference_X = rng.normal(size=(n_ref, 2))
    base_weights = np.exp(rng.normal(0.0, 0.08, size=n))
    reference_weights = np.exp(rng.normal(0.0, 0.05, size=n_ref))
    latent_y = 4.0 + 1.2 * X[:, 0] - 0.7 * X[:, 1] + rng.normal(0.0, 0.4, size=n)
    response = rng.binomial(
        1,
        1.0 / (1.0 + np.exp(-(-0.1 + 0.6 * X[:, 0] - 0.3 * X[:, 1]))),
        size=n,
    ).astype(float)
    Y = np.where(response > 0.5, latent_y, 0.0)
    return {
        "X": X,
        "Y": Y,
        "response_indicator": response,
        "base_weights": base_weights,
        "strata": np.where(X[:, 0] > 0.0, "north", "south"),
        "clusters": np.array([f"a{i % 20}" for i in range(n)], dtype=object),
        "reference_X": reference_X,
        "reference_design_weights": reference_weights,
        "reference_strata": np.where(reference_X[:, 0] > 0.0, "north", "south"),
        "reference_clusters": np.array([f"r{i % 28}" for i in range(n_ref)], dtype=object),
    }


class TestDesignMissingnessDR:
    def test_population_mar_threads_missingness_assessment_into_certificate(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(isolated_registry, "survey.dr.design_missingness@1.0.0")
        result = method.pure_step(
            _synthetic_dr_state(assessment=_recoverable_assessment()),
            {
                "regime": "population_mar",
                "crossfit_folds": 4,
                "diagnostic_threshold": 0.08,
            },
        )

        payload = result["result"]
        certificate = payload["survey_quality_certificate"]

        assert np.isfinite(payload["estimate"])
        assert payload["standard_error"] >= 0.0
        assert certificate["regime_requested"] == "population_mar"
        assert certificate["regime_validated"] in {
            "both_valid",
            "design_valid_only",
            "imputation_valid_only",
        }
        assert certificate["missingness_status"] == "recoverable"
        assert certificate["missingness_class"] == "registration_not_registered"
        assert certificate["overall_pass"] is True

    def test_replicate_variance_path_is_used_when_requested(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.dr.design_missingness@1.0.0")
        result = method.pure_step(
            _synthetic_dr_state(seed=7),
            {
                "regime": "population_mar",
                "variance_mode": "replicate",
                "crossfit_folds": 4,
                "diagnostic_threshold": 0.08,
            },
        )

        payload = result["result"]
        certificate = payload["survey_quality_certificate"]

        assert payload["variance_mode"] == "replicate"
        assert certificate["variance_mode"] == "replicate"
        assert payload["replicate_estimates"] is not None

    def test_mnar_shadow_can_validate_identified_branch_when_shadow_signal_is_strong(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(isolated_registry, "survey.dr.design_missingness@1.0.0")
        result = method.pure_step(
            _synthetic_shadow_state(),
            {
                "regime": "mnar_shadow",
                "crossfit_folds": 4,
                "diagnostic_threshold": 0.12,
            },
        )

        payload = result["result"]
        certificate = payload["survey_quality_certificate"]

        assert payload["selection_membership_probability"] is None
        assert certificate["regime_validated"] == "mnar_shadow_identified"
        assert certificate["overall_pass"] is True
        ids_to_status = {
            component["component_id"]: component["status"]
            for component in certificate["identification_assumptions"]
        }
        assert ids_to_status["shadow_variable_valid"] == "pass"
        assert ids_to_status["validation_link_available"] == "pass"

    def test_mnar_shadow_without_shadow_variables_is_blocked(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.dr.design_missingness@1.0.0")
        result = method.pure_step(
            _synthetic_dr_state(seed=9, assessment=_recoverable_assessment()),
            {
                "regime": "mnar_shadow",
                "crossfit_folds": 4,
                "diagnostic_threshold": 0.08,
            },
        )

        certificate = result["result"]["survey_quality_certificate"]
        assert certificate["regime_validated"] == "mnar_unidentified"
        assert certificate["overall_pass"] is False
        assert "mnar_shadow_requires_shadow_variables" in certificate["blocking_reasons"]

    def test_population_mar_is_guarded_when_missingness_is_not_recoverable(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(isolated_registry, "survey.dr.design_missingness@1.0.0")
        result = method.pure_step(
            _synthetic_dr_state(seed=11, assessment=_not_recoverable_assessment()),
            {
                "regime": "population_mar",
                "crossfit_folds": 4,
                "diagnostic_threshold": 0.08,
            },
        )

        certificate = result["result"]["survey_quality_certificate"]
        assert certificate["regime_validated"] == "mnar_unidentified"
        assert certificate["overall_pass"] is False
        assert (
            "missingness_assessment_requires_non_mar_identification"
            in certificate["blocking_reasons"]
        )
        assert "missingness_not_recoverable" in certificate["blocking_reasons"]

    def test_reference_integration_path_returns_reference_mode_payload(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(isolated_registry, "survey.dr.design_missingness@1.0.0")
        result = method.pure_step(
            _synthetic_reference_state(),
            {
                "regime": "population_mar",
                "crossfit_folds": 4,
                "diagnostic_threshold": 0.15,
            },
        )

        payload = result["result"]
        certificate = payload["survey_quality_certificate"]

        assert payload["estimation_mode"] == "reference_integration"
        assert payload["selection_membership_probability"] is not None
        assert payload["reference_outcome_regression"] is not None
        assert certificate["overall_pass"] is True
        assert certificate["regime_validated"] in {
            "both_valid",
            "design_valid_only",
            "imputation_valid_only",
        }

    def test_certificate_is_persisted_when_artifact_store_is_present(
        self,
        isolated_registry,
        tmp_path,
    ) -> None:
        method = _method_or_skip(isolated_registry, "survey.dr.design_missingness@1.0.0")
        store = FileSystemCAS(tmp_path / "cas")
        result = method.pure_step(
            {
                **_synthetic_dr_state(assessment=_recoverable_assessment()),
                "metadata": {
                    "dataset_id": "demo-government-dataset",
                    "data_origin": "government",
                },
            },
            {
                "regime": "population_mar",
                "crossfit_folds": 4,
                "diagnostic_threshold": 0.08,
                "artifact_store": store,
            },
        )

        payload = result["result"]
        ref_payload = payload["survey_quality_certificate_ref"]

        assert ref_payload is not None
        loaded = load_survey_quality_certificate(
            store,
            SurveyQualityCertificateRef.model_validate(ref_payload),
        )
        assert loaded.dataset_id == "demo-government-dataset"
        assert loaded.data_origin == "government"
        assert loaded.overall_pass is True


def test_shadow_identified_certificate_requires_sensitivity_radius() -> None:
    with pytest.raises(ValueError, match="sensitivity_radius"):
        SurveyQualityCertificate(
            target_estimand="E[Y]",
            estimator_id="survey.dr.design_missingness@1.0.0",
            regime_requested=SurveyRequestedRegime.MNAR_SHADOW,
            regime_validated=SurveyValidatedRegime.MNAR_SHADOW_IDENTIFIED,
            estimate=1.0,
            standard_error=0.1,
            variance_mode=SurveyVarianceMode.SANDWICH,
            overall_pass=True,
        )
