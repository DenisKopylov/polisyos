"""Persist and verify a candidate-only HTE scope over exact selected source rows.

The owner binds Runtime's immutable HTE request selectors to the physically
materialized source rows. Request-to-source semantic mappings remain declared
candidate predicates; this artifact does not establish causal meaning, units,
population identity, currentness, or authority.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, TypeGuard

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core.artifacts import (
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStore,
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
)
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ArtifactRef,
    ArtifactTenantContextInfo,
    CanonInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptPhysicalSourceBindingRef,
    OwnedHTERequestContextV1,
    SelectedArtifactRef,
)
from polisyos.foundry.data_plane.bindings import (
    HTEInputPreparationRefusal,
    HTEPhysicalSourceMaterializationBinding,
    PreparedHTEObservationalInput,
    load_hte_physical_source_materialization_binding,
    materialize_method_contract,
)
from polisyos.foundry.methods import MethodSignature
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.observation.bundles import (
    HTE_OBSERVATIONAL_DATA_TARGET,
    OBSERVATION_METHOD_INPUT_KIND,
    ObservationMethodInputEnvelope,
)

HTE_CANDIDATE_SCOPE_BINDING_KIND = "foundry.hte.selected_row_candidate_scope_binding"
HTE_CANDIDATE_SCOPE_BINDING_SCHEMA = SchemaInfo(
    name="polisyos.foundry.HTESelectedRowCandidateScopeBinding",
    version="1.0",
)
HTE_CANDIDATE_SCOPE_ROLE_KIND = "foundry.hte.selected_row_candidate_scope_role"
HTE_CANDIDATE_SCOPE_ROLE_SCHEMA = SchemaInfo(
    name="polisyos.foundry.HTESelectedRowCandidateScopeRoleProjection",
    version="1.0",
)
HTE_CANDIDATE_SCOPE_MEDIA_TYPE = "application/json"
_CANDIDATE_SCOPE_DISCRIMINATOR = "policyos.foundry.hte.selected_row_candidate_scope_binding.v1"
_CANDIDATE_SCOPE_ROLE_DISCRIMINATOR = "policyos.foundry.hte.selected_row_candidate_scope_role.v1"
_CANDIDATE_SCOPE_PRODUCER = "polisyos.foundry.data_plane.selected_row_candidate_scope"
_CANDIDATE_SCOPE_PRODUCER_VERSION = "1.0.0"
_SHA256 = r"^sha256:[0-9a-f]{64}$"


class HTECandidateScopeStore(
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStore,
    Protocol,
):
    """Core store used by the selected-row scope producer and reader."""


class SelectedHTECandidateScopeBindingRef(SelectedArtifactRef):
    """Select one exact profile-qualified candidate scope binding."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: str = Field(
        default=HTE_CANDIDATE_SCOPE_BINDING_KIND,
        json_schema_extra={"const": HTE_CANDIDATE_SCOPE_BINDING_KIND},
    )
    media_type: str = Field(
        default=HTE_CANDIDATE_SCOPE_MEDIA_TYPE,
        json_schema_extra={"const": HTE_CANDIDATE_SCOPE_MEDIA_TYPE},
    )

    @model_validator(mode="after")
    def _require_binding_owner_identity(self) -> SelectedHTECandidateScopeBindingRef:
        if (
            self.kind != HTE_CANDIDATE_SCOPE_BINDING_KIND
            or self.media_type != HTE_CANDIDATE_SCOPE_MEDIA_TYPE
        ):
            raise ValueError("candidate_scope_binding_ref_identity_mismatch")
        return self


class SelectedHTECandidateScopeRoleRef(SelectedArtifactRef):
    """Select one exact profile-qualified candidate scope role projection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: str = Field(
        default=HTE_CANDIDATE_SCOPE_ROLE_KIND,
        json_schema_extra={"const": HTE_CANDIDATE_SCOPE_ROLE_KIND},
    )
    media_type: str = Field(
        default=HTE_CANDIDATE_SCOPE_MEDIA_TYPE,
        json_schema_extra={"const": HTE_CANDIDATE_SCOPE_MEDIA_TYPE},
    )

    @model_validator(mode="after")
    def _require_role_owner_identity(self) -> SelectedHTECandidateScopeRoleRef:
        if (
            self.kind != HTE_CANDIDATE_SCOPE_ROLE_KIND
            or self.media_type != HTE_CANDIDATE_SCOPE_MEDIA_TYPE
        ):
            raise ValueError("candidate_scope_role_ref_identity_mismatch")
        return self


class HTECandidateSelectedMethodProfile(BaseModel):
    """Freeze the actual selected HTE method ABI and its declared profile."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    method_fqn: str = Field(min_length=1, max_length=256)
    method_version: str = Field(min_length=1, max_length=64)
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: str = Field(min_length=1, max_length=256)


