from __future__ import annotations

import numpy as np
import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.microsim import (
    DynamicMicrosimEstimator,
    DynamicMicrosimResult,
    DynamicMicrosimResultV2,
    DynamicValidationSensitivitySpec,
    DynamicValidationSpec,
    SurveyMicroData,
    ValidationMomentSpec,
    attach_dynamic_validation,
    ensure_microsim_methods_registered,
    run_dynamic_validation,
    upgrade_dynamic_microsim_result,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.phase4_dynamics import (
    DynamicMicrosimValidationReport,
    load_dynamic_microsim_validation_report,
    persist_dynamic_microsim_validation_report,
)


def _survey_state() -> SurveyMicroData:
    rng = np.random.default_rng(141)
    return SurveyMicroData(
        market_income=np.array([4000.0, 12000.0, 22000.0, 40000.0, 55000.0]),
        weights=np.array([1.0, 1.5, 1.1, 0.9, 0.7]),
        features=rng.normal(size=(5, 3)),
        household_ids=np.arange(5),
    )


def _mnar_survey_state() -> SurveyMicroData:
    return SurveyMicroData(
        market_income=np.array(
            [22.0, 28.0, 35.0, 41.0, 47.0, 55.0, 68.0, 80.0, np.nan, np.nan, np.nan, np.nan]
        ),
        weights=np.ones(12, dtype=float),
        household_ids=np.arange(12),
    )


def test_tax_behavior_imputation_and_dynamic_microsim_run() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    survey = _survey_state()

    tax_cls = registry.get("microsim.policy.tax_benefit_calculator@1.0.0")
    tax_result = dispatcher.dispatch(
        method_class=tax_cls,
        signature=tax_cls.signature,
        state=survey,
        params={},
        seed=143,
    )
    assert tax_result.output["result"].weighted_mean_disposable_income > 0.0

    behavior_cls = registry.get("microsim.behavior.behavioral_response@1.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": survey.market_income,
            "weights": survey.weights,
            "effective_tax_rate": tax_result.output["effective_tax_rate"],
        },
        params={"elasticity": 0.15},
        seed=145,
    )
    assert behavior_result.output["result"].elasticity == 0.15

    imputation_cls = registry.get("microsim.imputation.imputation_model@1.0.0")
    imputation_result = dispatcher.dispatch(
        method_class=imputation_cls,
        signature=imputation_cls.signature,
        state={
            "market_income": np.array([4000.0, np.nan, 22000.0, np.nan, 55000.0]),
            "features": survey.features,
            "weights": survey.weights,
        },
        params={"n_estimators": 50},
        seed=147,
    )
    assert np.isfinite(np.asarray(imputation_result.output["market_income"], dtype=float)).all()

    dynamic_cls = registry.get("microsim.dynamic.dynamic_microsim@1.0.0")
    dynamic_result = dispatcher.dispatch(
        method_class=dynamic_cls,
        signature=dynamic_cls.signature,
        state=survey,
        params={"n_periods": 4, "store_market_income_path": True},
        seed=149,
    )
    assert isinstance(dynamic_result.output["result"], DynamicMicrosimResultV2)
    assert dynamic_result.output["result"].contract_id == "foundry.microsim.dynamic_result.v2"
    assert dynamic_result.output["result"].weighted_mean_final_income > 0.0
    assert np.asarray(dynamic_result.output["result"].market_income_path).shape == (4, 5)
    assert dynamic_result.output["uncertainty_envelope"] is not None


