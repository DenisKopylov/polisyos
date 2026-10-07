"""Multi-objective Bayesian optimization strategy."""

from __future__ import annotations

import hashlib
import io
import json
import math
from collections.abc import Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass
from importlib.metadata import version
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.methods.autotune.pareto import (
    HypervolumeAssessment,
    HypervolumeResult,
    _finite_vector,
    compute_hypervolume_assessed,
    finite_real_scalar,
)
from polisyos.scientist.methods.search.objective import OptimizationDirection
from polisyos.scientist.methods.search.strategies._deps import (
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
from polisyos.scientist.methods.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.methods.search.strategies.errors import OptionalDependencyUnavailableError
from polisyos.scientist.methods.search.strategies.resource_arbiter import ResourceArbiter
from polisyos.scientist.methods.search.strategies.runtime import apply_torch_runtime_settings
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    PolicyCandidate,
    StrategyState,
)

logger = get_logger(__name__)


class _InvalidReferencePointError(ValueError):
    """The configured or derived float64 reference cannot be admitted."""


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
        if any(not isinstance(name, str) or not name for name in objective_names) or len(
            set(objective_names)
        ) != len(objective_names):
            raise ValueError("Declared objective names must be unique nonempty strings")
        if any(not isinstance(direction, OptimizationDirection) for direction in directions):
            raise ValueError("Declared objective directions must be supported")

        cfg = config or MOConfig()
        super().__init__(space=space, seed=cfg.seed)
        self._config = cfg
        self._objective_names = list(objective_names)
        self._directions = list(directions)
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
        self._last_objective_admission: dict[str, Any] = {
            "version": "mo_objective_admission.v1",
            "status": "unavailable",
            "input_count": 0,
            "assessed_count": 0,
            "rejected_rows": [],
        }

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
        self._iteration = len(evaluations)
        admitted = self._admit_objective_rows(evaluations, for_training=True)
        report = self.last_objective_admission
        try:
            candidate = self._suggest_admitted(admitted, pending)
        finally:
            self._last_objective_admission = report
        candidate.metadata["objective_admission"] = deepcopy(report)
        return candidate

    def _suggest_admitted(
        self, evaluations: list[Evaluation], pending: list[PolicyCandidate] | None
    ) -> PolicyCandidate:
        del pending
        if len(evaluations) < self._config.n_initial:
            return self._sobol_candidate(self._iteration, source="sobol_init")
        if not self._botorch_ready:
            return self._random_candidate(source="random_no_botorch")

        train_set = self._select_training_subset(evaluations)
        if len(train_set) >= max(3, len(self._objective_names)):
            self._reference_point_values([self._objective_vector(row) for row in train_set])
        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return self._random_candidate(source="random_hard_limit")
            if len(train_set) < max(3, len(self._objective_names)):
                return self._random_candidate(source="random_insufficient_data")
            try:
                X, Y = self._prepare_training_data(train_set)
                with self._owned_torch_random():
                    self._fit_model_list(X, Y)
                    candidate, acq_value = self._optimize_ehvi(soft_limit=soft, batch_size=1)
                return self._tensor_to_candidate(
                    candidate.squeeze(0),
                    source="ehvi",
                    acquisition_value=float(acq_value.squeeze().item()),
                )
            except _InvalidReferencePointError:
                raise
            except Exception as exc:
                logger.warning("MO optimization failed; random fallback: {}", exc)
                return self._random_candidate(source="random_fallback")

    def suggest_batch(
        self, evaluations: list[Evaluation], batch_size: int
    ) -> list[PolicyCandidate]:
        admitted = self._admit_objective_rows(evaluations, for_training=True)
        report = self.last_objective_admission
        try:
            candidates = self._suggest_batch_admitted(admitted, batch_size, len(evaluations))
        finally:
            self._last_objective_admission = report
        for candidate in candidates:
            candidate.metadata["objective_admission"] = deepcopy(report)
        return candidates

    def _suggest_batch_admitted(
        self, evaluations: list[Evaluation], batch_size: int, initial_index: int
    ) -> list[PolicyCandidate]:
        if batch_size < 1:
            return []
        if len(evaluations) < self._config.n_initial:
            return [
                self._sobol_candidate(initial_index + idx, source="sobol_init")
                for idx in range(batch_size)
            ]
        if not self._botorch_ready:
            return [self._random_candidate(source="random_no_botorch") for _ in range(batch_size)]

        train_set = self._select_training_subset(evaluations)
        if len(train_set) >= max(3, len(self._objective_names)):
            self._reference_point_values([self._objective_vector(row) for row in train_set])
        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return [
                    self._random_candidate(source="random_hard_limit") for _ in range(batch_size)
                ]
            if len(train_set) < max(3, len(self._objective_names)):
                return [
                    self._random_candidate(source="random_insufficient_data")
                    for _ in range(batch_size)
                ]
            try:
                X, Y = self._prepare_training_data(train_set)
                with self._owned_torch_random():
                    self._fit_model_list(X, Y)
                    candidates, _ = self._optimize_ehvi(soft_limit=soft, batch_size=batch_size)
                return [
                    self._tensor_to_candidate(candidates[idx], source="batch_qehvi")
                    for idx in range(batch_size)
                ]
            except _InvalidReferencePointError:
                raise
            except Exception as exc:
                logger.warning("MO batch optimization failed; random fallback: {}", exc)
                return [
                    self._random_candidate(source="random_batch_fallback")
                    for _ in range(batch_size)
                ]

    def get_pareto_front(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        valid = self._admit_objective_rows(evaluations)
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

    def compute_hypervolume_assessed(self, evaluations: list[Evaluation]) -> HypervolumeResult:
        """Exact volume for the existing direction-normalized maximizing reference.

        Configured ``ref_point`` retains its existing maximizing-coordinate
        convention. No metric-unit rescaling or new reference policy is applied.
        Indicator availability never changes complete-vector front membership.
        """
        valid = self._admit_objective_rows(evaluations)
        try:
            self._reference_configuration()
            invalid_reference = False
        except ValueError:
            invalid_reference = True
        if not valid or not self._botorch_ready:
            result = HypervolumeResult(
                value=None,
                assessment=HypervolumeAssessment(
                    version="hypervolume-assessment.v2",
                    status="unavailable",
                    basis="not_established",
                    reason="no_usable_inputs" if not valid else "optional_backend_unavailable",
                    profile="dominated_box_union.float64.maximize.v1",
                ),
            )
        elif invalid_reference:
            result = compute_hypervolume_assessed([], ())
        else:
            points = [tuple(self._objective_vector(evaluation)) for evaluation in valid]
            with self._arbiter.acquire("torch"):
                if self._ref_point is None:
                    Y = self._torch.tensor(points, dtype=self._torch.float64, device=self._device)
                    try:
                        self._update_ref_point(Y)
                    except _InvalidReferencePointError:
                        result = compute_hypervolume_assessed([], ())
                        self._last_hypervolume_result = result
                        return result
                reference = tuple(self._ref_point.detach().cpu().tolist())
                result = compute_hypervolume_assessed(points, reference)
        self._last_hypervolume_result = result
        return result

    def compute_hypervolume(self, evaluations: list[Evaluation]) -> float | None:
        """Null means unavailable; a measured zero remains a recomputed quantity."""
        return self.compute_hypervolume_assessed(evaluations).value

    @property
    def last_hypervolume_assessment(self) -> HypervolumeAssessment | None:
        result = getattr(self, "_last_hypervolume_result", None)
        return result.assessment if result is not None else None

    def get_state(self) -> StrategyState:
        """Persist the existing CPU refit-per-ask optimizer, including its fitted model."""
        base = super().get_state()
        profile = self._state_profile()
        metadata: dict[str, Any] = {
            **base.metadata,
            "mo_state_version": 1,
            "profile": profile,
            "backend": self._backend_identity() if self._botorch_ready else None,
            "config": asdict(self._config),
            "objective_names": list(self._objective_names),
            "directions": [direction.value for direction in self._directions],
            "ref_point": self._ref_point.tolist() if self._ref_point is not None else None,
            "train_X": None,
            "train_Y": None,
        }
        model_state = None
        if self._model is not None:
            self._assert_model_corpus(self._model, self._train_X, self._train_Y)
            buffer = io.BytesIO()
            self._torch.save(self._model.state_dict(), buffer)
            model_state = buffer.getvalue()
            metadata["train_X"] = self._train_X.tolist()
            metadata["train_Y"] = self._train_Y.tolist()
        elif self._train_X is not None or self._train_Y is not None:
            raise ValueError("MO checkpoint has training data without a fitted model")
        metadata["model_state_sha256"] = (
            hashlib.sha256(model_state).hexdigest() if model_state is not None else None
        )
        metadata["corpus_sha256"] = self._corpus_digest(metadata)
        rng_state = dict(base.rng_state)
        if self._torch_rng is not None:
            rng_state["torch"] = self._torch_rng.get_state().tolist()
        return StrategyState(
            "MOBayesianOptimizer", self._iteration, rng_state, model_state, metadata
        )

    def set_state(self, state: StrategyState) -> None:
        """Validate a complete numerical continuation before changing live state."""
        meta = state.metadata
        if (
            not isinstance(meta, Mapping)
            or type(meta.get("mo_state_version")) is not int
            or meta["mo_state_version"] != 1
            or meta.get("profile") != self._state_profile()
            or meta.get("backend") != (self._backend_identity() if self._botorch_ready else None)
        ):
            raise ValueError("MO checkpoint profile/backend is unsupported or changed")
        if (
            meta.get("objective_names") != self._objective_names
            or meta.get("directions") != [direction.value for direction in self._directions]
            or meta.get("space") != self._space.sobol_space_fingerprint()
        ):
            raise ValueError("MO checkpoint objective or search-space basis changed")
        cfg = meta.get("config")
        expected = asdict(self._config)
        if not isinstance(cfg, Mapping) or set(cfg) != set(expected):
            raise ValueError("MO checkpoint configuration is incomplete")
        for key, value in expected.items():
            actual = cfg[key]
            if isinstance(value, int) and type(actual) is not int:
                raise ValueError("MO checkpoint integer configuration is invalid")
            if isinstance(value, float) and finite_real_scalar(actual) is None:
                raise ValueError("MO checkpoint numeric configuration is invalid")
            if key != "seed" and actual != value:
                raise ValueError("MO checkpoint configuration changed")
        if cfg["ref_point"] is not None and (
            _finite_vector(cfg["ref_point"]) is None
            or len(cfg["ref_point"]) != len(self._objective_names)
        ):
            raise ValueError("MO checkpoint configured reference is invalid")
        if type(cfg["seed"]) is not int or cfg["seed"] != meta.get("seed"):
            raise ValueError("MO checkpoint seed basis changed")
        if meta.get("corpus_sha256") != self._corpus_digest(meta):
            raise ValueError("MO checkpoint corpus differs from its saved content binding")
        if state.model_state is not None and not isinstance(state.model_state, bytes):
            raise ValueError("MO checkpoint model requires bytes or null")
        expected_digest = (
            hashlib.sha256(state.model_state).hexdigest() if state.model_state is not None else None
        )
        if meta.get("model_state_sha256") != expected_digest:
            raise ValueError("MO checkpoint fitted model content changed")
        torch_rng = None
        if self._botorch_ready:
            raw_rng = state.rng_state.get("torch") if isinstance(state.rng_state, Mapping) else None
            if not isinstance(raw_rng, list) or any(
                type(v) is not int or not 0 <= v <= 255 for v in raw_rng
            ):
                raise ValueError("MO checkpoint Torch RNG bytes are invalid")
            try:
                torch_rng = self._torch.Generator()
                torch_rng.set_state(self._torch.tensor(raw_rng, dtype=self._torch.uint8))
            except (RuntimeError, TypeError) as exc:
                raise ValueError("MO checkpoint Torch RNG state is invalid") from exc
        elif isinstance(state.rng_state, Mapping) and "torch" in state.rng_state:
            raise ValueError("MO checkpoint requires its original numerical backend")
        reference = meta.get("ref_point")
        if reference is not None:
            admitted_reference = _finite_vector(reference)
            if admitted_reference is None or len(admitted_reference) != len(self._objective_names):
                raise ValueError("MO checkpoint reference is invalid")
            if not self._botorch_ready:
                raise ValueError("MO checkpoint reference requires its original numerical backend")
            if cfg["ref_point"] is not None and admitted_reference != _finite_vector(
                cfg["ref_point"]
            ):
                raise ValueError("MO checkpoint configured reference basis changed")
            reference = self._torch.tensor(
                admitted_reference, dtype=self._torch.float64, device=self._device
            )
        model = X = Y = None
        if state.model_state is not None:
            if not self._botorch_ready or reference is None:
                raise ValueError("MO checkpoint fitted model lacks its numerical basis")
            X, Y = self._checkpoint_tensors(meta)
            if tuple(reference.tolist()) != self._reference_point_values(Y.tolist()):
                raise ValueError("MO checkpoint fitted reference/corpus basis changed")
            try:
                weights = self._torch.load(
                    io.BytesIO(state.model_state), weights_only=True, map_location=self._device
                )
                if not isinstance(weights, Mapping) or any(
                    not self._torch.is_tensor(value) for value in weights.values()
                ):
                    raise ValueError("MO checkpoint learned state is malformed")
                models = []
                for index in range(len(self._objective_names)):
                    input_transform = Normalize(d=self._space.dim)
                    outcome_transform = Standardize(m=1)
                    for name, transform in (
                        ("input_transform", input_transform),
                        ("outcome_transform", outcome_transform),
                    ):
                        prefix = f"models.{index}.{name}."
                        transform.load_state_dict(
                            {
                                key[len(prefix) :]: value
                                for key, value in weights.items()
                                if key.startswith(prefix)
                            },
                            strict=True,
                        )
                        transform.eval()
                    models.append(
                        SingleTaskGP(
                            train_X=X,
                            train_Y=Y[:, index : index + 1],
                            input_transform=input_transform,
                            outcome_transform=outcome_transform,
                        )
                    )
                model = ModelListGP(*models)
                defaults = model.state_dict()
                for key, value in weights.items():
                    if (
                        key not in defaults
                        or value.dtype != defaults[key].dtype
                        or value.shape != defaults[key].shape
                    ):
                        raise ValueError("MO checkpoint learned tensor type/shape changed")
                    if not self._torch.isfinite(value).all() and (
                        key not in defaults or not self._torch.equal(value, defaults[key])
                    ):
                        raise ValueError("MO checkpoint nonfinite learned state changed")
                model.load_state_dict(weights, strict=True)
                if any(
                    not self._torch.equal(value, model.state_dict()[key])
                    for key, value in weights.items()
                ):
                    raise ValueError("MO checkpoint shared likelihood state is inconsistent")
                if any(not self._torch.isfinite(value).all() for value in model.parameters()):
                    raise ValueError("MO checkpoint fitted parameter is nonfinite")
                model.eval()
                self._assert_model_corpus(model, X, Y)
            except Exception as exc:
                raise ValueError("MO checkpoint fitted numerical model is invalid") from exc
        elif meta.get("train_X") is not None or meta.get("train_Y") is not None:
            raise ValueError("MO checkpoint lost its fitted model")
        super().set_state(state)
        self._config.seed = cfg["seed"]
        self._torch_rng = torch_rng
        self._ref_point = reference
        self._model, self._train_X, self._train_Y = model, X, Y

    def _state_profile(self) -> str:
        if not self._botorch_ready:
            return "mo.random_or_sobol.no_botorch.v1"
        if self._device != "cpu":
            raise ValueError("MO checkpoint supports the existing CPU numerical profile only")
        return "mo.single_task_gp.cpu.refit_each_ask.v1"

    @staticmethod
    def _backend_identity() -> dict[str, str]:
        return {
            **{name: version(name) for name in ("torch", "botorch", "gpytorch")},
            "torch_runtime": str(require_torch().__version__),
        }

    @staticmethod
    def _corpus_digest(meta) -> str:
        try:
            return hashlib.sha256(
                json.dumps(
                    {
                        key: meta[key]
                        for key in (
                            "profile",
                            "backend",
                            "config",
                            "objective_names",
                            "directions",
                            "space",
                            "seed",
                            "ref_point",
                            "train_X",
                            "train_Y",
                        )
                    },
                    sort_keys=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("MO checkpoint content basis is incomplete or nonfinite") from exc

    def _checkpoint_tensors(self, meta):
        matrices = []
        for name, dimension in (
            ("train_X", self._space.dim),
            ("train_Y", len(self._objective_names)),
        ):
            rows = meta.get(name)
            if (
                not isinstance(rows, list)
                or not rows
                or any(
                    not isinstance(row, list)
                    or len(row) != dimension
                    or any(finite_real_scalar(value) is None for value in row)
                    for row in rows
                )
            ):
                raise ValueError("MO checkpoint tensors require complete finite numerical rows")
            matrices.append(
                self._torch.tensor(rows, dtype=self._torch.float64, device=self._device)
            )
        X, Y = matrices
        if (
            len(X) != len(Y)
            or len(X) > self._config.max_train_size
            or (X < 0).any()
            or (X > 1).any()
        ):
            raise ValueError("MO checkpoint tensor shape/range changed")
        return X, Y

    def _assert_model_corpus(self, model, X, Y) -> None:
        if X is None or Y is None or len(model.models) != len(self._objective_names):
            raise ValueError("MO fitted corpus is missing")
        with self._torch.no_grad():
            for index, component in enumerate(model.models):
                if any(not self._torch.isfinite(value).all() for value in component.parameters()):
                    raise ValueError("MO fitted parameter is nonfinite")
                actual_X = component.train_inputs[0]
                transformed_X = component.transform_inputs(X)
                if not any(
                    expected.shape == actual_X.shape and self._torch.equal(expected, actual_X)
                    for expected in (X, transformed_X)
                ):
                    raise ValueError("MO fitted inputs differ from the saved corpus")
                expected_Y = component.outcome_transform(Y[:, index : index + 1])[0].squeeze(-1)
                if not self._torch.allclose(
                    component.train_targets, expected_Y, rtol=1e-12, atol=1e-12
                ):
                    raise ValueError("MO fitted targets differ from their transform/corpus")
                if (
                    not (component.covar_module.lengthscale > 0).all()
                    or not (component.likelihood.noise > 0).all()
                    or not (component.input_transform._coefficient > 0).all()
                    or not (component.outcome_transform.stdvs > 0).all()
                ):
                    raise ValueError("MO fitted numerical scales are invalid")

    @contextmanager
    def _owned_torch_random(self):
        if self._device != "cpu":
            yield
            return
        # Existing CPU acquisition/refit path owns this stream; ambient Torch
        # RNG and independently seeded replicas retain their own continuation.
        with self._torch.random.fork_rng(devices=[]):
            self._torch.set_rng_state(self._torch_rng.get_state())
            try:
                yield
            finally:
                self._torch_rng.set_state(self._torch.get_rng_state())

    def _select_training_subset(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        filtered = self._admit_objective_rows(evaluations, for_training=True)
        if len(filtered) <= self._config.max_train_size:
            return filtered
        recent_n = self._config.max_train_size // 2
        recent = filtered[-recent_n:]
        older = filtered[:-recent_n]
        step = max(1, len(older) // max(1, self._config.max_train_size - recent_n))
        sampled = older[::step][: self._config.max_train_size - recent_n]
        return sampled + recent

    def _prepare_training_data(self, evaluations: list[Evaluation]):
        admitted = self._admit_objective_rows(evaluations, for_training=True)
        if not admitted:
            raise ValueError("No complete finite declared objective vectors for training")
        X = self._torch.tensor(
            [list(self._space.normalize(e.params)) for e in admitted],
            dtype=self._torch.float64,
        )
        Y = self._torch.tensor(
            [self._objective_vector(evaluation) for evaluation in admitted],
            dtype=self._torch.float64,
        )
        if self._device != "cpu":
            X = X.to(self._device)
            Y = Y.to(self._device)
        return X, Y

    def _objective_vector(self, evaluation: Evaluation) -> list[float]:
        objective_values = {}
        for objective in evaluation.objectives:
            if objective.name not in self._objective_names:
                continue
            if objective.name in objective_values:
                raise ValueError(f"duplicate_declared_objective:{objective.name}")
            objective_values[objective.name] = objective
        output: list[float] = []
        for idx, objective_name in enumerate(self._objective_names):
            if objective_name not in objective_values:
                raise ValueError(f"missing_declared_objective:{objective_name}")
            objective = objective_values[objective_name]
            if objective.direction != self._directions[idx]:
                raise ValueError(f"objective_direction_mismatch:{objective_name}")
            raw = objective.raw_value
            scalar = _finite_vector((raw,))
            if scalar is None:
                raise ValueError(f"non_finite_or_untyped_objective:{objective_name}")
            output.append(scalar[0] * self._negate_mask[idx])
        return output

    @property
    def last_objective_admission(self) -> dict[str, Any]:
        """Original input coverage; excluded rows never become invented zero coordinates."""
        return deepcopy(self._last_objective_admission)

    def _admit_objective_rows(
        self, evaluations: list[Evaluation], *, for_training: bool = False
    ) -> list[Evaluation]:
        admitted = []
        rejected = []
        for index, evaluation in enumerate(evaluations):
            try:
                if not evaluation.is_valid:
                    raise ValueError("invalid_evaluation_outcome")
                self._objective_vector(evaluation)
                if for_training:
                    executed = self._space.normalize(evaluation.params)
                    supplied = _finite_vector(evaluation.params_normalized)
                    if (
                        supplied is None
                        or len(supplied) != len(executed)
                        or any(
                            not math.isclose(value, effective, rel_tol=0.0, abs_tol=1e-10)
                            for value, effective in zip(supplied, executed, strict=True)
                        )
                    ):
                        raise ValueError("executed_coordinates_mismatch")
                admitted.append(evaluation)
            except (TypeError, ValueError, OverflowError) as exc:
                rejected.append(
                    {
                        "input_index": index,
                        "candidate_id": evaluation.candidate_id,
                        "reason": str(exc),
                    }
                )
        self._last_objective_admission = {
            "version": "mo_objective_admission.v1",
            "status": "complete"
            if admitted and not rejected
            else "partial"
            if admitted
            else "unavailable",
            "input_count": len(evaluations),
            "assessed_count": len(admitted),
            "rejected_rows": rejected,
        }
        return admitted

    def _fit_model_list(self, X, Y) -> None:
        reference = self._torch.tensor(
            self._reference_point_values(Y.detach().cpu().tolist()),
            dtype=self._torch.float64,
            device=self._device,
        )
        models = [
            SingleTaskGP(
                train_X=X,
                train_Y=Y[:, idx : idx + 1],
                input_transform=Normalize(d=X.shape[-1]),
                outcome_transform=Standardize(m=1),
            )
            for idx in range(len(self._objective_names))
        ]
        model = ModelListGP(*models)
        mll = SumMarginalLogLikelihood(model.likelihood, model)
        fit_gpytorch_mll(mll)
        # A failed refit must retain the previous coherent model/corpus/reference
        # so its ordinary random-fallback checkpoint remains resumable.
        self._model, self._train_X, self._train_Y, self._ref_point = model, X, Y, reference

    def _reference_configuration(self) -> tuple[tuple[float, ...] | None, float | None]:
        """Admit configured numeric reference inputs before any tensor arithmetic."""
        if self._config.ref_point is not None:
            reference = _finite_vector(self._config.ref_point)
            if reference is None or len(reference) != len(self._objective_names):
                raise _InvalidReferencePointError("invalid_reference_point")
            return reference, None
        offset = finite_real_scalar(self._config.ref_point_offset)
        if offset is None:
            raise _InvalidReferencePointError("invalid_reference_point")
        return None, offset

    def _reference_point_values(self, points: list[list[float]]) -> tuple[float, ...]:
        """Admit geometry before tensors, model fitting, or fallback generation."""
        reference, configured_offset = self._reference_configuration()
        if reference is not None:
            return reference
        if not points or configured_offset is None:
            raise _InvalidReferencePointError("invalid_reference_point")
        values: list[float] = []
        for index in range(len(self._objective_names)):
            worst = min(point[index] for point in points)
            best = max(point[index] for point in points)
            span = finite_real_scalar(best - worst)
            if span is None:
                raise _InvalidReferencePointError("invalid_reference_point")
            value = finite_real_scalar(worst - configured_offset * span)
            if value is None:
                raise _InvalidReferencePointError("invalid_reference_point")
            values.append(value)
        return tuple(values)

    def _update_ref_point(self, Y) -> None:
        reference = self._reference_point_values(Y.detach().cpu().tolist())
        self._ref_point = self._torch.tensor(
            reference, dtype=self._torch.float64, device=self._device
        )

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
        return self._space.candidate_from_vector(
            vector,
            acquisition_value=acquisition_value,
            source_strategy=source,
            metadata={
                "prediction_basis": "not_established_no_scalar_predictor",
                "acquisition_value_basis": "relaxed_proposal"
                if acquisition_value is not None
                else "not_established",
            },
        )


def _dominates(lhs: list[float], rhs: list[float]) -> bool:
    better_or_equal = all(left >= right for left, right in zip(lhs, rhs))
    strictly_better = any(left > right for left, right in zip(lhs, rhs))
    return better_or_equal and strictly_better