class HTECandidatePhysicalSlot(BaseModel):
    """Copy one exact array slot commitment from the existing physical owner."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    physical_slot: Literal[
        "outcome_vector",
        "treatment_vector",
        "covariate_matrix_column",
        "confounder_matrix_column",
    ]
    payload_pointer: str = Field(pattern=r"^/contract_payload/[a-z_]+$")
    component_index: int | None = Field(default=None, ge=0)
    array_shape: tuple[int, ...] = Field(min_length=1)
    array_dtype: str = Field(min_length=1, max_length=32)
    value_sha256: str = Field(pattern=_SHA256)
    row_order_sha256: str = Field(pattern=_SHA256)


class HTESelectedRowCandidateScopeBinding(BaseModel):
    """Persist selected-row identity while keeping semantic claims candidate-only."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.foundry.hte.selected_row_candidate_scope_binding.v1"] = (
        _CANDIDATE_SCOPE_DISCRIMINATOR
    )
    binding_scope: Literal["candidate_selected_evaluation_rows_only"] = (
        "candidate_selected_evaluation_rows_only"
    )
    semantic_alignment_status: Literal["not_established"] = "not_established"
    submitted_ref: ArtifactRef
    effective_ref: ArtifactRef
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef
    effective_artifact_schema: SchemaInfo
    request_context: OwnedHTERequestContextV1
    request_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_method: HTECandidateSelectedMethodProfile
    requested_target_scope: Literal["selected_evaluation_rows"]
    target_scope_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    requested_estimand: Literal["mean_effect_over_selected_x"]
    quantity_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    outcome_variable_id: str = Field(min_length=1, max_length=256)
    outcome_physical_slot: Literal["outcome_vector"] = "outcome_vector"
    outcome_slot_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    treatment_variable_id: str = Field(min_length=1, max_length=256)
    treatment_physical_slot: Literal["treatment_vector"] = "treatment_vector"
    treatment_slot_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    control_value: float
    treated_value: float
    control_rows: int = Field(ge=1, strict=True)
    treated_rows: int = Field(ge=1, strict=True)
    observed_arm_presence_status: Literal["recomputed"] = "recomputed"
    observation_count: int = Field(ge=40, strict=True)
    row_order_basis: Literal["sample_ids", "positional_row_ordinal"]
    row_order_sha256: str = Field(pattern=_SHA256)
    outcome_value_sha256: str = Field(pattern=_SHA256)
    treatment_value_sha256: str = Field(pattern=_SHA256)
    selected_x_shape: tuple[int, int]
    selected_x_value_sha256: str = Field(pattern=_SHA256)
    physical_slots: tuple[HTECandidatePhysicalSlot, ...] = Field(min_length=2)
    unit_scope_status: Literal["unknown"] = "unknown"
    computed_estimand_status: Literal["not_established"] = "not_established"
    computed_target_scope_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _coherent_candidate_scope(self) -> HTESelectedRowCandidateScopeBinding:
        context = self.request_context
        if (
            context.request_estimand_status != "declared"
            or context.request_estimand != self.requested_estimand
            or context.request_target_scope_status != "declared"
            or context.request_target_scope != self.requested_target_scope
            or context.outcome_variable_status != "declared"
            or context.outcome_variable_id != self.outcome_variable_id
            or context.treatment_variable_status != "declared"
            or context.treatment_variable_id != self.treatment_variable_id
            or context.contrast_status != "declared"
            or context.control_value != self.control_value
            or context.treated_value != self.treated_value
        ):
            raise ValueError("hte_candidate_scope_request_context_mismatch")
        if (
            self.control_value == self.treated_value
            or self.control_rows + self.treated_rows != self.observation_count
        ):
            raise ValueError("hte_candidate_scope_contrast_rows_invalid")
        if self.outcome_variable_id == self.treatment_variable_id:
            raise ValueError("hte_candidate_scope_request_variables_must_differ")
        if self.materialization_binding_ref.manifest_profile_sha256 is None:
            raise ValueError("hte_candidate_scope_physical_profile_required")
        if self.submitted_ref.manifest_profile_sha256 is None:
            raise ValueError("hte_candidate_scope_submitted_profile_required")
        if self.effective_ref.manifest_profile_sha256 is None:
            raise ValueError("hte_candidate_scope_effective_profile_required")
        slots = {(item.physical_slot, item.component_index) for item in self.physical_slots}
        if (
            ("outcome_vector", None) not in slots
            or ("treatment_vector", None) not in slots
            or len(slots) != len(self.physical_slots)
        ):
            raise ValueError("hte_candidate_scope_physical_slot_inventory_invalid")
        if any(item.row_order_sha256 != self.row_order_sha256 for item in self.physical_slots):
            raise ValueError("hte_candidate_scope_slot_row_order_mismatch")
        return self


