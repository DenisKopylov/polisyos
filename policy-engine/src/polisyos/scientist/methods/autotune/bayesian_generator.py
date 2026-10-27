"""Bayesian candidate generator wrapping the methods.search strategies module."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    CoreJSONArtifactStore,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
    matches_runtime_protocol_definition,
)
from polisyos.core.artifacts import (
    require_return_selected_profile_writer as _require_return_selected_profile_writer,
)
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    _assess_search_metric,
    _configured_search_metric_binding,
    _configured_search_metric_profile_fingerprint,
    _evaluation_matches_selected_objectives,
    _unestablished_score_assessment,
)
from polisyos.scientist.methods.search.strategies.space import (
    SearchSpace as NativeSearchSpace,
)
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
)

from .models import (
    BayesianSourceProfile,
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    SearchGPFitBasis,
    SearchGPFitBound,
    SearchGPFitConfig,
    SearchMethodRunProfile,
)

logger = logging.getLogger(__name__)

_MISSING = object()
_INVALID = object()
_IDENTITY_KEYS = frozenset(
    {
        "subject",
        "subject_id",
        "subject_version",
        "search_space_version",
        "data_snapshot",
        "dataset_version",
        "split",
        "origin",
        "candidate_id",
        "evaluation_id",
        "provenance_ref",
        "replicate_id",
        "replica_id",
        "seed",
    }
)


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _identity_value(value: Any) -> Any:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, ArtifactID):
        return str(value)
    return value


def _merge_identity_sources(
    sources: tuple[Mapping[str, Any], ...],
) -> dict[str, Any] | None:
    """Merge identity claims only when every explicit claim agrees."""
    identity: dict[str, Any] = {}
    for source in sources:
        for key in _IDENTITY_KEYS:
            if key not in source or source[key] is None:
                continue
            value = _identity_value(source[key])
            if key in identity and identity[key] != value:
                return None
            identity[key] = value
    return identity


def _finite_float(value: Any) -> float | object:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return _INVALID
    return result if math.isfinite(result) else _INVALID


def _try_import_bayesian():
    """Lazy import of BayesianOptimizer and dependencies."""
    try:
        from polisyos.scientist.methods.search.objective import (
            ObjectiveValue,
            OptimizationDirection,
        )
        from polisyos.scientist.methods.search.strategies.bayesian import (
            BayesianConfig,
            BayesianOptimizer,
        )
        from polisyos.scientist.methods.search.strategies.types import (
            Evaluation,
            EvaluationStatus,
            ParameterBounds,
        )

        return (
            BayesianConfig,
            BayesianOptimizer,
            Evaluation,
            EvaluationStatus,
            ParameterBounds,
            ObjectiveValue,
            OptimizationDirection,
        )
    except ImportError:
        return None


class SearchSpace:
    """Autotune adapter backed by the canonical strategy ``SearchSpace``."""

    def __init__(self, bounds: list[dict[str, Any] | ParameterBounds]) -> None:
        self._native = NativeSearchSpace(
            bounds=[self._to_parameter_bound(bound) for bound in bounds]
        )

    @staticmethod
    def _to_parameter_bound(bound: dict[str, Any] | ParameterBounds) -> ParameterBounds:
        if isinstance(bound, ParameterBounds):
            return bound

        raw_dtype = bound.get("dtype", ParameterType.CONTINUOUS)
        dtype = raw_dtype if isinstance(raw_dtype, ParameterType) else ParameterType(raw_dtype)
        categories = bound.get("categories")
        if categories is not None:
            categories = tuple(categories)
        lower = bound.get("lower", 0.0)
        upper = bound.get("upper", 1.0)
        if lower is None:
            lower = 0.0
        if upper is None:
            upper = 1.0
        return ParameterBounds(
            name=str(bound["name"]),
            lower=lower,
            upper=upper,
            dtype=dtype,
            log_scale=bool(bound.get("log_scale", False)),
            categories=categories,
        )

    @property
    def bounds(self) -> list[ParameterBounds]:
        """Return the canonical parameter bounds used by the strategy."""
        return self._native.bounds

    @property
    def dim(self) -> int:
        return self._native.dim

    @property
    def param_bounds(self) -> list[Any]:
        """Compatibility alias for consumers that inspect parameter bounds."""
        return self._native.bounds

    @property
    def names(self) -> list[str]:
        """Return canonical expanded parameter names."""
        return self._native.names

    def normalize(self, params: dict[str, Any]) -> tuple[float, ...]:
        """Normalize parameters through the canonical strategy implementation."""
        return self._native.normalize(params)

    def denormalize(self, vector: tuple[float, ...]) -> dict[str, Any]:
        """Resolve a relaxed vector to the effective typed execution."""
        return self._native.denormalize(vector)

    def sample_sobol(self, n_samples: int, seed: int = 42) -> list[tuple[float, ...]]:
        """Sample relaxed vectors through the canonical strategy implementation."""
        return self._native.sample_sobol(n_samples=n_samples, seed=seed)

    def to_botorch_bounds(self) -> Any:
        """Delegate optional BoTorch bounds construction to the native space."""
        return self._native.to_botorch_bounds()


class BayesianCandidateGenerator:
    """CandidateGenerator backed by GP-based Bayesian optimization.

    Falls back to returning the last known best when botorch is unavailable.
    """

    def __init__(
        self,
        search_space: SearchSpace | None = None,
        *,
        primary_metric: str = "score",
        direction: MetricDirection = MetricDirection.MAXIMIZE,
        unit: str | None = None,
        compare_split: BenchmarkSplit = BenchmarkSplit.HOLDOUT,
        n_initial: int = 6,
        seed: int = 42,
    ) -> None:
        self._primary_metric = primary_metric
        self._direction = direction
        self._selected_objective_unit = unit
        self._selected_objective_binding = _configured_search_metric_binding(
            primary_metric, direction.value, unit
        )
        if self._selected_objective_binding is None:
            raise ValueError("Bayesian candidate generation requires a configured scalar objective")
        self._compare_split = compare_split
        self._search_space = search_space
        self._n_initial = n_initial
        self._seed = seed
        self._optimizer: Any = None
        self._botorch_available = False
        self._warm_evals: list[Any] = []
        self._warm_start_rejections: list[dict[str, str]] = []
        self._warm_start_applied = False
        self._warm_start_context_fingerprint: str | None = None
        self._warm_start_accepted_count = 0
        self._search_run_context_fingerprint: str | None = None
        self._source_store: CoreJSONArtifactStore | None = None
        self._issued_source_profiles: dict[
            str,
            tuple[
                BayesianSourceProfile,
                dict[str, Any],
                ArtifactRef | None,
                dict[str, Any],
            ],
        ] = {}
        self._search_method_run_profile: SearchMethodRunProfile | None = None

        deps = _try_import_bayesian()
        if deps is not None and search_space is not None:
            BayesianConfig, BayesianOptimizer, _, _, _, _, _ = deps
            try:
                cfg = BayesianConfig(n_initial=n_initial, seed=seed)
                objective_name, _, _ = self._selected_objective_binding
                self._optimizer = BayesianOptimizer(
                    search_space._native,
                    config=cfg,
                    objective_name=objective_name,
                    objective_source_direction=direction.value,
                    objective_source_unit=unit,
                )
                self._botorch_available = True
            except Exception as exc:
                logger.warning("BayesianCandidateGenerator: optimizer init failed: %s", exc)

    @property
    def botorch_available(self) -> bool:
        return self._botorch_available

    def warm_start(self, evaluations: list[Any]) -> None:
        """Queue historical evaluations for context-bound admission on generation."""
        if self._warm_start_applied:
            raise RuntimeError("warm-start history must be supplied before generation")
        self._warm_evals.extend(evaluations)

    def warm_start_for_context(
        self,
        evaluations: list[Any],
        *,
        context: dict[str, Any],
    ) -> None:
        """Queue and admit historical evaluations against the actual target context."""
        self.warm_start(evaluations)
        self._apply_warm_start(context)

    def set_search_run_context(self, context: dict[str, Any]) -> None:
        """Freeze the caller context used to bind search history and GP profiles."""
        context_fingerprint = self._profile_fingerprint(context)
        if (
            self._search_run_context_fingerprint is not None
            and context_fingerprint != self._search_run_context_fingerprint
        ):
            raise RuntimeError("search context changed; create a fresh candidate generator")
        if self._warm_start_accepted_count:
            raise RuntimeError("use a fresh BayesianCandidateGenerator for a new search run")
        self._search_run_context_fingerprint = context_fingerprint
        self._warm_start_applied = False
        self._warm_start_context_fingerprint = None
        self._warm_start_rejections.clear()
        self._warm_evals.clear()
        self._issued_source_profiles.clear()
        self._search_method_run_profile = None

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        # A source profile is valid for only the proposal currently crossing the
        # generator/runner boundary. Drop any proposal a prior caller did not use.
        self._issued_source_profiles.clear()
        if not self._botorch_available or self._optimizer is None:
            return self._fallback_generate(history, current_best, context)

        if self._search_run_context_fingerprint is None:
            self._search_run_context_fingerprint = self._profile_fingerprint(context)
        run_context_fingerprint = self._search_run_context_fingerprint
        self._set_optimizer_run_profile(run_context_fingerprint)
        self._apply_warm_start(context)
        evals = self._history_to_evaluations(history)
        try:
            deps = _try_import_bayesian()
            native_optimizer_type = deps[1] if deps is not None else None
            if native_optimizer_type is not None and type(self._optimizer) is native_optimizer_type:
                candidate = native_optimizer_type.suggest(
                    self._optimizer, evals, attempted_count=len(history)
                )
            else:
                candidate = self._optimizer.suggest(evals)
            profile = self._build_source_profile(
                candidate=candidate,
                evaluations=evals,
                context=context,
            )
            fit_basis_ref = self._persist_gp_fit_basis(profile)
            if profile.warm_start_eligible and fit_basis_ref is None:
                profile = profile.model_copy(update={"warm_start_eligible": False})
            candidate.metadata["warm_start_compatibility"] = profile.model_dump(
                mode="json",
                exclude_none=True,
            )
            candidate_payload = candidate.to_dict()
            candidate_id = getattr(candidate, "candidate_id", None)
            if isinstance(candidate_id, str):
                self._issued_source_profiles[candidate_id] = (
                    profile,
                    dict(getattr(candidate, "params", {}) or {}),
                    fit_basis_ref,
                    {
                        "source": getattr(candidate, "source_strategy", None),
                        "acquisition_type": _as_mapping(
                            candidate_payload.get("_strategy_metadata")
                        ).get("acquisition_type"),
                        "predicted_mean": getattr(candidate, "predicted_mean", None),
                        "predicted_std": getattr(candidate, "predicted_std", None),
                        "acquisition_value": getattr(candidate, "acquisition_value", None),
                    },
                )
            return candidate_payload
        except Exception as exc:
            logger.warning("BayesianCandidateGenerator: suggest failed: %s", exc)
            return self._fallback_generate(history, current_best, context)

    def _apply_warm_start(self, context: dict[str, Any]) -> None:
        """Admit only source profiles compatible with this configured target run."""
        context_fingerprint = (
            self._search_run_context_fingerprint
            if self._search_run_context_fingerprint is not None
            else self._profile_fingerprint(context)
        )
        if self._warm_start_applied:
            if (
                self._warm_start_accepted_count
                and context_fingerprint != self._warm_start_context_fingerprint
            ):
                raise RuntimeError(
                    "search context changed after compatible warm-start data was admitted"
                )
            return
        self._warm_start_applied = True
        self._warm_start_context_fingerprint = context_fingerprint
        optimizer = self._optimizer
        if optimizer is None:
            return

        deps = _try_import_bayesian()
        native_optimizer_type = deps[1] if deps is not None else None
        ready_property = (
            getattr(native_optimizer_type, "native_gp_ready", None)
            if native_optimizer_type is not None
            else None
        )
        ready_getter = getattr(ready_property, "fget", None)
        native_ready = (
            bool(ready_getter(optimizer))
            if callable(ready_getter) and type(optimizer) is native_optimizer_type
            else False
        )
        if (
            native_optimizer_type is None
            or type(optimizer) is not native_optimizer_type
            or not native_ready
        ):
            self._warm_start_rejections.extend(
                {"reason": "target optimizer is not configured native GP"} for _ in self._warm_evals
            )
            return
        compatible_profiles: list[Any] = []
        from .source_profile_verification import _verify_search_source_profile_receipt

        target_method_run_profile = self._search_method_run_profile
        if target_method_run_profile is None:
            self._warm_start_rejections.extend(
                {"reason": "target MethodJob run profile is not established"}
                for _ in self._warm_evals
            )
            return

        for evaluation in self._warm_evals:
            objective_name, objective_direction, expected_rule_spec = (
                self._selected_objective_binding
            )
            if not _evaluation_matches_selected_objectives(
                evaluation,
                objective_names=[objective_name],
                objective_directions={objective_name: objective_direction},
                objective_rule_specs={objective_name: expected_rule_spec},
                require_scalar_score=True,
            ):
                self._warm_start_rejections.append(
                    {"reason": "selected primary metric rule not reconciled"}
                )
                continue
            metadata = getattr(evaluation, "metadata", None)
            if (
                not isinstance(metadata, Mapping)
                or not isinstance(metadata.get("search_source_profile_receipt"), Mapping)
                or not isinstance(metadata.get("warm_start_compatibility"), Mapping)
                or metadata.get("search_source_evaluation_ref") is None
            ):
                self._warm_start_rejections.append({"reason": "source profile receipt missing"})
                continue
            raw_profile = metadata.get("warm_start_compatibility")
            if (
                not isinstance(raw_profile, Mapping)
                or raw_profile.get("warm_start_eligible") is not True
            ):
                self._warm_start_rejections.append(
                    {"reason": "missing or incompatible warm-start fingerprint"}
                )
                continue
            verified = _verify_search_source_profile_receipt(
                store=self._source_store,
                evaluation_ref=metadata.get("search_source_evaluation_ref"),
                expected_receipt=metadata.get("search_source_profile_receipt"),
                expected_profile=metadata.get("warm_start_compatibility"),
                expected_params=getattr(evaluation, "params", None),
                expected_scalar=getattr(evaluation, "scalar_score", None),
                expected_candidate_id=getattr(evaluation, "candidate_id", None),
                expected_provenance_ref=getattr(evaluation, "provenance_ref", None),
                expected_method_run_profile=target_method_run_profile,
                require_warm_start_eligible=True,
            )
            if verified is None:
                self._warm_start_rejections.append(
                    {"reason": "source profile receipt or CAS chain invalid"}
                )
                continue
            compatible_profiles.append(evaluation)

        objective_fingerprint = self._objective_profile_fingerprint()
        accepted_before = optimizer.warm_start_accepted_count
        rejected_before = len(optimizer.warm_start_rejections)
        from polisyos.scientist.methods.search.strategies.bayesian import (
            _issue_verified_warm_start_admission,
        )

        optimizer_type = native_optimizer_type
        optimizer_type.warm_start(
            optimizer,
            compatible_profiles,
            target_context_fingerprint=context_fingerprint,
            target_objective_fingerprint=objective_fingerprint,
            _source_admission=_issue_verified_warm_start_admission(compatible_profiles),
        )
        self._warm_start_accepted_count = optimizer.warm_start_accepted_count - accepted_before
        self._warm_start_rejections.extend(
            {"reason": str(rejection.get("reason", "warm-start rejected"))}
            for rejection in optimizer.warm_start_rejections[rejected_before:]
        )

    def _build_source_profile(
        self,
        *,
        candidate: Any,
        evaluations: list[Any],
        context: dict[str, Any],
    ) -> BayesianSourceProfile:
        """Describe the effective optimizer, fit, context, and corpus for one proposal."""
        optimizer = self._optimizer
        context_fingerprint = (
            self._search_run_context_fingerprint
            if self._search_run_context_fingerprint is not None
            else self._profile_fingerprint(context)
        )
        deps = _try_import_bayesian()
        native_optimizer_type = deps[1] if deps is not None else None
        if native_optimizer_type is not None and type(optimizer) is native_optimizer_type:
            fit_profile = native_optimizer_type.effective_fit_profile(
                optimizer,
                proposal_source=str(getattr(candidate, "source_strategy", "unknown")),
                context_fingerprint=context_fingerprint,
                objective_fingerprint=self._objective_profile_fingerprint(),
            )
            payload = asdict(fit_profile) if is_dataclass(fit_profile) else dict(fit_profile)
            return BayesianSourceProfile.model_validate(payload)

        optimizer_fqn = (
            f"{type(optimizer).__module__}.{type(optimizer).__qualname__}"
            if optimizer is not None
            else None
        )
        if optimizer is None:
            profile_kind = "fallback"
        else:
            profile_kind = "injected_optimizer"

        native_space = getattr(optimizer, "_space", None)
        space_fingerprint = None
        space_fingerprint_fn = getattr(native_space, "sobol_space_fingerprint", None)
        if callable(space_fingerprint_fn):
            space_fingerprint = str(space_fingerprint_fn())

        effective_corpus: list[Any] | None = None
        effective_corpus_fn = getattr(optimizer, "_effective_training_corpus", None)
        if callable(effective_corpus_fn):
            try:
                result = effective_corpus_fn(evaluations)
                if isinstance(result, (list, tuple)):
                    effective_corpus = list(result)
            except Exception:
                effective_corpus = None
        corpus_records = None
        if effective_corpus is not None:
            corpus_records = [
                {
                    "candidate_id": getattr(item, "candidate_id", None),
                    "params": dict(getattr(item, "params", {}) or {}),
                    "params_normalized": list(getattr(item, "params_normalized", ()) or ()),
                    "scalar_score": getattr(item, "scalar_score", None),
                    "status": getattr(getattr(item, "status", None), "value", None),
                    "provenance_ref": getattr(item, "provenance_ref", None),
                }
                for item in effective_corpus
            ]
        corpus_fingerprint = self._profile_fingerprint(corpus_records)
        config = getattr(optimizer, "_config", None)
        config_payload: Any = vars(config) if hasattr(config, "__dict__") else config
        config_fingerprint = self._profile_fingerprint(config_payload)

        model = getattr(optimizer, "_model", None)
        model_fqn = (
            f"{type(model).__module__}.{type(model).__qualname__}" if model is not None else None
        )
        proposal_source = str(getattr(candidate, "source_strategy", "unknown"))
        return BayesianSourceProfile(
            profile_kind=profile_kind,
            optimizer_fqn=optimizer_fqn,
            optimizer_config_fingerprint=config_fingerprint,
            proposal_source=proposal_source,
            search_space_fingerprint=space_fingerprint,
            input_transform_fingerprint=None,
            input_transform_state_fingerprint=None,
            outcome_transform_fingerprint=None,
            outcome_transform_state_fingerprint=None,
            noise_model_fingerprint=None,
            noise_model_state_fingerprint=None,
            objective_fingerprint=self._objective_profile_fingerprint(),
            context_fingerprint=context_fingerprint,
            training_corpus_fingerprint=corpus_fingerprint,
            training_observation_count=(
                len(effective_corpus) if effective_corpus is not None else None
            ),
            gp_model_fqn=model_fqn,
            warm_start_eligible=False,
        )

    def set_search_method_run_profile(self, profile: SearchMethodRunProfile | None) -> None:
        """Bind the immutable MethodJob/data basis used by this search run."""
        if profile is not None and not isinstance(profile, SearchMethodRunProfile):
            raise TypeError("Search MethodJob run profile must be a validated typed record")
        if profile is not None:
            profile_binding = _configured_search_metric_binding(
                profile.primary_metric, profile.direction, profile.unit
            )
            if (
                profile_binding is None
                or self._selected_objective_binding is None
                or profile_binding[:2] != self._selected_objective_binding[:2]
                or profile.objective_fingerprint
                != _configured_search_metric_profile_fingerprint(
                    profile.primary_metric, profile.direction, profile.unit
                )
            ):
                raise ValueError(
                    "Search MethodJob profile differs from the selected Bayesian objective basis"
                )
            if (
                self._selected_objective_unit is not None
                and profile.unit != self._selected_objective_unit
            ):
                raise ValueError("Search MethodJob profile changes the selected objective unit")
            self._selected_objective_unit = profile.unit
            self._selected_objective_binding = profile_binding
        if (
            self._search_method_run_profile is not None
            and profile != self._search_method_run_profile
        ):
            raise RuntimeError("Search MethodJob run profile is immutable for this generator")
        self._search_method_run_profile = profile
        if profile is not None and self._search_run_context_fingerprint is not None:
            self._set_optimizer_run_profile(self._search_run_context_fingerprint)

    def _persist_gp_fit_basis(self, profile: BayesianSourceProfile) -> ArtifactRef | None:
        """Persist the selected, complete rows required for a fresh native GP refit."""
        optimizer = self._optimizer
        source_store = self._source_store
        if (
            not profile.warm_start_eligible
            or source_store is None
            or not matches_runtime_protocol_definition(source_store, CoreJSONArtifactStore)
            or self._search_method_run_profile is None
            or optimizer is None
        ):
            return None
        deps = _try_import_bayesian()
        native_optimizer_type = deps[1] if deps is not None else None
        if native_optimizer_type is None or type(optimizer) is not native_optimizer_type:
            return None
        refs = getattr(optimizer, "_last_fitted_training_evaluation_refs", None)
        if not isinstance(refs, list) or len(refs) != profile.training_observation_count:
            return None
        acquisition_refs = getattr(
            optimizer,
            "_last_acquisition_training_evaluation_refs",
            None,
        )
        acquisition_count = getattr(
            optimizer,
            "_last_acquisition_training_observation_count",
            None,
        )
        if (
            not isinstance(acquisition_refs, list)
            or not acquisition_refs
            or type(acquisition_count) is not int
            or acquisition_count != len(acquisition_refs)
            or acquisition_count < len(refs)
        ):
            return None
        model_state_fingerprint = optimizer._fitted_model_state_fingerprint()
        if not isinstance(model_state_fingerprint, str) or len(model_state_fingerprint) != 64:
            return None
        try:
            # Refuse a writer that cannot return the exact manifest profile before
            # building or attempting to persist the selected fit basis.
            _require_return_selected_profile_writer(source_store, "put_json")
            fit_config_payload = asdict(optimizer._config)
            fit_config_payload["acquisition"] = getattr(
                fit_config_payload.get("acquisition"),
                "value",
                fit_config_payload.get("acquisition"),
            )
            fit_config = SearchGPFitConfig.model_validate(fit_config_payload)
            bounds = [
                SearchGPFitBound(
                    name=bound.name,
                    lower=float(bound.lower),
                    upper=float(bound.upper),
                    dtype=bound.dtype.value,
                    log_scale=bool(bound.log_scale),
                    categories=(list(bound.categories) if bound.categories is not None else None),
                )
                for bound in self._search_space.bounds
            ]
            selected_refs = [ArtifactRef.model_validate(ref) for ref in refs]
            selected_acquisition_refs = [
                ArtifactRef.model_validate(ref) for ref in acquisition_refs
            ]
            basis = SearchGPFitBasis(
                schema_version="2",
                run_profile=self._search_method_run_profile,
                fit_config=fit_config,
                bounds=bounds,
                training_evaluation_refs=selected_refs,
                training_observation_count=len(selected_refs),
                acquisition_evaluation_refs=selected_acquisition_refs,
                acquisition_observation_count=len(selected_acquisition_refs),
                fit_backend=str(getattr(optimizer, "_device", "unknown")),
                fitted_model_state_fingerprint=model_state_fingerprint,
                proposal_source=profile.proposal_source,
                profile=profile,
            )
            basis_ref = source_store.put_json(
                basis,
                ArtifactWriteOptions(
                    kind="scientist.autotune.search_gp_fit_basis",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.methods.autotune.SearchGPFitBasis",
                        version="2.0",
                    ),
                    producer=ProducerInfo(
                        component="polisyos.scientist.methods.autotune.bayesian_generator",
                        version="2.0",
                    ),
                    inputs=[
                        input_ref_from_artifact_ref(ref, role="training_evaluation")
                        for ref in selected_refs
                    ]
                    + [
                        input_ref_from_artifact_ref(ref, role="acquisition_evaluation")
                        for ref in selected_acquisition_refs
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
                return_selected_profile=True,
            )
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return None
        if basis_ref.manifest_profile_sha256 is None:
            return None
        return basis_ref

    def _objective_profile_fingerprint(self, *, unit: str | None = None) -> str | None:
        """Bind the selected metric rule and declared unit to optimizer compatibility."""
        if unit is None:
            unit = self._selected_objective_unit
        return _configured_search_metric_profile_fingerprint(
            self._primary_metric, self._direction.value, unit
        )

    def _set_optimizer_run_profile(self, context_fingerprint: str | None) -> None:
        """Pass the immutable context/objective header to the canonical strategy."""
        deps = _try_import_bayesian()
        native_optimizer_type = deps[1] if deps is not None else None
        objective_fingerprint = self._objective_profile_fingerprint()
        if (
            native_optimizer_type is not None
            and type(self._optimizer) is native_optimizer_type
            and context_fingerprint
            and objective_fingerprint
        ):
            native_optimizer_type.set_search_run_profile(
                self._optimizer,
                context_fingerprint=context_fingerprint,
                objective_fingerprint=objective_fingerprint,
                objective_unit=self._selected_objective_unit,
            )

    def _configure_source_store(self, store: CoreJSONArtifactStore) -> None:
        """Bind the CAS used by this runtime for fresh-read source verification."""
        self._source_store = store

    def _consume_issued_source_profile(
        self, candidate_payload: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """Consume one canonical proposal profile only when the emitted row is unchanged."""
        strategy_metadata = _as_mapping(candidate_payload.get("_strategy_metadata"))
        proposal_id = strategy_metadata.get("candidate_id")
        if not isinstance(proposal_id, str):
            return None
        issued = self._issued_source_profiles.pop(proposal_id, None)
        if issued is None:
            return None
        profile, issued_params, fit_basis_ref, issued_prediction = issued
        raw_profile = strategy_metadata.get("warm_start_compatibility")
        if not isinstance(raw_profile, Mapping):
            return None
        try:
            if BayesianSourceProfile.model_validate(raw_profile) != profile:
                return None
        except ValidationError:
            return None
        names = {bound.name for bound in self._search_space.bounds} if self._search_space else set()
        actual_params = {
            name: candidate_payload[name] for name in names if name in candidate_payload
        }
        if (
            names != set(issued_params)
            or self._profile_fingerprint(actual_params) != self._profile_fingerprint(issued_params)
            or strategy_metadata.get("source") != profile.proposal_source
        ):
            return None
        proposal_prediction: dict[str, Any] | None = None
        if profile.warm_start_eligible:
            if (
                profile.profile_kind != "configured_native_gp"
                or profile.proposal_source != "bayesian_acquisition"
                or fit_basis_ref is None
                or issued_prediction.get("source") != profile.proposal_source
            ):
                return None
            acquisition_type = issued_prediction.get("acquisition_type")
            if (
                not isinstance(acquisition_type, str)
                or strategy_metadata.get("acquisition_type") != acquisition_type
            ):
                return None
            values: dict[str, float] = {}
            for name in ("predicted_mean", "predicted_std", "acquisition_value"):
                expected = issued_prediction.get(name)
                actual = strategy_metadata.get(name)
                if (
                    isinstance(expected, bool)
                    or type(expected) not in {int, float}
                    or not math.isfinite(float(expected))
                    or isinstance(actual, bool)
                    or type(actual) not in {int, float}
                    or not math.isfinite(float(actual))
                    or float(actual) != float(expected)
                ):
                    return None
                values[name] = float(expected)
            if values["predicted_std"] < 0:
                return None
            proposal_prediction = {
                "acquisition_type": acquisition_type,
                **values,
            }
        return {
            "proposal_id": proposal_id,
            "params": dict(issued_params),
            "profile": profile,
            "fit_basis_ref": fit_basis_ref,
            "proposal_prediction": proposal_prediction,
        }

    @staticmethod
    def _profile_fingerprint(value: Any) -> str | None:
        if value is None:
            return None
        try:
            return fingerprint(
                value,
                canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
            )
        except (TypeError, ValueError, OverflowError):
            return None

    def _fallback_generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if current_best is not None:
            return dict(current_best)
        if history:
            last = history[-1]
            if isinstance(last, dict):
                return dict(last)
        return dict(context) if context else {}

    @staticmethod
    def _history_parts(
        entry: Any,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
    ]:
        """Extract candidate, stage-B, entry, and entry-metadata mappings."""
        if isinstance(entry, Mapping):
            entry_mapping = dict(entry)
            candidate = _as_mapping(entry_mapping.get("candidate", entry_mapping))
            stage_b_result = _as_mapping(entry_mapping.get("stage_b_result"))
            entry_metadata = _as_mapping(entry_mapping.get("metadata"))
            return candidate, stage_b_result, entry_mapping, entry_metadata

        candidate = _as_mapping(getattr(entry, "candidate", None))
        stage_b_result = _as_mapping(getattr(entry, "stage_b_result", None))
        entry_metadata = _as_mapping(getattr(entry, "metadata", None))
        return candidate, stage_b_result, {}, entry_metadata

    def _history_params(
        self,
        *,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any],
        entry_mapping: dict[str, Any],
    ) -> dict[str, Any]:
        for source in (stage_b_result, candidate, entry_mapping):
            explicit = source.get("params")
            if isinstance(explicit, Mapping):
                return dict(explicit)

        reserved = {
            self._primary_metric,
            "candidate",
            "stage_b_result",
            "objective_value",
            "objective_details",
            "is_promising",
            "stage_a_passed",
            "duration_seconds",
            "timestamp",
            "policy_evaluation",
            "semantic",
            "_strategy_metadata",
            "metadata",
        }
        return {key: value for key, value in candidate.items() if key not in reserved}

    def _history_score(
        self,
        *,
        entry: Any,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any],
        entry_mapping: dict[str, Any],
    ) -> tuple[float | object, bool]:
        """Return one finite metric and whether it is already scalarized."""
        metric_sources = (
            stage_b_result,
            _as_mapping(stage_b_result.get("simulation_results")),
            _as_mapping(stage_b_result.get("metrics")),
            entry_mapping,
            candidate,
        )
        for source in metric_sources:
            if self._primary_metric not in source:
                continue
            value = _finite_float(source[self._primary_metric])
            return value, False

        objective_details = getattr(entry, "objective_details", None)
        if objective_details is None:
            objective_details = entry_mapping.get("objective_details")
        if isinstance(objective_details, list):
            for objective in objective_details:
                if isinstance(objective, Mapping):
                    name = objective.get("name")
                    raw_value = objective.get("raw_value")
                else:
                    name = getattr(objective, "name", None)
                    raw_value = getattr(objective, "raw_value", None)
                if name == self._primary_metric:
                    value = _finite_float(raw_value)
                    return value, False

        objective_value = getattr(entry, "objective_value", _MISSING)
        if objective_value is _MISSING:
            objective_value = entry_mapping.get("objective_value", _MISSING)
        if objective_value is not _MISSING:
            value = _finite_float(objective_value)
            return value, True
        return _MISSING, True

    @staticmethod
    def _history_identity(
        *,
        candidate: dict[str, Any],
        stage_b_result: dict[str, Any],
        entry_mapping: dict[str, Any],
        entry_metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidate_metadata = _as_mapping(candidate.get("_strategy_metadata"))
        stage_b_metadata = _as_mapping(stage_b_result.get("metadata"))
        return _merge_identity_sources(
            (
                entry_mapping,
                entry_metadata,
                candidate,
                candidate_metadata,
                stage_b_result,
                stage_b_metadata,
            )
        )

    def _history_to_evaluations(self, history: list[Any]) -> list[Any]:
        deps = _try_import_bayesian()
        if deps is None or self._search_space is None:
            return []
        _, _, Evaluation, EvaluationStatus, _, ObjectiveValue, OptimizationDirection = deps

        evaluations: list[Any] = []
        required_names = {bound.name for bound in self._search_space.bounds}
        for idx, entry in enumerate(history):
            candidate, stage_b_result, entry_mapping, entry_metadata = self._history_parts(entry)
            params = self._history_params(
                candidate=candidate,
                stage_b_result=stage_b_result,
                entry_mapping=entry_mapping,
            )
            if not required_names.issubset(params):
                logger.warning(
                    "Skipping history entry %s: candidate params are incomplete for the search space",
                    idx,
                )
                continue
            try:
                normalized = tuple(self._search_space.normalize(params))
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping history entry %s: candidate params cannot be normalized",
                    idx,
                )
                continue

            identity = self._history_identity(
                candidate=candidate,
                stage_b_result=stage_b_result,
                entry_mapping=entry_mapping,
                entry_metadata=entry_metadata,
            )
            if identity is None:
                logger.warning("Skipping history entry %s: conflicting identity fields", idx)
                continue
            candidate_id = str(identity.get("candidate_id") or f"hist_{idx}")
            score, score_is_scalar = self._history_score(
                entry=entry,
                candidate=candidate,
                stage_b_result=stage_b_result,
                entry_mapping=entry_mapping,
            )
            assessment = _assess_search_metric(
                stage_b_result,
                self._primary_metric,
                self._direction.value,
                self._selected_objective_unit,
            )
            stage_b_metadata = _as_mapping(stage_b_result.get("metadata"))
            history_result = _as_mapping(stage_b_result.get("simulation_results"))
            history_units = _as_mapping(history_result.get("metric_units"))
            selected_history_unit = history_units.get(self._primary_metric)
            evaluation_ref_payload = stage_b_metadata.get("evaluation_artifact_ref")
            evaluation_ref_present = evaluation_ref_payload is not None
            proposal_metadata = _as_mapping(candidate.get("_strategy_metadata"))
            from .source_profile_verification import (
                _resolve_search_history_source,
                _SearchHistorySourceDisposition,
            )

            source_resolution = _resolve_search_history_source(
                store=self._source_store,
                evaluation_ref=evaluation_ref_payload,
                expected_params=params,
                expected_scalar=(
                    assessment.value
                    if assessment.status is ObjectiveScoreStatus.AVAILABLE
                    else None
                ),
                expected_proposal_id=proposal_metadata.get("candidate_id"),
                expected_provenance_ref=(
                    str(identity["provenance_ref"])
                    if identity.get("provenance_ref") is not None
                    else None
                ),
            )
            persisted_evaluation = source_resolution.evaluation
            method_job_claimed = (
                source_resolution.disposition is not _SearchHistorySourceDisposition.NOT_APPLICABLE
            )
            verified = source_resolution.verified
            configured_unit = self._selected_objective_unit
            selected_unit_is_exact = (
                isinstance(configured_unit, str)
                and bool(configured_unit.strip())
                and configured_unit == configured_unit.strip()
                and selected_history_unit == configured_unit
                and persisted_evaluation is not None
                and persisted_evaluation.metadata.get("metric_unit") == selected_history_unit
            )
            if (
                not evaluation_ref_present
                and isinstance(configured_unit, str)
                and configured_unit.strip()
                and assessment.status is ObjectiveScoreStatus.AVAILABLE
            ):
                assessment = _unestablished_score_assessment(
                    "search_method_result_evaluation_cas_ref_not_established"
                )
            if (
                method_job_claimed
                and not selected_unit_is_exact
                and assessment.status is ObjectiveScoreStatus.AVAILABLE
            ):
                assessment = _unestablished_score_assessment(
                    "search_method_result_unit_not_established"
                )
            if (
                not method_job_claimed
                and persisted_evaluation is not None
                and assessment.status is ObjectiveScoreStatus.AVAILABLE
            ):
                # Generic output is candidate-grade producer declaration, not
                # independently verified external measurement. Reconcile the
                # stage view with the selected persisted producer artifact.
                selected_metrics = persisted_evaluation.metrics_for_split(self._compare_split)
                generic_source = {
                    "metrics": selected_metrics,
                    "metric_units": {
                        self._primary_metric: persisted_evaluation.metadata.get("metric_unit")
                    },
                }
                generic_assessment = _assess_search_metric(
                    generic_source,
                    self._primary_metric,
                    self._direction.value,
                    self._selected_objective_unit,
                )
                generic_feedback = _as_mapping(stage_b_result.get("feedback"))
                stage_status = generic_feedback.get("status", stage_b_result.get("status"))
                if (
                    persisted_evaluation.status not in {"ok", "measured_candidate"}
                    or stage_status != persisted_evaluation.status
                    or persisted_evaluation.resolved_runtime_split_type() is not self._compare_split
                    or generic_assessment.status is not ObjectiveScoreStatus.AVAILABLE
                    or generic_assessment.value != assessment.value
                    or persisted_evaluation.metadata.get("metric_unit") != selected_history_unit
                ):
                    assessment = _unestablished_score_assessment(
                        "generic_benchmark_selected_source_not_reconciled"
                    )
            has_score = (
                assessment.status is ObjectiveScoreStatus.AVAILABLE
                and assessment.value is not None
                and math.isfinite(assessment.value)
            )
            if has_score:
                scalar = assessment.value
                objective_raw_value = assessment.value
            else:
                scalar = None
                if score not in {_MISSING, _INVALID}:
                    diagnostic_value = float(score)
                    objective_raw_value = (
                        diagnostic_value
                        if score_is_scalar or self._direction == MetricDirection.MINIMIZE
                        else -diagnostic_value
                    )
                else:
                    objective_raw_value = math.nan

            stage_a_passed = bool(
                getattr(entry, "stage_a_passed", entry_mapping.get("stage_a_passed", True))
            )
            feedback = _as_mapping(stage_b_result.get("feedback"))
            reported_status = str(
                feedback.get("status") or stage_b_result.get("status") or ""
            ).lower()
            if not stage_a_passed:
                status = EvaluationStatus.STAGE_A_REJECT
            elif not has_score or reported_status in {
                "error",
                "failed",
                "invalid",
                "source_profile_conflict",
                EvaluationStatus.STAGE_B_ERROR.value,
            }:
                status = EvaluationStatus.STAGE_B_ERROR
            else:
                status = EvaluationStatus.SUCCESS

            metadata = dict(entry_metadata)
            metadata.update(_as_mapping(candidate.get("_strategy_metadata")))
            metadata.update(stage_b_metadata)
            for key in (
                "warm_start_compatibility",
                "search_source_profile_receipt",
                "search_source_evaluation_ref",
            ):
                metadata.pop(key, None)
            metadata.update(
                {
                    "source": "search_iteration",
                    "params": dict(params),
                    "params_normalized": list(normalized),
                }
            )
            if not method_job_claimed and persisted_evaluation is not None:
                metadata["search_source_assurance"] = "generic_producer_declared_candidate_only"
            for key, value in identity.items():
                metadata[key] = value
            if not has_score:
                metadata["invalid_reason"] = (
                    assessment.limitation or f"primary_metric_{assessment.status.value}"
                )

            timestamp = getattr(entry, "timestamp", None)
            if not isinstance(timestamp, datetime):
                timestamp = datetime.now(UTC)
            duration = getattr(
                entry, "duration_seconds", entry_mapping.get("duration_seconds", 0.0)
            )
            try:
                duration_seconds = float(duration)
            except (TypeError, ValueError):
                duration_seconds = 0.0
            provenance_ref = identity.get("provenance_ref")
            evaluation = Evaluation(
                candidate_id=candidate_id,
                params=dict(params),
                params_normalized=normalized,
                objectives=[
                    ObjectiveValue(
                        name=self._primary_metric,
                        raw_value=objective_raw_value,
                        direction=OptimizationDirection.MINIMIZE,
                        score_status=assessment.status,
                        score_assessment=assessment,
                    )
                ],
                scalar_score=scalar,
                stage_a_passed=stage_a_passed,
                stage_b_result=dict(stage_b_result) or None,
                status=status,
                timestamp=timestamp,
                wall_time_seconds=duration_seconds,
                provenance_ref=str(provenance_ref) if provenance_ref is not None else None,
                metadata=metadata,
                score_status=assessment.status,
                score_assessment=assessment,
            )
            if verified is not None:
                _, receipt, _ = verified
                if (
                    not has_score
                    or selected_history_unit != receipt.get("unit")
                    or selected_history_unit != self._selected_objective_unit
                ):
                    verified = None
            if (
                method_job_claimed
                and verified is None
                and (evaluation.score_status is ObjectiveScoreStatus.AVAILABLE)
            ):
                unavailable_assessment = _unestablished_score_assessment(
                    "search_method_result_profile_or_cas_chain_not_established"
                )
                evaluation.objectives = [
                    replace(
                        objective,
                        score_status=unavailable_assessment.status,
                        score_assessment=unavailable_assessment,
                        is_satisfied=False,
                    )
                    for objective in evaluation.objectives
                ]
                evaluation.scalar_score = None
                evaluation.status = EvaluationStatus.STAGE_B_ERROR
                evaluation.score_status = unavailable_assessment.status
                evaluation.score_assessment = unavailable_assessment
                evaluation.metadata["invalid_reason"] = unavailable_assessment.limitation
            if verified is not None:
                profile, receipt, source_candidate_ref = verified
                evaluation.candidate_id = str(source_candidate_ref.artifact_id)
                evaluation.provenance_ref = str(receipt["method_result_ref"]["artifact_id"])
                evaluation.metadata["warm_start_compatibility"] = profile.model_dump(
                    mode="json", exclude_none=True
                )
                evaluation.metadata["search_source_profile_receipt"] = receipt
                evaluation.metadata["search_source_evaluation_ref"] = ArtifactRef.model_validate(
                    evaluation_ref_payload
                ).model_dump(mode="json")
            evaluations.append(evaluation)
        return evaluations


def benchmark_to_evaluation(
    bench: BenchmarkEvaluation,
    *,
    primary_metric: str,
    direction: MetricDirection = MetricDirection.MAXIMIZE,
    split: BenchmarkSplit = BenchmarkSplit.HOLDOUT,
    dim: int = 0,
    search_space: Any | None = None,
    expected_unit: str | None = None,
) -> Any | None:
    """Convert a BenchmarkEvaluation to a methods.search strategy Evaluation."""
    deps = _try_import_bayesian()
    if deps is None:
        return None
    _, _, Evaluation, EvaluationStatus, _, ObjectiveValue, OptimizationDirection = deps

    runtime_split = bench.resolved_runtime_split_type()
    if runtime_split != split:
        return None
    benchmark_metadata = dict(bench.metadata)
    benchmark_identity = _merge_identity_sources(
        (
            {"candidate_id": bench.candidate_ref.artifact_id, "split": runtime_split},
            benchmark_metadata,
            _as_mapping(benchmark_metadata.get("metadata")),
        )
    )
    if benchmark_identity is None:
        return None
    value = bench.primary_value(split=split, metric=primary_metric)
    if value is None:
        return None
    finite_value = _finite_float(value)
    if finite_value is _INVALID:
        return None

    raw_params = benchmark_metadata.get("params", benchmark_metadata.get("candidate_params"))
    if not isinstance(raw_params, Mapping):
        return None
    params = dict(raw_params)

    if search_space is not None:
        try:
            params_normalized = tuple(search_space.normalize(params))
        except (TypeError, ValueError):
            return None
    else:
        raw_normalized = benchmark_metadata.get("params_normalized")
        if not isinstance(raw_normalized, (list, tuple)):
            return None
        try:
            params_normalized = tuple(float(item) for item in raw_normalized)
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(item) for item in params_normalized):
            return None
    if dim and len(params_normalized) != dim:
        return None

    from .source_profile_verification import _search_history_source_payload_claimed

    # This converter has no source store. A MethodJob claim requires the
    # selected-CAS verifier and cannot be promoted from its metadata here.
    if _search_history_source_payload_claimed(bench) or bench.status not in {
        "ok",
        "measured_candidate",
    }:
        return None
    declared_source_unit = benchmark_metadata.get("metric_unit")
    if (
        not isinstance(expected_unit, str)
        or not expected_unit.strip()
        or declared_source_unit != expected_unit
    ):
        return None
    source_result = {
        "metrics": {primary_metric: float(finite_value)},
        "metric_units": {primary_metric: declared_source_unit},
    }
    assessment = _assess_search_metric(
        source_result, primary_metric, direction.value, expected_unit
    )
    if assessment.status is not ObjectiveScoreStatus.AVAILABLE or assessment.value is None:
        return None
    scalar = assessment.value
    split_value = split.value
    metadata = {
        **benchmark_metadata,
        "source": "benchmark_evaluation",
        "search_source_assurance": "generic_caller_declared_candidate_only",
        "loop_id": bench.loop_id,
        "suite_id": bench.suite_id,
        "suite_version": bench.suite_version,
        "split": split_value,
        "params": dict(params),
        "params_normalized": list(params_normalized),
    }
    candidate_id = str(bench.candidate_ref.artifact_id)

    return Evaluation(
        candidate_id=candidate_id,
        params=params,
        params_normalized=params_normalized,
        objectives=[
            ObjectiveValue(
                name=primary_metric,
                raw_value=scalar,
                direction=OptimizationDirection.MINIMIZE,
                score_status=assessment.status,
                score_assessment=assessment,
            )
        ],
        scalar_score=scalar,
        stage_a_passed=True,
        stage_b_result=source_result,
        status=EvaluationStatus.SUCCESS,
        score_status=assessment.status,
        score_assessment=assessment,
        provenance_ref=str(benchmark_metadata["provenance_ref"])
        if benchmark_metadata.get("provenance_ref") is not None
        else None,
        metadata=metadata,
    )
