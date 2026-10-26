"""Single-objective Bayesian optimization strategy."""

from __future__ import annotations

import io
import json
import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.scientist.methods.search.objective import (
    OptimizationDirection,
    _configured_search_metric_binding,
    _configured_search_metric_profile_fingerprint,
    _evaluation_matches_selected_objectives,
)

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
from polisyos.scientist.methods.search.strategies.errors import (
    OptionalDependencyUnavailableError,
)
from polisyos.scientist.methods.search.strategies.resource_arbiter import (
    ResourceArbiter,
)
from polisyos.scientist.methods.search.strategies.runtime import (
    apply_torch_runtime_settings,
)
from polisyos.scientist.methods.search.strategies.types import (
    AcquisitionType,
    Evaluation,
    PolicyCandidate,
    StrategyState,
)

logger = get_logger(__name__)


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
}
_WARM_REJECTION_REASONS = {
    "invalid outcome",
    "missing provenance_ref",
    "incompatible normalized parameters",
    "missing or incompatible warm-start fingerprint",
    "incompatible context fingerprint",
    "incompatible objective fingerprint",
    "source profile is not fitted native GP",
    "native GP profile lacks fresh fit-basis admission",
    "selected objective rule is not configured",
    "objective basis does not match configured scalar rule",
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


_WARM_START_ADMISSION_SEAL = object()


@dataclass(frozen=True, slots=True)
class _VerifiedWarmStartAdmission:
    """Private handoff for evaluations freshly admitted by the Search CAS reader."""

    seal: object
    evaluation_ids: frozenset[int]

    def allows(self, evaluation: Evaluation) -> bool:
        """Return whether this exact in-memory row crossed the fresh verifier."""
        return self.seal is _WARM_START_ADMISSION_SEAL and id(evaluation) in self.evaluation_ids


def _issue_verified_warm_start_admission(
    evaluations: list[Evaluation],
) -> _VerifiedWarmStartAdmission:
    """Create the private handoff after the shared Search source verifier succeeds."""
    return _VerifiedWarmStartAdmission(
        seal=_WARM_START_ADMISSION_SEAL,
        evaluation_ids=frozenset(id(evaluation) for evaluation in evaluations),
    )


@dataclass(frozen=True, slots=True)
class BayesianFitProfile:
    """Measured native optimizer and fitted-corpus profile for one proposal."""

    profile_kind: str
    optimizer_fqn: str
    optimizer_config_fingerprint: str | None
    proposal_source: str
    search_space_fingerprint: str | None
    input_transform_fingerprint: str | None
    input_transform_state_fingerprint: str | None
    outcome_transform_fingerprint: str | None
    outcome_transform_state_fingerprint: str | None
    noise_model_fingerprint: str | None
    noise_model_state_fingerprint: str | None
    objective_fingerprint: str | None
    context_fingerprint: str | None
    training_corpus_fingerprint: str | None
    training_observation_count: int | None
    gp_model_fqn: str | None
    warm_start_eligible: bool


class BayesianOptimizer(BaseSearchStrategy):
    """Gaussian Process Bayesian optimizer with robust fallback behavior."""

    def __init__(
        self,
        space,
        config: BayesianConfig | None = None,
        resource_arbiter: ResourceArbiter | None = None,
        *,
        objective_name: str | None = None,
        objective_source_direction: str | None = None,
        objective_source_unit: str | None = None,
    ):
        if (objective_name is None) != (objective_source_direction is None):
            raise ValueError(
                "selected objective name and source direction must be supplied together"
            )
        selected_binding = None
        if objective_name is not None:
            if not isinstance(objective_name, str) or not objective_name.strip():
                raise ValueError("selected objective name must be non-empty")
            if not isinstance(objective_source_direction, str):
                raise ValueError("selected objective source direction must be a string")
            selected_binding = _configured_search_metric_binding(
                objective_name, objective_source_direction, objective_source_unit
            )
            if selected_binding is None:
                raise ValueError("selected objective source rule is not configured")
        cfg = config or BayesianConfig()
        super().__init__(space=space, seed=cfg.seed)
        self._config = cfg
        if selected_binding is None:
            self._selected_objective_name = None
            self._selected_objective_direction = None
            self._selected_objective_source_direction = None
            self._selected_objective_rule_spec = None
            self._selected_objective_unit = None
        else:
            (
                self._selected_objective_name,
                self._selected_objective_direction,
                self._selected_objective_rule_spec,
            ) = selected_binding
            # The selected rule uses source direction; the optimizer direction is normalized.
            self._selected_objective_source_direction = objective_source_direction
            self._selected_objective_unit = objective_source_unit
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
        self._warm_start_target_objective_fingerprint: str | None = None
        self._run_context_fingerprint: str | None = None
        self._run_objective_fingerprint: str | None = None
        self._warm_start_rejections: list[dict[str, Any]] = []
        self._warm_start_rejection_history_complete = True
        self._last_fitted_training_corpus_fingerprint: str | None = None
        self._last_fitted_training_observation_count: int | None = None
        self._last_fitted_training_evaluation_refs: list[dict[str, Any]] | None = None
        self._last_acquisition_training_observation_count: int | None = None
        self._last_acquisition_training_evaluation_refs: list[dict[str, Any]] | None = None
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

    def warm_start(
        self,
        evaluations: list[Evaluation],
        *,
        target_context_fingerprint: str | None = None,
        target_objective_fingerprint: str | None = None,
        _source_admission: _VerifiedWarmStartAdmission | None = None,
    ) -> None:
        """Pre-seed GP with historical evaluations admitted by its source boundary."""
        if (target_context_fingerprint is None) != (target_objective_fingerprint is None):
            raise ValueError("target context and objective fingerprints must be supplied together")
        accepted: list[Evaluation] = []
        rejected: list[str] = []
        for evaluation in evaluations:
            profile = evaluation.metadata.get(_WARM_COMPATIBILITY_METADATA)
            claims_configured_gp = isinstance(profile, Mapping) and (
                profile.get("profile_kind") == "configured_native_gp"
                or profile.get("warm_start_eligible") is True
            )
            if claims_configured_gp and (
                _source_admission is None or not _source_admission.allows(evaluation)
            ):
                rejected.append("native GP profile lacks fresh fit-basis admission")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if not self._score_is_admissible(evaluation):
                reason = (
                    "objective basis does not match configured scalar rule"
                    if self._selected_objective_name is not None
                    else "invalid outcome"
                )
                rejected.append(reason)
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if self._origin_ref(evaluation) is None:
                rejected.append("missing provenance_ref")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if not self._has_compatible_params(evaluation):
                rejected.append("incompatible normalized parameters")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            compatibility = self._warm_compatibility(
                evaluation,
                expected_objective_fingerprint=target_objective_fingerprint,
            )
            if compatibility is None:
                rejected.append("missing or incompatible warm-start fingerprint")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            context_fingerprint = compatibility[-1]
            if (
                target_context_fingerprint is not None
                and context_fingerprint != target_context_fingerprint
            ):
                rejected.append("incompatible context fingerprint")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if target_context_fingerprint is not None and not self._warm_profile_compatible(
                evaluation
            ):
                rejected.append("source profile is not fitted native GP")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if (
                self._warm_context_fingerprint is not None
                and context_fingerprint != self._warm_context_fingerprint
            ):
                rejected.append("incompatible context fingerprint")
                self._record_warm_start_rejection(evaluation, rejected[-1])
                continue
            if self._warm_context_fingerprint is None:
                self._warm_context_fingerprint = context_fingerprint
            if target_objective_fingerprint is not None:
                self._warm_start_target_objective_fingerprint = target_objective_fingerprint
            accepted.append(evaluation)
            self._warm_evaluation_ids.add(id(evaluation))

        self._warm_evals.extend(accepted)
        logger.info(
            "Bayesian warm-start: added {} historical evaluations; rejected {}",
            len(accepted),
            len(rejected),
        )

    @property
    def warm_start_accepted_count(self) -> int:
        """Return the number of source evaluations admitted by this optimizer."""
        return len(self._warm_evals)

    @property
    def native_gp_ready(self) -> bool:
        """Return whether the canonical optimizer has its real BoTorch stack."""
        return self._botorch_ready

    def set_search_run_profile(
        self,
        *,
        context_fingerprint: str,
        objective_fingerprint: str,
        objective_unit: str | None = None,
    ) -> None:
        """Bind current and historical evaluations to this run's immutable header."""
        if not context_fingerprint.strip() or not objective_fingerprint.strip():
            raise ValueError("search-run context and objective fingerprints are required")
        if (
            self._selected_objective_name is None
            or self._selected_objective_direction is None
            or self._selected_objective_source_direction is None
        ):
            raise ValueError("configured search runs require a selected objective rule")
        selected_binding = _configured_search_metric_binding(
            self._selected_objective_name,
            self._selected_objective_source_direction,
            objective_unit,
        )
        expected_objective_fingerprint = _configured_search_metric_profile_fingerprint(
            self._selected_objective_name,
            self._selected_objective_source_direction,
            objective_unit,
        )
        if (
            selected_binding is None
            or expected_objective_fingerprint is None
            or expected_objective_fingerprint != objective_fingerprint
        ):
            raise ValueError("configured search run differs from selected objective rule and unit")
        if objective_unit != self._selected_objective_unit:
            if (
                self._run_context_fingerprint is not None
                or self._warm_evals
                or self._train_X is not None
                or self._model is not None
            ):
                raise RuntimeError("selected objective unit cannot change after score admission")
            self._selected_objective_unit = objective_unit
            self._selected_objective_rule_spec = selected_binding[2]
        if (
            self._run_context_fingerprint is not None
            and (
                self._run_context_fingerprint != context_fingerprint
                or self._run_objective_fingerprint != objective_fingerprint
            )
            and (self._warm_evals or self._train_X is not None or self._model is not None)
        ):
            raise RuntimeError("search-run profile is immutable after score admission")
        if self._warm_evals and (
            self._warm_context_fingerprint != context_fingerprint
            or self._warm_start_target_objective_fingerprint != objective_fingerprint
        ):
            raise RuntimeError("search-run profile changed after warm-start admission")
        self._run_context_fingerprint = context_fingerprint
        self._run_objective_fingerprint = objective_fingerprint

    @property
    def warm_start_rejections(self) -> tuple[dict[str, Any], ...]:
        """Return a copy of recorded warm-start rejection evidence."""
        return tuple(deepcopy(self._warm_start_rejections))

    def effective_fit_profile(
        self,
        *,
        proposal_source: str,
        context_fingerprint: str | None,
        objective_fingerprint: str | None,
    ) -> BayesianFitProfile:
        """Describe the actual native optimizer, fitted GP, and fit corpus.

        The fit basis comes from the model currently held by this optimizer. A
        configured native strategy without a successful GP acquisition reports
        its actual optimizer class but cannot claim a reusable fitted profile.
        """
        optimizer_fqn = f"{type(self).__module__}.{type(self).__qualname__}"
        config_fingerprint = _profile_fingerprint(asdict(self._config))
        model = self._model
        model_fqn = (
            f"{type(model).__module__}.{type(model).__qualname__}" if model is not None else None
        )
        input_transform = self._input_transform_fingerprint(getattr(model, "input_transform", None))
        input_transform_state = self._input_transform_state_fingerprint(
            getattr(model, "input_transform", None)
        )
        outcome_transform = self._outcome_transform_fingerprint(
            getattr(model, "outcome_transform", None)
        )
        outcome_transform_state = self._outcome_transform_state_fingerprint(
            getattr(model, "outcome_transform", None)
        )
        noise_model = self._noise_model_fingerprint(getattr(model, "likelihood", None))
        noise_model_state = self._noise_model_state_fingerprint(getattr(model, "likelihood", None))
        training_count = self._last_fitted_training_observation_count
        corpus_fingerprint = self._last_fitted_training_corpus_fingerprint
        fitted_model_is_live = self._fitted_model_matches_recorded_basis()
        eligible = bool(
            self._botorch_ready
            and self._selected_objective_name is not None
            and proposal_source == "bayesian_acquisition"
            and fitted_model_is_live
            and model_fqn == "botorch.models.gp_regression.SingleTaskGP"
            and input_transform == "Normalize[0,1]"
            and input_transform_state
            and outcome_transform == "Standardize[m=1]"
            and outcome_transform_state
            and noise_model == "GaussianLikelihood[inferred]"
            and noise_model_state
            and self._space.sobol_space_fingerprint()
            and context_fingerprint
            and objective_fingerprint
            and corpus_fingerprint
            and training_count is not None
            and training_count > 0
            and self._last_fitted_training_evaluation_refs is not None
            and len(self._last_fitted_training_evaluation_refs) == training_count
        )
        return BayesianFitProfile(
            profile_kind="configured_native_gp",
            optimizer_fqn=optimizer_fqn,
            optimizer_config_fingerprint=config_fingerprint,
            proposal_source=proposal_source,
            search_space_fingerprint=self._space.sobol_space_fingerprint(),
            input_transform_fingerprint=input_transform,
            input_transform_state_fingerprint=input_transform_state,
            outcome_transform_fingerprint=outcome_transform,
            outcome_transform_state_fingerprint=outcome_transform_state,
            noise_model_fingerprint=noise_model,
            noise_model_state_fingerprint=noise_model_state,
            objective_fingerprint=(
                objective_fingerprint if self._selected_objective_name is not None else None
            ),
            context_fingerprint=context_fingerprint,
            training_corpus_fingerprint=corpus_fingerprint,
            training_observation_count=training_count,
            gp_model_fqn=model_fqn,
            warm_start_eligible=eligible,
        )

    def _fitted_model_state_fingerprint(self) -> str | None:
        """Fingerprint the complete fitted state, including structural constraint infinities."""
        model = self._model
        if model is None or not self._botorch_ready or self._torch is None:
            return None
        try:
            from gpytorch.constraints import Interval

            state = model.state_dict()
            if not isinstance(state, Mapping) or not state:
                return None
            torch = self._torch
            parameter_names = {name for name, _ in model.named_parameters()}
            constraint_bound_entries: dict[str, tuple[Any, str, Any]] = {}
            for module_name, module in model.named_modules():
                if not isinstance(module, Interval):
                    continue
                buffers = dict(module.named_buffers(recurse=False))
                parameters = {name for name, _ in module.named_parameters(recurse=False)}
                lower_bound = buffers.get("lower_bound")
                upper_bound = buffers.get("upper_bound")
                if (
                    lower_bound is None
                    or upper_bound is None
                    or "lower_bound" in parameters
                    or "upper_bound" in parameters
                ):
                    return None
                lower_tensor = lower_bound.detach().cpu()
                upper_tensor = upper_bound.detach().cpu()
                if bool(torch.isnan(lower_tensor).any().item()) or bool(
                    torch.isnan(upper_tensor).any().item()
                ):
                    return None
                if not bool(torch.all(lower_tensor < upper_tensor).item()):
                    return None
                if bool(
                    torch.logical_and(torch.isneginf(lower_tensor), torch.isposinf(upper_tensor))
                    .any()
                    .item()
                ):
                    return None
                for bound_name, bound in (
                    ("lower_bound", lower_bound),
                    ("upper_bound", upper_bound),
                ):
                    state_name = f"{module_name}.{bound_name}" if module_name else bound_name
                    if state_name not in state:
                        return None
                    constraint_bound_entries[state_name] = (
                        module,
                        bound_name,
                        bound,
                    )

            def encode_infinity_sentinels(value: Any) -> Any:
                if isinstance(value, list):
                    return [encode_infinity_sentinels(item) for item in value]
                if isinstance(value, float) and math.isinf(value):
                    return "+inf" if value > 0 else "-inf"
                return value

            state_values: dict[str, dict[str, Any]] = {}
            for name, value in sorted(state.items()):
                detach = getattr(value, "detach", None)
                if not callable(detach):
                    return None
                tensor = detach().cpu()
                finite = bool(torch.isfinite(tensor).all().item())
                values = tensor.tolist()
                entry: dict[str, Any] = {
                    "dtype": str(tensor.dtype),
                    "shape": list(tensor.shape),
                    "values": values,
                }
                if not finite:
                    constraint_entry = constraint_bound_entries.get(name)
                    if (
                        constraint_entry is None
                        or name in parameter_names
                        or bool(torch.isnan(tensor).any().item())
                        or not bool(torch.isinf(tensor).any().item())
                    ):
                        return None
                    module, bound_name, registered_buffer = constraint_entry
                    registered_tensor = registered_buffer.detach().cpu()
                    if (
                        registered_tensor.dtype != tensor.dtype
                        or tuple(registered_tensor.shape) != tuple(tensor.shape)
                        or not bool(torch.equal(registered_tensor, tensor))
                    ):
                        return None
                    if bound_name == "lower_bound" and bool(torch.isposinf(tensor).any().item()):
                        return None
                    if bound_name == "upper_bound" and bool(torch.isneginf(tensor).any().item()):
                        return None
                    entry["values"] = encode_infinity_sentinels(values)
                    entry["constraint_owner_fqn"] = (
                        f"{type(module).__module__}.{type(module).__qualname__}"
                    )
                    entry["constraint_member"] = bound_name
                state_values[name] = entry
            return _profile_fingerprint(
                {
                    "model_fqn": f"{type(model).__module__}.{type(model).__qualname__}",
                    "state_dict": state_values,
                }
            )
        except (
            AttributeError,
            ImportError,
            RuntimeError,
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

    def _fitted_model_matches_recorded_basis(self) -> bool:
        """Confirm the active model still represents the recorded fitted basis."""
        if (
            self._model is None
            or self._fitted_train_X is None
            or self._fitted_train_y_bo is None
            or self._last_fitted_training_observation_count is None
        ):
            return False
        if self._fitted_train_X.shape[0] != self._last_fitted_training_observation_count:
            return False
        model_X = self._model_train_x()
        if model_X is None or not self._model_train_x_matches_fitted(model_X):
            return False
        return bool(
            self._torch.isfinite(self._fitted_train_X).all()
            and self._torch.isfinite(self._fitted_train_y_bo).all()
            and self._fitted_train_y_bo.shape[0] == self._last_fitted_training_observation_count
        )

    def _record_fitted_training_corpus(self, evaluations: list[Evaluation]) -> None:
        """Fingerprint source rows and numeric training data actually used by the GP."""
        self._last_fitted_training_corpus_fingerprint = None
        self._last_fitted_training_observation_count = None
        self._last_fitted_training_evaluation_refs = None
        if not self._fitted_model_matches_current_fit():
            return
        rows = [
            {
                "candidate_id": evaluation.candidate_id,
                "provenance_ref": evaluation.provenance_ref,
                "params_normalized": list(evaluation.params_normalized),
                "scalar_score": evaluation.scalar_score,
                "is_valid": self._score_is_admissible(evaluation),
            }
            for evaluation in evaluations
        ]
        fit_x = self._fitted_train_X.detach().cpu().tolist()
        fit_y = self._fitted_train_y_bo.detach().cpu().tolist()
        count = len(fit_x)
        if len(rows) != count or len(fit_y) != count:
            return
        valid_scores: list[float] = []
        for evaluation in evaluations:
            score = evaluation.scalar_score
            if (
                not self._score_is_admissible(evaluation)
                or score is None
                or not math.isfinite(score)
            ):
                return
            valid_scores.append(float(score))
        if not valid_scores:
            return
        expected_x = self._torch.tensor(
            [list(evaluation.params_normalized) for evaluation in evaluations],
            dtype=self._fitted_train_X.dtype,
            device=self._fitted_train_X.device,
        )
        expected_y = self._torch.tensor(
            [[-score] for score in valid_scores],
            dtype=self._fitted_train_y_bo.dtype,
            device=self._fitted_train_y_bo.device,
        )
        if not self._torch.equal(expected_x, self._fitted_train_X) or not self._torch.equal(
            expected_y, self._fitted_train_y_bo
        ):
            return
        source_refs: list[dict[str, Any]] = []
        seen_source_refs: set[tuple[str, str]] = set()
        for evaluation in evaluations:
            raw_ref = evaluation.metadata.get("search_source_evaluation_ref")
            if not isinstance(raw_ref, Mapping):
                return
            try:
                selected_ref = ArtifactRef.model_validate(raw_ref)
            except (TypeError, ValueError):
                return
            selected_profile = selected_ref.manifest_profile_sha256
            if selected_profile is None:
                return
            identity = (str(selected_ref.artifact_id), selected_profile)
            if identity in seen_source_refs:
                return
            seen_source_refs.add(identity)
            source_refs.append(selected_ref.model_dump(mode="json"))
        if len(source_refs) != count:
            return
        corpus_fingerprint = _profile_fingerprint(
            {
                "selected_objective_binding": self._objective_binding_payload(),
                "observations": rows,
                "fitted_normalized_inputs": fit_x,
                "fitted_minimization_targets": fit_y,
            }
        )
        if corpus_fingerprint is None:
            return
        self._last_fitted_training_corpus_fingerprint = corpus_fingerprint
        self._last_fitted_training_observation_count = count
        self._last_fitted_training_evaluation_refs = source_refs

    def _record_acquisition_training_corpus(self, evaluations: list[Evaluation]) -> None:
        """Bind the exact full effective corpus that selects adaptive acquisition."""
        self._last_acquisition_training_observation_count = None
        self._last_acquisition_training_evaluation_refs = None
        if not evaluations or any(
            not self._score_is_admissible(evaluation)
            or evaluation.scalar_score is None
            or not math.isfinite(evaluation.scalar_score)
            for evaluation in evaluations
        ):
            return
        source_refs: list[dict[str, Any]] = []
        seen_source_refs: set[tuple[str, str]] = set()
        for evaluation in evaluations:
            raw_ref = evaluation.metadata.get("search_source_evaluation_ref")
            if not isinstance(raw_ref, Mapping):
                return
            try:
                selected_ref = ArtifactRef.model_validate(raw_ref)
            except (TypeError, ValueError):
                return
            selected_profile = selected_ref.manifest_profile_sha256
            if selected_profile is None:
                return
            identity = (str(selected_ref.artifact_id), selected_profile)
            if identity in seen_source_refs:
                return
            seen_source_refs.add(identity)
            source_refs.append(selected_ref.model_dump(mode="json"))
        if len(source_refs) != len(evaluations):
            return
        self._last_acquisition_training_observation_count = len(source_refs)
        self._last_acquisition_training_evaluation_refs = source_refs

    def _fitted_model_matches_current_fit(self) -> bool:
        """Validate a model and fit matrices before binding training source rows."""
        if self._model is None or self._fitted_train_X is None or self._fitted_train_y_bo is None:
            return False
        model_X = self._model_train_x()
        return model_X is not None and self._model_train_x_matches_fitted(model_X)

    @staticmethod
    def _input_transform_fingerprint(transform: Any) -> str | None:
        if transform is None or type(transform).__name__ != "Normalize":
            return None
        try:
            center = float(getattr(transform, "center", math.nan))
        except (TypeError, ValueError, OverflowError):
            return None
        if (
            getattr(transform, "learn_bounds", False) is not True
            or getattr(transform, "indices", None) is not None
            or not math.isclose(center, 0.5)
            or not getattr(transform, "transform_on_train", False)
            or not getattr(transform, "transform_on_eval", False)
            or not getattr(transform, "transform_on_fantasize", False)
        ):
            return None
        return "Normalize[0,1]"

    @staticmethod
    def _input_transform_state_fingerprint(transform: Any) -> str | None:
        if transform is None or type(transform).__name__ != "Normalize":
            return None
        bounds = getattr(transform, "bounds", None)
        if hasattr(bounds, "detach"):
            bounds = bounds.detach().cpu().tolist()
        return _profile_fingerprint(
            {
                "transform": f"{type(transform).__module__}.{type(transform).__qualname__}",
                "bounds": bounds,
                "learn_bounds": getattr(transform, "learn_bounds", None),
                "center": getattr(transform, "center", None),
                "min_range": getattr(transform, "min_range", None),
                "transform_on_train": getattr(transform, "transform_on_train", None),
                "transform_on_eval": getattr(transform, "transform_on_eval", None),
                "transform_on_fantasize": getattr(transform, "transform_on_fantasize", None),
            }
        )

    @staticmethod
    def _outcome_transform_fingerprint(transform: Any) -> str | None:
        if transform is None or type(transform).__name__ != "Standardize":
            return None
        measure_count = getattr(transform, "_m", None)
        if hasattr(measure_count, "numel") and measure_count.numel() == 1:
            measure_count = measure_count.item()
        if measure_count is None:
            measure_count = getattr(transform, "m", None)
        try:
            if int(measure_count) == 1:
                return "Standardize[m=1]"
        except (TypeError, ValueError, OverflowError):
            return None
        return None

    @staticmethod
    def _outcome_transform_state_fingerprint(transform: Any) -> str | None:
        if transform is None or type(transform).__name__ != "Standardize":
            return None
        means = getattr(transform, "means", None)
        stdvs = getattr(transform, "stdvs", None)
        if hasattr(means, "detach"):
            means = means.detach().cpu().tolist()
        if hasattr(stdvs, "detach"):
            stdvs = stdvs.detach().cpu().tolist()
        measure_count = getattr(transform, "_m", None)
        if hasattr(measure_count, "numel") and measure_count.numel() == 1:
            measure_count = measure_count.item()
        try:
            measure_count = int(measure_count)
        except (TypeError, ValueError, OverflowError):
            return None
        return _profile_fingerprint(
            {
                "transform": f"{type(transform).__module__}.{type(transform).__qualname__}",
                "measure_count": measure_count,
                "means": means,
                "standard_deviations": stdvs,
            }
        )

    @staticmethod
    def _noise_model_fingerprint(likelihood: Any) -> str | None:
        if likelihood is not None and type(likelihood).__name__ == "GaussianLikelihood":
            return "GaussianLikelihood[inferred]"
        return None

    @staticmethod
    def _noise_model_state_fingerprint(likelihood: Any) -> str | None:
        if likelihood is None or type(likelihood).__name__ != "GaussianLikelihood":
            return None
        noise = getattr(likelihood, "noise", None)
        if hasattr(noise, "detach"):
            noise = noise.detach().cpu().tolist()
        return _profile_fingerprint(
            {
                "likelihood": f"{type(likelihood).__module__}.{type(likelihood).__qualname__}",
                "noise": noise,
            }
        )

    def _objective_binding_payload(self) -> dict[str, str] | None:
        """Return the immutable consumer-selected scalar basis, if configured."""
        if (
            self._selected_objective_name is None
            or self._selected_objective_direction is None
            or self._selected_objective_rule_spec is None
        ):
            return None
        payload = {
            "name": self._selected_objective_name,
            "direction": self._selected_objective_direction.value,
            "rule_spec": self._selected_objective_rule_spec,
        }
        if self._selected_objective_unit is not None:
            payload["unit"] = self._selected_objective_unit
        return payload

    def _score_is_admissible(self, evaluation: Evaluation) -> bool:
        """Apply the configured scalar rule, or the generic candidate-only contract."""
        if self._selected_objective_name is None:
            # The generic strategy contract accepts a caller-supplied numeric objective
            # for candidate exploration only; it does not resolve configured semantics.
            score = evaluation.scalar_score
            status = getattr(evaluation.status, "value", evaluation.status)
            return bool(
                status == "success"
                and evaluation.stage_a_passed is True
                and isinstance(score, (int, float))
                and not isinstance(score, bool)
                and math.isfinite(float(score))
            )
        assert self._selected_objective_direction is not None
        assert self._selected_objective_rule_spec is not None
        return _evaluation_matches_selected_objectives(
            evaluation,
            objective_names=[self._selected_objective_name],
            objective_directions={
                self._selected_objective_name: self._selected_objective_direction
            },
            objective_rule_specs={
                self._selected_objective_name: self._selected_objective_rule_spec
            },
            require_scalar_score=True,
        )

    def _record_warm_start_rejection(self, evaluation: Evaluation, reason: str) -> None:
        self._warm_start_rejections.append({"reason": reason, "evaluation": asdict(evaluation)})
        logger.info("Bayesian warm-start rejected {}: {}", evaluation.candidate_id, reason)

    def suggest(
        self,
        evaluations: list[Evaluation],
        pending: list[PolicyCandidate] | None = None,
        *,
        attempted_count: int | None = None,
    ) -> PolicyCandidate:
        """Suggest using attempts for exploration and admissible scores for GP fitting."""
        if attempted_count is None:
            attempted_count = len(evaluations)
        elif type(attempted_count) is not int or attempted_count < 0:
            raise ValueError("attempted_count must be a non-negative integer")
        history_count = max(len(evaluations), attempted_count)
        self._iteration = history_count
        pending = pending or []
        training_corpus = self._effective_training_corpus(evaluations)
        proposal_index = max(history_count, len(training_corpus), self._sobol_cursor)

        if len(training_corpus) < self._config.n_initial:
            return self._sobol_candidate(proposal_index, source="sobol_init")

        if not self._botorch_ready:
            return self._non_duplicate_random(pending, source="random_no_botorch")

        with self._arbiter.acquire("torch"):
            soft, hard = self._arbiter.enforce_limits()
            if hard:
                return self._non_duplicate_random(pending, source="random_hard_limit")

            train_set = self._select_training_subset(training_corpus)
            if len(train_set) < 3:
                return self._non_duplicate_random(pending, source="random_insufficient_data")

            try:
                X, y_bo = self._prepare_training_data(train_set)
                self._fit_gp(X, y_bo)
                self._record_fitted_training_corpus(train_set)
                self._record_acquisition_training_corpus(training_corpus)
                candidate, _, acquisition_type = self._optimize_acquisition(
                    y_bo=y_bo,
                    soft_limit=soft,
                    evaluations=training_corpus,
                )
                result = self._tensor_to_candidate(
                    candidate.squeeze(0),
                    source="bayesian_acquisition",
                    acquisition_type=acquisition_type,
                )
                prediction = self.proposal_prediction(
                    params=result.params,
                    evaluations=training_corpus,
                )
                result.predicted_mean = prediction["predicted_mean"]
                result.predicted_std = prediction["predicted_std"]
                result.acquisition_value = prediction["acquisition_value"]
                result.metadata["acquisition_type"] = prediction["acquisition_type"]
            except Exception as exc:
                logger.warning("BayesianOptimizer failed; fallback to random: {}", exc)
                if not self._config.fallback_on_failure:
                    raise
                result = self._non_duplicate_random(pending, source="random_fallback")

        if self._is_duplicate(result, pending):
            return self._non_duplicate_random(pending, source="random_duplicate_avoidance")
        return result

    def suggest_batch(
        self,
        evaluations: list[Evaluation],
        batch_size: int,
        *,
        attempted_count: int | None = None,
    ) -> list[PolicyCandidate]:
        """Suggest a batch while keeping attempt and score counts separate."""
        if batch_size < 1:
            return []
        if attempted_count is None:
            attempted_count = len(evaluations)
        elif type(attempted_count) is not int or attempted_count < 0:
            raise ValueError("attempted_count must be a non-negative integer")
        history_count = max(len(evaluations), attempted_count)
        self._iteration = history_count

        training_corpus = self._effective_training_corpus(evaluations)
        proposal_index = max(history_count, len(training_corpus), self._sobol_cursor)
        if len(training_corpus) < self._config.n_initial:
            return [
                self._sobol_candidate(proposal_index + idx, source="sobol_init")
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

            train_set = self._select_training_subset(training_corpus)
            if len(train_set) < 3:
                return [
                    self._non_duplicate_random([], source="random_insufficient_data")
                    for _ in range(batch_size)
                ]

            try:
                X, y_bo = self._prepare_training_data(train_set)
                self._fit_gp(X, y_bo)
                self._record_fitted_training_corpus(train_set)
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

        metadata: dict[str, Any] = {
            "config": asdict(self._config),
            "selected_objective_binding": self._objective_binding_payload(),
            "warm_start_rejections": {
                "version": 1,
                "complete": self._warm_start_rejection_history_complete,
                "records": deepcopy(self._warm_start_rejections),
            },
        }
        if self._train_X is not None and self._train_y_bo is not None:
            metadata["train_X"] = self._train_X.tolist()
            metadata["train_y_bo"] = self._train_y_bo.tolist()
        if (
            self._model is not None
            and self._fitted_train_X is not None
            and self._fitted_train_y_bo is not None
        ):
            metadata["gp_continuation"] = {
                "version": "1.0",
                "space_fingerprint": self._space.sobol_space_fingerprint(),
                "fitted_train_X": self._fitted_train_X.tolist(),
                "fitted_train_y_bo": self._fitted_train_y_bo.tolist(),
                "last_refit_iteration": self._last_refit_iteration,
                "last_train_size": self._last_train_size,
            }

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
        """Restore a recorded GP basis and its actual full-refit boundary.

        Legacy model snapshots lack enough information for append continuation;
        reject them explicitly rather than invent the missing fitting history.
        """
        score_state_present = state.model_state is not None or any(
            field in state.metadata for field in ("train_X", "train_y_bo", "gp_continuation")
        )
        if (
            score_state_present
            and state.metadata.get("selected_objective_binding")
            != self._objective_binding_payload()
        ):
            raise ValueError("GP continuation objective binding differs from the selected run")
        rejection_history = state.metadata.get("warm_start_rejections")
        if rejection_history is None:
            rejection_records: list[dict[str, Any]] = []
            rejection_history_complete = False
        else:
            if (
                not isinstance(rejection_history, Mapping)
                or type(rejection_history.get("version")) is not int
                or rejection_history.get("version") != 1
                or type(rejection_history.get("complete")) is not bool
                or not isinstance(rejection_history.get("records"), list)
            ):
                raise ValueError("Warm-start rejection history is malformed or unsupported")
            for record in rejection_history["records"]:
                if (
                    not isinstance(record, Mapping)
                    or not isinstance(record.get("reason"), str)
                    or record.get("reason") not in _WARM_REJECTION_REASONS
                    or not isinstance(record.get("evaluation"), Mapping)
                    or not isinstance(record["evaluation"].get("candidate_id"), str)
                ):
                    raise ValueError("Warm-start rejection record or reason is malformed")
            rejection_records = deepcopy(rejection_history["records"])
            rejection_history_complete = rejection_history["complete"]
        continuation = state.metadata.get("gp_continuation")
        if state.model_state is not None:
            if not isinstance(continuation, Mapping) or continuation.get("version") != "1.0":
                raise ValueError("GP continuation basis/refit history not established in snapshot")
            if continuation.get("space_fingerprint") != self._space.sobol_space_fingerprint():
                raise ValueError("GP continuation search space differs from the snapshot")
            last_iteration = continuation.get("last_refit_iteration")
            last_size = continuation.get("last_train_size")
            if (
                type(last_iteration) is not int
                or type(last_size) is not int
                or last_iteration < 0
                or last_iteration > state.iteration
                or last_size < 1
            ):
                raise ValueError("GP continuation has invalid full-refit counters")
        super().set_state(state)
        self._warm_start_rejections = rejection_records
        self._warm_start_rejection_history_complete = rejection_history_complete
        self._model = None
        self._train_X = self._train_y_bo = None
        self._fitted_train_X = self._fitted_train_y_bo = None
        self._last_fitted_training_evaluation_refs = None
        self._last_refit_iteration, self._last_train_size = -1, 0
        if not self._botorch_ready:
            return
        torch_rng_state = state.rng_state.get("torch")
        if self._torch_rng is not None and torch_rng_state is not None:
            self._torch_rng.set_state(self._torch.tensor(torch_rng_state, dtype=self._torch.uint8))

        train_X_list = state.metadata.get("train_X")
        train_y_list = state.metadata.get("train_y_bo")
        if train_X_list is None or train_y_list is None:
            if state.model_state is not None:
                raise ValueError("GP continuation requested corpus is missing from snapshot")
            return
        self._train_X = self._torch.tensor(train_X_list, dtype=self._torch.float64)
        self._train_y_bo = self._torch.tensor(train_y_list, dtype=self._torch.float64)
        if self._device != "cpu":
            self._train_X = self._train_X.to(self._device)
            self._train_y_bo = self._train_y_bo.to(self._device)
        if state.model_state is None:
            return
        if not isinstance(continuation.get("fitted_train_X"), (list, tuple)) or not isinstance(
            continuation.get("fitted_train_y_bo"), (list, tuple)
        ):
            raise ValueError("GP continuation fitted corpus is missing from snapshot")
        fitted_X = self._torch.tensor(continuation.get("fitted_train_X"), dtype=self._torch.float64)
        fitted_y = self._torch.tensor(
            continuation.get("fitted_train_y_bo"), dtype=self._torch.float64
        )
        if (
            fitted_X.ndim != 2
            or fitted_X.shape[1] != self._space.dim
            or fitted_y.shape != (fitted_X.shape[0], 1)
            or fitted_X.shape[0] < last_size
            or not self._torch.isfinite(fitted_X).all()
            or not self._torch.isfinite(fitted_y).all()
        ):
            raise ValueError("GP continuation fitted corpus has invalid shape or values")
        self._fitted_train_X = fitted_X.to(self._device)
        self._fitted_train_y_bo = fitted_y.to(self._device)
        self._model = SingleTaskGP(
            train_X=self._fitted_train_X,
            train_Y=self._fitted_train_y_bo,
            input_transform=Normalize(d=self._fitted_train_X.shape[-1]),
            outcome_transform=Standardize(m=1),
        )
        buffer = io.BytesIO(state.model_state)
        self._model.load_state_dict(self._torch.load(buffer, map_location=self._device))
        self._last_refit_iteration = last_iteration
        self._last_train_size = last_size

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
            if not self._score_is_admissible(evaluation):
                continue
            if not self._has_compatible_params(evaluation):
                continue
            requires_warm_fingerprint = id(evaluation) in self._warm_evaluation_ids
            if requires_warm_fingerprint:
                if self._warm_compatibility(evaluation) is None:
                    continue
            elif _WARM_COMPATIBILITY_METADATA in evaluation.metadata:
                if self._run_context_fingerprint is not None:
                    if not self._current_run_evaluation_compatible(evaluation):
                        continue
                else:
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

    def _current_run_evaluation_compatible(self, evaluation: Evaluation) -> bool:
        """Bind same-run rows to the immutable run header without requiring a prior fit."""
        payload = evaluation.metadata.get(_WARM_COMPATIBILITY_METADATA)
        if not isinstance(payload, Mapping):
            return False
        expected_optimizer = f"{type(self).__module__}.{type(self).__qualname__}"
        expected_objective = self._run_objective_fingerprint
        return bool(
            payload.get("search_space_fingerprint") == self._space.sobol_space_fingerprint()
            and payload.get("context_fingerprint") == self._run_context_fingerprint
            and expected_objective
            and payload.get("objective_fingerprint") == expected_objective
            and payload.get("profile_kind") == "configured_native_gp"
            and payload.get("optimizer_fqn") == expected_optimizer
        )

    def _warm_compatibility(
        self,
        evaluation: Evaluation,
        *,
        expected_objective_fingerprint: str | None = None,
    ) -> tuple[str, ...] | None:
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
        expected_fields = dict(_EXPECTED_WARM_COMPATIBILITY)
        expected_fields["objective_fingerprint"] = (
            expected_objective_fingerprint
            or self._warm_start_target_objective_fingerprint
            or self._run_objective_fingerprint
            or "scalar_score[minimize]"
        )
        for field, expected in expected_fields.items():
            if payload.get(field) != expected:
                return None
        return tuple(values)

    def _warm_profile_compatible(self, evaluation: Evaluation) -> bool:
        """Require a complete profile emitted by a successful native GP fit."""
        if not self._botorch_ready:
            return False
        payload = evaluation.metadata.get(_WARM_COMPATIBILITY_METADATA)
        if not isinstance(payload, Mapping):
            return False
        expected_optimizer = f"{type(self).__module__}.{type(self).__qualname__}"
        return bool(
            payload.get("profile_kind") == "configured_native_gp"
            and payload.get("optimizer_fqn") == expected_optimizer
            and payload.get("proposal_source") == "bayesian_acquisition"
            and payload.get("gp_model_fqn") == "botorch.models.gp_regression.SingleTaskGP"
            and payload.get("warm_start_eligible") is True
            and isinstance(payload.get("input_transform_state_fingerprint"), str)
            and bool(payload.get("input_transform_state_fingerprint", "").strip())
            and isinstance(payload.get("outcome_transform_state_fingerprint"), str)
            and bool(payload.get("outcome_transform_state_fingerprint", "").strip())
            and isinstance(payload.get("noise_model_state_fingerprint"), str)
            and bool(payload.get("noise_model_state_fingerprint", "").strip())
            and isinstance(payload.get("optimizer_config_fingerprint"), str)
            and bool(payload.get("optimizer_config_fingerprint", "").strip())
            and isinstance(payload.get("training_corpus_fingerprint"), str)
            and bool(payload.get("training_corpus_fingerprint", "").strip())
            and type(payload.get("training_observation_count")) is int
            and payload.get("training_observation_count", 0) > 0
        )

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
        if not evaluations or any(not self._score_is_admissible(item) for item in evaluations):
            raise RuntimeError(
                "GP training requires only selected-rule-reconciled objective scores"
            )
        x_rows = [
            [float(value) for value in evaluation.params_normalized] for evaluation in evaluations
        ]
        y_search: list[float] = []
        for evaluation in evaluations:
            if evaluation.scalar_score is None or not math.isfinite(evaluation.scalar_score):
                raise RuntimeError("GP training requires finite selected objective scores")
            y_search.append(float(evaluation.scalar_score))

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

        valid = [e for e in evaluations if self._score_is_admissible(e)]
        if len(valid) < 3:
            return AcquisitionType.EI

        valid_scores = [float(e.scalar_score) for e in valid if e.scalar_score is not None]
        recent_scores = valid_scores[-5:]
        overall_best = min(valid_scores)
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
        acq, acquisition_type = self._acquisition_function(y_bo, evaluations or [])
        restarts, raw_samples = self._effective_optim_params(soft_limit=soft_limit)
        candidate, value = optimize_acqf(
            acq_function=acq,
            bounds=self._space.to_botorch_bounds().to(self._device),
            q=1,
            num_restarts=restarts,
            raw_samples=raw_samples,
        )
        return candidate, value, acquisition_type

    def _acquisition_function(self, y_bo, evaluations: list[Evaluation]):
        """Build the exact single-objective acquisition used by this optimizer."""
        best_f = y_bo.max()
        acq_type = self._select_acquisition(evaluations, y_bo)

        if acq_type == AcquisitionType.UCB:
            acq = UpperConfidenceBound(model=self._model, beta=self._config.ucb_beta)
            acquisition_type = AcquisitionType.UCB.value
        elif acq_type == AcquisitionType.PI:
            acq = ProbabilityOfImprovement(model=self._model, best_f=best_f)
            acquisition_type = AcquisitionType.PI.value
        else:
            acq = ExpectedImprovement(model=self._model, best_f=best_f)
            acquisition_type = AcquisitionType.EI.value
        return acq, acquisition_type

    def proposal_prediction(
        self,
        *,
        params: Mapping[str, Any],
        evaluations: list[Evaluation],
    ) -> dict[str, float | str]:
        """Recompute one exact effective candidate under the fitted native GP."""
        if (
            not self.native_gp_ready
            or self._model is None
            or self._fitted_train_y_bo is None
            or not self._fitted_model_matches_current_fit()
        ):
            raise ValueError("proposal prediction requires the exact fitted native GP")
        normalized = self._space.normalize(dict(params))
        point = self._torch.tensor(
            [normalized],
            dtype=self._torch.float64,
            device=self._device,
        )
        acquisition, acquisition_type = self._acquisition_function(
            self._fitted_train_y_bo,
            evaluations,
        )
        self._model.eval()
        with self._torch.no_grad():
            posterior = self._model.posterior(point)
            predicted_mean = -float(posterior.mean.squeeze().item())
            predicted_std = abs(float(posterior.variance.sqrt().squeeze().item()))
            acquisition_values = acquisition(point).reshape(-1)
            if acquisition_values.numel() != 1:
                raise ValueError("proposal acquisition must produce one scalar")
            acquisition_value = float(acquisition_values.item())
        if not all(
            math.isfinite(value) for value in (predicted_mean, predicted_std, acquisition_value)
        ):
            raise ValueError("proposal prediction must be finite")
        return {
            "acquisition_type": acquisition_type,
            "predicted_mean": predicted_mean,
            "predicted_std": predicted_std,
            "acquisition_value": acquisition_value,
        }

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
        acquisition_type: str | None = None,
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
            metadata=(
                {"acquisition_type": acquisition_type} if acquisition_type is not None else {}
            ),
        )