def test_dynamic_microsim_validation_diagnostic_and_v1_adapter() -> None:
    v1_result = DynamicMicrosimResult(
        final_market_income=np.array([110.0, 220.0]),
        disposable_income=np.array([100.0, 200.0]),
        mean_income_path=[150.0, 165.0],
        policy_revenue_path=[5.0, 7.0],
        weighted_mean_final_income=165.0,
        metadata={"horizon": 2},
    )
    result = upgrade_dynamic_microsim_result(
        v1_result,
        market_income_path=np.array([[100.0, 200.0], [110.0, 220.0]]),
        weights=np.array([1.0, 1.0]),
    )

    spec = DynamicValidationSpec(
        comparison_dataset="unit_panel",
        comparison_dataset_version="fixture",
        direct_support_max_horizon=1,
        horizons=(1, 2),
        moment_specs=(
            ValidationMomentSpec(
                moment_id="mean_income",
                family="level",
                scale="raw",
                unit="currency",
                tolerance_rel=0.20,
                primary=True,
            ),
        ),
        bootstrap_reps=16,
        bootstrap_seed=11,
    )
    panel_moments = {
        "observed_moments": [
            {
                "cohort_key": {"all": "all"},
                "horizon_years": 1,
                "moment_id": "mean_income",
                "support_type": "direct",
                "observed_value": 145.0,
                "se": 20.0,
                "n": 2,
                "ess": 2.0,
            },
            {
                "cohort_key": {"all": "all"},
                "horizon_years": 2,
                "moment_id": "mean_income",
                "support_type": "extrapolated",
                "observed_value": 160.0,
                "se": 20.0,
                "n": 2,
                "ess": 2.0,
            },
        ]
    }

    diagnostic = run_dynamic_validation(result, panel_moments, spec)

    assert diagnostic.status == "warn"
    assert diagnostic.horizons_reported == [1, 2]
    assert len(diagnostic.cell_results) == 2
    assert diagnostic.cell_results[0].bias == 5.0
    assert diagnostic.omnibus_tests
    assert diagnostic.bias_envelopes[0].target_moment_id == "mean_income"
    assert "some_horizons_are_extrapolated_beyond_direct_panel_support" in diagnostic.warnings

    attached = attach_dynamic_validation(result, panel_moments, spec)
    envelope = attached.to_uncertainty_envelope()
    assert attached.validation_diagnostic == diagnostic
    assert envelope.confidence_level == 0.95
    assert envelope.confidence_interval[0] < envelope.point_estimate
    assert envelope.confidence_interval[1] > envelope.point_estimate


def test_dynamic_microsim_refuses_red_phase4_validation_report() -> None:
    survey = SurveyMicroData(
        market_income=np.array([100.0, 120.0, 140.0]),
        weights=np.ones(3),
    )
    red_report = DynamicMicrosimValidationReport(
        validation_status="red",
        source_status="fail",
        can_run_dynamic_microsim=False,
        refusal_code="dynamic_microsim_validation_red",
        blocking_reasons=("dynamic_microsim_validation_red",),
    )

    with pytest.raises(ValueError, match="dynamic_microsim_validation_red"):
        DynamicMicrosimEstimator.pure_step(
            survey,
            {
                "horizon": 2,
                "dynamic_validation_report": red_report.model_dump(mode="json"),
            },
        )


