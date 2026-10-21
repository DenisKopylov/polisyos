"""Define heterogeneous treatment effect estimates and targeting recommendations."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, TypeAdapter, model_validator

from polisyos.ir._internal.validation import (
    ensure_confidence_interval,
    ensure_finite_numeric,
    ensure_unique_ids,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    ATEInferenceBasisRef,
    HTEInputSourceRef,
    HTEOutcomeRef,
    HTEPhysicalSourceMaterializationBindingRef,
    HTEPointResultRef,
    HTERefusalDiagnosticRef,
    HTEResourcePolicyRef,
    HTEResultEvidenceRef,
    HTEResultRef,
    MethodExecutionEvidenceRef,
    MethodResultEvidenceRef,
    OwnedAttemptAnchorRef,
    PolicyRecommendationRef,
    SearchUncertaintyTaskBindingRef,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal import CausalMethod
else:
    from polisyos.ir.analytics.causal import CausalMethod


class SubgroupEffect(BaseModel):
    """Estimated conditional treatment effect for one labeled subgroup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subgroup_id: str = Field(min_length=1)
    subgroup_label: str = Field(min_length=1)
    subgroup_query: str = Field(min_length=1)
    subgroup_label_human: str | None = None
    n_units: int = Field(ge=0)
    cate_mean: float
    cate_std: float = Field(ge=0.0)
    cate_ci_lower: float
    cate_ci_upper: float
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    is_significant: bool = False
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_ci(self) -> SubgroupEffect:
        ensure_finite_numeric(self.cate_mean, field_name="cate_mean")
        ensure_finite_numeric(self.cate_std, field_name="cate_std")
        ensure_confidence_interval(
            (self.cate_ci_lower, self.cate_ci_upper),
            label="cate_ci",
            point_estimate=self.cate_mean,
            point_label="cate_mean",
        )
        return self


class FeatureImportance(BaseModel):
    """Ranking signal for a feature used in heterogeneous-effect modeling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_name: str = Field(min_length=1)
    importance_score: float
    importance_rank: int = Field(ge=1)
    method: str = "tree_based"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_score(self) -> FeatureImportance:
        ensure_finite_numeric(self.importance_score, field_name="importance_score")
        return self


class HTEResult(BaseModel):
    """Canonical artifact for heterogeneous treatment effect estimation.

    The contract keeps list/dict containers for ABI compatibility, but derived
    fields are normalized before instantiation rather than by mutating the
    validated model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    method: CausalMethod
    ate: float
    ate_ci_lower: float
    ate_ci_upper: float
    ate_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)

    cate_values: list[float] = Field(default_factory=list)
    cate_std_values: list[float] = Field(default_factory=list)
    cate_ci_lower_values: list[float] = Field(default_factory=list)
    cate_ci_upper_values: list[float] = Field(default_factory=list)

    subgroup_effects: list[SubgroupEffect] = Field(default_factory=list)
    feature_importances: list[FeatureImportance] = Field(default_factory=list)

    n_samples: int = Field(default=0, ge=0)
    n_treated: int = Field(default=0, ge=0)
    n_control: int = Field(default=0, ge=0)
    n_features: int = Field(default=0, ge=0)
    feature_names: list[str] = Field(default_factory=list)

    econml_estimator_class: str = ""
    econml_params: dict[str, Any] = Field(default_factory=dict)
    model_fit_metrics: dict[str, float] = Field(default_factory=dict)

    feature_display_map: dict[str, str] = Field(default_factory=dict)
    feature_transformations: dict[str, str] = Field(default_factory=dict)

    causal_effect_report_ref: str | None = None
    cas_artifact_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, payload: Any) -> Any:
        return cls.normalize_payload(payload)

    @classmethod
    def normalize_payload(cls, payload: Any) -> Any:
        """Return an HTE payload with explicit derived defaults filled.

        This helper is the supported normalization boundary for loaded legacy
        payloads and construction helpers. Validators call it only to preserve
        dual-read compatibility; business code should prefer
        :meth:`from_estimates` when deriving fields such as ``n_samples``.
        """
        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        cate_values = normalized.get("cate_values")
        if (
            isinstance(cate_values, Sequence)
            and not isinstance(cate_values, (str, bytes, bytearray))
            and normalized.get("n_samples", 0) in {None, 0, ""}
        ):
            normalized["n_samples"] = len(cate_values)
        return normalized

    @classmethod
    def from_estimates(cls, **payload: Any) -> HTEResult:
        """Construct an HTE result after applying explicit derived defaults."""

        return cls.model_validate(cls.normalize_payload(payload))

    @model_validator(mode="after")
    def _validate_shapes(self) -> HTEResult:
        if self.n_samples != len(self.cate_values):
            raise ValueError("n_samples must match cate_values length")
        ensure_finite_numeric(self.ate, field_name="ate")
        ensure_confidence_interval(
            (self.ate_ci_lower, self.ate_ci_upper),
            label="ate_ci",
            point_estimate=self.ate,
            point_label="ate",
        )
        for index, cate in enumerate(self.cate_values):
            ensure_finite_numeric(cate, field_name=f"cate_values[{index}]")
        if self.cate_std_values and len(self.cate_std_values) != self.n_samples:
            raise ValueError("cate_std_values length must match n_samples")
        if self.cate_ci_lower_values and len(self.cate_ci_lower_values) != self.n_samples:
            raise ValueError("cate_ci_lower_values length must match n_samples")
        if self.cate_ci_upper_values and len(self.cate_ci_upper_values) != self.n_samples:
            raise ValueError("cate_ci_upper_values length must match n_samples")
        if bool(self.cate_ci_lower_values) != bool(self.cate_ci_upper_values):
            raise ValueError(
                "cate_ci_lower_values and cate_ci_upper_values must be provided together"
            )
        for index, cate_std in enumerate(self.cate_std_values):
            ensure_finite_numeric(cate_std, field_name=f"cate_std_values[{index}]")
        for index, (lower, upper) in enumerate(
            zip(self.cate_ci_lower_values, self.cate_ci_upper_values, strict=False)
        ):
            ensure_confidence_interval(
                (lower, upper),
                label=f"cate_ci[{index}]",
                point_estimate=self.cate_values[index],
                point_label=f"cate_values[{index}]",
            )
        if self.n_treated + self.n_control > self.n_samples:
            raise ValueError("n_treated + n_control cannot exceed n_samples")
        if self.feature_names and len(self.feature_names) != self.n_features:
            raise ValueError("feature_names length must match n_features")
        if not self.feature_names and self.n_features != 0:
            raise ValueError("n_features requires feature_names")
        ensure_unique_ids(self.feature_names, key_fn=lambda item: item, label="feature_name")
        ensure_unique_ids(
            self.subgroup_effects,
            key_fn=lambda item: item.subgroup_id,
            label="subgroup_effect subgroup_id",
        )
        ensure_unique_ids(
            self.feature_importances,
            key_fn=lambda item: item.feature_name,
            label="feature_importance feature_name",
        )
        ensure_unique_ids(
            self.feature_importances,
            key_fn=lambda item: item.importance_rank,
            label="feature_importance importance_rank",
        )
        for metric_name, metric_value in self.model_fit_metrics.items():
            ensure_finite_numeric(metric_value, field_name=f"model_fit_metrics.{metric_name}")
        return self


