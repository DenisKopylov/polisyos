from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.exceptions import MethodNotFoundError
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_foundry_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_foundry_v2_distributional_and_survey_methods_dispatch() -> None:
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    atkinson_cls = registry.get("distributional.inequality.atkinson@1.0.0")
    atkinson_result = dispatcher.dispatch(
        method_class=atkinson_cls,
        signature=atkinson_cls.signature,
        state={"values": np.array([1.0, 2.0, 4.0, 8.0])},
        params={"epsilon": 0.5},
        seed=17,
    )
    assert atkinson_result.output["result"]["atkinson_index"] > 0.0
    assert atkinson_result.reproducibility.backend.value == "numpy"

    ht_cls = registry.get("survey.weighting.horvitz_thompson@1.0.0")
    ht_result = dispatcher.dispatch(
        method_class=ht_cls,
        signature=ht_cls.signature,
        state={
            "values": np.array([10.0, 15.0, 5.0]),
            "inclusion_probabilities": np.array([0.5, 0.25, 1.0]),
        },
        params={},
        seed=17,
    )
    assert ht_result.output["result"]["total_estimate"] == pytest.approx(85.0)
    assert len(ht_result.output["result"]["weights"]) == 3


def test_foundry_v2_forecasting_validation_and_sensitivity_methods_dispatch() -> None:
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    ets_cls = registry.get("forecasting.univariate.exponential_smoothing@1.0.0")
    ets_result = dispatcher.dispatch(
        method_class=ets_cls,
        signature=ets_cls.signature,
        state={"series": np.array([10.0, 11.0, 13.0, 14.0, 16.0])},
        params={"horizon": 3, "alpha": 0.4, "beta": 0.2},
        seed=5,
    )
    assert len(ets_result.output["result"]["forecast"]) == 3
    assert ets_result.output["forecasting_uncertainty_bundle"] is not None

    scoring_cls = registry.get("validation.probabilistic.normal_scores@1.0.0")
    scoring_result = dispatcher.dispatch(
        method_class=scoring_cls,
        signature=scoring_cls.signature,
        state={
            "observations": np.array([1.1, 1.9, 3.2]),
            "predictive_mean": np.array([1.0, 2.0, 3.0]),
            "predictive_std": np.array([0.3, 0.4, 0.5]),
        },
        params={},
        seed=5,
    )
    assert scoring_result.output["result"]["mean_crps"] >= 0.0
    assert scoring_result.output["result"]["mean_log_score"] >= 0.0

    sobol_cls = registry.get("sensitivity.global.sobol_first_order@1.0.0")
    sobol_result = dispatcher.dispatch(
        method_class=sobol_cls,
        signature=sobol_cls.signature,
        state={
            "outputs_a": np.array([1.0, 2.0, 3.0, 4.0]),
            "outputs_b": np.array([1.5, 2.5, 3.5, 4.5]),
            "mixed_outputs": np.array(
                [
                    [1.3, 2.2, 3.4, 4.3],
                    [1.1, 2.4, 3.2, 4.7],
                ]
            ),
        },
        params={},
        seed=5,
    )
    assert len(sobol_result.output["result"]["first_order_indices"]) == 2
    assert sobol_result.output["result"]["variance"] > 0.0


def test_foundry_v2_registry_excludes_removed_wrapper_fqns() -> None:
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()

    removed_fqns = [
        "causal.inference.difference_in_differences@1.0.0",
        "econometrics.iv.instrumental_variables@1.0.0",
        "econometrics.panel.panel_data@1.0.0",
        "econometrics.timeseries.time_series@1.0.0",
        "optimization.resource_lp@1.0.0",
        "optimization.budget_milp@1.0.0",
        "optimization.leontief_io@1.0.0",
    ]

    for fqn in removed_fqns:
        with pytest.raises(MethodNotFoundError):
            registry.get(fqn)


def test_foundry_v2_dynamic_programming_rollout_samples_transitions() -> None:
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()

    dp_cls = registry.get("optimization.dynamic.dynamic_programming@1.0.0")
    result = dp_cls.pure_step(
        {
            "reward_tensor": np.array([[[1.0], [0.5]]]),
            "transition_tensor": np.array([[[[0.1, 0.9]], [[1.0, 0.0]]]]),
            "initial_state": 0,
        },
        {"discount_factor": 0.95, "__seed__": 3},
    )

    metadata = result["result"]["metadata"]
    assert metadata["rollout_mode"] == "sampled_markov_path"
    assert metadata["terminal_state"] == 0
