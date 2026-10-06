"""Actual generator checkpoint and owner-paired transfer activation consumers."""

import sys
from copy import deepcopy
from dataclasses import replace

import pytest

from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import BenchmarkSplit, MetricDirection
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history


def cold(seed=19):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0.0, "upper": 1.0}]), seed=seed
    )
    assert generator.botorch_available, "UNRUN: required actual optional backend"
    return generator


def test_public_checkpoint_preserves_next_actual_sobol_action():
    original = cold()
    original.generate([], None, {})
    state = original.get_state()
    resumed = cold()
    resumed.set_state(deepcopy(state))
    expected = original.generate([], None, {})
    actual = resumed.generate([], None, {})
    assert actual["x"] == expected["x"]
    assert actual["_strategy_metadata"]["source"] == "sobol_init"
    assert (
        resumed.get_state()["strategy_state"]["rng_state"]["sobol"]
        == original.get_state()["strategy_state"]["rng_state"]["sobol"]
    )


@pytest.mark.parametrize("mutation", ["metric", "bool_seed", "flag", "schema", "rng"])
def test_wrapper_refusal_is_atomic_for_actual_native_rng(mutation):
    generator = cold()
    generator.generate([], None, {})
    before = generator.get_state()
    invalid = deepcopy(before)
    if mutation == "metric":
        invalid["config"]["primary_metric"] = "foreign"
    elif mutation == "bool_seed":
        invalid["config"]["seed"] = True
    elif mutation == "flag":
        invalid["activity_started"] = "false"
    elif mutation == "schema":
        invalid["schema_version"] = None
    else:
        invalid["strategy_state"]["rng_state"]["python"] = {"codec": "foreign"}
    with pytest.raises(ValueError):
        generator.set_state(invalid)
    assert generator.get_state() == before


def test_changed_processed_history_refuses_before_next_native_suggest():
    generator = cold()
    history = [{"params": {"x": 0.2}, "score": 1.0, "stage_a_passed": True}]
    generator.generate(history, None, {})
    resumed = cold()
    resumed.set_state(generator.get_state())
    history[0]["score"] = 2.0
    with pytest.raises(ValueError, match="resume history differs"):
        resumed.generate(history, None, {})


def test_configure_transfer_requires_pre_activity_pair():
    generator = cold()
    generator.generate([], None, {})
    with pytest.raises(ValueError, match="before warm/history/generation"):
        generator.configure_transfer(object(), object())


def test_owner_configured_bridge_reaches_real_gp_and_wrapper_resume_without_mll_fit(tmp_path):
    _, _, manager, _, target, _, basis = measured_history(tmp_path, count=8)
    bridge = WarmStartBridge(manager)

    def receiver():
        generator = BayesianCandidateGenerator(
            SearchSpace(basis.bounds["parameters"]),
            primary_metric="score",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            n_initial=3,
            seed=19,
        )
        generator.configure_transfer(bridge, target)
        generator._optimizer._config = replace(
            generator._optimizer._config,
            num_restarts=2,
            raw_samples=32,
            refit_interval=20,
            fallback_on_failure=False,
        )
        return generator

    counts = {"mll": 0}

    def observe(frame, event, arg):
        if (
            event == "call"
            and frame.f_code.co_name == "fit_gpytorch_mll"
            and frame.f_code.co_filename.endswith("botorch/fit.py")
        ):
            counts["mll"] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        original = receiver()
        assert len(original._optimizer._warm_evals) == 8
        original.generate([], None, {})
        assert counts["mll"] == 1
        assert original._optimizer._model is not None
        state = original.get_state()
        resumed = receiver()
        resumed.set_state(deepcopy(state))
        assert counts["mll"] == 1
        assert (
            resumed._optimizer._fitted_train_X.tolist()
            == original._optimizer._fitted_train_X.tolist()
        )
        assert (
            resumed._optimizer._fitted_train_y_bo.tolist()
            == original._optimizer._fitted_train_y_bo.tolist()
        )
        expected = original.generate([], None, {})
        actual = resumed.generate([], None, {})
        assert actual["x"] == pytest.approx(expected["x"], abs=1e-12)
        assert actual["_strategy_metadata"]["source"] == "bayesian_acquisition"
        assert counts["mll"] == 1
    finally:
        sys.setprofile(previous)


def test_missing_configured_pair_refuses_without_changing_native_receiver():
    generator = cold()
    before = generator.get_state()
    with pytest.raises(ValueError, match="paired bridge"):
        generator.configure_transfer(None, None)
    assert generator.get_state() == before
