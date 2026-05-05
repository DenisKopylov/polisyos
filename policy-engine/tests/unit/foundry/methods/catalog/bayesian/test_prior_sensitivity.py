from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.bayesian.prior_sensitivity import (
    BayesianPolicyModelFamily,
    DataConditioningMode,
    PriorSensitivityReport,
    PriorSensitivityStatus,
    ReadinessTier,
    assemble_prior_sensitivity_report,
    build_admissible_prior_class,
    build_sensitivity_record_from_intervals,
    calibrate_composite_prior_class,
    prior_predictive_rank_test,
    simulate_bart_prior_predictive,
    simulate_var_prior_predictive,
)
from polisyos.foundry.methods.catalog.bayesian.protocols import PosteriorResult
from polisyos.foundry.methods.catalog.bayesian.regression import BayesianLinearRegressionEstimator
from polisyos.foundry.methods.catalog.ml.protocols import TabularData


def test_posterior_result_exposes_default_prior_sensitivity_contract() -> None:
    posterior = PosteriorResult(method_name="bayesian_linear_regression")

    assert posterior.prior_sensitivity.status is PriorSensitivityStatus.NOT_RUN
    assert posterior.prior_sensitivity.model_family is BayesianPolicyModelFamily.LINEAR
    assert posterior.prior_sensitivity.version == "1.0"


def test_outcome_conditioned_prior_without_calibration_fails_closed() -> None:
    report = PriorSensitivityReport(
        status="pass",
        readiness_tier_requested="tier_2",
        readiness_tier_achieved="tier_2",
        model_family="bart",
        selected_prior_id="bart_response_range_default",
        admissible_prior_class_id="bart_sum_of_trees_policy_v1",
        uses_outcome_to_set_prior=True,
        data_conditioning_mode="none",
    )

    assert report.status is PriorSensitivityStatus.FAIL
    assert report.data_conditioning_mode is DataConditioningMode.INVALID
    assert (
        "outcome_used_to_set_prior_without_split_or_full_procedure_calibration"
        in report.failure_reasons
    )


def test_prior_predictive_rank_test_rejects_extreme_history() -> None:
    rng = np.random.default_rng(15)
    simulations = rng.normal(size=(99, 24))
    observed = np.full(24, 100.0)

    check = prior_predictive_rank_test(
        observed,
        simulations,
        alpha=0.05,
        model_family=BayesianPolicyModelFamily.LINEAR,
    )

    assert check.status is PriorSensitivityStatus.FAIL
    assert check.p_value is not None
    assert check.p_value <= 0.05
    assert check.n_simulations == 99
    assert check.diagnostics


def test_admissible_prior_library_rejects_logistic_prior_without_baseline() -> None:
    record = build_admissible_prior_class(BayesianPolicyModelFamily.LOGISTIC)

    failures = {constraint.name for constraint in record.constraints if not constraint.passed}
    assert "baseline_aware_intercept" in failures


def test_sensitivity_curve_reports_width_factor_and_tier_failure() -> None:
    admissible = build_admissible_prior_class(
        BayesianPolicyModelFamily.LINEAR,
        hyperparameters={"prior_scale": 1.0, "sigma_scale": 1.0, "nu_beta": 10.0},
    )
    check = prior_predictive_rank_test(
        np.array([0.0, 0.1, -0.1, 0.2]),
        np.array([[0.0, 0.1, -0.1, 0.2], [0.1, 0.0, -0.2, 0.3]]),
        alpha=0.01,
        model_family=BayesianPolicyModelFamily.LINEAR,
    )
    sensitivity = build_sensitivity_record_from_intervals(
        estimand_id="ate",
        baseline_interval=(-1.0, 1.0),
        perturbation_intervals=[
            {
                "hyperparameter": "prior_scale",
                "multiplier": 0.5,
                "interval": (-0.5, 0.5),
                "half_width": 0.5,
            },
            {
                "hyperparameter": "prior_scale",
                "multiplier": 2.0,
                "interval": (-2.0, 2.0),
                "half_width": 2.0,
            },
        ],
        credible_interval_level=0.95,
    )
    report = assemble_prior_sensitivity_report(
        model_family=BayesianPolicyModelFamily.LINEAR,
        selected_prior_id="linear_normal_logsigma_prior_v1",
        admissible_prior_class=admissible,
        prior_predictive_check=check,
        sensitivity=sensitivity,
        readiness_tier_requested=ReadinessTier.TIER_1,
    )

    assert sensitivity.width_factor == 4.0
    assert sensitivity.elasticities["prior_scale"] == 1.0
    assert report.status is PriorSensitivityStatus.FAIL
    assert "credible_interval_width_factor_exceeds_tier_threshold" in report.failure_reasons
    assert "pass" in report.model_dump(mode="json")["sensitivity"]
    assert "pass_" not in report.model_dump(mode="json")["sensitivity"]


