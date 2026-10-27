"""Source-bound HTE producers with a native-only interval path.

The private writer-ready union is carried inside the ordinary Scientist method
result. The Scientist CAS bridge adds the winning owner refs and persists the
public IR ``HTEOutcome``; this module does not persist or attest owner facts.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import inspect
import json
import math
import re
import sys
from collections.abc import Callable, Mapping
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, TypeGuard, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorDispatchContext,
    OwnedHTERequestContextV1,
)
from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._econml_adapter import (
    HTEData,
    build_hte_data,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.analytics import CausalMethod
from polisyos.ir.analytics.hte import (
    HTEInputSourceRef,
    HTEPhysicalSourceMaterializationBindingRef,
    OwnedAttemptAnchorRef,
    SearchUncertaintyTaskBindingRef,
    _native_inference_profile_for_method_profile_v1,
    _native_inference_profile_v1,
    _validate_native_inference_profile_identity_v1,
)

_INPUT_PROFILE_ID = "all_source_rows_in_input_order@1.0"
_INTERVAL_PROFILE_ID = "econml_native_mean_over_selected_x@1.0"
_CF_INFERENCE_CLASS = "_GenericSingleOutcomeModelFinalWithCovInference"
_FOREST_DR_INFERENCE_CLASS = "GenericModelFinalInferenceDiscrete"
_ECONML_METADATA_SHA256 = "fbc529a8ebe9a8daa40b4d3ab294586cde4c542bd3a69bc2020e5888b296a490"
_ECONML_RECORD_SHA256 = "6bd84a244d1c35438f058496edb854ab9352249ae5c05105a398b7ca22bd2097"
_ECONML_SOURCE_FILES_SHA256 = {
    "econml/inference/_inference.py": "71ecad2fbccc75c7d1ace0ba15f2e3ab956c0dee70ccdb93426f76cc8061ead9",
    "econml/_cate_estimator.py": "ccaa73084ece98d28931cfce984e745bf66f31c541c8a15d51172e0ae4900add",
    "econml/dml/causal_forest.py": "8b3c833d9e5adccfe2a234e2aecefb996c095ecb004fa70944cda24d5ce0f1c8",
    "econml/dr/_drlearner.py": "1b046bdfa41fa3210b70540d87d01966af986a008733299e3fa40a37172b1950",
    "econml/dml/dml.py": "2e2dcf9dc74be09130f3951ae4cf9398ec21fd443dc028af1b9b86c2ef3526a1",
    "econml/metalearners/_metalearners.py": "78708e5766eea5d7505616430e4ddca732b59b45be21206d8e2741f9a4f29908",
}
_ECONML_SOURCE_PROFILE_SHA256 = "27b24c985f552585d38a3cd163301feb0f3755bf1e39c32c3abdbb1b865dba56"
_ECONML_NATIVE_RESULT_CLASS = "econml.inference._inference.PopulationSummaryResults"
_CONF_INT_MEAN_METHOD = "econml.inference._inference.PopulationSummaryResults.conf_int_mean"
_CONDITIONAL_ASSUMPTIONS = (
    "consistency",
    "conditional_unconfoundedness_given_observed_covariates",
    "overlap_on_selected_covariate_support",
)
_METHOD_PROFILE_BY_FQN = {
    "causal.hte.causal_forest@2.0.0": "econml.causal_forest_dml.native_mean@2.0",
    "causal.hte.double_ml@2.0.0": "econml.dml.point_only@2.0",
    "causal.hte.meta_learner@2.0.0": "econml.meta_learner.point_only@2.0",
    "causal.hte.forest_dr@2.0.0": "econml.forest_dr.native_mean@2.0",
}


type _HTEMethodProfileId = Literal[
    "econml.causal_forest_dml.native_mean@2.0",
    "econml.dml.point_only@2.0",
    "econml.meta_learner.point_only@2.0",
    "econml.forest_dr.native_mean@2.0",
]
type _HTENativeIntervalMethodProfileId = Literal[
    "econml.causal_forest_dml.native_mean@2.0",
    "econml.forest_dr.native_mean@2.0",
]
type _HTEDiagnosticCode = Literal[
    "hte_input_invalid",
    "contrast_not_established",
    "empty_selected_input",
    "econml_unavailable",
    "joblib_unavailable",
    "resource_profile_invalid",
    "dml_profile_invalid",
    "meta_profile_invalid",
    "hte_execution_failed",
    "hte_fit_failed",
    "hte_point_estimate_invalid",
]
type _HTEProfileKind = Literal["causal_forest", "forest_dr", "point_only"]
type _HTENativeIntervalProfileKind = Literal["causal_forest", "forest_dr"]
type _EstimatorFactory = Callable[..., object]


@runtime_checkable
class _HTEFitPort(Protocol):
    """The fitted-estimator operation used at the EconML boundary."""

    def fit(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        *,
        X: np.ndarray,
        W: np.ndarray | None,
        inference: str | None = None,
    ) -> object: ...


@runtime_checkable
class _HTEEffectPort(Protocol):
    """The point-effect operation required from a fitted EconML estimator."""

    def effect(self, X: np.ndarray, *, T0: float, T1: float) -> object: ...


@runtime_checkable
class _NativeMeanInferencePort(Protocol):
    """Runtime surface of the source-qualified native mean inference result."""

    pred: object
    pred_stderr: object

    def conf_int_mean(self, *, alpha: float) -> tuple[object, object]: ...


def _is_registered_method_profile_id(value: object) -> TypeGuard[_HTEMethodProfileId]:
    return isinstance(value, str) and value in _METHOD_PROFILE_BY_FQN.values()


def _validate_successor_identity(method_fqn: str, method_abi: str, profile_id: str) -> None:
    """Require one exact registered successor method and its owned profile."""
    if method_abi != "2.0.0" or _METHOD_PROFILE_BY_FQN.get(method_fqn) != profile_id:
        raise ValueError("hte_method_identity_profile_mismatch")


class OwnedHTEInputCaptureV1(BaseModel):
    """Strict nonpersisted capture of the actual HTE data and selected request."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    source_data_ref: HTEInputSourceRef
    source_data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"]
    selected_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fit_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eval_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fit_eval_relation: Literal["same_selected_rows"]
    n_selected_rows: int = Field(gt=0)
    n_treated: int = Field(ge=0, strict=True)
    n_control: int = Field(ge=0, strict=True)
    n_features: int = Field(gt=0)
    source_feature_names: tuple[str, ...] | None = None
    n_confounders: int = Field(ge=0)
    sample_ids_status: Literal["provided", "not_established"]
    sample_ids_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    method_fqn: str = Field(min_length=1)
    method_abi: str = Field(min_length=1)
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: str = Field(min_length=1)
    resolved_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolved_params: dict[str, Any]
    seed: int
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef
    request_estimand_status: Literal["declared", "not_established"]
    request_estimand: str | None
    request_target_scope_status: Literal["declared", "not_established"]
    request_target_scope: str | None
    outcome_variable_status: Literal["declared", "not_established"]
    outcome_variable_id: str | None
    treatment_variable_status: Literal["declared", "not_established"]
    treatment_variable_id: str | None
    contrast_status: Literal["declared", "not_established"]
    control_value: float | None
    treated_value: float | None
    request_alpha_status: Literal["declared", "not_established"]
    requested_alpha: float | None = Field(default=None, gt=0.0, lt=1.0)
    requested_guarantee_status: Literal["declared", "not_established"]
    requested_guarantee: (
        Literal[
            "candidate_point",
            "backend_conditional_interval",
            "population_sampling_coverage",
        ]
        | None
    )

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_capture(self) -> OwnedHTEInputCaptureV1:
        _validate_successor_identity(self.method_fqn, self.method_abi, self.method_profile_id)
        if self.source_data_ref.manifest_profile_sha256 is None:
            raise ValueError("source_data_ref must carry the selected manifest profile")
        if self.selected_input_sha256 != self.source_data_sha256:
            raise ValueError("selected_input_sha256 must bind the full selected source input")
        if self.fit_rows_sha256 != self.eval_rows_sha256:
            raise ValueError("this HTE profile fits and evaluates on the same selected rows")
        if (
            self.source_feature_names is not None
            and len(self.source_feature_names) != self.n_features
        ):
            raise ValueError("source feature names must match the selected X width")
        if (self.sample_ids_status == "provided") != (self.sample_ids_sha256 is not None):
            raise ValueError("sample_ids_sha256 must match sample_ids_status")
        declaration_pairs = (
            (self.request_estimand_status, self.request_estimand),
            (self.request_target_scope_status, self.request_target_scope),
            (self.outcome_variable_status, self.outcome_variable_id),
            (self.treatment_variable_status, self.treatment_variable_id),
            (self.contrast_status, self.control_value),
            (self.request_alpha_status, self.requested_alpha),
            (self.requested_guarantee_status, self.requested_guarantee),
        )
        for status, value in declaration_pairs:
            if (status == "declared") != (value is not None):
                raise ValueError("request declaration must match its explicit status")
        if (self.contrast_status == "declared") != (self.treated_value is not None):
            raise ValueError("treated_value must match contrast_status")
        if self.control_value is not None and self.treated_value is not None:
            if not math.isfinite(self.control_value) or not math.isfinite(self.treated_value):
                raise ValueError("contrast values must be finite")
            if self.control_value == self.treated_value:
                raise ValueError("control and treated values must differ")
        return self


class _CaptureFactsV1(BaseModel):
    """Private writer-ready facts matched to the actual selected input."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    source_data_ref: HTEInputSourceRef | None
    source_data_ref_status: Literal["capture_matched", "not_established"]
    source_data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"]
    selected_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fit_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eval_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fit_eval_relation: Literal["same_selected_rows"]
    n_selected_rows: int = Field(gt=0)
    n_treated: int = Field(ge=0, strict=True)
    n_control: int = Field(ge=0, strict=True)
    n_features: int = Field(gt=0)
    source_feature_names: tuple[str, ...] | None = None
    n_confounders: int = Field(ge=0)
    sample_ids_status: Literal["provided", "not_established"]
    sample_ids_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    method_fqn: str = Field(min_length=1)
    method_abi: str = Field(min_length=1)
    method_abi_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    method_profile_id: str = Field(min_length=1)
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef | None = None
    resolved_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolved_params: dict[str, Any]
    seed: int
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef | None = None
    request_estimand_status: Literal["declared", "not_established"]
    request_estimand: str | None
    request_target_scope_status: Literal["declared", "not_established"]
    request_target_scope: str | None
    outcome_variable_status: Literal["declared", "not_established"]
    outcome_variable_id: str | None
    treatment_variable_status: Literal["declared", "not_established"]
    treatment_variable_id: str | None
    contrast_status: Literal["declared", "not_established"]
    control_value: float | None
    treated_value: float | None
    request_alpha_status: Literal["declared", "not_established"]
    requested_alpha: float | None = Field(default=None, gt=0.0, lt=1.0)
    requested_guarantee_status: Literal["declared", "not_established"]
    requested_guarantee: (
        Literal[
            "candidate_point",
            "backend_conditional_interval",
            "population_sampling_coverage",
        ]
        | None
    )

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_capture(self) -> _CaptureFactsV1:
        _validate_successor_identity(self.method_fqn, self.method_abi, self.method_profile_id)
        if (self.source_data_ref_status == "capture_matched") != (self.source_data_ref is not None):
            raise ValueError("source ref must match source_data_ref_status")
        if (self.source_data_ref_status == "capture_matched") != (
            self.method_abi_digest is not None
        ):
            raise ValueError("method ABI digest must match capture matching status")
        if (self.source_data_ref_status == "capture_matched") != (
            self.owned_attempt_anchor_ref is not None
        ):
            raise ValueError("owner anchor ref must match capture matching status")
        if (self.source_data_ref_status == "capture_matched") != (
            self.materialization_binding_ref is not None
        ):
            raise ValueError("physical materialization ref must match capture matching status")
        if self.selected_input_sha256 != self.source_data_sha256:
            raise ValueError("selected input digest must match full source digest")
        if self.fit_rows_sha256 != self.eval_rows_sha256:
            raise ValueError("fit and eval rows must be the same selected rows")
        if (
            self.source_feature_names is not None
            and len(self.source_feature_names) != self.n_features
        ):
            raise ValueError("source feature names must match the selected X width")
        if self.contrast_status == "declared":
            if self.n_treated + self.n_control != self.n_selected_rows:
                raise ValueError("binary requested contrast counts must cover selected rows")
        elif self.n_treated != 0 or self.n_control != 0:
            raise ValueError("unestablished contrast cannot carry treatment counts")
        if (self.sample_ids_status == "provided") != (self.sample_ids_sha256 is not None):
            raise ValueError("sample_ids_sha256 must match sample_ids_status")
        if (self.request_alpha_status == "declared") != (self.requested_alpha is not None):
            raise ValueError("requested alpha must match its declaration status")
        return self


class HTEProducerResourceReceiptV1(BaseModel):
    """Observed entry and exit state of the complete v2 producer resource scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    execution_status: Literal["not_started", "returned", "raised"]
    scope: Literal["producer_scoped_joblib_parallelism_one"] = (
        "producer_scoped_joblib_parallelism_one"
    )
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    estimator_before_class_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    estimator_before_n_jobs: int | None = Field(default=None, strict=True)
    estimator_before_params_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    estimator_after_class_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    estimator_after_n_jobs: int | None = Field(default=None, strict=True)
    estimator_after_params_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    joblib_started: bool = False
    joblib_finished: bool = False
    joblib_exit_status: Literal["not_started", "returned", "raised"] = "not_started"
    joblib_profile_id: Literal["joblib.parallel_config.current_thread@1.0"] | None = None
    joblib_profile_revision: Literal["1.0"] | None = None
    joblib_implementation: Literal["joblib.parallel_config"] | None = None
    joblib_implementation_version: str | None = Field(default=None, min_length=1, max_length=96)
    joblib_scope: Literal["current_thread_joblib"] | None = None
    joblib_max_jobs: Literal[1] | None = None
    joblib_entry_effective_jobs: int | None = Field(default=None, ge=1, strict=True)
    joblib_entry_backend_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    joblib_entry_config_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    joblib_entry_implementation_version: str | None = Field(
        default=None, min_length=1, max_length=96
    )
    joblib_exit_effective_jobs: int | None = Field(default=None, ge=1, strict=True)
    joblib_exit_backend_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    joblib_exit_config_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    joblib_exit_implementation_version: str | None = Field(
        default=None, min_length=1, max_length=96
    )

    @model_validator(mode="after")
    def _validate_resource_receipt(self) -> HTEProducerResourceReceiptV1:
        estimator_fields = (
            self.estimator_before_class_fqn,
            self.estimator_before_n_jobs,
            self.estimator_before_params_sha256,
            self.estimator_after_class_fqn,
            self.estimator_after_n_jobs,
            self.estimator_after_params_sha256,
        )
        joblib_fields = (
            self.joblib_profile_id,
            self.joblib_profile_revision,
            self.joblib_implementation,
            self.joblib_implementation_version,
            self.joblib_scope,
            self.joblib_max_jobs,
            self.joblib_entry_effective_jobs,
            self.joblib_entry_backend_fqn,
            self.joblib_entry_config_sha256,
            self.joblib_entry_implementation_version,
            self.joblib_exit_effective_jobs,
            self.joblib_exit_backend_fqn,
            self.joblib_exit_config_sha256,
            self.joblib_exit_implementation_version,
        )
        if self.execution_status == "not_started":
            if any(value is not None for value in estimator_fields + joblib_fields):
                raise ValueError("unstarted_hte_resource_receipt_contains_observations")
            if (
                self.joblib_started
                or self.joblib_finished
                or self.joblib_exit_status != "not_started"
            ):
                raise ValueError("unstarted_hte_resource_receipt_has_joblib_lifecycle")
            return self
        if not self.joblib_started or not self.joblib_finished:
            raise ValueError("started_hte_producer_requires_full_joblib_lifecycle")
        if self.joblib_exit_status != self.execution_status:
            raise ValueError("joblib_receipt_lifecycle_status_mismatch")
        if any(value is None for value in joblib_fields):
            raise ValueError("joblib_receipt_missing_observation")
        if (
            self.joblib_profile_id != "joblib.parallel_config.current_thread@1.0"
            or self.joblib_profile_revision != "1.0"
            or self.joblib_implementation != "joblib.parallel_config"
            or self.joblib_scope != "current_thread_joblib"
            or self.joblib_max_jobs != 1
            or self.joblib_entry_implementation_version != self.joblib_implementation_version
        ):
            raise ValueError("joblib_receipt_identity_mismatch")
        # This receipt records what the producer observed. Qualification of a
        # numeric result is a separate predicate in
        # _validate_numeric_resource_receipt; a normal typed refusal must be
        # able to preserve a returned-but-invalid resource observation.
        estimator_complete = all(value is not None for value in estimator_fields)
        if any(value is not None for value in estimator_fields) and not estimator_complete:
            raise ValueError("estimator_observation_must_be_complete")
        if (
            estimator_complete
            and self.execution_status == "returned"
            and (
                self.estimator_before_class_fqn != self.estimator_after_class_fqn
                or self.estimator_before_params_sha256 != self.estimator_after_params_sha256
            )
        ):
            raise ValueError("returned_estimator_observation_changed_configuration")
        return self


