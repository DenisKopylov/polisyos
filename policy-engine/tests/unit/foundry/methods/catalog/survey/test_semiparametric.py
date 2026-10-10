from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.survey.semiparametric import (
    SamplingModelSpec,
    SurveyDesignSpec,
    SurveySemiparametricATEEstimator,
    SurveySemiparametricATTEstimator,
    SurveySemiparametricSubgroupMeanEstimator,
    SurveyVarianceBackend,
    build_psu_stratified_cross_fit_schedule,
    build_survey_adjusted_signal,
    compute_binder_linearized_variance,
    diagnose_weight_regime,
)


def test_build_survey_adjusted_signal_matches_observed_data_formula() -> None:
    design = SurveyDesignSpec(
        weights=np.array([2.0, 1.0, 4.0, 1.0]),
        strata=np.array([0, 0, 1, 1]),
        psu=np.array([10, 11, 20, 21]),
        provenance="base",
    )
    sampling = SamplingModelSpec(sampled=np.array([1.0, 0.0, 1.0, 1.0]))
    full_signal = np.array([1.0, 2.0, 4.0, 8.0])
    augmentation = np.array([0.5, 0.5, 1.0, 2.0])

    result = build_survey_adjusted_signal(
        full_signal,
        design,
        sampling,
        augmentation=augmentation,
        normalization="horvitz_thompson",
        estimand_label="ate",
    )

    expected = augmentation + sampling.sampled * design.weights * (full_signal - augmentation)
    np.testing.assert_allclose(result.observed_signal, expected)
    assert result.estimate == np.mean(expected)


def test_hajek_normalization_rescales_inverse_inclusion_weights_to_mean_one() -> None:
    design = SurveyDesignSpec(
        weights=np.array([1.0, 2.0, 3.0, 4.0]),
        strata=np.array([0, 0, 1, 1]),
        psu=np.array([0, 1, 2, 3]),
        provenance="base",
    )

    result = build_survey_adjusted_signal(
        np.array([1.0, 2.0, 3.0, 4.0]),
        design,
        augmentation=0.0,
        normalization="hajek",
        estimand_label="generic",
    )

    assert np.isclose(np.mean(result.inverse_inclusion_weights), 1.0)


def test_build_survey_adjusted_signal_supports_replicate_variance_backend() -> None:
    design = SurveyDesignSpec(
        weights=np.array([1.0, 1.0, 1.0, 1.0]),
        strata=np.array([0, 0, 1, 1]),
        psu=np.array([10, 11, 20, 21]),
        replicate_weights=np.array(
            [
                [2.0, 0.0, 1.0, 1.0],
                [0.0, 2.0, 1.0, 1.0],
                [1.0, 1.0, 2.0, 0.0],
                [1.0, 1.0, 0.0, 2.0],
            ]
        ),
        provenance="base",
    )

    result = build_survey_adjusted_signal(
        np.array([1.0, 2.0, 3.0, 4.0]),
        design,
        augmentation=0.0,
        normalization="hajek",
        estimand_label="ate",
        variance_backend=SurveyVarianceBackend(method="brr"),
    )

    assert result.variance_method == "brr"
    assert result.std_error >= 0.0


def test_compute_binder_linearized_variance_matches_manual_cluster_formula() -> None:
    values = np.array([1.0, 2.0, 2.0, 4.0])
    strata = np.array([0, 0, 1, 1])
    psu = np.array([10, 11, 20, 21])

    variance = compute_binder_linearized_variance(values, strata=strata, psu=psu)

    assert np.isclose(variance.variance, 5.0 / 16.0)
    assert np.isclose(variance.standard_error, np.sqrt(5.0 / 16.0))
    assert len(variance.psu_labels) == 4