def test_dynamic_microsim_persists_generated_phase4_validation_report(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    survey = _survey_state()
    weighted_mean = float(np.average(survey.market_income, weights=survey.weights))
    spec = DynamicValidationSpec(
        comparison_dataset="green_panel",
        comparison_dataset_version="fixture",
        direct_support_max_horizon=2,
        horizons=(1, 2),
        moment_specs=(
            ValidationMomentSpec(
                moment_id="mean_income",
                family="level",
                scale="raw",
                unit="currency",
                tolerance_rel=1.0,
                primary=True,
            ),
        ),
        bootstrap_reps=8,
        bootstrap_seed=11,
    )
    panel_moments = {
        "observed_moments": [
            {
                "cohort_key": {"all": "all"},
                "horizon_years": 1,
                "moment_id": "mean_income",
                "support_type": "direct",
                "observed_value": weighted_mean,
                "se": 10.0,
                "n": int(survey.market_income.size),
                "ess": float(np.sum(survey.weights)),
            },
            {
                "cohort_key": {"all": "all"},
                "horizon_years": 2,
                "moment_id": "mean_income",
                "support_type": "direct",
                "observed_value": weighted_mean,
                "se": 10.0,
                "n": int(survey.market_income.size),
                "ess": float(np.sum(survey.weights)),
            },
        ]
    }

    result = DynamicMicrosimEstimator.pure_step(
        survey,
        {
            "n_periods": 2,
            "drift": 0.0,
            "volatility": 0.0,
            "artifact_store": store,
            "validation_panel_data": panel_moments,
            "validation_spec": spec,
        },
    )["result"]

    assert result.dynamic_validation_report_ref is not None
    loaded = load_dynamic_microsim_validation_report(store, result.dynamic_validation_report_ref)
    assert loaded.validation_status in {"green", "amber"}
    assert result.metadata["dynamic_validation_status"] == loaded.validation_status


def test_dynamic_microsim_persists_supplied_amber_report_with_warning(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = DynamicMicrosimValidationReport(
        validation_status="amber",
        source_status="warn",
        can_run_dynamic_microsim=True,
        warnings=("longitudinal_panel_support_partial",),
    )

    result = DynamicMicrosimEstimator.pure_step(
        _survey_state(),
        {
            "n_periods": 2,
            "artifact_store": store,
            "dynamic_validation_report": report.model_dump(mode="json"),
        },
    )["result"]

    assert result.dynamic_validation_report_ref is not None
    loaded = load_dynamic_microsim_validation_report(store, result.dynamic_validation_report_ref)
    assert loaded.validation_status == "amber"
    assert result.metadata["dynamic_validation_status"] == "amber"
    assert result.metadata["dynamic_validation_warning_count"] == 1


def test_dynamic_microsim_refuses_red_phase4_validation_report_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    red_report = DynamicMicrosimValidationReport(
        validation_status="red",
        source_status="fail",
        can_run_dynamic_microsim=False,
        refusal_code="dynamic_microsim_validation_red",
        blocking_reasons=("dynamic_microsim_validation_red",),
    )
    report_ref = persist_dynamic_microsim_validation_report(store, red_report)

    with pytest.raises(ValueError, match="dynamic_microsim_validation_red"):
        DynamicMicrosimEstimator.pure_step(
            _survey_state(),
            {
                "n_periods": 2,
                "artifact_store": store,
                "dynamic_validation_report_ref": report_ref,
            },
        )


def test_dynamic_validation_uses_cohort_paths_core_moments_and_sensitivity() -> None:
    cohort_id = np.array(["young", "young", "senior", "senior"])
    weights = np.array([1.0, 1.3, 0.9, 1.1])
    observed_path = np.array(
        [
            [100.0, 120.0, 210.0, 240.0],
            [106.0, 126.0, 214.0, 246.0],
            [111.0, 132.0, 219.0, 252.0],
            [116.0, 137.0, 224.0, 258.0],
            [121.0, 143.0, 229.0, 264.0],
            [126.0, 149.0, 235.0, 271.0],
        ],
        dtype=float,
    )
    simulated_path = observed_path * np.array([[1.0], [1.01], [1.015], [1.018], [1.02], [1.022]])
    result = DynamicMicrosimResultV2(
        final_market_income=simulated_path[-1],
        disposable_income=simulated_path[-1],
        mean_income_path=[float(np.average(row, weights=weights)) for row in simulated_path],
        policy_revenue_path=[0.0] * simulated_path.shape[0],
        weighted_mean_final_income=float(np.average(simulated_path[-1], weights=weights)),
        market_income_path=simulated_path,
        weights=weights,
        cohort_data={"cohort_id": cohort_id},
    )

    spec = DynamicValidationSpec(
        comparison_dataset="panel_fixture",
        cohort_dimensions=("cohort_id",),
        direct_support_max_horizon=6,
        horizons=(2, 6),
        moment_specs=(
            ValidationMomentSpec(
                moment_id="mean_log_income",
                family="level",
                scale="log",
                unit="log_currency",
                tolerance_abs=0.05,
                primary=True,
            ),
            ValidationMomentSpec(
                moment_id="autocovariance_1y_log_income",
                family="persistence",
                scale="log",
                unit="log_currency_sq",
                primary=True,
            ),
            ValidationMomentSpec(
                moment_id="rank_rank_persistence",
                family="mobility",
                scale="relative",
                unit="correlation",
                primary=True,
            ),
            ValidationMomentSpec(
                moment_id="lifetime_discounted_income",
                family="lifetime",
                scale="raw",
                unit="currency_present_value",
                tolerance_rel=0.10,
                primary=True,
            ),
        ),
        bootstrap_reps=24,
        bootstrap_seed=17,
        multiple_testing_correction="holm_stepdown",
        max_abs_relative_bias_warn=0.50,
        max_abs_relative_bias_fail=0.90,
        sensitivity_scenarios=(
            DynamicValidationSensitivitySpec(
                scenario_id="strict_bias_gate",
                changed_inputs={
                    "max_abs_relative_bias_warn": 0.0001,
                    "max_abs_relative_bias_fail": 0.0002,
                },
            ),
        ),
        metadata={"lifetime_discount_factor": 0.98},
    )

    diagnostic = run_dynamic_validation(
        result,
        {
            "observed_income_path": observed_path,
            "weights": weights,
            "cohort_data": {"cohort_id": cohort_id},
        },
        spec,
    )

    assert diagnostic.status == "pass"
    assert diagnostic.cohort_dimensions == ("cohort_id",)
    assert {cell.cohort_key["cohort_id"] for cell in diagnostic.cell_results} == {
        "young",
        "senior",
    }
    assert "rank_rank_persistence" in {cell.moment_id for cell in diagnostic.cell_results}
    assert all(
        cell.p_value_adjusted is not None
        for cell in diagnostic.cell_results
        if cell.p_value is not None
    )
    assert {"wald", "hansen_j_type"}.issubset({test.method for test in diagnostic.omnibus_tests})
    assert diagnostic.bias_envelopes
    assert diagnostic.bias_envelopes[0].simultaneous is True
    assert diagnostic.diagnostics["multiple_testing_correction"] == "holm_stepdown"
    assert diagnostic.sensitivity_runs[0].scenario_id == "strict_bias_gate"
    assert diagnostic.sensitivity_runs[0].status == "fail"

    long_panel_diagnostic = run_dynamic_validation(
        result,
        {
            "person_id": np.tile(np.arange(observed_path.shape[1]), observed_path.shape[0]),
            "year": np.repeat(np.arange(1, observed_path.shape[0] + 1), observed_path.shape[1]),
            "income": observed_path.reshape(-1),
            "weights": np.tile(weights, observed_path.shape[0]),
            "cohort_data": {"cohort_id": np.tile(cohort_id, observed_path.shape[0])},
        },
        spec.model_copy(update={"sensitivity_scenarios": ()}),
    )
    assert long_panel_diagnostic.status == "pass"
    assert len(long_panel_diagnostic.cell_results) == len(diagnostic.cell_results)


def test_behavioral_response_v2_blocks_unidentified_cross_section() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    survey = _survey_state()

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": survey.market_income,
            "weights": survey.weights,
            "effective_tax_rate": np.array([0.05, 0.09, 0.12, 0.18, 0.23]),
            "features": survey.features,
        },
        params={"minimum_effective_sample_size": 1.0},
        seed=211,
    )

    result = behavior_result.output["result"]
    assert result.identified_object == "not_identified"
    assert result.identifiability_status == "non_identified"
    np.testing.assert_allclose(
        np.asarray(behavior_result.output["market_income"], dtype=float), survey.market_income
    )