class _ProfiledArtifactRef(ArtifactRefModel):
    """Require the exact manifest profile selected by the producing write."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    manifest_profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


_HTE_V2_METHOD_PROFILES: dict[str, str] = {
    "causal.hte.causal_forest@2.0.0": "econml.causal_forest_dml.native_mean@2.0",
    "causal.hte.double_ml@2.0.0": "econml.dml.point_only@2.0",
    "causal.hte.meta_learner@2.0.0": "econml.meta_learner.point_only@2.0",
    "causal.hte.forest_dr@2.0.0": "econml.forest_dr.native_mean@2.0",
}


@dataclass(frozen=True, slots=True)
class _NativeInferenceProfileV1:
    """One admitted source-bound EconML estimator and mean-inference route."""

    method_fqn: str
    method_profile_id: str
    econml_version: str
    econml_source_profile_sha256: str
    estimator_class: str
    inference_class: str
    ate_inference_method: str
    conf_int_mean_method: str
    native_result_class: str
    inference_route: str


_NATIVE_INFERENCE_PROFILES_V1 = (
    _NativeInferenceProfileV1(
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_profile_id="econml.causal_forest_dml.native_mean@2.0",
        econml_version="0.17.0",
        econml_source_profile_sha256=(
            "27b24c985f552585d38a3cd163301feb0f3755bf1e39c32c3abdbb1b865dba56"
        ),
        estimator_class="econml.dml.causal_forest.CausalForestDML",
        inference_class=(
            "econml.dml.causal_forest._GenericSingleOutcomeModelFinalWithCovInference"
        ),
        ate_inference_method="econml._cate_estimator.TreatmentExpansionMixin.ate_inference",
        conf_int_mean_method="econml.inference._inference.PopulationSummaryResults.conf_int_mean",
        native_result_class="econml.inference._inference.PopulationSummaryResults",
        inference_route="ate_inference.conf_int_mean",
    ),
    _NativeInferenceProfileV1(
        method_fqn="causal.hte.forest_dr@2.0.0",
        method_profile_id="econml.forest_dr.native_mean@2.0",
        econml_version="0.17.0",
        econml_source_profile_sha256=(
            "27b24c985f552585d38a3cd163301feb0f3755bf1e39c32c3abdbb1b865dba56"
        ),
        estimator_class="econml.dr._drlearner.ForestDRLearner",
        inference_class="econml.inference._inference.GenericModelFinalInferenceDiscrete",
        ate_inference_method="econml._cate_estimator.TreatmentExpansionMixin.ate_inference",
        conf_int_mean_method="econml.inference._inference.PopulationSummaryResults.conf_int_mean",
        native_result_class="econml.inference._inference.PopulationSummaryResults",
        inference_route="ate_inference.conf_int_mean",
    ),
)


def _native_inference_profile_v1(
    method_fqn: str,
    method_abi: str,
    method_profile_id: str,
) -> _NativeInferenceProfileV1:
    """Resolve the complete identity tuple for an admitted native mean route.

    This shared IR-owned mapping is used by the Foundry producer and by strict
    persisted-basis validation. Installed-package byte verification remains a
    producer responsibility; this function checks the identity carried across
    the artifact boundary.
    """
    if method_abi != "2.0.0":
        raise ValueError("native_inference_profile_identity_mismatch")
    for profile in _NATIVE_INFERENCE_PROFILES_V1:
        if profile.method_fqn == method_fqn and profile.method_profile_id == method_profile_id:
            return profile
    raise ValueError("native_inference_profile_identity_mismatch")


def _native_inference_profile_for_method_profile_v1(
    method_profile_id: str,
) -> _NativeInferenceProfileV1:
    """Resolve a unique native profile by its owner-selected method profile."""
    for profile in _NATIVE_INFERENCE_PROFILES_V1:
        if profile.method_profile_id == method_profile_id:
            return profile
    raise ValueError("native_inference_profile_identity_mismatch")


def _validate_native_inference_profile_identity_v1(
    *,
    method_fqn: str,
    method_abi: str,
    method_profile_id: str,
    econml_version: str,
    estimator_class: str,
    inference_class: str,
    econml_source_profile_sha256: str,
    ate_inference_method: str,
    conf_int_mean_method: str,
    native_result_class: str,
    inference_route: str,
) -> _NativeInferenceProfileV1:
    """Reject any artifact or producer capture that mixes profile identities."""
    profile = _native_inference_profile_v1(method_fqn, method_abi, method_profile_id)
    observed = (
        econml_version,
        estimator_class,
        inference_class,
        econml_source_profile_sha256,
        ate_inference_method,
        conf_int_mean_method,
        native_result_class,
        inference_route,
    )
    expected = (
        profile.econml_version,
        profile.estimator_class,
        profile.inference_class,
        profile.econml_source_profile_sha256,
        profile.ate_inference_method,
        profile.conf_int_mean_method,
        profile.native_result_class,
        profile.inference_route,
    )
    if observed != expected:
        raise ValueError("native_inference_profile_identity_mismatch")
    return profile


def _validate_hte_v2_method_profile(
    method_fqn: str,
    method_abi: str,
    method_profile_id: str,
) -> None:
    """Reject legacy or cross-profile identities on successor HTE artifacts."""
    if method_abi != "2.0.0" or _HTE_V2_METHOD_PROFILES.get(method_fqn) != method_profile_id:
        raise ValueError("hte_method_identity_profile_mismatch")


class HTEPointEstimate(BaseModel):
    """Finite point estimate with explicit target and measurement-unit limits."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    value: float
    estimand: Literal["mean_effect_over_selected_x"] = "mean_effect_over_selected_x"
    computed_target_scope_status: Literal["recomputed"] = "recomputed"
    computed_target_scope: Literal["selected_evaluation_rows"] = "selected_evaluation_rows"
    measure_unit_status: Literal["established", "not_established"]
    measure_unit: str | None

    @model_validator(mode="after")
    def _validate_point(self) -> HTEPointEstimate:
        ensure_finite_numeric(self.value, field_name="value")
        if (self.measure_unit_status == "established") != (self.measure_unit is not None):
            raise ValueError("measure_unit must match measure_unit_status")
        if self.measure_unit is not None and not self.measure_unit.strip():
            raise ValueError("an established measure unit must be non-empty")
        return self


