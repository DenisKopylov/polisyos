"""Neural search strategy with learned surrogate and cross-run transfer.

Extends ``BaseSearchStrategy`` with:
* GP-based surrogate that can warm-start from historical evaluations
* Integration with ``VectorMemoryStore`` for cross-run knowledge
"""

from __future__ import annotations

import json
import logging
import math
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.methods.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import (
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
        *,
        transfer_manager: TransferLearningManager | None = None,
        transfer_target: RunFingerprint | None = None,
    ) -> None:
        cfg = config or NeuralSearchConfig()
        super().__init__(space, seed=cfg.seed)
        self._config = cfg
        self._memory = memory
        self._warm_data: list[Evaluation] = []
        self._historical: list[Evaluation] = []
        if (transfer_manager is None) != (transfer_target is None):
            raise ValueError("Neural transfer requires a manager and a selected target")
        if transfer_target is not None and (
            not isinstance(transfer_manager, TransferLearningManager)
            or not isinstance(transfer_target, RunFingerprint)
            or transfer_target.space_hash != space.sobol_space_fingerprint()
        ):
            raise ValueError("Neural transfer target does not match its search space")
        self._transfer_manager = transfer_manager
        self._transfer_target = deepcopy(transfer_target)
        self._transfer_sources: list[RunFingerprint] = []
        self._transfer_max_evaluations = 0
        self._surrogate_attempted = False

    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Pre-seed the surrogate with historical evaluations from similar runs.

        These are combined with current-run evaluations when fitting the GP.
        Invalid evaluations (failed, stage A rejected) are filtered out.
        """
        if self._transfer_sources:
            raise ValueError("Cannot mix unbound warm data with a selected transfer corpus")
        valid = [e for e in evaluations if e.is_valid]
        self._warm_data.extend(valid)
        logger.info(
            "Neural strategy warm-started with %d evaluations (%d valid)",
            len(evaluations),
            len(valid),
        )

    def warm_start_from_transfer(
        self, sources: list[RunFingerprint], *, max_evaluations: int
    ) -> None:
        """Bind warm observations to exact selected transfer histories.

        Args:
            sources: Source run identities with selected CAS history profiles.
            max_evaluations: Maximum number of observations to retain.

        Raises:
            ValueError: If the selection or its verified observations are unavailable.
        """
        if self._warm_data or self._transfer_sources:
            raise ValueError("Neural transfer corpus already selected or warm data is unbound")
        selected = deepcopy(sources)
        warm = self._read_transfer(selected, max_evaluations)
        self._transfer_sources = selected
        self._transfer_max_evaluations = max_evaluations
        self._warm_data = deepcopy(warm)

    def _read_transfer(
        self, sources: list[RunFingerprint], max_evaluations: int
    ) -> list[Evaluation]:
        manager, target = self._transfer_manager, self._transfer_target
        if (
            manager is None
            or target is None
            or not sources
            or type(max_evaluations) is not int
            or max_evaluations < 1
            or any(
                not isinstance(source, RunFingerprint)
                or source.history_ref is None
                or source.history_ref.manifest_profile_sha256 is None
                or source.space_hash != self._space.sobol_space_fingerprint()
                for source in sources
            )
        ):
            raise ValueError("Neural transfer requires exact selected history profiles")
        if any(not manager._binding_matches(target, source) for source in sources):
            raise ValueError("Neural transfer source does not match the selected target basis")
        rows = manager.get_warm_start_evaluations(
            sources, max_evals=max_evaluations, target_fingerprint=target
        )
        valid = [row for row in rows if row.is_valid]
        for row in valid:
            try:
                normalized = self._space.normalize(row.params)
                if len(normalized) != len(row.params_normalized) or any(
                    not math.isfinite(value)
                    or not math.isclose(value, expected, rel_tol=0, abs_tol=1e-12)
                    for value, expected in zip(row.params_normalized, normalized, strict=True)
                ):
                    raise ValueError("Neural transfer has inconsistent coordinates")
            except (TypeError, OverflowError) as exc:
                raise ValueError("Neural transfer has invalid coordinates") from exc
        if not valid:
            raise ValueError("Neural transfer has no admitted observations")
        return valid

    @staticmethod
    def _transfer_values(evaluations: list[Evaluation]) -> list[dict[str, Any]]:
        """Compare the fields consumed by neural search; the reader does not restore timestamp."""
        result = []
        for evaluation in evaluations:
            row = TransferLearningManager._serialize_evaluation(evaluation)
            row.pop("timestamp")
            result.append(row)
        return result

    def _verify_warm_transfer(self) -> None:
        if not self._transfer_sources:
            if self._warm_data:
                raise ValueError("Neural checkpoint requires a selected transfer corpus")
            return
        actual = self._read_transfer(self._transfer_sources, self._transfer_max_evaluations)
        if self._encoded_transfer_values(actual) != self._encoded_transfer_values(self._warm_data):
            raise ValueError("Neural transfer observations changed after admission")

    @classmethod
    def _encoded_transfer_values(cls, evaluations: list[Evaluation]) -> str:
        return json.dumps(
            cls._transfer_values(evaluations),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
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
        if self._transfer_sources:
            self._verify_warm_transfer()
        self._iteration += 1
        all_evals = self._warm_data + [e for e in evaluations if e.is_valid]

        if len(all_evals) < self._config.n_initial:
            return self._sobol_candidate(
                max(len(evaluations), self._sobol_cursor),
                source="neural_sobol_init",
            )

        # Try fitting a GP surrogate
        self._surrogate_attempted = True
        try:
            return self._suggest_from_surrogate(all_evals, pending)
        except Exception:
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
        from polisyos.scientist.methods.search.strategies._deps import (
            ExactMarginalLogLikelihood,
            ExpectedImprovement,
            SingleTaskGP,
            Standardize,
            fit_gpytorch_mll,
            optimize_acqf,
            require_botorch,
            require_torch,
        )

        torch = require_torch()
        require_botorch()

        # Build training data
        valid = (
            evaluations[-self._config.transfer_top_k :]
            if self._config.transfer_top_k
            else evaluations
        )
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
            acqf,
            bounds=bounds,
            q=1,
            num_restarts=12,
            raw_samples=256,
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
        if self._surrogate_attempted:
            raise ValueError("Neural fitted-surrogate checkpoint is not established")
        self._verify_warm_transfer()
        state = super().get_state()
        state.metadata.update(
            {
                "neural_state_profile": "neural_sobol_transfer.v1",
                "config": self._config.model_dump(mode="json"),
                "warm_start_count": len(self._warm_data),
                "warm_values": self._transfer_values(self._warm_data),
                "transfer_target": (
                    self._transfer_target.model_dump(mode="json")
                    if self._transfer_sources and self._transfer_target is not None
                    else None
                ),
                "transfer_sources": [
                    source.model_dump(mode="json") for source in self._transfer_sources
                ],
                "max_evaluations": self._transfer_max_evaluations,
            }
        )
        return state

    def set_state(self, state: StrategyState) -> None:
        metadata = state.metadata
        if (
            not isinstance(metadata, dict)
            or metadata.get("neural_state_profile") != ("neural_sobol_transfer.v1")
            or state.model_state is not None
        ):
            raise ValueError("Neural checkpoint lacks a supported Sobol transfer profile")
        config = NeuralSearchConfig.model_validate(metadata.get("config"), strict=True)
        if config.model_dump(exclude={"seed"}) != self._config.model_dump(
            exclude={"seed"}
        ) or config.seed != metadata.get("seed"):
            raise ValueError("Neural checkpoint configuration changed")
        values = metadata.get("warm_values")
        count = metadata.get("warm_start_count")
        raw_sources = metadata.get("transfer_sources")
        maximum = metadata.get("max_evaluations")
        if not isinstance(values, list) or type(count) is not int or count != len(values):
            raise ValueError("Neural checkpoint warm corpus is malformed")
        if not isinstance(raw_sources, list):
            raise ValueError("Neural checkpoint transfer selection is malformed")
        if raw_sources:
            if self._transfer_target is None or metadata.get("transfer_target") != (
                self._transfer_target.model_dump(mode="json")
            ):
                raise ValueError("Neural checkpoint transfer target changed")
            try:
                sources = [RunFingerprint.model_validate(item) for item in raw_sources]
                warm = self._read_transfer(sources, maximum)
            except (TypeError, ValueError) as exc:
                raise ValueError("Neural checkpoint selected history is unavailable") from exc
            if self._encoded_transfer_values(warm) != json.dumps(
                values, sort_keys=True, separators=(",", ":"), allow_nan=False
            ):
                raise ValueError("Neural checkpoint warm corpus differs from selected history")
        else:
            if values or count != 0 or maximum != 0 or metadata.get("transfer_target") is not None:
                raise ValueError("Neural checkpoint unbound warm corpus cannot be restored")
            sources, warm = [], []
        super().set_state(state)
        self._config = config
        self._warm_data = deepcopy(warm)
        self._transfer_sources = sources
        self._transfer_max_evaluations = maximum
        self._surrogate_attempted = False
