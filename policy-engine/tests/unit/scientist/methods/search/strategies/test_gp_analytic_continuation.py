"""Independent dense Gaussian conditioning oracle for the locked native GP.

These are synthetic analytic observations, not production history.  Expected
values use only saved scalar parameters and explicit NumPy matrices.  Neither
the model's posterior nor its kernel/transform methods calculate an expectation.
The supported profile is BoTorch's ConstantMean / unit-amplitude RBF /
homoskedastic GaussianLikelihood with Normalize and Standardize, in float64.
"""

from __future__ import annotations

import copy
import inspect
import io
import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies import bayesian as bayesian_module
from polisyos.scientist.methods.search.strategies._deps import require_botorch, require_torch
from polisyos.scientist.methods.search.strategies.bayesian import BayesianConfig, BayesianOptimizer
from polisyos.scientist.methods.search.strategies.errors import OptionalDependencyUnavailableError
from polisyos.scientist.methods.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourcePolicy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    EvaluationStatus,
    ParameterBounds,
    StrategyState,
)

POINTS = (0.08, 0.16, 0.23, 0.35, 0.42, 0.50, 0.61, 0.70, 0.82, 0.93)
APPEND_POINT = 0.975
QUERIES = (0.015, 0.12, 0.29, 0.465, 0.655, 0.885, 0.99)
RTOL = 2e-7
ATOL = 2e-8
CONTEXT = "synthetic-analytic-cost/oracle-v1"
TIMESTAMP = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


def _score(x: float) -> float:
    """Declared cost in objective units; positive offset and nonunit scale."""
    return 50.0 + 9.0 * math.sin(5.0 * x) + 6.0 * x


def _evaluation(space: SearchSpace, x: float, identity: str, *, warm: bool = False) -> Evaluation:
    score = _score(x)
    metadata = {"replicate_id": identity, "seed": 31}
    if warm:
        metadata["warm_start_compatibility"] = {
            "search_space_fingerprint": space.sobol_space_fingerprint(),
            "input_transform_fingerprint": "Normalize[0,1]",
            "outcome_transform_fingerprint": "Standardize[m=1]",
            "noise_model_fingerprint": "GaussianLikelihood[inferred]",
            "objective_fingerprint": "scalar_score[minimize]",
            "context_fingerprint": CONTEXT,
        }
    return Evaluation(
        candidate_id=identity,
        params={"x": x},
        params_normalized=(x,),
        objectives=[ObjectiveValue("analytic_cost", score, OptimizationDirection.MINIMIZE)],
        scalar_score=score,
        stage_a_passed=True,
        timestamp=TIMESTAMP,
        provenance_ref=f"synthetic-analytic/{identity}",
        metadata=metadata,
    )


def _strategy(space: SearchSpace, *, interval: int = 100) -> BayesianOptimizer:
    basis = {
        "profile": "synthetic_scalar_gp.v1",
        "search_space_fingerprint": space.sobol_space_fingerprint(),
        "context_fingerprint": CONTEXT,
        "metric": "analytic_cost",
        "unit": "analytic_cost_units",
        "direction": "minimize",
    }
    # Preserve a useful numerical baseline on the published predecessor.  The
    # separate required-interface assertion below keeps its absent target
    # configuration visibly FAIL; this compatibility branch cannot pass it.
    configured_basis = (
        {"numerical_basis": basis, "warm_start_admission": None}
        if "numerical_basis" in inspect.signature(BayesianOptimizer).parameters
        else {}
    )
    return BayesianOptimizer(
        space,
        BayesianConfig(
            n_initial=6,
            acquisition=AcquisitionType.UCB,
            num_restarts=1,
            raw_samples=16,
            max_train_size=64,
            seed=31,
            fallback_on_failure=False,
            refit_interval=interval,
        ),
        ResourceArbiter(
            ResourcePolicy(soft_rss_mb=1_000_000, hard_rss_mb=2_000_000, enable_cleanup=False)
        ),
        **configured_basis,
    )