def test_behavioral_response_v2_supports_manual_override() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    survey = _survey_state()

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": survey.market_income,
            "weights": survey.weights,
            "effective_tax_rate": np.array([0.05, 0.09, 0.12, 0.18, 0.23]),
        },
        params={"manual_elasticity": 0.15},
        seed=223,
    )

    result = behavior_result.output["result"]
    assert result.identified_object == "manual_override_required"
    assert result.elasticity_mean == 0.15
    assert not np.allclose(
        np.asarray(behavior_result.output["market_income"], dtype=float), survey.market_income
    )


def test_behavioral_response_v2_estimates_panel_average_partial_effect() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    household_ids = np.repeat(np.arange(4), 3)
    period_id = np.tile(np.arange(3), 4)
    net_rate = np.array(
        [
            0.55,
            0.60,
            0.65,
            0.58,
            0.62,
            0.68,
            0.61,
            0.66,
            0.70,
            0.64,
            0.69,
            0.74,
        ],
        dtype=float,
    )
    base_income = np.repeat(np.array([18000.0, 22000.0, 26000.0, 32000.0]), 3)
    market_income = base_income * np.power(net_rate, 0.5)
    weights = np.ones_like(market_income)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "household_ids": household_ids,
            "period_id": period_id,
        },
        params={
            "minimum_effective_sample_size": 1.0,
            "panel_min_periods": 3,
            "variation_floor": 1e-8,
        },
        seed=227,
    )

    result = behavior_result.output["result"]
    assert result.regime == "panel"
    assert result.identified_object == "conditional_mean_eta"
    assert result.identifiability_status in {"identified", "sloppy"}
    assert result.elasticity_mean is not None
    assert abs(result.elasticity_mean - 0.5) < 1e-6


