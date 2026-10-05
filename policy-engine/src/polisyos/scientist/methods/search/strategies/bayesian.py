"""Single-objective Bayesian optimization strategy."""

from __future__ import annotations

import io
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.metadata import version
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection

# Imported lazily through _deps to keep module importable without optional stack.
from polisyos.scientist.methods.search.strategies._deps import (
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
from polisyos.scientist.methods.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.methods.search.strategies.errors import OptionalDependencyUnavailableError
from polisyos.scientist.methods.search.strategies.resource_arbiter import ResourceArbiter
from polisyos.scientist.methods.search.strategies.runtime import apply_torch_runtime_settings
from polisyos.scientist.methods.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    EvaluationStatus,
    PolicyCandidate,
    StrategyState,
)

logger = get_logger(__name__)

_WARM_COMPATIBILITY_METADATA = "warm_start_compatibility"
_WARM_COMPATIBILITY_FIELDS = (
    "search_space_fingerprint",
    "input_transform_fingerprint",
    "outcome_transform_fingerprint",
    "noise_model_fingerprint",
    "objective_fingerprint",
    "context_fingerprint",
)
_EXPECTED_WARM_COMPATIBILITY = {
    "input_transform_fingerprint": "Normalize[0,1]",
    "outcome_transform_fingerprint": "Standardize[m=1]",
    "noise_model_fingerprint": "GaussianLikelihood[inferred]",
    "objective_fingerprint": "scalar_score[minimize]",
}


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
    # Phase 6 WS6.6 additions
    adaptive_acquisition: bool = False
    exploration_switch_threshold: float = 0.3
    refit_interval: int = 5
    warm_start_noise_factor: float = 0.1


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
        self._warm_evals: list[Evaluation] = []
        self._warm_evaluation_ids: set[int] = set()
        self._warm_context_fingerprint: str | None = None
        self._fitted_train_X: Any = None
        self._fitted_train_y_bo: Any = None
        self._last_refit_iteration: int = -1
        self._last_train_size: int = 0

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

    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Pre-seed GP with historical evaluations from similar runs."""
        accepted: list[Evaluation] = []
        rejected: list[str] = []
        for evaluation in evaluations:
            if not evaluation.is_valid:
                rejected.append("invalid outcome")
                continue
            if self._origin_ref(evaluation) is None:
                rejected.append("missing provenance_ref")
                continue
            if not self._has_compatible_params(evaluation):
                rejected.append("incompatible normalized parameters")
                continue
            compatibility = self._warm_compatibility(evaluation)
            if compatibility is None:
                rejected.append("missing or incompatible warm-start fingerprint")
                continue
            context_fingerprint = compatibility[-1]
            if (
                self._warm_context_fingerprint is not None
                and context_fingerprint != self._warm_context_fingerprint
            ):
                rejected.append("incompatible context fingerprint")
                continue
            if self._warm_context_fingerprint is None:
                self._warm_context_fingerprint = context_fingerprint
            accepted.append(evaluation)
            self._warm_evaluation_ids.add(id(evaluation))

        self._warm_evals.extend(accepted)
        logger.info(
            "Bayesian warm-start: added {} historical evaluations; rejected {}",
            len(accepted),
            len(rejected),
        )

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        self._iteration = len(evaluations)
        pending = pending or []
        training_corpus = self._effective_training_corpus(evaluations)

        if len(training_corpus) < self._config.n_initial:
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
                    evaluations=evaluations,
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

    def suggest_batch(
        self, evaluations: list[Evaluation], batch_size: int
    ) -> list[PolicyCandidate]:
        if batch_size < 1:
            return []

        training_corpus = self._effective_training_corpus(evaluations)
        if len(training_corpus) < self._config.n_initial:
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
        """Persist the numerical model and the corpus/refit basis of its next ask."""
        base_state = super().get_state()
        model_state: bytes | None = None
        if self._model is not None and self._botorch_ready:
            buffer = io.BytesIO()
            self._torch.save(self._model.state_dict(), buffer)
            model_state = buffer.getvalue()

        metadata: dict[str, Any] = {
            **base_state.metadata,
            "gp_checkpoint_version": 1,
            "config": asdict(self._config),
            "last_refit_iteration": self._last_refit_iteration,
            "last_train_size": self._last_train_size,
            "warm_evaluations": [self._warm_checkpoint_record(e) for e in self._warm_evals],
            "warm_context_fingerprint": self._warm_context_fingerprint,
        }
        if model_state is not None:
            if self._fitted_train_X is None or self._fitted_train_y_bo is None:
                raise ValueError("GP checkpoint is incompatible: fitted corpus is missing")
            metadata["train_X"] = self._fitted_train_X.tolist()
            metadata["train_y_bo"] = self._fitted_train_y_bo.tolist()
            metadata["backend"] = self._backend_identity()

        rng_state = base_state.rng_state
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
        """Restore an admitted continuation without refitting or losing warm data."""
        metadata = state.metadata
        if not isinstance(state.rng_state, Mapping):
            raise ValueError("GP checkpoint RNG state must be an object")
        if not isinstance(metadata, Mapping) or metadata.get("gp_checkpoint_version") != 1:
            raise ValueError("GP checkpoint is incompatible: replay basis is missing")
        config = metadata.get("config")
        if not isinstance(config, Mapping) or set(config) != set(asdict(self._config)):
            raise ValueError("GP checkpoint is incompatible: configuration is missing")
        if any(
            config[key] != value for key, value in asdict(self._config).items() if key != "seed"
        ):
            raise ValueError("GP checkpoint is incompatible: configuration changed")
        if config.get("seed") != metadata.get("seed"):
            raise ValueError("GP checkpoint is incompatible: seed basis changed")
        last_refit = metadata.get("last_refit_iteration")
        last_size = metadata.get("last_train_size")
        if (
            isinstance(last_refit, bool)
            or not isinstance(last_refit, int)
            or last_refit < -1
            or isinstance(last_size, bool)
            or not isinstance(last_size, int)
            or last_size < 0
        ):
            raise ValueError("GP checkpoint is incompatible: refit counters are invalid")
        warm_payloads = metadata.get("warm_evaluations")
        if not isinstance(warm_payloads, list):
            raise ValueError("GP checkpoint is incompatible: warm corpus is missing")
        warm_evals = [self._warm_from_checkpoint(payload) for payload in warm_payloads]
        warm_context = metadata.get("warm_context_fingerprint")
        if warm_context is not None and (not isinstance(warm_context, str) or not warm_context):
            raise ValueError("GP checkpoint is incompatible: warm context is invalid")
        if any(self._warm_compatibility(e)[-1] != warm_context for e in warm_evals):
            raise ValueError("GP checkpoint is incompatible: warm context changed")

        torch_rng = None
        torch_rng_state = state.rng_state.get("torch")
        if self._torch_rng is not None:
            if not isinstance(torch_rng_state, list) or any(
                type(value) is not int or not 0 <= value <= 255 for value in torch_rng_state
            ):
                raise ValueError("GP checkpoint is incompatible: torch RNG state is invalid")
            torch_rng = self._torch.Generator()
            torch_rng.set_state(self._torch.tensor(torch_rng_state, dtype=self._torch.uint8))

        train_X = train_y = model = None
        if state.model_state is not None:
            if not self._botorch_ready or metadata.get("backend") != self._backend_identity():
                raise ValueError("GP checkpoint is incompatible: numerical backend changed")
            try:
                train_X = self._torch.tensor(
                    metadata.get("train_X"), dtype=self._torch.float64, device=self._device
                )
                train_y = self._torch.tensor(
                    metadata.get("train_y_bo"), dtype=self._torch.float64, device=self._device
                )
            except (TypeError, ValueError, RuntimeError) as exc:
                raise ValueError("GP checkpoint is incompatible: fitted corpus is invalid") from exc
            if (
                train_X.ndim != 2
                or train_X.shape[1] != self._space.dim
                or train_X.shape[0] < 1
                or train_y.shape != (train_X.shape[0], 1)
                or not self._torch.isfinite(train_X).all()
                or not self._torch.isfinite(train_y).all()
                or not ((train_X >= 0) & (train_X <= 1)).all()
                or not 0 < last_size <= train_X.shape[0]
                or last_refit < 0
            ):
                raise ValueError("GP checkpoint is incompatible: fitted corpus shape/basis changed")
            model = SingleTaskGP(
                train_X=train_X,
                train_Y=train_y,
                input_transform=Normalize(d=train_X.shape[-1]),
                outcome_transform=Standardize(m=1),
            )
            buffer = io.BytesIO(state.model_state)
            model.load_state_dict(
                self._torch.load(buffer, weights_only=True, map_location=self._device)
            )
        elif (
            last_size != 0 or last_refit != -1 or "train_X" in metadata or "train_y_bo" in metadata
        ):
            raise ValueError("GP checkpoint is incompatible: model/corpus mismatch")

        # Validate all numerical/corpus fields before the canonical owner
        # changes its RNG and Sobol stream. The rebuilt model is still local.
        super().set_state(state)
        self._model = model
        self._train_X, self._train_y_bo = train_X, train_y
        self._fitted_train_X = train_X.clone() if train_X is not None else None
        self._fitted_train_y_bo = train_y.clone() if train_y is not None else None
        self._last_refit_iteration, self._last_train_size = last_refit, last_size
        self._warm_evals = warm_evals
        self._warm_evaluation_ids = {id(e) for e in warm_evals}
        self._warm_context_fingerprint = warm_context
        self._config.seed = config["seed"]
        if torch_rng is not None:
            self._torch_rng = torch_rng

    @staticmethod
    def _backend_identity() -> dict[str, str]:
        return {name: version(name) for name in ("torch", "botorch", "gpytorch")}

    @staticmethod
    def _warm_checkpoint_record(evaluation: Evaluation) -> dict[str, Any]:
        record = asdict(evaluation)
        record["timestamp"] = evaluation.timestamp.isoformat()
        record["status"] = evaluation.status.value
        for objective in record["objectives"]:
            objective["direction"] = objective["direction"].value
        # Refuse lossy coercion of provenance, replica IDs, or scientific data.
        json.dumps(record, allow_nan=False)
        return record

    def _warm_from_checkpoint(self, payload: Any) -> Evaluation:
        try:
            if not isinstance(payload, Mapping):
                raise ValueError("warm evaluation must be an object")
            record = dict(payload)
            record["timestamp"] = datetime.fromisoformat(record["timestamp"])
            record["status"] = EvaluationStatus(record["status"])
            record["params_normalized"] = tuple(record["params_normalized"])
            record["objectives"] = [
                ObjectiveValue(
                    **{**objective, "direction": OptimizationDirection(objective["direction"])}
                )
                for objective in record["objectives"]
            ]
            evaluation = Evaluation(**record)
            if (
                not isinstance(evaluation.candidate_id, str)
                or not evaluation.candidate_id
                or not isinstance(evaluation.params, dict)
                or not isinstance(evaluation.metadata, dict)
                or not evaluation.is_valid
                or not math.isfinite(evaluation.scalar_score)
                or self._origin_ref(evaluation) is None
                or not self._has_compatible_params(evaluation)
                or self._warm_compatibility(evaluation) is None
            ):
                raise ValueError("warm evaluation binding changed")
            return evaluation
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("GP checkpoint is incompatible: warm evaluation is invalid") from exc

    def _select_training_subset(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        filtered = self._effective_training_corpus(evaluations)
        if len(filtered) <= self._config.max_train_size:
            return filtered
        # Keep recent half + uniformly sampled remainder for diversity.
        recent_n = self._config.max_train_size // 2
        recent = filtered[-recent_n:]
        older = filtered[:-recent_n]
        step = max(1, len(older) // max(1, self._config.max_train_size - recent_n))
        sampled = older[::step][: self._config.max_train_size - recent_n]
        return sampled + recent

    def _effective_training_corpus(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        """Combine compatible warm/current records without double-counting artifacts."""
        corpus: list[Evaluation] = []
        seen: set[tuple[Any, ...]] = set()
        for evaluation in [*self._warm_evals, *evaluations]:
            if not self._has_compatible_params(evaluation):
                continue
            requires_warm_fingerprint = id(evaluation) in self._warm_evaluation_ids
            if requires_warm_fingerprint and self._warm_compatibility(evaluation) is None:
                continue
            if _WARM_COMPATIBILITY_METADATA in evaluation.metadata:
                compatibility = self._warm_compatibility(evaluation)
                if compatibility is None:
                    continue
                if (
                    self._warm_context_fingerprint is not None
                    and compatibility[-1] != self._warm_context_fingerprint
                ):
                    continue
            identity = self._evaluation_identity(evaluation)
            if identity in seen:
                continue
            seen.add(identity)
            corpus.append(evaluation)
        return corpus

    def _has_compatible_params(self, evaluation: Evaluation) -> bool:
        """Return whether normalized parameters match this space and GP bounds."""
        try:
            normalized = tuple(float(value) for value in evaluation.params_normalized)
        except (TypeError, ValueError, OverflowError):
            return False
        return len(normalized) == self._space.dim and all(
            math.isfinite(value) and 0.0 <= value <= 1.0 for value in normalized
        )

    def _warm_compatibility(self, evaluation: Evaluation) -> tuple[str, ...] | None:
        """Validate the model/data contract carried by a warm-start record."""
        payload = evaluation.metadata.get(_WARM_COMPATIBILITY_METADATA)
        if not isinstance(payload, Mapping):
            return None
        values: list[str] = []
        for field in _WARM_COMPATIBILITY_FIELDS:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                return None
            values.append(value.strip())

        if values[0] != self._space.sobol_space_fingerprint():
            return None
        for field, expected in _EXPECTED_WARM_COMPATIBILITY.items():
            if payload.get(field) != expected:
                return None
        return tuple(values)

    @staticmethod
    def _origin_ref(evaluation: Evaluation) -> str | None:
        """Return a non-empty provenance reference, if one is present."""
        reference = evaluation.provenance_ref
        if not isinstance(reference, str):
            return None
        reference = reference.strip()
        return reference or None

    @staticmethod
    def _evaluation_identity(evaluation: Evaluation) -> tuple[Any, ...]:
        """Identify one artifact while keeping explicitly independent replicas."""
        metadata = evaluation.metadata
        replicate_identity = tuple(
            (key, repr(metadata[key]))
            for key in ("replicate_id", "replica_id", "seed")
            if key in metadata
        )
        origin = BayesianOptimizer._origin_ref(evaluation)
        if origin is not None:
            return ("origin", origin, replicate_identity)
        return ("candidate", evaluation.candidate_id, replicate_identity)

    def _prepare_training_data(self, evaluations: list[Evaluation]):
        valid_scores = [
            e.scalar_score for e in evaluations if e.is_valid and math.isfinite(e.scalar_score)
        ]
        if not valid_scores:
            raise RuntimeError("No valid objective values available for GP fitting")

        worst_valid = max(valid_scores)
        penalty = self._config.invalid_penalty
        x_rows: list[list[float]] = []
        y_search: list[float] = []
        for evaluation in evaluations:
            x_rows.append([float(value) for value in evaluation.params_normalized])
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
        current_train_size = X.shape[0]
        should_refit = (
            self._model is None
            or self._iteration - self._last_refit_iteration >= self._config.refit_interval
            or current_train_size > self._last_train_size * 1.2
        )

        if should_refit:
            self._fit_full_gp(X, y_bo)
            return

        previous_X = self._model_train_x()
        if (
            previous_X is None
            or self._fitted_train_X is None
            or self._fitted_train_y_bo is None
            or not self._model_train_x_matches_fitted(previous_X)
            or not self._is_append_update(X, y_bo)
        ):
            logger.info("Bayesian GP corpus changed outside append-only update; refitting model")
            self._fit_full_gp(X, y_bo)
            return

        previous_size = previous_X.shape[0]
        if previous_size == current_train_size:
            return

        try:
            # GPyTorch's supported fantasy update requires an evaluation-mode
            # prediction cache.  Acquisition optimization normally creates it,
            # but keep this invariant local so a caller that updates the model
            # before requesting a posterior is still handled safely.
            self._model.eval()
            if getattr(self._model, "prediction_strategy", None) is None:
                with self._torch.no_grad():
                    self._model(X[:1])
            self._model = self._model.condition_on_observations(
                X=X[previous_size:],
                Y=y_bo[previous_size:],
            )
            self._fitted_train_X = X.detach().clone()
            self._fitted_train_y_bo = y_bo.detach().clone()
        except Exception as exc:
            logger.warning("Bayesian GP conditioning unavailable; using bounded refit: {}", exc)
            self._fit_full_gp(X, y_bo)

    def _fit_full_gp(self, X, y_bo) -> None:
        """Fit a fresh model and record the full-refit boundary."""
        self._model = SingleTaskGP(
            train_X=X,
            train_Y=y_bo,
            input_transform=Normalize(d=X.shape[-1]),
            outcome_transform=Standardize(m=1),
        )
        mll = ExactMarginalLogLikelihood(self._model.likelihood, self._model)
        fit_gpytorch_mll(mll)
        self._fitted_train_X = X.detach().clone()
        self._fitted_train_y_bo = y_bo.detach().clone()
        self._last_refit_iteration = self._iteration
        self._last_train_size = X.shape[0]

    def _model_train_x(self):
        """Read the model's raw training inputs in the two-dimensional GP shape."""
        if self._model is None:
            return None
        train_inputs = getattr(self._model, "train_inputs", None)
        if not train_inputs:
            return None
        train_X = train_inputs[0]
        if train_X.ndim < 2:
            return None
        return train_X.reshape(-1, train_X.shape[-1])

    def _model_train_x_matches_fitted(self, model_X) -> bool:
        """Accept the model's raw or input-transformed training coordinate system."""
        if self._model is None or self._fitted_train_X is None:
            return False
        fitted_X = self._fitted_train_X
        candidates = [fitted_X]
        try:
            transformed_X = self._model.transform_inputs(fitted_X)
        except Exception:
            transformed_X = None
        if transformed_X is not None:
            candidates.append(transformed_X)
        for expected_X in candidates:
            expected_X = expected_X.reshape(-1, expected_X.shape[-1]).to(
                device=model_X.device,
                dtype=model_X.dtype,
            )
            if expected_X.shape == model_X.shape and self._torch.equal(expected_X, model_X):
                return True
        return False

    def _is_append_update(self, X, y_bo) -> bool:
        """Check that the new corpus retains fitted X and y rows as a prefix."""
        if self._fitted_train_X is None or self._fitted_train_y_bo is None:
            return False
        previous_X = self._fitted_train_X
        previous_y_bo = self._fitted_train_y_bo
        if (
            previous_X.shape[-1] != X.shape[-1]
            or previous_X.shape[0] > X.shape[0]
            or previous_y_bo.ndim != y_bo.ndim
            or previous_y_bo.shape[1:] != y_bo.shape[1:]
            or previous_y_bo.shape[0] > y_bo.shape[0]
        ):
            return False
        previous_X = previous_X.to(device=X.device, dtype=X.dtype)
        previous_y_bo = previous_y_bo.to(device=y_bo.device, dtype=y_bo.dtype)
        return bool(
            self._torch.equal(previous_X, X[: previous_X.shape[0]])
            and self._torch.equal(previous_y_bo, y_bo[: previous_y_bo.shape[0]])
        )

    def _select_acquisition(
        self,
        evaluations: list[Evaluation],
        y_bo,
    ) -> AcquisitionType:
        """Select acquisition function, optionally adapting based on progress."""
        if not self._config.adaptive_acquisition:
            return self._config.acquisition

        n = len(evaluations)
        if n < 5:
            return AcquisitionType.EI

        valid = [e for e in evaluations if e.is_valid]
        if len(valid) < 3:
            return AcquisitionType.EI

        recent_scores = [e.scalar_score for e in valid[-5:]]
        overall_best = min(e.scalar_score for e in valid)
        recent_best = min(recent_scores)

        # No improvement in recent window -> explore more
        if abs(recent_best - overall_best) < 1e-8:
            return AcquisitionType.UCB

        # Good progress -> exploit
        improvement_rate = (overall_best - recent_best) / max(abs(overall_best), 1e-8)
        if improvement_rate > self._config.exploration_switch_threshold:
            return AcquisitionType.PI

        return AcquisitionType.EI

    def _optimize_acquisition(
        self, y_bo, soft_limit: bool, evaluations: list[Evaluation] | None = None
    ):
        best_f = y_bo.max()
        acq_type = self._select_acquisition(evaluations or [], y_bo)

        if acq_type == AcquisitionType.UCB:
            acq = UpperConfidenceBound(model=self._model, beta=self._config.ucb_beta)
        elif acq_type == AcquisitionType.PI:
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
        candidate_execution = self._effective_execution(candidate)
        if candidate_execution is None:
            return False
        for other in pending:
            if not self._same_replicate_scope(candidate, other):
                continue
            other_execution = self._effective_execution(other)
            if other_execution is None:
                continue
            if candidate_execution == other_execution:
                return True
        return False

    def _effective_execution(self, candidate: PolicyCandidate) -> dict[str, Any] | None:
        """Resolve a proposal to the typed parameters that will actually run."""
        if candidate.params_normalized is not None:
            try:
                return self._space.denormalize(candidate.params_normalized)
            except (TypeError, ValueError):
                return None
        if candidate.params:
            return dict(candidate.params)
        return None

    @staticmethod
    def _same_replicate_scope(left: PolicyCandidate, right: PolicyCandidate) -> bool:
        """Keep explicit independent replicate identities distinct."""
        replicate_keys = ("replicate_id", "replica_id", "seed")
        for key in replicate_keys:
            left_value = left.metadata.get(key)
            right_value = right.metadata.get(key)
            if left_value is None and right_value is None:
                continue
            if left_value != right_value:
                return False
        return True

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
