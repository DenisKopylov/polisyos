"""Numerical witnesses for the canonical Bayesian strategy's warm/resume path.

The owner is ``scientist.methods.search.strategies.bayesian``. These tests run
the actual optional backend; an unavailable backend is a failed prerequisite,
never evidence that GP restoration works.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, replace
from typing import Any

import pytest

from polisyos.scientist.methods.search.strategies import bayesian as owner
from polisyos.scientist.methods.search.strategies._deps import require_botorch, require_torch
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    ParameterBounds,
    PolicyCandidate,
    StrategyState,
)

_LOG = logging.getLogger(__name__)
_QUERY = [[0.12], [0.29], [0.47], [0.68], [0.87]]
_COORDINATES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 0.9)


def _new(space: SearchSpace) -> BayesianOptimizer:
    require_botorch()
    strategy = BayesianOptimizer(
        space,
        BayesianConfig(
            n_initial=8,
            acquisition=AcquisitionType.UCB,
            num_restarts=3,
            raw_samples=32,
            refit_interval=20,
            fallback_on_failure=False,
            seed=47,
        ),
    )
    assert strategy._botorch_ready, "Real GP backend must execute this witness"
    return strategy


def _evaluation(space: SearchSpace, index: int, x: float) -> Evaluation:
    score = (x - 0.37) ** 2 + 0.02 * (index % 3)
    return Evaluation(
        candidate_id=f"observation-{index}",
        params={"x": x},
        params_normalized=space.normalize({"x": x}),
        objectives=[],
        scalar_score=score,
        stage_a_passed=True,
        provenance_ref=f"fixture/history/observation-{index}",
        metadata={
            "replicate_id": f"replica-{index}",
            "seed": index,
            "warm_start_compatibility": {
                "search_space_fingerprint": space.sobol_space_fingerprint(),
                "input_transform_fingerprint": "Normalize[0,1]",
                "outcome_transform_fingerprint": "Standardize[m=1]",
                "noise_model_fingerprint": "GaussianLikelihood[inferred]",
                "objective_fingerprint": "scalar_score[minimize]",
                "context_fingerprint": "fixture/context/v1",
            },
        },
    )


def _posterior(model: Any) -> tuple[Any, Any]:
    torch = require_torch()
    with torch.no_grad():
        posterior = model.posterior(torch.tensor(_QUERY, dtype=torch.float64))
    return posterior.mean.detach().clone(), posterior.variance.detach().clone()


def _assert_candidate(candidate: PolicyCandidate) -> None:
    assert candidate.source_strategy == "bayesian_acquisition"
    assert candidate.acquisition_value is not None
    assert candidate.predicted_mean is not None
    assert candidate.predicted_std is not None


def _assert_gp_corpus(strategy: BayesianOptimizer, expected: list[Evaluation]) -> None:
    torch = require_torch()
    model = strategy._model
    assert isinstance(model, owner.SingleTaskGP), "Observations must reach a real GP"
    expected_x = torch.tensor([list(e.params_normalized) for e in expected], dtype=torch.float64)
    expected_y = torch.tensor([[-e.scalar_score] for e in expected], dtype=torch.float64)
    raw_x = model._original_train_inputs
    if raw_x is None:
        raw_x = model.train_inputs[0]
    torch.testing.assert_close(raw_x.reshape(-1, expected_x.shape[-1]), expected_x)
    raw_y, _ = model.outcome_transform.untransform(model.train_targets.unsqueeze(-1))
    torch.testing.assert_close(raw_y.reshape(-1, 1), expected_y, rtol=1e-9, atol=1e-10)


def _assert_same_model(expected: Any, actual: Any) -> None:
    torch = require_torch()
    expected_parameters = dict(expected.named_parameters())
    actual_parameters = dict(actual.named_parameters())
    assert expected_parameters.keys() == actual_parameters.keys()
    for name, parameter in expected_parameters.items():
        torch.testing.assert_close(actual_parameters[name], parameter, rtol=0, atol=0)
    for attribute in ("input_transform", "outcome_transform"):
        expected_state = getattr(expected, attribute).state_dict()
        actual_state = getattr(actual, attribute).state_dict()
        assert expected_state.keys() == actual_state.keys()
        for name, value in expected_state.items():
            torch.testing.assert_close(actual_state[name], value, rtol=0, atol=0)
    for actual_value, expected_value in zip(_posterior(actual), _posterior(expected), strict=True):
        torch.testing.assert_close(actual_value, expected_value, rtol=1e-8, atol=1e-10)


def _forbid_refit(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("forbidden full GP refit during admitted continuation")

    monkeypatch.setattr(BayesianOptimizer, "_fit_full_gp", forbidden)
    monkeypatch.setattr(owner, "fit_gpytorch_mll", forbidden)


def _emit(name: str, strategy: BayesianOptimizer, candidate: PolicyCandidate) -> None:
    import botorch
    import gpytorch

    torch = require_torch()
    mean, variance = _posterior(strategy._model)
    _LOG.warning(
        "%s %s",
        name,
        json.dumps(
            {
                "owner": owner.__file__,
                "torch": torch.__version__,
                "botorch": botorch.__version__,
                "gpytorch": gpytorch.__version__,
                "device": strategy._device,
                "train_rows": strategy._model.train_targets.shape[-1],
                "posterior_mean": mean.flatten().tolist(),
                "posterior_variance": variance.flatten().tolist(),
                "ask": candidate.params_normalized,
                "source": candidate.source_strategy,
            },
            sort_keys=True,
        ),
    )


@dataclass
class _Scene:
    space: SearchSpace
    evaluations: list[Evaluation]
    fitted: BayesianOptimizer
    artifact: bytes


@pytest.fixture(scope="module")
def fitted_scene() -> _Scene:
    """Fit eight genuine observations once, without mocking the numerical path."""
    torch = require_torch()
    space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
    evaluations = [_evaluation(space, i, x) for i, x in enumerate(_COORDINATES)]
    fitted = _new(space)
    with torch.random.fork_rng():
        torch.manual_seed(73)
        candidate = fitted.suggest(evaluations)
    _assert_candidate(candidate)
    _assert_gp_corpus(fitted, evaluations)
    _emit("initial_real_fit", fitted, candidate)
    return _Scene(space, evaluations, fitted, fitted.get_state().to_artifact())


def test_warm_observations_reach_real_gp_and_match_unsplit_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warm history is effective data, with artifact deduplication and independent replicas."""
    torch = require_torch()
    space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
    evaluations = [_evaluation(space, i, x) for i, x in enumerate(_COORDINATES)]
    warm = evaluations[:7]
    current = evaluations[7:]
    independent = copy.deepcopy(warm[3])
    independent.candidate_id = "independent-replica"
    independent.scalar_score += 0.04
    independent.metadata["replicate_id"] = "replica-independent"
    independent.metadata["seed"] = 103
    duplicate = replace(warm[3], candidate_id="same-artifact-alias")
    rejected = copy.deepcopy(warm[0])
    rejected.candidate_id = "incompatible-noise"
    rejected.metadata["warm_start_compatibility"]["noise_model_fingerprint"] = "foreign-noise"
    out_of_bounds = replace(warm[0], candidate_id="out-of-bounds", params_normalized=(1.2,))
    unbound = replace(warm[0], candidate_id="unbound", provenance_ref=None)
    expected = [*warm, independent, *current]
    split = _new(space)
    split.warm_start([*warm, duplicate, independent, rejected, out_of_bounds, unbound])
    whole = _new(space)
    candidates = []
    for strategy, corpus in ((split, current), (whole, expected)):
        with torch.random.fork_rng():
            torch.manual_seed(79)
            candidate = strategy.suggest(corpus)
        _assert_candidate(candidate)
        _assert_gp_corpus(strategy, expected)
        candidates.append(candidate)
    _assert_same_model(whole._model, split._model)
    assert candidates[0].params_normalized == pytest.approx(
        candidates[1].params_normalized, abs=1e-8
    )
    _emit("warm_split_real_gp", split, candidates[0])

    # Remove the property but retain _warm_evals and their provenance/compatibility markers.
    removed = _new(space)
    removed.warm_start([*warm, independent])
    monkeypatch.setattr(removed, "_effective_training_corpus", lambda values: values)
    assert len(removed._warm_evals) == 8
    removed.suggest(current)
    with pytest.raises(AssertionError, match="Observations must reach a real GP"):
        _assert_gp_corpus(removed, expected)