class _EstimatorConfigurationV1(BaseModel):
    """Strict captured estimator class and complete-parameter digest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    class_fqn: str = Field(min_length=1, max_length=256)
    n_jobs: int = Field(strict=True)
    params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class _EstimatorObservationPairV1(BaseModel):
    """Captured estimator configuration before and after the fitted call."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    before: _EstimatorConfigurationV1 | None
    after: _EstimatorConfigurationV1 | None

    @model_validator(mode="after")
    def _require_complete_pair(self) -> _EstimatorObservationPairV1:
        if (self.before is None) != (self.after is None):
            raise ValueError("estimator_observation_pair_must_be_complete")
        return self


class _InvalidJoblibEffectiveJobs(ValueError):
    """A Joblib backend returned a value outside its integer contract."""


def _not_started_resource_receipt(
    method_profile_id: _HTEMethodProfileId,
) -> HTEProducerResourceReceiptV1:
    """Describe a selected but not-entered method resource scope."""
    return HTEProducerResourceReceiptV1(
        execution_status="not_started",
        method_profile_id=method_profile_id,
    )


def _capture_joblib_observation() -> dict[str, Any]:
    """Recompute current-thread joblib configuration inside its owner scope."""
    try:
        from importlib.metadata import version as package_version

        import joblib
        from joblib.parallel import get_active_backend
    except (ImportError, PackageNotFoundError) as exc:
        raise ValueError("hte_joblib_resource_profile_unavailable") from exc
    # Explicit None asks Joblib to resolve the thread-local parallel_config value;
    # omitting it uses the API default n_jobs=-1 and measures host capacity.
    effective_n_jobs_api: object = getattr(joblib, "effective_n_jobs", None)
    if not callable(effective_n_jobs_api):
        raise ValueError("hte_joblib_resource_profile_unavailable")
    raw_effective_jobs: object = effective_n_jobs_api(n_jobs=None)
    if type(raw_effective_jobs) is not int:
        raise _InvalidJoblibEffectiveJobs("hte_joblib_resource_profile_invalid")
    if raw_effective_jobs < 1:
        raise _InvalidJoblibEffectiveJobs("hte_joblib_resource_profile_invalid")
    effective_jobs: int = raw_effective_jobs
    backend = get_active_backend()[0]
    backend_fqn = f"{type(backend).__module__}.{type(backend).__qualname__}"
    joblib_version = package_version("joblib")
    config_payload = {
        "profile_id": "joblib.parallel_config.current_thread@1.0",
        "profile_revision": "1.0",
        "implementation": "joblib.parallel_config",
        "implementation_version": joblib_version,
        "scope": "current_thread_joblib",
        "max_jobs": 1,
        "effective_jobs": effective_jobs,
        "active_backend_fqn": backend_fqn,
    }
    return {
        "effective_jobs": effective_jobs,
        "backend_fqn": backend_fqn,
        "implementation_version": joblib_version,
        "config_sha256": _sha256(config_payload),
    }


def _capture_estimator_observation(estimator: Any) -> dict[str, Any]:
    """Recompute the actual estimator class and complete deep parameters."""
    getter = getattr(estimator, "get_params", None)
    if not callable(getter):
        return _capture_pinned_econml_constructor_observation(estimator)
    params = getter(deep=True)
    if not isinstance(params, Mapping):
        raise ValueError("hte_estimator_n_jobs_not_one")
    n_jobs = params.get("n_jobs")
    if type(n_jobs) is not int:
        raise ValueError("hte_estimator_n_jobs_not_one")
    return {
        "class_fqn": f"{type(estimator).__module__}.{type(estimator).__qualname__}",
        "n_jobs": n_jobs,
        "params_sha256": _sha256(_json_value(params)),
    }


def _pinned_econml_constructor_values(estimator: object) -> dict[str, object]:
    """Read every named constructor field from one source-pinned EconML instance."""
    try:
        from econml.dml.causal_forest import CausalForestDML
        from econml.dr._drlearner import ForestDRLearner
    except (ImportError, ModuleNotFoundError) as exc:
        raise ValueError("hte_estimator_n_jobs_not_one") from exc

    estimator_type = type(estimator)
    if estimator_type is CausalForestDML:
        relative_source = "econml/dml/causal_forest.py"
    elif estimator_type is ForestDRLearner:
        relative_source = "econml/dr/_drlearner.py"
    else:
        raise ValueError("hte_estimator_n_jobs_not_one")

    distribution_root = _installed_econml_distribution_root()
    initializer = getattr(estimator_type, "__init__", None)
    if (
        distribution_root is None
        or not _source_module_matches(estimator_type, distribution_root, relative_source)
        or not callable(initializer)
        or not _source_module_matches(initializer, distribution_root, relative_source)
    ):
        raise ValueError("hte_estimator_n_jobs_not_one")
    try:
        parameters = inspect.signature(initializer).parameters
    except (TypeError, ValueError) as exc:
        raise ValueError("hte_estimator_n_jobs_not_one") from exc

    constructor_values: dict[str, object] = {}
    for name, parameter in parameters.items():
        if name == "self":
            continue
        if parameter.kind not in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        } or not hasattr(estimator, name):
            raise ValueError("hte_estimator_n_jobs_not_one")
        constructor_values[name] = getattr(estimator, name)
    n_jobs = constructor_values.get("n_jobs")
    if type(n_jobs) is not int or n_jobs != 1:
        raise ValueError("hte_estimator_n_jobs_not_one")
    try:
        _canonical_json_bytes(_json_value(constructor_values))
    except (TypeError, ValueError) as exc:
        raise ValueError("hte_estimator_n_jobs_not_one") from exc
    return constructor_values


def _capture_pinned_econml_constructor_observation(estimator: object) -> dict[str, Any]:
    """Capture class and complete constructor-parameter digest for pinned EconML."""
    constructor_values = _pinned_econml_constructor_values(estimator)
    estimator_type = type(estimator)
    n_jobs = constructor_values["n_jobs"]
    try:
        params_sha256 = _sha256(_json_value(constructor_values))
    except (TypeError, ValueError) as exc:
        raise ValueError("hte_estimator_n_jobs_not_one") from exc
    return {
        "class_fqn": f"{estimator_type.__module__}.{estimator_type.__qualname__}",
        "n_jobs": n_jobs,
        "params_sha256": params_sha256,
    }


def _safe_estimator_observation(estimator: Any | None) -> dict[str, Any] | None:
    """Return a complete observed estimator configuration or explicit unknown."""
    if estimator is None:
        return None
    try:
        return _capture_estimator_observation(estimator)
    except (AttributeError, TypeError, ValueError):
        return None


def _writer_output_with_estimator_observation(
    output: dict[str, Any],
    *,
    method_profile_id: _HTEMethodProfileId,
    before: Mapping[str, Any] | None,
    estimator: Any | None,
) -> dict[str, Any]:
    """Carry actual estimator observations until the complete joblib receipt is closed."""
    if method_profile_id == "econml.causal_forest_dml.native_mean@2.0":
        interval_profile_id: _HTENativeIntervalMethodProfileId = method_profile_id
    elif method_profile_id == "econml.forest_dr.native_mean@2.0":
        interval_profile_id = method_profile_id
    else:
        return output
    after = _safe_estimator_observation(estimator)
    if before is None or after is None:
        return output
    pair = _EstimatorObservationPairV1(
        method_profile_id=interval_profile_id,
        before=_EstimatorConfigurationV1.model_validate(before, strict=True),
        after=_EstimatorConfigurationV1.model_validate(after, strict=True),
    )
    return {**output, "_hte_estimator_observation": pair.model_dump(mode="json")}


def _resource_receipt(
    *,
    method_profile_id: str,
    status: Literal["not_started", "returned", "raised"],
    estimator_before: Mapping[str, Any] | None = None,
    estimator_after: Mapping[str, Any] | None = None,
    joblib_entry: Mapping[str, Any] | None = None,
    joblib_exit: Mapping[str, Any] | None = None,
    joblib_exit_status: Literal["not_started", "returned", "raised"] = "not_started",
    estimator_observation: _EstimatorObservationPairV1 | None = None,
) -> HTEProducerResourceReceiptV1:
    """Build a strict receipt from measured entry and terminal observations."""
    values: dict[str, Any] = {
        "execution_status": status,
        "scope": "producer_scoped_joblib_parallelism_one",
        "method_profile_id": method_profile_id,
    }
    if estimator_observation is not None:
        if estimator_observation.method_profile_id != method_profile_id:
            raise ValueError("estimator_observation_method_profile_mismatch")
        estimator_before = (
            None
            if estimator_observation.before is None
            else estimator_observation.before.model_dump(mode="python")
        )
        estimator_after = (
            None
            if estimator_observation.after is None
            else estimator_observation.after.model_dump(mode="python")
        )
    if estimator_before is not None and estimator_after is not None:
        values.update(
            estimator_before_class_fqn=estimator_before["class_fqn"],
            estimator_before_n_jobs=estimator_before["n_jobs"],
            estimator_before_params_sha256=estimator_before["params_sha256"],
            estimator_after_class_fqn=estimator_after["class_fqn"],
            estimator_after_n_jobs=estimator_after["n_jobs"],
            estimator_after_params_sha256=estimator_after["params_sha256"],
        )
    if joblib_entry is not None and joblib_exit is not None:
        values.update(
            joblib_started=True,
            joblib_finished=True,
            joblib_exit_status=joblib_exit_status,
            joblib_profile_id="joblib.parallel_config.current_thread@1.0",
            joblib_profile_revision="1.0",
            joblib_implementation="joblib.parallel_config",
            joblib_implementation_version=joblib_entry["implementation_version"],
            joblib_scope="current_thread_joblib",
            joblib_max_jobs=1,
            joblib_entry_effective_jobs=joblib_entry["effective_jobs"],
            joblib_entry_backend_fqn=joblib_entry["backend_fqn"],
            joblib_entry_config_sha256=joblib_entry["config_sha256"],
            joblib_entry_implementation_version=joblib_entry["implementation_version"],
            joblib_exit_effective_jobs=joblib_exit["effective_jobs"],
            joblib_exit_backend_fqn=joblib_exit["backend_fqn"],
            joblib_exit_config_sha256=joblib_exit["config_sha256"],
            joblib_exit_implementation_version=joblib_exit["implementation_version"],
        )
    return HTEProducerResourceReceiptV1.model_validate(values)


class _JoblibProfileFailure(ValueError):
    """Carry a measured rejected joblib scope to the typed refusal output."""

    diagnostic_code: _HTEDiagnosticCode

    def __init__(
        self,
        diagnostic_code: _HTEDiagnosticCode,
        receipt: HTEProducerResourceReceiptV1,
        output: Mapping[str, Any] | None = None,
    ):
        self.diagnostic_code = diagnostic_code
        self.receipt = receipt
        self.output = output
        super().__init__(diagnostic_code)


