"""Single-objective Bayesian optimization strategy."""

from __future__ import annotations

import io
import math
from dataclasses import asdict, dataclass
from typing import Any

from polisyos.common.logger import get_logger

# Imported lazily through _deps to keep module importable without optional stack.
from polisyos.scientist.search.strategies._deps import (  # noqa: E402
    ExactMarginalLogLikelihood,
    ExpectedImprovement,
    Normalize,
    ProbabilityOfImprovement,
    SingleTaskGP,
    Standardize,
    UpperConfidenceBound,
    fit_gpytorch_mll,
    optimize_acqf,
    qExpectedImprovement,
    require_botorch,
    require_torch,
)
from polisyos.scientist.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.search.strategies.errors import OptionalDependencyUnavailableError
from polisyos.scientist.search.strategies.resource_arbiter import ResourceArbiter
from polisyos.scientist.search.strategies.runtime import apply_torch_runtime_settings
from polisyos.scientist.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    PolicyCandidate,
    StrategyState,
)

logger = get_logger(__name__)


@dataclass(slots=True)
class BayesianConfig:
    """Configuration for Bayesian optimization."""

    n_initial: int = 6
    acquisition: AcquisitionType = AcquisitionType.EI
    ucb_beta: float = 2.0
    num_restarts: int = 12
    raw_samples: int = 256
    max_train_size: int = 512
    invalid_penalty: float = 10.0
    seed: int = 42
    fallback_on_failure: bool = True