def test_warm_corpus_survives_artifact_restore_without_cold_start(
    fitted_scene: _Scene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The receiving optimizer retains effective history after the bytes cross a checkpoint."""
    torch = require_torch()
    scene = fitted_scene
    warm, current = scene.evaluations[:7], scene.evaluations[7:]
    fitted = _new(scene.space)
    fitted.warm_start(warm)
    with torch.random.fork_rng():
        torch.manual_seed(97)
        _assert_candidate(fitted.suggest(current))
    restored = _new(scene.space)
    _forbid_refit(monkeypatch)
    restored.set_state(StrategyState.from_artifact(fitted.get_state().to_artifact()))
    _assert_same_model(fitted._model, restored._model)
    with torch.random.fork_rng():
        torch.manual_seed(101)
        candidate = restored.suggest(current)
    _assert_candidate(candidate)
    _assert_gp_corpus(restored, scene.evaluations)
    _emit("restored_warm_corpus_no_cold_start", restored, candidate)


def test_saved_real_gp_restores_numerical_model_and_same_corpus_ask_without_refit(
    fitted_scene: _Scene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A numerical model roundtrip must continue without secretly fitting another model."""
    torch = require_torch()
    scene = fitted_scene
    restored = _new(scene.space)
    _forbid_refit(monkeypatch)
    restored.set_state(StrategyState.from_artifact(scene.artifact))
    _assert_same_model(scene.fitted._model, restored._model)
    _assert_gp_corpus(restored, scene.evaluations)
    with torch.random.fork_rng():
        torch.manual_seed(83)
        expected_tensor, _ = scene.fitted._optimize_acquisition(
            scene.fitted._train_y_bo, soft_limit=False, evaluations=scene.evaluations
        )
        torch.manual_seed(83)
        candidate = restored.suggest(scene.evaluations)
    _assert_candidate(candidate)
    assert candidate.params_normalized == pytest.approx(
        expected_tensor.flatten().tolist(), abs=1e-8
    )
    _assert_same_model(scene.fitted._model, restored._model)
    _emit("restored_same_corpus_no_refit", restored, candidate)


def test_resumed_append_conditions_real_gp_and_preserves_learned_transforms(
    fitted_scene: _Scene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One new observation changes posterior through the real supported conditioning path."""
    torch = require_torch()
    scene = fitted_scene
    expanded = [*scene.evaluations, _evaluation(scene.space, 8, 0.82)]
    restored = _new(scene.space)
    restored.set_state(StrategyState.from_artifact(scene.artifact))
    reference = copy.deepcopy(scene.fitted._model)
    reference.eval()
    with torch.no_grad():
        reference.posterior(torch.tensor(_QUERY, dtype=torch.float64))
        reference = reference.condition_on_observations(
            X=torch.tensor([[0.82]], dtype=torch.float64),
            Y=torch.tensor([[-expanded[-1].scalar_score]], dtype=torch.float64),
        )
    _forbid_refit(monkeypatch)
    with torch.random.fork_rng():
        torch.manual_seed(89)
        candidate = restored.suggest(expanded)
    _assert_candidate(candidate)
    _assert_gp_corpus(restored, expanded)
    _assert_same_model(reference, restored._model)
    before_mean, _ = _posterior(scene.fitted._model)
    after_mean, _ = _posterior(restored._model)
    assert torch.max(torch.abs(after_mean - before_mean)).item() > 1e-7
    _emit("restored_append_no_refit", restored, candidate)


def test_conditioned_checkpoint_preserves_target_transform_basis_and_posterior(
    fitted_scene: _Scene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving a fantasy GP must not re-standardize targets against its enlarged corpus."""
    torch = require_torch()
    scene = fitted_scene
    expanded = [*scene.evaluations, replace(_evaluation(scene.space, 8, 0.82), scalar_score=0.7)]
    uninterrupted = _new(scene.space)
    with torch.random.fork_rng():
        torch.manual_seed(107)
        _assert_candidate(uninterrupted.suggest(scene.evaluations))
    _forbid_refit(monkeypatch)
    with torch.random.fork_rng():
        torch.manual_seed(109)
        _assert_candidate(uninterrupted.suggest(expanded))
    _assert_gp_corpus(uninterrupted, expanded)
    restored = _new(scene.space)
    restored.set_state(StrategyState.from_artifact(uninterrupted.get_state().to_artifact()))
    _assert_gp_corpus(restored, expanded)
    _assert_same_model(uninterrupted._model, restored._model)
    with torch.random.fork_rng():
        torch.manual_seed(113)
        expected_tensor, _ = uninterrupted._optimize_acquisition(
            uninterrupted._train_y_bo, soft_limit=False, evaluations=expanded
        )
        torch.manual_seed(113)
        candidate = restored.suggest(expanded)
    _assert_candidate(candidate)
    assert candidate.params_normalized == pytest.approx(
        expected_tensor.flatten().tolist(), abs=1e-8
    )
    _emit("restored_conditioned_transform_basis", restored, candidate)


def test_numerical_restore_oracle_rejects_saved_markers_without_loaded_weights(
    fitted_scene: _Scene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted bytes and train rows alone cannot stand in for loaded GP parameters."""
    scene = fitted_scene
    state = StrategyState.from_artifact(scene.artifact)
    assert state.model_state is not None
    assert "train_X" in state.metadata and "train_y_bo" in state.metadata
    monkeypatch.setattr(owner.SingleTaskGP, "load_state_dict", lambda *args, **kwargs: None)
    restored = _new(scene.space)
    restored.set_state(state)
    assert restored.get_state().model_state is not None
    _assert_gp_corpus(restored, scene.evaluations)
    with pytest.raises(AssertionError):
        _assert_same_model(scene.fitted._model, restored._model)


def test_refit_trap_rejects_reset_counter_with_model_markers_intact(
    fitted_scene: _Scene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The no-refit oracle distinguishes a real continuation from a hidden retrain."""
    scene = fitted_scene
    restored = _new(scene.space)
    restored.set_state(StrategyState.from_artifact(scene.artifact))
    restored._last_train_size = 0
    assert restored._model is not None
    assert restored.get_state().model_state is not None
    _forbid_refit(monkeypatch)
    with pytest.raises(AssertionError, match="forbidden full GP refit"):
        restored.suggest(scene.evaluations)


def test_intrinsic_checkpoint_single_and_batch_replay_ignores_external_torch_draws(
    fitted_scene: _Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual next asks consume the persisted instance stream and leave global RNG alone."""
    torch = require_torch()
    scene = fitted_scene
    control, restored = _new(scene.space), _new(scene.space)
    for strategy in (control, restored):
        strategy.set_state(StrategyState.from_artifact(scene.artifact))
    _forbid_refit(monkeypatch)

    def ask(strategy: BayesianOptimizer, *, batch: bool) -> list[PolicyCandidate]:
        global_before = torch.random.get_rng_state().clone()
        local_before = strategy._torch_rng.get_state().clone()
        if batch:
            candidates = strategy.suggest_batch(scene.evaluations, batch_size=2)
            assert len(candidates) == 2
            assert all(c.source_strategy == "batch_qei" for c in candidates)
            assert all(
                c.predicted_mean is not None and c.predicted_std is not None for c in candidates
            )
        else:
            candidates = [strategy.suggest(scene.evaluations)]
            _assert_candidate(candidates[0])
        assert torch.equal(torch.random.get_rng_state(), global_before)
        assert not torch.equal(strategy._torch_rng.get_state(), local_before)
        _assert_gp_corpus(strategy, scene.evaluations)
        return candidates

    # No manual_seed/fork_rng surrounds these asks. Unrelated global draws
    # between matching calls must affect neither the next single ask nor qEI.
    for batch in (False, True, False):
        expected = ask(control, batch=batch)
        torch.rand(137, dtype=torch.float64)
        actual = ask(restored, batch=batch)
        for wanted, got in zip(expected, actual, strict=True):
            assert got.params_normalized == pytest.approx(wanted.params_normalized, abs=1e-8)
            assert got.predicted_mean == pytest.approx(wanted.predicted_mean, abs=1e-9)
            assert got.predicted_std == pytest.approx(wanted.predicted_std, abs=1e-9)
        assert torch.equal(control._torch_rng.get_state(), restored._torch_rng.get_state())
        _assert_same_model(control._model, restored._model)
        _LOG.warning(
            "intrinsic_replay %s",
            json.dumps(
                {
                    "owner": owner.__file__,
                    "batch": batch,
                    "asks": [c.params_normalized for c in actual],
                    "global_rng_unchanged": True,
                    "local_rng_equal": True,
                },
                sort_keys=True,
            ),
        )


def test_removing_local_acquisition_rng_keeps_gp_markers_but_oracle_detects_global_draw(
    fitted_scene: _Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real numerical ask with a global seed draw cannot pass the intrinsic replay oracle."""
    torch = require_torch()
    scene = fitted_scene
    restored = _new(scene.space)
    restored.set_state(StrategyState.from_artifact(scene.artifact))
    _forbid_refit(monkeypatch)
    assert restored.get_state().model_state is not None
    local_before = restored._torch_rng.get_state().clone()
    global_before = torch.random.get_rng_state().clone()
    monkeypatch.setattr(
        restored, "_next_acquisition_seed", lambda: int(torch.randint(0, 2**31 - 1, (1,)).item())
    )
    _assert_candidate(restored.suggest(scene.evaluations))
    _assert_same_model(scene.fitted._model, restored._model)
    assert torch.equal(restored._torch_rng.get_state(), local_before)
    with pytest.raises(AssertionError):
        assert torch.equal(torch.random.get_rng_state(), global_before)


@pytest.mark.parametrize(
    "field,value",
    [("last_refit_iteration", 999999), ("acquisition_replay_policy", "old_unconfined_policy")],
)
def test_future_refit_clock_and_old_acquisition_policy_refuse_atomically(
    fitted_scene: _Scene, field: str, value: Any
) -> None:
    """Persisted model markers cannot authorize an impossible clock or obsolete ask policy."""
    torch = require_torch()
    scene = fitted_scene
    restored = _new(scene.space)
    restored.set_state(StrategyState.from_artifact(scene.artifact))
    state = StrategyState.from_artifact(scene.artifact)
    assert state.model_state is not None
    state.metadata[field] = value
    model_before = restored._model
    rng_before = restored._rng.getstate()
    torch_before = restored._torch_rng.get_state().clone()
    iteration_before = restored._iteration
    with pytest.raises(ValueError, match="incompatible"):
        restored.set_state(state)
    assert restored._model is model_before
    assert restored._rng.getstate() == rng_before
    assert torch.equal(restored._torch_rng.get_state(), torch_before)
    assert restored._iteration == iteration_before
    _assert_same_model(scene.fitted._model, restored._model)
