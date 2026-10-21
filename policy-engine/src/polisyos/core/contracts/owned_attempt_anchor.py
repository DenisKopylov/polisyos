"""Strict contract for a persisted pre-output HTE attempt anchor.

The anchor binds one live fenced worker attempt to its immutable request and
pre-dispatch input capture. It intentionally contains no estimator output,
inference basis, method-result, or post-run association reference.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..artifacts.manifest import ArtifactRef

OWNED_ATTEMPT_ANCHOR_KIND = "runtime.owned_attempt_anchor"
OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME = "polisyos.runtime.OwnedAttemptAnchor"
OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION = "1.0"
OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION_FIELD = "1.0"
_SHA256 = r"^sha256:[0-9a-f]{64}$"
_HEX_SHA256 = r"^[0-9a-f]{64}$"
_ORIGIN_LABELS = frozenset(
    {
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    }
)


class SelectedArtifactRef(ArtifactRef):
    """Require a concrete immutable CAS manifest profile at this boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    manifest_profile_sha256: str = Field(pattern=_SHA256, strict=True)


class OwnedAttemptAnchorRef(SelectedArtifactRef):
    """Resolve one exact selected-profile view of an owned-attempt anchor."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["runtime.owned_attempt_anchor"] = OWNED_ATTEMPT_ANCHOR_KIND
    media_type: Literal["application/json"] = "application/json"


class OwnedAttemptPhysicalSourceBindingRef(SelectedArtifactRef):
    """Resolve one exact profile-selected physical HTE materialization record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["foundry.hte.physical_source_materialization_binding"] = (
        "foundry.hte.physical_source_materialization_binding"
    )
    media_type: Literal["application/json"] = "application/json"


class OwnedAttemptLifecycleEvent(BaseModel):
    """Identify one immutable lifecycle event row by owner identity and digest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: int = Field(ge=1)
    job_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["job_created", "job_running", "job_completed", "job_failed"]
    payload_sha256: str = Field(pattern=_SHA256)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def require_aware_event_time(cls, value: datetime) -> datetime:
        """Reject owner timestamps that do not carry an explicit time zone."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("owned_attempt_event_time_must_be_aware")
        return value


class OwnedHTERequestContextV1(BaseModel):
    """Freeze request selectors from the immutable Runtime intent."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_estimand_status: Literal["declared", "not_established"]
    request_estimand: str | None = Field(default=None, min_length=1, max_length=256)
    request_target_scope_status: Literal["declared", "not_established"]
    request_target_scope: str | None = Field(default=None, min_length=1, max_length=256)
    outcome_variable_status: Literal["declared", "not_established"]
    outcome_variable_id: str | None = Field(default=None, min_length=1, max_length=256)
    treatment_variable_status: Literal["declared", "not_established"]
    treatment_variable_id: str | None = Field(default=None, min_length=1, max_length=256)
    contrast_status: Literal["declared", "not_established"]
    control_value: float | None = None
    treated_value: float | None = None
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
    ) = None
    search_uncertainty_task_binding_ref: SelectedArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @field_validator("control_value", "treated_value")
    @classmethod
    def require_finite_context_contrast(cls, value: float | None) -> float | None:
        """Reject non-finite treatment values in a selected request."""
        if value is not None and not math.isfinite(value):
            raise ValueError("owned_attempt_request_contrast_non_finite")
        return value

    @model_validator(mode="after")
    def require_coherent_request_context(self) -> OwnedHTERequestContextV1:
        """Keep each declared selector paired with its owner-supplied value."""
        declarations = (
            (self.request_estimand_status, self.request_estimand),
            (self.request_target_scope_status, self.request_target_scope),
            (self.outcome_variable_status, self.outcome_variable_id),
            (self.treatment_variable_status, self.treatment_variable_id),
            (self.contrast_status, self.control_value),
            (self.request_alpha_status, self.requested_alpha),
            (self.requested_guarantee_status, self.requested_guarantee),
        )
        if any((status == "declared") != (value is not None) for status, value in declarations):
            raise ValueError("owned_attempt_request_context_status_mismatch")
        if (self.control_value is None) != (self.treated_value is None):
            raise ValueError("owned_attempt_request_context_contrast_pair_incomplete")
        if self.control_value is not None and self.control_value == self.treated_value:
            raise ValueError("owned_attempt_request_context_contrast_values_must_differ")
        binding_ref = self.search_uncertainty_task_binding_ref
        if binding_ref is not None and (
            binding_ref.kind != "scientist.search.uncertainty_task_binding"
            or binding_ref.media_type != "application/json"
        ):
            raise ValueError("owned_attempt_search_binding_ref_kind_mismatch")
        return self


class OwnedAttemptPredicateOrigins(BaseModel):
    """Freeze the evidence origin for every predicate used by this gate.

    Request declarations are reconciled to immutable Runtime intent, not
    promoted to external truth. Execution receipts and Search dependency
    closure are outside this pre-output artifact and remain not established.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    owner_attempt_fence: Literal["recomputed"]
    lifecycle_event_chain: Literal["recomputed"]
    requested_source_identity: Literal["independently_reconciled"]
    selected_method_abi: Literal["independently_reconciled"]
    selected_resource_policy: Literal["independently_reconciled"]
    resolved_params_and_seed: Literal["independently_reconciled"]
    selected_input_content: Literal["recomputed", "not_established"]
    request_estimand: Literal["independently_reconciled", "not_established"]
    request_target_scope: Literal["independently_reconciled", "not_established"]
    outcome_variable: Literal["independently_reconciled", "not_established"]
    treatment_variable: Literal["independently_reconciled", "not_established"]
    treatment_contrast: Literal["independently_reconciled", "not_established"]
    requested_alpha: Literal["independently_reconciled", "not_established"]
    requested_guarantee: Literal["independently_reconciled", "not_established"]
    estimator_job_cap: Literal["independently_reconciled", "not_established"]
    selected_producer_job_cap: Literal["independently_reconciled", "not_established"]
    actual_execution_resource_context: Literal["not_established"]
    search_dependency_inventory: Literal["not_established"]
    completed_output_owner_association: Literal["not_established"]

    @model_validator(mode="after")
    def reject_non_owner_origin_labels(self) -> OwnedAttemptPredicateOrigins:
        """Do not admit caller-asserted or institutionally supplied gate facts."""
        for name in type(self).model_fields:
            value = getattr(self, name)
            if value not in _ORIGIN_LABELS or value in {
                "consumer_asserted",
                "institutionally_supplied",
            }:
                raise ValueError(f"owned_attempt_predicate_origin_not_admissible:{name}")
        return self


