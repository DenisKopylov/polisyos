"""CAS checkpoints for the existing MO CPU refit-per-ask profile.

Numerical expectations use saved scalar parameters and NumPy only.  Actual
predictions and proposals execute the locked native SingleTaskGP/ModelListGP.
The synthetic utility/cost measurements are not production evaluator truth.
"""

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import asdict

import numpy as np
import pytest

from polisyos.core import artifacts
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies import multi_objective as mo_module
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    StrategyState,
)

POINTS = (0.08, 0.16, 0.23, 0.35, 0.42, 0.50, 0.61, 0.70)
QUERIES = (0.015, 0.12, 0.29, 0.465, 0.655, 0.885, 0.99)
DIRECTIONS = (OptimizationDirection.MAXIMIZE, OptimizationDirection.MINIMIZE)


def _space():
    return SearchSpace([ParameterBounds("x", 0.0, 1.0)])


def _strategy(space, config=None):
    return MOBayesianOptimizer(space, ["utility", "cost"], list(DIRECTIONS), config or MOConfig())


def _measurement(x):
    return 12.0 + 3.0 * math.sin(5.0 * x), 50.0 + 5.0 * math.cos(4.0 * x) + 2.0 * x


def _rows(space):
    output = []
    for index, x in enumerate(POINTS):
        utility, cost = _measurement(x)
        output.append(
            Evaluation(
                candidate_id=f"mo-measurement-{index}",
                params={"x": x},
                params_normalized=(x,),
                objectives=[
                    ObjectiveValue("utility", utility, DIRECTIONS[0]),
                    ObjectiveValue("cost", cost, DIRECTIONS[1]),
                ],
                scalar_score=utility - cost,
                stage_a_passed=True,
                stage_b_result={"synthetic_utility": utility, "synthetic_cost": cost},
                provenance_ref=f"synthetic-mo/{index}",
            )
        )
    return output


def _persist(tmp_path, strategy):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        strategy.get_state().to_artifact(),
        artifacts.PutOptions(
            kind="search.strategy_state",
            media_type="application/octet-stream",
        ),
    )
    fresh_store = artifacts.FileSystemCAS(tmp_path / "cas")
    return StrategyState.from_artifact(fresh_store.get_bytes(ref))


def test_current_mo_profile_actual_cas_sobol_next_sequence_and_independent_replica(tmp_path):
    space = _space()
    config = MOConfig(n_initial=20, seed=19)
    live = _strategy(space, config)
    rows = _rows(space)
    initial = [live.suggest(rows[:index]).params for index in range(3)]
    assert len({repr(value) for value in initial}) == 3
    state = _persist(tmp_path, live)
    fresh = _strategy(space, MOConfig(n_initial=20, seed=999))
    replica = _strategy(space, MOConfig(n_initial=20, seed=71))
    reference = _strategy(space, MOConfig(n_initial=20, seed=71))
    fresh.set_state(state)
    resumed, independent = [], []
    for index in range(3, 8):
        resumed.append(fresh.suggest(rows[:index]).params)
        assert resumed[-1] == live.suggest(rows[:index]).params
        independent.append(replica.suggest(rows[:index]).params)
        assert independent[-1] == reference.suggest(rows[:index]).params
    assert resumed != independent
    assert fresh.get_state().metadata["config"]["seed"] == 19
    assert state.metadata["profile"] == (
        "mo.single_task_gp.cpu.refit_each_ask.v1"
        if live._botorch_ready
        else "mo.random_or_sobol.no_botorch.v1"
    )
    print("ACTUAL_MO_CAS_SOBOL", state.metadata["profile"], resumed)