class HTETargetRelationV1(BaseModel):
    """Keep the requested target separate from the computed row frame and guarantee."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    requested_scope_status: Literal["declared", "not_established"]
    requested_scope: str | None = Field(default=None, min_length=1)
    requested_guarantee_status: Literal["declared", "not_established"]
    requested_guarantee: (
        Literal[
            "candidate_point",
            "backend_conditional_interval",
            "population_sampling_coverage",
        ]
        | None
    )
    computed_scope_status: Literal["recomputed", "not_established"]
    computed_scope: Literal["selected_evaluation_rows"] | None
    computed_guarantee_status: Literal["computed", "not_established"]
    computed_guarantee: Literal["candidate_point", "backend_conditional_interval"] | None
    source_content_status: Literal["content_bound", "not_established"]
    row_order_status: Literal["recomputed", "not_established"]
    contrast_status: Literal["recomputed", "not_established"]
    # HTEObservationalData has no typed mapping from requested variable IDs to
    # its Y/T arrays. A serialized status cannot establish that missing join.
    estimand_status: Literal["not_established"] = "not_established"
    alpha_status: Literal["recomputed", "not_applicable", "not_established"]
    profile_status: Literal["qualified", "point_only", "not_established"]
    scope_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]
    guarantee_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]
    overall_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]

    @model_validator(mode="after")
    def _validate_relation(self) -> HTETargetRelationV1:
        if (self.requested_scope_status == "declared") != (self.requested_scope is not None):
            raise ValueError("requested scope must match its explicit status")
        if (self.computed_scope_status == "recomputed") != (
            self.computed_scope == "selected_evaluation_rows"
        ):
            raise ValueError("computed scope must match its recomputed status")
        if (self.requested_guarantee_status == "declared") != (
            self.requested_guarantee is not None
        ):
            raise ValueError("requested guarantee must match its explicit status")
        if (self.computed_guarantee_status == "computed") != (self.computed_guarantee is not None):
            raise ValueError("computed guarantee must match its explicit status")
        scope_frame_known = (
            self.requested_scope_status == "declared" and self.computed_scope_status == "recomputed"
        )
        if not scope_frame_known:
            expected_scope = "not_established"
        elif self.requested_scope == "population":
            # The producer computes over the selected rows, which is a known
            # narrower frame than a population request. Preserve this known
            # mismatch even when source-variable identity or row-order binding
            # remains unknown; those predicates only limit positive admission.
            expected_scope = "requested_claim_not_satisfied"
        elif (
            self.requested_scope == self.computed_scope
            and self.source_content_status == "content_bound"
            and self.row_order_status == "recomputed"
        ):
            expected_scope = "satisfied"
        else:
            # Matching or arbitrary labels cannot satisfy a scope without a
            # bound source and recomputed row order.
            expected_scope = "not_established"

        guarantee_predicates_bound = (
            self.requested_guarantee_status == "declared"
            and self.computed_guarantee_status == "computed"
        )
        if not guarantee_predicates_bound:
            expected_guarantee = "not_established"
        elif self.requested_guarantee == self.computed_guarantee:
            expected_guarantee = "satisfied"
        else:
            expected_guarantee = "requested_claim_not_satisfied"

        semantic_basis_bound = self.contrast_status == "recomputed"
        expected_overall = (
            "requested_claim_not_satisfied"
            if "requested_claim_not_satisfied" in {expected_scope, expected_guarantee}
            else "not_established"
            if not semantic_basis_bound
            or self.estimand_status != "recomputed"
            or "not_established" in {expected_scope, expected_guarantee}
            else "satisfied"
        )
        if (
            self.scope_disposition != expected_scope
            or self.guarantee_disposition != expected_guarantee
            or self.overall_disposition != expected_overall
        ):
            raise ValueError(
                "target relation dispositions must be recomputed from bound predicates"
            )
        return self


class HTEResourceExecutionEvidenceV1(BaseModel):
    """Bind the selected Runtime policy to its method-specific observed scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    owner_policy_ref: HTEResourcePolicyRef
    owner_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    owner_policy_schema_version: Literal["polisyos.runtime.observational_input_resource_policy.v5"]
    owner_policy_revision: Literal["r5"]
    owner_policy_method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    owner_policy_method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    owner_policy_execution_scope: Literal["producer_scoped_joblib_parallelism_one"]
    owner_policy_max_jobs: Literal[1]
    owner_policy_required_estimator_n_jobs: Literal[1] | None
    owner_policy_manifest_schema_version: Literal["1.0"] = "1.0"
    execution_status: Literal["not_started", "returned", "raised"]
    estimator_observation_status: Literal["recomputed", "not_applicable", "not_established"]
    estimator_before_class_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    estimator_before_n_jobs: int | None = Field(default=None, strict=True)
    estimator_before_params_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    estimator_after_class_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    estimator_after_n_jobs: int | None = Field(default=None, strict=True)
    estimator_after_params_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    joblib_observation_status: Literal["recomputed", "not_applicable", "not_established"]
    joblib_started: bool
    joblib_finished: bool
    joblib_exit_status: Literal["not_started", "returned", "raised"]
    joblib_profile_id: Literal["joblib.parallel_config.current_thread@1.0"] | None
    joblib_profile_revision: Literal["1.0"] | None
    joblib_implementation: Literal["joblib.parallel_config"] | None
    joblib_implementation_version: str | None = Field(default=None, min_length=1, max_length=96)
    joblib_scope: Literal["current_thread_joblib"] | None
    joblib_max_jobs: Literal[1] | None
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
    physical_thread_limit_status: Literal["not_established"] = "not_established"
    physical_thread_limit: None = None

    @model_validator(mode="after")
    def _validate_resource_evidence(self) -> HTEResourceExecutionEvidenceV1:
        if (
            self.owner_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.owner_policy_ref.media_type != "application/json"
            or self.owner_policy_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("owner resource policy ref is not profile selected")
        expected_policy = {
            "causal.hte.causal_forest@2.0.0": (
                "econml.causal_forest_dml.native_mean@2.0",
                1,
            ),
            "causal.hte.double_ml@2.0.0": ("econml.dml.point_only@2.0", None),
            "causal.hte.meta_learner@2.0.0": ("econml.meta_learner.point_only@2.0", None),
            "causal.hte.forest_dr@2.0.0": ("econml.forest_dr.native_mean@2.0", 1),
        }[self.owner_policy_method_fqn]
        if (
            self.owner_policy_schema_version
            != "polisyos.runtime.observational_input_resource_policy.v5"
            or self.owner_policy_revision != "r5"
            or self.owner_policy_method_profile_id != expected_policy[0]
            or self.owner_policy_execution_scope != "producer_scoped_joblib_parallelism_one"
            or self.owner_policy_required_estimator_n_jobs != expected_policy[1]
            or self.owner_policy_max_jobs != 1
        ):
            raise ValueError("owner resource policy method tuple mismatch")

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
        estimator_required = self.owner_policy_required_estimator_n_jobs == 1
        if not estimator_required and (
            self.estimator_observation_status != "not_applicable"
            or any(value is not None for value in estimator_fields)
        ):
            raise ValueError("joblib-only method cannot carry estimator observations")
        if self.execution_status == "not_started":
            if (
                self.joblib_observation_status != "not_established"
                or self.joblib_started
                or self.joblib_finished
                or self.joblib_exit_status != "not_started"
                or any(value is not None for value in joblib_fields)
            ):
                raise ValueError("unstarted joblib policy cannot carry observations")
            if estimator_required and (
                self.estimator_observation_status != "not_established"
                or any(value is not None for value in estimator_fields)
            ):
                raise ValueError("unstarted estimator cannot carry observations")
            return self
        if (
            self.joblib_observation_status != "recomputed"
            or not self.joblib_started
            or not self.joblib_finished
            or self.joblib_exit_status != self.execution_status
            or any(value is None for value in joblib_fields)
            or self.joblib_profile_id != "joblib.parallel_config.current_thread@1.0"
            or self.joblib_profile_revision != "1.0"
            or self.joblib_implementation != "joblib.parallel_config"
            or self.joblib_scope != "current_thread_joblib"
            or self.joblib_max_jobs != 1
            or self.joblib_implementation_version != self.joblib_entry_implementation_version
        ):
            raise ValueError("joblib entry and exit evidence must be complete and source-bound")
        # Keep the raw observed receipt lossless for typed refusals. Numeric
        # artifacts independently require the selected one-job profile in
        # _require_numeric_hte_resource_evidence.
        if estimator_required:
            estimator_complete = all(value is not None for value in estimator_fields)
            if self.execution_status == "returned":
                if self.estimator_observation_status == "not_established":
                    if estimator_complete or any(value is not None for value in estimator_fields):
                        raise ValueError(
                            "unestablished returned estimator observation must be empty"
                        )
                elif self.estimator_observation_status != "recomputed" or not estimator_complete:
                    raise ValueError("returned estimator observation must be complete or unknown")
            if self.execution_status == "raised":
                if self.estimator_observation_status == "recomputed":
                    if not estimator_complete:
                        raise ValueError("raised estimator observation must be complete")
                elif self.estimator_observation_status != "not_established" or any(
                    value is not None for value in estimator_fields
                ):
                    raise ValueError("raised estimator observations must be complete or unknown")
        return self


def _require_numeric_hte_resource_evidence(
    evidence: HTEResourceExecutionEvidenceV1,
) -> None:
    """Require the complete selected resource profile before emitting numbers.

    A typed refusal may truthfully retain a returned joblib lifecycle while no
    estimator was constructed. Numeric artifacts have a higher bar: the
    observed joblib context must remain one-job and any estimator cap required
    by the selected owner policy must be recomputed before and after execution.
    """
    if (
        evidence.execution_status != "returned"
        or evidence.joblib_observation_status != "recomputed"
        or evidence.joblib_entry_effective_jobs != 1
        or evidence.joblib_exit_effective_jobs != 1
        or evidence.joblib_entry_backend_fqn != evidence.joblib_exit_backend_fqn
        or evidence.joblib_entry_config_sha256 != evidence.joblib_exit_config_sha256
        or evidence.joblib_entry_implementation_version
        != evidence.joblib_exit_implementation_version
    ):
        raise ValueError("numeric_hte_result_requires_returned_one_job_profile")
    if evidence.owner_policy_required_estimator_n_jobs == 1 and (
        evidence.estimator_observation_status != "recomputed"
        or evidence.estimator_before_class_fqn is None
        or evidence.estimator_after_class_fqn is None
        or evidence.estimator_before_n_jobs != 1
        or evidence.estimator_after_n_jobs != 1
        or evidence.estimator_before_class_fqn != evidence.estimator_after_class_fqn
        or evidence.estimator_before_params_sha256 is None
        or evidence.estimator_before_params_sha256 != evidence.estimator_after_params_sha256
    ):
        raise ValueError("numeric_hte_result_requires_stable_n_jobs_one_estimator")
    if evidence.owner_policy_method_profile_id in {
        profile.method_profile_id for profile in _NATIVE_INFERENCE_PROFILES_V1
    }:
        profile = _native_inference_profile_v1(
            evidence.owner_policy_method_fqn,
            "2.0.0",
            evidence.owner_policy_method_profile_id,
        )
        if (
            evidence.estimator_before_class_fqn != profile.estimator_class
            or evidence.estimator_after_class_fqn != profile.estimator_class
        ):
            raise ValueError("native_hte_resource_estimator_profile_mismatch")


class HTEPointResult(BaseModel):
    """Persist the selected per-row HTE point vector without interval semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_abi: Literal["2.0.0"]
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    resolved_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_data_ref: HTEInputSourceRef
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef
    source_data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"]
    selected_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    n_selected_rows: int = Field(gt=0)
    point_estimate: float
    cate_values: tuple[float, ...] = Field(min_length=1)
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef
    method_result_ref: MethodResultEvidenceRef
    method_evidence_ref: MethodExecutionEvidenceRef
    resource_evidence: HTEResourceExecutionEvidenceV1

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_point_result(self) -> HTEPointResult:
        _validate_hte_v2_method_profile(self.method_fqn, self.method_abi, self.method_profile_id)
        for name, value in (("point_estimate", self.point_estimate),):
            ensure_finite_numeric(value, field_name=name)
        if len(self.cate_values) != self.n_selected_rows:
            raise ValueError("HTE point result vector must match selected row count")
        for index, value in enumerate(self.cate_values):
            ensure_finite_numeric(value, field_name=f"cate_values[{index}]")
        if not math.isclose(
            self.point_estimate,
            math.fsum(self.cate_values) / self.n_selected_rows,
            rel_tol=1.0e-10,
            abs_tol=1.0e-12,
        ):
            raise ValueError("HTE point result must equal the selected-row vector mean")
        if self.selected_input_sha256 != self.source_data_sha256:
            raise ValueError("point result source and selected-input digests differ")
        _require_numeric_hte_resource_evidence(self.resource_evidence)
        return self


class ATEInferenceBasis(BaseModel):
    """Native EconML mean-inference record, conditional on its declared profile."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    inference_profile_id: Literal["econml_native_mean_over_selected_x@1.0"]
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_abi: Literal["2.0.0"]
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    estimator_class: str = Field(min_length=1)
    inference_class: str = Field(min_length=1)
    econml_version: str = Field(min_length=1)
    econml_source_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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
    resolved_params: dict[str, Any]
    seed: int
    fit_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eval_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fit_eval_relation: Literal["same_selected_rows"]
    sample_ids_status: Literal["provided", "not_established"]
    sample_ids_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
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
    selected_x_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    native_pred_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    native_pred_stderr_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    n_selected_rows: int = Field(gt=0)
    contrast_status: Literal["established", "not_established"]
    control_value: float | None
    treated_value: float | None
    request_estimand_status: Literal["declared", "not_established"]
    request_estimand: str | None = Field(default=None, min_length=1)
    request_target_scope_status: Literal["declared", "not_established"]
    request_target_scope: str | None = Field(default=None, min_length=1)
    outcome_variable_status: Literal["declared", "not_established"]
    outcome_variable_id: str | None = Field(default=None, min_length=1)
    treatment_variable_status: Literal["declared", "not_established"]
    treatment_variable_id: str | None = Field(default=None, min_length=1)
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
    computed_target_scope_status: Literal["recomputed"] = "recomputed"
    computed_target_scope: Literal["selected_evaluation_rows"] = "selected_evaluation_rows"
    target_relation: HTETargetRelationV1
    conditional_assumptions: tuple[str, ...] = Field(min_length=1)
    source_data_ref: HTEInputSourceRef
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef
    invocation_basis_ref: ArtifactRefModel | None
    invocation_basis_status: Literal["established", "not_established"]
    invocation_basis_reason: (
        Literal[
            "owner_selected_invocation_basis",
            "no_invocation_basis_artifact_contract",
        ]
        | None
    )
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef
    resource_evidence: HTEResourceExecutionEvidenceV1
    native_result_disposition: Literal[
        "legacy_hte_result_admitted", "legacy_hte_result_unrepresentable"
    ]
    native_result_disposition_reason: (
        Literal["point_not_contained_in_legacy_interval", "native_bounds_unordered"] | None
    ) = None
    hte_result_ref: HTEResultEvidenceRef | None = None
    point_result_ref: HTEPointResultRef | None = None
    method_result_ref: MethodResultEvidenceRef
    method_evidence_ref: MethodExecutionEvidenceRef

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_basis(self) -> ATEInferenceBasis:
        _validate_hte_v2_method_profile(self.method_fqn, self.method_abi, self.method_profile_id)
        native_profile = _validate_native_inference_profile_identity_v1(
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
        resolved_params_bytes = json.dumps(
            {"params": self.resolved_params, "seed": self.seed},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if hashlib.sha256(resolved_params_bytes).hexdigest() != self.resolved_params_sha256:
            raise ValueError("resolved_params_sha256 does not match canonical request params")
        estimator_params_bytes = json.dumps(
            self.estimator_params,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if hashlib.sha256(estimator_params_bytes).hexdigest() != self.estimator_params_sha256:
            raise ValueError("estimator_params_sha256 does not match canonical estimator config")
        if (self.sample_ids_status == "provided") != (self.sample_ids_sha256 is not None):
            raise ValueError("sample ids digest must match sample_ids_status")
        if self.fit_rows_sha256 != self.eval_rows_sha256:
            raise ValueError("this native profile requires identical fit and evaluation rows")
        if (
            self.resource_evidence.owner_policy_method_fqn != native_profile.method_fqn
            or self.resource_evidence.owner_policy_method_profile_id
            != native_profile.method_profile_id
            or self.resource_evidence.estimator_before_class_fqn != native_profile.estimator_class
            or self.resource_evidence.estimator_after_class_fqn != native_profile.estimator_class
        ):
            raise ValueError("native basis estimator does not match the selected resource profile")
        for name in (
            "native_point",
            "native_lower_bound",
            "native_upper_bound",
            "native_mean_pred",
            "standard_error_value",
        ):
            ensure_finite_numeric(getattr(self, name), field_name=name)
        if self.native_mean_pred_stderr is not None:
            ensure_finite_numeric(
                self.native_mean_pred_stderr, field_name="native_mean_pred_stderr"
            )
            if self.native_mean_pred_stderr < 0.0:
                raise ValueError("native_mean_pred_stderr must be nonnegative")
        if self.native_stderr_mean is not None:
            ensure_finite_numeric(self.native_stderr_mean, field_name="native_stderr_mean")
            if self.native_stderr_mean < 0.0:
                raise ValueError("native_stderr_mean must be nonnegative")
        for index, value in enumerate(self.native_pred_stderr_values):
            ensure_finite_numeric(value, field_name=f"native_pred_stderr_values[{index}]")
            if value < 0.0:
                raise ValueError("native prediction standard errors must be nonnegative")
        if len(self.native_pred_stderr_values) != self.n_selected_rows:
            raise ValueError("native prediction standard errors must match selected row count")
        canonical_native_stderr = json.dumps(
            list(self.native_pred_stderr_values),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if hashlib.sha256(canonical_native_stderr).hexdigest() != self.native_pred_stderr_sha256:
            raise ValueError("native_pred_stderr_sha256 does not match captured standard errors")
        if self.native_result_disposition == "legacy_hte_result_admitted":
            if (
                self.hte_result_ref is None
                or self.point_result_ref is not None
                or self.native_result_disposition_reason is not None
                or self.native_lower_bound > self.native_upper_bound
                or not self.native_lower_bound <= self.native_point <= self.native_upper_bound
            ):
                raise ValueError("admitted_native_interval_requires_containing_hte_result_v1")
        elif (
            self.hte_result_ref is not None
            or self.point_result_ref is None
            or self.native_lower_bound <= self.native_point <= self.native_upper_bound
            or self.native_result_disposition_reason
            != (
                "native_bounds_unordered"
                if self.native_lower_bound > self.native_upper_bound
                else "point_not_contained_in_legacy_interval"
            )
        ):
            raise ValueError("unrepresentable_native_interval_requires_point_only_diagnostic")
        if not math.isclose(
            self.confidence_level,
            1.0 - self.alpha,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("confidence_level must equal 1 - alpha")
        if (
            self.request_alpha_status != "declared"
            or self.requested_alpha is None
            or not math.isclose(self.alpha, self.requested_alpha, rel_tol=0.0, abs_tol=1.0e-12)
        ):
            raise ValueError("native alpha must match the owner-declared request alpha")
        resolved_alpha = self.resolved_params.get("alpha")
        if (
            isinstance(resolved_alpha, bool)
            or not isinstance(resolved_alpha, (int, float))
            or not math.isclose(
                self.alpha,
                float(resolved_alpha),
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
        ):
            raise ValueError("native alpha must match resolved method parameters")
        if self.target_relation.computed_scope != self.computed_target_scope:
            raise ValueError("basis target relation must bind the computed row frame")
        if (
            self.target_relation.requested_scope_status != self.request_target_scope_status
            or self.target_relation.requested_scope != self.request_target_scope
            or self.target_relation.requested_guarantee_status != self.requested_guarantee_status
            or self.target_relation.requested_guarantee != self.requested_guarantee
            or self.target_relation.computed_guarantee_status != "computed"
            or self.target_relation.computed_guarantee
            != (
                "backend_conditional_interval"
                if self.native_result_disposition == "legacy_hte_result_admitted"
                else "candidate_point"
            )
            or self.target_relation.source_content_status != "content_bound"
            or self.target_relation.row_order_status != "recomputed"
            or self.target_relation.contrast_status != "recomputed"
            or self.target_relation.alpha_status != "recomputed"
            or self.target_relation.profile_status != "qualified"
        ):
            raise ValueError("basis target relation must preserve requested and computed claims")
        if self.contrast_status == "established":
            if self.control_value is None or self.treated_value is None:
                raise ValueError("established contrast requires both values")
            ensure_finite_numeric(self.control_value, field_name="control_value")
            ensure_finite_numeric(self.treated_value, field_name="treated_value")
            if self.control_value == self.treated_value:
                raise ValueError("established contrast values must differ")
        elif self.control_value is not None or self.treated_value is not None:
            raise ValueError("unestablished contrast cannot carry assumed values")
        request_pairs = (
            (self.request_estimand_status, self.request_estimand),
            (self.request_target_scope_status, self.request_target_scope),
            (self.outcome_variable_status, self.outcome_variable_id),
            (self.treatment_variable_status, self.treatment_variable_id),
            (self.request_alpha_status, self.requested_alpha),
            (self.requested_guarantee_status, self.requested_guarantee),
        )
        if any((status == "declared") != (value is not None) for status, value in request_pairs):
            raise ValueError("request values must match their declaration status")
        if (self.invocation_basis_ref is None) != (
            self.invocation_basis_status == "not_established"
        ):
            raise ValueError("invocation basis ref must match its status")
        if (self.invocation_basis_ref is None) != (self.invocation_basis_reason is not None):
            raise ValueError("missing invocation basis requires an explicit reason")
        if self.invocation_basis_ref is not None and self.invocation_basis_reason is not None:
            raise ValueError("established invocation basis cannot carry a missing reason")
        if self.resource_evidence.execution_status != "returned":
            raise ValueError("native inference requires the observed one-job resource profile")
        if self.standard_error_source == "mean_pred_stderr":
            if self.native_mean_pred_stderr is None:
                raise ValueError("mean_pred_stderr source requires native mean_pred_stderr")
            if not math.isclose(
                self.standard_error_value,
                self.native_mean_pred_stderr,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ValueError("standard_error_value must preserve native mean_pred_stderr")
        else:
            rms = math.sqrt(
                math.fsum(value * value for value in self.native_pred_stderr_values)
                / self.n_selected_rows
            )
            if self.native_mean_pred_stderr is not None:
                raise ValueError("RMS standard error route requires absent mean_pred_stderr")
            if self.native_stderr_mean is None:
                raise ValueError("RMS route requires the backend native stderr_mean")
            if not math.isclose(
                self.native_stderr_mean,
                rms,
                rel_tol=1.0e-10,
                abs_tol=1.0e-12,
            ):
                raise ValueError("native stderr_mean must equal RMS of captured prediction SEs")
            if not math.isclose(
                self.standard_error_value,
                rms,
                rel_tol=1.0e-10,
                abs_tol=1.0e-12,
            ):
                raise ValueError("standard_error_value must equal recomputed native RMS")
        return self


class HTERefusalDiagnostic(BaseModel):
    """Persist the typed refusal returned by one owned HTE method execution.

    The diagnostic binds the selected attempt and its actual method result and
    execution-evidence artifacts. It does not carry a point, interval, or
    fabricated successful-fit vector.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    diagnostic_origin: Literal["method_execution"] = "method_execution"
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_abi: Literal["2.0.0"]
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
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
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef
    method_result_ref: MethodResultEvidenceRef
    method_evidence_ref: MethodExecutionEvidenceRef
    resource_evidence: HTEResourceExecutionEvidenceV1 | None
    selected_rows_status: Literal["recomputed", "not_established"]
    n_selected_rows: int | None = Field(default=None, ge=0, strict=True)
    selected_input_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    limitations: tuple[str, ...] = Field(min_length=1)

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_refusal_diagnostic(self) -> HTERefusalDiagnostic:
        _validate_hte_v2_method_profile(self.method_fqn, self.method_abi, self.method_profile_id)
        row_fields = (
            self.n_selected_rows,
            self.selected_input_sha256,
            self.selected_rows_sha256,
            self.selected_x_sha256,
            self.selected_row_order_sha256,
        )
        if (self.selected_rows_status == "recomputed") != all(
            value is not None for value in row_fields
        ):
            raise ValueError("refusal diagnostic row fields must match their evidence status")
        if self.selected_rows_status == "not_established" and any(
            value is not None for value in row_fields
        ):
            raise ValueError("unestablished refusal rows cannot carry selected-input hashes")
        if self.resource_evidence is not None and (
            self.resource_evidence.owner_policy_method_fqn != self.method_fqn
            or self.resource_evidence.owner_policy_method_profile_id != self.method_profile_id
        ):
            raise ValueError("refusal diagnostic resource evidence does not match its method")
        return self


class _HTEOutcomeBase(BaseModel):
    """Successful point-bearing outcomes with complete selected-input evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    authority_status: Literal["candidate"] = "candidate"
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_abi: Literal["2.0.0"]
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"]
    selected_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolved_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    n_selected_rows: int = Field(gt=0)
    source_data_ref: HTEInputSourceRef
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef
    invocation_basis_ref: ArtifactRefModel | None
    invocation_basis_status: Literal["established", "not_established"]
    invocation_basis_reason: (
        Literal[
            "owner_selected_invocation_basis",
            "no_invocation_basis_artifact_contract",
        ]
        | None
    )
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef
    resource_evidence: HTEResourceExecutionEvidenceV1
    method_result_ref: MethodResultEvidenceRef
    method_evidence_ref: MethodExecutionEvidenceRef
    request_estimand_status: Literal["declared", "not_established"]
    request_estimand: str | None = Field(default=None, min_length=1)
    request_target_scope_status: Literal["declared", "not_established"]
    request_target_scope: str | None = Field(default=None, min_length=1)
    outcome_variable_status: Literal["declared", "not_established"]
    outcome_variable_id: str | None = Field(default=None, min_length=1)
    treatment_variable_status: Literal["declared", "not_established"]
    treatment_variable_id: str | None = Field(default=None, min_length=1)
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
    contrast_status: Literal["established", "not_established"]
    control_value: float | None
    treated_value: float | None
    target_relation: HTETargetRelationV1
    limitations: tuple[str, ...] = Field(min_length=1)

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_common(self) -> _HTEOutcomeBase:
        _validate_hte_v2_method_profile(self.method_fqn, self.method_abi, self.method_profile_id)
        if (self.invocation_basis_ref is None) != (
            self.invocation_basis_status == "not_established"
        ):
            raise ValueError("invocation basis ref must match its status")
        if (self.invocation_basis_ref is None) != (self.invocation_basis_reason is not None):
            raise ValueError("missing invocation basis requires an explicit reason")
        if self.invocation_basis_ref is not None and self.invocation_basis_reason is not None:
            raise ValueError("established invocation basis cannot carry a missing reason")
        request_pairs = (
            (self.request_estimand_status, self.request_estimand),
            (self.request_target_scope_status, self.request_target_scope),
            (self.outcome_variable_status, self.outcome_variable_id),
            (self.treatment_variable_status, self.treatment_variable_id),
            (self.request_alpha_status, self.requested_alpha),
            (self.requested_guarantee_status, self.requested_guarantee),
        )
        if any((status == "declared") != (value is not None) for status, value in request_pairs):
            raise ValueError("request values must match their explicit statuses")
        if self.contrast_status == "established":
            if self.control_value is None or self.treated_value is None:
                raise ValueError("established contrast requires both values")
            ensure_finite_numeric(self.control_value, field_name="control_value")
            ensure_finite_numeric(self.treated_value, field_name="treated_value")
            if self.control_value == self.treated_value:
                raise ValueError("control and treated values must differ")
        elif self.control_value is not None or self.treated_value is not None:
            raise ValueError("unestablished contrast cannot carry assumed values")
        if self.resource_evidence.execution_status != "returned":
            raise ValueError("candidate outcomes require an observed scoped resource profile")
        if (
            self.target_relation.requested_scope_status != self.request_target_scope_status
            or self.target_relation.requested_scope != self.request_target_scope
            or self.target_relation.requested_guarantee_status != self.requested_guarantee_status
            or self.target_relation.requested_guarantee != self.requested_guarantee
            or self.target_relation.computed_scope_status != "recomputed"
            or self.target_relation.computed_scope != "selected_evaluation_rows"
        ):
            raise ValueError(
                "target relation must preserve actual selected rows and requested claim"
            )
        if (
            self.request_target_scope is not None
            and self.target_relation.scope_disposition == "satisfied"
        ):
            if self.request_target_scope != "selected_evaluation_rows":
                raise ValueError("a stronger requested scope cannot be marked satisfied")
        return self


class HTEPointOutcome(_HTEOutcomeBase):
    """Valid candidate point result whose interval route is unavailable or unqualified."""

    kind: Literal["point_estimate"] = "point_estimate"
    authority_status: Literal["candidate"] = "candidate"
    point_result_ref: HTEPointResultRef
    inference_basis_ref: ATEInferenceBasisRef | None = None
    point_estimate: HTEPointEstimate
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

    @model_validator(mode="after")
    def _validate_point_result_relation(self) -> HTEPointOutcome:
        expected_reasons = {
            "not_requested": {"inference_not_requested"},
            "unavailable": {"native_inference_unavailable"},
            "unsupported": {"selection_uses_outcomes", "contrast_not_established"},
            "not_qualified": {"method_profile_not_qualified", "request_alpha_not_established"},
            "failed": {"native_inference_invalid"},
        }
        if self.inference_reason not in expected_reasons[self.inference_status]:
            raise ValueError("inference status and reason are contradictory")
        if self.inference_basis_ref is not None and (
            self.inference_status != "failed" or self.inference_reason != "native_inference_invalid"
        ):
            raise ValueError("point inference basis requires rejected native evidence")
        expected_guarantee = "candidate_point"
        if (
            self.target_relation.computed_guarantee_status != "computed"
            or self.target_relation.computed_guarantee != expected_guarantee
        ):
            raise ValueError("point outcome must identify its computed candidate-point guarantee")
        return self


class HTEIntervalOutcome(_HTEOutcomeBase):
    """Conditionally qualified native mean confidence interval."""

    kind: Literal["interval_estimate"] = "interval_estimate"
    authority_status: Literal["candidate"] = "candidate"
    point_estimate: HTEPointEstimate
    lower_bound: float
    upper_bound: float
    confidence_level: float = Field(gt=0.0, lt=1.0)
    interval_semantics: Literal["native_mean_confidence_interval"]
    inference_status: Literal["native_ate_inference_validated"]
    hte_result_ref: HTEResultEvidenceRef
    inference_basis_ref: ATEInferenceBasisRef

    @model_validator(mode="after")
    def _validate_interval(self) -> HTEIntervalOutcome:
        ensure_finite_numeric(self.lower_bound, field_name="lower_bound")
        ensure_finite_numeric(self.upper_bound, field_name="upper_bound")
        if self.lower_bound > self.upper_bound:
            raise ValueError("native interval bounds must be ordered")
        if not self.lower_bound <= self.point_estimate.value <= self.upper_bound:
            raise ValueError(
                "native interval must satisfy the legacy HTEResult point-containment rule"
            )
        ensure_finite_numeric(self.confidence_level, field_name="confidence_level")
        if self.request_alpha_status != "declared" or self.requested_alpha is None:
            raise ValueError("interval requires an owner-declared request alpha")
        if not math.isclose(
            1.0 - self.confidence_level,
            self.requested_alpha,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ):
            raise ValueError("interval confidence level must match requested alpha")
        if self.requested_guarantee_status != "declared":
            raise ValueError("interval requires an owner-declared requested guarantee")
        if (
            self.target_relation.computed_guarantee_status != "computed"
            or self.target_relation.computed_guarantee != "backend_conditional_interval"
            or self.target_relation.profile_status != "qualified"
            or self.target_relation.alpha_status != "recomputed"
            or self.target_relation.contrast_status != "recomputed"
        ):
            raise ValueError("native interval requires recomputed profile and request predicates")
        return self


class HTERefusalOutcome(BaseModel):
    """Stage-appropriate refusal that does not require successful-fit artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["refusal"] = "refusal"
    authority_status: Literal["refusal"] = "refusal"
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_abi: Literal["2.0.0"]
    method_abi_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    refusal_stage: Literal["prepare", "fit", "infer", "origin_verification"]
    refusal_reason: Literal[
        "invalid_point_estimate",
        "method_execution_failed",
        "required_input_unavailable",
        "invalid_selected_input",
        "method_profile_unavailable",
        "runtime_origin_not_verified",
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
        "runtime_origin_not_verified",
    ]
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef | None
    anchor_status: Literal["pre_output_anchor_resolved", "not_established"]
    requested_source_ref: HTEInputSourceRef | None
    requested_source_status: Literal["declared", "not_established"]
    source_data_ref: HTEInputSourceRef | None
    source_data_status: Literal["content_bound", "not_established"]
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"] | None
    selected_input_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_rows_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    resolved_params_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    n_selected_rows: int | None = Field(default=None, ge=0)
    selected_rows_status: Literal["recomputed", "not_established"]
    method_result_ref: MethodResultEvidenceRef | None
    method_result_status: Literal["available", "not_established"]
    method_evidence_ref: MethodExecutionEvidenceRef | None
    method_evidence_status: Literal["available", "not_established"]
    resource_evidence: HTEResourceExecutionEvidenceV1 | None
    invocation_basis_ref: ArtifactRefModel | None
    invocation_basis_status: Literal["established", "not_established"]
    invocation_basis_reason: (
        Literal[
            "owner_selected_invocation_basis",
            "no_invocation_basis_artifact_contract",
            "not_available_at_refusal_stage",
        ]
        | None
    )
    refusal_diagnostic_ref: HTERefusalDiagnosticRef
    request_estimand_status: Literal["declared", "not_established"]
    request_estimand: str | None = Field(default=None, min_length=1)
    request_target_scope_status: Literal["declared", "not_established"]
    request_target_scope: str | None = Field(default=None, min_length=1)
    outcome_variable_status: Literal["declared", "not_established"]
    outcome_variable_id: str | None = Field(default=None, min_length=1)
    treatment_variable_status: Literal["declared", "not_established"]
    treatment_variable_id: str | None = Field(default=None, min_length=1)
    contrast_status: Literal["established", "not_established"]
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
    target_relation: HTETargetRelationV1 | None
    limitations: tuple[str, ...] = Field(min_length=1)

    search_uncertainty_task_binding_ref: SearchUncertaintyTaskBindingRef | None = None

    @model_validator(mode="after")
    def _validate_refusal(self) -> HTERefusalOutcome:
        _validate_hte_v2_method_profile(self.method_fqn, self.method_abi, self.method_profile_id)
        expected_reasons = {
            "prepare": {
                "required_input_unavailable",
                "invalid_selected_input",
                "method_profile_unavailable",
            },
            "fit": {"method_execution_failed"},
            "infer": {"invalid_point_estimate"},
            "origin_verification": {"runtime_origin_not_verified"},
        }
        if self.refusal_reason not in expected_reasons[self.refusal_stage]:
            raise ValueError("refusal stage and reason are contradictory")
        if (self.anchor_status == "pre_output_anchor_resolved") != (
            self.owned_attempt_anchor_ref is not None
        ):
            raise ValueError("refusal anchor ref must match anchor_status")
        if self.anchor_status != "pre_output_anchor_resolved":
            raise ValueError("a persisted method-execution refusal requires its owner anchor")
        if (self.requested_source_status == "declared") != (self.requested_source_ref is not None):
            raise ValueError("requested source ref must match its status")
        if (self.source_data_status == "content_bound") != (self.source_data_ref is not None):
            raise ValueError("selected source ref must match its content status")
        row_values = (
            self.input_profile_id,
            self.selected_input_sha256,
            self.selected_rows_sha256,
            self.selected_x_sha256,
            self.selected_row_order_sha256,
            self.resolved_params_sha256,
            self.n_selected_rows,
        )
        if (self.selected_rows_status == "recomputed") != all(
            value is not None for value in row_values
        ):
            raise ValueError("selected-row fields must match their recomputation status")
        if self.selected_rows_status == "not_established" and any(
            value is not None for value in row_values
        ):
            raise ValueError("unestablished selected rows cannot carry success-path hashes")
        for value, status, label in (
            (self.method_result_ref, self.method_result_status, "method result"),
            (self.method_evidence_ref, self.method_evidence_status, "method evidence"),
        ):
            if (status == "available") != (value is not None):
                raise ValueError(f"{label} ref must match its availability status")
        if self.method_result_status != "available" or self.method_evidence_status != "available":
            raise ValueError(
                "a persisted method-execution refusal requires result and evidence refs"
            )
        if (self.invocation_basis_ref is None) != (
            self.invocation_basis_status == "not_established"
        ):
            raise ValueError("invocation basis ref must match its status")
        if (self.invocation_basis_ref is None) != (self.invocation_basis_reason is not None):
            raise ValueError("unavailable invocation basis requires a reason")
        request_pairs = (
            (self.request_estimand_status, self.request_estimand),
            (self.request_target_scope_status, self.request_target_scope),
            (self.outcome_variable_status, self.outcome_variable_id),
            (self.treatment_variable_status, self.treatment_variable_id),
            (self.request_alpha_status, self.requested_alpha),
            (self.requested_guarantee_status, self.requested_guarantee),
        )
        if any((status == "declared") != (value is not None) for status, value in request_pairs):
            raise ValueError("request values must match their explicit statuses")
        if self.contrast_status == "established":
            if self.control_value is None or self.treated_value is None:
                raise ValueError("established contrast requires both values")
            ensure_finite_numeric(self.control_value, field_name="control_value")
            ensure_finite_numeric(self.treated_value, field_name="treated_value")
            if self.control_value == self.treated_value:
                raise ValueError("control and treated values must differ")
        elif self.control_value is not None or self.treated_value is not None:
            raise ValueError("unestablished contrast cannot carry assumed values")
        if self.target_relation is not None and (
            self.target_relation.requested_scope_status != self.request_target_scope_status
            or self.target_relation.requested_scope != self.request_target_scope
            or self.target_relation.requested_guarantee_status != self.requested_guarantee_status
            or self.target_relation.requested_guarantee != self.requested_guarantee
        ):
            raise ValueError("refusal target relation must preserve the owner request")
        if self.resource_evidence is not None and self.owned_attempt_anchor_ref is None:
            raise ValueError("resource evidence requires the resolved owner anchor")
        if (
            self.refusal_diagnostic_ref.kind != "ir.hte_refusal_diagnostic"
            or self.refusal_diagnostic_ref.media_type != "application/json"
            or self.refusal_diagnostic_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method-execution refusal requires a selected diagnostic artifact")
        return self


type _HTEOutcomeVariant = Annotated[
    HTEPointOutcome | HTEIntervalOutcome | HTERefusalOutcome,
    Field(discriminator="kind"),
]


class HTEOutcome(RootModel[_HTEOutcomeVariant]):
    """Serialize the strict discriminated HTE outcome union as its branch payload.

    The root model gives schema reflection a concrete public owner while keeping
    the persisted JSON shape flat and preserving the branch-specific fields.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    @property
    def kind(self) -> str:
        """Return the outcome branch discriminator."""
        return self.root.kind

    def __getattr__(self, name: str) -> Any:
        """Forward common branch-field reads to the validated root variant."""
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.root, name)


_HTE_OUTCOME_ADAPTER: TypeAdapter[HTEOutcome] = TypeAdapter(HTEOutcome)


class HTEFinalizedArtifactRefs(BaseModel):
    """CAS refs returned after Runtime finalizes and persists one HTE outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    owned_attempt_anchor_ref: OwnedAttemptAnchorRef
    materialization_binding_ref: HTEPhysicalSourceMaterializationBindingRef
    hte_outcome_ref: HTEOutcomeRef
    point_result_ref: HTEPointResultRef | None = None
    hte_result_ref: HTEResultEvidenceRef | None = None
    inference_basis_ref: ATEInferenceBasisRef | None = None
    refusal_diagnostic_ref: HTERefusalDiagnosticRef | None = None
    invocation_basis_ref: ArtifactRefModel | None = None

    @model_validator(mode="after")
    def _validate_ref_chain(self) -> HTEFinalizedArtifactRefs:
        if self.refusal_diagnostic_ref is not None:
            if any(
                ref is not None
                for ref in (self.point_result_ref, self.hte_result_ref, self.inference_basis_ref)
            ):
                raise ValueError("refusal diagnostic cannot be combined with numeric result refs")
        elif self.hte_result_ref is not None:
            if self.point_result_ref is not None or self.inference_basis_ref is None:
                raise ValueError(
                    "HTEResult interval requires its basis and no duplicate point result"
                )
        elif self.point_result_ref is None:
            raise ValueError("non-refusal HTE outcome requires a point-result artifact")
        return self


def _assert_hte_artifact_manifest(
    store: ArtifactStore,
    ref: _ProfiledArtifactRef,
    *,
    schema_name: str,
    schema_version: str,
) -> None:
    """Check selected CAS manifest identity before validating a typed payload."""
    # Resolve by the Core selector value, then compare the typed IR descriptor
    # below. Passing the IR ref object itself makes the Core adapter inspect
    # its schema ClassVars as if they were selector fields.
    manifest = store.get_manifest(ref.artifact_id)
    dump = getattr(manifest, "model_dump", None)
    if callable(dump):
        payload = dump(mode="json", by_alias=True, exclude_none=True)
    elif isinstance(manifest, Mapping):
        payload = dict(manifest)
    else:
        raise ValueError("hte_manifest_invalid")
    schema = payload.get("schema")
    if (
        str(payload.get("artifact_id")) != str(ref.artifact_id)
        or payload.get("kind") != ref.kind
        or payload.get("media_type") != ref.media_type
        or not isinstance(schema, Mapping)
        or schema.get("name") != schema_name
        or str(schema.get("version")) != schema_version
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("hte_selected_manifest_identity_mismatch")


def _artifact_view_selector(ref: _ProfiledArtifactRef) -> dict[str, str]:
    """Project an HTE ref to IR's base selected-view selector fields."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("hte_selected_manifest_profile_missing")
    return {
        "artifact_id": str(ref.artifact_id),
        "kind": ref.kind,
        "media_type": ref.media_type,
        "manifest_profile_sha256": ref.manifest_profile_sha256,
    }


def _strict_hte_json[ModelT: BaseModel](model: type[ModelT], payload: Any) -> ModelT:
    """Validate a decoded CAS payload using strict JSON-mode container rules."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return model.model_validate_json(encoded, strict=True)


def persist_hte_outcome(
    store: ArtifactStore,
    outcome: HTEOutcome,
    *,
    inputs: list[InputRef] | None = None,
) -> HTEOutcomeRef:
    """Persist a finalized HTE union with its exact selected manifest profile."""
    validated = _HTE_OUTCOME_ADAPTER.validate_python(outcome, strict=True)
    ref = put_json_artifact(
        store,
        validated.model_dump(mode="json"),
        kind="ir.hte_outcome",
        schema_name=HTEOutcomeRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTEOutcomeRef.ARTIFACT_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return HTEOutcomeRef.model_validate(ref)


def load_hte_outcome(store: ArtifactStore, ref: HTEOutcomeRef) -> HTEOutcome:
    """Load and strictly validate a profile-bound HTE outcome artifact."""
    normalized = HTEOutcomeRef.model_validate(ref, strict=True)
    _assert_hte_artifact_manifest(
        store,
        normalized,
        schema_name=HTEOutcomeRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTEOutcomeRef.ARTIFACT_SCHEMA_VERSION,
    )
    encoded = json.dumps(
        get_json_artifact(store, _artifact_view_selector(normalized)),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _HTE_OUTCOME_ADAPTER.validate_json(encoded, strict=True)


def persist_ate_inference_basis(
    store: ArtifactStore,
    basis: ATEInferenceBasis,
    *,
    inputs: list[InputRef] | None = None,
) -> ATEInferenceBasisRef:
    """Persist native inference evidence with the selected manifest profile."""
    ref = put_json_artifact(
        store,
        basis.model_dump(mode="json"),
        kind="ir.ate_inference_basis",
        schema_name=ATEInferenceBasisRef.ARTIFACT_SCHEMA_NAME,
        schema_version=ATEInferenceBasisRef.ARTIFACT_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ATEInferenceBasisRef.model_validate(ref)


def load_ate_inference_basis(
    store: ArtifactStore,
    ref: ATEInferenceBasisRef,
) -> ATEInferenceBasis:
    """Load and strictly validate a profile-bound native inference basis."""
    normalized = ATEInferenceBasisRef.model_validate(ref)
    _assert_hte_artifact_manifest(
        store,
        normalized,
        schema_name=ATEInferenceBasisRef.ARTIFACT_SCHEMA_NAME,
        schema_version=ATEInferenceBasisRef.ARTIFACT_SCHEMA_VERSION,
    )
    return _strict_hte_json(
        ATEInferenceBasis, get_json_artifact(store, _artifact_view_selector(normalized))
    )


def persist_hte_point_result(
    store: ArtifactStore,
    result: HTEPointResult,
    *,
    inputs: list[InputRef] | None = None,
) -> HTEPointResultRef:
    """Persist the exact selected-row point vector without CI fields."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind=HTEPointResultRef.model_fields["kind"].default,
        schema_name=HTEPointResultRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTEPointResultRef.ARTIFACT_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return HTEPointResultRef.model_validate(ref)


def load_hte_point_result(
    store: ArtifactStore,
    ref: HTEPointResultRef,
) -> HTEPointResult:
    """Load one exact profile-bound point result and validate its row vector."""
    normalized = HTEPointResultRef.model_validate(ref)
    _assert_hte_artifact_manifest(
        store,
        normalized,
        schema_name=HTEPointResultRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTEPointResultRef.ARTIFACT_SCHEMA_VERSION,
    )
    return _strict_hte_json(
        HTEPointResult, get_json_artifact(store, _artifact_view_selector(normalized))
    )


def persist_hte_refusal_diagnostic(
    store: ArtifactStore,
    diagnostic: HTERefusalDiagnostic,
    *,
    inputs: list[InputRef],
) -> HTERefusalDiagnosticRef:
    """Persist one method-execution refusal bound to its selected owner refs."""
    validated = HTERefusalDiagnostic.model_validate(diagnostic, strict=True)
    ref = put_json_artifact(
        store,
        validated.model_dump(mode="json"),
        kind="ir.hte_refusal_diagnostic",
        schema_name=HTERefusalDiagnosticRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTERefusalDiagnosticRef.ARTIFACT_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return HTERefusalDiagnosticRef.model_validate(ref)


def load_hte_refusal_diagnostic(
    store: ArtifactStore,
    ref: HTERefusalDiagnosticRef,
) -> HTERefusalDiagnostic:
    """Load a refusal diagnostic only from its exact selected profile."""
    normalized = HTERefusalDiagnosticRef.model_validate(ref, strict=True)
    _assert_hte_artifact_manifest(
        store,
        normalized,
        schema_name=HTERefusalDiagnosticRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTERefusalDiagnosticRef.ARTIFACT_SCHEMA_VERSION,
    )
    return _strict_hte_json(
        HTERefusalDiagnostic, get_json_artifact(store, _artifact_view_selector(normalized))
    )


def persist_hte_result_v2(
    store: ArtifactStore,
    result: HTEResult,
    *,
    inputs: list[InputRef] | None = None,
) -> HTEResultEvidenceRef:
    """Persist a result for the new basis chain and retain its exact profile."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.hte_result",
        schema_name=HTEResultEvidenceRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTEResultEvidenceRef.ARTIFACT_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return HTEResultEvidenceRef.model_validate(ref)


def load_hte_result_v2(store: ArtifactStore, ref: HTEResultEvidenceRef) -> HTEResult:
    """Load the selected result only after exact kind/schema/profile checks."""
    normalized = HTEResultEvidenceRef.model_validate(ref)
    _assert_hte_artifact_manifest(
        store,
        normalized,
        schema_name=HTEResultEvidenceRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTEResultEvidenceRef.ARTIFACT_SCHEMA_VERSION,
    )
    return HTEResult.model_validate(get_json_artifact(store, _artifact_view_selector(normalized)))


class TargetingRule(BaseModel):
    """Operational rule for targeting treatment to high-value units."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    predicate_human: str | None = None
    priority: int = Field(ge=1)
    expected_cate: float
    expected_cost_per_unit: float = Field(ge=0.0)
    n_eligible_units: int = Field(ge=0)
    cumulative_budget_share: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_numbers(self) -> TargetingRule:
        if not math.isfinite(self.expected_cate):
            raise ValueError("expected_cate must be finite")
        if not math.isfinite(self.expected_cost_per_unit):
            raise ValueError("expected_cost_per_unit must be finite")
        return self


class PolicyRecommendation(BaseModel):
    """Budget-aware targeting recommendation derived from an HTE result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    hte_result_ref: str | None = None
    budget_constraint: float | None = Field(default=None, ge=0.0)
    optimization_objective: str = "maximize_total_effect"

    targeting_rules: list[TargetingRule] = Field(default_factory=list)
    total_expected_effect: float = 0.0
    total_cost: float = 0.0
    n_targeted_units: int = Field(default=0, ge=0)
    n_total_units: int = Field(default=0, ge=0)
    targeting_efficiency: float | None = None

    tree_depth: int | None = Field(default=None, ge=1)
    tree_n_leaves: int | None = Field(default=None, ge=1)

    cas_artifact_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, payload: Any) -> Any:
        return cls.normalize_payload(payload)

    @classmethod
    def normalize_payload(cls, payload: Any) -> Any:
        """Return a recommendation payload with explicit derived efficiency."""

        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        if normalized.get("targeting_efficiency") is not None:
            return normalized
        try:
            total_cost = float(normalized.get("total_cost", 0.0) or 0.0)
            total_effect = float(normalized.get("total_expected_effect", 0.0) or 0.0)
        except (TypeError, ValueError):
            return normalized
        if total_cost > 0.0:
            normalized["targeting_efficiency"] = total_effect / total_cost
        return normalized

    @classmethod
    def from_totals(cls, **payload: Any) -> PolicyRecommendation:
        """Construct a recommendation after applying explicit derived defaults."""

        return cls.model_validate(cls.normalize_payload(payload))

    @model_validator(mode="after")
    def _validate_totals(self) -> PolicyRecommendation:
        ensure_finite_numeric(self.total_expected_effect, field_name="total_expected_effect")
        ensure_finite_numeric(self.total_cost, field_name="total_cost")
        if self.n_targeted_units > self.n_total_units and self.n_total_units > 0:
            raise ValueError("n_targeted_units cannot exceed n_total_units")
        if self.targeting_efficiency is not None:
            ensure_finite_numeric(self.targeting_efficiency, field_name="targeting_efficiency")
        if self.total_cost == 0.0 and self.targeting_efficiency not in {None, 0.0}:
            raise ValueError("targeting_efficiency must be None or 0.0 when total_cost is zero")
        if self.total_cost > 0.0 and self.targeting_efficiency is not None:
            expected_efficiency = self.total_expected_effect / self.total_cost
            if not math.isclose(
                self.targeting_efficiency,
                expected_efficiency,
                rel_tol=1.0e-12,
                abs_tol=1.0e-12,
            ):
                raise ValueError(
                    "targeting_efficiency must equal total_expected_effect / total_cost"
                )
        if (
            self.budget_constraint is not None
            and self.total_cost > self.budget_constraint + 1.0e-12
        ):
            raise ValueError("total_cost cannot exceed budget_constraint")
        ensure_unique_ids(
            self.targeting_rules,
            key_fn=lambda item: item.rule_id,
            label="targeting_rule rule_id",
        )
        ensure_unique_ids(
            self.targeting_rules,
            key_fn=lambda item: item.priority,
            label="targeting_rule priority",
        )
        return self


def persist_hte_result(
    store: ArtifactStore,
    result: HTEResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.hte_result",
    schema_version: str = "1.0",
) -> HTEResultRef:
    """Persist an HTE result and return its typed artifact reference."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.hte_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return HTEResultRef.model_validate(ref)


def load_hte_result(store: ArtifactStore, ref: HTEResultRef) -> HTEResult:
    """Load hte result."""
    payload = get_json_artifact(store, ref)
    return HTEResult.model_validate(payload)


def persist_policy_recommendation(
    store: ArtifactStore,
    recommendation: PolicyRecommendation,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.policy_recommendation",
    schema_version: str = "1.0",
) -> PolicyRecommendationRef:
    """Persist a targeting recommendation derived from an HTE artifact."""
    ref = put_json_artifact(
        store,
        recommendation.model_dump(mode="json"),
        kind="ir.policy_recommendation",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PolicyRecommendationRef.model_validate(ref)


def load_policy_recommendation(
    store: ArtifactStore,
    ref: PolicyRecommendationRef,
) -> PolicyRecommendation:
    """Load policy recommendation."""
    payload = get_json_artifact(store, ref)
    return PolicyRecommendation.model_validate(payload)


__all__ = [
    "ATEInferenceBasis",
    "ATEInferenceBasisRef",
    "FeatureImportance",
    "HTEFinalizedArtifactRefs",
    "HTEInputSourceRef",
    "HTEIntervalOutcome",
    "HTEOutcome",
    "HTEOutcomeRef",
    "HTEPointEstimate",
    "HTEPointOutcome",
    "HTEPointResult",
    "HTEPointResultRef",
    "HTERefusalDiagnostic",
    "HTERefusalDiagnosticRef",
    "HTERefusalOutcome",
    "HTEResourceExecutionEvidenceV1",
    "HTEResult",
    "HTEResultEvidenceRef",
    "MethodExecutionEvidenceRef",
    "MethodResultEvidenceRef",
    "OwnedAttemptAnchorRef",
    "PolicyRecommendation",
    "SearchUncertaintyTaskBindingRef",
    "SubgroupEffect",
    "TargetingRule",
    "load_ate_inference_basis",
    "load_hte_outcome",
    "load_hte_point_result",
    "load_hte_refusal_diagnostic",
    "load_hte_result",
    "load_hte_result_v2",
    "load_policy_recommendation",
    "persist_ate_inference_basis",
    "persist_hte_outcome",
    "persist_hte_point_result",
    "persist_hte_refusal_diagnostic",
    "persist_hte_result",
    "persist_hte_result_v2",
    "persist_policy_recommendation",
]