class OwnedAttemptHTEInputRefusal(BaseModel):
    """Capture a typed preparation refusal without inventing admitted input."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    refusal_code: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    failure_stage: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    observed_manifest_selection_bytes: int | None = Field(default=None, ge=0)
    observed_manifest_verification_bytes: int | None = Field(default=None, ge=0)
    observed_payload_bytes: int | None = Field(default=None, ge=0)
    observed_source_bytes: int | None = Field(default=None, ge=0)
    source_usage_complete: bool
    payload_integrity_verified: bool

    @model_validator(mode="after")
    def require_coherent_usage(self) -> OwnedAttemptHTEInputRefusal:
        """Preserve only exact bounded usage supplied by Core's refusal type."""
        parts = (
            self.observed_manifest_selection_bytes,
            self.observed_manifest_verification_bytes,
            self.observed_payload_bytes,
        )
        if self.source_usage_complete:
            if any(type(value) is not int for value in parts):
                raise ValueError("owned_attempt_refusal_usage_completeness_mismatch")
            if self.observed_source_bytes != sum(parts):
                raise ValueError("owned_attempt_refusal_source_byte_total_mismatch")
        elif self.observed_source_bytes is not None:
            raise ValueError("owned_attempt_refusal_unknown_usage_has_total")
        return self