@pytest.mark.parametrize(
    "field",
    [
        "version",
        "profile",
        "backend",
        "config",
        "objective_names",
        "directions",
        "space",
        "seed",
        "reference",
        "torch_rng",
        "type",
    ],
)
def test_mo_changed_or_incomplete_state_refuses_without_live_mutation(tmp_path, field):
    space = _space()
    live = _strategy(space, MOConfig(n_initial=20, seed=19))
    live.suggest([])
    state = _persist(tmp_path, live)
    fresh = _strategy(space, MOConfig(n_initial=20, seed=999))
    before = fresh.get_state().to_artifact()
    state.iteration += 99
    if field == "version":
        state.metadata["mo_state_version"] = True
    elif field == "profile":
        state.metadata["profile"] = "unknown"
    elif field == "backend":
        state.metadata["backend"] = {"torch": "changed"}
    elif field == "config":
        state.metadata["config"]["n_initial"] = True
    elif field == "objective_names":
        state.metadata[field] = ["cost", "utility"]
    elif field == "directions":
        state.metadata[field] = [direction.value for direction in reversed(DIRECTIONS)]
    elif field == "space":
        state.metadata[field] = "foreign"
    elif field == "seed":
        state.metadata[field] = True
    elif field == "reference":
        state.metadata["ref_point"] = [True, -70.0]
    elif field == "torch_rng":
        state.rng_state["torch"] = [True]
    else:
        state.strategy_name = "RandomSearchStrategy"
    with pytest.raises(ValueError):
        fresh.set_state(state)
    assert fresh.get_state().to_artifact() == before


@pytest.fixture(scope="module")
def fitted_case(tmp_path_factory):
    torch = pytest.importorskip("torch", reason="UNRUN: MO numerical state requires Torch")
    pytest.importorskip("botorch", reason="UNRUN: MO numerical state requires BoTorch")
    pytest.importorskip("gpytorch", reason="UNRUN: MO numerical state requires GPyTorch")
    assert mo_module.fit_gpytorch_mll is not None
    space = _space()
    config = MOConfig(n_initial=6, ref_point=[0.0, -70.0], max_train_size=64, seed=19)
    strategy = _strategy(space, config)
    assert strategy._botorch_ready and strategy._device == "cpu"
    actual_fit = mo_module.fit_gpytorch_mll
    calls = []

    def observe_fit(mll, *args, **kwargs):
        calls.append(mll)
        return actual_fit(mll, *args, **kwargs)

    patch = pytest.MonkeyPatch()
    patch.setattr(mo_module, "fit_gpytorch_mll", observe_fit)
    directory = tmp_path_factory.mktemp("mo-native-cas")
    rows = _rows(space)
    ambient = torch.get_rng_state().clone()
    candidate = strategy.suggest(rows)
    assert candidate.source_strategy == "ehvi", "A random fallback is not numerical MO execution"
    assert torch.equal(ambient, torch.get_rng_state())
    assert len(calls) == 1
    saved = _persist(directory, strategy)
    (directory / "native-mo.artifact").write_bytes(saved.to_artifact())
    print(
        "ACTUAL_MO_NATIVE_CORPUS",
        saved.metadata["train_X"],
        saved.metadata["train_Y"],
        saved.metadata["profile"],
        saved.metadata["backend"],
    )
    try:
        yield space, config, rows, strategy, saved, calls
    finally:
        patch.undo()


def _weights(state):
    import torch

    return torch.load(io.BytesIO(state.model_state), weights_only=True)


def _scalar(weights, key):
    value = weights[key].detach().cpu().numpy()
    assert value.size == 1
    return float(value.reshape(-1)[0])


