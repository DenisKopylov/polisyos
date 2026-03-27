"""Neural search strategy with learned surrogate and cross-run transfer.

Extends ``BaseSearchStrategy`` with:
* GP-based surrogate that can warm-start from historical evaluations
* Integration with ``VectorMemoryStore`` for cross-run knowledge
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.search.strategies.space import SearchSpace
from polisyos.scientist.search.strategies.types import (
    Evaluation,
    PolicyCandidate,
    StrategyState,
)

logger = logging.getLogger(__name__)


class NeuralSearchConfig(BaseModel):
    """Configuration for neural search strategy."""

    model_config = ConfigDict(extra="forbid")

    n_initial: int = Field(default=8, ge=1)
    embedding_dim: int = Field(default=64, ge=1)
    transfer_top_k: int = Field(default=50, ge=0)
    surrogate_type: Literal["gp", "ensemble"] = "gp"
    warm_start: bool = True
    seed: int = 42


class NeuralSearchStrategy(BaseSearchStrategy):
    """Search strategy with learned surrogate and cross-run transfer.

    During the initial phase (< ``n_initial`` evaluations), falls back to
    Sobol quasi-random sampling.  Once enough data is collected, fits a
    Gaussian Process surrogate (from BoTorch) and uses Expected Improvement
    acquisition.  Historical evaluations from similar runs can be injected
    via ``warm_start()`` to accelerate convergence.

    Parameters
    ----------
    space:
        The search space definition.
    config:
        Strategy configuration.
    memory:
        Optional ``VectorMemoryStore`` for embedding-based knowledge recall.
    """

    def __init__(
        self,
        space: SearchSpace,
        config: NeuralSearchConfig | None = None,
        memory: Any | None = None,  # VectorMemoryStore
    ) -> None:
        cfg = config or NeuralSearchConfig()
        super().__init__(space, seed=cfg.seed)
        self._config = cfg
        self._memory = memory
        self._warm_data: list[Evaluation] = []
        self._historical: list[Evaluation] = []

    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Pre-seed the surrogate with historical evaluations from similar runs.

        These are combined with current-run evaluations when fitting the GP.
        Invalid evaluations (failed, stage A rejected) are filtered out.
        """
        valid = [e for e in evaluations if e.is_valid]
        self._warm_data.extend(valid)
        logger.info(
            "Neural strategy warm-started with %d evaluations (%d valid)",
            len(evaluations), len(valid),
        )

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        """Suggest the next candidate.

        * If len(evaluations) < n_initial: Sobol quasi-random
        * Otherwise: fit GP surrogate on evaluations + warm-start data,
          optimise EI acquisition, return best candidate.
        """
        self._iteration += 1
        all_evals = self._warm_data + [e for e in evaluations if e.is_valid]

        if len(all_evals) < self._config.n_initial:
            return self._sobol_candidate(
                len(evaluations), source="neural_sobol_init",
            )

        # Try fitting a GP surrogate
        try:
            return self._suggest_from_surrogate(all_evals, pending)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Neural surrogate fitting failed, falling back to random",
                exc_info=True,
            )
            return self._random_candidate(source="neural_fallback")

    def _suggest_from_surrogate(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None,
    ) -> PolicyCandidate:
        """Fit GP and optimise acquisition function."""
        from polisyos.scientist.search.strategies._deps import (
            ExpectedImprovement,
            SingleTaskGP,
            Standardize,
            fit_gpytorch_mll,
            optimize_acqf,
            require_botorch,
            require_torch,
            ExactMarginalLogLikelihood,
        )

        torch = require_torch()
        require_botorch()

        # Build training data
        valid = evaluations[-self._config.transfer_top_k:] if self._config.transfer_top_k else evaluations
        train_x = torch.tensor(
            [list(e.params_normalized) for e in valid if e.params_normalized],
            dtype=torch.double,
        )
        train_y = torch.tensor(
            [[e.scalar_score] for e in valid],
            dtype=torch.double,
        )

        if train_x.shape[0] < 2:
            return self._random_candidate(source="neural_insufficient_data")

        # Fit GP
        model = SingleTaskGP(train_x, train_y, outcome_transform=Standardize(m=1))
        mll = ExactMarginalLogLikelihood(model.likelihood, model)
        fit_gpytorch_mll(mll)

        # Optimise EI
        best_f = train_y.max().item()
        acqf = ExpectedImprovement(model=model, best_f=best_f)

        bounds = torch.zeros(2, self._space.dim, dtype=torch.double)
        bounds[1] = 1.0

        candidate, acq_value = optimize_acqf(
            acqf, bounds=bounds,
            q=1, num_restarts=12, raw_samples=256,
        )

        vector = tuple(candidate.squeeze(0).tolist())
        params = self._space.denormalize(vector)

        return PolicyCandidate(
            params=params,
            params_normalized=vector,
            acquisition_value=acq_value.item(),
            source_strategy="neural_gp",
            metadata={"warm_start_count": len(self._warm_data)},
        )

    def update(self, evaluation: Evaluation) -> None:
        """Track historical evaluations for potential cross-run transfer."""
        self._historical.append(evaluation)

    def get_state(self) -> StrategyState:
        state = super().get_state()
        state.metadata["warm_start_count"] = len(self._warm_data)
        state.metadata["config"] = self._config.model_dump()
        return state

    def set_state(self, state: StrategyState) -> None:
        super().set_state(state)