class OwnedAttemptHTEInputCapture(BaseModel):
    """Record the HTE input and request facts recomputed before estimator dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    source_data_ref: SelectedArtifactRef
    source_data_sha256: str = Field(pattern=_HEX_SHA256)
    input_profile_id: Literal["all_source_rows_in_input_order@1.0"]
    selected_input_sha256: str = Field(pattern=_HEX_SHA256)
    selected_rows_sha256: str = Field(pattern=_HEX_SHA256)
    selected_x_sha256: str = Field(pattern=_HEX_SHA256)
    selected_row_order_sha256: str = Field(pattern=_HEX_SHA256)
    fit_rows_sha256: str = Field(pattern=_HEX_SHA256)
    eval_rows_sha256: str = Field(pattern=_HEX_SHA256)
    fit_eval_relation: Literal["same_selected_rows"]
    n_selected_rows: int = Field(gt=0)
    n_treated: int = Field(ge=0, strict=True)
    n_control: int = Field(ge=0, strict=True)
    n_features: int = Field(gt=0)
    source_feature_names: tuple[str, ...] | None = None
    n_confounders: int = Field(ge=0)
    sample_ids_status: Literal["provided", "not_established"]
    sample_ids_sha256: str | None = Field(default=None, pattern=_HEX_SHA256)
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_abi: Literal["2.0.0"]
    method_abi_digest: str = Field(pattern=_HEX_SHA256)
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    resolved_params_sha256: str = Field(pattern=_HEX_SHA256)
    resolved_params: dict[str, Any]
    seed: int = Field(ge=0, le=4_294_967_295)
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef | None = None
    request_context: OwnedHTERequestContextV1

    @field_validator("source_data_ref")
    @classmethod
    def require_selected_source_profile(cls, value: SelectedArtifactRef) -> SelectedArtifactRef:
        """Require the capture to identify an exact source view."""
        if value.manifest_profile_sha256 is None:
            raise ValueError("owned_attempt_input_source_profile_missing")
        return value

    @model_validator(mode="after")
    def require_coherent_capture(self) -> OwnedAttemptHTEInputCapture:
        """Keep method profile, row selection, and request declarations coherent."""
        if self.selected_input_sha256 != self.source_data_sha256:
            raise ValueError("owned_attempt_input_source_digest_mismatch")
        if self.materialization_binding_ref != self.request_context.materialization_binding_ref:
            raise ValueError("owned_attempt_input_materialization_binding_context_mismatch")
        if self.fit_rows_sha256 != self.eval_rows_sha256:
            raise ValueError("owned_attempt_input_fit_eval_rows_mismatch")
        if (
            self.source_feature_names is not None
            and len(self.source_feature_names) != self.n_features
        ):
            raise ValueError("owned_attempt_input_feature_names_width_mismatch")
        if self.request_context.contrast_status == "declared":
            if self.n_treated + self.n_control != self.n_selected_rows:
                raise ValueError("owned_attempt_input_treatment_counts_do_not_cover_rows")
        elif self.n_treated != 0 or self.n_control != 0:
            raise ValueError("owned_attempt_input_treatment_counts_without_declared_contrast")
        if (self.sample_ids_status == "provided") != (self.sample_ids_sha256 is not None):
            raise ValueError("owned_attempt_input_sample_id_digest_mismatch")
        expected_method_profile = {
            "causal.hte.causal_forest@2.0.0": "econml.causal_forest_dml.native_mean@2.0",
            "causal.hte.double_ml@2.0.0": "econml.dml.point_only@2.0",
            "causal.hte.meta_learner@2.0.0": "econml.meta_learner.point_only@2.0",
            "causal.hte.forest_dr@2.0.0": "econml.forest_dr.native_mean@2.0",
        }[self.method_fqn]
        if self.method_profile_id != expected_method_profile:
            raise ValueError("owned_attempt_input_method_profile_mismatch")
        request_context = self.request_context
        resolved_alpha = self.resolved_params.get("alpha")
        if request_context.request_alpha_status == "declared" and (
            resolved_alpha is None
            or isinstance(resolved_alpha, bool)
            or not isinstance(resolved_alpha, (int, float))
            or not math.isfinite(float(resolved_alpha))
            or not math.isclose(
                float(resolved_alpha),
                float(request_context.requested_alpha),
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
        ):
            raise ValueError("owned_attempt_input_alpha_request_mismatch")
        resolved_control = self.resolved_params.get("control_value")
        resolved_treated = self.resolved_params.get("treated_value")
        if (resolved_control is None) != (resolved_treated is None):
            raise ValueError("owned_attempt_input_resolved_contrast_pair_incomplete")
        if resolved_control is not None and (
            request_context.contrast_status != "declared"
            or isinstance(resolved_control, bool)
            or isinstance(resolved_treated, bool)
            or not isinstance(resolved_control, (int, float))
            or not isinstance(resolved_treated, (int, float))
            or not math.isfinite(float(resolved_control))
            or not math.isfinite(float(resolved_treated))
            or not math.isclose(
                float(resolved_control),
                float(request_context.control_value),
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
            or not math.isclose(
                float(resolved_treated),
                float(request_context.treated_value),
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
        ):
            raise ValueError("owned_attempt_input_resolved_contrast_mismatch")
        params_payload = json.dumps(
            {"params": self.resolved_params, "seed": self.seed},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if hashlib.sha256(params_payload).hexdigest() != self.resolved_params_sha256:
            raise ValueError("owned_attempt_input_params_digest_mismatch")
        return self


class OwnedAttemptHTEInputAdmitted(BaseModel):
    """Discriminated successful preparation branch with complete selected refs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    admission_status: Literal["input_admitted"] = "input_admitted"
    content_admitted_intent_ref: SelectedArtifactRef
    submitted_input_ref: SelectedArtifactRef
    effective_input_ref: SelectedArtifactRef
    normalization: Literal[
        "canonical_passthrough",
        "legacy_to_method_input_envelope_v1",
    ]
    input_capture: OwnedAttemptHTEInputCapture


class OwnedAttemptHTEInputRefused(BaseModel):
    """Discriminated refusal branch containing no fake admission artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    admission_status: Literal["input_admission_refused"] = "input_admission_refused"
    refusal: OwnedAttemptHTEInputRefusal


OwnedAttemptInputAdmission = Annotated[
    OwnedAttemptHTEInputAdmitted | OwnedAttemptHTEInputRefused,
    Field(discriminator="admission_status"),
]


class OwnedAttemptAnchorDispatchContext(BaseModel):
    """Typed Core bridge passed separately to one HTE method dispatch.

    This object is Runtime-owned execution metadata. It is never merged into
    scientific method parameters, and the selected parameter digest remains
    the digest of the exact scientific parameter mapping plus seed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    anchor_ref: OwnedAttemptAnchorRef
    input_capture: OwnedAttemptHTEInputCapture
    method_abi_digest: str = Field(pattern=_HEX_SHA256)

    @model_validator(mode="after")
    def require_capture_abi_matches(self) -> OwnedAttemptAnchorDispatchContext:
        """Keep the transient dispatch frame bound to its persisted anchor capture."""
        if self.input_capture.method_abi_digest != self.method_abi_digest:
            raise ValueError("owned_attempt_dispatch_context_abi_mismatch")
        if self.anchor_ref.kind != OWNED_ATTEMPT_ANCHOR_KIND:
            raise ValueError("owned_attempt_dispatch_context_anchor_kind_mismatch")
        return self

    def hte_capture_payload(self) -> dict[str, Any]:
        """Project the capture for an HTE-owned strict reader, outside params."""
        capture = self.input_capture.model_dump(mode="json", exclude={"request_context"})
        if self.input_capture.source_feature_names is not None:
            capture["source_feature_names"] = self.input_capture.source_feature_names
        capture.update(self.input_capture.request_context.model_dump(mode="json"))
        return capture