def _independent_mean_full_covariance(state, index):
    """Saved ConstantMean/unit-RBF/GaussianLikelihood with explicit transforms."""
    weights = _weights(state)
    prefix = f"models.{index}."
    lengthscale = _scalar(weights, prefix + "covar_module.raw_lengthscale")
    noise = _scalar(weights, prefix + "likelihood.noise_covar.raw_noise")
    constant = _scalar(weights, prefix + "mean_module.raw_constant")
    offset = _scalar(weights, prefix + "input_transform._offset")
    scale = _scalar(weights, prefix + "input_transform._coefficient")
    mean = _scalar(weights, prefix + "outcome_transform.means")
    std = _scalar(weights, prefix + "outcome_transform.stdvs")
    assert min(lengthscale, noise, scale, std) > 0
    assert _scalar(weights, prefix + "outcome_transform._stdvs_sq") == pytest.approx(std**2)
    raw_x = np.asarray(POINTS)
    raw_y = np.asarray([_measurement(x)[index] * (1 if index == 0 else -1) for x in POINTS])
    np.testing.assert_allclose(np.asarray(state.metadata["train_X"])[:, 0], raw_x)
    np.testing.assert_allclose(np.asarray(state.metadata["train_Y"])[:, index], raw_y)
    assert len(raw_x) == 8 == len(set(POINTS))
    x = (raw_x - offset) / scale
    q = (np.asarray(QUERIES) - offset) / scale
    y = (raw_y - mean) / std

    def rbf(left, right):
        return np.exp(-0.5 * ((left[:, None] - right[None, :]) / lengthscale) ** 2)

    covariance = rbf(x, x) + noise * np.eye(len(x))
    cross = rbf(q, x)
    expected_mean = mean + std * (constant + cross @ np.linalg.solve(covariance, y - constant))
    expected_covariance = std**2 * (rbf(q, q) - cross @ np.linalg.solve(covariance, cross.T))
    if index == 1:
        expected_mean = -expected_mean
    assert np.max(np.abs(expected_covariance - np.diag(np.diag(expected_covariance)))) > 1e-8
    assert np.linalg.eigvalsh(expected_covariance).min() > -1e-9
    return expected_mean, expected_covariance


def _actual(component, index):
    import gpytorch
    import torch
    from gpytorch.kernels import RBFKernel
    from gpytorch.likelihoods import GaussianLikelihood
    from gpytorch.means import ConstantMean

    assert isinstance(component.covar_module, RBFKernel)
    assert isinstance(component.mean_module, ConstantMean)
    assert isinstance(component.likelihood, GaussianLikelihood)
    assert not component.covar_module.raw_lengthscale_constraint.enforced
    assert not component.likelihood.noise_covar.raw_noise_constraint.enforced
    query = torch.tensor(QUERIES, dtype=torch.float64).reshape(-1, 1)
    component.eval()
    with (
        torch.no_grad(),
        gpytorch.settings.fast_pred_var(False),
        gpytorch.settings.fast_computations(
            covar_root_decomposition=False,
            log_prob=False,
            solves=False,
        ),
    ):
        posterior = component.posterior(query)
        return (
            (1 if index == 0 else -1) * posterior.mean.detach().cpu().numpy().reshape(-1),
            posterior.distribution.covariance_matrix.detach().cpu().numpy(),
        )


@pytest.mark.integration
def test_native_mo_fitted_cas_restore_matches_independent_mean_and_full_covariance(fitted_case):
    import torch

    space, config, _, live, saved, calls = fitted_case
    before = len(calls)
    fresh = _strategy(space, MOConfig(**{**asdict(config), "seed": 999}))
    ambient = torch.get_rng_state().clone()
    fresh.set_state(StrategyState.from_artifact(saved.to_artifact()))
    assert len(calls) == before, "Restore must not fit an MLL"
    assert torch.equal(ambient, torch.get_rng_state())
    assert torch.equal(fresh._torch_rng.get_state(), live._torch_rng.get_state())
    assert fresh._rng.getstate() == live._rng.getstate()
    for index in range(2):
        expected_mean, expected_covariance = _independent_mean_full_covariance(saved, index)
        for component in (live._model.models[index], fresh._model.models[index]):
            actual_mean, actual_covariance = _actual(component, index)
            np.testing.assert_allclose(actual_mean, expected_mean, rtol=2e-7, atol=2e-8)
            np.testing.assert_allclose(actual_covariance, expected_covariance, rtol=2e-7, atol=2e-8)
        old_weights, new_weights = (
            live._model.models[index].state_dict(),
            fresh._model.models[index].state_dict(),
        )
        assert set(old_weights) == set(new_weights)
        assert all(torch.equal(value, new_weights[key]) for key, value in old_weights.items())
    print(
        "ACTUAL_MO_RESTORE_ORACLE",
        before,
        len(calls),
        "8 distinct points; 2 full covariance matrices",
    )