def test_behavioral_response_v2_uses_iv_proxy_when_instrument_is_strong() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    n_obs = 40
    z = np.repeat(np.array([0.0, 1.0]), n_obs // 2)
    feature = np.tile(np.linspace(0.0, 1.0, n_obs // 2), 2)
    net_rate = 0.5 + 0.03 * z + 0.1 * feature
    market_income = 12000.0 * np.exp(0.2 * feature) * np.power(net_rate, 0.4)
    weights = np.ones(n_obs, dtype=float)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "instrument_z": z,
            "features": feature[:, None],
        },
        params={
            "minimum_effective_sample_size": 1.0,
            "minimum_first_stage_strength": 1.0,
            "minimum_overlap_score": 0.05,
            "variation_floor": 1e-8,
            "max_control_features": 1,
        },
        seed=229,
    )

    result = behavior_result.output["result"]
    assert result.regime == "cross_section"
    assert result.identified_object == "conditional_mean_eta"
    assert result.elasticity_mean is not None
    assert abs(result.elasticity_mean - 0.4) < 0.05
    assert result.first_stage_strength is not None


def test_behavioral_response_v2_supports_matrix_instruments() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    n_obs = 80
    z_binary = np.repeat(np.array([0.0, 1.0]), n_obs // 2)
    z_continuous = np.tile(np.linspace(-1.0, 1.0, n_obs // 2), 2)
    feature = np.tile(np.linspace(-0.8, 0.8, n_obs // 2), 2)
    net_rate = 0.56 + 0.015 * z_binary + 0.03 * z_continuous + 0.04 * feature
    true_eta = 0.35 + 0.08 * feature
    market_income = 15000.0 * np.exp(0.1 * feature) * np.power(net_rate, true_eta)
    weights = np.ones(n_obs, dtype=float)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "instrument_z": np.column_stack([z_binary, z_continuous]),
            "features": feature[:, None],
        },
        params={
            "minimum_effective_sample_size": 1.0,
            "minimum_first_stage_strength": 1.0,
            "minimum_overlap_score": 0.02,
            "variation_floor": 1e-8,
            "max_control_features": 1,
        },
        seed=231,
    )

    result = behavior_result.output["result"]
    assert result.identified_object in {"conditional_mean_eta", "bounds_only"}
    assert result.elasticity_mean is not None
    assert result.first_stage_strength is not None and result.first_stage_strength > 1.0
    assert result.overlap_score is not None


def test_behavioral_response_v2_recovers_conditional_mean_elasticity_under_exogeneity() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    feature = np.repeat(np.linspace(-1.0, 1.0, 20), 4)
    price_component = np.tile(np.linspace(-0.15, 0.15, 4), 20)
    net_rate = 0.6 + price_component
    true_eta = 0.25 + 0.12 * feature
    market_income = 10000.0 * np.exp(0.15 * feature) * np.power(net_rate, true_eta)
    weights = np.ones_like(market_income)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "features": feature[:, None],
            "feature_names": ["skill_index"],
        },
        params={
            "assume_exogenous_price": True,
            "minimum_effective_sample_size": 1.0,
            "variation_floor": 1e-8,
            "max_control_features": 1,
        },
        seed=233,
    )

    result = behavior_result.output["result"]
    eta_hat = np.asarray(result.elasticity_by_obs, dtype=float)
    assert result.identified_object == "conditional_mean_eta"
    assert eta_hat.shape == true_eta.shape
    assert abs(result.elasticity_mean - float(np.mean(true_eta))) < 1e-3
    assert float(np.corrcoef(eta_hat, true_eta)[0, 1]) > 0.99
    assert "skill_index:low_mean" in result.elasticity_grid


def test_behavioral_response_v2_uses_grouping_iv_for_repeated_cross_sections() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    cohort_id = np.repeat(np.array(["young", "old"]), 60)
    period_id = np.tile(np.repeat(np.arange(4), 15), 2)
    reform = np.tile(np.linspace(0.0, 1.0, 60), 2)
    z = np.where(cohort_id == "young", 1.0, 0.4) + 0.5 * reform
    beta = np.where(cohort_id == "young", 0.45, 0.25)
    net_rate = 0.50 + 0.04 * z + 0.02 * reform
    baseline_income = np.where(cohort_id == "young", 18000.0, 24000.0) * np.exp(0.05 * reform)
    market_income = baseline_income * np.power(net_rate, beta)
    weights = np.ones_like(market_income)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "cohort_id": cohort_id,
            "period_id": period_id,
            "instrument_z": z,
        },
        params={
            "minimum_effective_sample_size": 1.0,
            "minimum_first_stage_strength": 1.0,
            "minimum_overlap_score": 0.05,
            "repeated_cross_section_min_periods": 3,
            "minimum_cohort_cell_size": 10,
            "variation_floor": 1e-8,
        },
        seed=237,
    )

    result = behavior_result.output["result"]
    assert result.regime == "repeated_cross_section"
    assert result.identified_object == "conditional_mean_eta"
    assert result.elasticity_mean is not None
    assert np.isfinite(result.elasticity_mean)
    assert result.elasticity_by_obs is None
    assert result.diagnostics["estimation_mode"] == "pseudo_panel_iv"