class BayesianOptimizer(BaseSearchStrategy):
    """Gaussian Process Bayesian optimizer with robust fallback behavior."""

    def __init__(
        self,
        space,
        config: BayesianConfig | None = None,
        resource_arbiter: ResourceArbiter | None = None,
    ):
        cfg = config or BayesianConfig()
        super().__init__(space=space, seed=cfg.seed)
        self._config = cfg
        self._arbiter = resource_arbiter or ResourceArbiter.from_env()
        self._model: Any = None
        self._train_X: Any = None
        self._train_y_bo: Any = None
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
            logger.warning("BayesianOptimizer dependencies unavailable: {}", exc)
            self._botorch_ready = False

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        self._iteration = len(evaluations)
        pending = pending or []

        if len(evaluations) < self._config.n_initial:
            return self._sobol_candidate(len(evaluations), source="sobol_init")

        if not self._botorch_ready:
            return self._non_duplicate_random(pending, source="random_no_botorch")

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return self._non_duplicate_random(pending, source="random_hard_limit")

            train_set = self._select_training_subset(evaluations)
            if len(train_set) < 3:
                return self._non_duplicate_random(pending, source="random_insufficient_data")

            try:
                X, y_bo = self._prepare_training_data(train_set)
                self._fit_gp(X, y_bo)
                candidate, acq_value = self._optimize_acquisition(
                    y_bo=y_bo,
                    soft_limit=soft,
                )
                result = self._tensor_to_candidate(
                    candidate.squeeze(0),
                    source="bayesian_acquisition",
                    acquisition_value=float(acq_value.squeeze().item()),
                )
            except Exception as exc:
                logger.warning("BayesianOptimizer failed; fallback to random: {}", exc)
                if not self._config.fallback_on_failure:
                    raise
                result = self._non_duplicate_random(pending, source="random_fallback")

        if self._is_duplicate(result, pending):
            return self._non_duplicate_random(pending, source="random_duplicate_avoidance")
        return result

    def suggest_batch(self, evaluations: list[Evaluation], batch_size: int) -> list[PolicyCandidate]:
        if batch_size < 1:
            return []

        if len(evaluations) < self._config.n_initial:
            return [
                self._sobol_candidate(len(evaluations) + idx, source="sobol_init")
                for idx in range(batch_size)
            ]

        if not self._botorch_ready:
            return [
                self._non_duplicate_random([], source="random_no_botorch")
                for _ in range(batch_size)
            ]

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return [
                    self._non_duplicate_random([], source="random_hard_limit")
                    for _ in range(batch_size)
                ]

            train_set = self._select_training_subset(evaluations)
            if len(train_set) < 3:
                return [
                    self._non_duplicate_random([], source="random_insufficient_data")
                    for _ in range(batch_size)
                ]

            try:
                X, y_bo = self._prepare_training_data(train_set)
                self._fit_gp(X, y_bo)
                restarts, raw_samples = self._effective_optim_params(soft_limit=soft)
                best_f = y_bo.max()
                acq = qExpectedImprovement(model=self._model, best_f=best_f)
                candidates, _ = optimize_acqf(
                    acq_function=acq,
                    bounds=self._space.to_botorch_bounds().to(self._device),
                    q=batch_size,
                    num_restarts=restarts,
                    raw_samples=raw_samples,
                )
                output: list[PolicyCandidate] = []
                for idx in range(batch_size):
                    output.append(
                        self._tensor_to_candidate(
                            candidates[idx],
                            source="batch_qei",
                        )
                    )
                return output
            except Exception as exc:
                logger.warning("Bayesian batch optimization failed; random fallback: {}", exc)
                return [
                    self._non_duplicate_random([], source="random_batch_fallback")
                    for _ in range(batch_size)
                ]

    def get_state(self) -> StrategyState:
        model_state: bytes | None = None
        if self._model is not None and self._botorch_ready:
            buffer = io.BytesIO()
            self._torch.save(self._model.state_dict(), buffer)
            model_state = buffer.getvalue()

        metadata: dict[str, Any] = {"config": asdict(self._config)}
        if self._train_X is not None and self._train_y_bo is not None:
            metadata["train_X"] = self._train_X.tolist()
            metadata["train_y_bo"] = self._train_y_bo.tolist()

        rng_state = super().get_state().rng_state
        if self._torch_rng is not None:
            rng_state = {
                **rng_state,
                "torch": self._torch_rng.get_state().tolist(),
            }
        return StrategyState(
            strategy_name="BayesianOptimizer",
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

        train_X_list = state.metadata.get("train_X")
        train_y_list = state.metadata.get("train_y_bo")
        if train_X_list is None or train_y_list is None:
            return
        self._train_X = self._torch.tensor(train_X_list, dtype=self._torch.float64)
        self._train_y_bo = self._torch.tensor(train_y_list, dtype=self._torch.float64)
        if self._device != "cpu":
            self._train_X = self._train_X.to(self._device)
            self._train_y_bo = self._train_y_bo.to(self._device)
        if state.model_state is None:
            return
        self._model = SingleTaskGP(
            train_X=self._train_X,
            train_Y=self._train_y_bo,
            input_transform=Normalize(d=self._train_X.shape[-1]),
            outcome_transform=Standardize(m=1),
        )
        buffer = io.BytesIO(state.model_state)
        self._model.load_state_dict(self._torch.load(buffer))

    def _select_training_subset(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        filtered = [e for e in evaluations if len(e.params_normalized) == self._space.dim]
        if len(filtered) <= self._config.max_train_size:
            return filtered
        # Keep recent half + uniformly sampled remainder for diversity.
        recent_n = self._config.max_train_size // 2
        recent = filtered[-recent_n:]
        older = filtered[:-recent_n]
        step = max(1, len(older) // max(1, self._config.max_train_size - recent_n))
        sampled = older[::step][: self._config.max_train_size - recent_n]
        return sampled + recent

    def _prepare_training_data(self, evaluations: list[Evaluation]):
        valid_scores = [
            e.scalar_score
            for e in evaluations
            if e.is_valid and math.isfinite(e.scalar_score)
        ]
        if not valid_scores:
            raise RuntimeError("No valid objective values available for GP fitting")

        worst_valid = max(valid_scores)
        penalty = self._config.invalid_penalty
        x_rows: list[list[float]] = []
        y_search: list[float] = []
        for evaluation in evaluations:
            x_rows.append(list(evaluation.params_normalized))
            if evaluation.is_valid and math.isfinite(evaluation.scalar_score):
                y_search.append(float(evaluation.scalar_score))
            else:
                y_search.append(float(worst_valid + penalty))

        X = self._torch.tensor(x_rows, dtype=self._torch.float64)
        y_bo = self._torch.tensor([[-score] for score in y_search], dtype=self._torch.float64)
        if self._device != "cpu":
            X = X.to(self._device)
            y_bo = y_bo.to(self._device)
        self._train_X = X
        self._train_y_bo = y_bo
        return X, y_bo

    def _fit_gp(self, X, y_bo) -> None:
        self._model = SingleTaskGP(
            train_X=X,
            train_Y=y_bo,
            input_transform=Normalize(d=X.shape[-1]),
            outcome_transform=Standardize(m=1),
        )
        mll = ExactMarginalLogLikelihood(self._model.likelihood, self._model)
        fit_gpytorch_mll(mll)

    def _optimize_acquisition(self, y_bo, soft_limit: bool):
        best_f = y_bo.max()
        if self._config.acquisition == AcquisitionType.UCB:
            acq = UpperConfidenceBound(model=self._model, beta=self._config.ucb_beta)
        elif self._config.acquisition == AcquisitionType.PI:
            acq = ProbabilityOfImprovement(model=self._model, best_f=best_f)
        else:
            acq = ExpectedImprovement(model=self._model, best_f=best_f)

        restarts, raw_samples = self._effective_optim_params(soft_limit=soft_limit)
        return optimize_acqf(
            acq_function=acq,
            bounds=self._space.to_botorch_bounds().to(self._device),
            q=1,
            num_restarts=restarts,
            raw_samples=raw_samples,
        )

    def _effective_optim_params(self, soft_limit: bool) -> tuple[int, int]:
        if not soft_limit:
            return self._config.num_restarts, self._config.raw_samples
        return max(3, self._config.num_restarts // 2), max(64, self._config.raw_samples // 2)

    def _non_duplicate_random(
        self,
        pending: list[PolicyCandidate],
        source: str,
        attempts: int = 20,
    ) -> PolicyCandidate:
        for _ in range(attempts):
            candidate = self._random_candidate(source=source)
            if not self._is_duplicate(candidate, pending):
                return candidate
        return self._random_candidate(source=source)

    def _is_duplicate(self, candidate: PolicyCandidate, pending: list[PolicyCandidate]) -> bool:
        if candidate.params_normalized is None:
            return False
        for other in pending:
            if other.params_normalized is None:
                continue
            if len(candidate.params_normalized) != len(other.params_normalized):
                continue
            dist = sum(
                (a - b) ** 2 for a, b in zip(candidate.params_normalized, other.params_normalized)
            )
            if dist <= 1e-10:
                return True
        return False

    def _tensor_to_candidate(
        self,
        tensor,
        source: str,
        acquisition_value: float | None = None,
    ) -> PolicyCandidate:
        vector = tuple(float(value) for value in tensor.detach().cpu().tolist())
        params = self._space.denormalize(vector)
        predicted_mean: float | None = None
        predicted_std: float | None = None
        if self._model is not None:
            with self._torch.no_grad():
                posterior = self._model.posterior(tensor.unsqueeze(0))
                mean_bo = float(posterior.mean.squeeze().item())
                std_bo = float(posterior.variance.sqrt().squeeze().item())
                predicted_mean = -mean_bo
                predicted_std = abs(std_bo)
        return PolicyCandidate(
            params=params,
            params_normalized=vector,
            acquisition_value=acquisition_value,
            predicted_mean=predicted_mean,
            predicted_std=predicted_std,
            source_strategy=source,
        )