@pytest.mark.integration
def test_native_mo_next_ehvi_and_fit_clock_matches_uninterrupted_with_ambient_rng_owned(
    fitted_case,
):
    import torch

    space, config, rows, left, saved, calls = fitted_case
    right = _strategy(space, MOConfig(**{**asdict(config), "seed": 999}))
    replica = _strategy(space, MOConfig(**{**asdict(config), "seed": 71}))
    right.set_state(StrategyState.from_artifact(saved.to_artifact()))
    replica_before = replica.get_state().to_artifact()
    ambient = torch.get_rng_state().clone()
    count = len(calls)
    next_left, next_right = left.suggest(rows), right.suggest(rows)
    assert next_left.source_strategy == next_right.source_strategy == "ehvi"
    assert len(calls) - count == 2, "Existing MO policy refits once on each actual ask"
    assert next_left.params == next_right.params
    assert next_left.params_normalized == next_right.params_normalized
    assert torch.equal(ambient, torch.get_rng_state())
    assert torch.equal(left._torch_rng.get_state(), right._torch_rng.get_state())
    assert replica.get_state().to_artifact() == replica_before
    print("ACTUAL_MO_NEXT_EHVI", next_left.params, len(calls) - count)


@pytest.mark.integration
@pytest.mark.parametrize(
    "field", ["model_bytes", "model_removed", "corpus", "reference", "rng", "version"]
)
def test_native_mo_marker_preserving_corruption_refuses_atomically(fitted_case, field):
    space, config, _, _, saved, calls = fitted_case
    state = StrategyState.from_artifact(saved.to_artifact())
    state.iteration += 99
    if field == "model_bytes":
        state.model_state = state.model_state[:-1] + bytes([state.model_state[-1] ^ 1])
    elif field == "model_removed":
        state.model_state = None
    elif field == "corpus":
        state.metadata["train_Y"][0][0] += 1
    elif field == "reference":
        state.metadata["ref_point"][0] = True
    elif field == "rng":
        state.rng_state["torch"][0] = True
    else:
        state.metadata["mo_state_version"] = True
    fresh = _strategy(space, MOConfig(**asdict(config)))
    before = fresh.get_state().to_artifact()
    fit_before = len(calls)
    with pytest.raises(ValueError):
        fresh.set_state(state)
    assert len(calls) == fit_before
    assert fresh.get_state().to_artifact() == before


@pytest.mark.integration
@pytest.mark.parametrize(
    "key",
    [
        "mean_module.raw_constant",
        "likelihood.noise_covar.raw_noise",
        "outcome_transform.means",
        "input_transform._coefficient",
    ],
)
def test_native_mo_changed_fitted_parameter_with_recomputed_local_digest_is_not_marker_equivalence(
    fitted_case, key
):
    import torch

    space, config, _, _, saved, calls = fitted_case
    weights = _weights(saved)
    weights["models.0." + key] = weights["models.0." + key] + 0.5
    # ModelListGP duplicates the same owned likelihood in its serialized tree.
    if key.startswith("likelihood."):
        weights["likelihood.likelihoods.0." + key[len("likelihood.") :]] = weights[
            "models.0." + key
        ]
    buffer = io.BytesIO()
    torch.save(weights, buffer)
    changed = StrategyState.from_artifact(saved.to_artifact())
    changed.model_state = buffer.getvalue()
    changed.metadata["model_state_sha256"] = hashlib.sha256(changed.model_state).hexdigest()
    fresh = _strategy(space, MOConfig(**asdict(config)))
    before = fresh.get_state().to_artifact()
    fit_before = len(calls)
    try:
        fresh.set_state(changed)
    except ValueError:
        assert fresh.get_state().to_artifact() == before
    else:
        expected_mean, expected_covariance = _independent_mean_full_covariance(saved, 0)
        actual_mean, actual_covariance = _actual(fresh._model.models[0], 0)
        assert not (
            np.allclose(actual_mean, expected_mean, rtol=2e-7, atol=2e-8)
            and np.allclose(actual_covariance, expected_covariance, rtol=2e-7, atol=2e-8)
        )
    assert len(calls) == fit_before