def _roundtrip(state: StrategyState, path: Path) -> StrategyState:
    path.write_bytes(state.to_artifact())
    return StrategyState.from_artifact(path.read_bytes())


def _weights(state: StrategyState) -> dict:
    assert state.model_state is not None, "A fitted checkpoint must contain actual learned state"
    return require_torch().load(io.BytesIO(state.model_state), weights_only=True)


def _scalar(weights: dict, name: str) -> float:
    value = weights[name].detach().cpu().numpy()
    assert value.size == 1, f"Oracle profile requires scalar {name}"
    return float(value.reshape(-1)[0])


def _dense_expected(
    reference: StrategyState,
    x: tuple[float, ...],
    *,
    observation_noise: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Cholesky solve in standardized units, then return original cost units.

    raw_y_bo is negative cost (native maximization convention).  The sign of
    predictive mean is reversed at the end; covariance is unchanged by sign.
    All transforms are explicit arithmetic on persisted fitted scalar buffers.
    """
    weights = _weights(reference)
    lengthscale = _scalar(weights, "covar_module.raw_lengthscale")
    noise_variance = _scalar(weights, "likelihood.noise_covar.raw_noise")
    constant_mean = _scalar(weights, "mean_module.raw_constant")
    offset = _scalar(weights, "input_transform._offset")
    coefficient = _scalar(weights, "input_transform._coefficient")
    outcome_mean = _scalar(weights, "outcome_transform.means")
    outcome_std = _scalar(weights, "outcome_transform.stdvs")
    assert lengthscale > 0 and noise_variance > 0 and coefficient > 0 and outcome_std > 0
    assert _scalar(weights, "outcome_transform._stdvs_sq") == pytest.approx(outcome_std**2)
    raw_x = np.asarray(x, dtype=np.float64)
    raw_y_bo = -np.asarray([_score(value) for value in x], dtype=np.float64)
    assert len(x) in (10, 11) and len(set(x)) == len(x)
    assert np.isfinite(raw_x).all() and np.isfinite(raw_y_bo).all()
    transformed_x = (raw_x - offset) / coefficient
    transformed_q = (np.asarray(QUERIES, dtype=np.float64) - offset) / coefficient
    transformed_y = (raw_y_bo - outcome_mean) / outcome_std

    def rbf(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        squared_distance = ((left[:, None] - right[None, :]) / lengthscale) ** 2
        return np.exp(-0.5 * squared_distance)

    covariance = rbf(transformed_x, transformed_x) + noise_variance * np.eye(len(x))
    cross_covariance = rbf(transformed_q, transformed_x)
    lower = np.linalg.cholesky(covariance)
    alpha = np.linalg.solve(lower.T, np.linalg.solve(lower, transformed_y - constant_mean))
    standardized_mean = constant_mean + cross_covariance @ alpha
    solved_cross = np.linalg.solve(lower, cross_covariance.T)
    standardized_covariance = rbf(transformed_q, transformed_q) - solved_cross.T @ solved_cross
    if observation_noise:
        standardized_covariance += noise_variance * np.eye(len(QUERIES))
    original_cost_mean = -(outcome_mean + outcome_std * standardized_mean)
    original_covariance = outcome_std**2 * standardized_covariance
    assert np.isfinite(original_cost_mean).all() and np.isfinite(original_covariance).all()
    np.testing.assert_allclose(original_covariance, original_covariance.T, atol=1e-12)
    assert np.linalg.eigvalsh(original_covariance).min() > -1e-10
    assert np.max(np.abs(original_covariance - np.diag(np.diag(original_covariance)))) > 1e-8
    return original_cost_mean, original_covariance


def _actual(model, *, observation_noise: bool = False) -> tuple[np.ndarray, np.ndarray]:
    import gpytorch

    torch = require_torch()
    query = torch.tensor(QUERIES, dtype=torch.float64).reshape(-1, 1)
    model.eval()
    with (
        torch.no_grad(),
        gpytorch.settings.fast_pred_var(False),
        gpytorch.settings.fast_computations(
            covar_root_decomposition=False, log_prob=False, solves=False
        ),
    ):
        posterior = model.posterior(query, observation_noise=observation_noise)
        return (
            -posterior.mean.detach().cpu().numpy().reshape(-1),
            posterior.distribution.covariance_matrix.detach().cpu().numpy(),
        )


def _assert_matches(model, reference: StrategyState, x: tuple[float, ...]) -> None:
    for observation_noise in (False, True):
        expected_mean, expected_covariance = _dense_expected(
            reference, x, observation_noise=observation_noise
        )
        actual_mean, actual_covariance = _actual(model, observation_noise=observation_noise)
        np.testing.assert_allclose(actual_mean, expected_mean, rtol=RTOL, atol=ATOL)
        np.testing.assert_allclose(actual_covariance, expected_covariance, rtol=RTOL, atol=ATOL)


def _assert_profile(model) -> None:
    from gpytorch.kernels import RBFKernel
    from gpytorch.likelihoods import GaussianLikelihood
    from gpytorch.means import ConstantMean

    assert isinstance(model.covar_module, RBFKernel), "UNRUN: unsupported locked kernel profile"
    assert isinstance(model.mean_module, ConstantMean)
    assert isinstance(model.likelihood, GaussianLikelihood)
    # These locked constraints use identity rather than softplus.  A changed
    # profile must be declared; interpreting transformed raw values silently is wrong.
    assert model.covar_module.raw_lengthscale_constraint.enforced is False
    assert model.likelihood.noise_covar.raw_noise_constraint.enforced is False


@dataclass
class AnalyticCase:
    space: SearchSpace
    warm: list[Evaluation]
    current: list[Evaluation]
    appended: Evaluation
    initial: StrategyState
    conditioned: StrategyState
    initial_model: object
    conditioned_model: object
    initial_fit_calls: int
    append_fit_calls: int
    conditioning_rows: list[tuple[list, list]]


@pytest.fixture(scope="module")
def analytic_case(tmp_path_factory: pytest.TempPathFactory) -> AnalyticCase:
    try:
        require_botorch()
        torch = require_torch()
    except OptionalDependencyUnavailableError as exc:
        pytest.skip(f"UNRUN: actual optional BoTorch/GPyTorch backend unavailable: {exc}")
    directory = tmp_path_factory.mktemp("gp-independent-analytic")
    space = SearchSpace([ParameterBounds("x", lower=0.0, upper=1.0)])
    warm = [_evaluation(space, x, f"warm-{index}", warm=True) for index, x in enumerate(POINTS[:8])]
    current = [_evaluation(space, x, f"current-{index}") for index, x in enumerate(POINTS[8:])]
    appended = _evaluation(space, APPEND_POINT, "current-append")
    strategy = _strategy(space)
    strategy._sobol_candidate(3)
    strategy._random_candidate(source="analytic-rng-prelude")
    strategy.warm_start(warm)
    conditioning_rows = []
    real_condition = bayesian_module.SingleTaskGP.condition_on_observations

    def observe_real_condition(model, *args, **kwargs):
        conditioning_rows.append(
            (kwargs["X"].detach().cpu().tolist(), kwargs["Y"].detach().cpu().tolist())
        )
        return real_condition(model, *args, **kwargs)

    with patch.object(
        bayesian_module, "fit_gpytorch_mll", wraps=bayesian_module.fit_gpytorch_mll
    ) as fit:
        candidate = strategy.suggest(current)
        assert candidate.source_strategy == "bayesian_acquisition"
        initial_fit_calls = fit.call_count
        assert strategy._model is not None
        _assert_profile(strategy._model)
        for parameter in strategy._model.parameters():
            parameter.requires_grad_(False)
        initial_model = strategy._model
        initial = _roundtrip(strategy.get_state(), directory / "initial.json")
        with patch.object(
            bayesian_module.SingleTaskGP, "condition_on_observations", new=observe_real_condition
        ):
            strategy.suggest([*current, appended])
        append_fit_calls = fit.call_count - initial_fit_calls
        conditioned = _roundtrip(strategy.get_state(), directory / "conditioned.json")
    assert strategy._model is not None
    assert torch.equal(
        initial_model.mean_module.raw_constant, strategy._model.mean_module.raw_constant
    )
    return AnalyticCase(
        space,
        warm,
        current,
        appended,
        initial,
        conditioned,
        initial_model,
        strategy._model,
        initial_fit_calls,
        append_fit_calls,
        conditioning_rows,
    )


def _restore(case: AnalyticCase, state: StrategyState | None = None) -> BayesianOptimizer:
    strategy = _strategy(case.space)
    strategy.set_state(copy.deepcopy(state or case.initial))
    assert strategy._model is not None
    return strategy


def _assert_unchanged(strategy: BayesianOptimizer, before: StrategyState) -> None:
    after = strategy.get_state()
    assert after.strategy_name == before.strategy_name and after.iteration == before.iteration
    assert after.rng_state == before.rng_state and after.metadata == before.metadata
    before_weights, after_weights = _weights(before), _weights(after)
    assert before_weights.keys() == after_weights.keys()
    for key in before_weights:
        assert require_torch().equal(before_weights[key], after_weights[key]), key


def test_real_initial_fit_matches_independent_original_unit_full_covariance(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    assert case.initial_fit_calls == 1
    weights = _weights(case.initial)
    assert _scalar(weights, "input_transform._offset") == pytest.approx(0.08)
    assert _scalar(weights, "input_transform._coefficient") == pytest.approx(0.85)
    assert abs(_scalar(weights, "outcome_transform.means")) > 1
    assert _scalar(weights, "outcome_transform.stdvs") != pytest.approx(1.0)
    raw_y_bo = -np.asarray([_score(x) for x in POINTS], dtype=np.float64)
    assert _scalar(weights, "outcome_transform.means") == pytest.approx(raw_y_bo.mean())
    assert _scalar(weights, "outcome_transform.stdvs") == pytest.approx(raw_y_bo.std(ddof=1))
    np.testing.assert_array_equal(np.asarray(case.initial.metadata["train_X"]).reshape(-1), POINTS)
    np.testing.assert_allclose(
        np.asarray(case.initial.metadata["train_y_bo"]).reshape(-1),
        [-_score(x) for x in POINTS],
        atol=1e-12,
    )
    _assert_matches(case.initial_model, case.initial, POINTS)
    mean, covariance = _dense_expected(case.initial, POINTS)
    print(
        json.dumps(
            {
                "cell": "initial-ten-point-independent-oracle",
                "x": POINTS,
                "queries": QUERIES,
                "expected_cost_mean": mean.tolist(),
                "expected_full_covariance": covariance.tolist(),
                "real_mll_calls": case.initial_fit_calls,
                "saved_scalar_parameters": {
                    name: _scalar(weights, name)
                    for name in (
                        "covar_module.raw_lengthscale",
                        "likelihood.noise_covar.raw_noise",
                        "mean_module.raw_constant",
                        "input_transform._offset",
                        "input_transform._coefficient",
                        "outcome_transform.means",
                        "outcome_transform.stdvs",
                    )
                },
            }
        )
    )


def test_warm_target_basis_is_explicitly_configurable() -> None:
    assert "numerical_basis" in inspect.signature(BayesianOptimizer).parameters, (
        "A warm row cannot choose its own receiver target basis"
    )


def test_actual_append_conditions_without_refit_and_matches_eleven_row_oracle(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    assert case.append_fit_calls == 0
    assert len(case.conditioning_rows) == 1
    np.testing.assert_allclose(case.conditioning_rows[0][0], [[APPEND_POINT]], atol=1e-12)
    np.testing.assert_allclose(case.conditioning_rows[0][1], [[-_score(APPEND_POINT)]], atol=1e-12)
    initial_weights, appended_weights = _weights(case.initial), _weights(case.conditioned)
    for key in initial_weights:
        if key.startswith(
            (
                "mean_module.",
                "covar_module.",
                "likelihood.",
                "input_transform.",
                "outcome_transform.",
            )
        ):
            assert require_torch().equal(initial_weights[key], appended_weights[key]), key
    _assert_matches(case.conditioned_model, case.initial, (*POINTS, APPEND_POINT))
    before, _ = _dense_expected(case.initial, POINTS)
    after, covariance = _dense_expected(case.initial, (*POINTS, APPEND_POINT))
    assert np.max(np.abs(after - before)) > 1e-5
    print(
        json.dumps(
            {
                "cell": "actual-eleven-point-conditioning",
                "append": APPEND_POINT,
                "expected_cost_mean": after.tolist(),
                "expected_full_covariance": covariance.tolist(),
                "extra_real_mll_calls": case.append_fit_calls,
            }
        )
    )


def test_conditioned_checkpoint_restores_saved_transform_basis_before_targets(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    with patch.object(
        bayesian_module, "fit_gpytorch_mll", wraps=bayesian_module.fit_gpytorch_mll
    ) as fit:
        restored = _restore(case, case.conditioned)
        _assert_matches(restored._model, case.initial, (*POINTS, APPEND_POINT))
        assert fit.call_count == 0


def test_restored_warm_corpus_noop_and_append_do_not_refit(analytic_case: AnalyticCase) -> None:
    case = analytic_case
    with patch.object(
        bayesian_module, "fit_gpytorch_mll", wraps=bayesian_module.fit_gpytorch_mll
    ) as fit:
        restored = _restore(case)
        assert (
            restored.suggest(copy.deepcopy(case.current)).source_strategy == "bayesian_acquisition"
        )
        _assert_matches(restored._model, case.initial, POINTS)
        assert (
            restored.suggest(
                [*copy.deepcopy(case.current), copy.deepcopy(case.appended)]
            ).source_strategy
            == "bayesian_acquisition"
        )
        _assert_matches(restored._model, case.initial, (*POINTS, APPEND_POINT))
        assert fit.call_count == 0


def test_changed_existing_outcome_requires_real_refit(analytic_case: AnalyticCase) -> None:
    case = analytic_case
    restored = _restore(case)
    changed = copy.deepcopy(case.current)
    changed[-1].scalar_score += 2.0
    changed[-1].objectives = [
        ObjectiveValue("analytic_cost", changed[-1].scalar_score, OptimizationDirection.MINIMIZE)
    ]
    with patch.object(
        bayesian_module, "fit_gpytorch_mll", wraps=bayesian_module.fit_gpytorch_mll
    ) as fit:
        assert restored.suggest(changed).source_strategy == "bayesian_acquisition"
        assert fit.call_count > 0


def test_explicit_due_cadence_performs_real_refit_after_restore(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    producer = _strategy(case.space, interval=1)
    producer.warm_start(copy.deepcopy(case.warm))
    with patch.object(
        bayesian_module, "fit_gpytorch_mll", wraps=bayesian_module.fit_gpytorch_mll
    ) as fit:
        assert (
            producer.suggest(copy.deepcopy(case.current)).source_strategy == "bayesian_acquisition"
        )
        assert fit.call_count == 1
        saved = StrategyState.from_artifact(producer.get_state().to_artifact())
        restored = _strategy(case.space, interval=1)
        restored.set_state(saved)
        assert fit.call_count == 1
        assert (
            restored.suggest(
                [*copy.deepcopy(case.current), copy.deepcopy(case.appended)]
            ).source_strategy
            == "bayesian_acquisition"
        )
        assert fit.call_count > 1


def test_same_checkpoint_acquisition_is_independent_of_ambient_torch_rng(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    torch = require_torch()
    ambient = torch.get_rng_state()
    try:
        proposals = []
        with patch.object(
            bayesian_module, "fit_gpytorch_mll", wraps=bayesian_module.fit_gpytorch_mll
        ) as fit:
            for seed in (4101, 9917):
                restored = _restore(case)
                torch.manual_seed(seed)
                candidate = restored.suggest(copy.deepcopy(case.current))
                assert candidate.source_strategy == "bayesian_acquisition"
                proposals.append(candidate.params_normalized)
            assert fit.call_count == 0
        np.testing.assert_allclose(proposals[0], proposals[1], rtol=0, atol=1e-12)
    finally:
        torch.set_rng_state(ambient)


@pytest.mark.parametrize(
    "field",
    ["covar_module.raw_lengthscale", "outcome_transform.means", "input_transform._coefficient"],
)
def test_same_marker_fitted_parameter_or_transform_changes_prediction_or_refuses(
    analytic_case: AnalyticCase, field: str
) -> None:
    case = analytic_case
    changed = copy.deepcopy(case.initial)
    weights = _weights(changed)
    weights[field] = weights[field] + (0.15 if "lengthscale" in field else 0.2)
    buffer = io.BytesIO()
    require_torch().save(weights, buffer)
    changed.model_state = buffer.getvalue()
    restored = _restore(case)
    before = restored.get_state()
    try:
        restored.set_state(changed)
    except ValueError:
        _assert_unchanged(restored, before)
        return
    expected_mean, expected_covariance = _dense_expected(case.initial, POINTS)
    actual_mean, actual_covariance = _actual(restored._model)
    assert not (
        np.allclose(actual_mean, expected_mean, rtol=RTOL, atol=ATOL)
        and np.allclose(actual_covariance, expected_covariance, rtol=RTOL, atol=ATOL)
    ), "Changed fitted state was ignored despite unchanged identity markers"


def _warm_row(value):
    if isinstance(value, dict):
        if value.get("candidate_id") == "warm-0":
            return value
        for child in value.values():
            result = _warm_row(child)
            if result is not None:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _warm_row(child)
            if result is not None:
                return result
    return None


def test_same_marker_warm_row_changes_corpus_or_refuses_atomically(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    changed = copy.deepcopy(case.initial)
    row = _warm_row(changed.metadata)
    assert row is not None, (
        "Checkpoint must persist its actual typed warm rows, not just a compatibility marker"
    )
    row["scalar_score"] += 3.0
    restored = _restore(case)
    before = restored.get_state()
    try:
        restored.set_state(changed)
        candidate = restored.suggest(copy.deepcopy(case.current))
    except ValueError:
        _assert_unchanged(restored, before)
        return
    assert candidate.source_strategy == "bayesian_acquisition"
    expected_mean, expected_covariance = _dense_expected(case.initial, POINTS)
    actual_mean, actual_covariance = _actual(restored._model)
    assert not (
        np.allclose(actual_mean, expected_mean, rtol=RTOL, atol=ATOL)
        and np.allclose(actual_covariance, expected_covariance, rtol=RTOL, atol=ATOL)
    ), "A changed actual warm row was silently ignored"


def test_valid_saved_python_rng_mutation_changes_native_random_proposal_or_refuses(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    changed = copy.deepcopy(case.initial)
    changed.rng_state["python"]["state"] = list(random.Random(9103).getstate()[1])  # noqa: S311 - deterministic RNG codec fixture
    baseline = _restore(case)._random_candidate(source="analytic-rng-control")
    restored = _restore(case)
    before = restored.get_state()
    try:
        restored.set_state(changed)
    except ValueError:
        _assert_unchanged(restored, before)
        return
    mutated = restored._random_candidate(source="analytic-rng-control")
    assert mutated.params_normalized != baseline.params_normalized


def test_saved_torch_rng_mutation_reaches_actual_acquisition_or_refuses(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    torch = require_torch()
    changed = copy.deepcopy(case.initial)
    generator = torch.Generator()
    generator.manual_seed(9103)
    changed.rng_state["torch"] = generator.get_state().tolist()
    observed = []
    real_optimize = bayesian_module.optimize_acqf

    def observe_real_acquisition(*args, **kwargs):
        observed.append(torch.get_rng_state().clone())
        return real_optimize(*args, **kwargs)

    ambient = torch.get_rng_state()
    try:
        with patch.object(bayesian_module, "optimize_acqf", side_effect=observe_real_acquisition):
            for state in (case.initial, changed):
                restored = _restore(case)
                before = restored.get_state()
                try:
                    restored.set_state(copy.deepcopy(state))
                except ValueError:
                    _assert_unchanged(restored, before)
                    return
                torch.manual_seed(7711)
                assert (
                    restored.suggest(copy.deepcopy(case.current)).source_strategy
                    == "bayesian_acquisition"
                )
        assert len(observed) == 2
        assert not torch.equal(observed[0], observed[1]), (
            "Saved Torch RNG was ignored by the actual acquisition consumer"
        )
    finally:
        torch.set_rng_state(ambient)


@pytest.mark.parametrize(
    "mutation",
    [
        "iteration-bool",
        "model-state-bool",
        "python-codec-bool",
        "sobol-algorithm-bool",
        "torch-byte-bool",
    ],
)
def test_checkpoint_type_mutations_are_refused_without_partial_restore(
    analytic_case: AnalyticCase, mutation: str
) -> None:
    case = analytic_case
    payload = json.loads(case.initial.to_artifact())
    if mutation == "iteration-bool":
        payload["iteration"] = True
    elif mutation == "model-state-bool":
        payload["model_state"] = False
    elif mutation == "python-codec-bool":
        payload["rng_state"]["python"]["codec_version"] = True
    elif mutation == "sobol-algorithm-bool":
        payload["rng_state"]["sobol"]["algorithm_version"] = True
    else:
        payload["rng_state"]["torch"][0] = True
    restored = _restore(case)
    before = restored.get_state()
    with pytest.raises(ValueError):
        restored.set_state(StrategyState.from_artifact(json.dumps(payload).encode()))
    _assert_unchanged(restored, before)


def test_omitting_fitted_state_load_is_detected_by_independent_oracle(
    analytic_case: AnalyticCase,
) -> None:
    from botorch.models import SingleTaskGP

    case = analytic_case
    restored = _restore(case)
    with patch.object(SingleTaskGP, "load_state_dict", return_value=None):
        try:
            restored.set_state(copy.deepcopy(case.initial))
        except ValueError:
            return
    with pytest.raises(AssertionError):
        _assert_matches(restored._model, case.initial, POINTS)


def test_invalid_outcomes_are_excluded_instead_of_fabricated_penalties(
    analytic_case: AnalyticCase,
) -> None:
    case = analytic_case
    strategy = _strategy(case.space)
    strategy.warm_start(copy.deepcopy(case.warm))
    bad = [
        _evaluation(case.space, 0.30, "invalid-nonfinite"),
        _evaluation(case.space, 0.55, "invalid-stage-a"),
        _evaluation(case.space, 0.76, "invalid-stage-b"),
        _evaluation(case.space, 0.87, "missing-outcome"),
    ]
    bad[0].scalar_score = math.nan
    bad[1].stage_a_passed = False
    bad[2].status = EvaluationStatus.STAGE_B_ERROR
    bad[3].objectives = []
    bad[3].scalar_score = math.nan
    with patch.object(
        bayesian_module, "fit_gpytorch_mll", wraps=bayesian_module.fit_gpytorch_mll
    ) as fit:
        candidate = strategy.suggest([*copy.deepcopy(case.current), *bad])
        assert candidate.source_strategy == "bayesian_acquisition"
        assert fit.call_count == 1
    state = strategy.get_state()
    np.testing.assert_array_equal(np.asarray(state.metadata["train_X"]).reshape(-1), POINTS)
    _assert_matches(strategy._model, state, POINTS)
