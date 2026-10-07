"""Neural search strategy with learned surrogate and cross-run transfer.

Extends ``BaseSearchStrategy`` with:
* GP-based surrogate that can warm-start from historical evaluations
* Integration with ``VectorMemoryStore`` for cross-run knowledge
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import canon
from polisyos.scientist.methods.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import (
    NumericTransferBasis,
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
        numerical_basis: NumericTransferBasis | None = None,
        warm_start_admission: Callable[[list[Evaluation], NumericTransferBasis], list[Evaluation]]
        | None = None,
    ) -> None:
        cfg = config or NeuralSearchConfig()
        super().__init__(space, seed=cfg.seed)
        self._config = cfg
        self._memory = memory
        self._warm_data: list[Evaluation] = []
        self._historical: list[Evaluation] = []
        if (numerical_basis is None) != (warm_start_admission is None):
            raise ValueError("Neural warm transfer requires both target basis and CAS reader")
        if numerical_basis is not None and (
            not isinstance(numerical_basis, NumericTransferBasis)
            or not callable(warm_start_admission)
            or numerical_basis.search_space_fingerprint != space.sobol_space_fingerprint()
        ):
            raise ValueError("Neural target numerical basis is incompatible with this space")
        self._numerical_basis = numerical_basis
        self._warm_start_admission = warm_start_admission
        self.last_warm_start_report: list[dict[str, str]] = []

    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Pre-seed the surrogate with historical evaluations from similar runs.

        These are combined with current-run evaluations when fitting the GP.
        Invalid evaluations (failed, stage A rejected) are filtered out.
        """
        self.last_warm_start_report = []
        if self._numerical_basis is None:
            self.last_warm_start_report = [
                {"candidate_id": e.candidate_id, "reason": "target_basis_missing"}
                for e in evaluations
            ]
            return
        valid = self._read_warm(evaluations, require_complete=False)
        self._warm_data.extend(deepcopy(valid))
        logger.info(
            "Neural strategy warm-started with %d evaluations (%d valid)",
            len(evaluations),
            len(valid),
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
        all_evals = self._training_corpus(evaluations)
        self._iteration += 1

        if len(all_evals) < self._config.n_initial:
            return self._sobol_candidate(
                max(len(all_evals), self._sobol_cursor),
                source="neural_sobol_init",
            )

        # Try fitting a GP surrogate
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
        """Use a checkpointed local RNG for the supported CPU refit profile."""
        from polisyos.scientist.methods.search.strategies._deps import require_torch

        torch = require_torch()
        # These tensors and the existing surrogate are CPU-only. Preserve the
        # ambient Torch stream; continuation owns its seed through Base RNG state.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self._rng.getrandbits(63))
            return self._fit_surrogate_candidate(evaluations, pending)

    def _fit_surrogate_candidate(
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
            [[-e.scalar_score] for e in valid],
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
        executed = torch.tensor(
            self._space.normalize(params), dtype=candidate.dtype, device=candidate.device
        ).reshape(1, -1)
        with torch.no_grad():
            posterior = model.posterior(executed)
            executed_acquisition = acqf(executed.unsqueeze(0)).item()
            predicted_mean = posterior.mean.squeeze().item()
            predicted_std = posterior.variance.sqrt().squeeze().item()
        return self._space.candidate_from_vector(
            vector,
            acquisition_value=executed_acquisition,
            predicted_mean=predicted_mean,
            predicted_std=predicted_std,
            source_strategy="neural_gp",
            metadata={
                "warm_start_count": len(self._warm_data),
                "prediction_basis": "executed_action",
                "acquisition_value_basis": "executed_action",
            },
        )

    def update(self, evaluation: Evaluation) -> None:
        """Track historical evaluations for potential cross-run transfer."""
        self._historical.append(evaluation)

    def get_state(self) -> StrategyState:
        """Persist the admitted corpus; this strategy refits its CPU GP each ask."""
        if self._config.surrogate_type != "gp":
            raise ValueError("Neural checkpoint supports only the existing CPU GP profile")
        warm = self._read_warm(self._warm_data, require_complete=True)
        state = super().get_state()
        state.metadata.update(
            {
                "neural_state_profile": "neural_warm_corpus.v1",
                "surrogate_policy": "single_task_gp.cpu.refit_each_ask.v1",
                "backend": self._backend_identity(),
                "warm_start_count": len(warm),
                "warm_evaluations": [self._encode_evaluation(e) for e in warm],
                "numerical_basis": self._basis_payload(),
                "config": self._config.model_dump(mode="json"),
            }
        )
        state.metadata["warm_corpus_sha256"] = self._corpus_digest(state.metadata)
        return state

    def set_state(self, state: StrategyState) -> None:
        """Reconcile the same content-bound corpus before mutating live state."""
        meta = state.metadata
        if not isinstance(meta, Mapping) or meta.get("neural_state_profile") != (
            "neural_warm_corpus.v1"
        ):
            raise ValueError("Neural checkpoint lacks a supported warm corpus state profile")
        if state.model_state is not None:
            raise ValueError("Neural refit profile does not accept a serialized GP model")
        if (
            meta.get("surrogate_policy") != "single_task_gp.cpu.refit_each_ask.v1"
            or meta.get("backend") != self._backend_identity()
            or not self._same_value(meta.get("numerical_basis"), self._basis_payload())
            or meta.get("warm_corpus_sha256") != self._corpus_digest(meta)
        ):
            raise ValueError("Neural checkpoint corpus or numerical/backend basis changed")
        config = NeuralSearchConfig.model_validate(meta.get("config"), strict=True)
        if config.model_dump(exclude={"seed"}) != self._config.model_dump(exclude={"seed"}):
            raise ValueError("Neural checkpoint configuration changed")
        if config.seed != meta.get("seed"):
            raise ValueError("Neural checkpoint seed basis changed")
        payloads = meta.get("warm_evaluations")
        count = meta.get("warm_start_count")
        if not isinstance(payloads, list) or type(count) is not int or count != len(payloads):
            raise ValueError("Neural checkpoint warm corpus is incomplete")
        try:
            warm = [
                TransferLearningManager._deserialize_evaluation(row, "checkpoint")
                for row in payloads
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Neural checkpoint warm evaluation is malformed") from exc
        warm = self._read_warm(warm, require_complete=True)
        super().set_state(state)
        self._config = config
        self._warm_data = deepcopy(warm)

    def _basis_payload(self) -> dict[str, Any] | None:
        return (
            None if self._numerical_basis is None else self._numerical_basis.model_dump(mode="json")
        )

    @staticmethod
    def _encode_evaluation(evaluation: Evaluation) -> dict[str, Any]:
        return TransferLearningManager._serialize_evaluation(evaluation)

    @staticmethod
    def _same_value(left: Any, right: Any) -> bool:
        return canon.to_canonical_bytes(left, canon.CanonSpec(forbid_floats=False)) == (
            canon.to_canonical_bytes(right, canon.CanonSpec(forbid_floats=False))
        )

    @staticmethod
    def _backend_identity() -> dict[str, str | None]:
        identity: dict[str, str | None] = {"device": "cpu", "dtype": "torch.float64"}
        for name in ("torch", "botorch", "gpytorch"):
            try:
                identity[name] = version(name)
            except PackageNotFoundError:
                identity[name] = None
        return identity

    @staticmethod
    def _corpus_digest(metadata: Mapping[str, Any]) -> str:
        import hashlib

        payload = {
            key: metadata.get(key)
            for key in (
                "neural_state_profile",
                "surrogate_policy",
                "backend",
                "warm_evaluations",
                "warm_start_count",
                "numerical_basis",
                "config",
            )
        }
        return hashlib.sha256(
            canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        ).hexdigest()

    def _compatible(self, evaluation: Evaluation) -> bool:
        try:
            expected = self._space.normalize(evaluation.params)
            actual = evaluation.params_normalized
            return (
                evaluation.is_valid
                and len(actual) == len(expected)
                and all(
                    type(value) in (int, float)
                    and math.isfinite(value)
                    and math.isclose(value, encoded, rel_tol=0, abs_tol=1e-12)
                    for value, encoded in zip(actual, expected, strict=True)
                )
            )
        except (TypeError, ValueError, OverflowError):
            return False

    def _read_warm(
        self, evaluations: list[Evaluation], *, require_complete: bool
    ) -> list[Evaluation]:
        if not evaluations:
            return []
        if self._numerical_basis is None or self._warm_start_admission is None:
            raise ValueError("Neural warm corpus requires the configured target and CAS reader")
        admitted = self._warm_start_admission(evaluations, self._numerical_basis)
        valid = [
            e
            for e in admitted
            if self._compatible(e)
            and self._same_value(e.metadata.get("numeric_transfer_basis"), self._basis_payload())
        ]
        if require_complete and [self._encode_evaluation(e) for e in valid] != [
            self._encode_evaluation(e) for e in evaluations
        ]:
            raise ValueError("Neural warm corpus is no longer admitted by original CAS content")
        if not require_complete:
            identities = {(e.candidate_id, e.provenance_ref) for e in valid}
            self.last_warm_start_report.extend(
                {"candidate_id": e.candidate_id, "reason": "cas_or_receiver_admission_refused"}
                for e in evaluations
                if (e.candidate_id, e.provenance_ref) not in identities
            )
        return valid

    def _training_corpus(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        warm = self._read_warm(self._warm_data, require_complete=True)
        transferred = [
            e
            for e in evaluations
            if any(
                key in e.metadata
                for key in ("numeric_transfer_basis", "transfer_history_ref", "source_row_index")
            )
        ]
        self._read_warm(transferred, require_complete=True)
        seen = set()
        corpus = []
        for evaluation in [*warm, *evaluations]:
            if not self._compatible(evaluation):
                continue
            replicas = tuple(
                (key, repr(evaluation.metadata[key]))
                for key in ("replicate_id", "replica_id", "seed")
                if key in evaluation.metadata
            )
            identity = (evaluation.provenance_ref or evaluation.candidate_id, replicas)
            if identity not in seen:
                seen.add(identity)
                corpus.append(evaluation)
        return corpus