def test_behavioral_response_v2_returns_bounds_only_when_iv_overlap_is_missing() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    n_obs = 60
    z = np.repeat(np.array([0.0, 1.0]), n_obs // 2)
    feature = np.tile(np.linspace(-0.5, 0.5, n_obs // 2), 2)
    net_rate = np.where(z < 0.5, 0.42 + 0.02 * (feature + 0.5), 0.72 + 0.02 * (feature + 0.5))
    market_income = 14000.0 * np.exp(0.1 * feature) * np.power(net_rate, 0.2 + 0.1 * z)
    weights = np.ones(n_obs, dtype=float)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "instrument_z": z,
            "features": feature[:, None],
        },
        params={
            "minimum_effective_sample_size": 1.0,
            "minimum_first_stage_strength": 1.0,
            "minimum_overlap_score": 0.5,
            "variation_floor": 1e-8,
            "max_control_features": 1,
        },
        seed=239,
    )

    result = behavior_result.output["result"]
    assert result.identified_object == "bounds_only"
    assert result.elasticity_lower is not None
    assert result.elasticity_upper is not None
    assert result.elasticity_grid is not None
    assert (
        result.elasticity_grid["weighted_mean_income_lower"]
        <= result.elasticity_grid["weighted_mean_income_upper"]
    )
    assert result.overlap_score is not None and result.overlap_score < 0.5


def test_behavioral_response_v2_bounds_propagate_to_uncertainty_envelope() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    n_obs = 60
    z = np.repeat(np.array([0.0, 1.0]), n_obs // 2)
    feature = np.tile(np.linspace(-0.5, 0.5, n_obs // 2), 2)
    net_rate = np.where(z < 0.5, 0.42 + 0.02 * (feature + 0.5), 0.72 + 0.02 * (feature + 0.5))
    market_income = 14000.0 * np.exp(0.1 * feature) * np.power(net_rate, 0.2 + 0.1 * z)
    weights = np.ones(n_obs, dtype=float)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "instrument_z": z,
            "features": feature[:, None],
        },
        params={
            "minimum_effective_sample_size": 1.0,
            "minimum_first_stage_strength": 1.0,
            "minimum_overlap_score": 0.5,
            "variation_floor": 1e-8,
            "max_control_features": 1,
        },
        seed=240,
    )

    result = behavior_result.output["result"]
    envelope = behavior_result.output["uncertainty_envelope"]
    assert result.identified_object == "bounds_only"
    assert envelope.confidence_interval[0] == result.elasticity_grid["weighted_mean_income_lower"]
    assert envelope.confidence_interval[1] == result.elasticity_grid["weighted_mean_income_upper"]


def test_behavioral_response_v2_uses_local_kink_fallback() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    market_income = np.array([45.0, 46.0, 47.0, 48.0, 49.0, 51.0, 52.0, 53.0, 54.0, 55.0])
    net_rate = np.array([0.60, 0.60, 0.60, 0.60, 0.60, 0.72, 0.72, 0.72, 0.72, 0.72])
    weights = np.ones_like(market_income)

    behavior_cls = registry.get("microsim.behavior.behavioral_response@2.0.0")
    behavior_result = dispatcher.dispatch(
        method_class=behavior_cls,
        signature=behavior_cls.signature,
        state={
            "market_income": market_income,
            "weights": weights,
            "effective_tax_rate": 1.0 - net_rate,
            "kink_points": np.array([50.0]),
        },
        params={
            "local_kink_bandwidth": 6.0,
            "local_kink_min_side_obs": 2,
        },
        seed=241,
    )

    result = behavior_result.output["result"]
    assert result.identified_object == "local_average_eta"
    assert result.elasticity_mean is not None
    assert result.elasticity_lower is not None
    assert result.elasticity_upper is not None
    assert "local_kink_estimates" in result.diagnostics


def test_mnar_income_bounds_support_only_matches_manski_interval() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("microsim.imputation.mnar_income_bounds@1.0.0")
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_mnar_survey_state(),
        params={
            "mechanism_class": "support_only",
            "support_lower": 0.0,
            "support_upper": 120.0,
        },
        seed=311,
    )

    result = dispatched.output["result"]
    payload = result.metadata["mnar_bounds"]
    np.testing.assert_allclose(payload["bounds"]["lower"], 31.333333333333332)
    np.testing.assert_allclose(payload["bounds"]["upper"], 71.33333333333333)
    assert payload["assumption_vector"]["mechanism_class"] == "support_only"
    assert (
        dispatched.output["uncertainty_envelope"].interval_semantics.value == "deterministic_bounds"
    )


def test_mnar_income_bounds_pattern_mixture_matches_closed_form_rectangle() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("microsim.imputation.mnar_income_bounds@1.0.0")
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_mnar_survey_state(),
        params={
            "mechanism_class": "pattern_mixture.locscale",
            "support_lower": 0.0,
            "support_upper": 120.0,
            "delta_range": [-10.0, 10.0],
            "lambda_range": [0.9, 1.1],
            "reference_delta": 0.0,
            "reference_lambda": 1.0,
            "n_delta_points": 3,
            "n_lambda_points": 3,
        },
        seed=313,
    )

    payload = dispatched.output["result"].metadata["mnar_bounds"]
    np.testing.assert_allclose(payload["bounds"]["lower"], 42.1, atol=1e-9)
    np.testing.assert_allclose(payload["bounds"]["upper"], 51.9, atol=1e-9)
    np.testing.assert_allclose(payload["bounds"]["reference_value"], 47.0, atol=1e-9)
    assert payload["bounds"]["grid_argmin"] == {"delta": -10.0, "lambda": 0.9}
    assert payload["bounds"]["grid_argmax"] == {"delta": 10.0, "lambda": 1.1}


