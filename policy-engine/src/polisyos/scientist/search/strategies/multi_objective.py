"""Multi-objective Bayesian optimization strategy."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.search.objective import OptimizationDirection
from polisyos.scientist.search.strategies._deps import (
    ExpectedHypervolumeImprovement,
    ModelListGP,
    NondominatedPartitioning,
    Normalize,
    SingleTaskGP,
    Standardize,
    SumMarginalLogLikelihood,
    fit_gpytorch_mll,
    is_non_dominated,
    optimize_acqf,
    qExpectedHypervolumeImprovement,
    require_botorch,
    require_torch,
)
from polisyos.scientist.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.search.strategies.errors import OptionalDependencyUnavailableError
from polisyos.scientist.search.strategies.resource_arbiter import ResourceArbiter
from polisyos.scientist.search.strategies.runtime import apply_torch_runtime_settings
from polisyos.scientist.search.strategies.types import Evaluation, PolicyCandidate, StrategyState

logger = get_logger(__name__)


@dataclass(slots=True)
class MOConfig:
    """Configuration for multi-objective BO."""

    n_initial: int = 10
    ref_point: list[float] | None = None
    ref_point_offset: float = 0.1
    num_restarts: int = 16
    raw_samples: int = 512
    max_train_size: int = 512
    seed: int = 42


class MOBayesianOptimizer(BaseSearchStrategy):
    """Expected-hypervolume-improvement based optimizer."""

    def __init__(
        self,
        space,
        objective_names: list[str],
        directions: list[OptimizationDirection],
        config: MOConfig | None = None,
        resource_arbiter: ResourceArbiter | None = None,
    ):
        if len(objective_names) != len(directions):
            raise ValueError("objective_names and directions lengths must match")
        if not objective_names:
            raise ValueError("At least one objective required")

        cfg = config or MOConfig()
        super().__init__(space=space, seed=cfg.seed)
        self._config = cfg
        self._objective_names = objective_names
        self._directions = directions
        self._negate_mask = [
            -1.0 if direction == OptimizationDirection.MINIMIZE else 1.0 for direction in directions
        ]
        self._arbiter = resource_arbiter or ResourceArbiter.from_env()
        self._ref_point: Any = None
        self._model: Any = None
        self._train_X: Any = None
        self._train_Y: Any = None
        self._torch = None
        self._torch_rng = None
        self._botorch_ready = False
        self._device = "cpu"

        try:
            require_botorch()
            self._torch = require_torch()
            self._device = apply_torch_runtime_settings(self._torch)
            self._torch_rng = self._torch.Generator()
            self._torch_rng.manual_seed(self._config.seed)
            self._botorch_ready = True
        except OptionalDependencyUnavailableError as exc:
            logger.warning("MOBayesianOptimizer dependencies unavailable: {}", exc)
            self._botorch_ready = False

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        del pending
        self._iteration = len(evaluations)
        if len(evaluations) < self._config.n_initial:
            return self._sobol_candidate(len(evaluations), source="sobol_init")
        if not self._botorch_ready:
            return self._random_candidate(source="random_no_botorch")

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return self._random_candidate(source="random_hard_limit")
            train_set = self._select_training_subset(evaluations)
            if len(train_set) < max(3, len(self._objective_names)):
                return self._random_candidate(source="random_insufficient_data")
            try:
                X, Y = self._prepare_training_data(train_set)
                self._fit_model_list(X, Y)
                self._update_ref_point(Y)
                candidate, acq_value = self._optimize_ehvi(soft_limit=soft, batch_size=1)
                return self._tensor_to_candidate(
                    candidate.squeeze(0),
                    source="ehvi",
                    acquisition_value=float(acq_value.squeeze().item()),
                )
            except Exception as exc:
                logger.warning("MO optimization failed; random fallback: {}", exc)
                return self._random_candidate(source="random_fallback")

    def suggest_batch(
        self, evaluations: list[Evaluation], batch_size: int
    ) -> list[PolicyCandidate]:
        if batch_size < 1:
            return []
        if len(evaluations) < self._config.n_initial:
            return [
                self._sobol_candidate(len(evaluations) + idx, source="sobol_init")
                for idx in range(batch_size)
            ]
        if not self._botorch_ready:
            return [self._random_candidate(source="random_no_botorch") for _ in range(batch_size)]

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return [
                    self._random_candidate(source="random_hard_limit") for _ in range(batch_size)
                ]
            train_set = self._select_training_subset(evaluations)
            if len(train_set) < max(3, len(self._objective_names)):
                return [
                    self._random_candidate(source="random_insufficient_data")
                    for _ in range(batch_size)
                ]
            try:
                X, Y = self._prepare_training_data(train_set)
                self._fit_model_list(X, Y)
                self._update_ref_point(Y)
                candidates, _ = self._optimize_ehvi(soft_limit=soft, batch_size=batch_size)
                return [
                    self._tensor_to_candidate(candidates[idx], source="batch_qehvi")
                    for idx in range(batch_size)
                ]
            except Exception as exc:
                logger.warning("MO batch optimization failed; random fallback: {}", exc)
                return [
                    self._random_candidate(source="random_batch_fallback")
                    for _ in range(batch_size)
                ]

    def get_pareto_front(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        valid = [evaluation for evaluation in evaluations if evaluation.is_valid]
        if len(valid) < 2:
            return valid
        points = [self._objective_vector(evaluation) for evaluation in valid]

        if self._botorch_ready:
            tensor = self._torch.tensor(points, dtype=self._torch.float64)
            if self._device != "cpu":
                tensor = tensor.to(self._device)
            mask = is_non_dominated(tensor)
            return [item for item, keep in zip(valid, mask.tolist()) if keep]

        # Pure-Python fallback.
        output: list[Evaluation] = []
        for idx, point in enumerate(points):
            dominated = False
            for jdx, other in enumerate(points):
                if idx == jdx:
                    continue
                if _dominates(other, point):
                    dominated = True
                    break
            if not dominated:
                output.append(valid[idx])
        return output

    def compute_hypervolume(self, evaluations: list[Evaluation]) -> float:
        if not self._botorch_ready:
            return 0.0
        valid = [evaluation for evaluation in evaluations if evaluation.is_valid]
        if not valid:
            return 0.0
        with self._arbiter.acquire("torch"):
            Y = self._torch.tensor(
                [self._objective_vector(evaluation) for evaluation in valid],
                dtype=self._torch.float64,
            )
            if self._device != "cpu":
                Y = Y.to(self._device)
            if self._ref_point is None:
                self._update_ref_point(Y)
            partitioning = NondominatedPartitioning(ref_point=self._ref_point, Y=Y)
            return float(partitioning.compute_hypervolume().item())

    def get_state(self) -> StrategyState:
        model_state: bytes | None = None
        if self._model is not None and self._botorch_ready:
            buffer = io.BytesIO()
            self._torch.save(self._model.state_dict(), buffer)
            model_state = buffer.getvalue()

        rng_state = super().get_state().rng_state
        if self._torch_rng is not None:
            rng_state = {
                **rng_state,
                "torch": self._torch_rng.get_state().tolist(),
            }
        metadata: dict[str, Any] = {
            "config": self._config.__dict__,
            "objective_names": self._objective_names,
            "directions": [direction.value for direction in self._directions],
            "ref_point": self._ref_point.tolist() if self._ref_point is not None else None,
        }
        if self._train_X is not None and self._train_Y is not None:
            metadata["train_X"] = self._train_X.tolist()
            metadata["train_Y"] = self._train_Y.tolist()
        return StrategyState(
            strategy_name="MOBayesianOptimizer",
            iteration=self._iteration,
            rng_state=rng_state,
            model_state=model_state,
            metadata=metadata,
        )

    def set_state(self, state: StrategyState) -> None:
        super().set_state(state)
        if not self._botorch_ready:
            return
        torch_rng_state = state.rng_state.get("torch")
        if self._torch_rng is not None and torch_rng_state is not None:
            self._torch_rng.set_state(self._torch.tensor(torch_rng_state, dtype=self._torch.uint8))
        ref_point = state.metadata.get("ref_point")
        if ref_point is not None:
            self._ref_point = self._torch.tensor(ref_point, dtype=self._torch.float64)
            if self._device != "cpu":
                self._ref_point = self._ref_point.to(self._device)

    def _select_training_subset(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        filtered = [e for e in evaluations if len(e.params_normalized) == self._space.dim]
        if len(filtered) <= self._config.max_train_size:
            return filtered
        recent_n = self._config.max_train_size // 2
        recent = filtered[-recent_n:]
        older = filtered[:-recent_n]
        step = max(1, len(older) // max(1, self._config.max_train_size - recent_n))
        sampled = older[::step][: self._config.max_train_size - recent_n]
        return sampled + recent

    def _prepare_training_data(self, evaluations: list[Evaluation]):
        X = self._torch.tensor(
            [list(e.params_normalized) for e in evaluations],
            dtype=self._torch.float64,
        )
        Y = self._torch.tensor(
            [self._objective_vector(evaluation) for evaluation in evaluations],
            dtype=self._torch.float64,
        )
        if self._device != "cpu":
            X = X.to(self._device)
            Y = Y.to(self._device)
        self._train_X = X
        self._train_Y = Y
        return X, Y

    def _objective_vector(self, evaluation: Evaluation) -> list[float]:
        objective_values = {
            objective.name: objective.raw_value for objective in evaluation.objectives
        }
        output: list[float] = []
        for idx, objective_name in enumerate(self._objective_names):
            raw = float(objective_values.get(objective_name, 0.0))
            output.append(raw * self._negate_mask[idx])
        return output

    def _fit_model_list(self, X, Y) -> None:
        models = [
            SingleTaskGP(
                train_X=X,
                train_Y=Y[:, idx : idx + 1],
                input_transform=Normalize(d=X.shape[-1]),
                outcome_transform=Standardize(m=1),
            )
            for idx in range(len(self._objective_names))
        ]
        self._model = ModelListGP(*models)
        mll = SumMarginalLogLikelihood(self._model.likelihood, self._model)
        fit_gpytorch_mll(mll)

    def _update_ref_point(self, Y) -> None:
        if self._config.ref_point is not None:
            self._ref_point = self._torch.tensor(self._config.ref_point, dtype=self._torch.float64)
            if self._device != "cpu":
                self._ref_point = self._ref_point.to(self._device)
            return
        worst = Y.min(dim=0).values
        best = Y.max(dim=0).values
        offset = self._config.ref_point_offset * (best - worst).abs()
        self._ref_point = worst - offset

    def _optimize_ehvi(self, soft_limit: bool, batch_size: int):
        assert self._model is not None
        assert self._ref_point is not None
        restarts = (
            self._config.num_restarts if not soft_limit else max(4, self._config.num_restarts // 2)
        )
        raw_samples = (
            self._config.raw_samples if not soft_limit else max(128, self._config.raw_samples // 2)
        )

        train_targets = self._train_Y
        partitioning = NondominatedPartitioning(ref_point=self._ref_point, Y=train_targets)
        if batch_size > 1:
            acq = qExpectedHypervolumeImprovement(
                model=self._model,
                ref_point=self._ref_point.tolist(),
                partitioning=partitioning,
            )
        else:
            acq = ExpectedHypervolumeImprovement(
                model=self._model,
                ref_point=self._ref_point.tolist(),
                partitioning=partitioning,
            )
        return optimize_acqf(
            acq_function=acq,
            bounds=self._space.to_botorch_bounds().to(self._device),
            q=batch_size,
            num_restarts=restarts,
            raw_samples=raw_samples,
        )

    def _tensor_to_candidate(
        self,
        tensor,
        source: str,
        acquisition_value: float | None = None,
    ) -> PolicyCandidate:
        vector = tuple(float(value) for value in tensor.detach().cpu().tolist())
        return PolicyCandidate(
            params=self._space.denormalize(vector),
            params_normalized=vector,
            acquisition_value=acquisition_value,
            source_strategy=source,
        )


def _dominates(lhs: list[float], rhs: list[float]) -> bool:
    better_or_equal = all(left >= right for left, right in zip(lhs, rhs))
    strictly_better = any(left > right for left, right in zip(lhs, rhs))
    return better_or_equal and strictly_better