def test_diagnose_weight_regime_claims_efficiency_only_in_full_design_regime() -> None:
    n_obs = 40
    design = SurveyDesignSpec(
        weights=np.ones(n_obs),
        strata=np.repeat(np.arange(4), 10),
        psu=np.repeat(np.arange(8), 5),
        provenance="base",
    )
    treatment = np.tile([0.0, 1.0], n_obs // 2)
    propensity = np.full(n_obs, 0.5)

    diagnostic = diagnose_weight_regime(
        design,
        estimand="ate",
        treatment=treatment,
        propensity=propensity,
    )

    assert diagnostic.weight_regime == "full_design"
    assert diagnostic.claim_level == "design_dr_efficiency_claimable"
    assert diagnostic.positivity_flags == ()


def test_diagnose_weight_regime_downgrades_calibrated_and_informative_cases() -> None:
    n_obs = 40
    treatment = np.tile([0.0, 1.0], n_obs // 2)
    propensity = np.full(n_obs, 0.5)

    calibrated_design = SurveyDesignSpec(
        weights=np.ones(n_obs),
        strata=np.repeat(np.arange(4), 10),
        psu=np.repeat(np.arange(8), 5),
        provenance="calibrated/raked",
    )
    calibrated = diagnose_weight_regime(
        calibrated_design,
        estimand="ate",
        treatment=treatment,
        propensity=propensity,
    )
    assert calibrated.weight_regime == "calibrated_only"
    assert calibrated.claim_level == "design_dr_consistent_only"

    unsafe_design = SurveyDesignSpec(
        weights=np.ones(n_obs),
        strata=np.repeat(np.arange(4), 10),
        psu=np.repeat(np.arange(8), 5),
        provenance="base",
    )
    unsafe = diagnose_weight_regime(
        unsafe_design,
        sampling_spec=SamplingModelSpec(informative_sampling_suspected=True),
        estimand="ate",
        treatment=treatment,
        propensity=propensity,
    )
    assert unsafe.weight_regime == "informative_or_unsafe"
    assert unsafe.claim_level == "selection_model_required"


def test_psu_stratified_cross_fit_schedule_keeps_clusters_intact_and_reports_small_strata() -> None:
    strata = np.array([0, 0, 0, 0, 1, 1, 1, 1, 2, 2])
    psu = np.array([10, 10, 11, 11, 20, 20, 21, 21, 30, 30])

    schedule = build_psu_stratified_cross_fit_schedule(strata, psu, n_folds=3, seed=7)

    for cluster in np.unique(psu):
        cluster_folds = np.unique(schedule.fold_ids[psu == cluster])
        assert cluster_folds.size == 1

    assert schedule.unit_of_independence == "psu_within_strata"
    assert schedule.fallback_used == "single_psu_strata"
    assert any(warning == "single_psu_stratum=2" for warning in schedule.warnings)


def _survey_dgp(n_obs: int = 80, seed: int = 3) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n_obs, 2))
    propensity = 1.0 / (1.0 + np.exp(-(0.5 * x[:, 0] - 0.25 * x[:, 1])))
    treatment = rng.binomial(1, propensity).astype(float)
    y = 1.0 + 1.5 * treatment + 0.8 * x[:, 0] - 0.3 * x[:, 1] + rng.normal(scale=0.2, size=n_obs)
    return {
        "X": x,
        "Y": y,
        "treatment": treatment,
        "weights": np.linspace(0.8, 1.2, n_obs),
        "strata": np.repeat(np.arange(4), n_obs // 4),
        "psu": np.repeat(np.arange(8), n_obs // 8),
        "subgroup": (x[:, 0] > 0.0).astype(int),
    }


def test_survey_semiparametric_ate_method_returns_full_result_contract() -> None:
    state = _survey_dgp()

    result = SurveySemiparametricATEEstimator.pure_step(
        state,
        {
            "crossfit_folds": 4,
            "seed": 7,
            "variance_method": "binder",
            "augmentation_mode": "mean",
        },
    )["result"]

    assert np.isfinite(result["estimate"])
    assert result["estimand_label"] == "ate"
    assert "claim_level" in result
    assert "influence_values_unit" in result
    assert result["variance_method"] == "binder"


def test_survey_semiparametric_att_method_returns_finite_estimate() -> None:
    state = _survey_dgp(seed=9)

    result = SurveySemiparametricATTEstimator.pure_step(
        state,
        {
            "crossfit_folds": 4,
            "seed": 11,
            "augmentation_mode": "mean",
        },
    )["result"]

    assert np.isfinite(result["estimate"])
    assert result["estimand_label"] == "att"
    assert result["effective_n"] > 0.0


def test_survey_semiparametric_subgroup_mean_method_targets_requested_group() -> None:
    state = _survey_dgp(seed=15)

    result = SurveySemiparametricSubgroupMeanEstimator.pure_step(
        state,
        {
            "crossfit_folds": 4,
            "seed": 5,
            "target_group": 1,
            "target_treatment": 1,
            "augmentation_mode": "mean",
        },
    )["result"]

    assert np.isfinite(result["estimate"])
    assert result["estimand_label"] == "subgroup_mean[a=1,b=1]"
    assert result["weight_regime"] in {"full_design", "calibrated_only", "informative_or_unsafe"}