def test_composite_prior_class_bonferroni_gate_records_p_min() -> None:
    calibration = calibrate_composite_prior_class(
        {"eta_0": 0.04, "eta_half": 0.03, "eta_double": 0.20},
        alpha=0.05,
        method="bonferroni",
    )

    assert calibration.status is PriorSensitivityStatus.PASS
    assert calibration.p_min == 0.03
    assert calibration.calibrated_cutoff == 0.05 / 3
    assert calibration.class_adjusted_pass is True


def test_bart_outcome_conditioned_prior_class_requires_calibration_mode() -> None:
    rng = np.random.default_rng(91)
    x = rng.normal(size=(18, 2))
    simulations, summary = simulate_bart_prior_predictive(
        x,
        num_trees=8,
        n_simulations=16,
        rng=rng,
    )
    record = build_admissible_prior_class(
        "bart",
        hyperparameters={
            **summary,
            "uses_outcome_to_set_prior": True,
            "data_conditioning_mode": "none",
        },
        prior_predictive_simulations=simulations,
    )

    failures = {constraint.name for constraint in record.constraints if not constraint.passed}
    assert "no_prohibited_outcome_leakage_in_hyperparameters" in failures


def test_var_prior_predictive_simulator_feeds_forecast_envelope_constraint() -> None:
    rng = np.random.default_rng(92)
    simulations, summary = simulate_var_prior_predictive(
        np.array([0.0, 0.1]),
        n_lags=2,
        horizon=8,
        tightness=0.1,
        n_simulations=64,
        rng=rng,
    )
    record = build_admissible_prior_class(
        "var",
        hyperparameters={"lambda": 0.1, "lag_decay": 1.0, **summary},
        policy_context={"forecast_growth_bound": 10.0},
        prior_predictive_simulations=simulations,
    )

    assert record.passed
    assert any(constraint.name == "forecast_growth_envelope" for constraint in record.constraints)


def test_linear_estimator_attaches_executed_prior_sensitivity_gate() -> None:
    rng = np.random.default_rng(42)
    x = rng.normal(size=(36, 2))
    y = 0.4 + 0.7 * x[:, 0] + rng.normal(scale=0.35, size=36)
    state = TabularData(features=x, target=y, feature_names=["x0", "x1"])

    result = BayesianLinearRegressionEstimator.pure_step(
        state,
        {
            "num_warmup": 32,
            "num_samples": 32,
            "num_chains": 1,
            "prior_predictive_simulations": 32,
            "proposal_scale": 0.04,
            "__seed__": 12,
        },
    )

    posterior = result["result"]
    assert isinstance(posterior, PosteriorResult)
    assert posterior.prior_sensitivity.status is not PriorSensitivityStatus.NOT_RUN
    assert posterior.prior_sensitivity.prior_predictive_check is not None
    assert posterior.prior_sensitivity.sensitivity is not None
    assert len(posterior.prior_sensitivity.sensitivity_by_estimand) >= 2