def _run_with_joblib_profile[OutputT: Mapping[str, object]](
    callback: Callable[[], OutputT],
    *,
    method_profile_id: _HTEMethodProfileId,
) -> tuple[OutputT, HTEProducerResourceReceiptV1]:
    """Run a complete HTE producer under a thread-local one-job context."""
    try:
        from joblib import parallel_config
    except ImportError as exc:
        raise ValueError("hte_joblib_resource_profile_unavailable") from exc
    entry: dict[str, Any] | None = None
    exit_observation: dict[str, Any] | None = None
    output: OutputT | None = None
    estimator_observation: _EstimatorObservationPairV1 | None = None
    failure_code: str | None = None
    callback_error: Exception | None = None
    callback_started = False
    try:
        with parallel_config(n_jobs=1):
            try:
                entry = _capture_joblib_observation()
                if entry["effective_jobs"] != 1:
                    failure_code = "resource_profile_invalid"
                else:
                    callback_started = True
                    try:
                        output = callback()
                    except Exception as exc:
                        callback_error = exc
                    if isinstance(output, Mapping):
                        raw_observation = output.get("_hte_estimator_observation")
                        if raw_observation is not None:
                            estimator_observation = _EstimatorObservationPairV1.model_validate(
                                raw_observation, strict=True
                            )
                        candidate = output.get("hte_outcome_write_ready")
                        if (
                            isinstance(candidate, Mapping)
                            and candidate.get("kind") in {"point_estimate", "interval_estimate"}
                            and method_profile_id
                            in {
                                "econml.causal_forest_dml.native_mean@2.0",
                                "econml.forest_dr.native_mean@2.0",
                            }
                            and (
                                estimator_observation is None
                                or estimator_observation.before is None
                                or estimator_observation.after is None
                                or estimator_observation.before.n_jobs != 1
                                or estimator_observation.after.n_jobs != 1
                                or estimator_observation.before.class_fqn
                                != estimator_observation.after.class_fqn
                                or estimator_observation.before.params_sha256
                                != estimator_observation.after.params_sha256
                            )
                        ):
                            failure_code = "resource_profile_invalid"
            finally:
                if entry is not None:
                    exit_observation = _capture_joblib_observation()
            if callback_error is not None:
                # Let the exception cross the context manager so its receipt
                # records a raised producer lifecycle, then convert it to a
                # typed refusal below.
                raise callback_error
    except _InvalidJoblibEffectiveJobs as exc:
        if callback_started:
            # Receipt v1 requires integer observations at both endpoints. Once
            # the method callback ran, do not manufacture a completed receipt
            # or downgrade the producer to a not_started refusal.
            raise ValueError("hte_joblib_resource_observation_invalid_after_start") from exc
        raise _JoblibProfileFailure(
            "resource_profile_invalid",
            _not_started_resource_receipt(method_profile_id),
        ) from exc
    except Exception:
        failure_code = failure_code or "hte_execution_failed"
        status: Literal["returned", "raised"] = "raised"
    else:
        status = "returned"
    if entry is None or exit_observation is None:
        # No output may claim an observed producer scope when either endpoint
        # could not be measured. Fail the worker path closed instead of
        # manufacturing an unstarted or completed receipt.
        raise ValueError("hte_joblib_resource_observation_incomplete")
    if (
        entry is not None
        and exit_observation is not None
        and (
            entry["effective_jobs"] != exit_observation["effective_jobs"]
            or entry["backend_fqn"] != exit_observation["backend_fqn"]
            or entry["config_sha256"] != exit_observation["config_sha256"]
            or entry["implementation_version"] != exit_observation["implementation_version"]
        )
    ):
        failure_code = failure_code or "resource_profile_invalid"
    receipt = _resource_receipt(
        method_profile_id=method_profile_id,
        status=status,
        estimator_observation=estimator_observation,
        joblib_entry=entry,
        joblib_exit=exit_observation,
        joblib_exit_status=status,
    )
    if failure_code is not None:
        raise _JoblibProfileFailure(
            failure_code,
            receipt,
            output if isinstance(output, Mapping) else None,
        )
    if output is None:
        raise ValueError("hte_joblib_callback_did_not_return_mapping")
    return output, receipt


def _validate_numeric_resource_receipt(
    method_profile_id: str,
    receipt: HTEProducerResourceReceiptV1,
) -> None:
    """Require the actual one-job scope for every numeric successor candidate."""
    if (
        receipt.method_profile_id != method_profile_id
        or receipt.execution_status != "returned"
        or receipt.scope != "producer_scoped_joblib_parallelism_one"
        or not receipt.joblib_started
        or not receipt.joblib_finished
        or receipt.joblib_exit_status != "returned"
        or receipt.joblib_entry_effective_jobs != 1
        or receipt.joblib_exit_effective_jobs != 1
        or receipt.joblib_entry_backend_fqn != receipt.joblib_exit_backend_fqn
        or receipt.joblib_entry_config_sha256 != receipt.joblib_exit_config_sha256
        or receipt.joblib_entry_implementation_version != receipt.joblib_exit_implementation_version
    ):
        raise ValueError("numeric_hte_candidate_requires_returned_one_job_scope")
    if method_profile_id in {
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.forest_dr.native_mean@2.0",
    }:
        native_profile = _native_inference_profile_for_method_profile_v1(method_profile_id)
        if (
            receipt.estimator_before_class_fqn is None
            or receipt.estimator_after_class_fqn is None
            or receipt.estimator_before_n_jobs != 1
            or receipt.estimator_after_n_jobs != 1
            or receipt.estimator_before_class_fqn != native_profile.estimator_class
            or receipt.estimator_after_class_fqn != native_profile.estimator_class
            or receipt.estimator_before_params_sha256 != receipt.estimator_after_params_sha256
        ):
            raise ValueError("native_hte_candidate_requires_recomputed_estimator_config")