def test_mnar_income_bounds_selection_logit_records_monotone_curve() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("microsim.imputation.mnar_income_bounds@1.0.0")
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_mnar_survey_state(),
        params={
            "mechanism_class": "selection.logit",
            "support_lower": 0.0,
            "support_upper": 120.0,
            "gamma_grid": [-1.0, 0.0, 1.0],
        },
        seed=317,
    )

    payload = dispatched.output["result"].metadata["mnar_bounds"]
    estimates = [point["estimate"] for point in payload["scenario_grid"]]
    assert len(estimates) == 3
    assert estimates[0] > estimates[1] > estimates[2]
    assert (
        payload["bounds"]["lower"]
        <= payload["bounds"]["reference_value"]
        <= payload["bounds"]["upper"]
    )
    assert payload["bounds"]["manski_outer_bound"]["lower"] <= payload["bounds"]["lower"]
    assert payload["bounds"]["upper"] <= payload["bounds"]["manski_outer_bound"]["upper"]
    assert payload["diagnostics"]["selection_curve_monotonicity"] == "nonincreasing"
    assert payload["diagnostics"]["selection_weight_effective_sample_size_min"] is not None


def test_mnar_income_bounds_supports_missingness_type_overrides() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    method_cls = registry.get("microsim.imputation.mnar_income_bounds@1.0.0")
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_mnar_survey_state(),
        params={
            "mechanism_class": "selection.logit",
            "support_lower": 0.0,
            "support_upper": 120.0,
            "missingness_types": ["refusal", "refusal", "dont_know", "dont_know"],
            "gamma_overrides": {
                "refusal": [0.0, 1.0],
                "dont_know": [-1.0, 0.0],
            },
            "reference_gamma_overrides": {
                "refusal": 0.5,
                "dont_know": -0.5,
            },
        },
        seed=319,
    )

    payload = dispatched.output["result"].metadata["mnar_bounds"]
    assert payload["scenario_grid"] == []
    assert (
        "component_specific_parameter_overrides_disable_single_collapsed_scenario_grid"
        in payload["warnings"]
    )
    assert payload["assumption_vector"]["missingness_types"] == ["dont_know", "refusal"]
    assert "mnar.refusal_vs_dk_split" in payload["assumption_vector"]["taxonomy_entries"]


