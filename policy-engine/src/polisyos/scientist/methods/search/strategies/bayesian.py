"""Single-objective Bayesian optimization strategy."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from collections.abc import Callable, Mapping
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
    SobolQMCNormalSampler,
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
_ACQUISITION_POLICY = "sobol_ranked_restarts.v1"
_GP_STATE_VERSION = 3

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

    def __post_init__(self):
        for key in ("n_initial", "num_restarts", "raw_samples", "max_train_size", "refit_interval"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"{key} requires a positive integer")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("seed requires an unsigned 32-bit integer")


class BayesianOptimizer(BaseSearchStrategy):
    """Gaussian Process Bayesian optimizer with robust fallback behavior."""

    def __init__(
        self,
        space,
        config: BayesianConfig | None = None,
        resource_arbiter: ResourceArbiter | None = None,
        *,
        numerical_basis: Any = None,
        warm_start_admission: Callable[[list[Evaluation], Any], list[Evaluation]] | None = None,
    ):
        cfg = config or BayesianConfig()
        super().__init__(space=space, seed=cfg.seed)
        self._config = cfg
        self._numerical_basis = numerical_basis
        self._warm_start_admission = warm_start_admission
        self._basis_payload = self._validated_basis(numerical_basis)
        self._training_record_ids: list[str] = []
        self._fitted_record_ids: list[str] = []
        self._refit_record_ids: list[str] = []
        self._refit_train_X = None
        self._refit_train_y_bo = None
        self.last_warm_start_report: list[dict[str, str]] = []
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
        self._warm_context_fingerprint: str | None = (
            self._basis_payload.get("context_fingerprint") if self._basis_payload else None
        )
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

    @property
    def backend_available(self) -> bool:
        return self._botorch_ready

    def _validated_basis(self, basis: Any) -> dict[str, Any] | None:
        if basis is None:
            if self._warm_start_admission is not None:
                raise ValueError("Warm admission requires a configured numerical basis")
            return None
        if isinstance(basis, Mapping):
            payload = dict(basis)
            fields = {
                "profile",
                "search_space_fingerprint",
                "context_fingerprint",
                "metric",
                "unit",
                "direction",
            }
            if set(payload) != fields or payload.get("profile") != "synthetic_scalar_gp.v1":
                raise ValueError("Unsupported local GP numerical basis")
            if any(not isinstance(payload[key], str) or not payload[key] for key in fields):
                raise ValueError("Complete synthetic GP basis required")
            if payload["direction"] not in {"minimize", "maximize"}:
                raise ValueError("Unsupported objective direction")
        else:
            # The transfer owner supplies both its strict target type and its
            # canonical CAS reader. A metadata declaration is never that reader.
            from polisyos.scientist.methods.search.strategies.transfer import NumericTransferBasis

            if not isinstance(basis, NumericTransferBasis) or not callable(
                self._warm_start_admission
            ):
                raise ValueError("Transferred GP rows require the canonical admission reader")
            payload = basis.model_dump(mode="json")
        if payload["search_space_fingerprint"] != self._space.sobol_space_fingerprint():
            raise ValueError("Numerical basis search space differs from the receiver")
        return payload

    def warm_start(self, evaluations: list[Evaluation]) -> None:
        """Admit warm rows against a configured target, never the first row."""
        self.last_warm_start_report = []
        if self._basis_payload is None:
            self.last_warm_start_report = [
                {"candidate_id": e.candidate_id, "reason": "target_basis_missing"}
                for e in evaluations
            ]
            return
        if self._warm_start_admission is not None:
            evaluations = self._warm_start_admission(evaluations, self._numerical_basis)
        accepted = []
        for evaluation in evaluations:
            reason = None
            if not evaluation.is_valid or not math.isfinite(evaluation.scalar_score):
                reason = "invalid_outcome"
            elif self._origin_ref(evaluation) is None:
                reason = "missing_origin"
            elif not self._has_compatible_params(evaluation):
                reason = "physical_coordinate_mismatch"
            elif self._warm_start_admission is None and (
                self._warm_compatibility(evaluation) is None
                or self._warm_compatibility(evaluation)[-1] != self._warm_context_fingerprint
            ):
                reason = "numerical_basis_mismatch"
            elif (
                self._warm_start_admission is not None
                and evaluation.metadata.get("numeric_transfer_basis") != self._basis_payload
            ):
                reason = "transfer_basis_mismatch"
            if reason:
                self.last_warm_start_report.append(
                    {"candidate_id": evaluation.candidate_id, "reason": reason}
                )
            else:
                accepted.append(copy.deepcopy(evaluation))
        self._warm_evals.extend(accepted)
        self._warm_evaluation_ids.update(id(e) for e in accepted)

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
    ) -> PolicyCandidate:
        self._iteration = len(evaluations)
        pending = [*(pending or []), *self._completed_candidates(evaluations)]
        training_corpus = self._effective_training_corpus(evaluations)

        if len(training_corpus) < self._config.n_initial:
            for _ in range(20):
                candidate = self._sobol_candidate(
                    max(len(evaluations), self._sobol_cursor), source="sobol_init"
                )
                if not self._is_duplicate(candidate, pending):
                    return candidate
            return self._non_duplicate_random(pending, source="random_initial_duplicate")

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

        self._iteration = len(evaluations)
        training_corpus = self._effective_training_corpus(evaluations)
        if len(training_corpus) < self._config.n_initial:
            output = []
            for _ in range(batch_size):
                output.append(self.suggest(evaluations, pending=output))
            return output

        if not self._botorch_ready:
            return self._random_batch(evaluations, batch_size, "random_no_botorch")

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return self._random_batch(evaluations, batch_size, "random_hard_limit")

            train_set = self._select_training_subset(evaluations)
            if len(train_set) < 3:
                return self._random_batch(evaluations, batch_size, "random_insufficient_data")

            try:
                X, y_bo = self._prepare_training_data(train_set)
                self._fit_gp(X, y_bo)
                restarts, raw_samples = self._effective_optim_params(soft_limit=soft)
                best_f = y_bo.max()
                acq = qExpectedImprovement(
                    model=self._model,
                    best_f=best_f,
                    sampler=SobolQMCNormalSampler(
                        self._torch.Size([128]), seed=self._next_acquisition_seed()
                    ),
                )
                bounds = self._space.to_botorch_bounds().to(self._device)
                initial = self._acquisition_initial_conditions(
                    acq, bounds, batch_size, restarts, raw_samples
                )
                candidates, _ = optimize_acqf(
                    acq_function=acq,
                    bounds=bounds,
                    q=batch_size,
                    num_restarts=restarts,
                    batch_initial_conditions=initial,
                )
                output: list[PolicyCandidate] = []
                for idx in range(batch_size):
                    candidate = self._tensor_to_candidate(candidates[idx], source="batch_qei")
                    if self._is_duplicate(
                        candidate, [*self._completed_candidates(evaluations), *output]
                    ):
                        candidate = self._non_duplicate_random(
                            [*self._completed_candidates(evaluations), *output],
                            source="random_batch_duplicate",
                        )
                    output.append(candidate)
                return output
            except Exception as exc:
                logger.warning("Bayesian batch optimization failed; random fallback: {}", exc)
                if not self._config.fallback_on_failure:
                    raise
                output = []
                for _ in range(batch_size):
                    output.append(
                        self._non_duplicate_random(
                            [*self._completed_candidates(evaluations), *output],
                            source="random_batch_fallback",
                        )
                    )
                return output

    def get_state(self) -> StrategyState:
        base = super().get_state()
        metadata = {
            **base.metadata,
            "gp_state_version": _GP_STATE_VERSION,
            "acquisition_policy": _ACQUISITION_POLICY,
            "config": asdict(self._config),
            "numerical_basis": self._basis_payload,
            "warm_evaluations": [self._encode_evaluation(e) for e in self._warm_evals],
            "last_refit_iteration": self._last_refit_iteration,
            "last_train_size": self._last_train_size,
        }
        model_state = None
        if self._model is not None:
            if not self._model_train_x_matches_fitted(self._model_train_x()):
                raise ValueError("GP model inputs differ from the persisted fitted corpus")
            with self._torch.no_grad():
                transformed_y = self._model.outcome_transform(self._fitted_train_y_bo)[0].squeeze(
                    -1
                )
            if not self._torch.allclose(
                self._model.train_targets, transformed_y, rtol=1e-12, atol=1e-12
            ):
                raise ValueError("GP model targets differ from the persisted fitted corpus")
            buffer = io.BytesIO()
            self._torch.save(self._model.state_dict(), buffer)
            model_state = buffer.getvalue()
            metadata["model_state_sha256"] = hashlib.sha256(model_state).hexdigest()
            metadata.update(
                {
                    "backend": self._backend_identity(),
                    "train_X": self._fitted_train_X.tolist(),
                    "train_y_bo": self._fitted_train_y_bo.tolist(),
                    "refit_train_X": self._refit_train_X.tolist(),
                    "refit_train_y_bo": self._refit_train_y_bo.tolist(),
                    "fitted_record_ids": list(self._fitted_record_ids),
                    "refit_record_ids": list(self._refit_record_ids),
                }
            )
            metadata["corpus_sha256"] = self._corpus_digest(metadata)
        rng = dict(base.rng_state)
        if self._torch_rng is not None:
            rng["torch"] = self._torch_rng.get_state().tolist()
        return StrategyState("BayesianOptimizer", self._iteration, rng, model_state, metadata)

    def set_state(self, state: StrategyState) -> None:
        """Decode and reconcile a complete continuation before any live mutation."""
        meta = state.metadata
        if state.model_state is not None and not isinstance(state.model_state, bytes):
            raise ValueError("GP model state requires bytes or null")
        if (
            not isinstance(meta, Mapping)
            or type(meta.get("gp_state_version")) is not int
            or meta["gp_state_version"] != _GP_STATE_VERSION
        ):
            raise ValueError("GP checkpoint lacks a supported complete state basis")
        if (
            meta.get("acquisition_policy") != _ACQUISITION_POLICY
            or meta.get("numerical_basis") != self._basis_payload
        ):
            raise ValueError("GP checkpoint numerical basis or acquisition policy changed")
        cfg = meta.get("config")
        expected = asdict(self._config)
        if not isinstance(cfg, Mapping) or set(cfg) != set(expected):
            raise ValueError("GP checkpoint configuration is invalid")
        for key, value in expected.items():
            actual = cfg[key]
            if isinstance(value, int) and not isinstance(value, bool) and type(actual) is not int:
                raise ValueError("GP integer configuration requires an integer")
            if isinstance(value, bool) and type(actual) is not bool:
                raise ValueError("GP boolean configuration requires a boolean")
            if isinstance(value, float) and (
                type(actual) not in (int, float) or not math.isfinite(actual)
            ):
                raise ValueError("GP numeric configuration requires a finite number")
            if key != "seed" and actual != value:
                raise ValueError("GP checkpoint configuration changed")
        if cfg["seed"] != meta.get("seed"):
            raise ValueError("GP seed basis changed")
        last_fit, last_size = meta.get("last_refit_iteration"), meta.get("last_train_size")
        if (
            type(state.iteration) is not int
            or state.iteration < 0
            or type(last_fit) is not int
            or type(last_size) is not int
            or not -1 <= last_fit <= state.iteration
            or last_size < 0
        ):
            raise ValueError("GP checkpoint refit counters are invalid")
        payloads = meta.get("warm_evaluations")
        if not isinstance(payloads, list):
            raise ValueError("GP checkpoint warm corpus is invalid")
        warm = [self._decode_evaluation(e) for e in payloads]
        if warm:
            # Reuse the same configured admission reader during restore. Its
            # failure/omission cannot silently remove rows from a fitted basis.
            probe = copy.copy(self)
            probe._warm_evals = []
            probe._warm_evaluation_ids = set()
            probe.warm_start(warm)
            if [self._encode_evaluation(e) for e in probe._warm_evals] != payloads:
                raise ValueError("GP checkpoint warm corpus is no longer admitted")
            warm = probe._warm_evals
        torch_rng = None
        if self._torch_rng is not None:
            raw_rng = state.rng_state.get("torch") if isinstance(state.rng_state, Mapping) else None
            if not isinstance(raw_rng, list) or any(
                type(v) is not int or not 0 <= v <= 255 for v in raw_rng
            ):
                raise ValueError("GP Torch RNG bytes are invalid")
            try:
                torch_rng = self._torch.Generator()
                torch_rng.set_state(self._torch.tensor(raw_rng, dtype=self._torch.uint8))
            except (RuntimeError, TypeError) as exc:
                raise ValueError("GP Torch RNG state is invalid") from exc
        model = X = Y = refit_X = refit_Y = None
        fitted_ids = refit_ids = []
        if state.model_state is not None:
            if meta.get("corpus_sha256") != self._corpus_digest(meta):
                raise ValueError("GP checkpoint corpus content differs from its saved binding")
            if meta.get("model_state_sha256") != hashlib.sha256(state.model_state).hexdigest():
                raise ValueError("GP checkpoint model content differs from its saved binding")
            if not self._botorch_ready or meta.get("backend") != self._backend_identity():
                raise ValueError("GP checkpoint numerical backend changed")
            X, Y = self._checkpoint_tensors(meta, "train_X", "train_y_bo")
            refit_X, refit_Y = self._checkpoint_tensors(meta, "refit_train_X", "refit_train_y_bo")
            fitted_ids, refit_ids = meta.get("fitted_record_ids"), meta.get("refit_record_ids")
            if (
                last_fit < 0
                or last_size != refit_X.shape[0]
                or X.shape[0] > last_size * 1.2
                or not self._torch.equal(refit_X, X[:last_size])
                or not self._torch.equal(refit_Y, Y[:last_size])
            ):
                raise ValueError("GP checkpoint full-refit corpus/counters disagree")
            if (
                not isinstance(fitted_ids, list)
                or not isinstance(refit_ids, list)
                or len(fitted_ids) != len(X)
                or len(refit_ids) != last_size
                or fitted_ids[:last_size] != refit_ids
                or any(not isinstance(v, str) or not v for v in fitted_ids)
            ):
                raise ValueError("GP checkpoint observation identities disagree")
            try:
                weights = self._torch.load(
                    io.BytesIO(state.model_state), weights_only=True, map_location=self._device
                )
                if not isinstance(weights, Mapping) or any(
                    not self._torch.is_tensor(v) for v in weights.values()
                ):
                    raise ValueError("Malformed model state")
                input_transform = Normalize(d=X.shape[-1])
                outcome_transform = Standardize(m=1)
                for prefix, transform in (
                    ("input_transform.", input_transform),
                    ("outcome_transform.", outcome_transform),
                ):
                    transform.load_state_dict(
                        {
                            key[len(prefix) :]: value
                            for key, value in weights.items()
                            if key.startswith(prefix)
                        },
                        strict=True,
                    )
                    transform.eval()
                model = SingleTaskGP(
                    train_X=X,
                    train_Y=Y,
                    input_transform=input_transform,
                    outcome_transform=outcome_transform,
                )
                defaults = model.state_dict()
                for key, value in weights.items():
                    if not self._torch.isfinite(value).all() and (
                        key not in defaults or not self._torch.equal(value, defaults[key])
                    ):
                        raise ValueError("Non-finite learned state or changed backend constraint")
                model.load_state_dict(weights, strict=True)
                if any(not self._torch.isfinite(p).all() for p in model.parameters()):
                    raise ValueError("Non-finite learned GP parameter")
                model.eval()
                with self._torch.no_grad():
                    expected_Y = model.outcome_transform(Y)[0].squeeze(-1)
                if not self._torch.allclose(
                    model.train_targets, expected_Y, rtol=1e-12, atol=1e-12
                ):
                    raise ValueError("Restored model targets differ from saved transform/corpus")
            except Exception as exc:
                raise ValueError("GP checkpoint numerical model is invalid") from exc
        elif (
            last_fit != -1
            or last_size != 0
            or any(
                key in meta
                for key in ("train_X", "train_y_bo", "refit_train_X", "refit_train_y_bo")
            )
        ):
            raise ValueError("GP checkpoint missing its fitted model")
        super().set_state(state)
        self._model, self._train_X, self._train_y_bo = model, X, Y
        self._fitted_train_X, self._fitted_train_y_bo = X, Y
        self._refit_train_X, self._refit_train_y_bo = refit_X, refit_Y
        self._fitted_record_ids, self._refit_record_ids = fitted_ids, refit_ids
        self._last_refit_iteration, self._last_train_size = last_fit, last_size
        self._warm_evals = warm
        self._warm_evaluation_ids = {id(e) for e in warm}
        self._config.seed = cfg["seed"]
        if torch_rng is not None:
            self._torch_rng = torch_rng

    @staticmethod
    def _backend_identity() -> dict[str, str]:
        return {name: version(name) for name in ("torch", "botorch", "gpytorch")}

    @staticmethod
    def _corpus_digest(meta):
        try:
            return hashlib.sha256(
                json.dumps(
                    {
                        key: meta[key]
                        for key in (
                            "train_X",
                            "train_y_bo",
                            "refit_train_X",
                            "refit_train_y_bo",
                            "fitted_record_ids",
                            "refit_record_ids",
                            "numerical_basis",
                            "warm_evaluations",
                            "last_refit_iteration",
                            "last_train_size",
                        )
                    },
                    sort_keys=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("GP checkpoint corpus binding is invalid") from exc

    def _checkpoint_tensors(self, meta, x_key, y_key):
        for key in (x_key, y_key):
            rows = meta.get(key)
            if not isinstance(rows, list) or any(
                not isinstance(row, list)
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in row)
                for row in rows
            ):
                raise ValueError("GP checkpoint tensors require finite numeric rows")
        try:
            X = self._torch.tensor(meta.get(x_key), dtype=self._torch.float64, device=self._device)
            Y = self._torch.tensor(meta.get(y_key), dtype=self._torch.float64, device=self._device)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise ValueError("GP checkpoint tensors are invalid") from exc
        if (
            X.ndim != 2
            or X.shape[1] != self._space.dim
            or not len(X)
            or Y.shape != (len(X), 1)
            or not self._torch.isfinite(X).all()
            or not self._torch.isfinite(Y).all()
            or not ((X >= 0) & (X <= 1)).all()
        ):
            raise ValueError("GP checkpoint tensor shape/range is invalid")
        return X, Y

    @staticmethod
    def _encode_evaluation(evaluation):
        record = asdict(evaluation)
        record["timestamp"] = evaluation.timestamp.isoformat()
        record["status"] = evaluation.status.value
        for objective in record["objectives"]:
            objective["direction"] = objective["direction"].value
        return json.loads(json.dumps(record, allow_nan=False))

    @staticmethod
    def _decode_evaluation(payload):
        try:
            record = dict(payload)
            record["timestamp"] = datetime.fromisoformat(record["timestamp"])
            record["status"] = EvaluationStatus(record["status"])
            record["params_normalized"] = tuple(record["params_normalized"])
            record["objectives"] = [
                ObjectiveValue(**{**o, "direction": OptimizationDirection(o["direction"])})
                for o in record["objectives"]
            ]
            if type(record["stage_a_passed"]) is not bool:
                raise ValueError("Evaluation stage flag must be boolean")
            return Evaluation(**record)
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError("GP checkpoint evaluation is invalid") from exc

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
        transferred = [
            e for e in [*self._warm_evals, *evaluations] if "numeric_transfer_basis" in e.metadata
        ]
        if transferred:
            if self._warm_start_admission is None:
                raise ValueError(
                    "Transferred training rows require the configured CAS admission reader"
                )
            admitted = self._warm_start_admission(transferred, self._numerical_basis)
            if [self._encode_evaluation(e) for e in admitted] != [
                self._encode_evaluation(e) for e in transferred
            ]:
                raise ValueError(
                    "Transferred training rows are no longer content-bound to the target"
                )
        corpus: list[Evaluation] = []
        seen: set[tuple[Any, ...]] = set()
        for evaluation in [*self._warm_evals, *evaluations]:
            if not evaluation.is_valid or not math.isfinite(evaluation.scalar_score):
                continue
            if not self._has_compatible_params(evaluation):
                continue
            requires_warm_fingerprint = id(evaluation) in self._warm_evaluation_ids
            if (
                requires_warm_fingerprint
                and self._warm_start_admission is None
                and self._warm_compatibility(evaluation) is None
            ):
                continue
            if (
                self._warm_start_admission is None
                and _WARM_COMPATIBILITY_METADATA in evaluation.metadata
            ):
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
        try:
            canonical = self._space.normalize(evaluation.params)
        except (TypeError, ValueError):
            return False
        return len(normalized) == len(canonical) and all(
            not isinstance(raw, bool)
            and math.isfinite(value)
            and 0.0 <= value <= 1.0
            and math.isclose(value, expected, rel_tol=0, abs_tol=1e-12)
            for raw, value, expected in zip(
                evaluation.params_normalized, normalized, canonical, strict=True
            )
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
        admitted = [
            e
            for e in evaluations
            if e.is_valid and math.isfinite(e.scalar_score) and self._has_compatible_params(e)
        ]
        if not admitted:
            raise RuntimeError("No valid measured objective values available for GP fitting")
        self._training_record_ids = [
            hashlib.sha256(
                json.dumps(
                    {
                        "identity": self._evaluation_identity(e),
                        "numeric_basis": e.metadata.get("numeric_transfer_basis"),
                        "space": self._space.sobol_space_fingerprint(),
                        "params": e.params,
                        "scalar": e.scalar_score,
                    },
                    sort_keys=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            for e in admitted
        ]
        X = self._torch.tensor(
            [list(self._space.normalize(e.params)) for e in admitted],
            dtype=self._torch.float64,
            device=self._device,
        )
        Y = self._torch.tensor(
            [[-e.scalar_score] for e in admitted], dtype=self._torch.float64, device=self._device
        )
        self._train_X, self._train_y_bo = X, Y
        return X, Y

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
            self._fitted_record_ids = list(self._training_record_ids)
        except Exception as exc:
            raise RuntimeError(
                "GP append conditioning failed; no silent same-basis MLL refit"
            ) from exc

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
        self._refit_train_X = X.detach().clone()
        self._refit_train_y_bo = y_bo.detach().clone()
        self._fitted_record_ids = list(self._training_record_ids)
        self._refit_record_ids = list(self._training_record_ids)
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
            self._training_record_ids[: len(self._fitted_record_ids)] != self._fitted_record_ids
            or previous_X.shape[-1] != X.shape[-1]
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
        bounds = self._space.to_botorch_bounds().to(self._device)
        initial = self._acquisition_initial_conditions(acq, bounds, 1, restarts, raw_samples)
        return optimize_acqf(
            acq_function=acq,
            bounds=bounds,
            q=1,
            num_restarts=restarts,
            batch_initial_conditions=initial,
        )

    def _next_acquisition_seed(self) -> int:
        return int(self._torch.randint(0, 2**31 - 1, (1,), generator=self._torch_rng).item())

    def _acquisition_initial_conditions(self, acquisition, bounds, q, restarts, raw_samples):
        """Versioned local Sobol pool with stable finite-score restart ranking."""
        pool = self._torch.quasirandom.SobolEngine(
            q * self._space.dim, scramble=True, seed=self._next_acquisition_seed()
        ).draw(raw_samples, dtype=self._torch.float64)
        pool = pool.reshape(raw_samples, q, self._space.dim).to(self._device)
        pool = bounds[0] + pool * (bounds[1] - bounds[0])
        with self._torch.no_grad():
            scores = acquisition(pool).reshape(raw_samples)
        safe = self._torch.where(self._torch.isfinite(scores), scores, -self._torch.inf)
        order = self._torch.argsort(safe, descending=True, stable=True)
        return pool[order[: min(restarts, raw_samples)]]

    def _completed_candidates(self, evaluations):
        return [
            PolicyCandidate(params=e.params, metadata=e.metadata)
            for e in [*self._warm_evals, *evaluations]
            if e.params
        ]

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

    def _random_batch(self, evaluations, batch_size, source):
        output = []
        occupied = self._completed_candidates(evaluations)
        for _ in range(batch_size):
            output.append(self._non_duplicate_random([*occupied, *output], source=source))
        return output

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
            if self._space.same_execution(candidate_execution, other_execution):
                return True
        return False

    def _effective_execution(self, candidate: PolicyCandidate) -> dict[str, Any] | None:
        """Resolve a proposal to the typed parameters that will actually run."""
        if candidate.params:
            try:
                self._space.normalize(candidate.params)
            except (TypeError, ValueError):
                return None
            return dict(candidate.params)
        if candidate.params_normalized is not None:
            try:
                return self._space.denormalize(candidate.params_normalized)
            except (TypeError, ValueError):
                return None
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
                executed = self._torch.tensor(
                    self._space.normalize(params), dtype=tensor.dtype, device=tensor.device
                )
                posterior = self._model.posterior(executed.unsqueeze(0))
                mean_bo = float(posterior.mean.squeeze().item())
                std_bo = float(posterior.variance.sqrt().squeeze().item())
                predicted_mean = -mean_bo
                predicted_std = abs(std_bo)
        return self._space.candidate_from_vector(
            vector,
            acquisition_value=acquisition_value,
            predicted_mean=predicted_mean,
            predicted_std=predicted_std,
            source_strategy=source,
        )