class _WriterReadyBase(BaseModel):
    """Strict private candidate written into the ordinary method result only."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    method_fqn: str = Field(min_length=1)
    method_abi: str = Field(min_length=1)
    method_profile_id: str = Field(min_length=1)
    resource_receipt: HTEProducerResourceReceiptV1
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_method_identity(self) -> _WriterReadyBase:
        _validate_successor_identity(self.method_fqn, self.method_abi, self.method_profile_id)
        if self.resource_receipt.method_profile_id != self.method_profile_id:
            raise ValueError("writer method and resource profile differ")
        return self


class _NativeInferenceCaptureV1(BaseModel):
    """Raw native summary consumed to create the persisted inference basis."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    inference_profile_id: Literal["econml_native_mean_over_selected_x@1.0"]
    method_fqn: str = Field(min_length=1)
    method_abi: str = Field(min_length=1)
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    estimator_class: str = Field(min_length=1)
    inference_class: str = Field(min_length=1)
    econml_version: Literal["0.17.0"]
    econml_source_profile_sha256: Literal[
        "27b24c985f552585d38a3cd163301feb0f3755bf1e39c32c3abdbb1b865dba56"
    ]
    ate_inference_method: Literal["econml._cate_estimator.TreatmentExpansionMixin.ate_inference"]
    conf_int_mean_method: Literal[
        "econml.inference._inference.PopulationSummaryResults.conf_int_mean"
    ]
    native_result_class: Literal["econml.inference._inference.PopulationSummaryResults"]
    inference_route: Literal["ate_inference.conf_int_mean"]
    resolved_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"]
    selected_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fit_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eval_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fit_eval_relation: Literal["same_selected_rows"]
    sample_ids_status: Literal["provided", "not_established"]
    sample_ids_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    n_selected_rows: int = Field(gt=0)
    resolved_params: dict[str, Any]
    seed: int
    estimator_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    estimator_params: dict[str, Any]
    nuisance_model_classes: tuple[str, ...]
    alpha: float = Field(gt=0.0, lt=1.0)
    confidence_level: float = Field(gt=0.0, lt=1.0)
    native_point: float
    native_lower_bound: float
    native_upper_bound: float
    native_mean_pred: float
    native_mean_pred_stderr: float | None
    native_stderr_mean: float | None
    standard_error_source: Literal["mean_pred_stderr", "rms_pred_stderr"]
    standard_error_value: float = Field(ge=0.0)
    native_pred_stderr_values: tuple[float, ...] = Field(min_length=1)
    native_pred_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    native_pred_stderr_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conditional_assumptions: tuple[str, ...] = Field(min_length=1)

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_native_capture(self) -> _NativeInferenceCaptureV1:
        _validate_successor_identity(self.method_fqn, self.method_abi, self.method_profile_id)
        _validate_native_inference_profile_identity_v1(
            method_fqn=self.method_fqn,
            method_abi=self.method_abi,
            method_profile_id=self.method_profile_id,
            econml_version=self.econml_version,
            estimator_class=self.estimator_class,
            inference_class=self.inference_class,
            econml_source_profile_sha256=self.econml_source_profile_sha256,
            ate_inference_method=self.ate_inference_method,
            conf_int_mean_method=self.conf_int_mean_method,
            native_result_class=self.native_result_class,
            inference_route=self.inference_route,
        )
        for field_name in (
            "native_point",
            "native_lower_bound",
            "native_upper_bound",
            "native_mean_pred",
            "standard_error_value",
        ):
            if not math.isfinite(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be finite")
        if not math.isclose(
            self.confidence_level,
            1.0 - self.alpha,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("confidence_level must equal 1 - alpha")
        if self.standard_error_source == "mean_pred_stderr":
            if self.native_mean_pred_stderr is None:
                raise ValueError("native mean standard error is required for this source")
            if not math.isclose(
                self.standard_error_value,
                self.native_mean_pred_stderr,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ValueError("native mean standard error must be preserved exactly")
        elif self.native_mean_pred_stderr is not None:
            raise ValueError("RMS standard error route requires absent mean_pred_stderr")
        if len(self.native_pred_stderr_values) != self.n_selected_rows:
            raise ValueError("native standard-error vector must match selected rows")
        if any(not math.isfinite(value) or value < 0.0 for value in self.native_pred_stderr_values):
            raise ValueError("native prediction standard errors must be finite and nonnegative")
        if _sha256(list(self.native_pred_stderr_values)) != self.native_pred_stderr_sha256:
            raise ValueError("native standard-error digest does not match its values")
        if self.standard_error_source == "rms_pred_stderr":
            rms = math.sqrt(
                math.fsum(value * value for value in self.native_pred_stderr_values)
                / len(self.native_pred_stderr_values)
            )
            if (
                self.native_stderr_mean is None
                or not math.isclose(self.native_stderr_mean, rms, rel_tol=1.0e-10, abs_tol=1.0e-12)
                or not math.isclose(
                    self.standard_error_value, rms, rel_tol=1.0e-10, abs_tol=1.0e-12
                )
            ):
                raise ValueError("RMS standard error must be recomputed from native row SEs")
        return self


def _validate_native_capture_resource_identity(
    capture: _NativeInferenceCaptureV1,
    receipt: HTEProducerResourceReceiptV1,
) -> None:
    """Join captured native estimator identity to observed owner resource data."""
    profile = _native_inference_profile_v1(
        capture.method_fqn,
        capture.method_abi,
        capture.method_profile_id,
    )
    if (
        receipt.method_profile_id != profile.method_profile_id
        or receipt.estimator_before_class_fqn != profile.estimator_class
        or receipt.estimator_after_class_fqn != profile.estimator_class
    ):
        raise ValueError("native_capture_estimator_does_not_match_resource_observation")


class HTEWriterReadyPointV1(_WriterReadyBase):
    """Finite point candidate with no inferential interval claim."""

    kind: Literal["point_estimate"] = "point_estimate"
    capture: _CaptureFactsV1
    point_estimate: float
    inference_status: Literal[
        "not_requested", "unavailable", "unsupported", "not_qualified", "failed"
    ]
    inference_reason: Literal[
        "inference_not_requested",
        "native_inference_unavailable",
        "native_inference_invalid",
        "method_profile_not_qualified",
        "selection_uses_outcomes",
        "contrast_not_established",
        "request_alpha_not_established",
    ]
    cate_values: tuple[float, ...]
    native_diagnostic: _NativeInferenceCaptureV1 | None = None

    @model_validator(mode="after")
    def _validate_point(self) -> HTEWriterReadyPointV1:
        expected_reasons = {
            "not_requested": {"inference_not_requested"},
            "unavailable": {"native_inference_unavailable"},
            "unsupported": {"selection_uses_outcomes", "contrast_not_established"},
            "not_qualified": {
                "method_profile_not_qualified",
                "request_alpha_not_established",
            },
            "failed": {"native_inference_invalid"},
        }
        if self.inference_reason not in expected_reasons[self.inference_status]:
            raise ValueError("inference status and reason are contradictory")
        if not math.isfinite(self.point_estimate):
            raise ValueError("point_estimate must be finite")
        if len(self.cate_values) != self.capture.n_selected_rows:
            raise ValueError("cate_values must match selected row count")
        if not all(math.isfinite(value) for value in self.cate_values):
            raise ValueError("cate_values must be finite")
        if self.native_diagnostic is not None:
            _validate_native_capture_resource_identity(
                self.native_diagnostic,
                self.resource_receipt,
            )
            if (
                self.inference_status != "failed"
                or self.inference_reason != "native_inference_invalid"
                or not math.isclose(
                    self.native_diagnostic.native_point,
                    self.point_estimate,
                    rel_tol=1.0e-12,
                    abs_tol=1.0e-12,
                )
                or self.native_diagnostic.native_lower_bound
                <= self.native_diagnostic.native_point
                <= self.native_diagnostic.native_upper_bound
            ):
                raise ValueError(
                    "native interval diagnostic must preserve a rejected point-excluding interval"
                )
        _validate_numeric_resource_receipt(self.method_profile_id, self.resource_receipt)
        return self


class HTEWriterReadyIntervalV1(_WriterReadyBase):
    """Native interval candidate with no winner-owner refs attached yet."""

    kind: Literal["interval_estimate"] = "interval_estimate"
    capture: _CaptureFactsV1
    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = Field(gt=0.0, lt=1.0)
    interval_semantics: Literal["native_mean_confidence_interval"]
    native_capture: _NativeInferenceCaptureV1
    cate_values: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_interval(self) -> HTEWriterReadyIntervalV1:
        if not all(
            math.isfinite(value)
            for value in (self.point_estimate, self.lower_bound, self.upper_bound)
        ):
            raise ValueError("native interval values must be finite")
        if self.lower_bound > self.upper_bound:
            raise ValueError("native interval bounds must be ordered")
        if not self.lower_bound <= self.point_estimate <= self.upper_bound:
            raise ValueError(
                "native interval must satisfy the legacy HTEResult point-containment rule"
            )
        if not math.isclose(
            self.confidence_level,
            self.native_capture.confidence_level,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("interval confidence must match native capture")
        if not math.isclose(
            self.point_estimate,
            self.native_capture.native_point,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("point_estimate must match native point")
        if len(self.cate_values) != self.native_capture.n_selected_rows:
            raise ValueError("native point-result vector must match selected rows")
        if not all(math.isfinite(value) for value in self.cate_values):
            raise ValueError("native point-result vector must be finite")
        _validate_numeric_resource_receipt(self.method_profile_id, self.resource_receipt)
        _validate_native_capture_resource_identity(
            self.native_capture,
            self.resource_receipt,
        )
        return self


class HTEWriterReadyRefusalV1(BaseModel):
    """Private refusal result with no estimate or interval values."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["refusal"] = "refusal"
    method_fqn: str = Field(min_length=1)
    method_abi: str = Field(min_length=1)
    method_profile_id: str = Field(min_length=1)
    resource_receipt: HTEProducerResourceReceiptV1
    capture: _CaptureFactsV1 | None = None
    limitations: tuple[str, ...] = Field(min_length=1)
    refusal_stage: Literal["prepare", "fit", "infer"]
    refusal_reason: Literal[
        "invalid_point_estimate",
        "method_execution_failed",
        "required_input_unavailable",
        "invalid_selected_input",
        "method_profile_unavailable",
    ]
    diagnostic_code: Literal[
        "hte_input_invalid",
        "contrast_not_established",
        "empty_selected_input",
        "econml_unavailable",
        "joblib_unavailable",
        "resource_profile_invalid",
        "dml_profile_invalid",
        "meta_profile_invalid",
        "hte_execution_failed",
        "hte_fit_failed",
        "hte_point_estimate_invalid",
    ]

    @model_validator(mode="after")
    def _validate_refusal_capture(self) -> HTEWriterReadyRefusalV1:
        _validate_successor_identity(self.method_fqn, self.method_abi, self.method_profile_id)
        if self.resource_receipt.method_profile_id != self.method_profile_id:
            raise ValueError("refusal method and resource profile differ")
        if self.refusal_stage in {"fit", "infer"} and self.capture is None:
            raise ValueError("post-prepare_method_refusal_requires_actual_input_capture")
        if self.capture is not None and (
            self.capture.method_fqn != self.method_fqn
            or self.capture.method_abi != self.method_abi
            or self.capture.method_profile_id != self.method_profile_id
        ):
            raise ValueError("refusal_capture_must_match_selected_method")
        return self


type HTEWriterReadyV1 = HTEWriterReadyPointV1 | HTEWriterReadyIntervalV1 | HTEWriterReadyRefusalV1
_WRITER_READY_ADAPTER: TypeAdapter[HTEWriterReadyV1] = TypeAdapter(HTEWriterReadyV1)


def validate_hte_writer_ready(payload: Any) -> HTEWriterReadyV1:
    """Strictly validate the private HTE value selected from MethodResult output."""
    return _WRITER_READY_ADAPTER.validate_python(payload)


def validate_hte_writer_ready_json(payload: Mapping[str, Any]) -> HTEWriterReadyV1:
    """Strictly validate an HTE value crossing a JSON serialization boundary.

    JSON arrays are accepted for tuple fields because the payload is parsed as
    JSON, while the Python validator remains strict for already-typed values.
    Non-JSON Python objects and non-string object keys are rejected before
    serialization so the encoder cannot silently coerce malformed members.
    """
    if type(payload) is not dict:
        raise TypeError("writer-ready JSON payload must be a JSON object")
    _require_writer_ready_json_value(payload)
    return _WRITER_READY_ADAPTER.validate_json(_canonical_json_bytes(payload), strict=True)


def _require_writer_ready_json_value(value: Any) -> None:
    """Require a lossless JSON-native tree before canonical serialization."""
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("writer-ready JSON numbers must be finite")
        return
    if type(value) is list:
        for item in value:
            _require_writer_ready_json_value(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON object keys must be strings")
            _require_writer_ready_json_value(item)
        return
    raise TypeError(f"writer-ready payload contains a non-JSON value: {type(value).__name__}")


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _capture_payload(data: Any, source_data: HTEObservationalData) -> dict[str, Any]:
    """Return the complete normalized input that the fitted estimator consumes."""
    sample_ids = (
        None if source_data.sample_ids is None else _json_value(np.asarray(source_data.sample_ids))
    )
    return {
        "input_contract_id": HTEObservationalData.contract_id,
        "outcome": np.asarray(data.y, dtype="<f8").tolist(),
        "treatment": np.asarray(data.t, dtype="<i8").tolist(),
        "covariates": np.asarray(data.x, dtype="<f8").tolist(),
        "confounders": None if data.w is None else np.asarray(data.w, dtype="<f8").tolist(),
        "feature_names": list(data.feature_names),
        "confounder_names": list(data.confounder_names),
        "sample_ids": sample_ids,
        "metadata": _json_value(source_data.metadata),
    }


def _method_params(params: Mapping[str, Any]) -> dict[str, Any]:
    allowed_runner_keys = {"__rng__", "__seed__"}
    unexpected_private = {
        str(key)
        for key in params
        if str(key).startswith("__") and str(key) not in allowed_runner_keys
    }
    if unexpected_private:
        raise ValueError("unexpected_reserved_method_parameter")
    return {
        str(key): _json_value(value)
        for key, value in params.items()
        if str(key) not in allowed_runner_keys
    }


def _row_identity_hashes(
    source_data: HTEObservationalData,
) -> tuple[str, str, str | None, str]:
    n_rows = int(source_data.outcome.shape[0])
    if source_data.sample_ids is None:
        row_keys: list[Any] = list(range(n_rows))
        sample_status: Literal["provided", "not_established"] = "not_established"
        sample_ids_digest = None
    else:
        row_keys = _json_value(np.asarray(source_data.sample_ids))
        if not isinstance(row_keys, list) or len(row_keys) != n_rows:
            raise ValueError("sample_ids_must_match_selected_row_count")
        if any(isinstance(value, bool) or not isinstance(value, (str, int)) for value in row_keys):
            raise ValueError("sample_ids_must_be_unique_json_strings_or_integers")
        row_tokens = [
            json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
            for value in row_keys
        ]
        if len(row_tokens) != len(set(row_tokens)):
            raise ValueError("sample_ids_must_be_unique")
        sample_status = "provided"
        sample_ids_digest = _sha256(row_keys)
    row_order_digest = _sha256(row_keys)
    row_set_digest = _sha256(
        sorted(
            row_keys,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
            ),
        )
    )
    return row_set_digest, row_order_digest, sample_ids_digest, sample_status


def _method_identity(method_class: type[Any]) -> tuple[str, str, str]:
    """Resolve HTE identity only from one of the four registered v2 classes."""
    identities = {
        CausalForestEstimatorV2,
        DoubleMachineLearningV2,
        MetaLearnerEstimatorV2,
        ForestDRLearnerEstimatorV2,
    }
    if method_class not in identities:
        raise ValueError("method_class_not_registered_for_hte_v2")
    return (
        method_class.owned_hte_method_fqn,
        method_class.owned_hte_method_abi,
        method_class.owned_hte_profile_id,
    )


def _request_context_payload(
    request_context: OwnedHTERequestContextV1 | None,
) -> dict[str, Any]:
    """Return the exact Runtime-owned request fields or an explicit unknown set."""
    if request_context is None:
        return {
            "request_estimand_status": "not_established",
            "request_estimand": None,
            "request_target_scope_status": "not_established",
            "request_target_scope": None,
            "outcome_variable_status": "not_established",
            "outcome_variable_id": None,
            "treatment_variable_status": "not_established",
            "treatment_variable_id": None,
            "contrast_status": "not_established",
            "control_value": None,
            "treated_value": None,
            "request_alpha_status": "not_established",
            "requested_alpha": None,
            "requested_guarantee_status": "not_established",
            "requested_guarantee": None,
            "search_uncertainty_task_binding_ref": None,
            "materialization_binding_ref": None,
        }
    if not isinstance(request_context, OwnedHTERequestContextV1):
        raise ValueError("request_context_must_be_runtime_owned_typed_context")
    raw = request_context.model_dump(mode="python")
    field_names = (
        "request_estimand_status",
        "request_estimand",
        "request_target_scope_status",
        "request_target_scope",
        "outcome_variable_status",
        "outcome_variable_id",
        "treatment_variable_status",
        "treatment_variable_id",
        "contrast_status",
        "control_value",
        "treated_value",
        "request_alpha_status",
        "requested_alpha",
        "requested_guarantee_status",
        "requested_guarantee",
        "search_uncertainty_task_binding_ref",
        "materialization_binding_ref",
    )
    try:
        values = {name: raw[name] for name in field_names}
    except KeyError as exc:
        raise ValueError("runtime_owned_hte_request_context_shape_mismatch") from exc
    return values


def _treatment_counts(
    treatment: Any,
    *,
    contrast_status: Literal["declared", "not_established"],
    control_value: float | None,
    treated_value: float | None,
) -> tuple[int, int]:
    """Count selected treatment rows only for an owner-declared contrast."""
    if contrast_status != "declared":
        return 0, 0
    if control_value is None or treated_value is None:
        raise ValueError("declared treatment contrast requires both values")
    values = np.asarray(treatment).reshape(-1)
    n_treated = int(np.count_nonzero(values == treated_value))
    n_control = int(np.count_nonzero(values == control_value))
    if n_treated + n_control != values.size:
        raise ValueError("binary requested contrast counts must cover selected rows")
    return n_treated, n_control


def _capture_facts(
    data: Any,
    source_data: HTEObservationalData,
    params: Mapping[str, Any],
    *,
    method_fqn: str,
    method_abi: str,
    method_profile_id: str,
    runtime_context: OwnedAttemptAnchorDispatchContext | None,
) -> _CaptureFactsV1:
    full_payload = _capture_payload(data, source_data)
    source_digest = _sha256(full_payload)
    n_rows = int(data.y.shape[0])
    row_set_digest, row_order_digest, sample_ids_digest, sample_ids_status = _row_identity_hashes(
        source_data
    )
    x_digest = _sha256(np.asarray(data.x, dtype="<f8").tolist())
    params_json = _method_params(params)
    raw_seed = params.get("__seed__", params_json.get("random_state", 0))
    if type(raw_seed) is not int:
        raise ValueError("random_state_must_be_a_resolved_integer")
    params_digest = _sha256({"params": params_json, "seed": raw_seed})
    source_ref: HTEInputSourceRef | None = None
    anchor_ref: OwnedAttemptAnchorRef | None = None
    method_abi_digest: str | None = None
    source_ref_status: Literal["capture_matched", "not_established"] = "not_established"
    candidate: OwnedHTEInputCaptureV1 | None = None
    n_treated = 0
    n_control = 0
    if runtime_context is not None:
        if not isinstance(runtime_context, OwnedAttemptAnchorDispatchContext):
            raise ValueError("runtime_context_must_be_owner_bound_dispatch_context")
        capture_model = runtime_context.input_capture
        if not isinstance(capture_model, BaseModel):
            raise ValueError("runtime_context_capture_must_be_typed_core_model")
        capture_raw = capture_model.model_dump(mode="python")
        request_raw = capture_raw.pop("request_context", None)
        if not isinstance(request_raw, Mapping):
            raise ValueError("runtime_context_request_capture_missing")
        if capture_raw.get("materialization_binding_ref") != request_raw.get(
            "materialization_binding_ref"
        ):
            raise ValueError("runtime_context_materialization_binding_mismatch")
        candidate = OwnedHTEInputCaptureV1.model_validate({**capture_raw, **dict(request_raw)})
        anchor_ref = OwnedAttemptAnchorRef.model_validate(
            runtime_context.anchor_ref.model_dump(mode="python"), strict=True
        )
        expected_abi_digest = runtime_context.method_abi_digest
        n_treated, n_control = _treatment_counts(
            data.t,
            contrast_status=candidate.contrast_status,
            control_value=candidate.control_value,
            treated_value=candidate.treated_value,
        )
        if (
            candidate.source_data_sha256 != source_digest
            or candidate.selected_input_sha256 != source_digest
            or candidate.selected_x_sha256 != x_digest
            or candidate.selected_rows_sha256 != row_set_digest
            or candidate.selected_row_order_sha256 != row_order_digest
            or candidate.n_selected_rows != n_rows
            or candidate.n_treated != n_treated
            or candidate.n_control != n_control
            or candidate.n_features != int(data.x.shape[1])
            or candidate.source_feature_names
            != (
                None
                if source_data.feature_names is None
                else tuple(str(name) for name in source_data.feature_names)
            )
            or candidate.n_confounders != (0 if data.w is None else int(data.w.shape[1]))
            or candidate.sample_ids_sha256 != sample_ids_digest
            or candidate.sample_ids_status != sample_ids_status
            or candidate.method_fqn != method_fqn
            or candidate.method_abi != method_abi
            or candidate.method_abi_digest != expected_abi_digest
            or candidate.method_profile_id != method_profile_id
            or candidate.resolved_params_sha256 != params_digest
            or candidate.resolved_params != params_json
            or candidate.seed != raw_seed
            or candidate.fit_rows_sha256 != row_order_digest
            or candidate.eval_rows_sha256 != row_order_digest
        ):
            raise ValueError("owned_hte_input_capture_mismatch")
        if candidate.request_alpha_status == "declared":
            resolved_alpha = params_json.get("alpha")
            if (
                resolved_alpha is None
                or candidate.requested_alpha is None
                or float(candidate.requested_alpha) != float(resolved_alpha)
            ):
                raise ValueError("owned_hte_request_alpha_mismatch")
        if any(
            params_json.get(name) is not None for name in ("control_value", "treated_value")
        ) and (
            candidate.contrast_status != "declared"
            or candidate.control_value != params_json.get("control_value")
            or candidate.treated_value != params_json.get("treated_value")
        ):
            raise ValueError("method_contrast_must_match_runtime_request_context")
        source_ref = candidate.source_data_ref
        method_abi_digest = candidate.method_abi_digest
        source_ref_status = "capture_matched"
    control_value = None
    treated_value = None
    contrast_declared = False
    if source_ref_status == "capture_matched" and candidate is not None:
        control_value = candidate.control_value
        treated_value = candidate.treated_value
        contrast_declared = candidate.contrast_status == "declared"
    if candidate is None:
        n_treated, n_control = _treatment_counts(
            data.t,
            contrast_status="not_established",
            control_value=None,
            treated_value=None,
        )
    return _CaptureFactsV1.model_validate(
        {
            "source_data_ref": source_ref,
            "source_data_ref_status": source_ref_status,
            "source_data_sha256": source_digest,
            "input_profile_id": _INPUT_PROFILE_ID,
            "selected_input_sha256": source_digest,
            "selected_rows_sha256": row_set_digest,
            "selected_x_sha256": x_digest,
            "selected_row_order_sha256": row_order_digest,
            "fit_rows_sha256": row_order_digest,
            "eval_rows_sha256": row_order_digest,
            "fit_eval_relation": "same_selected_rows",
            "n_selected_rows": n_rows,
            "n_treated": n_treated,
            "n_control": n_control,
            "n_features": int(data.x.shape[1]),
            "source_feature_names": (
                None
                if source_data.feature_names is None
                else tuple(str(name) for name in source_data.feature_names)
            ),
            "n_confounders": 0 if data.w is None else int(data.w.shape[1]),
            "sample_ids_status": sample_ids_status,
            "sample_ids_sha256": sample_ids_digest,
            "method_fqn": method_fqn,
            "method_abi": method_abi,
            "method_abi_digest": method_abi_digest,
            "method_profile_id": method_profile_id,
            "owned_attempt_anchor_ref": anchor_ref,
            "resolved_params_sha256": params_digest,
            "resolved_params": params_json,
            "seed": raw_seed,
            "materialization_binding_ref": candidate.materialization_binding_ref
            if candidate is not None
            else None,
            "request_estimand_status": candidate.request_estimand_status
            if candidate is not None
            else "not_established",
            "request_estimand": candidate.request_estimand if candidate is not None else None,
            "request_target_scope_status": candidate.request_target_scope_status
            if candidate is not None
            else "not_established",
            "request_target_scope": candidate.request_target_scope
            if candidate is not None
            else None,
            "outcome_variable_status": candidate.outcome_variable_status
            if candidate is not None
            else "not_established",
            "outcome_variable_id": candidate.outcome_variable_id if candidate is not None else None,
            "treatment_variable_status": candidate.treatment_variable_status
            if candidate is not None
            else "not_established",
            "treatment_variable_id": candidate.treatment_variable_id
            if candidate is not None
            else None,
            "request_alpha_status": candidate.request_alpha_status
            if candidate is not None
            else "not_established",
            "requested_alpha": candidate.requested_alpha if candidate is not None else None,
            "requested_guarantee_status": candidate.requested_guarantee_status
            if candidate is not None
            else "not_established",
            "requested_guarantee": candidate.requested_guarantee if candidate is not None else None,
            "search_uncertainty_task_binding_ref": (
                candidate.search_uncertainty_task_binding_ref if candidate is not None else None
            ),
            "contrast_status": "declared" if contrast_declared else "not_established",
            "control_value": control_value if contrast_declared else None,
            "treated_value": treated_value if contrast_declared else None,
        }
    )


def build_owned_hte_input_capture(
    data: HTEObservationalData | Mapping[str, Any],
    *,
    source_data_ref: HTEInputSourceRef | Mapping[str, Any],
    method_class: type[Any],
    method_abi_digest: str,
    resolved_params: Mapping[str, Any],
    seed: int,
    request_context: OwnedHTERequestContextV1,
) -> Any:
    """Build the Core-owned pre-fit capture from the exact selected HTE input.

    This function only prepares and fingerprints input already selected by
    Runtime. It never constructs or fits an estimator. Runtime persists the
    returned strict Core model as part of the pre-output owner anchor.
    """
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptHTEInputCapture,
        OwnedHTERequestContextV1,
    )

    if not isinstance(request_context, OwnedHTERequestContextV1):
        raise ValueError("request_context_must_be_runtime_owned_typed_context")
    if type(seed) is not int:
        raise ValueError("seed_must_be_a_resolved_integer")
    if not re.fullmatch(r"[0-9a-f]{64}", method_abi_digest):
        raise ValueError("method_abi_digest_must_be_sha256_hex")
    method_fqn, method_abi, method_profile_id = _method_identity(method_class)
    parsed_state = (
        data
        if isinstance(data, HTEObservationalData)
        else HTEObservationalData.model_validate(data)
    )
    selected_data = build_hte_data(parsed_state)
    normalized_params = _method_params(resolved_params)
    payload = _capture_payload(selected_data, parsed_state)
    source_digest = _sha256(payload)
    row_set_digest, row_order_digest, sample_ids_digest, sample_ids_status = _row_identity_hashes(
        parsed_state
    )
    x_digest = _sha256(np.asarray(selected_data.x, dtype="<f8").tolist())
    n_treated, n_control = _treatment_counts(
        selected_data.t,
        contrast_status=request_context.contrast_status,
        control_value=request_context.control_value,
        treated_value=request_context.treated_value,
    )
    source_ref = HTEInputSourceRef.model_validate(source_data_ref)
    capture_payload = {
        "schema_version": "1.0",
        "source_data_ref": source_ref.model_dump(mode="python"),
        "source_data_sha256": source_digest,
        "input_profile_id": _INPUT_PROFILE_ID,
        "selected_input_sha256": source_digest,
        "selected_rows_sha256": row_set_digest,
        "selected_x_sha256": x_digest,
        "selected_row_order_sha256": row_order_digest,
        "fit_rows_sha256": row_order_digest,
        "eval_rows_sha256": row_order_digest,
        "fit_eval_relation": "same_selected_rows",
        "n_selected_rows": int(selected_data.y.shape[0]),
        "n_treated": n_treated,
        "n_control": n_control,
        "n_features": int(selected_data.x.shape[1]),
        "source_feature_names": (
            None
            if parsed_state.feature_names is None
            else tuple(str(name) for name in parsed_state.feature_names)
        ),
        "n_confounders": 0 if selected_data.w is None else int(selected_data.w.shape[1]),
        "sample_ids_status": sample_ids_status,
        "sample_ids_sha256": sample_ids_digest,
        "method_fqn": method_fqn,
        "method_abi": method_abi,
        "method_abi_digest": method_abi_digest,
        "method_profile_id": method_profile_id,
        "resolved_params_sha256": _sha256({"params": normalized_params, "seed": seed}),
        "resolved_params": normalized_params,
        "seed": seed,
        "materialization_binding_ref": (
            None
            if request_context.materialization_binding_ref is None
            else request_context.materialization_binding_ref.model_dump(mode="python")
        ),
        "request_context": request_context.model_dump(mode="python"),
    }
    return OwnedAttemptHTEInputCapture.model_validate(capture_payload)


def _strict_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _contains_boolean(value: Any) -> bool:
    """Detect Python and NumPy booleans before any lossy numeric coercion."""
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, np.ndarray):
        if value.dtype.kind == "b":
            return True
        if value.dtype.kind == "O":
            return any(_contains_boolean(item) for item in value.flat)
        return False
    if isinstance(value, (tuple, list)):
        return any(_contains_boolean(item) for item in value)
    return False


def _finite_effect(values: object, *, n_rows: int) -> np.ndarray:
    if _contains_boolean(values):
        raise ValueError("point_estimate_invalid")
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("point_estimate_invalid") from exc
    if array.ndim == 0:
        array = array.reshape(1)
    if any(dimension != 1 for dimension in array.shape[1:]):
        raise ValueError("point_estimate_invalid")
    array = array.reshape(-1)
    if array.size != n_rows or not np.isfinite(array).all():
        raise ValueError("point_estimate_invalid")
    return array


def _one_scalar(value: Any, *, name: str) -> float:
    if _contains_boolean(value):
        raise ValueError(f"{name}_invalid")
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}_invalid") from exc
    if array.size != 1:
        raise ValueError(f"{name}_must_be_scalar")
    result = float(array.reshape(-1)[0])
    if not math.isfinite(result):
        raise ValueError(f"{name}_nonfinite")
    return result


def _model_names(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    candidates = value if isinstance(value, (tuple, list)) else (value,)
    names = []
    for candidate in candidates:
        if isinstance(candidate, (tuple, list)):
            names.extend(_model_names(candidate))
        else:
            cls = candidate if isinstance(candidate, type) else type(candidate)
            names.append(f"{cls.__module__}.{cls.__qualname__}")
    return tuple(sorted(set(names)))


def _fitted_nuisance_classes(model: Any) -> tuple[str, ...]:
    names: list[str] = []
    for name in (
        "models_y",
        "models_t",
        "models_regression",
        "models_propensity",
    ):
        if hasattr(model, name):
            names.extend(_model_names(getattr(model, name)))
    return tuple(sorted(set(names)))


def _method_result(
    data: HTEData,
    source_data: HTEObservationalData,
    params: Mapping[str, Any],
    *,
    method_fqn: str,
    method_abi: str,
    method_profile_id: _HTEMethodProfileId,
    method_enum: CausalMethod,
    estimator_factory: _EstimatorFactory,
    profile_kind: _HTEProfileKind,
    estimator_params: dict[str, Any],
    runtime_context: OwnedAttemptAnchorDispatchContext | None,
) -> dict[str, Any]:
    facts = _capture_facts(
        data,
        source_data,
        params,
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        runtime_context=runtime_context,
    )
    limitations = [
        "target_population_not_established_by_this_fit",
        "outcome_measure_unit_not_established",
        "causal_interpretation_is_conditional_on_declared_assumptions",
    ]
    if (
        facts.contrast_status != "declared"
        or facts.control_value is None
        or facts.treated_value is None
    ):
        refusal = HTEWriterReadyRefusalV1(
            method_fqn=method_fqn,
            method_abi=method_abi,
            method_profile_id=method_profile_id,
            resource_receipt=_not_started_resource_receipt(method_profile_id),
            capture=facts,
            limitations=tuple([*limitations, "requested_contrast_not_established"]),
            kind="refusal",
            refusal_stage="prepare",
            refusal_reason="required_input_unavailable",
            diagnostic_code="contrast_not_established",
        )
        return {"hte_outcome_write_ready": refusal.model_dump(mode="json")}

    model: _HTEFitPort | _HTEEffectPort | None = None
    estimator_before: Mapping[str, Any] | None = None

    def output_with_observation(output: dict[str, Any]) -> dict[str, Any]:
        return _writer_output_with_estimator_observation(
            output,
            method_profile_id=method_profile_id,
            before=estimator_before,
            estimator=model,
        )

    try:
        constructor_params = (
            {name: value for name, value in estimator_params.items() if name != "inference"}
            if profile_kind == "forest_dr"
            else estimator_params
        )
        candidate: object = estimator_factory(**constructor_params)
        if not isinstance(candidate, _HTEFitPort):
            raise TypeError("hte_estimator_fit_port_unavailable")
        model = candidate
        if method_profile_id in {
            "econml.causal_forest_dml.native_mean@2.0",
            "econml.forest_dr.native_mean@2.0",
        }:
            estimator_before = _safe_estimator_observation(model)
            if estimator_before is None or estimator_before["n_jobs"] != 1:
                raise ValueError("hte_estimator_n_jobs_not_one")
        if profile_kind == "forest_dr":
            model.fit(
                data.y,
                data.t,
                X=data.x,
                W=data.w,
                inference=estimator_params["inference"],
            )
        else:
            model.fit(data.y, data.t, X=data.x, W=data.w)
    except Exception:
        refusal = HTEWriterReadyRefusalV1(
            method_fqn=method_fqn,
            method_abi=method_abi,
            method_profile_id=method_profile_id,
            resource_receipt=_not_started_resource_receipt(method_profile_id),
            capture=facts,
            limitations=tuple([*limitations, "model_fit_failed"]),
            kind="refusal",
            refusal_stage="fit",
            refusal_reason="method_execution_failed",
            diagnostic_code="hte_fit_failed",
        )
        return output_with_observation({"hte_outcome_write_ready": refusal.model_dump(mode="json")})

    try:
        if not isinstance(model, _HTEEffectPort):
            raise TypeError("hte_estimator_effect_port_unavailable")
        raw_cate = model.effect(data.x, T0=facts.control_value, T1=facts.treated_value)
        cate = _finite_effect(raw_cate, n_rows=facts.n_selected_rows)
        point = _one_scalar(float(np.mean(cate)), name="point_estimate")
    except Exception:
        refusal = HTEWriterReadyRefusalV1(
            method_fqn=method_fqn,
            method_abi=method_abi,
            method_profile_id=method_profile_id,
            resource_receipt=_not_started_resource_receipt(method_profile_id),
            capture=facts,
            limitations=tuple([*limitations, "point_estimate_invalid"]),
            kind="refusal",
            refusal_stage="infer",
            refusal_reason="invalid_point_estimate",
            diagnostic_code="hte_point_estimate_invalid",
        )
        return output_with_observation({"hte_outcome_write_ready": refusal.model_dump(mode="json")})

    point_reason: str | None = "method_profile_not_qualified"
    native_capture: _NativeInferenceCaptureV1 | None = None
    inference_requested = (
        facts.requested_guarantee_status == "declared"
        and facts.requested_guarantee
        in {"backend_conditional_interval", "population_sampling_coverage"}
    )
    if not inference_requested:
        point_reason = "inference_not_requested"
    elif profile_kind == "causal_forest" or profile_kind == "forest_dr":
        native_capture, point_reason = _native_interval_candidate(
            model,
            data.x,
            cate=cate,
            facts=facts,
            params=params,
            estimator_params=estimator_params,
            profile_kind=profile_kind,
            method_fqn=method_fqn,
            method_abi=method_abi,
            nuisance_model_classes=_fitted_nuisance_classes(model),
        )

    resource_receipt = _not_started_resource_receipt(method_profile_id)
    if native_capture is not None and not (
        native_capture.native_lower_bound <= point <= native_capture.native_upper_bound
    ):
        point_reason = "native_inference_invalid"
    if native_capture is not None and point_reason != "native_inference_invalid":
        # This in-process draft is completed only after the outer owner-scoped
        # joblib context exits. It is never returned or persisted before that
        # context replaces the provisional receipt and validates the union.
        interval = HTEWriterReadyIntervalV1.model_construct(
            method_fqn=method_fqn,
            method_abi=method_abi,
            method_profile_id=method_profile_id,
            resource_receipt=resource_receipt,
            capture=facts,
            limitations=tuple(limitations),
            kind="interval_estimate",
            point_estimate=native_capture.native_point,
            lower_bound=native_capture.native_lower_bound,
            upper_bound=native_capture.native_upper_bound,
            confidence_level=native_capture.confidence_level,
            interval_semantics="native_mean_confidence_interval",
            native_capture=native_capture,
            cate_values=tuple(float(value) for value in cate),
        )
        return output_with_observation(
            {"hte_outcome_write_ready": interval.model_dump(mode="json")}
        )

    if profile_kind == "point_only" and inference_requested:
        point_reason = (
            "selection_uses_outcomes"
            if params.get("base_model_candidates")
            else "method_profile_not_qualified"
        )
    # As above, the point is an in-process draft until the complete producer
    # resource receipt is attached after the method-local context exits.
    point_result = HTEWriterReadyPointV1.model_construct(
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        resource_receipt=resource_receipt,
        capture=facts,
        limitations=tuple([*limitations, "native_ate_interval_not_admitted"]),
        kind="point_estimate",
        point_estimate=point,
        inference_status=(
            "not_requested"
            if point_reason == "inference_not_requested"
            else "failed"
            if point_reason == "native_inference_invalid"
            else "unavailable"
            if point_reason == "native_inference_unavailable"
            else "unsupported"
            if point_reason in {"selection_uses_outcomes", "contrast_not_established"}
            else "not_qualified"
        ),
        inference_reason=point_reason or "method_profile_not_qualified",
        cate_values=tuple(float(value) for value in cate),
        native_diagnostic=(
            native_capture
            if native_capture is not None and point_reason == "native_inference_invalid"
            else None
        ),
    )
    return output_with_observation(
        {"hte_outcome_write_ready": point_result.model_dump(mode="json")}
    )


def _econml_source_profile_digest(distribution_root: Path) -> str | None:
    """Recompute the installed EconML 0.17 source identity from pinned bytes.

    The digest includes the exact distribution METADATA and RECORD bytes plus
    every source module used by the supported estimator, inference, and
    extraction path. RECORD entries are independently checked for digest and
    size; matching only a version string or class name never qualifies.
    """
    metadata_path = distribution_root / "econml-0.17.0.dist-info" / "METADATA"
    record_path = distribution_root / "econml-0.17.0.dist-info" / "RECORD"
    try:
        metadata_bytes = metadata_path.read_bytes()
        record_bytes = record_path.read_bytes()
    except OSError:
        return None
    metadata_sha256 = hashlib.sha256(metadata_bytes).hexdigest()
    record_sha256 = hashlib.sha256(record_bytes).hexdigest()
    if metadata_sha256 != _ECONML_METADATA_SHA256 or record_sha256 != _ECONML_RECORD_SHA256:
        return None
    try:
        rows = {row[0]: row for row in csv.reader(record_bytes.decode("utf-8").splitlines())}
    except (UnicodeDecodeError, csv.Error, IndexError):
        return None
    for relative_path, expected_sha256 in _ECONML_SOURCE_FILES_SHA256.items():
        source_path = distribution_root / relative_path
        try:
            source_bytes = source_path.read_bytes()
        except OSError:
            return None
        actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if actual_sha256 != expected_sha256:
            return None
        entry = rows.get(relative_path)
        if entry is None or len(entry) != 3:
            return None
        try:
            recorded_digest = base64.urlsafe_b64decode(
                entry[1].removeprefix("sha256=") + "==="
            ).hex()
            recorded_size = int(entry[2])
        except (ValueError, TypeError):
            return None
        if recorded_digest != actual_sha256 or recorded_size != len(source_bytes):
            return None
    identity = {
        "distribution": "econml",
        "version": "0.17.0",
        "metadata_sha256": metadata_sha256,
        "record_sha256": record_sha256,
        "source_files": _ECONML_SOURCE_FILES_SHA256,
    }
    digest = _sha256(identity)
    return digest if digest == _ECONML_SOURCE_PROFILE_SHA256 else None


def _installed_econml_distribution_root() -> Path | None:
    """Return the active EconML root only when its pinned source bytes match."""
    try:
        installed = distribution("econml")
        if installed.version != "0.17.0":
            return None
        root = Path(str(installed.locate_file(""))).resolve()
    except (PackageNotFoundError, OSError, TypeError):
        return None
    return root if _econml_source_profile_digest(root) is not None else None


def _installed_econml_source_profile_digest() -> str | None:
    """Resolve and verify the active EconML distribution before returning its pin."""
    root = _installed_econml_distribution_root()
    return None if root is None else _econml_source_profile_digest(root)


def _source_module_matches(value: Any, root: Path, relative_path: str) -> bool:
    """Require the loaded class/function module to be the exact pinned file."""
    module = sys.modules.get(getattr(value, "__module__", ""))
    module_path = getattr(module, "__file__", None)
    if not isinstance(module_path, str):
        return False
    try:
        expected = (root / relative_path).resolve()
        loaded = Path(module_path).resolve()
        if loaded != expected:
            return False
        code = getattr(value, "__code__", None)
        if code is not None and Path(code.co_filename).resolve() != expected:
            return False
    except (OSError, RuntimeError, TypeError):
        return False
    return True


def _native_extraction_entry(
    model: Any,
    inference_owner: Any,
    inference_result: Any | None,
    *,
    profile_kind: _HTENativeIntervalProfileKind,
    distribution_root: Path,
) -> tuple[str, str, str] | None:
    """Require exact installed classes and methods for one native extraction route."""
    selected_method_fqn, selected_profile_id = (
        (
            "causal.hte.causal_forest@2.0.0",
            "econml.causal_forest_dml.native_mean@2.0",
        )
        if profile_kind == "causal_forest"
        else (
            "causal.hte.forest_dr@2.0.0",
            "econml.forest_dr.native_mean@2.0",
        )
    )
    selected_profile = _native_inference_profile_v1(
        selected_method_fqn,
        "2.0.0",
        selected_profile_id,
    )
    try:
        from econml.dml.causal_forest import (
            CausalForestDML,
            _GenericSingleOutcomeModelFinalWithCovInference,
        )
        from econml.dr._drlearner import ForestDRLearner
        from econml.inference._inference import (
            GenericModelFinalInferenceDiscrete,
            PopulationSummaryResults,
        )
    except ImportError:
        return None
    if profile_kind == "causal_forest":
        expected_estimator = CausalForestDML
        expected_inference = _GenericSingleOutcomeModelFinalWithCovInference
        estimator_source = "econml/dml/causal_forest.py"
        inference_source = "econml/dml/causal_forest.py"
    else:
        expected_estimator = ForestDRLearner
        expected_inference = GenericModelFinalInferenceDiscrete
        estimator_source = "econml/dr/_drlearner.py"
        inference_source = "econml/inference/_inference.py"
    if (
        type(model) is not expected_estimator
        or type(inference_owner) is not expected_inference
        or (
            f"{expected_estimator.__module__}.{expected_estimator.__qualname__}"
            != selected_profile.estimator_class
        )
        or (
            f"{expected_inference.__module__}.{expected_inference.__qualname__}"
            != selected_profile.inference_class
        )
        or not _source_module_matches(expected_estimator, distribution_root, estimator_source)
        or not _source_module_matches(expected_inference, distribution_root, inference_source)
    ):
        return None
    bound_ate = getattr(model, "ate_inference", None)
    expected_ate = getattr(expected_estimator, "ate_inference", None)
    if (
        getattr(bound_ate, "__func__", None) is not expected_ate
        or getattr(expected_ate, "__module__", None) is None
        or getattr(expected_ate, "__qualname__", None) is None
        or not _source_module_matches(expected_ate, distribution_root, "econml/_cate_estimator.py")
    ):
        return None
    if inference_result is not None:
        if type(inference_result) is not PopulationSummaryResults or not _source_module_matches(
            PopulationSummaryResults,
            distribution_root,
            "econml/inference/_inference.py",
        ):
            return None
        bound_conf_int = getattr(inference_result, "conf_int_mean", None)
        if getattr(
            bound_conf_int, "__func__", None
        ) is not PopulationSummaryResults.conf_int_mean or not _source_module_matches(
            PopulationSummaryResults.conf_int_mean,
            distribution_root,
            "econml/inference/_inference.py",
        ):
            return None
    return (
        f"{expected_ate.__module__}.{expected_ate.__qualname__}",
        _CONF_INT_MEAN_METHOD,
        _ECONML_NATIVE_RESULT_CLASS,
    )


def _native_interval_candidate(
    model: object,
    x: np.ndarray,
    *,
    cate: np.ndarray,
    facts: _CaptureFactsV1,
    params: Mapping[str, Any],
    estimator_params: Mapping[str, Any],
    profile_kind: _HTENativeIntervalProfileKind,
    method_fqn: str,
    method_abi: str,
    nuisance_model_classes: tuple[str, ...],
) -> tuple[_NativeInferenceCaptureV1 | None, str]:
    if facts.source_data_ref_status != "capture_matched" or facts.method_abi_digest is None:
        return None, "method_profile_not_qualified"
    # The request's estimand text is retained as a candidate selector but does
    # not bind the numeric Y/T arrays. The native CI can still be emitted for
    # its actual selected-X mean and the consumer will see identity as unknown.
    if (
        facts.request_target_scope_status != "declared"
        or facts.requested_guarantee_status != "declared"
        or facts.request_alpha_status != "declared"
    ):
        return None, "method_profile_not_qualified"
    if facts.request_alpha_status != "declared" or facts.requested_alpha is None:
        return None, "request_alpha_not_established"
    try:
        selected_profile = _native_inference_profile_v1(
            method_fqn,
            method_abi,
            facts.method_profile_id,
        )
    except ValueError:
        return None, "method_profile_not_qualified"
    actual_estimator_class = f"{type(model).__module__}.{type(model).__qualname__}"
    if actual_estimator_class != selected_profile.estimator_class:
        return None, "method_profile_not_qualified"
    if profile_kind == "causal_forest":
        if (
            selected_profile.method_profile_id != "econml.causal_forest_dml.native_mean@2.0"
            or not _causal_forest_profile_matches(estimator_params)
        ):
            return None, "method_profile_not_qualified"
    elif (
        selected_profile.method_profile_id != "econml.forest_dr.native_mean@2.0"
        or not _forest_dr_profile_matches(estimator_params)
    ):
        return None, "method_profile_not_qualified"
    if (
        facts.contrast_status != "declared"
        or facts.control_value not in {0, 1}
        or facts.treated_value not in {0, 1}
        or facts.control_value == facts.treated_value
    ):
        return None, "contrast_not_established"
    alpha = params.get("alpha")
    if (
        isinstance(alpha, bool)
        or not isinstance(alpha, (int, float))
        or not 0.0 < float(alpha) < 1.0
        or not math.isclose(float(alpha), facts.requested_alpha, rel_tol=0.0, abs_tol=1.0e-12)
    ):
        return None, "method_profile_not_qualified"
    distribution_root = _installed_econml_distribution_root()
    if distribution_root is None:
        return None, "method_profile_not_qualified"
    try:
        econml_version = version("econml")
    except PackageNotFoundError:
        return None, "method_profile_not_qualified"
    source_profile_digest = _econml_source_profile_digest(distribution_root)
    if econml_version != "0.17.0" or source_profile_digest is None:
        return None, "method_profile_not_qualified"
    inference_owner = getattr(model, "_inference", None)
    if inference_owner is None:
        return None, "native_inference_unavailable"
    inference_class = f"{type(inference_owner).__module__}.{type(inference_owner).__qualname__}"
    extraction = _native_extraction_entry(
        model,
        inference_owner,
        None,
        profile_kind=profile_kind,
        distribution_root=distribution_root,
    )
    if extraction is None:
        return None, "method_profile_not_qualified"
    native_inference_method = getattr(model, "ate_inference", None)
    if not callable(native_inference_method):
        return None, "native_inference_unavailable"
    try:
        inference_value: object = native_inference_method(
            x,
            T0=float(facts.control_value),
            T1=float(facts.treated_value),
        )
        extraction = _native_extraction_entry(
            model,
            inference_owner,
            inference_value,
            profile_kind=profile_kind,
            distribution_root=distribution_root,
        )
        if extraction is None:
            return None, "method_profile_not_qualified"
        conf_int_mean = getattr(inference_value, "conf_int_mean", None)
        if not callable(conf_int_mean):
            return None, "native_inference_unavailable"
        if not isinstance(inference_value, _NativeMeanInferencePort):
            return None, "native_inference_unavailable"
        inference = inference_value
        raw_lower, raw_upper = inference.conf_int_mean(alpha=float(alpha))
        lower = _one_scalar(raw_lower, name="native_lower_bound")
        upper = _one_scalar(raw_upper, name="native_upper_bound")
        pred = _finite_effect(inference.pred, n_rows=x.shape[0])
        pred_stderr = _finite_effect(inference.pred_stderr, n_rows=x.shape[0])
        if np.any(pred_stderr < 0.0):
            return None, "native_inference_invalid"
        native_point = _one_scalar(float(np.mean(pred)), name="native_point")
        if not np.array_equal(pred, cate):
            return None, "native_inference_invalid"
        member_mean_se = getattr(inference, "mean_pred_stderr", None)
        if member_mean_se is None:
            stderr_source: Literal["mean_pred_stderr", "rms_pred_stderr"] = "rms_pred_stderr"
            se_value = float(np.sqrt(np.mean(np.square(pred_stderr))))
        else:
            stderr_source = "mean_pred_stderr"
            se_value = _one_scalar(member_mean_se, name="native_mean_pred_stderr")
        stderr_mean = getattr(inference, "stderr_mean", None)
        stderr_mean_value = (
            None if stderr_mean is None else _one_scalar(stderr_mean, name="native_stderr_mean")
        )
        if stderr_mean_value is not None and not math.isclose(
            stderr_mean_value,
            se_value,
            rel_tol=1.0e-10,
            abs_tol=1.0e-12,
        ):
            return None, "native_inference_invalid"
        if stderr_source == "mean_pred_stderr" and se_value < 0.0:
            return None, "native_inference_invalid"
        if stderr_source == "rms_pred_stderr" and (not math.isfinite(se_value) or se_value < 0.0):
            return None, "native_inference_invalid"
    except (AttributeError, NotImplementedError):
        return None, "native_inference_unavailable"
    except Exception:
        return None, "native_inference_invalid"

    if not math.isclose(float(alpha) + (1.0 - float(alpha)), 1.0, abs_tol=1.0e-12):
        return None, "native_inference_invalid"
    facts_dump = facts.model_dump(mode="python")
    data_digest = facts.source_data_sha256
    profile_payload = {
        "inference_profile_id": _INTERVAL_PROFILE_ID,
        "method_fqn": method_fqn,
        "method_abi": method_abi,
        "method_abi_digest": facts.method_abi_digest,
        "method_profile_id": facts.method_profile_id,
        "estimator_class": actual_estimator_class,
        "inference_class": inference_class,
        "econml_version": econml_version,
        "econml_source_profile_sha256": source_profile_digest,
        "native_result_class": extraction[2],
        "ate_inference_method": extraction[0],
        "conf_int_mean_method": extraction[1],
        "inference_route": "ate_inference.conf_int_mean",
        "resolved_params_sha256": facts.resolved_params_sha256,
        "source_data_sha256": data_digest,
        "input_profile_id": _INPUT_PROFILE_ID,
        "selected_input_sha256": facts.selected_input_sha256,
        "selected_rows_sha256": facts.selected_rows_sha256,
        "selected_x_sha256": facts.selected_x_sha256,
        "selected_row_order_sha256": facts.selected_row_order_sha256,
        "fit_rows_sha256": facts.fit_rows_sha256,
        "eval_rows_sha256": facts.eval_rows_sha256,
        "fit_eval_relation": facts.fit_eval_relation,
        "sample_ids_status": facts.sample_ids_status,
        "sample_ids_sha256": facts.sample_ids_sha256,
        "n_selected_rows": int(x.shape[0]),
        "resolved_params": facts_dump["resolved_params"],
        "seed": facts.seed,
        "estimator_params_sha256": _sha256(_json_value(estimator_params)),
        "estimator_params": _json_value(estimator_params),
        "nuisance_model_classes": nuisance_model_classes,
        "alpha": float(alpha),
        "confidence_level": 1.0 - float(alpha),
        "native_point": native_point,
        "native_lower_bound": lower,
        "native_upper_bound": upper,
        "native_mean_pred": native_point,
        "native_mean_pred_stderr": None if member_mean_se is None else se_value,
        "native_stderr_mean": stderr_mean_value,
        "standard_error_source": stderr_source,
        "standard_error_value": se_value,
        "native_pred_stderr_values": tuple(float(value) for value in pred_stderr),
        "native_pred_sha256": _sha256(pred.tolist()),
        "native_pred_stderr_sha256": _sha256(pred_stderr.tolist()),
        "conditional_assumptions": _CONDITIONAL_ASSUMPTIONS,
        "search_uncertainty_task_binding_ref": facts.search_uncertainty_task_binding_ref,
    }
    return _NativeInferenceCaptureV1.model_validate(profile_payload), ""


def _shared_parameters(*, alpha: float) -> tuple[ParameterSpec, ...]:
    return (
        ParameterSpec(name="alpha", default=alpha),
        ParameterSpec(name="control_value", default=None),
        ParameterSpec(name="treated_value", default=None),
        ParameterSpec(name="random_state", default=0),
    )


def _signature(name: str, parameters: tuple[ParameterSpec, ...]) -> MethodSignature:
    return MethodSignature(
        name=name,
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="hte_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_features"),
                    contract_id=HTEObservationalData.contract_id,
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="hte_outcome_write_ready",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("candidate", "json"),
                    description=(
                        "Private writer-ready HTE union; Scientist finalizes owner refs and CAS."
                    ),
                )
            }
        ),
        parameters=parameters,
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend("numpy"),
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


def _metadata(name: str) -> MethodMetadata:
    return MethodMetadata(
        description=f"Source-bound {name} HTE producer with native-only interval admission.",
        tags=frozenset({"causal", "hte", "native-inference"}),
        citations=(
            "Causal interpretation and interval validity remain conditional on the recorded assumptions.",
        ),
        equations={
            "point": "mean_i effect(X_i, T0, T1)",
            "interval": "native ate_inference(X, T0, T1).conf_int_mean(alpha)",
        },
        assumptions={
            "consistency": "Observed outcome equals the potential outcome under observed treatment.",
            "unconfoundedness": "No unobserved confounding conditional on observed covariates.",
            "overlap": "Treatment support covers selected covariate rows.",
        },
        when_to_use="Candidate heterogeneous treatment effect estimation from observational data.",
        when_not_to_use="Requests requiring population scope, external legal authority, or unsupported inference.",
        typical_min_obs=200,
        output_interpretation="Point estimates remain candidates; qualified intervals preserve native bounds exactly.",
    )


def _params_for_request(params: Mapping[str, Any]) -> dict[str, Any]:
    resolved = _method_params(params)
    for name in ("control_value", "treated_value"):
        if resolved.get(name) is not None:
            resolved[name] = _strict_number(resolved[name], name=name)
    for name in (
        "request_estimand",
        "target_scope",
        "outcome_variable_id",
        "treatment_variable_id",
    ):
        if name in resolved:
            raise ValueError(f"{name} requires Runtime-owned request context, not method params")
    if (resolved.get("control_value") is None) != (resolved.get("treated_value") is None):
        raise ValueError("control_value_and_treated_value_must_be_selected_together")
    return resolved


def _attach_resource_receipt(
    output: Mapping[str, Any],
    receipt: HTEProducerResourceReceiptV1,
) -> dict[str, Any]:
    """Attach the observed typed receipt to the private writer-ready value."""
    result = dict(output)
    result.pop("_hte_estimator_observation", None)
    candidate = result.get("hte_outcome_write_ready")
    if not isinstance(candidate, Mapping):
        raise ValueError("hte_writer_ready_output_missing")
    updated = dict(candidate)
    updated["resource_receipt"] = receipt.model_dump(mode="json")
    if updated.get("kind") in {"point_estimate", "interval_estimate"}:
        try:
            _validate_numeric_resource_receipt(receipt.method_profile_id, receipt)
        except ValueError as exc:
            raw_method_profile_id: object = updated.get(
                "method_profile_id", receipt.method_profile_id
            )
            if not _is_registered_method_profile_id(raw_method_profile_id):
                raise ValueError("hte_method_identity_profile_mismatch") from exc
            refusal = _refusal_output(
                str(updated.get("method_fqn", "causal.hte.unknown@2.0.0")),
                str(updated.get("method_abi", "2.0.0")),
                raw_method_profile_id,
                diagnostic_code="resource_profile_invalid",
                resource_receipt=receipt,
                capture=updated.get("capture"),
                limitations=updated.get("limitations", ()),
            )
            return {"hte_outcome_write_ready": refusal["hte_outcome_write_ready"]}
    validated = validate_hte_writer_ready_json(updated)
    return {**result, "hte_outcome_write_ready": validated.model_dump(mode="json")}


def _execute_with_profile(
    state: HTEObservationalData | Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    method_name: str,
    method_abi: str,
    method_profile_id: _HTEMethodProfileId,
    method_enum: CausalMethod,
    profile_kind: _HTEProfileKind,
    runtime_context: OwnedAttemptAnchorDispatchContext | None = None,
) -> dict[str, Any]:
    """Run every v2 producer under its owner-selected one-job method scope."""
    try:
        output, receipt = _run_with_joblib_profile(
            lambda: _execute_with_profile_unscoped(
                state,
                params,
                method_name=method_name,
                method_abi=method_abi,
                method_profile_id=method_profile_id,
                method_enum=method_enum,
                profile_kind=profile_kind,
                runtime_context=runtime_context,
            ),
            method_profile_id=method_profile_id,
        )
    except _JoblibProfileFailure as exc:
        return _refusal_output(
            f"causal.hte.{method_name}@{method_abi}",
            method_abi,
            method_profile_id,
            diagnostic_code=exc.diagnostic_code,
            resource_receipt=exc.receipt,
            capture=(
                exc.output.get("hte_outcome_write_ready", {}).get("capture")
                if isinstance(exc.output, Mapping)
                and isinstance(exc.output.get("hte_outcome_write_ready"), Mapping)
                else None
            ),
            limitations=(
                exc.output.get("hte_outcome_write_ready", {}).get("limitations", ())
                if isinstance(exc.output, Mapping)
                and isinstance(exc.output.get("hte_outcome_write_ready"), Mapping)
                else ()
            ),
        )
    except ValueError as exc:
        if str(exc) == "hte_joblib_resource_profile_unavailable":
            diagnostic_code = "joblib_unavailable"
        else:
            raise
        return _preparation_refusal(
            f"causal.hte.{method_name}@{method_abi}",
            method_abi,
            method_profile_id,
            diagnostic_code,
        )
    return _attach_resource_receipt(output, receipt)


def _execute_with_profile_unscoped(
    state: HTEObservationalData | Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    method_name: str,
    method_abi: str,
    method_profile_id: _HTEMethodProfileId,
    method_enum: CausalMethod,
    profile_kind: _HTEProfileKind,
    runtime_context: OwnedAttemptAnchorDispatchContext | None = None,
) -> dict[str, Any]:
    method_fqn = f"causal.hte.{method_name}@{method_abi}"
    try:
        parsed_state = (
            state
            if isinstance(state, HTEObservationalData)
            else HTEObservationalData.model_validate(state)
        )
        data = build_hte_data(parsed_state)
        resolved = _params_for_request(params)
        seed = resolved.get("random_state", 0)
        if type(seed) is not int:
            raise ValueError("random_state_must_be_int")
    except Exception:
        return _preparation_refusal(method_fqn, method_abi, method_profile_id, "hte_input_invalid")

    estimator_factory: _EstimatorFactory
    profile_id: _HTEMethodProfileId = method_profile_id

    # Explicitly materialize the complete config. The profile gate below checks
    # these values and the live fitted inference object; it never infers a config
    # from a method name or an old result.
    if profile_kind == "causal_forest":
        try:
            from econml.dml import CausalForestDML
        except Exception:
            return _preparation_refusal(
                method_fqn, method_abi, method_profile_id, "econml_unavailable"
            )

        config = {
            "n_estimators": resolved.get("n_estimators", 100),
            "max_depth": resolved.get("max_depth"),
            "min_samples_leaf": resolved.get("min_samples_leaf", 5),
            "max_samples": resolved.get("max_samples", 0.5),
            "honest": resolved.get("honest", True),
            "cv": resolved.get("cv_folds", 3),
            "random_state": seed,
            "model_y": resolved.get("model_y", "auto"),
            "model_t": resolved.get("model_t", "auto"),
            "discrete_treatment": True,
            "n_jobs": resolved.get("n_jobs", 1),
            "inference": "auto",
        }
        profile_id = "econml.causal_forest_dml.native_mean@2.0"
        estimator_factory = CausalForestDML
    elif profile_kind == "forest_dr":
        try:
            from econml.dr import ForestDRLearner
        except Exception:
            return _preparation_refusal(
                method_fqn, method_abi, method_profile_id, "econml_unavailable"
            )

        config = {
            "model_regression": resolved.get("model_regression", "auto"),
            "model_propensity": resolved.get("model_propensity", "auto"),
            "discrete_outcome": False,
            "min_propensity": resolved.get("min_propensity", 0.001),
            "categories": resolved.get("categories", "auto"),
            "cv": resolved.get("cv_folds", 2),
            "mc_iters": resolved.get("mc_iters", 1),
            "mc_agg": resolved.get("mc_agg", "mean"),
            "n_estimators": resolved.get("n_estimators", 32),
            "max_depth": resolved.get("max_depth"),
            "min_samples_split": resolved.get("min_samples_split", 5),
            "min_samples_leaf": resolved.get("min_samples_leaf", 5),
            "max_samples": resolved.get("max_samples", 0.45),
            "min_balancedness_tol": resolved.get("min_balancedness_tol", 0.45),
            "honest": resolved.get("honest", True),
            "subforest_size": resolved.get("subforest_size", 2),
            "n_jobs": resolved.get("n_jobs", 1),
            "random_state": seed,
            "inference": "auto",
        }
        profile_id = "econml.forest_dr.native_mean@2.0"
        estimator_factory = ForestDRLearner
    elif method_name == "double_ml":
        try:
            from econml.dml import KernelDML, LinearDML, SparseLinearDML
        except Exception:
            return _preparation_refusal(
                method_fqn, method_abi, method_profile_id, "econml_unavailable"
            )
        model_type = str(resolved.get("model_type", "linear")).lower()
        model_types: dict[str, _EstimatorFactory] = {
            "linear": LinearDML,
            "sparse": SparseLinearDML,
            "kernel": KernelDML,
        }
        estimator_factory = model_types.get(model_type)
        if estimator_factory is None:
            return _preparation_refusal(
                method_fqn, method_abi, method_profile_id, "dml_profile_invalid"
            )
        # `model_type` selects a constructor; it remains in the resolved
        # caller/owner capture but is not an EconML constructor parameter.
        config = {
            "model_y": resolved.get("model_y", "auto"),
            "model_t": resolved.get("model_t", "auto"),
            "cv": resolved.get("cv_folds", 3),
            "discrete_treatment": True,
            "use_ray": False,
        }
        if model_type == "sparse":
            config["n_jobs"] = 1
        if model_type != "kernel":
            config["random_state"] = seed
        profile_id = method_profile_id
    else:
        from polisyos.foundry.methods.catalog.causal.meta_learners import (
            _build_learner,
            _make_base_model,
            _select_base_model_name,
        )

        learner_type = str(resolved.get("learner_type", "x")).lower()
        base_model = str(resolved.get("base_model", "random_forest")).lower()
        try:
            base_model, _selection_scores = _select_base_model_name(
                data,
                learner_type=learner_type,
                primary_name=base_model,
                candidate_names=[
                    str(value) for value in resolved.get("base_model_candidates", ()) or ()
                ],
                seed=seed,
                alpha=float(resolved.get("alpha", 0.05)),
                selection_objective=str(resolved.get("selection_objective", "r_risk")),
            )
            base_estimator = _make_base_model(base_model, seed)
            estimator, method_enum, _ = _build_learner(
                learner_type,
                base_estimator,
                seed=seed,
            )
        except Exception:
            return _preparation_refusal(
                method_fqn, method_abi, method_profile_id, "meta_profile_invalid"
            )
        profile_id = method_profile_id
        config = {"learner_type": learner_type, "base_model": base_model}

        def build_meta_estimator(**_kwargs: object) -> object:
            return estimator

        estimator_factory = build_meta_estimator

    try:
        candidate_profile_id = profile_id
        model_fqn = f"causal.hte.{method_name}@{method_abi}"
        params_for_capture = dict(resolved)
        params_for_capture["__seed__"] = seed

        def fit_call() -> dict[str, Any]:
            return _method_result(
                data,
                parsed_state,
                params_for_capture,
                method_fqn=model_fqn,
                method_abi=method_abi,
                method_profile_id=candidate_profile_id,
                method_enum=method_enum,
                estimator_factory=estimator_factory,
                profile_kind=profile_kind,
                estimator_params=config,
                runtime_context=runtime_context,
            )

        return fit_call()
    except Exception:
        return _preparation_refusal(method_fqn, method_abi, profile_id, "hte_execution_failed")


def _causal_forest_profile_matches(config: Mapping[str, Any]) -> bool:
    return (
        config.get("n_estimators") == 100
        and config.get("max_depth") is None
        and config.get("min_samples_leaf") == 5
        and config.get("max_samples") == 0.5
        and config.get("honest") is True
        and config.get("cv") == 3
        and config.get("model_y") == "auto"
        and config.get("model_t") == "auto"
        and config.get("discrete_treatment") is True
        and config.get("n_jobs") == 1
        and config.get("inference") == "auto"
    )


def _forest_dr_profile_matches(config: Mapping[str, Any]) -> bool:
    return (
        config.get("model_regression") == "auto"
        and config.get("model_propensity") == "auto"
        and config.get("discrete_outcome") is False
        and config.get("min_propensity") == 0.001
        and config.get("categories") == "auto"
        and config.get("cv") == 2
        and config.get("mc_iters") == 1
        and config.get("mc_agg") == "mean"
        and config.get("n_estimators") == 32
        and config.get("max_depth") is None
        and config.get("min_samples_split") == 5
        and config.get("min_samples_leaf") == 5
        and config.get("max_samples") == 0.45
        and config.get("min_balancedness_tol") == 0.45
        and config.get("honest") is True
        and config.get("subforest_size") == 2
        and config.get("n_jobs") == 1
        and config.get("inference") == "auto"
    )


def _refusal_output(
    method_fqn: str,
    method_abi: str,
    method_profile_id: _HTEMethodProfileId,
    *,
    diagnostic_code: _HTEDiagnosticCode,
    resource_receipt: HTEProducerResourceReceiptV1,
    capture: Mapping[str, Any] | _CaptureFactsV1 | None = None,
    limitations: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Return a method-profile refusal while preserving observed scope facts."""
    if diagnostic_code == "hte_execution_failed":
        reason = "method_execution_failed"
        stage = "prepare"
        code = "hte_execution_failed"
    else:
        reason = "method_profile_unavailable"
        stage = "prepare"
        code = "resource_profile_invalid"
    refusal = HTEWriterReadyRefusalV1(
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        resource_receipt=resource_receipt,
        capture=(
            capture
            if isinstance(capture, _CaptureFactsV1)
            else _CaptureFactsV1.model_validate_json(
                json.dumps(
                    dict(capture),
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                strict=True,
            )
            if capture is not None
            else None
        ),
        limitations=tuple(dict.fromkeys((*limitations, "method_resource_profile_not_qualified"))),
        kind="refusal",
        refusal_stage=stage,
        refusal_reason=reason,
        diagnostic_code=code,
    )
    return {"hte_outcome_write_ready": refusal.model_dump(mode="json")}


def _preparation_refusal(
    method_fqn: str,
    method_abi: str,
    method_profile_id: _HTEMethodProfileId,
    diagnostic_code: _HTEDiagnosticCode,
) -> dict[str, Any]:
    """Return a nonnumeric refusal without fabricated success-path evidence."""
    if diagnostic_code == "hte_input_invalid":
        reason: Literal[
            "required_input_unavailable",
            "invalid_selected_input",
            "method_profile_unavailable",
        ] = "invalid_selected_input"
    elif diagnostic_code in {
        "econml_unavailable",
        "joblib_unavailable",
        "resource_profile_invalid",
        "dml_profile_invalid",
        "meta_profile_invalid",
    }:
        reason = "method_profile_unavailable"
    else:
        reason = "required_input_unavailable"
    refusal = HTEWriterReadyRefusalV1(
        kind="refusal",
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        resource_receipt=_not_started_resource_receipt(method_profile_id),
        limitations=("selected_input_or_method_profile_not_established",),
        refusal_stage="prepare",
        refusal_reason=reason,
        diagnostic_code=diagnostic_code,
    )
    return {"hte_outcome_write_ready": refusal.model_dump(mode="json")}


@foundry_method(namespace="causal.hte", version="2.0.0", tags={"causal", "hte", "causal-forest"})
class CausalForestEstimatorV2:
    """Causal Forest DML with explicit bounded auto-nuisance profile."""

    owned_hte_method_fqn: ClassVar[str] = "causal.hte.causal_forest@2.0.0"
    owned_hte_method_abi: ClassVar[str] = "2.0.0"
    owned_hte_profile_id: ClassVar[_HTEMethodProfileId] = "econml.causal_forest_dml.native_mean@2.0"
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    signature: ClassVar[MethodSignature] = _signature(
        "causal_forest",
        (
            *_shared_parameters(alpha=0.1),
            ParameterSpec(name="n_estimators", default=100),
            ParameterSpec(name="max_depth", default=None),
            ParameterSpec(name="min_samples_leaf", default=5),
            ParameterSpec(name="max_samples", default=0.5),
            ParameterSpec(name="honest", default=True),
            ParameterSpec(name="cv_folds", default=3),
            ParameterSpec(name="model_y", default="auto"),
            ParameterSpec(name="model_t", default="auto"),
            ParameterSpec(name="n_jobs", default=1, bounds=(1, 1)),
        ),
    )
    metadata: ClassVar[MethodMetadata] = _metadata("causal forest")

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="causal_forest",
            method_abi="2.0.0",
            method_profile_id=CausalForestEstimatorV2.owned_hte_profile_id,
            method_enum=CausalMethod.CAUSAL_FOREST,
            profile_kind="causal_forest",
        )

    @staticmethod
    def pure_step_with_runtime_context(
        state: HTEObservationalData,
        params: Mapping[str, Any],
        *,
        runtime_context: OwnedAttemptAnchorDispatchContext,
    ) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="causal_forest",
            method_abi="2.0.0",
            method_profile_id=CausalForestEstimatorV2.owned_hte_profile_id,
            method_enum=CausalMethod.CAUSAL_FOREST,
            profile_kind="causal_forest",
            runtime_context=runtime_context,
        )


@foundry_method(namespace="causal.hte", version="2.0.0", tags={"causal", "hte", "double-ml"})
class DoubleMachineLearningV2:
    """Distinct DML estimators with point-only output until profile qualification."""

    owned_hte_method_fqn: ClassVar[str] = "causal.hte.double_ml@2.0.0"
    owned_hte_method_abi: ClassVar[str] = "2.0.0"
    owned_hte_profile_id: ClassVar[_HTEMethodProfileId] = "econml.dml.point_only@2.0"
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    signature: ClassVar[MethodSignature] = _signature(
        "double_ml",
        (
            *_shared_parameters(alpha=0.05),
            ParameterSpec(name="model_type", default="linear"),
            ParameterSpec(name="model_y", default="auto"),
            ParameterSpec(name="model_t", default="auto"),
            ParameterSpec(name="cv_folds", default=3),
        ),
    )
    metadata: ClassVar[MethodMetadata] = _metadata("double machine learning")

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="double_ml",
            method_abi="2.0.0",
            method_profile_id=DoubleMachineLearningV2.owned_hte_profile_id,
            method_enum=CausalMethod.DOUBLE_ML,
            profile_kind="point_only",
        )

    @staticmethod
    def pure_step_with_runtime_context(
        state: HTEObservationalData,
        params: Mapping[str, Any],
        *,
        runtime_context: OwnedAttemptAnchorDispatchContext,
    ) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="double_ml",
            method_abi="2.0.0",
            method_profile_id=DoubleMachineLearningV2.owned_hte_profile_id,
            method_enum=CausalMethod.DOUBLE_ML,
            profile_kind="point_only",
            runtime_context=runtime_context,
        )


@foundry_method(namespace="causal.hte", version="2.0.0", tags={"causal", "hte", "meta-learner"})
class MetaLearnerEstimatorV2:
    """S/T/X candidates remain point-only because model selection uses outcomes."""

    owned_hte_method_fqn: ClassVar[str] = "causal.hte.meta_learner@2.0.0"
    owned_hte_method_abi: ClassVar[str] = "2.0.0"
    owned_hte_profile_id: ClassVar[_HTEMethodProfileId] = "econml.meta_learner.point_only@2.0"
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    signature: ClassVar[MethodSignature] = _signature(
        "meta_learner",
        (
            *_shared_parameters(alpha=0.05),
            ParameterSpec(name="learner_type", default="x"),
            ParameterSpec(name="base_model", default="random_forest"),
            ParameterSpec(name="base_model_candidates", default=()),
        ),
    )
    metadata: ClassVar[MethodMetadata] = _metadata("meta learner")

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="meta_learner",
            method_abi="2.0.0",
            method_profile_id=MetaLearnerEstimatorV2.owned_hte_profile_id,
            method_enum=CausalMethod.X_LEARNER,
            profile_kind="point_only",
        )

    @staticmethod
    def pure_step_with_runtime_context(
        state: HTEObservationalData,
        params: Mapping[str, Any],
        *,
        runtime_context: OwnedAttemptAnchorDispatchContext,
    ) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="meta_learner",
            method_abi="2.0.0",
            method_profile_id=MetaLearnerEstimatorV2.owned_hte_profile_id,
            method_enum=CausalMethod.X_LEARNER,
            profile_kind="point_only",
            runtime_context=runtime_context,
        )


