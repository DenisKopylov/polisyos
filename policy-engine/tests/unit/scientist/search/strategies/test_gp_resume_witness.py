"""Numerical checks for a real Bayesian GP checkpoint and continuation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.scientist.methods.search.strategies import bayesian as owner
from polisyos.scientist.methods.search.strategies._deps import (
    fit_gpytorch_mll,
    require_botorch,
    require_torch,
)
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    ParameterBounds,
    StrategyState,
)

from .conftest import make_evaluation

pytestmark = pytest.mark.skipif(
    fit_gpytorch_mll is None, reason="BoTorch stack unavailable; GP witness unrun"
)

_X = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 0.9)
_QUERY = np.array([0.12, 0.29, 0.47, 0.68, 0.87], dtype=np.float64).reshape(-1, 1)
_BETA = 2.0


@dataclass(frozen=True)
class _Basis:
    """Fitted scalar RBF GP and affine transform values, in double precision."""

    offset: float
    coefficient: float
    target_mean: float
    target_std: float
    lengthscale: float
    noise: float
    mean: float


@dataclass
class _Scene:
    space: SearchSpace
    evaluations: list[Evaluation]
    fitted: BayesianOptimizer
    artifact: bytes
    basis: _Basis


def _new(space: SearchSpace) -> BayesianOptimizer:
    require_botorch()  # Unexpected runtime unavailability remains an error.
    strategy = BayesianOptimizer(
        space,
        BayesianConfig(
            n_initial=8,
            acquisition=AcquisitionType.UCB,
            ucb_beta=_BETA,
            num_restarts=3,
            raw_samples=32,
            refit_interval=50,
            fallback_on_failure=False,
            seed=47,
        ),
    )
    assert strategy._botorch_ready
    assert strategy._device == "cpu"
    return strategy


def _basis(model: Any) -> _Basis:
    from gpytorch.kernels import RBFKernel
    from gpytorch.means import ConstantMean

    # Do not silently apply this formula to a different GP kernel or mean.
    assert type(model.covar_module) is RBFKernel
    assert type(model.mean_module) is ConstantMean
    return _Basis(
        offset=float(model.input_transform.offset.item()),
        coefficient=float(model.input_transform.coefficient.item()),
        target_mean=float(model.outcome_transform.means.item()),
        target_std=float(model.outcome_transform.stdvs.item()),
        lengthscale=float(model.covar_module.lengthscale.item()),
        noise=float(model.likelihood.noise.item()),
        mean=float(model.mean_module.constant.item()),
    )


def _oracle(basis: _Basis, evaluations: list[Evaluation]) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate the latent GP posterior using only the frozen basis and linear algebra."""
    x = np.array([evaluation.params_normalized for evaluation in evaluations], dtype=np.float64)
    y = -np.array([evaluation.scalar_score for evaluation in evaluations], dtype=np.float64)
    x = (x - basis.offset) / basis.coefficient
    query = (_QUERY - basis.offset) / basis.coefficient
    y = (y - basis.target_mean) / basis.target_std

    def kernel(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        scaled = (left[:, None, :] - right[None, :, :]) / basis.lengthscale
        return np.exp(-0.5 * np.sum(scaled * scaled, axis=-1))

    cross = kernel(x, query)
    covariance = kernel(x, x) + basis.noise * np.eye(len(x))
    cholesky = np.linalg.cholesky(covariance)
    alpha = np.linalg.solve(cholesky.T, np.linalg.solve(cholesky, y - basis.mean))
    mean = (basis.mean + cross.T @ alpha) * basis.target_std + basis.target_mean
    projected = np.linalg.solve(cholesky, cross)
    covariance = (kernel(query, query) - projected.T @ projected) * basis.target_std**2
    return mean, covariance


def _posterior(model: Any) -> tuple[np.ndarray, np.ndarray]:
    torch = require_torch()
    with torch.no_grad():
        posterior = model.posterior(
            torch.tensor(_QUERY, dtype=torch.float64), observation_noise=False
        )
    return (
        posterior.mean.detach().cpu().numpy().reshape(-1),
        posterior.mvn.covariance_matrix.detach().cpu().numpy(),
    )


def _assert_numerics(strategy: BayesianOptimizer, basis: _Basis, values: list[Evaluation]) -> None:
    expected_mean, expected_covariance = _oracle(basis, values)
    actual_mean, actual_covariance = _posterior(strategy._model)
    np.testing.assert_allclose(actual_mean, expected_mean, rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(actual_covariance, expected_covariance, rtol=1e-6, atol=1e-8)

    # UCB is evaluated by the optimizer's real acquisition constructor; the
    # expected values are calculated independently from the analytic posterior.
    torch = require_torch()
    acquisition, kind = strategy._acquisition_function(strategy._train_y_bo, values)
    assert kind == AcquisitionType.UCB.value
    with torch.no_grad():
        actual_ucb = acquisition(torch.tensor(_QUERY[:, None, :], dtype=torch.float64))
    expected_ucb = expected_mean + np.sqrt(_BETA * np.diag(expected_covariance))
    np.testing.assert_allclose(
        actual_ucb.detach().cpu().numpy(), expected_ucb, rtol=1e-6, atol=1e-8
    )


def _restore(scene: _Scene, artifact: bytes) -> BayesianOptimizer:
    restored = _new(scene.space)
    restored.set_state(StrategyState.from_artifact(artifact))
    return restored


def _forbid_refit(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("unexpected GP refit during continuation")

    monkeypatch.setattr(owner, "fit_gpytorch_mll", forbidden)
    monkeypatch.setattr(BayesianOptimizer, "_fit_full_gp", forbidden)


@pytest.fixture(scope="module")
def scene() -> _Scene:
    torch = require_torch()
    require_botorch()
    space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
    evaluations = [
        make_evaluation(
            candidate_id=f"row-{index}",
            params={"x": x},
            score=(x - 0.37) ** 2 + 0.02 * (index % 3),
            space=space,
        )
        for index, x in enumerate(_X)
    ]
    fitted = _new(space)
    with torch.random.fork_rng():
        torch.manual_seed(73)
        candidate = fitted.suggest(evaluations)
    assert candidate.source_strategy == "bayesian_acquisition"
    return _Scene(
        space, evaluations, fitted, fitted.get_state().to_artifact(), _basis(fitted._model)
    )


def test_fitted_checkpoint_matches_independent_posterior_and_acquisition(
    scene: _Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fresh restore preserves the fitted transform and the numerical GP, without refitting."""
    _forbid_refit(monkeypatch)
    restored = _restore(scene, scene.artifact)
    assert _basis(restored._model) == scene.basis
    _assert_numerics(scene.fitted, scene.basis, scene.evaluations)
    _assert_numerics(restored, scene.basis, scene.evaluations)


def test_conditioned_checkpoint_restores_frozen_target_basis_and_posterior(
    scene: _Scene, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An appended target must retain the old transform after another checkpoint."""
    torch = require_torch()
    expanded = [
        *scene.evaluations,
        make_evaluation(candidate_id="appended", params={"x": 0.82}, score=0.7, space=scene.space),
    ]
    _forbid_refit(monkeypatch)
    uninterrupted = _restore(scene, scene.artifact)
    with torch.random.fork_rng():
        torch.manual_seed(109)
        candidate = uninterrupted.suggest(expanded)
    assert candidate.source_strategy == "bayesian_acquisition"
    assert _basis(uninterrupted._model) == scene.basis
    _assert_numerics(uninterrupted, scene.basis, expanded)

    artifact_path = tmp_path / "conditioned-strategy.json"
    artifact_path.write_bytes(uninterrupted.get_state().to_artifact())
    restored = _restore(scene, artifact_path.read_bytes())
    assert _basis(restored._model) == scene.basis
    raw_targets = -np.array([item.scalar_score for item in expanded], dtype=np.float64)
    assert abs(raw_targets.mean() - scene.basis.target_mean) > 0.01
    expected_targets = (raw_targets - scene.basis.target_mean) / scene.basis.target_std
    np.testing.assert_allclose(
        restored._model.train_targets.detach().cpu().numpy(),
        expected_targets,
        rtol=1e-9,
        atol=1e-10,
    )
    _assert_numerics(restored, scene.basis, expanded)
    with torch.random.fork_rng():
        torch.manual_seed(113)
        expected = uninterrupted.suggest(expanded)
        torch.manual_seed(113)
        actual = restored.suggest(expanded)
    assert actual.source_strategy == expected.source_strategy == "bayesian_acquisition"
    assert actual.params_normalized == pytest.approx(expected.params_normalized, abs=1e-8)
    assert actual.acquisition_value == pytest.approx(expected.acquisition_value, abs=1e-8)


def test_conditioned_restore_detects_removed_target_restandardization(
    scene: _Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Saved markers cannot substitute for reconciling targets with the loaded transform."""
    expanded = [
        *scene.evaluations,
        make_evaluation(candidate_id="appended", params={"x": 0.82}, score=0.7, space=scene.space),
    ]
    _forbid_refit(monkeypatch)
    conditioned = _restore(scene, scene.artifact)
    assert conditioned.suggest(expanded).source_strategy == "bayesian_acquisition"
    _assert_numerics(conditioned, scene.basis, expanded)
    artifact = conditioned.get_state().to_artifact()
    assert StrategyState.from_artifact(artifact).metadata["gp_continuation"]
    actual_load = owner.SingleTaskGP.load_state_dict

    def without_target_restandardization(model: Any, state: Any, **kwargs: Any) -> Any:
        return actual_load(model, state, keep_transforms=False, **kwargs)

    monkeypatch.setattr(owner.SingleTaskGP, "load_state_dict", without_target_restandardization)
    fake = _restore(scene, artifact)
    assert _basis(fake._model) == scene.basis
    with pytest.raises(AssertionError):
        _assert_numerics(fake, scene.basis, expanded)


def test_missing_state_load_is_detected_with_checkpoint_markers_present(
    scene: _Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The oracle rejects a real model reconstructed without its saved fitted values."""
    state = StrategyState.from_artifact(scene.artifact)
    assert state.model_state is not None and state.metadata["gp_continuation"]
    _forbid_refit(monkeypatch)
    monkeypatch.setattr(owner.SingleTaskGP, "load_state_dict", lambda *args, **kwargs: None)
    fake = _restore(scene, scene.artifact)
    assert fake.get_state().model_state is not None
    expected_mean, expected_covariance = _oracle(scene.basis, scene.evaluations)
    actual_mean, actual_covariance = _posterior(fake._model)
    assert not np.allclose(actual_mean, expected_mean, rtol=1e-6, atol=1e-8)
    assert not np.allclose(actual_covariance, expected_covariance, rtol=1e-6, atol=1e-8)


def test_scheduled_refit_runs_after_restore(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    """The no-refit continuation rule does not suppress a genuinely due full fit."""
    restored = _restore(scene, scene.artifact)
    original_fit = owner.fit_gpytorch_mll
    calls: list[int] = []

    def record_fit(mll: Any) -> Any:
        calls.append(int(mll.model.train_inputs[0].shape[-2]))
        return original_fit(mll)

    monkeypatch.setattr(owner, "fit_gpytorch_mll", record_fit)
    candidate = restored.suggest(scene.evaluations, attempted_count=58)
    assert candidate.source_strategy == "bayesian_acquisition"
    assert calls == [8]
    assert restored._last_refit_iteration == 58