@pytest.mark.integration
@pytest.mark.parametrize("field", ["boolean_parameter", "rebound_reference"])
def test_native_mo_rehashed_malformed_or_foreign_state_refuses_before_live_mutation(
    fitted_case, field
):
    import torch

    space, config, _, _, saved, calls = fitted_case
    changed = StrategyState.from_artifact(saved.to_artifact())
    if field == "boolean_parameter":
        weights = _weights(saved)
        weights["models.0.mean_module.raw_constant"] = torch.tensor(True)
        buffer = io.BytesIO()
        torch.save(weights, buffer)
        changed.model_state = buffer.getvalue()
        changed.metadata["model_state_sha256"] = hashlib.sha256(changed.model_state).hexdigest()
    else:
        changed.metadata["ref_point"][0] += 1.0
        changed.metadata["corpus_sha256"] = MOBayesianOptimizer._corpus_digest(changed.metadata)
    fresh = _strategy(space, MOConfig(**asdict(config)))
    before = fresh.get_state().to_artifact()
    fit_before = len(calls)
    with pytest.raises(ValueError):
        fresh.set_state(changed)
    assert len(calls) == fit_before
    assert fresh.get_state().to_artifact() == before


@pytest.mark.integration
def test_native_mo_failed_refit_fallback_checkpoint_is_coherent_and_fresh_resume_recovers(
    fitted_case,
    tmp_path,
    monkeypatch,
):
    import torch

    space, _, rows, _, _, calls = fitted_case
    config = MOConfig(n_initial=6, max_train_size=64, seed=23)
    live = _strategy(space, config)
    first = live.suggest(rows)
    assert first.source_strategy == "ehvi"
    original = _persist(tmp_path, live)
    changed = Evaluation(
        candidate_id="changed-measurement",
        params={"x": 0.93},
        params_normalized=(0.93,),
        objectives=[
            ObjectiveValue("utility", 1.0, DIRECTIONS[0]),
            ObjectiveValue("cost", 200.0, DIRECTIONS[1]),
        ],
        scalar_score=-199.0,
        stage_a_passed=True,
        stage_b_result={"synthetic_utility": 1.0, "synthetic_cost": 200.0},
    )
    history = [*rows, changed]
    old_reference = original.metadata["ref_point"]
    assert (
        list(live._reference_point_values([live._objective_vector(r) for r in history]))
        != old_reference
    )
    before_failure = len(calls)

    def failed_fit(*args, **kwargs):
        raise RuntimeError("controlled actual refit failure before model publication")

    with monkeypatch.context() as fault:
        fault.setattr(mo_module, "fit_gpytorch_mll", failed_fit)
        fallback = live.suggest(history)
    assert fallback.source_strategy == "random_fallback"
    assert len(calls) == before_failure
    failed_checkpoint = _persist(tmp_path, live)
    assert failed_checkpoint.iteration == len(history)
    for field in ("train_X", "train_Y", "ref_point"):
        assert failed_checkpoint.metadata[field] == original.metadata[field]
    original_weights, failed_weights = _weights(original), _weights(failed_checkpoint)
    assert all(torch.equal(value, failed_weights[key]) for key, value in original_weights.items())
    fresh = _strategy(space, MOConfig(**{**asdict(config), "seed": 999}))
    ambient = torch.get_rng_state().clone()
    fresh.set_state(failed_checkpoint)
    assert len(calls) == before_failure
    assert torch.equal(ambient, torch.get_rng_state())
    for index in range(2):
        expected_mean, expected_covariance = _independent_mean_full_covariance(original, index)
        actual_mean, actual_covariance = _actual(fresh._model.models[index], index)
        np.testing.assert_allclose(actual_mean, expected_mean, rtol=2e-7, atol=2e-8)
        np.testing.assert_allclose(actual_covariance, expected_covariance, rtol=2e-7, atol=2e-8)
    next_live, next_fresh = live.suggest(history), fresh.suggest(history)
    assert next_live.source_strategy == next_fresh.source_strategy == "ehvi"
    assert next_live.params == next_fresh.params
    assert len(calls) - before_failure == 2
    assert torch.equal(ambient, torch.get_rng_state())
    print(
        "ACTUAL_MO_REFIT_FAILURE_CAS_RECOVERY",
        old_reference,
        fresh.get_state().metadata["ref_point"],
        next_fresh.params,
        len(calls) - before_failure,
    )