class OwnedAttemptAnchor(BaseModel):
    """Bind immutable owner events, current lease, intent, and pre-output HTE input."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = OWNED_ATTEMPT_ANCHOR_KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION

    schema_version: Literal["1.0"] = OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION_FIELD
    purpose: Literal["pre_output_owned_attempt_anchor"] = "pre_output_owned_attempt_anchor"
    captured_at: datetime
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=256)
    cell_id: str | None = Field(default=None, min_length=1, max_length=256)
    attempt: int = Field(ge=1)
    worker_id: str = Field(min_length=1, max_length=256)
    lease_expires_at: datetime
    job_created_event: OwnedAttemptLifecycleEvent
    job_running_event: OwnedAttemptLifecycleEvent
    requested_source_ref: SelectedArtifactRef
    observational_run_intent_ref: SelectedArtifactRef
    resource_policy_ref: SelectedArtifactRef
    selection_digest: str = Field(pattern=_HEX_SHA256)
    source_manifest_sha256: str = Field(pattern=_HEX_SHA256)
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_version: Literal["2.0.0"]
    method_abi_digest: str = Field(pattern=_HEX_SHA256)
    method_build_digest: str = Field(pattern=_HEX_SHA256)
    resource_policy_digest: str = Field(pattern=_HEX_SHA256)
    resource_policy_schema_version: Literal[
        "polisyos.runtime.observational_input_resource_policy.v1",
        "polisyos.runtime.observational_input_resource_policy.v2",
        "polisyos.runtime.observational_input_resource_policy.v3",
        "polisyos.runtime.observational_input_resource_policy.v4",
        "polisyos.runtime.observational_input_resource_policy.v5",
    ]
    resource_policy_revision: Literal["r1", "r2", "r3", "r4", "r5"]
    resource_policy_method_contract_target: (
        Literal["polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"] | None
    )
    resource_policy_required_estimator_n_jobs: Literal[1] | None
    resource_policy_method_fqn: (
        Literal[
            "causal.hte.causal_forest@2.0.0",
            "causal.hte.double_ml@2.0.0",
            "causal.hte.meta_learner@2.0.0",
            "causal.hte.forest_dr@2.0.0",
        ]
        | None
    )
    resource_policy_method_profile_id: (
        Literal[
            "econml.causal_forest_dml.native_mean@2.0",
            "econml.dml.point_only@2.0",
            "econml.meta_learner.point_only@2.0",
            "econml.forest_dr.native_mean@2.0",
        ]
        | None
    )
    resource_policy_execution_scope: (
        Literal[
            "estimator_n_jobs_one",
            "producer_scoped_joblib_parallelism_one",
        ]
        | None
    )
    resource_policy_max_jobs: Literal[1] | None
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    resolved_params_sha256: str = Field(pattern=_HEX_SHA256)
    request_context: OwnedHTERequestContextV1
    input_admission: OwnedAttemptInputAdmission
    predicate_origins: OwnedAttemptPredicateOrigins

    @property
    def content_admitted_intent_ref(self) -> SelectedArtifactRef:
        """Return the admitted-intent ref only for the successful branch."""
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted):
            return self.input_admission.content_admitted_intent_ref
        raise ValueError("owned_attempt_input_admission_refused")

    @property
    def submitted_input_ref(self) -> SelectedArtifactRef:
        """Return the submitted source ref only for the successful branch."""
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted):
            return self.input_admission.submitted_input_ref
        raise ValueError("owned_attempt_input_admission_refused")

    @property
    def effective_input_ref(self) -> SelectedArtifactRef:
        """Return the effective input ref only for the successful branch."""
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted):
            return self.input_admission.effective_input_ref
        raise ValueError("owned_attempt_input_admission_refused")

    @property
    def normalization(
        self,
    ) -> Literal[
        "canonical_passthrough",
        "legacy_to_method_input_envelope_v1",
    ]:
        """Return the producer-observed normalization only on admission."""
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted):
            return self.input_admission.normalization
        raise ValueError("owned_attempt_input_admission_refused")

    @property
    def input_capture(self) -> OwnedAttemptHTEInputCapture:
        """Return selected input facts only for a content-admitted input."""
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted):
            return self.input_admission.input_capture
        raise ValueError("owned_attempt_input_admission_refused")

    @field_validator("captured_at", "lease_expires_at")
    @classmethod
    def require_aware_anchor_times(cls, value: datetime) -> datetime:
        """Require aware timestamps for the capture and live lease boundary."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("owned_attempt_anchor_time_must_be_aware")
        return value

    @field_validator(
        "requested_source_ref",
        "observational_run_intent_ref",
        "resource_policy_ref",
    )
    @classmethod
    def require_full_selected_refs(cls, value: SelectedArtifactRef) -> SelectedArtifactRef:
        """Require every cross-boundary ref to retain its selected profile."""
        if value.manifest_profile_sha256 is None:
            raise ValueError("owned_attempt_anchor_selected_profile_missing")
        return value

    @model_validator(mode="after")
    def require_owner_and_request_bindings(self) -> OwnedAttemptAnchor:
        """Reject owner-event, reference, and method facts that disagree."""
        if self.captured_at.tzinfo is None or self.lease_expires_at <= self.captured_at:
            raise ValueError("owned_attempt_anchor_lease_not_live_at_capture")
        if (
            self.job_created_event.event_type != "job_created"
            or self.job_running_event.event_type != "job_running"
            or self.job_created_event.job_id != self.job_id
            or self.job_running_event.job_id != self.job_id
            or self.job_created_event.event_id >= self.job_running_event.event_id
            or self.job_created_event.created_at > self.job_running_event.created_at
            or self.job_running_event.created_at > self.captured_at
        ):
            raise ValueError("owned_attempt_anchor_lifecycle_event_mismatch")
        refs = [
            self.requested_source_ref,
            self.observational_run_intent_ref,
            self.resource_policy_ref,
        ]
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted):
            refs.extend(
                (
                    self.input_admission.content_admitted_intent_ref,
                    self.input_admission.submitted_input_ref,
                    self.input_admission.effective_input_ref,
                    self.input_admission.input_capture.source_data_ref,
                )
            )
            physical_binding_ref = self.input_admission.input_capture.materialization_binding_ref
            if self.resource_policy_revision == "r5" and physical_binding_ref is None:
                raise ValueError("owned_attempt_r5_physical_materialization_binding_required")
            if physical_binding_ref is not None:
                refs.append(physical_binding_ref)
                if self.request_context.materialization_binding_ref != physical_binding_ref:
                    raise ValueError(
                        "owned_attempt_anchor_physical_materialization_context_mismatch"
                    )
        else:
            if self.input_admission.refusal is None:
                raise ValueError("owned_attempt_refusal_capture_required")
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("owned_attempt_anchor_selected_profile_missing")
        if (
            self.observational_run_intent_ref.kind != "runtime.observational_run_intent"
            or self.observational_run_intent_ref.media_type != "application/json"
            or self.resource_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.resource_policy_ref.media_type != "application/json"
            or self.method_fqn.rpartition("@")[2] != self.method_version
        ):
            raise ValueError("owned_attempt_anchor_selected_intent_binding_mismatch")
        origins = self.predicate_origins
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted):
            capture = self.input_admission.input_capture
            if (
                self.input_admission.content_admitted_intent_ref.kind
                != "runtime.content_admitted_observational_run_intent"
                or self.input_admission.content_admitted_intent_ref.media_type != "application/json"
                or self.input_admission.submitted_input_ref != self.requested_source_ref
                or capture.source_data_ref != self.input_admission.effective_input_ref
                or capture.method_fqn != self.method_fqn
                or capture.method_abi != self.method_version
                or capture.method_abi_digest != self.method_abi_digest
                or capture.resolved_params_sha256 != self.resolved_params_sha256
                or capture.request_context != self.request_context
                or origins.selected_input_content != "recomputed"
            ):
                raise ValueError("owned_attempt_anchor_admitted_input_binding_mismatch")
        elif origins.selected_input_content != "not_established":
            raise ValueError("owned_attempt_refusal_input_origin_mismatch")
        for field_name, status in (
            ("request_estimand", self.request_context.request_estimand_status),
            ("request_target_scope", self.request_context.request_target_scope_status),
            ("outcome_variable", self.request_context.outcome_variable_status),
            ("treatment_variable", self.request_context.treatment_variable_status),
            ("treatment_contrast", self.request_context.contrast_status),
            ("requested_alpha", self.request_context.request_alpha_status),
            ("requested_guarantee", self.request_context.requested_guarantee_status),
        ):
            expected_origin = (
                "independently_reconciled" if status == "declared" else "not_established"
            )
            if getattr(origins, field_name) != expected_origin:
                raise ValueError("owned_attempt_request_predicate_origin_mismatch")
        if origins.estimator_job_cap != (
            "independently_reconciled"
            if self.resource_policy_required_estimator_n_jobs == 1
            else "not_established"
        ):
            raise ValueError("owned_attempt_resource_cap_origin_mismatch")
        if origins.selected_producer_job_cap != (
            "independently_reconciled"
            if self.resource_policy_execution_scope == "producer_scoped_joblib_parallelism_one"
            and self.resource_policy_max_jobs == 1
            else "not_established"
        ):
            raise ValueError("owned_attempt_producer_cap_origin_mismatch")
        expected_source_kind = (
            "ir.observation_method_input"
            if self.source_protocol == "method_input_envelope_v1"
            else "ir.observational_data"
        )
        if self.requested_source_ref.kind != expected_source_kind or (
            self.requested_source_ref.media_type != "application/json"
        ):
            raise ValueError("owned_attempt_anchor_input_ref_kind_mismatch")
        if isinstance(self.input_admission, OwnedAttemptHTEInputAdmitted) and (
            self.input_admission.effective_input_ref.kind != "ir.observation_method_input"
            or self.input_admission.effective_input_ref.media_type != "application/json"
        ):
            raise ValueError("owned_attempt_anchor_input_ref_kind_mismatch")
        expected_resource_policy_profile = {
            "r1": (
                "polisyos.runtime.observational_input_resource_policy.v1",
                None,
                None,
                None,
                None,
                None,
                None,
            ),
            "r2": (
                "polisyos.runtime.observational_input_resource_policy.v2",
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
                1,
                None,
                None,
                None,
                None,
            ),
            "r3": (
                "polisyos.runtime.observational_input_resource_policy.v3",
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
                1,
                None,
                None,
                None,
                None,
            ),
        }
        if self.resource_policy_revision == "r4":
            expected_profile_id, expected_scope, expected_estimator_jobs = {
                "causal.hte.causal_forest@2.0.0": (
                    "econml.causal_forest_dml.native_mean@2.0",
                    "estimator_n_jobs_one",
                    1,
                ),
                "causal.hte.double_ml@2.0.0": (
                    "econml.dml.point_only@2.0",
                    "producer_scoped_joblib_parallelism_one",
                    None,
                ),
                "causal.hte.meta_learner@2.0.0": (
                    "econml.meta_learner.point_only@2.0",
                    "producer_scoped_joblib_parallelism_one",
                    None,
                ),
                "causal.hte.forest_dr@2.0.0": (
                    "econml.forest_dr.native_mean@2.0",
                    "estimator_n_jobs_one",
                    1,
                ),
            }[self.method_fqn]
            expected_resource_policy_profile = (
                "polisyos.runtime.observational_input_resource_policy.v4",
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
                expected_estimator_jobs,
                self.method_fqn,
                expected_profile_id,
                expected_scope,
                1,
            )
        elif self.resource_policy_revision == "r5":
            expected_profile_id, expected_estimator_jobs = {
                "causal.hte.causal_forest@2.0.0": (
                    "econml.causal_forest_dml.native_mean@2.0",
                    1,
                ),
                "causal.hte.double_ml@2.0.0": (
                    "econml.dml.point_only@2.0",
                    None,
                ),
                "causal.hte.meta_learner@2.0.0": (
                    "econml.meta_learner.point_only@2.0",
                    None,
                ),
                "causal.hte.forest_dr@2.0.0": (
                    "econml.forest_dr.native_mean@2.0",
                    1,
                ),
            }[self.method_fqn]
            expected_resource_policy_profile = (
                "polisyos.runtime.observational_input_resource_policy.v5",
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
                expected_estimator_jobs,
                self.method_fqn,
                expected_profile_id,
                "producer_scoped_joblib_parallelism_one",
                1,
            )
        else:
            expected_resource_policy_profile = expected_resource_policy_profile[
                self.resource_policy_revision
            ]
        if (
            self.resource_policy_schema_version,
            self.resource_policy_method_contract_target,
            self.resource_policy_required_estimator_n_jobs,
            self.resource_policy_method_fqn,
            self.resource_policy_method_profile_id,
            self.resource_policy_execution_scope,
            self.resource_policy_max_jobs,
        ) != expected_resource_policy_profile:
            raise ValueError("owned_attempt_resource_policy_profile_revision_mismatch")
        return self