@foundry_method(namespace="causal.hte", version="2.0.0", tags={"causal", "hte", "forest-dr"})
class ForestDRLearnerEstimatorV2:
    """ForestDR with explicit auto nuisance models and single-job execution."""

    owned_hte_method_fqn: ClassVar[str] = "causal.hte.forest_dr@2.0.0"
    owned_hte_method_abi: ClassVar[str] = "2.0.0"
    owned_hte_profile_id: ClassVar[_HTEMethodProfileId] = "econml.forest_dr.native_mean@2.0"
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    signature: ClassVar[MethodSignature] = _signature(
        "forest_dr",
        (
            *_shared_parameters(alpha=0.05),
            ParameterSpec(name="model_regression", default="auto"),
            ParameterSpec(name="model_propensity", default="auto"),
            ParameterSpec(name="min_propensity", default=0.001),
            ParameterSpec(name="categories", default="auto"),
            ParameterSpec(name="cv_folds", default=2),
            ParameterSpec(name="mc_iters", default=1),
            ParameterSpec(name="mc_agg", default="mean"),
            ParameterSpec(name="n_estimators", default=32),
            ParameterSpec(name="max_depth", default=None),
            ParameterSpec(name="min_samples_split", default=5),
            ParameterSpec(name="min_samples_leaf", default=5),
            ParameterSpec(name="max_samples", default=0.45),
            ParameterSpec(name="min_balancedness_tol", default=0.45),
            ParameterSpec(name="honest", default=True),
            ParameterSpec(name="subforest_size", default=2),
            ParameterSpec(name="n_jobs", default=1, bounds=(1, 1)),
        ),
    )
    metadata: ClassVar[MethodMetadata] = _metadata("ForestDR learner")

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="forest_dr",
            method_abi="2.0.0",
            method_profile_id=ForestDRLearnerEstimatorV2.owned_hte_profile_id,
            method_enum=CausalMethod.FOREST_DR,
            profile_kind="forest_dr",
        )

    @staticmethod
    def pure_step_with_runtime_context(
        state: HTEObservationalData,
        params: Mapping[str, Any],
        *,
        runtime_context: OwnedAttemptAnchorDispatchContext,
    ) -> dict[str, Any]:
        return _execute_with_profile(
            state,
            params,
            method_name="forest_dr",
            method_abi="2.0.0",
            method_profile_id=ForestDRLearnerEstimatorV2.owned_hte_profile_id,
            method_enum=CausalMethod.FOREST_DR,
            profile_kind="forest_dr",
            runtime_context=runtime_context,
        )


__all__ = [
    "CausalForestEstimatorV2",
    "DoubleMachineLearningV2",
    "ForestDRLearnerEstimatorV2",
    "HTEWriterReadyIntervalV1",
    "HTEWriterReadyPointV1",
    "HTEWriterReadyRefusalV1",
    "MetaLearnerEstimatorV2",
    "OwnedHTEInputCaptureV1",
    "build_owned_hte_input_capture",
    "validate_hte_writer_ready",
    "validate_hte_writer_ready_json",
]