def test_mnar_income_bounds_supports_log_income_target_scale() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    survey = _mnar_survey_state()
    observed = survey.market_income[np.isfinite(survey.market_income)]
    observed_log_mean = float(np.mean(np.log1p(observed)))
    expected_lower = (observed.size / survey.market_income.size) * observed_log_mean
    expected_upper = expected_lower + (1.0 - observed.size / survey.market_income.size) * float(
        np.log1p(120.0)
    )

    method_cls = registry.get("microsim.imputation.mnar_income_bounds@1.0.0")
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=survey,
        params={
            "mechanism_class": "support_only",
            "target_scale": "log_income",
            "support_lower": 0.0,
            "support_upper": 120.0,
        },
        seed=331,
    )

    payload = dispatched.output["result"].metadata["mnar_bounds"]
    np.testing.assert_allclose(payload["bounds"]["lower"], expected_lower)
    np.testing.assert_allclose(payload["bounds"]["upper"], expected_upper)
    assert payload["target"]["scale"] == "log_income"
    assert payload["target"]["back_transform_rule"] == "no_exact_inverse_for_mean_log_income"
    np.testing.assert_allclose(
        payload["assumption_vector"]["support_bounds"][1], float(np.log1p(120.0))
    )


def test_mnar_income_bounds_equivalized_scale_uses_unit_specific_support() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    survey = _mnar_survey_state()
    equivalence_scale = np.array([1.0] * 8 + [2.0] * 4, dtype=float)
    observed_mask = np.isfinite(survey.market_income)
    observed_equivalized = survey.market_income[observed_mask] / equivalence_scale[observed_mask]
    fixed_observed_total = float(np.sum(observed_equivalized) / survey.market_income.size)
    missing_upper_total = float(
        np.sum(120.0 / equivalence_scale[~observed_mask]) / survey.market_income.size
    )

    method_cls = registry.get("microsim.imputation.mnar_income_bounds@1.0.0")
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=survey,
        params={
            "mechanism_class": "support_only",
            "target_scale": "equivalized_income",
            "equivalence_scale": equivalence_scale,
            "support_lower": 0.0,
            "support_upper": 120.0,
        },
        seed=337,
    )

    payload = dispatched.output["result"].metadata["mnar_bounds"]
    np.testing.assert_allclose(payload["bounds"]["lower"], fixed_observed_total)
    np.testing.assert_allclose(
        payload["bounds"]["upper"], fixed_observed_total + missing_upper_total
    )
    assert payload["target"]["scale"] == "equivalized_income"
    assert payload["target"]["equivalence_scale_source"] == "vector_param_or_metadata"
    assert payload["diagnostics"]["notes"]["unit_specific_support"] is True


def test_mnar_income_bounds_pattern_mixture_respects_support_clipping() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_microsim_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    survey = _mnar_survey_state()
    observed = survey.market_income[np.isfinite(survey.market_income)]
    clipped_nonrespondent_mean = float(np.mean(np.clip(observed + 60.0, 0.0, 90.0)))
    expected_total = float(
        (np.sum(observed) + 4.0 * clipped_nonrespondent_mean) / survey.market_income.size
    )

    method_cls = registry.get("microsim.imputation.mnar_income_bounds@1.0.0")
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=survey,
        params={
            "mechanism_class": "pattern_mixture.locscale",
            "support_lower": 0.0,
            "support_upper": 90.0,
            "delta_range": [60.0, 60.0],
            "lambda_range": [1.0, 1.0],
            "reference_delta": 60.0,
            "reference_lambda": 1.0,
        },
        seed=341,
    )

    payload = dispatched.output["result"].metadata["mnar_bounds"]
    np.testing.assert_allclose(payload["bounds"]["lower"], expected_total)
    np.testing.assert_allclose(payload["bounds"]["upper"], expected_total)
    np.testing.assert_allclose(payload["bounds"]["reference_value"], expected_total)
    np.testing.assert_allclose(payload["diagnostics"]["share_clipped_to_support"], 0.75)
    assert payload["assumption_vector"]["taxonomy_entries"] == ["mnar.pattern_mixture.delta"]