class _HTECandidateScopeRoleBase(BaseModel):
    """Shared selected-source, request, method, and row identity for one role."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.foundry.hte.selected_row_candidate_scope_role.v1"] = (
        _CANDIDATE_SCOPE_ROLE_DISCRIMINATOR
    )
    candidate_scope_binding_ref: SelectedHTECandidateScopeBindingRef
    submitted_ref: ArtifactRef
    effective_ref: ArtifactRef
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef
    request_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_method: HTECandidateSelectedMethodProfile
    semantic_alignment_status: Literal["not_established"] = "not_established"
    observation_count: int = Field(ge=40, strict=True)
    row_order_basis: Literal["sample_ids", "positional_row_ordinal"]
    row_order_sha256: str = Field(pattern=_SHA256)


class HTEQuantityRoleProjection(_HTECandidateScopeRoleBase):
    """Project the declared quantity selector without claiming computed meaning."""

    role: Literal["quantity"] = "quantity"
    requested_estimand: Literal["mean_effect_over_selected_x"]
    quantity_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    computed_estimand_status: Literal["not_established"] = "not_established"


class HTETreatmentContrastRoleProjection(_HTECandidateScopeRoleBase):
    """Project request contrast values and recomputed arm presence on these rows."""

    role: Literal["treatment_contrast"] = "treatment_contrast"
    treatment_variable_id: str = Field(min_length=1, max_length=256)
    physical_slot: Literal["treatment_vector"] = "treatment_vector"
    slot_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    control_value: float
    treated_value: float
    control_rows: int = Field(ge=1, strict=True)
    treated_rows: int = Field(ge=1, strict=True)
    observed_arm_presence_status: Literal["recomputed"] = "recomputed"


class HTEPopulationRoleProjection(_HTECandidateScopeRoleBase):
    """Project exact selected rows with an explicitly unknown unit."""

    role: Literal["population"] = "population"
    requested_target_scope: Literal["selected_evaluation_rows"]
    target_scope_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    selected_rows_status: Literal["recomputed"] = "recomputed"
    unit_scope_status: Literal["unknown"] = "unknown"


class HTEOutcomeRoleProjection(_HTECandidateScopeRoleBase):
    """Project one request-declared outcome ID onto its exact source vector."""

    role: Literal["outcome"] = "outcome"
    outcome_variable_id: str = Field(min_length=1, max_length=256)
    physical_slot: Literal["outcome_vector"] = "outcome_vector"
    payload_pointer: Literal["/contract_payload/outcome"] = "/contract_payload/outcome"
    slot_mapping_origin: Literal["consumer_asserted"] = "consumer_asserted"
    outcome_value_sha256: str = Field(pattern=_SHA256)


_REQUIRED_ROLES = frozenset({"quantity", "treatment_contrast", "population", "outcome"})


class _HTESelectedMethodClass(Protocol):
    signature: ClassVar[MethodSignature]
    owned_hte_profile_id: ClassVar[str]


@dataclass(frozen=True, slots=True)
class HTECandidateSelectedMethodIdentity:
    """Carry the actual selected class beside its admitted FQN/version/ABI.

    The selected class must come from Runtime's exact registry resolution. This
    DTO is only a join input: the producer recomputes its signature and profile
    and refuses any disagreement with the admitted identity.
    """

    method_class: type[_HTESelectedMethodClass]
    method_fqn: str
    method_version: str
    method_abi_digest: str


class HTECandidateScopeRoleRefs(BaseModel):
    """Exact selected-profile role refs required by the Search semantic scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    quantity_ref: SelectedHTECandidateScopeRoleRef
    treatment_contrast_ref: SelectedHTECandidateScopeRoleRef
    population_ref: SelectedHTECandidateScopeRoleRef
    outcome_ref: SelectedHTECandidateScopeRoleRef

    @model_validator(mode="after")
    def _unique_role_refs(self) -> HTECandidateScopeRoleRefs:
        refs = (
            self.quantity_ref,
            self.treatment_contrast_ref,
            self.population_ref,
            self.outcome_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("hte_candidate_scope_role_profile_required")
        if len({(str(ref.artifact_id), ref.manifest_profile_sha256) for ref in refs}) != len(refs):
            raise ValueError("hte_candidate_scope_role_refs_must_be_distinct")
        return self


class HTESelectedRowCandidateScopeArtifacts(BaseModel):
    """Return one binding plus the four independently typed Search role refs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding_ref: SelectedHTECandidateScopeBindingRef
    roles: HTECandidateScopeRoleRefs


class HTESelectedRowCandidateScopeRead(BaseModel):
    """Return the exact persisted candidate binding and freshly read role owners."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding: HTESelectedRowCandidateScopeBinding
    binding_ref: SelectedHTECandidateScopeBindingRef
    quantity: HTEQuantityRoleProjection
    treatment_contrast: HTETreatmentContrastRoleProjection
    population: HTEPopulationRoleProjection
    outcome: HTEOutcomeRoleProjection


def _refusal(code: str) -> HTEInputPreparationRefusal:
    """Build one stable typed HTE pre-output refusal."""
    return HTEInputPreparationRefusal(code, failure_stage="candidate_scope_owner")


def _as_core_artifact_ref(ref: ArtifactRef) -> ArtifactRef:
    """Project a bounded selector subclass to Core's exact base reference type."""
    try:
        return ArtifactRef.model_validate(ref.model_dump(mode="json"), strict=True)
    except Exception as exc:
        raise _refusal("candidate_scope_artifact_ref_invalid") from exc


def _request_context_sha256(
    context: OwnedHTERequestContextV1,
    *,
    max_depth: int,
) -> str:
    """Hash the exact JSON representation of Runtime's frozen request context."""
    payload = context.model_dump(mode="json", exclude_none=False)
    encoded = to_canonical_bytes(
        payload,
        CanonSpec(
            forbid_floats=False,
            forbid_nan_inf=True,
            exclude_none=False,
            max_depth=max_depth,
        ),
    )
    return hashlib.sha256(encoded).hexdigest()


def _value_sha256(value: object, *, max_depth: int) -> str:
    """Hash one materialized value using the selected input's canonical bounds."""
    encoded = to_canonical_bytes(
        value,
        CanonSpec(
            forbid_floats=False,
            forbid_nan_inf=True,
            exclude_none=False,
            max_depth=max_depth,
        ),
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _is_selected_hte_method_class(
    value: object,
) -> TypeGuard[type[_HTESelectedMethodClass]]:
    """Narrow a selected class only after checking its actual ABI fields."""
    if type(value) is not type:
        return False
    signature = getattr(value, "signature", None)
    profile_id = getattr(value, "owned_hte_profile_id", None)
    return (
        isinstance(signature, MethodSignature)
        and type(profile_id) is str
        and bool(profile_id.strip())
    )


def _selected_method_profile(
    identity: HTECandidateSelectedMethodIdentity,
    *,
    expected_fqn: str | None = None,
) -> HTECandidateSelectedMethodProfile:
    """Reconcile Runtime's admitted identity to its actual selected class."""
    if type(identity) is not HTECandidateSelectedMethodIdentity:
        raise _refusal("candidate_scope_selected_method_identity_type_invalid")
    if (
        not _is_selected_hte_method_class(identity.method_class)
        or type(identity.method_fqn) is not str
        or type(identity.method_version) is not str
        or type(identity.method_abi_digest) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", identity.method_abi_digest)
    ):
        raise _refusal("candidate_scope_selected_method_identity_invalid")
    method_class = identity.method_class
    signature = method_class.signature
    profile_id = method_class.owned_hte_profile_id
    if (
        signature.fqn != identity.method_fqn
        or signature.version != identity.method_version
        or signature.abi_digest() != identity.method_abi_digest
        or (expected_fqn is not None and signature.fqn != expected_fqn)
    ):
        raise _refusal("candidate_scope_selected_method_identity_mismatch")
    return HTECandidateSelectedMethodProfile(
        method_fqn=signature.fqn,
        method_version=signature.version,
        method_abi_digest=identity.method_abi_digest,
        method_profile_id=profile_id,
    )


@dataclass(frozen=True, slots=True)
class _RequiredHTECandidateRequest:
    outcome_variable_id: str
    treatment_variable_id: str
    control_value: float
    treated_value: float


def _required_request_context(
    context: OwnedHTERequestContextV1,
) -> _RequiredHTECandidateRequest:
    """Require declared selectors and return their validated values."""
    if (
        type(context) is not OwnedHTERequestContextV1
        or context.request_estimand_status != "declared"
        or context.request_estimand != "mean_effect_over_selected_x"
        or context.request_target_scope_status != "declared"
        or context.request_target_scope != "selected_evaluation_rows"
        or context.outcome_variable_status != "declared"
        or type(context.outcome_variable_id) is not str
        or not context.outcome_variable_id.strip()
        or context.treatment_variable_status != "declared"
        or type(context.treatment_variable_id) is not str
        or not context.treatment_variable_id.strip()
        or context.contrast_status != "declared"
        or type(context.control_value) is not float
        or type(context.treated_value) is not float
    ):
        raise _refusal("candidate_scope_required_request_selectors_not_established")
    if context.outcome_variable_id == context.treatment_variable_id:
        raise _refusal("candidate_scope_request_variables_must_differ")
    return _RequiredHTECandidateRequest(
        outcome_variable_id=context.outcome_variable_id,
        treatment_variable_id=context.treatment_variable_id,
        control_value=context.control_value,
        treated_value=context.treated_value,
    )


def _read_effective_data(
    store: HTECandidateScopeStore,
    *,
    effective_ref: ArtifactRef,
    effective_schema: SchemaInfo,
    limits: CoreJsonReadLimits,
) -> HTEObservationalData:
    """Reopen one exact selected effective HTE envelope through bounded Core."""
    try:
        selected = read_core_json_artifact_bounded(store, effective_ref, limits=limits)
        if (
            selected.effective_ref != effective_ref
            or selected.manifest.kind != OBSERVATION_METHOD_INPUT_KIND
            or selected.manifest.media_type != "application/json"
            or selected.manifest.artifact_schema != effective_schema
        ):
            raise _refusal("candidate_scope_effective_source_identity_mismatch")
        value = require_declared_profile(selected.profile_read)
        if not isinstance(value, dict):
            raise _refusal("candidate_scope_effective_source_payload_invalid")
        envelope = ObservationMethodInputEnvelope.model_validate(value, strict=True)
        try:
            value = materialize_method_contract(
                contract_target=HTE_OBSERVATIONAL_DATA_TARGET,
                contract_payload=envelope.contract_payload,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _refusal("invalid_hte_observational_data") from exc
        if not isinstance(value, HTEObservationalData):
            raise _refusal("hte_target_materializer_mismatch")
        return value
    except HTEInputPreparationRefusal:
        raise
    except CoreJsonReadBoundsRefusalError as exc:
        raise _refusal("candidate_scope_effective_source_bounds_refused") from exc
    except Exception as exc:
        raise _refusal("candidate_scope_effective_source_read_refused") from exc


def _physical_slots(
    binding: HTEPhysicalSourceMaterializationBinding,
) -> tuple[HTECandidatePhysicalSlot, ...]:
    """Copy the entire existing physical slot inventory without reinterpretation."""
    return tuple(
        HTECandidatePhysicalSlot(
            physical_slot=item.physical_slot,
            payload_pointer=item.payload_pointer,
            component_index=item.component_index,
            array_shape=item.array_shape,
            array_dtype=item.array_dtype,
            value_sha256=item.value_sha256,
            row_order_sha256=item.row_order_sha256,
        )
        for item in binding.arrays
    )


def _compose_binding(
    *,
    submitted_ref: ArtifactRef,
    effective_ref: ArtifactRef,
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef,
    effective_artifact_schema: SchemaInfo,
    request_context: OwnedHTERequestContextV1,
    selected_method: HTECandidateSelectedMethodProfile,
    physical_binding: HTEPhysicalSourceMaterializationBinding,
    data: HTEObservationalData,
    limits: CoreJsonReadLimits,
) -> HTESelectedRowCandidateScopeBinding:
    """Recompute exact selected arrays and compose the bounded candidate owner."""
    selectors = _required_request_context(request_context)
    if (
        physical_binding.submitted_ref != submitted_ref
        or physical_binding.effective_ref != effective_ref
        or physical_binding.observation_count != data.n_obs
    ):
        raise _refusal("candidate_scope_physical_source_join_mismatch")

    by_slot = {item.physical_slot: item for item in physical_binding.arrays}
    outcome_slot = by_slot.get("outcome_vector")
    treatment_slot = by_slot.get("treatment_vector")
    if outcome_slot is None or treatment_slot is None:
        raise _refusal("candidate_scope_required_physical_slots_missing")

    outcome_digest = _value_sha256(data.outcome.tolist(), max_depth=limits.max_depth)
    treatment_digest = _value_sha256(data.treatment.tolist(), max_depth=limits.max_depth)
    if (
        outcome_digest != outcome_slot.value_sha256
        or treatment_digest != treatment_slot.value_sha256
    ):
        raise _refusal("candidate_scope_physical_slot_value_mismatch")

    control = selectors.control_value
    treated = selectors.treated_value
    treatment = np.asarray(data.treatment)
    control_rows = int(np.count_nonzero(treatment == control))
    treated_rows = int(np.count_nonzero(treatment == treated))
    if control_rows < 1 or treated_rows < 1 or control_rows + treated_rows != data.n_obs:
        raise _refusal("candidate_scope_requested_contrast_not_observed_on_selected_rows")

    if data.confounders is None:
        selected_x = np.asarray(data.covariates)
    else:
        selected_x = np.column_stack((data.covariates, data.confounders))
    selected_x_digest = _value_sha256(selected_x.tolist(), max_depth=limits.max_depth)
    request_digest = _request_context_sha256(request_context, max_depth=limits.max_depth)
    return HTESelectedRowCandidateScopeBinding(
        submitted_ref=submitted_ref,
        effective_ref=effective_ref,
        materialization_binding_ref=materialization_binding_ref,
        effective_artifact_schema=effective_artifact_schema,
        request_context=request_context,
        request_context_sha256=request_digest,
        selected_method=selected_method,
        requested_target_scope="selected_evaluation_rows",
        requested_estimand="mean_effect_over_selected_x",
        outcome_variable_id=selectors.outcome_variable_id,
        treatment_variable_id=selectors.treatment_variable_id,
        control_value=control,
        treated_value=treated,
        control_rows=control_rows,
        treated_rows=treated_rows,
        observation_count=data.n_obs,
        row_order_basis=physical_binding.row_order_basis,
        row_order_sha256=physical_binding.row_order_sha256,
        outcome_value_sha256=outcome_digest,
        treatment_value_sha256=treatment_digest,
        selected_x_shape=(int(selected_x.shape[0]), int(selected_x.shape[1])),
        selected_x_value_sha256=selected_x_digest,
        physical_slots=_physical_slots(physical_binding),
    )


@dataclass(frozen=True, slots=True)
class _HTECandidateRoleProjectionSet:
    quantity: HTEQuantityRoleProjection
    treatment_contrast: HTETreatmentContrastRoleProjection
    population: HTEPopulationRoleProjection
    outcome: HTEOutcomeRoleProjection

    def items(self) -> tuple[tuple[str, BaseModel], ...]:
        return (
            ("quantity", self.quantity),
            ("treatment_contrast", self.treatment_contrast),
            ("population", self.population),
            ("outcome", self.outcome),
        )


def _role_projections(
    *,
    binding_ref: SelectedHTECandidateScopeBindingRef,
    binding: HTESelectedRowCandidateScopeBinding,
) -> _HTECandidateRoleProjectionSet:
    """Build the complete four-role set from the selected scope owner."""
    common = {
        "candidate_scope_binding_ref": binding_ref,
        "submitted_ref": binding.submitted_ref,
        "effective_ref": binding.effective_ref,
        "materialization_binding_ref": binding.materialization_binding_ref,
        "request_context_sha256": binding.request_context_sha256,
        "selected_method": binding.selected_method,
        "observation_count": binding.observation_count,
        "row_order_basis": binding.row_order_basis,
        "row_order_sha256": binding.row_order_sha256,
    }
    projections = _HTECandidateRoleProjectionSet(
        quantity=HTEQuantityRoleProjection(
            **common,
            requested_estimand=binding.requested_estimand,
        ),
        treatment_contrast=HTETreatmentContrastRoleProjection(
            **common,
            treatment_variable_id=binding.treatment_variable_id,
            control_value=binding.control_value,
            treated_value=binding.treated_value,
            control_rows=binding.control_rows,
            treated_rows=binding.treated_rows,
        ),
        population=HTEPopulationRoleProjection(
            **common,
            requested_target_scope=binding.requested_target_scope,
        ),
        outcome=HTEOutcomeRoleProjection(
            **common,
            outcome_variable_id=binding.outcome_variable_id,
            outcome_value_sha256=binding.outcome_value_sha256,
        ),
    )
    if frozenset(role for role, _ in projections.items()) != _REQUIRED_ROLES:
        raise _refusal("candidate_scope_required_role_inventory_invalid")
    return projections


def _input_edges(refs: tuple[tuple[str, ArtifactRef], ...]) -> list[InputRef]:
    """Create one exact selected profile lineage edge for every owner input."""
    return [input_ref_from_artifact_ref(ref, role=role) for role, ref in refs]


def _edge_keys(edges: tuple[InputRef, ...] | list[InputRef]) -> list[tuple[str, str, str | None]]:
    """Normalize manifest edges for order-independent exact comparison."""
    return sorted(
        (
            str(edge.artifact_id),
            edge.role,
            edge.manifest_profile_sha256,
        )
        for edge in edges
    )


def _persist_model(
    store: HTECandidateScopeStore,
    *,
    model: BaseModel,
    kind: str,
    schema: SchemaInfo,
    inputs: list[InputRef],
    governance: ArtifactGovernanceInfo | None,
    tenant_context: ArtifactTenantContextInfo | None,
    limits: CoreJsonReadLimits,
) -> ArtifactRef:
    """Persist one strict selected-profile JSON owner with bounded content."""
    payload = model.model_dump(mode="json", exclude_none=False)
    spec = CanonSpec(
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=False,
        max_depth=limits.max_depth,
    )
    encoded = to_canonical_bytes(payload, spec)
    if len(encoded) > limits.max_bytes:
        raise _refusal("candidate_scope_artifact_exceeds_byte_limit")
    if _element_count(payload, stop_after=limits.max_elements) > limits.max_elements:
        raise _refusal("candidate_scope_artifact_exceeds_element_limit")
    try:
        ref = store.put_bytes(
            encoded,
            PutOptions(
                kind=kind,
                media_type=HTE_CANDIDATE_SCOPE_MEDIA_TYPE,
                schema=schema,
                producer=ProducerInfo(
                    component=_CANDIDATE_SCOPE_PRODUCER,
                    version=_CANDIDATE_SCOPE_PRODUCER_VERSION,
                ),
                inputs=inputs,
                canon=CanonInfo.from_spec(spec),
                governance=governance,
                tenant_context=tenant_context,
            ),
            return_selected_profile=True,
        )
    except Exception as exc:
        raise _refusal("candidate_scope_artifact_write_refused") from exc
    if type(ref) is not ArtifactRef or not ref.manifest_profile_sha256:
        raise _refusal("candidate_scope_artifact_profile_missing")
    return ref


def _persist_role_projection(
    store: HTECandidateScopeStore,
    *,
    model: BaseModel,
    binding_ref: SelectedHTECandidateScopeBindingRef,
    effective_ref: ArtifactRef,
    physical_binding_ref: ArtifactRef,
    governance: ArtifactGovernanceInfo | None,
    tenant_context: ArtifactTenantContextInfo | None,
    limits: CoreJsonReadLimits,
) -> SelectedHTECandidateScopeRoleRef:
    """Persist one role with its exact selected binding and source lineage."""
    raw_ref = _persist_model(
        store,
        model=model,
        kind=HTE_CANDIDATE_SCOPE_ROLE_KIND,
        schema=HTE_CANDIDATE_SCOPE_ROLE_SCHEMA,
        inputs=_input_edges(
            (
                ("candidate_scope_binding", binding_ref),
                ("effective_source", effective_ref),
                ("physical_materialization", physical_binding_ref),
            )
        ),
        governance=governance,
        tenant_context=tenant_context,
        limits=limits,
    )
    try:
        return SelectedHTECandidateScopeRoleRef.model_validate(
            raw_ref.model_dump(mode="json"),
            strict=True,
        )
    except Exception as exc:
        raise _refusal("candidate_scope_role_ref_invalid") from exc


def _element_count(value: object, *, stop_after: int) -> int:
    """Count selected JSON nodes without materializing another expanded view."""
    count = 0
    pending = [value]
    while pending:
        current = pending.pop()
        count += 1
        if isinstance(current, Mapping):
            count += len(current)
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
        if count > stop_after:
            return count
    return count


def _is_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """Require a JSON mapping with string keys and retain its values as objects."""
    return type(value) is dict and all(type(key) is str for key in value)


def _strict_model_from_profile_payload[ModelT: BaseModel](
    model_type: type[ModelT],
    payload: dict[str, object],
) -> ModelT:
    """Strictly validate one decoded profile payload, restoring tuple fields."""
    selected_payload = dict(payload)
    if model_type is HTESelectedRowCandidateScopeBinding:
        selected_x_shape = selected_payload.get("selected_x_shape")
        physical_slots = selected_payload.get("physical_slots")
        if type(selected_x_shape) is not list or type(physical_slots) is not list:
            raise _refusal("candidate_scope_artifact_payload_invalid")
        selected_payload["selected_x_shape"] = tuple(selected_x_shape)
        restored_slots: list[dict[str, object]] = []
        for slot in physical_slots:
            if not _is_json_object(slot) or type(slot.get("array_shape")) is not list:
                raise _refusal("candidate_scope_artifact_payload_invalid")
            restored_slot = dict(slot)
            array_shape = restored_slot["array_shape"]
            if type(array_shape) is not list:
                raise _refusal("candidate_scope_artifact_payload_invalid")
            restored_slot["array_shape"] = tuple(array_shape)
            restored_slots.append(restored_slot)
        selected_payload["physical_slots"] = tuple(restored_slots)
    return model_type.model_validate(selected_payload, strict=True)


def _read_model[ModelT: BaseModel](
    store: HTECandidateScopeStore,
    *,
    ref: ArtifactRef,
    expected_kind: str,
    expected_schema: SchemaInfo,
    model_type: type[ModelT],
    limits: CoreJsonReadLimits,
) -> tuple[ModelT, ArtifactManifest]:
    """Resolve a profile-qualified owner with the bounded Core JSON reader."""
    core_ref = _as_core_artifact_ref(ref)
    try:
        selected = read_core_json_artifact_bounded(store, core_ref, limits=limits)
        producer = selected.manifest.producer
        if (
            selected.effective_ref != core_ref
            or selected.manifest.kind != expected_kind
            or selected.manifest.media_type != HTE_CANDIDATE_SCOPE_MEDIA_TYPE
            or selected.manifest.artifact_schema != expected_schema
            or producer is None
            or producer.component != _CANDIDATE_SCOPE_PRODUCER
            or producer.version != _CANDIDATE_SCOPE_PRODUCER_VERSION
        ):
            raise _refusal("candidate_scope_artifact_identity_mismatch")
        payload = require_declared_profile(selected.profile_read)
        if not _is_json_object(payload):
            raise _refusal("candidate_scope_artifact_payload_invalid")
        return _strict_model_from_profile_payload(model_type, payload), selected.manifest
    except HTEInputPreparationRefusal:
        raise
    except CoreJsonReadBoundsRefusalError as exc:
        raise _refusal("candidate_scope_artifact_bounds_refused") from exc
    except Exception as exc:
        raise _refusal("candidate_scope_artifact_read_refused") from exc


def _verify_edges(manifest: ArtifactManifest, expected: list[InputRef]) -> None:
    """Require exact parent roles and profile-qualified refs, with no extras."""
    if _edge_keys(manifest.inputs) != _edge_keys(expected):
        raise _refusal("candidate_scope_artifact_lineage_mismatch")


def _read_role_projection[ModelT: BaseModel](
    store: HTECandidateScopeStore,
    *,
    role: str,
    ref: SelectedHTECandidateScopeRoleRef,
    expected_model: ModelT,
    expected_inputs: list[InputRef],
    limits: CoreJsonReadLimits,
) -> ModelT:
    """Resolve and compare one typed role payload and its exact lineage."""
    model, manifest = _read_model(
        store,
        ref=ref,
        expected_kind=HTE_CANDIDATE_SCOPE_ROLE_KIND,
        expected_schema=HTE_CANDIDATE_SCOPE_ROLE_SCHEMA,
        model_type=type(expected_model),
        limits=limits,
    )
    if model != expected_model:
        raise _refusal(f"candidate_scope_role_recomputation_mismatch:{role}")
    _verify_edges(manifest, expected_inputs)
    return model


def _load_scope_from_source(
    store: HTECandidateScopeStore,
    *,
    submitted_ref: ArtifactRef,
    effective_ref: ArtifactRef,
    materialization_binding_ref: OwnedAttemptPhysicalSourceBindingRef,
    effective_artifact_schema: SchemaInfo,
    request_context: OwnedHTERequestContextV1,
    selected_method_identity: HTECandidateSelectedMethodIdentity,
    limits: CoreJsonReadLimits,
) -> HTESelectedRowCandidateScopeBinding:
    """Reopen source and physical owner, then recompute expected scope."""
    _required_request_context(request_context)
    data = _read_effective_data(
        store,
        effective_ref=effective_ref,
        effective_schema=effective_artifact_schema,
        limits=limits,
    )
    physical = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=_as_core_artifact_ref(materialization_binding_ref),
        expected_submitted_ref=submitted_ref,
        expected_effective_ref=effective_ref,
        limits=limits,
        expected_data=data,
    )
    if (
        request_context.materialization_binding_ref is not None
        and request_context.materialization_binding_ref != materialization_binding_ref
    ):
        raise _refusal("candidate_scope_request_physical_binding_mismatch")
    selected_method = _selected_method_profile(selected_method_identity)
    return _compose_binding(
        submitted_ref=submitted_ref,
        effective_ref=effective_ref,
        materialization_binding_ref=materialization_binding_ref,
        effective_artifact_schema=effective_artifact_schema,
        request_context=request_context,
        selected_method=selected_method,
        physical_binding=physical,
        data=data,
        limits=limits,
    )


def build_hte_selected_row_candidate_scope(
    *,
    store: HTECandidateScopeStore,
    prepared: PreparedHTEObservationalInput,
    physical_binding_ref: OwnedAttemptPhysicalSourceBindingRef | None,
    request_context: OwnedHTERequestContextV1,
    selected_method_identity: HTECandidateSelectedMethodIdentity,
    limits: CoreJsonReadLimits,
) -> HTESelectedRowCandidateScopeArtifacts:
    """Persist one candidate-only selected-row owner and its four Search role refs.

    This function must run in the physical worker after bounded HTE input
    preparation and before method dispatch. It requires the already emitted
    physical-only binding; it never creates or upgrades that binding.

    Args:
        store: Current Runtime worker's Core store.
        prepared: Input decoded by the existing bounded HTE producer.
        physical_binding_ref: Exact profile-qualified physical owner emitted
            during this preparation.
        request_context: Exact immutable request captured by Runtime.
        selected_method_identity: Actual registered class and admitted FQN,
            version, and ABI digest from Runtime.
        limits: The same selected Core resource bounds used by HTE preparation.

    Returns:
        HTESelectedRowCandidateScopeArtifacts: Persisted binding and distinct role refs.

    Raises:
        HTEInputPreparationRefusal: If any selected request, method, physical
            source, content, role, or bounded write cannot be reconciled.
    """
    if type(prepared) is not PreparedHTEObservationalInput:
        raise _refusal("candidate_scope_prepared_input_type_invalid")
    if type(prepared.data) is not HTEObservationalData:
        raise _refusal("candidate_scope_worker_data_type_invalid")
    _required_request_context(request_context)
    raw_physical_ref = prepared.materialization_binding_ref
    if raw_physical_ref is None or physical_binding_ref is None:
        raise _refusal("candidate_scope_physical_binding_required")
    try:
        prepared_physical_ref = OwnedAttemptPhysicalSourceBindingRef.model_validate(
            raw_physical_ref.model_dump(mode="json"),
            strict=True,
        )
        selected_physical_ref = OwnedAttemptPhysicalSourceBindingRef.model_validate(
            physical_binding_ref.model_dump(mode="json"),
            strict=True,
        )
    except Exception as exc:
        raise _refusal("candidate_scope_physical_binding_ref_invalid") from exc
    if prepared_physical_ref != selected_physical_ref:
        raise _refusal("candidate_scope_physical_binding_ref_mismatch")
    if (
        request_context.materialization_binding_ref is not None
        and request_context.materialization_binding_ref != selected_physical_ref
    ):
        raise _refusal("candidate_scope_caller_physical_binding_mismatch")
    physical_ref = selected_physical_ref
    physical_core_ref = _as_core_artifact_ref(physical_ref)

    # The selected physical owner is reopened against both the exact source and
    # the worker-local DTO before any candidate scope artifact is written.
    physical = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=physical_core_ref,
        expected_submitted_ref=prepared.submitted_ref,
        expected_effective_ref=prepared.effective_ref,
        limits=limits,
        expected_data=prepared.data,
    )
    selected_method = _selected_method_profile(
        selected_method_identity,
        expected_fqn=prepared.method_fqn,
    )
    binding = _compose_binding(
        submitted_ref=prepared.submitted_ref,
        effective_ref=prepared.effective_ref,
        materialization_binding_ref=physical_ref,
        effective_artifact_schema=prepared.effective_artifact_schema,
        request_context=request_context,
        selected_method=selected_method,
        physical_binding=physical,
        data=prepared.data,
        limits=limits,
    )

    binding_ref_raw = _persist_model(
        store,
        model=binding,
        kind=HTE_CANDIDATE_SCOPE_BINDING_KIND,
        schema=HTE_CANDIDATE_SCOPE_BINDING_SCHEMA,
        inputs=_input_edges(
            (
                ("submitted_source", binding.submitted_ref),
                ("effective_source", binding.effective_ref),
                ("physical_materialization", physical_core_ref),
            )
        ),
        governance=prepared.source_governance,
        tenant_context=prepared.write_tenant_context,
        limits=limits,
    )
    try:
        binding_ref = SelectedHTECandidateScopeBindingRef.model_validate(
            binding_ref_raw.model_dump(mode="json"),
            strict=True,
        )
    except Exception as exc:
        raise _refusal("candidate_scope_binding_ref_invalid") from exc

    projection_models = _role_projections(binding_ref=binding_ref, binding=binding)
    role_refs = HTECandidateScopeRoleRefs(
        quantity_ref=_persist_role_projection(
            store,
            model=projection_models.quantity,
            binding_ref=binding_ref,
            effective_ref=binding.effective_ref,
            physical_binding_ref=physical_core_ref,
            governance=prepared.source_governance,
            tenant_context=prepared.write_tenant_context,
            limits=limits,
        ),
        treatment_contrast_ref=_persist_role_projection(
            store,
            model=projection_models.treatment_contrast,
            binding_ref=binding_ref,
            effective_ref=binding.effective_ref,
            physical_binding_ref=physical_core_ref,
            governance=prepared.source_governance,
            tenant_context=prepared.write_tenant_context,
            limits=limits,
        ),
        population_ref=_persist_role_projection(
            store,
            model=projection_models.population,
            binding_ref=binding_ref,
            effective_ref=binding.effective_ref,
            physical_binding_ref=physical_core_ref,
            governance=prepared.source_governance,
            tenant_context=prepared.write_tenant_context,
            limits=limits,
        ),
        outcome_ref=_persist_role_projection(
            store,
            model=projection_models.outcome,
            binding_ref=binding_ref,
            effective_ref=binding.effective_ref,
            physical_binding_ref=physical_core_ref,
            governance=prepared.source_governance,
            tenant_context=prepared.write_tenant_context,
            limits=limits,
        ),
    )
    try:
        artifacts = HTESelectedRowCandidateScopeArtifacts(
            binding_ref=binding_ref,
            roles=role_refs,
        )
    except Exception as exc:
        raise _refusal("candidate_scope_role_ref_invalid") from exc

    # Reopen the newly persisted owners through the same bounded readers used by
    # downstream Search; this is an actual producer/readback, not a model-only check.
    load_hte_selected_row_candidate_scope(
        store=store,
        artifacts=artifacts,
        expected_submitted_ref=prepared.submitted_ref,
        expected_effective_ref=prepared.effective_ref,
        expected_effective_artifact_schema=prepared.effective_artifact_schema,
        expected_physical_binding_ref=physical_ref,
        expected_request_context=request_context,
        selected_method_identity=selected_method_identity,
        limits=limits,
    )
    return artifacts


def load_hte_selected_row_candidate_scope(
    *,
    store: HTECandidateScopeStore,
    artifacts: HTESelectedRowCandidateScopeArtifacts,
    expected_submitted_ref: ArtifactRef,
    expected_effective_ref: ArtifactRef,
    expected_effective_artifact_schema: SchemaInfo,
    expected_physical_binding_ref: OwnedAttemptPhysicalSourceBindingRef,
    expected_request_context: OwnedHTERequestContextV1,
    selected_method_identity: HTECandidateSelectedMethodIdentity,
    limits: CoreJsonReadLimits,
) -> HTESelectedRowCandidateScopeRead:
    """Resolve every role and recompute its source, request, row, and method joins.

    Each role is parsed using its role-specific schema and then compared with
    content freshly reconstructed from the exact Core source, request owner,
    method class, and physical materialization owner. A profile-valid artifact
    in another role fails because its role discriminator and expected content
    differ, even when it has the same kind and schema.
    """
    if type(artifacts) is not HTESelectedRowCandidateScopeArtifacts:
        raise _refusal("candidate_scope_artifacts_type_invalid")
    try:
        expected_physical_binding_ref = OwnedAttemptPhysicalSourceBindingRef.model_validate(
            expected_physical_binding_ref.model_dump(mode="json"),
            strict=True,
        )
    except Exception as exc:
        raise _refusal("candidate_scope_physical_binding_ref_invalid") from exc
    _required_request_context(expected_request_context)
    expected_binding = _load_scope_from_source(
        store,
        submitted_ref=expected_submitted_ref,
        effective_ref=expected_effective_ref,
        materialization_binding_ref=expected_physical_binding_ref,
        effective_artifact_schema=expected_effective_artifact_schema,
        request_context=expected_request_context,
        selected_method_identity=selected_method_identity,
        limits=limits,
    )
    binding_model, binding_manifest = _read_model(
        store,
        ref=artifacts.binding_ref,
        expected_kind=HTE_CANDIDATE_SCOPE_BINDING_KIND,
        expected_schema=HTE_CANDIDATE_SCOPE_BINDING_SCHEMA,
        model_type=HTESelectedRowCandidateScopeBinding,
        limits=limits,
    )
    if binding_model != expected_binding:
        raise _refusal("candidate_scope_binding_recomputation_mismatch")
    _verify_edges(
        binding_manifest,
        _input_edges(
            (
                ("submitted_source", expected_submitted_ref),
                ("effective_source", expected_effective_ref),
                ("physical_materialization", expected_physical_binding_ref),
            )
        ),
    )

    expected_projections = _role_projections(
        binding_ref=artifacts.binding_ref,
        binding=expected_binding,
    )
    expected_role_inputs = _input_edges(
        (
            ("candidate_scope_binding", artifacts.binding_ref),
            ("effective_source", expected_effective_ref),
            ("physical_materialization", expected_physical_binding_ref),
        )
    )
    quantity = _read_role_projection(
        store,
        role="quantity",
        ref=artifacts.roles.quantity_ref,
        expected_model=expected_projections.quantity,
        expected_inputs=expected_role_inputs,
        limits=limits,
    )
    treatment_contrast = _read_role_projection(
        store,
        role="treatment_contrast",
        ref=artifacts.roles.treatment_contrast_ref,
        expected_model=expected_projections.treatment_contrast,
        expected_inputs=expected_role_inputs,
        limits=limits,
    )
    population = _read_role_projection(
        store,
        role="population",
        ref=artifacts.roles.population_ref,
        expected_model=expected_projections.population,
        expected_inputs=expected_role_inputs,
        limits=limits,
    )
    outcome = _read_role_projection(
        store,
        role="outcome",
        ref=artifacts.roles.outcome_ref,
        expected_model=expected_projections.outcome,
        expected_inputs=expected_role_inputs,
        limits=limits,
    )

    return HTESelectedRowCandidateScopeRead(
        binding=expected_binding,
        binding_ref=artifacts.binding_ref,
        quantity=quantity,
        treatment_contrast=treatment_contrast,
        population=population,
        outcome=outcome,
    )