class OwnedAttemptAnchorAssociation(BaseModel):
    """Return the completed owner-selected output tuple bound to one anchor.

    This is an ephemeral verification result. It is not persisted and cannot
    independently grant inference authority; consumers must retain the returned
    source and method-evidence refs and apply their own contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["owner_selection_reconciled"] = "owner_selection_reconciled"
    verified_at: datetime
    anchor_ref: OwnedAttemptAnchorRef
    outcome_ref: SelectedArtifactRef
    invocation_basis_ref: SelectedArtifactRef | None = None
    invocation_basis_content_status: Literal["not_established"] = "not_established"
    outcome_kind: Literal["point_estimate", "interval_estimate", "refusal"]
    source_data_ref: SelectedArtifactRef
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef | None = None
    search_uncertainty_task_binding_ref: SelectedArtifactRef | None = None
    method_result_ref: SelectedArtifactRef
    method_evidence_ref: SelectedArtifactRef
    refusal_diagnostic_ref: SelectedArtifactRef | None = None
    point_result_ref: SelectedArtifactRef | None = None
    hte_result_ref: SelectedArtifactRef | None = None
    inference_basis_ref: SelectedArtifactRef | None = None
    job_completed_event: OwnedAttemptLifecycleEvent
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1)

    @field_validator("verified_at")
    @classmethod
    def require_aware_verification_time(cls, value: datetime) -> datetime:
        """Require an aware timestamp for the owner reconciliation read."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("owned_attempt_association_time_must_be_aware")
        return value

    @field_validator(
        "outcome_ref",
        "invocation_basis_ref",
        "source_data_ref",
        "materialization_binding_ref",
        "search_uncertainty_task_binding_ref",
        "method_result_ref",
        "method_evidence_ref",
        "refusal_diagnostic_ref",
        "point_result_ref",
        "hte_result_ref",
        "inference_basis_ref",
    )
    @classmethod
    def require_selected_output_profiles(
        cls, value: SelectedArtifactRef | None
    ) -> SelectedArtifactRef | None:
        """Require profile-qualified refs for every present owner-selected output."""
        if value is not None and value.manifest_profile_sha256 is None:
            raise ValueError("owned_attempt_association_output_profile_missing")
        return value

    @model_validator(mode="after")
    def require_outcome_result_chain(self) -> OwnedAttemptAnchorAssociation:
        """Require the exact point-result chain for every numeric outcome."""
        if self.job_completed_event.event_type != "job_completed":
            raise ValueError("owned_attempt_association_completion_event_invalid")
        if self.job_completed_event.job_id != self.job_id:
            raise ValueError("owned_attempt_association_completion_job_mismatch")
        if self.search_uncertainty_task_binding_ref is not None and (
            self.search_uncertainty_task_binding_ref.kind
            != "scientist.search.uncertainty_task_binding"
            or self.search_uncertainty_task_binding_ref.media_type != "application/json"
        ):
            raise ValueError("owned_attempt_association_search_binding_ref_invalid")
        if self.materialization_binding_ref is not None and (
            self.materialization_binding_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("owned_attempt_association_materialization_profile_missing")
        has_point_result = self.point_result_ref is not None
        has_hte_result = self.hte_result_ref is not None
        has_basis = self.inference_basis_ref is not None
        if self.outcome_kind == "point_estimate" and (not has_point_result or has_hte_result):
            raise ValueError("owned_attempt_association_point_result_chain_invalid")
        if self.outcome_kind == "interval_estimate" and (
            has_point_result or not has_hte_result or not has_basis
        ):
            raise ValueError("owned_attempt_association_interval_result_chain_invalid")
        if self.outcome_kind == "refusal" and any((has_point_result, has_hte_result, has_basis)):
            raise ValueError("owned_attempt_association_refusal_has_numeric_result")
        if (self.outcome_kind == "refusal") != (self.refusal_diagnostic_ref is not None):
            raise ValueError("owned_attempt_association_refusal_diagnostic_mismatch")
        if has_hte_result and (
            self.hte_result_ref.kind != "ir.hte_result"
            or self.hte_result_ref.media_type != "application/json"
        ):
            raise ValueError("owned_attempt_association_hte_result_ref_invalid")
        if has_basis and self.outcome_kind == "point_estimate" and not has_point_result:
            raise ValueError("owned_attempt_association_diagnostic_basis_without_point")
        return self


class OwnedAttemptAnchorProjectionAssociation(BaseModel):
    """Bind a bounded scalar summary to the current completed owner selection.

    This result reconciles the owner row, terminal event, selected manifest
    identities, and the already worker-admitted scalar-summary digest. It does
    not read or recompute method-result, CATE, or native inference arrays.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["owner_projection_reconciled"] = "owner_projection_reconciled"
    content_validation_status: Literal["worker_admitted_not_recomputed"] = (
        "worker_admitted_not_recomputed"
    )
    manifest_identity_status: Literal["independently_reconciled"] = "independently_reconciled"
    verified_at: datetime
    anchor_ref: OwnedAttemptAnchorRef
    outcome_ref: SelectedArtifactRef
    outcome_kind: Literal["point_estimate", "interval_estimate", "refusal"]
    selected_summary_sha256: str = Field(pattern=_HEX_SHA256)
    source_data_ref: SelectedArtifactRef
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef | None = None
    search_uncertainty_task_binding_ref: SelectedArtifactRef | None = None
    source_data_summary_status: Literal["content_bound"] = "content_bound"
    resource_policy_ref: SelectedArtifactRef
    method_result_ref: SelectedArtifactRef
    method_evidence_ref: SelectedArtifactRef
    invocation_basis_ref: SelectedArtifactRef | None = None
    point_result_ref: SelectedArtifactRef | None = None
    hte_result_ref: SelectedArtifactRef | None = None
    inference_basis_ref: SelectedArtifactRef | None = None
    refusal_diagnostic_ref: SelectedArtifactRef | None = None
    job_completed_event: OwnedAttemptLifecycleEvent
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=256)
    cell_id: str | None = Field(default=None, min_length=1, max_length=256)
    attempt: int = Field(ge=1)

    @field_validator("verified_at")
    @classmethod
    def require_aware_projection_time(cls, value: datetime) -> datetime:
        """Require an aware timestamp for the owner projection reconciliation."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("owned_attempt_projection_time_must_be_aware")
        return value

    @field_validator(
        "outcome_ref",
        "source_data_ref",
        "materialization_binding_ref",
        "search_uncertainty_task_binding_ref",
        "resource_policy_ref",
        "method_result_ref",
        "method_evidence_ref",
        "invocation_basis_ref",
        "point_result_ref",
        "hte_result_ref",
        "inference_basis_ref",
        "refusal_diagnostic_ref",
    )
    @classmethod
    def require_projection_selected_profiles(
        cls, value: SelectedArtifactRef | None
    ) -> SelectedArtifactRef | None:
        """Require every selected manifest view carried by the projection."""
        if value is not None and value.manifest_profile_sha256 is None:
            raise ValueError("owned_attempt_projection_selected_profile_missing")
        return value

    @model_validator(mode="after")
    def require_projection_result_chain(self) -> OwnedAttemptAnchorProjectionAssociation:
        """Keep scalar outcome kind, selected refs, and terminal owner event aligned."""
        if self.job_completed_event.event_type != "job_completed" or (
            self.job_completed_event.job_id != self.job_id
        ):
            raise ValueError("owned_attempt_projection_completion_event_mismatch")
        if (
            self.outcome_ref.kind != "ir.hte_outcome"
            or self.source_data_ref.kind != "ir.observation_method_input"
            or self.resource_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.method_result_ref.kind != "scientist.method_result.causal.hte"
            or self.method_evidence_ref.kind != "scientist.method_evidence"
        ):
            raise ValueError("owned_attempt_projection_ref_kind_mismatch")
        if self.search_uncertainty_task_binding_ref is not None and (
            self.search_uncertainty_task_binding_ref.kind
            != "scientist.search.uncertainty_task_binding"
            or self.search_uncertainty_task_binding_ref.media_type != "application/json"
        ):
            raise ValueError("owned_attempt_projection_search_binding_ref_invalid")
        if self.materialization_binding_ref is not None and (
            self.materialization_binding_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("owned_attempt_projection_materialization_profile_missing")
        if self.outcome_kind == "point_estimate":
            if (
                self.point_result_ref is None
                or self.hte_result_ref is not None
                or self.refusal_diagnostic_ref is not None
            ):
                raise ValueError("owned_attempt_projection_point_result_chain_invalid")
        elif self.outcome_kind == "interval_estimate":
            if (
                self.point_result_ref is not None
                or self.hte_result_ref is None
                or self.inference_basis_ref is None
                or self.refusal_diagnostic_ref is not None
            ):
                raise ValueError("owned_attempt_projection_interval_result_chain_invalid")
        elif (
            any(
                ref is not None
                for ref in (
                    self.point_result_ref,
                    self.hte_result_ref,
                    self.inference_basis_ref,
                )
            )
            or self.refusal_diagnostic_ref is None
        ):
            raise ValueError("owned_attempt_projection_refusal_result_chain_invalid")
        if (
            (
                self.point_result_ref is not None
                and self.point_result_ref.kind != "ir.hte_point_result"
            )
            or (self.hte_result_ref is not None and self.hte_result_ref.kind != "ir.hte_result")
            or (
                self.inference_basis_ref is not None
                and self.inference_basis_ref.kind != "ir.ate_inference_basis"
            )
            or (
                self.refusal_diagnostic_ref is not None
                and self.refusal_diagnostic_ref.kind != "ir.hte_refusal_diagnostic"
            )
        ):
            raise ValueError("owned_attempt_projection_optional_ref_kind_mismatch")
        if (
            self.outcome_kind in {"point_estimate", "interval_estimate"}
            and self.source_data_summary_status != "content_bound"
        ):
            raise ValueError("owned_attempt_projection_source_status_mismatch")
        return self


class OwnedAttemptAnchorRefusalAssociation(BaseModel):
    """Return a failed-input anchor reconciled to its current failed owner event.

    This result contains no method output refs. It establishes only that an
    owner-fenced preparation refusal belongs to the current failed attempt.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["input_refusal_reconciled"] = "input_refusal_reconciled"
    verified_at: datetime
    anchor_ref: OwnedAttemptAnchorRef
    refusal: OwnedAttemptHTEInputRefusal
    requested_source_ref: SelectedArtifactRef
    search_uncertainty_task_binding_ref: SelectedArtifactRef | None = None
    observational_run_intent_ref: SelectedArtifactRef
    resource_policy_ref: SelectedArtifactRef
    job_failed_event: OwnedAttemptLifecycleEvent
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1)

    @field_validator("verified_at")
    @classmethod
    def require_aware_verification_time(cls, value: datetime) -> datetime:
        """Require an aware timestamp for this owner reconciliation read."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("owned_attempt_refusal_association_time_must_be_aware")
        return value

    @field_validator(
        "requested_source_ref",
        "search_uncertainty_task_binding_ref",
        "observational_run_intent_ref",
        "resource_policy_ref",
    )
    @classmethod
    def require_selected_profiles(
        cls, value: SelectedArtifactRef | None
    ) -> SelectedArtifactRef | None:
        """Require exact selected-profile refs on the owner request chain."""
        if value is not None and value.manifest_profile_sha256 is None:
            raise ValueError("owned_attempt_refusal_association_profile_missing")
        return value

    @model_validator(mode="after")
    def require_failed_owner_identity(self) -> OwnedAttemptAnchorRefusalAssociation:
        """Bind the result's refusal and event to one failed owner attempt."""
        if (
            self.job_failed_event.event_type != "job_failed"
            or self.job_failed_event.job_id != self.job_id
        ):
            raise ValueError("owned_attempt_refusal_association_failed_event_mismatch")
        if (
            self.requested_source_ref.kind
            not in {"ir.observation_method_input", "ir.observational_data"}
            or self.observational_run_intent_ref.kind != "runtime.observational_run_intent"
            or self.resource_policy_ref.kind != "runtime.observational_input_resource_policy"
        ):
            raise ValueError("owned_attempt_refusal_association_ref_kind_mismatch")
        if self.search_uncertainty_task_binding_ref is not None and (
            self.search_uncertainty_task_binding_ref.kind
            != "scientist.search.uncertainty_task_binding"
            or self.search_uncertainty_task_binding_ref.media_type != "application/json"
        ):
            raise ValueError("owned_attempt_refusal_search_binding_ref_invalid")
        return self


__all__ = [
    "OWNED_ATTEMPT_ANCHOR_KIND",
    "OWNED_ATTEMPT_ANCHOR_SCHEMA_NAME",
    "OWNED_ATTEMPT_ANCHOR_SCHEMA_VERSION",
    "OwnedAttemptAnchor",
    "OwnedAttemptAnchorAssociation",
    "OwnedAttemptAnchorDispatchContext",
    "OwnedAttemptAnchorProjectionAssociation",
    "OwnedAttemptAnchorRef",
    "OwnedAttemptAnchorRefusalAssociation",
    "OwnedAttemptHTEInputAdmitted",
    "OwnedAttemptHTEInputCapture",
    "OwnedAttemptHTEInputRefusal",
    "OwnedAttemptHTEInputRefused",
    "OwnedAttemptInputAdmission",
    "OwnedAttemptLifecycleEvent",
    "OwnedAttemptPhysicalSourceBindingRef",
    "OwnedAttemptPredicateOrigins",
    "OwnedHTERequestContextV1",
    "SelectedArtifactRef",
]
