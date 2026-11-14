"""Bind Fabric snapshots into Foundry state snapshots and input-binding reports.

The public functions in this module implement the data-plane boundary consumed
by `polisyos.foundry.execute.api.execute`: they resolve Fabric snapshot
payloads, materialize a `GlobalState`, persist `FoundryInputBindings`, and
return the bound `StateSnapshotRef` that execution should use as its base
synthetic runtime state.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    ROUND_HALF_EVEN,
    ROUND_UP,
    Context,
    Decimal,
    Inexact,
    InvalidOperation,
    localcontext,
)
from io import BytesIO
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, NoReturn, Protocol

import jax.numpy as jnp
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.common.serialization import to_python_data
from polisyos.core.artifacts import (
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    ArtifactTenantContextInfo,
    CanonInfo,
    CoreJSONArtifactBoundedMemberReader,
    CoreJsonArtifactBoundedRead,
    CoreJSONArtifactStore,
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    read_core_json_artifact_bounded,
    resolve_manifest_by_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts import (
    DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
    DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION,
    DERIVED_MODEL_INPUT_PAYLOAD_KIND,
    RESOLVED_INPUT_BINDING_MANIFEST_ROLE,
    AcquiredObservationSemanticInputDataSnapshotLineage,
    DataSnapshot,
    DataSnapshotRef,
    DerivedModelInputDataSnapshotLineage,
    ExecuteRequest,
    FeedbackConfig,
    FeedbackStateSnapshot,
    FoundryInputBindingReportRef,
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    FoundrySelectedMethodInput,
    MeasurementBindingProfile,
    ModelInputObligation,
    ProgramGraphInputInvocation,
    ReplayedDerivedMeasurementRole,
    ResolvedDerivedInput,
    ResolvedInputBindingManifest,
    ResolvedInputBindingManifestRef,
    ResolvedMeasurementInput,
    ScopedCorrespondenceBasis,
    ScopedMeasurementOccurrence,
    ScopedMeasurementOccurrenceRef,
    ScopedSourceSelection,
    SelectedVariableBindingRef,
    SemanticHorizonStepContext,
    StateSnapshot,
    StateSnapshotRef,
    ValueOuterSet,
    VariableRepresentation,
    VariableSemanticDefinition,
    data_snapshot_owner_input_requirements,
    data_snapshot_reference_fields,
    data_snapshot_reference_input_roles,
    evaluate_derived_input_correspondence,
    evaluate_scoped_correspondence_basis,
    load_derived_input_correspondence,
    load_derived_input_profile,
    load_model_input_obligation_set,
    load_ratio_denominator_source_context,
    load_resolved_input_binding_manifest,
    load_variable_representation,
    persist_resolved_input_binding_manifest,
    scoped_correspondence_basis_manifest_inputs,
)
from polisyos.core.derivations import (
    DerivationRefusalError,
    SourceSeries,
    load_derivation_recipe_artifact,
    resolve_certified_derivation,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.data_forge import read_api
from polisyos.foundry._artifact_capabilities import resolve_core_json_profile_store
from polisyos.foundry.contracts.state import FeedbackState, GlobalState
from polisyos.foundry.data_plane.selected_tensors import (
    encode_selected_tensor,
    selected_tensor_value_sha256,
)
from polisyos.foundry.execute._internal.models import load_tensor, put_tensor
from polisyos.foundry.execute.executor import (
    get_state_path,
    load_state_snapshot,
    put_state_snapshot,
    set_state_path,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    HTEObservationalData,
    NetworkCausalData,
    PanelObservationalData,
    ProxyMeasurementData,
)
from polisyos.foundry.methods.catalog.econometrics.protocols import PanelData
from polisyos.foundry.methods.catalog.microsim.protocols import SurveyMicroData
from polisyos.foundry.methods.catalog.ml.protocols import SurvivalData
from polisyos.foundry.methods.catalog.network.protocols import (
    MultiplexNetworkData,
    NetworkData,
)
from polisyos.ir.kernel import MoneyUnit, SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType
from polisyos.ir.observation.bundles import (
    HTE_OBSERVATIONAL_DATA_CONTRACT_FQN,
    HTE_OBSERVATIONAL_DATA_CONTRACT_ID,
    HTE_OBSERVATIONAL_DATA_TARGET,
    OBSERVATION_METHOD_INPUT_KIND,
    OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
    ContractCompatibilityTarget,
    ObservationMethodInputEnvelope,
)

_MISSING = object()
_FLOAT_QUANT = Decimal("0.000000001")
_CELL_PREFIX = "cells."
_HOUSEHOLD_CELL_PREFIX = "household_cells."
_JSON_MEDIA_TYPE = "application/json"
_ARROW_MEDIA_TYPE = "application/vnd.apache.arrow.stream"


@dataclass(frozen=True)
class _MethodContractSpec:
    """Bind one admitted IR target identity to its concrete Foundry DTO."""

    contract_fqn: str
    model_type: type[BaseModel]


@dataclass(frozen=True, slots=True)
class _SelectedBindingTensorPolicy:
    """Physical encoding selected by an independently verified binding manifest.

    The multiplier, when present, is the fixed unit owner's verified value.
    This numerical policy alone does not establish semantic correspondence.
    """

    shape: tuple[int, ...]
    dtype: str
    max_absolute_error: Decimal
    fixed_unit_multiplier: Decimal | None = None


@dataclass(frozen=True, slots=True)
class _ExplicitInitialBinding:
    """One exact predecessor source value and its replayed physical policy."""

    rule: FoundryInputBindingRule
    source_value: object
    policy: _SelectedBindingTensorPolicy


_METHOD_CONTRACT_ALLOW_REGISTRY: dict[str, _MethodContractSpec] = {
    model_type.contract_id: _MethodContractSpec(
        contract_fqn=f"{model_type.__module__}.{model_type.__name__}",
        model_type=model_type,
    )
    for model_type in (
        DynamicTreatmentData,
        HTEObservationalData,
        MultiplexNetworkData,
        NetworkCausalData,
        NetworkData,
        PanelData,
        PanelObservationalData,
        ProxyMeasurementData,
        SurveyMicroData,
        SurvivalData,
    )
}


type HTEInputLimits = CoreJsonReadLimits


HTE_PHYSICAL_SOURCE_BINDING_KIND = "foundry.hte.physical_source_materialization_binding"
HTE_PHYSICAL_SOURCE_BINDING_SCHEMA = SchemaInfo(
    name="polisyos.foundry.HTEPhysicalSourceMaterializationBinding",
    version="1.0",
)
HTE_PHYSICAL_SOURCE_BINDING_MEDIA_TYPE = "application/json"
_HTE_PHYSICAL_SOURCE_BINDING_DISCRIMINATOR = (
    "policyos.foundry.hte.physical_source_materialization_binding.v1"
)
_HTE_PHYSICAL_SOURCE_BINDING_PRODUCER = (
    "polisyos.foundry.data_plane.prepare_hte_observational_input"
)


class HTEPhysicalArraySlotBinding(BaseModel):
    """Bind one materialized HTE array slot to its exact selected JSON field."""

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
    value_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    row_order_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    transform: Literal["identity_numpy_materialization_v1"] = "identity_numpy_materialization_v1"


class HTEPhysicalSourceMaterializationBinding(BaseModel):
    """Describe only the physical materialization of one selected HTE input.

    This artifact does not establish that physical slots identify a requested
    causal variable, contrast, query, unit, population, law, or current source.
    Those semantic relations remain ``not_established`` until an independent
    owner supplies and verifies them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["policyos.foundry.hte.physical_source_materialization_binding.v1"] = (
        _HTE_PHYSICAL_SOURCE_BINDING_DISCRIMINATOR
    )
    binding_scope: Literal["physical_materialization_only"] = "physical_materialization_only"
    semantic_alignment_status: Literal["not_established"] = "not_established"
    submitted_ref: ArtifactRef
    effective_ref: ArtifactRef
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    normalization: Literal["canonical_passthrough", "legacy_to_method_input_envelope_v1"]
    contract_target: ContractCompatibilityTarget
    effective_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observation_count: int = Field(gt=0)
    row_order_basis: Literal["sample_ids", "positional_row_ordinal"]
    row_order_pointer: str | None = Field(
        default=None,
        pattern=r"^/contract_payload/sample_ids$",
    )
    row_order_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    submitted_sample_ids_state: Literal["absent", "null", "materialized"]
    effective_sample_ids_state: Literal["absent", "null", "materialized"]
    submitted_confounders_state: Literal["absent", "null", "materialized"]
    effective_confounders_state: Literal["absent", "null", "materialized"]
    arrays: tuple[HTEPhysicalArraySlotBinding, ...] = Field(min_length=2)


class _HTEObservationalInputStore(
    CoreJSONArtifactStore,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Require both the producer's write path and bounded selected-view reader."""


class HTEInputPreparationRefusal(ValueError):
    """Refuse HTE admission while retaining known Core source usage.

    Usage counts describe selected-store API transfers. Unknown attempted
    components remain ``None`` and make the aggregate total unavailable.
    """

    def __init__(
        self,
        code: str,
        *,
        observed_manifest_selection_bytes: int | None = 0,
        observed_manifest_verification_bytes: int | None = 0,
        observed_payload_bytes: int | None = 0,
        payload_integrity_verified: bool = False,
        source_usage_complete: bool = True,
        failure_stage: str | None = None,
        cleanup_failure_stage: str | None = None,
        cleanup_exception_type: str | None = None,
        cleanup_exception_code: str | None = None,
        original_exception_type: str | None = None,
        original_exception_code: str | None = None,
        original_exception_message: str | None = None,
    ) -> None:
        """Retain exact Core selected-store transfers on success-bound refusals."""
        self.code = code
        self.observed_manifest_selection_bytes = observed_manifest_selection_bytes
        self.observed_manifest_verification_bytes = observed_manifest_verification_bytes
        self.observed_payload_bytes = observed_payload_bytes
        self.observed_source_bytes = (
            observed_manifest_selection_bytes
            + observed_manifest_verification_bytes
            + observed_payload_bytes
            if source_usage_complete
            and type(observed_manifest_selection_bytes) is int
            and observed_manifest_selection_bytes >= 0
            and type(observed_manifest_verification_bytes) is int
            and observed_manifest_verification_bytes >= 0
            and type(observed_payload_bytes) is int
            and observed_payload_bytes >= 0
            else None
        )
        self.payload_integrity_verified = payload_integrity_verified
        self.source_usage_complete = source_usage_complete
        self.failure_stage = failure_stage
        self.cleanup_failure_stage = cleanup_failure_stage
        self.cleanup_exception_type = cleanup_exception_type
        self.cleanup_exception_code = cleanup_exception_code
        self.original_exception_type = original_exception_type
        self.original_exception_code = original_exception_code
        self.original_exception_message = original_exception_message
        # Compatibility aliases retained for existing Runtime consumers.
        self.observed_manifest_bytes = observed_manifest_selection_bytes
        self.observed_bytes = observed_payload_bytes
        super().__init__(code)


def _bounded_read_usage_fields(
    bounded_read: CoreJsonArtifactBoundedRead,
    *,
    include_observed_source_bytes: bool = True,
) -> dict[str, Any]:
    """Copy the complete owner-measured Core usage into an HTE carrier."""
    fields = {
        "observed_manifest_selection_bytes": bounded_read.observed_manifest_selection_bytes,
        "observed_manifest_verification_bytes": bounded_read.observed_manifest_verification_bytes,
        "observed_payload_bytes": bounded_read.observed_payload_bytes,
        "observed_source_bytes": bounded_read.observed_source_bytes,
        "payload_integrity_verified": bounded_read.payload_integrity_verified,
    }
    if not include_observed_source_bytes:
        fields.pop("observed_source_bytes")
    return fields


def _bounded_refusal_usage_fields(
    error: CoreJsonReadBoundsRefusalError,
) -> dict[str, Any]:
    """Copy only exact owner components from one Core typed refusal."""
    return {
        "observed_manifest_selection_bytes": error.observed_manifest_selection_bytes,
        "observed_manifest_verification_bytes": error.observed_manifest_verification_bytes,
        "observed_payload_bytes": error.observed_payload_bytes,
        "payload_integrity_verified": error.payload_integrity_verified,
        "source_usage_complete": type(error.observed_source_bytes) is int,
        "failure_stage": error.failure_stage,
        "cleanup_failure_stage": error.cleanup_failure_stage,
        "cleanup_exception_type": error.cleanup_exception_type,
        "cleanup_exception_code": error.cleanup_exception_code,
        "original_exception_type": error.original_exception_type,
        "original_exception_code": error.original_exception_code,
        "original_exception_message": error.original_exception_message,
    }


def _source_binding_bounds_refusal(
    error: CoreJsonReadBoundsRefusalError,
    *,
    phase: Literal["binding", "effective", "submitted"],
) -> HTEInputPreparationRefusal:
    """Preserve Core's exact resource refusal and transfer receipt."""
    usage = _bounded_refusal_usage_fields(error)
    usage.update(
        {
            "original_exception_type": type(error).__name__,
            "original_exception_code": error.code,
            "original_exception_message": str(error),
        }
    )
    return HTEInputPreparationRefusal(
        f"source_binding_{phase}_resource_refused",
        **usage,
    )


def _raise_hte_refusal_with_usage(
    error: HTEInputPreparationRefusal,
    *,
    bounded_read: CoreJsonArtifactBoundedRead | None,
    cause: BaseException | None = None,
) -> HTEInputPreparationRefusal:
    """Preserve the source receipt when later HTE validation refuses."""
    origin = cause if cause is not None else error.__cause__ or error
    current: BaseException | None = origin
    last_error = origin
    core_refusal: CoreJsonReadBoundsRefusalError | None = None
    seen: set[int] = set()
    while current is not None:
        if id(current) in seen:
            break
        seen.add(id(current))
        last_error = current
        if isinstance(current, CoreJsonReadBoundsRefusalError):
            core_refusal = current
            break
        current = current.__cause__

    try:
        original_code = getattr(last_error, "code", None)
    except Exception:
        original_code = None
    try:
        original_message = str(last_error)
    except Exception:
        original_message = f"<{type(last_error).__name__} message unavailable>"
    original_metadata = {
        "original_exception_type": type(last_error).__name__,
        "original_exception_code": original_code if type(original_code) is str else None,
        "original_exception_message": original_message,
    }

    if core_refusal is not None:
        usage = _bounded_refusal_usage_fields(core_refusal)
    elif bounded_read is not None:
        usage = {
            **_bounded_read_usage_fields(
                bounded_read,
                include_observed_source_bytes=False,
            ),
            "source_usage_complete": type(bounded_read.observed_source_bytes) is int,
            "failure_stage": error.failure_stage or "hte_selected_source_validation",
            **original_metadata,
        }
    else:
        usage = {
            "observed_manifest_selection_bytes": None,
            "observed_manifest_verification_bytes": None,
            "observed_payload_bytes": None,
            "payload_integrity_verified": False,
            "source_usage_complete": False,
            "failure_stage": "hte_selected_source_read",
            **original_metadata,
        }
    return HTEInputPreparationRefusal(error.code, **usage)


@dataclass(frozen=True)
class PreparedHTEObservationalInput:
    """Worker-local HTE DTO plus selected-source admission metadata.

    ``data`` is an in-worker value. Callers must consume it before returning a
    worker outcome and must persist only the typed references and metadata.
    Source usage counts describe selected-store API transfers, not physical
    device I/O.
    """

    data: HTEObservationalData
    submitted_ref: ArtifactRef
    effective_ref: ArtifactRef
    effective_artifact_schema: SchemaInfo
    contract_target: ContractCompatibilityTarget
    method_fqn: str
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    normalization: Literal[
        "canonical_passthrough",
        "legacy_to_method_input_envelope_v1",
    ]
    limitations: tuple[
        Literal[
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            "legacy_hte_json_v1_source_normalized",
        ],
        ...,
    ]
    source_governance: ArtifactGovernanceInfo | None
    source_tenant_context: ArtifactTenantContextInfo | None
    observed_manifest_bytes: int
    observed_bytes: int
    observed_depth: int
    observed_elements: int
    observed_manifest_selection_bytes: int
    observed_manifest_verification_bytes: int
    observed_payload_bytes: int
    observed_source_bytes: int
    payload_integrity_verified: bool
    materialization_binding_ref: ArtifactRef | None = None
    derived_tenant_context: ArtifactTenantContextInfo | None = None

    @property
    def write_tenant_context(self) -> ArtifactTenantContextInfo | None:
        """Return explicit derived custody, preserving legacy producer defaults."""
        return self.derived_tenant_context or self.source_tenant_context


_HTE_SOURCE_PROTOCOLS = ("method_input_envelope_v1", "legacy_hte_json_v1")
_HTE_CANONICAL_INPUT_KIND = OBSERVATION_METHOD_INPUT_KIND
_HTE_LEGACY_INPUT_KIND = "ir.observational_data"
_HTE_PHYSICAL_SOURCE_BINDING_INPUT_SCHEMA = SchemaInfo(
    name=OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    version=OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
)
_HTE_CANDIDATE_LIMITATIONS = (
    "candidate_input_not_external_truth",
    "scientific_validity_not_established",
    "units_and_context_not_established",
)


def _selected_source_governance(
    bounded_read: CoreJsonArtifactBoundedRead,
) -> ArtifactGovernanceInfo | None:
    """Return governance only when the selected raw manifest declared it."""
    try:
        raw_manifest = json.loads(bounded_read.raw_manifest_bytes)
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise HTEInputPreparationRefusal("selected_manifest_invalid") from exc
    if not isinstance(raw_manifest, dict):
        raise HTEInputPreparationRefusal("selected_manifest_invalid")

    raw_governance = raw_manifest.get("governance")
    if raw_governance is None:
        return None
    if not isinstance(raw_governance, dict):
        return None
    raw_classification = raw_governance.get("classification")
    if not isinstance(raw_classification, str) or not raw_classification.strip():
        return None

    governance = bounded_read.manifest.governance
    if governance is None or governance.classification != raw_classification:
        raise HTEInputPreparationRefusal("selected_governance_mismatch")
    return governance


def _materialize_hte_observational_data(
    contract_payload: Mapping[str, Any],
) -> HTEObservationalData:
    """Apply the registered HTE DTO validator to one exact IR target."""
    try:
        value = materialize_method_contract(
            contract_target=HTE_OBSERVATIONAL_DATA_TARGET,
            contract_payload=contract_payload,
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise HTEInputPreparationRefusal("invalid_hte_observational_data") from exc
    if not isinstance(value, HTEObservationalData):
        raise HTEInputPreparationRefusal("hte_target_materializer_mismatch")
    return value


def _normalize_legacy_hte_source(
    payload: Mapping[str, Any],
    *,
    max_depth: int,
) -> tuple[HTEObservationalData, ObservationMethodInputEnvelope, CanonSpec, bytes]:
    """Apply the existing legacy HTE→method-input normalization exactly."""
    data = _materialize_hte_observational_data(payload)
    envelope = ObservationMethodInputEnvelope(
        contract_target=HTE_OBSERVATIONAL_DATA_TARGET,
        contract_payload=data.model_dump(mode="json", exclude_none=False),
    )
    output_spec = CanonSpec(
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=False,
        max_depth=max_depth,
    )
    try:
        output_bytes = to_canonical_bytes(
            envelope.model_dump(mode="json", exclude_none=False),
            output_spec,
        )
    except (TypeError, ValueError) as exc:
        raise HTEInputPreparationRefusal(
            "legacy_hte_normalization_refused",
            failure_stage="normalized_hte_input_serialization",
        ) from exc
    return data, envelope, output_spec, output_bytes


def _sha256_bytes(value: bytes) -> str:
    """Return one namespaced SHA-256 digest for immutable bytes."""
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _canonical_value_sha256(value: object, *, max_depth: int) -> str:
    """Hash a canonical JSON value used to recompute a physical array slot."""
    try:
        encoded = to_canonical_bytes(
            value,
            CanonSpec(
                forbid_floats=False,
                forbid_nan_inf=True,
                exclude_none=False,
                max_depth=max_depth,
            ),
        )
    except (TypeError, ValueError) as exc:
        raise HTEInputPreparationRefusal("source_binding_value_serialization_refused") from exc
    return _sha256_bytes(encoded)


def _optional_field_state(payload: Mapping[str, Any], field_name: str) -> str:
    """Preserve whether an optional source field was absent, null, or materialized."""
    if field_name not in payload:
        return "absent"
    if payload[field_name] is None:
        return "null"
    return "materialized"


def _json_element_count(value: object, *, stop_after: int) -> int:
    """Count JSON lexical nodes and object member names up to a selected bound."""
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


def _build_hte_physical_source_binding(
    *,
    data: HTEObservationalData,
    submitted_ref: ArtifactRef,
    effective_ref: ArtifactRef,
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"],
    normalization: Literal["canonical_passthrough", "legacy_to_method_input_envelope_v1"],
    contract_target: ContractCompatibilityTarget,
    submitted_contract_payload: Mapping[str, Any],
    effective_contract_payload: Mapping[str, Any],
    effective_payload_bytes: bytes,
    max_depth: int,
) -> HTEPhysicalSourceMaterializationBinding:
    """Recompute the physical slot map from the selected, typed HTE DTO."""
    if data.sample_ids is None:
        row_order_basis: Literal["sample_ids", "positional_row_ordinal"] = "positional_row_ordinal"
        row_order_pointer = None
        row_order_value = list(range(data.n_obs))
    else:
        row_order_basis = "sample_ids"
        row_order_pointer = "/contract_payload/sample_ids"
        row_order_value = data.sample_ids.tolist()
    row_order_sha256 = _canonical_value_sha256(row_order_value, max_depth=max_depth)

    arrays: list[HTEPhysicalArraySlotBinding] = []

    def add_array_slot(
        *,
        physical_slot: Literal[
            "outcome_vector",
            "treatment_vector",
            "covariate_matrix_column",
            "confounder_matrix_column",
        ],
        payload_field: str,
        array: np.ndarray,
        component_index: int | None = None,
    ) -> None:
        selected = array if component_index is None else array[:, component_index]
        arrays.append(
            HTEPhysicalArraySlotBinding(
                physical_slot=physical_slot,
                payload_pointer=f"/contract_payload/{payload_field}",
                component_index=component_index,
                array_shape=tuple(int(size) for size in array.shape),
                array_dtype=array.dtype.str,
                value_sha256=_canonical_value_sha256(
                    selected.tolist(),
                    max_depth=max_depth,
                ),
                row_order_sha256=row_order_sha256,
            )
        )

    add_array_slot(
        physical_slot="outcome_vector",
        payload_field="outcome",
        array=data.outcome,
    )
    add_array_slot(
        physical_slot="treatment_vector",
        payload_field="treatment",
        array=data.treatment,
    )
    for component_index in range(data.covariates.shape[1]):
        add_array_slot(
            physical_slot="covariate_matrix_column",
            payload_field="covariates",
            array=data.covariates,
            component_index=component_index,
        )
    if data.confounders is not None:
        for component_index in range(data.confounders.shape[1]):
            add_array_slot(
                physical_slot="confounder_matrix_column",
                payload_field="confounders",
                array=data.confounders,
                component_index=component_index,
            )

    return HTEPhysicalSourceMaterializationBinding(
        submitted_ref=submitted_ref,
        effective_ref=effective_ref,
        source_protocol=source_protocol,
        normalization=normalization,
        contract_target=contract_target,
        effective_payload_sha256=_sha256_bytes(effective_payload_bytes),
        observation_count=data.n_obs,
        row_order_basis=row_order_basis,
        row_order_pointer=row_order_pointer,
        row_order_sha256=row_order_sha256,
        submitted_sample_ids_state=_optional_field_state(submitted_contract_payload, "sample_ids"),
        effective_sample_ids_state=_optional_field_state(effective_contract_payload, "sample_ids"),
        submitted_confounders_state=_optional_field_state(
            submitted_contract_payload, "confounders"
        ),
        effective_confounders_state=_optional_field_state(
            effective_contract_payload, "confounders"
        ),
        arrays=tuple(arrays),
    )


def _persist_hte_physical_source_binding(
    *,
    store: _HTEObservationalInputStore,
    binding: HTEPhysicalSourceMaterializationBinding,
    source_governance: ArtifactGovernanceInfo | None,
    tenant_context: ArtifactTenantContextInfo | None,
    limits: HTEInputLimits,
) -> ArtifactRef:
    """Persist the opt-in physical-only binding with an exact source edge."""
    spec = CanonSpec(
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=False,
        max_depth=limits.max_depth,
    )
    payload_value = binding.model_dump(mode="json")
    if _json_element_count(payload_value, stop_after=limits.max_elements) > limits.max_elements:
        raise HTEInputPreparationRefusal("source_binding_exceeds_element_limit")
    try:
        payload_bytes = to_canonical_bytes(payload_value, spec)
    except (TypeError, ValueError) as exc:
        raise HTEInputPreparationRefusal("source_binding_serialization_refused") from exc
    if len(payload_bytes) > limits.max_bytes:
        raise HTEInputPreparationRefusal("source_binding_exceeds_byte_limit")

    try:
        binding_ref = store.put_bytes(
            payload_bytes,
            PutOptions(
                kind=HTE_PHYSICAL_SOURCE_BINDING_KIND,
                media_type=HTE_PHYSICAL_SOURCE_BINDING_MEDIA_TYPE,
                schema=HTE_PHYSICAL_SOURCE_BINDING_SCHEMA,
                producer=ProducerInfo(
                    component=_HTE_PHYSICAL_SOURCE_BINDING_PRODUCER,
                    version="1.0.0",
                ),
                inputs=[
                    input_ref_from_artifact_ref(
                        binding.effective_ref,
                        role="materialized_hte_method_input",
                    )
                ],
                canon=CanonInfo.from_spec(spec),
                governance=source_governance,
                tenant_context=tenant_context,
            ),
            return_selected_profile=True,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise HTEInputPreparationRefusal("source_binding_write_refused") from exc
    if not binding_ref.manifest_profile_sha256:
        raise HTEInputPreparationRefusal("source_binding_profile_missing")
    return binding_ref


def load_hte_physical_source_materialization_binding(
    *,
    store: _HTEObservationalInputStore,
    binding_ref: ArtifactRef,
    expected_submitted_ref: ArtifactRef,
    expected_effective_ref: ArtifactRef,
    limits: HTEInputLimits,
    expected_data: HTEObservationalData | None = None,
) -> HTEPhysicalSourceMaterializationBinding:
    """Resolve and recompute a physical binding against the selected HTE input.

    This reader requires the consumer's exact submitted/effective references,
    resolves the profile-bound binding and input bytes, rematerializes the HTE
    DTO, and rejects any field, array, row-order, or profile drift. Legacy
    normalization and the binding must share derived custody; source ownership
    remains provenance bound through exact selected lineage. It proves
    only the physical materialization recorded in the source; it does not
    establish semantic variable, query, contrast, unit, causal, population, or
    legal alignment.

    Args:
        store: Core JSON writer and bounded selected-member reader.
        binding_ref: Full profile-qualified reference to the binding artifact.
        expected_submitted_ref: Exact original selected source expected by the
            caller's already selected input context.
        expected_effective_ref: Exact HTE method-input reference expected by
            the caller's already selected input context.
        limits: Pinned Core limits used to resolve both artifacts.
        expected_data: Optional worker-local DTO captured by the owned Runtime
            attempt. Its physical arrays and row order must match this source.

    Returns:
        HTEPhysicalSourceMaterializationBinding: Recomputed physical binding.

    Raises:
        HTEInputPreparationRefusal: If any selected identity, profile, schema,
            input, or recomputed materialization differs.
    """
    if not binding_ref.manifest_profile_sha256:
        raise HTEInputPreparationRefusal("source_binding_profile_required")
    try:
        binding_read = read_core_json_artifact_bounded(store, binding_ref, limits=limits)
        if binding_read.effective_ref != binding_ref:
            raise HTEInputPreparationRefusal("source_binding_ref_mismatch")
        if (
            binding_read.manifest.kind != HTE_PHYSICAL_SOURCE_BINDING_KIND
            or binding_read.manifest.media_type != HTE_PHYSICAL_SOURCE_BINDING_MEDIA_TYPE
            or binding_read.manifest.artifact_schema != HTE_PHYSICAL_SOURCE_BINDING_SCHEMA
        ):
            raise HTEInputPreparationRefusal("source_binding_schema_mismatch")
        require_declared_profile(binding_read.profile_read)
        binding = HTEPhysicalSourceMaterializationBinding.model_validate_json(
            binding_read.raw_payload_bytes
        )
    except HTEInputPreparationRefusal:
        raise
    except CoreJsonReadBoundsRefusalError as exc:
        raise _source_binding_bounds_refusal(
            exc,
            phase="binding",
        ) from exc
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        raise HTEInputPreparationRefusal("source_binding_payload_invalid") from exc

    if (
        binding.submitted_ref != expected_submitted_ref
        or binding.effective_ref != expected_effective_ref
    ):
        raise HTEInputPreparationRefusal("source_binding_input_ref_mismatch")
    if (
        not binding.submitted_ref.manifest_profile_sha256
        or not binding.effective_ref.manifest_profile_sha256
    ):
        raise HTEInputPreparationRefusal("source_binding_input_profile_required")
    expected_binding_lineage = input_ref_from_artifact_ref(
        binding.effective_ref,
        role="materialized_hte_method_input",
    )
    if expected_binding_lineage not in binding_read.manifest.inputs:
        raise HTEInputPreparationRefusal("source_binding_artifact_lineage_mismatch")
    if binding.source_protocol == "method_input_envelope_v1":
        if (
            binding.normalization != "canonical_passthrough"
            or binding.submitted_ref != binding.effective_ref
        ):
            raise HTEInputPreparationRefusal("source_binding_protocol_mismatch")
    elif (
        binding.normalization != "legacy_to_method_input_envelope_v1"
        or binding.submitted_ref.kind != _HTE_LEGACY_INPUT_KIND
        or binding.submitted_ref.media_type != _JSON_MEDIA_TYPE
    ):
        raise HTEInputPreparationRefusal("source_binding_protocol_mismatch")

    try:
        effective_read = read_core_json_artifact_bounded(
            store,
            binding.effective_ref,
            limits=limits,
        )
        if effective_read.effective_ref != binding.effective_ref:
            raise HTEInputPreparationRefusal("source_binding_effective_ref_mismatch")
        if (
            effective_read.manifest.kind != OBSERVATION_METHOD_INPUT_KIND
            or effective_read.manifest.media_type != _JSON_MEDIA_TYPE
            or effective_read.manifest.artifact_schema != _HTE_PHYSICAL_SOURCE_BINDING_INPUT_SCHEMA
        ):
            raise HTEInputPreparationRefusal("source_binding_effective_schema_mismatch")
        if _sha256_bytes(effective_read.raw_payload_bytes) != binding.effective_payload_sha256:
            raise HTEInputPreparationRefusal("source_binding_effective_payload_mismatch")
        effective_value = require_declared_profile(effective_read.profile_read)
        if not isinstance(effective_value, dict):
            raise HTEInputPreparationRefusal("source_binding_effective_payload_invalid")
        envelope = ObservationMethodInputEnvelope.model_validate(effective_value)
        if (
            envelope.contract_target.contract_id != HTE_OBSERVATIONAL_DATA_CONTRACT_ID
            or envelope.contract_target.contract_fqn != HTE_OBSERVATIONAL_DATA_TARGET.contract_fqn
            or envelope.contract_target != binding.contract_target
        ):
            raise HTEInputPreparationRefusal("source_binding_contract_target_mismatch")
        data = _materialize_hte_observational_data(envelope.contract_payload)
    except HTEInputPreparationRefusal:
        raise
    except CoreJsonReadBoundsRefusalError as exc:
        raise _source_binding_bounds_refusal(
            exc,
            phase="effective",
        ) from exc
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        raise HTEInputPreparationRefusal("source_binding_effective_payload_invalid") from exc

    submitted_contract_payload = envelope.contract_payload
    if binding.source_protocol == "legacy_hte_json_v1":
        try:
            submitted_read = read_core_json_artifact_bounded(
                store,
                binding.submitted_ref,
                limits=limits,
            )
            if (
                submitted_read.effective_ref != binding.submitted_ref
                or submitted_read.manifest.kind != _HTE_LEGACY_INPUT_KIND
                or submitted_read.manifest.media_type != _JSON_MEDIA_TYPE
                or submitted_read.manifest.artifact_schema is not None
            ):
                raise HTEInputPreparationRefusal("source_binding_legacy_source_identity_mismatch")
            submitted_value = require_declared_profile(submitted_read.profile_read)
            if not isinstance(submitted_value, dict):
                raise HTEInputPreparationRefusal("source_binding_legacy_source_invalid")
            if _selected_source_governance(submitted_read) is None:
                raise HTEInputPreparationRefusal(
                    "source_binding_legacy_source_governance_unavailable"
                )
            _, normalized_envelope, normalized_spec, normalized_bytes = (
                _normalize_legacy_hte_source(
                    submitted_value,
                    max_depth=limits.max_depth,
                )
            )
            if len(normalized_bytes) > limits.max_bytes:
                raise HTEInputPreparationRefusal(
                    "source_binding_legacy_normalized_input_exceeds_byte_limit"
                )
        except HTEInputPreparationRefusal:
            raise
        except CoreJsonReadBoundsRefusalError as exc:
            raise _source_binding_bounds_refusal(
                exc,
                phase="submitted",
            ) from exc
        except (OSError, TypeError, ValueError, ValidationError) as exc:
            raise HTEInputPreparationRefusal("source_binding_legacy_source_invalid") from exc

        expected_legacy_lineage = input_ref_from_artifact_ref(
            binding.submitted_ref,
            role="legacy_hte_json_v1_source",
        )
        if expected_legacy_lineage not in effective_read.manifest.inputs:
            raise HTEInputPreparationRefusal("source_binding_legacy_lineage_mismatch")
        # The submitted source is provenance. Normalization and its physical
        # binding are derived artifacts written under the same actual custody;
        # their exact selected lineage still binds the independently read source.
        if effective_read.manifest.tenant_context != binding_read.manifest.tenant_context:
            raise HTEInputPreparationRefusal("source_binding_legacy_derived_custody_mismatch")
        if (
            normalized_bytes != effective_read.raw_payload_bytes
            or normalized_envelope.contract_target != envelope.contract_target
            or effective_read.manifest.canon != CanonInfo.from_spec(normalized_spec)
            or effective_read.manifest.governance != submitted_read.manifest.governance
        ):
            raise HTEInputPreparationRefusal("source_binding_legacy_normalization_mismatch")
        submitted_contract_payload = submitted_value

    recomputed = _build_hte_physical_source_binding(
        data=data,
        submitted_ref=binding.submitted_ref,
        effective_ref=binding.effective_ref,
        source_protocol=binding.source_protocol,
        normalization=binding.normalization,
        contract_target=envelope.contract_target,
        submitted_contract_payload=submitted_contract_payload,
        effective_contract_payload=envelope.contract_payload,
        effective_payload_bytes=effective_read.raw_payload_bytes,
        max_depth=limits.max_depth,
    )
    if recomputed != binding:
        raise HTEInputPreparationRefusal("source_binding_recomputation_mismatch")
    if expected_data is not None:
        if not isinstance(expected_data, HTEObservationalData):
            raise HTEInputPreparationRefusal("source_binding_worker_data_invalid")
        worker_binding = _build_hte_physical_source_binding(
            data=expected_data,
            submitted_ref=binding.submitted_ref,
            effective_ref=binding.effective_ref,
            source_protocol=binding.source_protocol,
            normalization=binding.normalization,
            contract_target=envelope.contract_target,
            submitted_contract_payload=submitted_contract_payload,
            effective_contract_payload=envelope.contract_payload,
            effective_payload_bytes=effective_read.raw_payload_bytes,
            max_depth=limits.max_depth,
        )
        if worker_binding != recomputed:
            raise HTEInputPreparationRefusal("source_binding_materialized_data_mismatch")
    return recomputed


def prepare_hte_observational_input(
    *,
    store: _HTEObservationalInputStore,
    source_ref: ArtifactRef,
    protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"],
    method_fqn: str,
    limits: HTEInputLimits,
    materialization_binding_version: Literal["physical_v1"] | None = None,
    derived_tenant_context: ArtifactTenantContextInfo | None = None,
) -> PreparedHTEObservationalInput:
    """Decode one explicitly selected HTE source under pinned resource limits.

    The selected Core JSON reader verifies the full manifest profile and bounds
    selected manifest bytes, payload bytes, structural depth, and elements
    before this function materializes NumPy arrays. Method selection/default
    resolution belongs to Runtime; this function only echoes the exact
    already-resolved method FQN.

    Args:
        store: Core JSON writer plus an owner-verified selected-member stream.
        source_ref: Full selected artifact reference including its profile hash.
        protocol: Explicitly selected envelope or legacy input protocol.
        method_fqn: Exact method identity already resolved by Runtime.
        limits: Required manifest and payload limits from the persisted
            resource-policy revision.
        materialization_binding_version: Opt in to the strict, physical-only
            source materialization artifact. The default preserves legacy
            producer behavior and emits no additional artifact.
        derived_tenant_context: Explicit custody for newly derived artifacts,
            supplied by Runtime's actual admitted job owner. Omission preserves
            the legacy direct-producer default; source provenance is unchanged.

    Returns:
        PreparedHTEObservationalInput: Worker-local DTO and profile-bound refs.

    Raises:
        HTEInputPreparationRefusal: If the selected protocol, profile, target,
            resource bounds, governance metadata, or HTE DTO is inadmissible.
    """
    if protocol not in _HTE_SOURCE_PROTOCOLS:
        raise HTEInputPreparationRefusal("unsupported_hte_source_protocol")
    if materialization_binding_version not in {None, "physical_v1"}:
        raise HTEInputPreparationRefusal("unsupported_hte_materialization_binding_version")
    if not isinstance(method_fqn, str) or not method_fqn or method_fqn != method_fqn.strip():
        raise HTEInputPreparationRefusal("invalid_selected_method_fqn")
    if not source_ref.manifest_profile_sha256:
        raise HTEInputPreparationRefusal("selected_manifest_profile_required")

    expected_kind = (
        _HTE_CANONICAL_INPUT_KIND
        if protocol == "method_input_envelope_v1"
        else _HTE_LEGACY_INPUT_KIND
    )
    if source_ref.kind != expected_kind or source_ref.media_type != _JSON_MEDIA_TYPE:
        raise HTEInputPreparationRefusal("source_protocol_kind_mismatch")

    bounded_read: CoreJsonArtifactBoundedRead | None = None
    try:
        bounded_read = read_core_json_artifact_bounded(
            store,
            source_ref,
            limits=limits,
        )
        if bounded_read.effective_ref != source_ref:
            raise HTEInputPreparationRefusal("selected_source_ref_mismatch")
        value = require_declared_profile(bounded_read.profile_read)
    except HTEInputPreparationRefusal as exc:
        raise _raise_hte_refusal_with_usage(
            exc,
            bounded_read=bounded_read,
        ) from exc
    except (OSError, TypeError, ValueError) as exc:
        refusal = HTEInputPreparationRefusal("selected_source_read_refused")
        raise _raise_hte_refusal_with_usage(
            refusal,
            bounded_read=bounded_read,
            cause=exc,
        ) from exc

    assert bounded_read is not None
    try:
        governance = _selected_source_governance(bounded_read)
        tenant_context = bounded_read.manifest.tenant_context
        writer_tenant_context = derived_tenant_context or tenant_context

        if protocol == "method_input_envelope_v1":
            effective_artifact_schema = SchemaInfo(
                name=OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
                version=OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
            )
            if bounded_read.manifest.artifact_schema != effective_artifact_schema:
                raise HTEInputPreparationRefusal("method_input_envelope_schema_mismatch")
            if not isinstance(value, dict):
                raise HTEInputPreparationRefusal("method_input_envelope_body_invalid")
            if value.get("schema_version") != "policyos.ir.observation.method_input_envelope.v1":
                raise HTEInputPreparationRefusal("method_input_envelope_discriminator_required")
            try:
                envelope = ObservationMethodInputEnvelope.model_validate(value)
            except ValidationError as exc:
                raise HTEInputPreparationRefusal("method_input_envelope_body_invalid") from exc
            if (
                envelope.contract_target.contract_id != HTE_OBSERVATIONAL_DATA_CONTRACT_ID
                or envelope.contract_target.contract_fqn != HTE_OBSERVATIONAL_DATA_CONTRACT_FQN
            ):
                raise HTEInputPreparationRefusal("hte_contract_target_mismatch")
            data = _materialize_hte_observational_data(envelope.contract_payload)
            prepared = PreparedHTEObservationalInput(
                data=data,
                submitted_ref=source_ref,
                effective_ref=bounded_read.effective_ref,
                effective_artifact_schema=effective_artifact_schema,
                contract_target=envelope.contract_target,
                method_fqn=method_fqn,
                source_protocol=protocol,
                normalization="canonical_passthrough",
                limitations=_HTE_CANDIDATE_LIMITATIONS,
                source_governance=governance,
                source_tenant_context=tenant_context,
                derived_tenant_context=writer_tenant_context,
                observed_manifest_bytes=bounded_read.observed_manifest_bytes,
                observed_bytes=bounded_read.observed_bytes,
                observed_depth=bounded_read.observed_depth,
                observed_elements=bounded_read.observed_elements,
                **_bounded_read_usage_fields(bounded_read),
            )
            if materialization_binding_version is None:
                return prepared
            binding = _build_hte_physical_source_binding(
                data=data,
                submitted_ref=source_ref,
                effective_ref=bounded_read.effective_ref,
                source_protocol="method_input_envelope_v1",
                normalization="canonical_passthrough",
                contract_target=envelope.contract_target,
                submitted_contract_payload=envelope.contract_payload,
                effective_contract_payload=envelope.contract_payload,
                effective_payload_bytes=bounded_read.raw_payload_bytes,
                max_depth=limits.max_depth,
            )
            binding_ref = _persist_hte_physical_source_binding(
                store=store,
                binding=binding,
                source_governance=governance,
                tenant_context=writer_tenant_context,
                limits=limits,
            )
            return replace(prepared, materialization_binding_ref=binding_ref)

        if bounded_read.manifest.artifact_schema is not None:
            raise HTEInputPreparationRefusal("legacy_hte_schema_must_be_null")
        if governance is None:
            raise HTEInputPreparationRefusal("source_governance_unavailable")
        if not isinstance(value, dict):
            raise HTEInputPreparationRefusal("legacy_hte_body_invalid")
        data, envelope, output_spec, output_bytes = _normalize_legacy_hte_source(
            value,
            max_depth=limits.max_depth,
        )
        if len(output_bytes) > limits.max_bytes:
            raise HTEInputPreparationRefusal(
                "normalized_hte_input_exceeds_byte_limit",
                failure_stage="normalized_hte_input_bounds_validation",
            )
        if materialization_binding_version is not None and (
            _json_element_count(
                envelope.model_dump(mode="json", exclude_none=False),
                stop_after=limits.max_elements,
            )
            > limits.max_elements
        ):
            raise HTEInputPreparationRefusal(
                "normalized_hte_input_exceeds_element_limit",
                failure_stage="normalized_hte_input_bounds_validation",
            )

        try:
            effective_artifact_schema = SchemaInfo(
                name=OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
                version=OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
            )
            effective_ref = store.put_bytes(
                output_bytes,
                PutOptions(
                    kind=OBSERVATION_METHOD_INPUT_KIND,
                    media_type=_JSON_MEDIA_TYPE,
                    schema=effective_artifact_schema,
                    producer=ProducerInfo(
                        component="polisyos.foundry.data_plane.prepare_hte_observational_input",
                        version="1.0.0",
                    ),
                    inputs=[
                        input_ref_from_artifact_ref(
                            source_ref,
                            role="legacy_hte_json_v1_source",
                        )
                    ],
                    canon=CanonInfo.from_spec(output_spec),
                    governance=governance,
                    tenant_context=writer_tenant_context,
                ),
                return_selected_profile=True,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise HTEInputPreparationRefusal(
                "normalized_hte_input_write_refused",
                failure_stage="normalized_hte_input_write",
            ) from exc
        if not effective_ref.manifest_profile_sha256:
            raise HTEInputPreparationRefusal(
                "normalized_hte_profile_missing",
                failure_stage="normalized_hte_input_profile_validation",
            )

        prepared = PreparedHTEObservationalInput(
            data=data,
            submitted_ref=source_ref,
            effective_ref=effective_ref,
            effective_artifact_schema=effective_artifact_schema,
            contract_target=HTE_OBSERVATIONAL_DATA_TARGET,
            method_fqn=method_fqn,
            source_protocol=protocol,
            normalization="legacy_to_method_input_envelope_v1",
            limitations=(
                *_HTE_CANDIDATE_LIMITATIONS,
                "legacy_hte_json_v1_source_normalized",
            ),
            source_governance=governance,
            source_tenant_context=tenant_context,
            derived_tenant_context=writer_tenant_context,
            observed_manifest_bytes=bounded_read.observed_manifest_bytes,
            observed_bytes=bounded_read.observed_bytes,
            observed_depth=bounded_read.observed_depth,
            observed_elements=bounded_read.observed_elements,
            **_bounded_read_usage_fields(bounded_read),
        )
        if materialization_binding_version is None:
            return prepared
        binding = _build_hte_physical_source_binding(
            data=data,
            submitted_ref=source_ref,
            effective_ref=effective_ref,
            source_protocol="legacy_hte_json_v1",
            normalization="legacy_to_method_input_envelope_v1",
            contract_target=HTE_OBSERVATIONAL_DATA_TARGET,
            submitted_contract_payload=value,
            effective_contract_payload=envelope.contract_payload,
            effective_payload_bytes=output_bytes,
            max_depth=limits.max_depth,
        )
        binding_ref = _persist_hte_physical_source_binding(
            store=store,
            binding=binding,
            source_governance=governance,
            tenant_context=writer_tenant_context,
            limits=limits,
        )
        return replace(prepared, materialization_binding_ref=binding_ref)
    except HTEInputPreparationRefusal as exc:
        raise _raise_hte_refusal_with_usage(
            exc,
            bounded_read=bounded_read,
        ) from exc


def materialize_method_contract(
    *,
    contract_target: ContractCompatibilityTarget | Mapping[str, Any],
    contract_payload: Mapping[str, Any],
) -> BaseModel:
    """Validate a neutral IR payload as one allowlisted Foundry method DTO.

    Args:
        contract_target: IR-declared contract identity. Both its stable ID and
            fully-qualified name must match the Foundry allow registry.
        contract_payload: Dependency-neutral JSON payload emitted by IR.

    Returns:
        The concrete, fully validated Foundry method DTO.

    Raises:
        ValueError: If the target is unknown, its FQN disagrees with the
            allowlisted ID, or the payload violates the concrete DTO.
    """

    target = ContractCompatibilityTarget.model_validate(contract_target)
    spec = _METHOD_CONTRACT_ALLOW_REGISTRY.get(target.contract_id)
    if spec is None:
        raise ValueError(f"unsupported method contract '{target.contract_id}'")
    if target.contract_fqn != spec.contract_fqn:
        raise ValueError(
            "contract target mismatch for "
            f"'{target.contract_id}': expected '{spec.contract_fqn}', "
            f"got '{target.contract_fqn}'"
        )
    try:
        return spec.model_type.model_validate(dict(contract_payload))
    except ValidationError as exc:
        raise ValueError(f"invalid payload for method contract '{target.contract_id}'") from exc


@dataclass(frozen=True)
class InputBindingValuesPreparation:
    """Complete numerical binding values before any snapshot exists.

    This is a computed value, never an admitted source, evaluation basis or
    retention permission. Its producer resolves the registry and uses the same
    rule/state owner as the persisted input-binding writer.
    """

    effective_rules: tuple[FoundryInputBindingRule, ...]
    materialized_state: GlobalState
    applied_binding_ids: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _PreparedSelectedMethodInput:
    """One source-recomputed candidate method value before NPY persistence."""

    model_input_obligation_ref: ArtifactRef
    binding_id: str
    port_id: str
    slot_id: str
    canonical_value: Decimal
    value: np.ndarray
    lineage_inputs: tuple[InputRef, ...]


@dataclass(frozen=True)
class InputBindingsPreparation:
    """Computed candidate state before any input-binding artifacts are written.

    The tuple fields identify the exact effective binding operations. The state
    is a freshly materialized numerical value, not an authority or retention
    receipt. A caller may inspect it; ``build_input_bindings`` always resolves
    its own source and constructs a new preparation before writing.
    """

    snapshot: DataSnapshot
    effective_rules: tuple[FoundryInputBindingRule, ...]
    materialized_state: GlobalState
    applied_binding_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    selected_method_inputs: tuple[_PreparedSelectedMethodInput, ...] = ()
    reused_bound_state_snapshot_ref: StateSnapshotRef | None = None


@dataclass(frozen=True)
class SelectedMethodInputFacts:
    """Immutable selected source and tensor facts, without use admission.

    These facts do not establish currentness, an execution occurrence, or the
    nominal method ABI or provider completeness. Callers own their subject join.
    """

    bindings: FoundryInputBindings
    values: Mapping[str, np.ndarray]
    records: tuple[FoundrySelectedMethodInput, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class SelectedMethodInputResolution(SelectedMethodInputFacts):
    """Facts additionally joined to a live preflight or exact stored execution."""


@dataclass(frozen=True)
class InputBindingsBuildResult:
    """Collect the CAS refs emitted by `build_input_bindings()`.

    Attributes:
        input_bindings_ref: Boundary artifact consumed later by `execute()`.
        input_binding_report_ref: Human-readable report describing applied
            rules and warnings from the materialization step.
        bound_state_snapshot_ref: Synthetic `GlobalState` snapshot produced
            from the Fabric data payload and binding rules.
        applied_binding_ids: IDs of binding rules that were successfully
            applied to the state snapshot.
    """

    input_bindings_ref: FoundryInputBindingsRef
    input_binding_report_ref: FoundryInputBindingReportRef
    bound_state_snapshot_ref: StateSnapshotRef
    applied_binding_ids: tuple[str, ...]


@dataclass(frozen=True)
class UkraineFoundryIntakeResult:
    """Typed result transported from the Ukraine intake bridge to orchestration."""

    data_snapshot_ref: DataSnapshotRef
    proxy_identification_bundle: dict[str, Any]
    method_contracts: dict[str, Any]
    method_contract_refs: dict[str, ArtifactRef]
    stage_receipt_refs: dict[str, ArtifactRef]
    method_input_bundle_ref: ArtifactRef
    receipt_ref: ArtifactRef
    source_snapshot_profile_reads: dict[str, read_api.ukraine.UkraineJSONSnapshotProvenance]


class _UkraineMethodInputContract(BaseModel):
    """Persisted transport metadata for one verified Foundry method input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str
    artifact_ref: ArtifactRef
    stage_receipt_ref: ArtifactRef
    source_snapshot_profile: read_api.ukraine.UkraineJSONSnapshotProvenance
    consumption_state: Literal[
        "exercised_workflow_consumer",
        "selectable_unselected",
    ]
    residual_state: Literal["none", "consumer_missing"]
    workflow_consumer: str | None = None


class _UkraineMethodInputBundle(BaseModel):
    """Strict CAS contract carrying all verified Ukraine Foundry inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.foundry.ukraine_method_input_bundle.v1"] = (
        "polisyos.foundry.ukraine_method_input_bundle.v1"
    )
    authority_purpose: Literal["method_input_transport"] = "method_input_transport"
    authoritative_for: tuple[Literal["verified_method_input_transport"], ...] = (
        "verified_method_input_transport",
    )
    may_not_use_for: tuple[
        Literal["governance_admissibility", "method_validity"],
        ...,
    ] = ("governance_admissibility", "method_validity")
    contracts: dict[str, _UkraineMethodInputContract]
    source_snapshot_profile_reads: dict[str, read_api.ukraine.UkraineJSONSnapshotProvenance]


def load_ukraine_foundry_intake(
    store: FileSystemCAS,
    *,
    stage_manifests: Mapping[str, str | Path],
    allowed_root: Path,
) -> UkraineFoundryIntakeResult:
    """Content-bind Ukraine producer receipts and construct Foundry method inputs.

    The function is the only Ukraine-to-Foundry intake surface.  It verifies
    every declared producer output before constructing the concrete Foundry
    method DTOs; its receipt establishes artifact identity, not governance or
    method-validity authority.

    Args:
        store: CAS receiving the persisted, inspectable intake receipt.
        stage_manifests: Exact ``d0_p0`` through ``d3`` producer manifest
            paths, keyed by stage ID.
        allowed_root: Root that contains those manifests and all producer
            outputs.

    Returns:
        A mapping containing the validated Fabric snapshot reference, the
        proxy bundle for causal readiness, concrete Foundry method DTOs, and a
        persisted-receipt-ready inspection payload.

    Raises:
        ValueError: If a stage receipt, required output, JSON payload, or
            concrete Foundry contract is missing or invalid.
    """

    required_outputs = {
        "d0_p0": ("runtime_bundle_manifest.json",),
        "d1": (
            "proxy_identification_bundle_v1.json",
            "multiplex_network_data.json",
            "trade_network_data.json",
            "trade_network_causal_data.json",
            "distress_network_data.json",
            "distress_network_causal_data.json",
            "public_service_network_data.json",
            "public_service_network_causal_data.json",
        ),
        "d2": (
            "panel_observational_contract.json",
            "dynamic_treatment_contract.json",
            "microsim_survey_contract_preview.json",
            "survival_contract.json",
            "panel_econometric_contract.json",
        ),
        "d3": ("microsim_survey_contract_v1.json",),
    }
    missing_stages = sorted(set(required_outputs).difference(stage_manifests))
    if missing_stages:
        raise ValueError("missing Ukraine stage manifests: " + ",".join(missing_stages))

    try:
        receipts = {
            stage_id: read_api.ukraine.load_verified_stage_artifacts(
                Path(stage_manifests[stage_id]),
                store=store,
                allowed_root=allowed_root,
                expected_stage=stage_id,
                required_outputs=outputs,
            )
            for stage_id, outputs in required_outputs.items()
        }
    except Exception as exc:
        raise ValueError(f"Ukraine intake receipt verification failed: {exc}") from exc

    json_snapshot_profile_reads: dict[str, read_api.ukraine.UkraineJSONSnapshotProvenance] = {}
    runtime_bundle = _load_verified_json_output(
        store,
        receipts["d0_p0"],
        "runtime_bundle_manifest.json",
        json_snapshot_profile_reads=json_snapshot_profile_reads,
        consumer_contract="foundry.ukraine.runtime_bundle_manifest",
    )
    data_snapshot_id = runtime_bundle.get("data_snapshot_artifact_id")
    raw_data_snapshot_ref = runtime_bundle.get("data_snapshot_ref")
    if data_snapshot_id is not None and (
        not isinstance(data_snapshot_id, str) or not data_snapshot_id.strip()
    ):
        raise ValueError("runtime_bundle_manifest has invalid data_snapshot_artifact_id")
    if raw_data_snapshot_ref is not None:
        try:
            data_snapshot_ref = DataSnapshotRef.model_validate(raw_data_snapshot_ref)
        except Exception as exc:
            raise ValueError("runtime_bundle_manifest has invalid data_snapshot_ref") from exc
        if (
            data_snapshot_ref.kind != DataSnapshot.ARTIFACT_KIND
            or data_snapshot_ref.media_type != DataSnapshot.ARTIFACT_MEDIA_TYPE
        ):
            raise ValueError(
                "runtime_bundle_manifest DataSnapshot ref has the wrong artifact contract"
            )
        if data_snapshot_id is not None and data_snapshot_id != str(data_snapshot_ref.artifact_id):
            raise ValueError(
                "runtime_bundle_manifest DataSnapshot ref does not match its artifact ID"
            )
        _verify_selected_data_snapshot_schema(store, data_snapshot_ref)
    else:
        if not isinstance(data_snapshot_id, str) or not data_snapshot_id.strip():
            raise ValueError("runtime_bundle_manifest is missing data_snapshot_artifact_id")
        try:
            # Legacy ID-only manifests remain unqualified: never infer a selected profile from ID.
            data_snapshot_ref = DataSnapshotRef(artifact_id=data_snapshot_id)
        except Exception as exc:
            raise ValueError(
                "runtime_bundle_manifest has invalid data_snapshot_artifact_id"
            ) from exc

    contract_specs: tuple[tuple[str, str, str, type[Any]], ...] = (
        (
            "d1_multiplex_network",
            "d1",
            "multiplex_network_data.json",
            MultiplexNetworkData,
        ),
        ("d1_trade_network", "d1", "trade_network_data.json", NetworkData),
        (
            "d1_trade_network_causal",
            "d1",
            "trade_network_causal_data.json",
            NetworkCausalData,
        ),
        ("d1_distress_network", "d1", "distress_network_data.json", NetworkData),
        (
            "d1_distress_network_causal",
            "d1",
            "distress_network_causal_data.json",
            NetworkCausalData,
        ),
        (
            "d1_public_service_network",
            "d1",
            "public_service_network_data.json",
            NetworkData,
        ),
        (
            "d1_public_service_network_causal",
            "d1",
            "public_service_network_causal_data.json",
            NetworkCausalData,
        ),
        (
            "d2_panel_observational",
            "d2",
            "panel_observational_contract.json",
            PanelObservationalData,
        ),
        (
            "d2_dynamic_treatment",
            "d2",
            "dynamic_treatment_contract.json",
            DynamicTreatmentData,
        ),
        (
            "d2_microsim_survey",
            "d2",
            "microsim_survey_contract_preview.json",
            SurveyMicroData,
        ),
        ("d2_survival", "d2", "survival_contract.json", SurvivalData),
        ("d2_panel_econometric", "d2", "panel_econometric_contract.json", PanelData),
        (
            "d3_microsim_survey",
            "d3",
            "microsim_survey_contract_v1.json",
            SurveyMicroData,
        ),
    )
    method_contracts: dict[str, Any] = {}
    validated_contracts: dict[str, dict[str, str]] = {}
    for contract_name, stage_id, output_name, model_type in contract_specs:
        try:
            registry_spec = _METHOD_CONTRACT_ALLOW_REGISTRY[model_type.contract_id]
            method_contracts[contract_name] = materialize_method_contract(
                contract_target=ContractCompatibilityTarget(
                    contract_id=model_type.contract_id,
                    contract_fqn=registry_spec.contract_fqn,
                ),
                contract_payload=_load_verified_json_output(
                    store,
                    receipts[stage_id],
                    output_name,
                    json_snapshot_profile_reads=json_snapshot_profile_reads,
                    consumer_contract=f"foundry.ukraine.method_input.{contract_name}",
                ),
            )
        except Exception as exc:
            raise ValueError(f"invalid Ukraine method contract {contract_name}: {exc}") from exc
        output = receipts[stage_id].outputs[output_name]
        validated_contracts[contract_name] = {
            "contract_id": str(model_type.contract_id),
            "source_path": output.source_path,
            "content_ref": str(output.content_ref.artifact_id),
            "sha256": output.sha256,
            "source_snapshot_profile": json_snapshot_profile_reads[
                f"{stage_id}:{output_name}"
            ].model_dump(mode="json"),
        }

    proxy_identification_bundle = _load_verified_json_output(
        store,
        receipts["d1"],
        "proxy_identification_bundle_v1.json",
        json_snapshot_profile_reads=json_snapshot_profile_reads,
        consumer_contract="foundry.ukraine.proxy_identification_bundle",
    )
    if not proxy_identification_bundle.get("proxy_channels"):
        raise ValueError("Ukraine proxy-identification bundle has no proxy_channels")

    stage_receipt_refs: dict[str, ArtifactRef] = {}
    for stage_id, stage_receipt in receipts.items():
        stage_inputs = [
            InputRef(
                artifact_id=stage_receipt.manifest_ref.artifact_id,
                role="verified_stage_manifest",
            )
        ]
        stage_inputs.extend(
            InputRef(
                artifact_id=output.content_ref.artifact_id,
                role=f"verified_stage_output:{output_name}",
            )
            for output_name, output in sorted(stage_receipt.outputs.items())
        )
        stage_receipt_refs[stage_id] = store.put_json(
            stage_receipt,
            PutOptions(
                kind="foundry.ukraine_stage_intake_receipt",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.foundry.UkraineStageIntakeReceipt",
                    version="2.0",
                ),
                inputs=stage_inputs,
            ),
        )

    method_contract_refs: dict[str, ArtifactRef] = {}
    method_input_contracts: dict[str, _UkraineMethodInputContract] = {}
    contract_specs_by_name = {spec[0]: spec for spec in contract_specs}
    for contract_name, contract in method_contracts.items():
        _, stage_id, output_name, model_type = contract_specs_by_name[contract_name]
        output_ref = receipts[stage_id].outputs[output_name].content_ref
        contract_ref = store.put_json(
            to_python_data(contract, sort_keys=True),
            PutOptions(
                kind="foundry.ukraine_method_input",
                media_type="application/json",
                schema=SchemaInfo(name=str(model_type.contract_id), version="1.0"),
                inputs=[
                    InputRef(
                        artifact_id=output_ref.artifact_id,
                        role="verified_stage_output",
                    ),
                    InputRef(
                        artifact_id=stage_receipt_refs[stage_id].artifact_id,
                        role="verified_stage_receipt",
                    ),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        method_contract_refs[contract_name] = contract_ref
        is_panel_consumer = contract_name == "d2_panel_observational"
        method_input_contracts[contract_name] = _UkraineMethodInputContract(
            contract_id=str(model_type.contract_id),
            artifact_ref=contract_ref,
            stage_receipt_ref=stage_receipt_refs[stage_id],
            source_snapshot_profile=json_snapshot_profile_reads[f"{stage_id}:{output_name}"],
            consumption_state=(
                "exercised_workflow_consumer" if is_panel_consumer else "selectable_unselected"
            ),
            residual_state="none" if is_panel_consumer else "consumer_missing",
            workflow_consumer=(
                "scientist_causal_full.run_causal_evaluation" if is_panel_consumer else None
            ),
        )

    method_input_bundle = _UkraineMethodInputBundle(
        contracts=method_input_contracts,
        source_snapshot_profile_reads=json_snapshot_profile_reads,
    )
    method_input_bundle_ref = store.put_json(
        method_input_bundle,
        PutOptions(
            kind="foundry.ukraine_method_input_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.UkraineMethodInputBundle",
                version="1.0",
            ),
            inputs=[
                *(
                    InputRef(
                        artifact_id=ref.artifact_id,
                        role=f"method_contract:{key}",
                    )
                    for key, ref in sorted(method_contract_refs.items())
                ),
                *(
                    InputRef(
                        artifact_id=ref.artifact_id,
                        role=f"stage_receipt:{stage_id}",
                    )
                    for stage_id, ref in sorted(stage_receipt_refs.items())
                ),
            ],
        ),
    )

    receipt = {
        "schema_version": "polisyos.foundry.ukraine_intake_receipt.v1",
        "authority_purpose": "producer_artifact_content_binding",
        "may_not_use_for": ["governance_admissibility", "method_validity"],
        "stage_receipts": {
            stage_id: receipt.model_dump(mode="json") for stage_id, receipt in receipts.items()
        },
        "validated_contracts": validated_contracts,
        "source_snapshot_profile_reads": {
            key: value.model_dump(mode="json")
            for key, value in sorted(json_snapshot_profile_reads.items())
        },
        "method_input_bundle_ref": method_input_bundle_ref.model_dump(mode="json"),
        "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
        "json_snapshot_profile_reads": {
            key: value.model_dump(mode="json")
            for key, value in sorted(json_snapshot_profile_reads.items())
        },
        "proxy_identification_bundle": {
            "source_path": receipts["d1"]
            .outputs["proxy_identification_bundle_v1.json"]
            .source_path,
            "content_ref": str(
                receipts["d1"]
                .outputs["proxy_identification_bundle_v1.json"]
                .content_ref.artifact_id
            ),
            "sha256": receipts["d1"].outputs["proxy_identification_bundle_v1.json"].sha256,
        },
    }
    receipt_ref = store.put_json(
        receipt,
        PutOptions(
            kind="foundry.ukraine_intake_receipt",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.UkraineIntakeReceipt", version="1.0"),
            inputs=[
                InputRef(
                    artifact_id=method_input_bundle_ref.artifact_id,
                    role="method_input_bundle",
                ),
                input_ref_from_artifact_ref(data_snapshot_ref, role="data_snapshot"),
                *(
                    InputRef(
                        artifact_id=ref.artifact_id,
                        role=f"stage_receipt:{stage_id}",
                    )
                    for stage_id, ref in sorted(stage_receipt_refs.items())
                ),
            ],
        ),
    )

    return UkraineFoundryIntakeResult(
        data_snapshot_ref=data_snapshot_ref,
        proxy_identification_bundle=proxy_identification_bundle,
        method_contracts=method_contracts,
        method_contract_refs=method_contract_refs,
        stage_receipt_refs=stage_receipt_refs,
        method_input_bundle_ref=method_input_bundle_ref,
        receipt_ref=receipt_ref,
        source_snapshot_profile_reads=json_snapshot_profile_reads,
    )


def _load_verified_json_output(
    store: FileSystemCAS,
    receipt: Any,
    output_name: str,
    *,
    json_snapshot_profile_reads: dict[str, read_api.ukraine.UkraineJSONSnapshotProvenance],
    consumer_contract: str,
) -> dict[str, Any]:
    """Load one JSON output through the shared status-gated snapshot reader."""
    read = read_api.ukraine.load_verified_stage_json_output(
        store,
        receipt,
        output_name,
        model_type=dict[str, Any],
        consumer_contract=consumer_contract,
    )
    json_snapshot_profile_reads[f"{receipt.stage_id}:{output_name}"] = read.provenance
    value = read.value_for_candidate()
    if not isinstance(value, dict):
        raise ValueError(f"JSON output {output_name} must be an object")
    return value


def _verify_registered_sql_transport(
    store: CoreJSONArtifactStore,
    *,
    snapshot: DataSnapshot,
    snapshot_ref: ArtifactRef,
    admission_ref: ArtifactRef,
) -> None:
    """Bind one selected transport to the actual snapshot; this is not authority."""
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts import RegisteredSQLAdmissionBinding

    binding = validate_core_model_json_artifact(RegisteredSQLAdmissionBinding, store, admission_ref)
    materialization = binding.materialization
    if artifact_ref_identity_key(materialization.snapshot_ref) != artifact_ref_identity_key(
        snapshot_ref
    ):
        raise ValueError("registered_sql_binding_snapshot_mismatch")
    refs = [
        input_ref_from_artifact_ref(snapshot_ref, role="source.snapshot"),
        input_ref_from_artifact_ref(
            materialization.registration.effective_view_contract_ref, role="source.view"
        ),
        input_ref_from_artifact_ref(
            materialization.registration.use_contract_ref, role="source.use"
        ),
        *(
            input_ref_from_artifact_ref(ref, role="snapshot." + role)
            for ref, role in data_snapshot_owner_input_requirements(snapshot)
        ),
        input_ref_from_artifact_ref(materialization.producer_capture_ref, role="source.capture"),
    ]
    manifest = store.get_manifest(admission_ref)

    def key(edge: InputRef) -> tuple[str, str, str | None]:
        return (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256)

    if (
        any(edge.manifest_profile_sha256 is None for edge in refs)
        or Counter(map(key, manifest.inputs)) != Counter(map(key, refs))
        or not store.verify(admission_ref).ok
    ):
        raise ValueError("registered_sql_binding_edges_not_established")


def _prepare_input_binding_values(
    store: CoreJSONArtifactStore,
    *,
    snapshot: DataSnapshot,
    slot_registry: SlotRegistry,
    binding_payload: Any,
    rules: list[FoundryInputBindingRule] | None,
    selected_tensor_policies: Mapping[str, _SelectedBindingTensorPolicy] | None = None,
) -> InputBindingsPreparation:
    """Run the same pure rule/state owner for persisted and prospective inputs.

    This internal numerical operation does not resolve or admit the supplied
    payload. The public preparation resolves its CAS source first; a prospective
    caller must separately own its payload and revalidate it before emission.
    """
    effective_rules = _prepare_rules(
        rules=rules,
        slot_registry=slot_registry,
        payload=binding_payload,
        explicit_only=selected_tensor_policies is not None,
    )
    _validate_rules(
        effective_rules, slot_registry, selected_tensor_policies=selected_tensor_policies
    )

    base_state = _build_base_state(
        store=store,
        snapshot=snapshot,
        payload=binding_payload,
        slot_registry=slot_registry,
        rules=effective_rules,
    )

    values = _prepare_materialized_binding_values(
        base_state=base_state,
        effective_rules=effective_rules,
        slot_registry=slot_registry,
        binding_payload=binding_payload,
        selected_tensor_policies=selected_tensor_policies,
    )
    return InputBindingsPreparation(
        snapshot=snapshot,
        effective_rules=values.effective_rules,
        materialized_state=values.materialized_state,
        applied_binding_ids=values.applied_binding_ids,
        warnings=values.warnings,
    )


def _prepare_materialized_binding_values(
    *,
    base_state: GlobalState,
    effective_rules: list[FoundryInputBindingRule],
    slot_registry: SlotRegistry,
    binding_payload: Any,
    selected_tensor_policies: Mapping[str, _SelectedBindingTensorPolicy] | None = None,
) -> InputBindingValuesPreparation:
    """Single materialization/error fold for persisted and prospective payloads."""

    materialized_state, applied_ids, errors, warnings = _materialize_state(
        base_state=base_state,
        rules=effective_rules,
        slot_registry=slot_registry,
        payload=binding_payload,
        selected_tensor_policies=selected_tensor_policies,
    )
    if errors:
        raise ValueError("; ".join(errors))
    return InputBindingValuesPreparation(
        effective_rules=tuple(effective_rules),
        materialized_state=materialized_state,
        applied_binding_ids=tuple(applied_ids),
        warnings=tuple(warnings),
    )


def prepare_json_input_binding_values(
    store: CoreJSONArtifactStore,
    *,
    payload_json: bytes,
    registry_bundle_ref: ArtifactRef,
    rules: list[FoundryInputBindingRule] | None = None,
) -> InputBindingValuesPreparation:
    """Compute an immutable JSON payload's actual binding values without writes.

    Args:
        store: Existing registry owner store; no artifact writes are performed.
        payload_json: Prospective JSON object bytes from the caller's producer.
        registry_bundle_ref: Real registry resolved through its existing owner.
        rules: Full explicit rule set, or the existing inference behavior.

    Returns:
        Complete actual rule/state values from the maintained numerical owner.

    Raises:
        TypeError: If the payload is not immutable JSON bytes.
        ValueError: If JSON, source paths, rules or numerical values are invalid.

    This port cannot admit a source, fabricate a DataSnapshot, or establish a
    semantic equality decision. Source custody and eligibility are resolved by
    the caller's actual source owner before use and again before emission.
    """

    if type(payload_json) is not bytes:
        raise TypeError("prospective_input_payload_requires_immutable_json_bytes")

    def reject_non_json_number(value: str) -> NoReturn:
        raise ValueError(f"prospective_input_payload_non_json_number:{value}")

    payload = json.loads(payload_json, parse_constant=reject_non_json_number)
    if type(payload) is not dict:
        raise ValueError("prospective_input_payload_not_object")
    # The real materializer emits a Core CAN.2 JSON artifact before Foundry
    # reads it. Reuse that complete encode/decode law here, including numeric
    # normalization and typed values; raw JSON parsing is not the consumed value.
    payload = from_canonical_bytes(to_canonical_bytes(payload, CanonSpec(forbid_floats=False)))
    registry = load_registry_bundle_content(store, registry_bundle_ref)
    effective_rules = _prepare_rules(
        rules=rules, slot_registry=registry.slot_registry, payload=payload
    )
    _validate_rules(effective_rules, registry.slot_registry)
    base_state = _build_payload_base_state(
        payload=payload, rules=effective_rules, slot_registry=registry.slot_registry
    )
    return _prepare_materialized_binding_values(
        base_state=base_state,
        effective_rules=effective_rules,
        slot_registry=registry.slot_registry,
        binding_payload=payload,
    )


def prepare_input_bindings(
    store: CoreJSONArtifactStore,
    *,
    data_snapshot_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef,
    rules: list[FoundryInputBindingRule] | None = None,
    registered_sql_admission_ref: ArtifactRef | None = None,
    resolved_binding_manifest_ref: ResolvedInputBindingManifestRef | None = None,
) -> InputBindingsPreparation:
    """Resolve real input owners and compute bindings without CAS writes.

    Args:
        store: Existing store containing the selected snapshot and registry.
        data_snapshot_ref: Exact snapshot resolved by the maintained reader.
        registry_bundle_ref: Exact registry resolved by its canonical owner.
        rules: Explicit rules, or None for the existing inference behavior.
        registered_sql_admission_ref: Optional selected SQL transport, rechecked
            before numerical preparation; it does not itself grant authority.
        resolved_binding_manifest_ref: Optional exact candidate selection whose
            proof and predecessor rules must be replayed before materialization.

    Returns:
        The freshly resolved snapshot, complete effective rule tuple and actual
        materialized state, applied IDs and warnings used by the writer.

    Raises:
        ValueError: If existing source, rule or state owner validation refuses.
    """
    if resolved_binding_manifest_ref is not None:
        if registered_sql_admission_ref is not None:
            raise ValueError("foundry_input_bindings_semantic_sql_replay_not_established")
        return _prepare_semantic_input_bindings(
            store,
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            resolved_binding_manifest_ref=resolved_binding_manifest_ref,
            rules=rules,
        )
    snapshot = _load_data_snapshot(store, data_snapshot_ref)
    if _snapshot_requires_resolved_input_manifest(snapshot):
        raise ValueError("foundry_input_bindings_semantic_manifest_required")
    if registered_sql_admission_ref is not None:
        if (
            data_snapshot_ref.manifest_profile_sha256 is None
            or registry_bundle_ref.manifest_profile_sha256 is None
            or registered_sql_admission_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("registered_sql_binding_selected_profile_required")
        _verify_registered_sql_transport(
            store,
            snapshot=snapshot,
            snapshot_ref=data_snapshot_ref,
            admission_ref=registered_sql_admission_ref,
        )
    registry = load_registry_bundle_content(store, registry_bundle_ref)
    binding_payload = _load_binding_payload(store, snapshot)
    replayed: bytes | None = None
    if registered_sql_admission_ref is not None:
        effective_rules = _prepare_rules(
            rules=rules, slot_registry=registry.slot_registry, payload=binding_payload
        )
        replayed, _ = _recompute_registered_sql_state(
            store,
            snapshot=snapshot,
            payload=binding_payload,
            slot_registry=registry.slot_registry,
            rules=effective_rules,
        )
    preparation = _prepare_input_binding_values(
        store,
        snapshot=snapshot,
        slot_registry=registry.slot_registry,
        binding_payload=binding_payload,
        rules=rules,
    )
    if registered_sql_admission_ref is not None:
        from polisyos.foundry.execute._internal.snapshots import _flatten_state

        expected = BytesIO()
        np.savez(expected, **dict(_flatten_state(preparation.materialized_state)))
        if replayed is None or expected.getvalue() != replayed:
            raise ValueError("registered_sql_binding_preparation_replay_mismatch")
    return preparation


def build_input_bindings(
    store: CoreJSONArtifactStore,
    *,
    data_snapshot_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef,
    rules: list[FoundryInputBindingRule] | None = None,
    quality_report_ref: ArtifactRef | None = None,
    notes: list[str] | None = None,
    return_selected_profile: bool = False,
    registered_sql_admission_ref: ArtifactRef | None = None,
    resolved_binding_manifest_ref: ResolvedInputBindingManifestRef | None = None,
) -> InputBindingsBuildResult:
    """Bind a Fabric snapshot into a concrete `GlobalState` runtime snapshot.

    Explicit `rules` are validated against the registry slot schema; when no
    rules are supplied, bindings are inferred from payload paths that match
    slot IDs or slot `state_path` values. The function writes
    `foundry.input_bindings`, `foundry.input_binding_report`, and a bound
    `foundry.state_snapshot` artifact into CAS.

    Args:
        store: CAS containing the Fabric `DataSnapshot` and registry bundle and
            receiving the bound state and binding artifacts.
        data_snapshot_ref: Artifact reference to the Fabric data snapshot, or
            a snapshot wrapper around an existing `foundry.state_snapshot`.
        registry_bundle_ref: Registry bundle used to validate slot IDs,
            infer entity sizes, and resolve `state_path` mappings.
        rules: Optional explicit binding rules. If omitted, rules are inferred
            from payload paths.
        quality_report_ref: Optional quality report to attach to the generated
            `FoundryInputBindings` artifact.
        notes: Optional free-form notes copied into the persisted bindings.
        return_selected_profile: Return the exact profiles emitted by this write.
        registered_sql_admission_ref: Optional selected registered SQL transport.
        resolved_binding_manifest_ref: Exact candidate selection for semantic inputs.

    Returns:
        `InputBindingsBuildResult` with the boundary artifact refs needed by
        `execute()`.

    Raises:
        ValueError: If a binding rule references an unknown slot, duplicates a
            `binding_id`, or required source values cannot be materialized into
            the target state path.

    Example:
        ```python
        from polisyos.foundry.data_plane.bindings import build_input_bindings

        built = build_input_bindings(
            store,
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
        )
        execute_request = execute_request.model_copy(
            update={"input_bindings_ref": built.input_bindings_ref}
        )
        ```
    """

    if registered_sql_admission_ref is not None and not return_selected_profile:
        raise ValueError("registered_sql_binding_selected_profile_required")
    if resolved_binding_manifest_ref is not None and not return_selected_profile:
        raise ValueError("foundry_input_bindings_semantic_profile_required")
    preparation = prepare_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=rules,
        registered_sql_admission_ref=registered_sql_admission_ref,
        resolved_binding_manifest_ref=resolved_binding_manifest_ref,
    )
    snapshot = preparation.snapshot
    effective_rules = list(preparation.effective_rules)
    materialized_state = preparation.materialized_state
    applied_ids = preparation.applied_binding_ids
    warnings = list(preparation.warnings)

    snapshot_inputs = [
        input_ref_from_artifact_ref(data_snapshot_ref, role="input.data_snapshot_ref"),
        input_ref_from_artifact_ref(registry_bundle_ref, role="input.registry_bundle_ref"),
    ]
    selected_method_inputs: list[FoundrySelectedMethodInput] = []
    for selected in preparation.selected_method_inputs:
        value_ref = put_tensor(
            store,
            selected.value,
            return_selected_profile=True,
            kind="foundry.selected_method_input_value",
            inputs=list(selected.lineage_inputs),
        )
        selected_method_inputs.append(
            FoundrySelectedMethodInput(
                model_input_obligation_ref=selected.model_input_obligation_ref,
                binding_id=selected.binding_id,
                port_id=selected.port_id,
                slot_id=selected.slot_id,
                canonical_value=selected.canonical_value,
                dtype=selected.value.dtype.name,
                shape=selected.value.shape,
                npy_value_ref=value_ref,
                value_sha256=_selected_method_tensor_digest(selected.value),
            )
        )
    if preparation.reused_bound_state_snapshot_ref is not None:
        if not selected_method_inputs:
            raise ValueError("foundry_selected_method_input_prestate_without_values")
        bound_state_snapshot_ref = preparation.reused_bound_state_snapshot_ref
    else:
        if selected_method_inputs:
            raise ValueError("foundry_selected_method_input_prestate_missing")
        bound_snapshot_ref = put_state_snapshot(
            store,
            state=materialized_state,
            step=int(np.asarray(materialized_state.step).item()),
            inputs=snapshot_inputs,
            return_selected_profile=return_selected_profile,
        )
        bound_state_snapshot_ref = StateSnapshotRef.model_validate(
            bound_snapshot_ref.model_dump(mode="python")
        )
    if registered_sql_admission_ref is not None:
        registry = load_registry_bundle_content(store, registry_bundle_ref)
        binding_payload = _load_binding_payload(store, snapshot)
        _reconcile_registered_sql_bound_state(
            store,
            snapshot=snapshot,
            payload=binding_payload,
            slot_registry=registry.slot_registry,
            rules=effective_rules,
            bound_state_ref=bound_state_snapshot_ref,
            lineage_inputs=snapshot_inputs,
        )

    bindings_notes = list(notes or [])
    if snapshot.data_ref.kind == "foundry.state_snapshot":
        bindings_notes.append("compatibility:data_snapshot_contains_foundry_state_snapshot")
    bindings_notes.extend(_snapshot_binding_notes(snapshot))
    warnings.extend(_snapshot_binding_warnings(snapshot))
    if warnings:
        bindings_notes.extend([f"warning:{msg}" for msg in warnings])

    bindings = FoundryInputBindings(
        schema_version=(
            "1.4"
            if selected_method_inputs
            else "1.2"
            if resolved_binding_manifest_ref is not None
            else "1.1"
            if registered_sql_admission_ref is not None
            else "1.0"
        ),
        data_snapshot_ref=data_snapshot_ref,
        registered_sql_admission_ref=registered_sql_admission_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=effective_rules,
        bound_state_snapshot_ref=bound_state_snapshot_ref,
        quality_report_ref=quality_report_ref or snapshot.quality_report_ref,
        notes=bindings_notes,
        **(
            {"resolved_binding_manifest_ref": resolved_binding_manifest_ref}
            if resolved_binding_manifest_ref is not None
            else {}
        ),
        **(
            {"selected_method_inputs": tuple(selected_method_inputs)}
            if selected_method_inputs
            else {}
        ),
    )
    bindings_ref_payload = store.put_json(
        bindings,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version=bindings.schema_version,
            ),
            inputs=[
                input_ref_from_artifact_ref(data_snapshot_ref, role="input.data_snapshot_ref"),
                input_ref_from_artifact_ref(
                    registry_bundle_ref,
                    role="input.registry_bundle_ref",
                ),
                input_ref_from_artifact_ref(
                    bound_state_snapshot_ref,
                    role="artifact.bound_state_snapshot_ref",
                ),
                *_selected_method_binding_inputs(tuple(selected_method_inputs)),
                *(
                    [
                        input_ref_from_artifact_ref(
                            resolved_binding_manifest_ref,
                            role=RESOLVED_INPUT_BINDING_MANIFEST_ROLE,
                        )
                    ]
                    if resolved_binding_manifest_ref is not None
                    else []
                ),
                *(
                    [
                        input_ref_from_artifact_ref(
                            registered_sql_admission_ref,
                            role="input.registered_sql_admission_ref",
                        )
                    ]
                    if registered_sql_admission_ref is not None
                    else []
                ),
                *(
                    [
                        input_ref_from_artifact_ref(
                            quality_report_ref or snapshot.quality_report_ref,
                            role="input.quality_report_ref",
                        )
                    ]
                    if quality_report_ref or snapshot.quality_report_ref
                    else []
                ),
            ],
        ),
        return_selected_profile=return_selected_profile,
    )

    report_payload = {
        "schema_version": "1.1",
        "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
        "registry_bundle_ref": registry_bundle_ref.model_dump(mode="json"),
        "bound_state_snapshot_ref": bound_state_snapshot_ref.model_dump(mode="json"),
        "rule_count": len(effective_rules),
        "applied_binding_ids": list(applied_ids),
        "warning_count": len(warnings),
        "warnings": warnings,
        "notes": bindings_notes,
    }
    report_ref_payload = store.put_json(
        report_payload,
        PutOptions(
            kind="foundry.input_binding_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FoundryInputBindingReport", version="1.1"),
            inputs=[
                input_ref_from_artifact_ref(
                    bindings_ref_payload,
                    role="artifact.input_bindings_ref",
                ),
                input_ref_from_artifact_ref(
                    bound_state_snapshot_ref,
                    role="artifact.bound_state_snapshot_ref",
                ),
                input_ref_from_artifact_ref(data_snapshot_ref, role="input.data_snapshot_ref"),
                input_ref_from_artifact_ref(
                    registry_bundle_ref,
                    role="input.registry_bundle_ref",
                ),
                *(
                    [
                        input_ref_from_artifact_ref(
                            quality_report_ref or snapshot.quality_report_ref,
                            role="input.quality_report_ref",
                        )
                    ]
                    if quality_report_ref or snapshot.quality_report_ref
                    else []
                ),
            ],
        ),
        return_selected_profile=return_selected_profile,
    )

    return InputBindingsBuildResult(
        input_bindings_ref=FoundryInputBindingsRef.model_validate(
            bindings_ref_payload.model_dump(mode="python")
        ),
        input_binding_report_ref=FoundryInputBindingReportRef.model_validate(
            report_ref_payload.model_dump(mode="python")
        ),
        bound_state_snapshot_ref=bound_state_snapshot_ref,
        applied_binding_ids=applied_ids,
    )


def load_input_bindings(
    store: CoreJSONArtifactStore,
    ref: FoundryInputBindingsRef | ArtifactRef,
) -> FoundryInputBindings:
    """Load a persisted `FoundryInputBindings` boundary artifact from CAS.

    Args:
        store: CAS containing the serialized bindings artifact.
        ref: Either a typed `FoundryInputBindingsRef` or a plain artifact ref
            whose `artifact_id` points to a `foundry.input_bindings` payload.

    Returns:
        Parsed `FoundryInputBindings` model.
    """
    from polisyos.core.artifacts import validate_core_model_json_artifact

    bindings = validate_core_model_json_artifact(FoundryInputBindings, store, ref)
    if bindings.resolved_binding_manifest_ref is not None:
        if ref.manifest_profile_sha256 is None:
            raise ValueError("foundry_input_bindings_semantic_profile_required")
        require_resolved_input_binding_manifest_edge(bindings, store.get_manifest(ref))
    return bindings


def require_resolved_input_binding_manifest_edge(
    bindings: FoundryInputBindings, manifest: ArtifactManifest
) -> None:
    """Require the binding's semantic field and exact manifest edge to agree."""
    ref = bindings.resolved_binding_manifest_ref
    expected = (
        []
        if ref is None
        else [input_ref_from_artifact_ref(ref, role=RESOLVED_INPUT_BINDING_MANIFEST_ROLE)]
    )
    actual = [edge for edge in manifest.inputs if edge.role == RESOLVED_INPUT_BINDING_MANIFEST_ROLE]
    if actual != expected:
        raise ValueError("foundry_input_bindings_semantic_manifest_edge_mismatch")
    if ref is not None:
        sql_ref = bindings.registered_sql_admission_ref
        sql_role = "input.registered_sql_admission_ref"
        if [edge for edge in manifest.inputs if edge.role == sql_role] != (
            [] if sql_ref is None else [input_ref_from_artifact_ref(sql_ref, role=sql_role)]
        ):
            raise ValueError("foundry_input_bindings_semantic_sql_edge_mismatch")
        _require_selected_binding_edges(
            manifest,
            {
                "input.data_snapshot_ref": bindings.data_snapshot_ref,
                "input.registry_bundle_ref": bindings.registry_bundle_ref,
                "artifact.bound_state_snapshot_ref": bindings.bound_state_snapshot_ref,
            },
            reason="foundry_input_bindings_semantic_lineage_mismatch",
        )
        if [edge for edge in manifest.inputs if edge.role.startswith("method_input.")] != (
            _selected_method_binding_inputs(bindings.selected_method_inputs or ())
        ):
            raise ValueError("foundry_selected_method_input_binding_lineage_mismatch")


def _selected_method_binding_inputs(
    records: tuple[FoundrySelectedMethodInput, ...],
) -> list[InputRef]:
    inputs: list[InputRef] = []
    for record in records:
        inputs.extend(
            (
                input_ref_from_artifact_ref(
                    record.model_input_obligation_ref,
                    role=f"method_input.{record.binding_id}.obligation",
                ),
                input_ref_from_artifact_ref(
                    record.npy_value_ref, role=f"method_input.{record.binding_id}.value"
                ),
            )
        )
    return inputs


def _selected_method_value_inputs(
    manifest_ref: ResolvedInputBindingManifestRef,
    selection: ResolvedMeasurementInput | ResolvedDerivedInput,
) -> tuple[InputRef, ...]:
    source_ref = (
        selection.selected_occurrence_ref
        if isinstance(selection, ResolvedMeasurementInput)
        else selection.output_ref
    )
    return (
        input_ref_from_artifact_ref(
            selection.model_input_obligation_ref, role="target.model_input_obligation"
        ),
        input_ref_from_artifact_ref(manifest_ref, role="input.resolved_binding_manifest"),
        input_ref_from_artifact_ref(source_ref, role="source.selected_value"),
        input_ref_from_artifact_ref(selection.correspondence_ref, role="source.correspondence"),
    )


def _prepare_selected_method_input(
    store: CoreJSONArtifactStore,
    *,
    selection: ResolvedMeasurementInput | ResolvedDerivedInput,
    manifest_ref: ResolvedInputBindingManifestRef,
    obligation: ModelInputObligation,
    canonical_value: Decimal,
    physical_value: object,
) -> _PreparedSelectedMethodInput:
    port = obligation.port
    registry = load_registry_bundle_content(store, obligation.registry_bundle_ref)
    slots = registry.slot_registry
    slot = slots.slots.get(port.slot_id)
    encoding = port.physical_encoding
    if (
        port.carrier != "method_input"
        or port.state_path is not None
        or slot is None
        or slot.state_path
        or slot.scope != SlotScope.GLOBAL
        or slot.kind != SlotKind.FLOW
        or slot.shape
        or slot.value_type != SlotValueType.DECIMAL
        or slot.unit is None
        or slot.unit.unit_id != port.unit_id
        or encoding is None
        or encoding.shape
        or (slot.dtype is not None and slot.dtype != encoding.dtype)
        or (slot.shape and tuple(slot.shape) != encoding.shape)
    ):
        raise ValueError("foundry_selected_method_input_port_encoding_mismatch")
    representation = load_variable_representation(store, port.representation_ref)
    money = representation.money_unit
    canonical_money = (
        None if registry.units_registry is None else registry.units_registry.units.get(port.unit_id)
    )
    if (
        not isinstance(canonical_money, MoneyUnit)
        or money is None
        or money.currency != canonical_money.currency
        or (
            canonical_money.nominal_year is not None
            and money.nominal_year != canonical_money.nominal_year
        )
        or (
            canonical_money.price_base is not None
            and money.price_base != canonical_money.price_base
        )
    ):
        raise ValueError("foundry_selected_method_input_canonical_money_unit_mismatch")
    value = encode_selected_tensor(
        physical_value,
        shape=encoding.shape,
        dtype=encoding.dtype,
        max_absolute_error=encoding.max_absolute_error,
    )
    _selected_method_tensor_digest(value)
    return _PreparedSelectedMethodInput(
        model_input_obligation_ref=selection.model_input_obligation_ref,
        binding_id=selection.binding_id,
        port_id=port.port_id,
        slot_id=port.slot_id,
        canonical_value=canonical_value,
        value=value,
        lineage_inputs=_selected_method_value_inputs(manifest_ref, selection),
    )


def _selected_method_tensor_digest(value: np.ndarray) -> str:
    from polisyos.foundry.execute._internal.graph import _bounded_array_metadata

    if (
        not isinstance(value, np.ndarray)
        or _bounded_array_metadata(value) is None
        or not np.isfinite(value).all()
    ):
        raise ValueError("foundry_selected_method_input_value_not_bounded")
    contiguous = value if value.flags.c_contiguous else np.array(value, copy=True, order="C")
    return selected_tensor_value_sha256(
        value.dtype, tuple(value.shape), memoryview(contiguous).cast("B")
    )


def persist_activated_observation_input_manifest(
    store: CoreJSONArtifactStore,
    *,
    data_snapshot_ref: ArtifactRef,
    obligation_set_ref: ArtifactRef,
    expected_invocation: ProgramGraphInputInvocation,
) -> ResolvedInputBindingManifestRef:
    """Select candidate inputs from a single activated observation and its preflight.

    Args:
        store: CAS containing the selected snapshot, compiled inputs, and preflight.
        data_snapshot_ref: Exact acquired-observation semantic snapshot view.
        obligation_set_ref: Exact complete missing-input set emitted by preflight.
        expected_invocation: Current graph, predecessor, registry and execution
            context selected independently of the obligation set.

    Returns:
        The persisted candidate selection for Foundry's semantic input consumer.

    Raises:
        ValueError: If the selected snapshot, preflight, or predecessor disagrees.
    """
    from polisyos.foundry.execute.model_input_requirements import (
        verify_program_graph_input_preflight,
    )

    if data_snapshot_ref.manifest_profile_sha256 is None:
        raise ValueError("foundry_input_bindings_semantic_profile_required")
    snapshot = _load_data_snapshot(store, data_snapshot_ref)
    lineage = snapshot.source_lineage
    if not isinstance(lineage, AcquiredObservationSemanticInputDataSnapshotLineage):
        raise ValueError("foundry_input_bindings_acquired_observation_semantic_lineage_required")

    selected_set = verify_program_graph_input_preflight(
        store, obligation_set_ref=obligation_set_ref, expected_invocation=expected_invocation
    )
    if len(selected_set.obligation_refs) != 1:
        raise ValueError("foundry_input_bindings_semantic_obligation_set_mismatch")
    (obligation_ref,) = selected_set.obligation_refs
    obligation = validate_core_model_json_artifact(ModelInputObligation, store, obligation_ref)
    predecessor = load_input_bindings(store, expected_invocation.input_bindings_ref)
    _require_acquired_observation_binding_basis(lineage, obligation, predecessor)

    slots = load_registry_bundle_content(
        store, expected_invocation.registry_bundle_ref
    ).slot_registry
    retained = _replay_explicit_initial_bindings(
        store,
        expected_invocation.input_bindings_ref,
        predecessor,
        {
            slot_id: slots.slots[slot_id].state_path or ""
            for slot_id in selected_set.supplied_initial_slots
        },
    )
    selection = lineage.selection
    return persist_resolved_input_binding_manifest(
        store,
        ResolvedInputBindingManifest(
            data_snapshot_ref=SelectedVariableBindingRef.model_validate(
                data_snapshot_ref.model_dump(mode="python")
            ),
            model_input_obligation_set_ref=SelectedVariableBindingRef.model_validate(
                obligation_set_ref.model_dump(mode="python")
            ),
            measurements=(
                ResolvedMeasurementInput(
                    binding_id=selection.binding_id,
                    model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
                        obligation_ref.model_dump(mode="python")
                    ),
                    selected_occurrence_ref=selection.occurrence_ref,
                    correspondence_ref=selection.correspondence_basis_ref,
                    source_path=selection.source_path,
                ),
            ),
            retained_binding_ids=tuple(item.rule.binding_id for item in retained),
        ),
    )


def _require_acquired_observation_binding_basis(
    lineage: AcquiredObservationSemanticInputDataSnapshotLineage,
    obligation: ModelInputObligation,
    predecessor: FoundryInputBindings,
) -> None:
    if artifact_ref_identity_key(lineage.base_data_snapshot_ref) != artifact_ref_identity_key(
        predecessor.data_snapshot_ref
    ):
        raise ValueError("foundry_input_bindings_semantic_base_snapshot_mismatch")
    selection = lineage.selection
    if (
        artifact_ref_identity_key(obligation.interface_ref)
        != artifact_ref_identity_key(selection.model_interface_ref)
        or obligation.port.port_id != selection.model_port_id
    ):
        raise ValueError("foundry_input_bindings_semantic_snapshot_selection_mismatch")


def _prepare_semantic_input_bindings(
    store: CoreJSONArtifactStore,
    *,
    data_snapshot_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef,
    resolved_binding_manifest_ref: ResolvedInputBindingManifestRef,
    rules: list[FoundryInputBindingRule] | None,
    execute_request: ExecuteRequest | None = None,
    effective_step: int | None = None,
    semantic_horizon_step: SemanticHorizonStepContext | None = None,
    expected_invocation: ProgramGraphInputInvocation | None = None,
    historical_execution_ref: ArtifactRef | None = None,
    historical_input_bindings_ref: ArtifactRef | None = None,
) -> InputBindingsPreparation:
    """Join the invocation's use purpose before replaying its immutable inputs."""
    from polisyos.foundry.execute.model_input_requirements import (
        verify_program_graph_input_preflight,
    )

    manifest = load_resolved_input_binding_manifest(store, resolved_binding_manifest_ref)
    selected_set, _ = load_model_input_obligation_set(
        store, manifest.model_input_obligation_set_ref
    )
    invocation = selected_set.invocation
    if expected_invocation is not None and invocation != expected_invocation:
        raise ValueError("foundry_input_bindings_semantic_invocation_mismatch")
    if historical_execution_ref is None:
        verify_program_graph_input_preflight(
            store,
            obligation_set_ref=manifest.model_input_obligation_set_ref,
            expected_invocation=invocation,
        )
    else:
        if historical_input_bindings_ref is None:
            raise ValueError("foundry_selected_method_input_historical_binding_ref_required")
        _verify_historical_selected_method_invocation(
            store,
            historical_execution_ref=historical_execution_ref,
            input_bindings_ref=historical_input_bindings_ref,
            invocation=invocation,
            execute_request=execute_request,
            effective_step=effective_step,
            semantic_horizon_step=semantic_horizon_step,
        )
    return _prepare_semantic_input_binding_facts(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        resolved_binding_manifest_ref=resolved_binding_manifest_ref,
        rules=rules,
        execute_request=execute_request,
        effective_step=effective_step,
        semantic_horizon_step=semantic_horizon_step,
        expected_invocation=expected_invocation,
    )


def _prepare_semantic_input_binding_facts(
    store: CoreJSONArtifactStore,
    *,
    data_snapshot_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef,
    resolved_binding_manifest_ref: ResolvedInputBindingManifestRef,
    rules: list[FoundryInputBindingRule] | None,
    execute_request: ExecuteRequest | None = None,
    effective_step: int | None = None,
    semantic_horizon_step: SemanticHorizonStepContext | None = None,
    expected_invocation: ProgramGraphInputInvocation | None = None,
) -> InputBindingsPreparation:
    """Replay immutable source, semantic, and physical input facts only."""
    manifest = load_resolved_input_binding_manifest(store, resolved_binding_manifest_ref)
    if artifact_ref_identity_key(manifest.data_snapshot_ref) != artifact_ref_identity_key(
        data_snapshot_ref
    ):
        raise ValueError("foundry_input_bindings_semantic_snapshot_mismatch")
    proofs = {
        item.binding_id: _load_scoped_correspondence(store, item) for item in manifest.measurements
    }
    selected_set, members = load_model_input_obligation_set(
        store, manifest.model_input_obligation_set_ref
    )
    invocation = selected_set.invocation
    if expected_invocation is not None and invocation != expected_invocation:
        raise ValueError("foundry_input_bindings_semantic_invocation_mismatch")
    if semantic_horizon_step is not None and (
        artifact_ref_identity_key(semantic_horizon_step.obligation_set_ref)
        != artifact_ref_identity_key(manifest.model_input_obligation_set_ref)
        or semantic_horizon_step.steps != invocation.steps
    ):
        raise ValueError("foundry_input_bindings_semantic_horizon_mismatch")
    if len(invocation.steps) > 1 and any(
        member.port.purpose != "initial_state" for member in members
    ):
        raise ValueError("foundry_input_bindings_semantic_horizon_time_profile_unsupported")
    if artifact_ref_identity_key(invocation.registry_bundle_ref) != artifact_ref_identity_key(
        registry_bundle_ref
    ):
        raise ValueError("foundry_input_bindings_semantic_registry_mismatch")
    if execute_request is not None:
        for expected, actual in (
            (invocation.exec_plan_ref, execute_request.exec_plan_ref),
            (invocation.registry_bundle_ref, execute_request.registry_bundle_ref),
            (
                invocation.parameter_override_bundle_ref,
                execute_request.parameter_override_bundle_ref,
            ),
        ):
            if (None if expected is None else artifact_ref_identity_key(expected)) != (
                None if actual is None else artifact_ref_identity_key(actual)
            ):
                raise ValueError("foundry_input_bindings_semantic_execution_mismatch")
    if any(member.port.carrier == "method_input" for member in members):
        _verify_selected_method_invocation_facts(store, invocation=invocation)
    obligations = {
        artifact_ref_identity_key(ref): member
        for ref, member in zip(selected_set.obligation_refs, members, strict=True)
    }
    selected_refs = tuple(
        artifact_ref_identity_key(item.model_input_obligation_ref)
        for item in (*manifest.measurements, *manifest.derivations)
    )
    if len(selected_refs) != len(obligations) or set(selected_refs) != obligations.keys():
        raise ValueError("foundry_input_bindings_semantic_obligation_set_mismatch")

    snapshot = _load_data_snapshot(store, data_snapshot_ref)
    if snapshot.data_ref.manifest_profile_sha256 is None:
        raise ValueError("foundry_input_bindings_semantic_profile_required")
    predecessor = load_input_bindings(store, invocation.input_bindings_ref)
    if isinstance(snapshot.source_lineage, AcquiredObservationSemanticInputDataSnapshotLineage):
        if manifest.derivations:
            raise ValueError("foundry_input_bindings_derived_output_is_not_acquired_observation")
        if len(manifest.measurements) != 1:
            raise ValueError("foundry_input_bindings_semantic_snapshot_selection_mismatch")
        selected = manifest.measurements[0]
        obligation = obligations[artifact_ref_identity_key(selected.model_input_obligation_ref)]
        proof = proofs[selected.binding_id]
        _require_acquired_observation_binding_basis(
            snapshot.source_lineage, obligation, predecessor
        )
        owner_selection = snapshot.source_lineage.selection
        if (
            selected.binding_id != owner_selection.binding_id
            or selected.source_path != owner_selection.source_path
            or artifact_ref_identity_key(selected.selected_occurrence_ref)
            != artifact_ref_identity_key(owner_selection.occurrence_ref)
            or artifact_ref_identity_key(selected.correspondence_ref)
            != artifact_ref_identity_key(owner_selection.correspondence_basis_ref)
            or artifact_ref_identity_key(proof.source_definition_ref)
            != artifact_ref_identity_key(owner_selection.source_definition_ref)
            or artifact_ref_identity_key(proof.source_representation_ref)
            != artifact_ref_identity_key(owner_selection.source_representation_ref)
        ):
            raise ValueError("foundry_input_bindings_semantic_snapshot_selection_mismatch")
    payload = _load_binding_payload(store, snapshot)
    payload_manifest = store.get_manifest(snapshot.data_ref)
    if (
        isinstance(snapshot.source_lineage, DerivedModelInputDataSnapshotLineage)
        and snapshot.data_ref.kind != DERIVED_MODEL_INPUT_PAYLOAD_KIND
    ):
        raise ValueError("foundry_input_bindings_derived_payload_profile_required")
    if snapshot.data_ref.kind == DERIVED_MODEL_INPUT_PAYLOAD_KIND:
        if manifest.schema_version != "2.0" or not manifest.derivations:
            raise ValueError("foundry_input_bindings_derived_manifest_required")
        if payload_manifest.artifact_schema != SchemaInfo(
            name="polisyos.runtime.quality.DerivedModelInputPayload", version="1.0"
        ):
            raise ValueError("foundry_input_bindings_derived_payload_profile_mismatch")
        base_snapshot = _load_data_snapshot(store, predecessor.data_snapshot_ref)
        owner_manifest = store.get_manifest(data_snapshot_ref)
        lineage = snapshot.source_lineage
        if isinstance(lineage, DerivedModelInputDataSnapshotLineage):
            if (
                artifact_ref_identity_key(lineage.base_data_snapshot_ref)
                != artifact_ref_identity_key(predecessor.data_snapshot_ref)
                or artifact_ref_identity_key(lineage.model_input_obligation_set_ref)
                != artifact_ref_identity_key(manifest.model_input_obligation_set_ref)
                or lineage.selections != manifest.derivations
            ):
                raise ValueError("foundry_input_bindings_derived_snapshot_selection_mismatch")
            # _load_data_snapshot has already reconciled the complete canonical
            # owner-input denominator, including every selected recipe parent.
            base_context_checks = (
                (payload_manifest, "context.base_payload", base_snapshot.data_ref),
            )
            correspondence_owners = (payload_manifest,)
        else:
            # Preserve the prior explicit Foundry-only derived snapshot reader.
            # Generic schema0.2 owner admission retains its stricter field law.
            base_context_checks = (
                (owner_manifest, "context.base_data_snapshot", predecessor.data_snapshot_ref),
                (payload_manifest, "context.base_payload", base_snapshot.data_ref),
            )
            correspondence_owners = (owner_manifest, payload_manifest)
        for checked_manifest, role, expected in base_context_checks:
            if [edge for edge in checked_manifest.inputs if edge.role == role] != [
                input_ref_from_artifact_ref(expected, role=role)
            ]:
                raise ValueError("foundry_input_bindings_derived_base_context_mismatch")
        for checked_manifest in correspondence_owners:
            if [
                edge for edge in checked_manifest.inputs if edge.role == "derived.correspondence"
            ] != [
                input_ref_from_artifact_ref(item.correspondence_ref, role="derived.correspondence")
                for item in manifest.derivations
            ]:
                raise ValueError("foundry_input_bindings_derived_owner_correspondence_mismatch")
    elif manifest.derivations:
        raise ValueError("foundry_input_bindings_derived_payload_profile_required")
    slots = load_registry_bundle_content(store, registry_bundle_ref).slot_registry
    retained = _replay_explicit_initial_bindings(
        store,
        invocation.input_bindings_ref,
        predecessor,
        {
            slot_id: slots.slots[slot_id].state_path or ""
            for slot_id in selected_set.supplied_initial_slots
        },
    )
    if {item.rule.binding_id for item in retained} != set(manifest.retained_binding_ids):
        raise ValueError("foundry_input_bindings_semantic_retained_set_mismatch")
    compiled_rules: list[FoundryInputBindingRule] = []
    policies: dict[str, _SelectedBindingTensorPolicy] = {}
    canon_spec = CanonSpec(forbid_floats=False)
    for item in retained:
        current = _resolve_source_path(payload, item.rule.source_path, missing=_MISSING)
        if current is _MISSING or to_canonical_bytes(current, canon_spec) != to_canonical_bytes(
            item.source_value, canon_spec
        ):
            raise ValueError("foundry_input_bindings_semantic_retained_value_mismatch")
        compiled_rules.append(item.rule)
        policies[item.rule.binding_id] = item.policy

    limitations: list[str] = []
    method_inputs: list[_PreparedSelectedMethodInput] = []
    state_selection_count = 0
    for selection in manifest.measurements:
        obligation = obligations[artifact_ref_identity_key(selection.model_input_obligation_ref)]
        occurrence, measurement_limits = _verify_scoped_measurement(
            store, selection, proofs[selection.binding_id], obligation
        )
        role = selection.payload_occurrence_role()
        if [edge for edge in payload_manifest.inputs if edge.role == role] != [
            input_ref_from_artifact_ref(selection.selected_occurrence_ref, role=role)
        ]:
            raise ValueError("foundry_input_bindings_semantic_payload_occurrence_mismatch")
        raw = _resolve_source_path(payload, selection.source_path, missing=_MISSING)
        if (
            not isinstance(raw, int | float | Decimal)
            or isinstance(raw, bool)
            or _to_decimal(raw) != Decimal(occurrence.canonical_value)
        ):
            raise ValueError("foundry_input_bindings_semantic_payload_value_mismatch")
        port = obligation.port
        encoding = port.physical_encoding
        if encoding is None:
            raise ValueError("foundry_input_bindings_semantic_encoding_missing")
        if port.carrier == "method_input":
            method_inputs.append(
                _prepare_selected_method_input(
                    store,
                    selection=selection,
                    manifest_ref=resolved_binding_manifest_ref,
                    obligation=obligation,
                    canonical_value=Decimal(occurrence.canonical_value),
                    physical_value=raw,
                )
            )
            limitations.extend(measurement_limits)
            continue
        state_selection_count += 1
        compiled_rules.append(
            FoundryInputBindingRule(
                binding_id=selection.binding_id,
                source_path=selection.source_path,
                target_slot_id=port.slot_id,
            )
        )
        policies[selection.binding_id] = _SelectedBindingTensorPolicy(
            encoding.shape, encoding.dtype, encoding.max_absolute_error
        )
        limitations.extend(measurement_limits)
    for selection in manifest.derivations:
        obligation = obligations[artifact_ref_identity_key(selection.model_input_obligation_ref)]
        value, projection, derived_limits = _verify_selected_derived_input(
            store,
            selection,
            obligation,
            obligation_set_ref=manifest.model_input_obligation_set_ref,
        )
        role = selection.payload_output_role()
        if [edge for edge in payload_manifest.inputs if edge.role == role] != [
            input_ref_from_artifact_ref(selection.output_ref, role=role)
        ]:
            raise ValueError("foundry_input_bindings_derived_payload_output_mismatch")
        raw = _resolve_source_path(payload, selection.source_path, missing=_MISSING)
        physical_value = raw
        if projection == "singleton_vector":
            if not isinstance(raw, list) or len(raw) != 1:
                raise ValueError("foundry_input_bindings_derived_singleton_pack_mismatch")
            raw = raw[0]
        if (
            not isinstance(raw, int | float | Decimal)
            or isinstance(raw, bool)
            or _to_decimal(raw) != value
        ):
            raise ValueError("foundry_input_bindings_derived_payload_value_mismatch")
        port = obligation.port
        encoding = port.physical_encoding
        if encoding is None:
            raise ValueError("foundry_input_bindings_semantic_encoding_missing")
        if port.carrier == "method_input":
            method_inputs.append(
                _prepare_selected_method_input(
                    store,
                    selection=selection,
                    manifest_ref=resolved_binding_manifest_ref,
                    obligation=obligation,
                    canonical_value=value,
                    physical_value=physical_value,
                )
            )
            limitations.extend(derived_limits)
            continue
        state_selection_count += 1
        compiled_rules.append(
            FoundryInputBindingRule(
                binding_id=selection.binding_id,
                source_path=selection.source_path,
                target_slot_id=port.slot_id,
            )
        )
        policies[selection.binding_id] = _SelectedBindingTensorPolicy(
            encoding.shape, encoding.dtype, encoding.max_absolute_error
        )
        limitations.extend(derived_limits)
    compiled_rules.sort(key=lambda rule: rule.binding_id)
    if method_inputs and state_selection_count:
        raise ValueError("foundry_selected_method_input_mixed_carrier_not_established")
    if method_inputs and predecessor.selected_method_inputs is not None:
        raise ValueError("foundry_selected_method_input_chained_prestate_not_established")
    if rules is not None and rules != compiled_rules:
        raise ValueError("foundry_input_bindings_semantic_rules_mismatch")
    prepared = _prepare_input_binding_values(
        store,
        snapshot=snapshot,
        slot_registry=slots,
        binding_payload=payload,
        rules=compiled_rules,
        selected_tensor_policies=policies,
    )
    if method_inputs:
        prepared = replace(
            prepared,
            materialized_state=load_state_snapshot(
                store, snapshot_ref=predecessor.bound_state_snapshot_ref
            ),
            selected_method_inputs=tuple(sorted(method_inputs, key=lambda item: item.binding_id)),
            reused_bound_state_snapshot_ref=predecessor.bound_state_snapshot_ref,
        )
    step = int(np.asarray(prepared.materialized_state.step).item())
    execution_step = step if semantic_horizon_step is None else semantic_horizon_step.effective_step
    if (
        invocation.steps[0] != step
        or (
            execute_request is not None
            and semantic_horizon_step is None
            and invocation.steps != (step,)
        )
        or (effective_step is not None and execution_step != effective_step)
    ):
        raise ValueError("foundry_input_bindings_semantic_execution_step_mismatch")
    return replace(prepared, warnings=tuple(dict.fromkeys((*prepared.warnings, *limitations))))


def _load_scoped_correspondence(
    store: CoreJSONArtifactStore, selection: ResolvedMeasurementInput
) -> ScopedCorrespondenceBasis:
    try:
        proof = validate_core_model_json_artifact(
            ScopedCorrespondenceBasis, store, selection.correspondence_ref
        )
    except FileNotFoundError as exc:
        raise ValueError("foundry_input_bindings_semantic_correspondence_missing") from exc
    if tuple(store.get_manifest(selection.correspondence_ref).inputs) != (
        scoped_correspondence_basis_manifest_inputs(proof)
    ):
        raise ValueError("foundry_input_bindings_semantic_correspondence_lineage_mismatch")
    if artifact_ref_identity_key(proof.occurrence_ref) != artifact_ref_identity_key(
        selection.selected_occurrence_ref
    ):
        raise ValueError("foundry_input_bindings_semantic_occurrence_mismatch")
    return proof


def _verify_scoped_measurement(
    store: CoreJSONArtifactStore,
    selection: ResolvedMeasurementInput,
    proof: ScopedCorrespondenceBasis,
    obligation: ModelInputObligation,
) -> tuple[ScopedMeasurementOccurrence, tuple[str, ...]]:
    occurrence, replayed, source = _replay_selected_scoped_measurement(
        store, selection.selected_occurrence_ref
    )
    for evidence_ref in proof.source_definition_evidence_refs:
        if not store.verify(evidence_ref).ok:
            raise ValueError("foundry_input_bindings_semantic_definition_evidence_unverified")
    port = obligation.port
    result = evaluate_scoped_correspondence_basis(
        basis=proof,
        occurrence_ref=selection.selected_occurrence_ref,
        occurrence=occurrence,
        replayed_occurrence=replayed,
        source_selection=source,
        source_definition_ref=proof.source_definition_ref,
        source_definition=validate_core_model_json_artifact(
            VariableSemanticDefinition, store, proof.source_definition_ref
        ),
        source_representation_ref=proof.source_representation_ref,
        source_representation=load_variable_representation(store, proof.source_representation_ref),
        target_definition_ref=port.semantic_definition_ref,
        target_definition=validate_core_model_json_artifact(
            VariableSemanticDefinition, store, port.semantic_definition_ref
        ),
        target_representation_ref=port.representation_ref,
        target_representation=load_variable_representation(store, port.representation_ref),
        binding_profile_ref=port.binding_profile_ref,
        profile=validate_core_model_json_artifact(
            MeasurementBindingProfile, store, port.binding_profile_ref
        ),
        model_interface_ref=SelectedVariableBindingRef.model_validate(
            obligation.interface_ref.model_dump()
        ),
        model_port=port,
    )
    if result.status != "candidate":
        raise ValueError(
            "foundry_input_bindings_semantic_correspondence_refused:"
            + ",".join(result.refusal_codes)
        )
    return replayed, result.limitation_codes


def _replay_selected_scoped_measurement(
    store: CoreJSONArtifactStore,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
) -> tuple[ScopedMeasurementOccurrence, ScopedMeasurementOccurrence, ScopedSourceSelection]:
    """Reopen and replay the exact admitted source, independent of output meaning."""
    try:
        occurrence, replayed, source = read_api.catalog.replay_selected_scoped_measurement_facts(
            store, occurrence_ref
        )
    except ValueError as exc:
        code = getattr(exc, "code", None)
        if code in {
            "occurrence_lineage_mismatch",
            "source_profile_required",
            "source_owner_mismatch",
        }:
            raise ValueError(f"foundry_input_bindings_semantic_{code}") from exc
        raise
    if source.unit_transform != "identity":
        raise ValueError("foundry_input_bindings_fixed_unit_verifier_not_established")
    return occurrence, replayed, source


def _verify_selected_derived_input(
    store: CoreJSONArtifactStore,
    selection: ResolvedDerivedInput,
    obligation: ModelInputObligation,
    *,
    obligation_set_ref: ArtifactRef,
) -> tuple[Decimal, Literal["scalar", "singleton_vector"], tuple[str, ...]]:
    """Use the one Core arithmetic replay and the separate Core semantic rule."""
    if store.get_manifest(selection.correspondence_ref).artifact_schema == SchemaInfo(
        name="polisyos.catalog.RegisteredDerivedInputCorrespondence", version="2.0"
    ):
        return _verify_registered_composition_input(
            store, selection, obligation, obligation_set_ref=obligation_set_ref
        )
    try:
        proof = load_derived_input_correspondence(store, selection.correspondence_ref)
    except FileNotFoundError as exc:
        raise ValueError("foundry_input_bindings_derived_correspondence_missing") from exc
    for left, right in (
        (selection.model_input_obligation_ref, proof.model_input_obligation_ref),
        (selection.model_interface_ref, proof.model_interface_ref),
        (selection.recipe_ref, proof.recipe_ref),
        (selection.certificate_ref, proof.certificate_ref),
        (selection.output_ref, proof.output_ref),
        (selection.profile_ref, proof.profile_ref),
    ):
        if artifact_ref_identity_key(left) != artifact_ref_identity_key(right):
            raise ValueError("foundry_input_bindings_derived_selection_mismatch")
    if (selection.year, selection.model_port_id) != (proof.year, proof.model_port_id):
        raise ValueError("foundry_input_bindings_derived_selection_mismatch")
    profile = load_derived_input_profile(store, proof.profile_ref)
    context = load_ratio_denominator_source_context(store, proof.source_context_ref)
    try:
        recipe = load_derivation_recipe_artifact(store, selection.recipe_ref)
    except (OSError, DerivationRefusalError) as exc:
        raise ValueError("foundry_input_bindings_derived_recipe_unavailable") from exc
    resolution = resolve_certified_derivation(
        store,
        certificate_ref=selection.certificate_ref,
        consumer_method_id="polisyos.foundry.semantic-derived-input.v1",
    )
    if recipe != resolution.certificate.recipe:
        raise ValueError("foundry_input_bindings_derived_recipe_certificate_mismatch")
    certified_output = resolution.certificate.derived_artifact_ref
    if certified_output is None or artifact_ref_identity_key(certified_output) != (
        artifact_ref_identity_key(selection.output_ref)
    ):
        raise ValueError("foundry_input_bindings_derived_certified_output_mismatch")
    roles: list[ReplayedDerivedMeasurementRole] = []
    for role in proof.roles:
        occurrence, replayed, source = _replay_selected_scoped_measurement(
            store, role.occurrence_ref
        )
        definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, role.definition_ref
        )
        for evidence_ref in definition.definition_evidence_refs:
            if not store.verify(evidence_ref).ok:
                raise ValueError("foundry_input_bindings_semantic_definition_evidence_unverified")
        roles.append(
            ReplayedDerivedMeasurementRole(
                selection=role,
                occurrence=occurrence,
                replayed_occurrence=replayed,
                source_selection=source,
                definition=definition,
                representation=load_variable_representation(store, role.representation_ref),
                series=SourceSeries.model_validate(
                    load_core_json_artifact(store, role.source_series_ref)
                ),
            )
        )
    target_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, obligation.port.semantic_definition_ref
    )
    for evidence_ref in target_definition.definition_evidence_refs:
        if not store.verify(evidence_ref).ok:
            raise ValueError("foundry_input_bindings_semantic_definition_evidence_unverified")
    result = evaluate_derived_input_correspondence(
        basis=proof,
        profile=profile,
        source_context=context,
        obligation_ref=selection.model_input_obligation_ref,
        obligation=obligation,
        target_definition=target_definition,
        target_representation=load_variable_representation(
            store, obligation.port.representation_ref
        ),
        binding_profile=validate_core_model_json_artifact(
            MeasurementBindingProfile, store, obligation.port.binding_profile_ref
        ),
        units_registry=load_registry_bundle_content(
            store, obligation.registry_bundle_ref
        ).units_registry,
        recipe=recipe,
        series=resolution.series,
        roles=tuple(roles),
    )
    if result.status != "candidate" or result.value is None:
        raise ValueError(
            "foundry_input_bindings_derived_correspondence_refused:"
            + ",".join(result.refusal_codes)
        )
    bundle_limitation = "n7_derivation_bundle_not_established"
    if selection.derivation_bundle_ref is not None:
        ref = selection.derivation_bundle_ref
        manifest = store.get_manifest(ref)
        bundle = load_core_json_artifact(store, ref)
        if (
            manifest.artifact_schema
            != SchemaInfo(name="polisyos.runtime.quality.N7DerivationBundle", version="1.0")
            or not isinstance(bundle, dict)
            or bundle.get("schema_version") != "policyos.runtime.n7_derivation_bundle.v1"
        ):
            raise ValueError("foundry_input_bindings_derived_bundle_profile_mismatch")
        for field, expected in (
            ("model_input_obligation_ref", selection.model_input_obligation_ref),
            ("obligation_set_ref", obligation_set_ref),
        ):
            actual = ArtifactRef.model_validate(bundle.get(field))
            if artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected):
                raise ValueError("foundry_input_bindings_derived_bundle_target_mismatch")
        bundle_limitation = "n7_derivation_bundle_provenance_only"
    return result.value, profile.output_projection, (*result.limitation_codes, bundle_limitation)


def _verify_registered_composition_input(
    store: CoreJSONArtifactStore,
    selection: ResolvedDerivedInput,
    obligation: ModelInputObligation,
    *,
    obligation_set_ref: ArtifactRef,
) -> tuple[Decimal, Literal["scalar"], tuple[str, ...]]:
    """Replay v3 arithmetic and selected native predicates without minting authority."""
    from polisyos.core.contracts import (
        RegisteredSemanticBasis,
        ReplayedCandidateDerivationRole,
        evaluate_registered_derived_input_correspondence,
        load_native_derivation_source_projection,
        load_registered_derived_input_context,
        load_registered_derived_input_correspondence,
        load_registered_derived_input_profile,
    )
    from polisyos.core.derivations import (
        CandidateSourceSeries,
        load_composition_recipe_artifact,
        resolve_certified_composition,
    )

    proof = load_registered_derived_input_correspondence(store, selection.correspondence_ref)
    if any(
        artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected)
        for actual, expected in (
            (selection.model_input_obligation_ref, proof.model_input_obligation_ref),
            (selection.model_interface_ref, proof.model_interface_ref),
            (selection.profile_ref, proof.profile_ref),
            (selection.recipe_ref, proof.recipe_ref),
            (selection.certificate_ref, proof.certificate_ref),
            (selection.output_ref, proof.output_ref),
        )
    ) or (selection.year, selection.model_port_id) != (proof.year, proof.model_port_id):
        raise ValueError("foundry_input_bindings_composition_selection_mismatch")
    profile = load_registered_derived_input_profile(store, proof.profile_ref)
    context = load_registered_derived_input_context(store, proof.context_ref)
    if artifact_ref_identity_key(context.obligation_set_ref) != artifact_ref_identity_key(
        obligation_set_ref
    ):
        raise ValueError("foundry_input_bindings_composition_obligation_set_mismatch")
    try:
        recipe = load_composition_recipe_artifact(store, selection.recipe_ref)
    except (OSError, DerivationRefusalError) as exc:
        raise ValueError("foundry_input_bindings_composition_recipe_unavailable") from exc
    resolution = resolve_certified_composition(
        store,
        certificate_ref=selection.certificate_ref,
        consumer_method_id="polisyos.foundry.semantic-composition-input.v1",
    )
    if recipe != resolution.certificate.recipe or artifact_ref_identity_key(
        resolution.certificate.derived_artifact_ref
    ) != artifact_ref_identity_key(selection.output_ref):
        raise ValueError("foundry_input_bindings_composition_certificate_mismatch")
    roles = []
    for role in proof.roles:
        projection = load_native_derivation_source_projection(store, role.source_projection_ref)
        occurrence, replayed, source_selection = (
            read_api.catalog.replay_selected_scoped_measurement_facts(
                store, projection.occurrence_ref
            )
        )
        definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, projection.source_basis.semantic_definition_ref
        )
        if any(not store.verify(ref).ok for ref in definition.definition_evidence_refs):
            raise ValueError("foundry_input_bindings_composition_definition_evidence_unavailable")
        roles.append(
            ReplayedCandidateDerivationRole(
                selection=role,
                projection=projection,
                occurrence=occurrence,
                replayed_occurrence=replayed,
                source_selection=source_selection,
                definition=definition,
                representation=load_variable_representation(
                    store, projection.source_basis.representation_ref
                ),
                binding_profile=validate_core_model_json_artifact(
                    MeasurementBindingProfile, store, projection.source_basis.binding_profile_ref
                ),
                series=CandidateSourceSeries.model_validate(
                    load_core_json_artifact(store, role.source_series_ref)
                ),
            )
        )
    target_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, obligation.port.semantic_definition_ref
    )
    if any(not store.verify(ref).ok for ref in target_definition.definition_evidence_refs):
        raise ValueError("foundry_input_bindings_composition_definition_evidence_unavailable")
    result = evaluate_registered_derived_input_correspondence(
        correspondence=proof,
        profile=profile,
        context=context,
        obligation_ref=selection.model_input_obligation_ref,
        obligation=obligation,
        target_definition=target_definition,
        target_representation=load_variable_representation(
            store, obligation.port.representation_ref
        ),
        binding_profile=validate_core_model_json_artifact(
            MeasurementBindingProfile, store, obligation.port.binding_profile_ref
        ),
        units_registry=load_registry_bundle_content(
            store, obligation.registry_bundle_ref
        ).units_registry,
        recipe=recipe,
        series=resolution.series,
        roles=tuple(roles),
    )
    if result.status != "candidate" or result.value is None:
        raise ValueError(
            "foundry_input_bindings_composition_correspondence_refused:"
            + ",".join(result.refusal_codes)
        )
    bundle_limitation = "n7_derivation_bundle_not_established"
    if selection.derivation_bundle_ref is not None:
        ref = selection.derivation_bundle_ref
        manifest = store.get_manifest(ref)
        bundle = load_core_json_artifact(store, ref)
        if (
            manifest.artifact_schema
            != SchemaInfo(name="polisyos.runtime.quality.N7DerivationBundle", version="1.0")
            or not isinstance(bundle, dict)
            or bundle.get("schema_version") != "policyos.runtime.n7_derivation_bundle.v1"
        ):
            raise ValueError("foundry_input_bindings_derived_bundle_profile_mismatch")
        for field, expected in (
            ("model_input_obligation_ref", selection.model_input_obligation_ref),
            ("obligation_set_ref", obligation_set_ref),
        ):
            actual = ArtifactRef.model_validate(bundle.get(field))
            if artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected):
                raise ValueError("foundry_input_bindings_derived_bundle_target_mismatch")
        nodes = bundle.get("operation_nodes")
        roots = (
            []
            if not isinstance(nodes, list)
            else [
                node
                for node in nodes
                if isinstance(node, dict) and node.get("node_id") == bundle.get("root_node_id")
            ]
        )
        if (
            len(roots) != 1
            or (roots[0].get("family_id"), roots[0].get("method_version"))
            != (profile.family_id, profile.method_version)
            or artifact_ref_identity_key(ArtifactRef.model_validate(roots[0].get("operator_ref")))
            != artifact_ref_identity_key(profile.registry_ref)
        ):
            raise ValueError("foundry_input_bindings_composition_bundle_operator_mismatch")
        role_inputs = roots[0].get("role_inputs")
        source_nodes = bundle.get("source_nodes")
        if not isinstance(role_inputs, list) or not isinstance(source_nodes, list):
            raise ValueError("foundry_input_bindings_composition_bundle_role_mismatch")
        source_ids = {node.get("node_id") for node in source_nodes if isinstance(node, dict)}
        if len(source_ids) != len(source_nodes) or any(
            not isinstance(item, dict) or item.get("input_node_id") not in source_ids
            for item in role_inputs
        ):
            raise ValueError("foundry_input_bindings_composition_bundle_leaf_profile_required")
        expected_bases = {item.role: item.basis for item in profile.inputs}
        actual_bases = {
            item.get("role"): RegisteredSemanticBasis.model_validate(item.get("source_basis"))
            for item in role_inputs
        }
        if (
            len(actual_bases) != len(role_inputs)
            or actual_bases != expected_bases
            or RegisteredSemanticBasis.model_validate(roots[0].get("output_basis"))
            != profile.output
        ):
            raise ValueError("foundry_input_bindings_composition_bundle_role_mismatch")
        bundle_limitation = "n7_derivation_bundle_structure_only"
    return result.value, "scalar", (*result.limitation_codes, bundle_limitation)


def _verify_historical_selected_method_invocation(
    store: CoreJSONArtifactStore,
    *,
    historical_execution_ref: ArtifactRef,
    input_bindings_ref: ArtifactRef,
    invocation: ProgramGraphInputInvocation,
    execute_request: ExecuteRequest | None,
    effective_step: int | None,
    semantic_horizon_step: SemanticHorizonStepContext | None,
) -> None:
    """Join immutable invocation and stored calls without a live ABI lookup."""
    from polisyos.core.contracts import (
        FoundryExecutionInputBasis,
        SimulationResult,
    )
    from polisyos.foundry.execute.api import load_stored_selected_method_input_occurrences

    # The actual execution owner reopens the selected result, basis, graph and
    # capture bundle, and joins every selected argument to its stored ABI/hash.
    # It performs no admission recursion or current MethodRegistry lookup.
    load_stored_selected_method_input_occurrences(
        store,
        historical_execution_ref=historical_execution_ref,
        input_bindings_ref=input_bindings_ref,
    )
    result = validate_core_model_json_artifact(SimulationResult, store, historical_execution_ref)
    basis_ref = result.execution_input_basis_ref
    if basis_ref is None:
        raise ValueError("foundry_selected_method_input_historical_basis_required")
    basis = validate_core_model_json_artifact(FoundryExecutionInputBasis, store, basis_ref)
    bindings = load_input_bindings(store, input_bindings_ref)
    if (
        invocation.steps != (basis.effective_step,)
        or basis.semantic_horizon_step is not None
        or semantic_horizon_step is not None
        or (effective_step is not None and effective_step != basis.effective_step)
        or (execute_request is not None and execute_request != basis.request)
    ):
        raise ValueError("foundry_selected_method_input_historical_execution_mismatch")
    for expected, actual in (
        (invocation.program_graph_ref, basis.program_graph_ref),
        (invocation.exec_plan_ref, basis.exec_plan_ref),
        (invocation.registry_bundle_ref, basis.runtime_registry_ref),
        (invocation.registry_bundle_ref, basis.binding_registry_ref),
        (bindings.data_snapshot_ref, basis.data_snapshot_ref),
        (bindings.bound_state_snapshot_ref, basis.bound_state_snapshot_ref),
        (bindings.bound_state_snapshot_ref, basis.base_state_snapshot_ref),
        (invocation.parameter_override_bundle_ref, basis.parameter_override_bundle_ref),
        (invocation.context.candidate_source_ref, basis.candidate_ref),
    ):
        if (None if expected is None else artifact_ref_identity_key(expected)) != (
            None if actual is None else artifact_ref_identity_key(actual)
        ):
            raise ValueError("foundry_selected_method_input_historical_invocation_mismatch")
    _require_selected_binding_edges(
        store.get_manifest(basis_ref),
        {
            "basis.source.actual_data_snapshot": bindings.data_snapshot_ref,
            "basis.source.bound_state_snapshot": bindings.bound_state_snapshot_ref,
            "basis.source.base_state_snapshot": bindings.bound_state_snapshot_ref,
            "basis.source.binding_registry_bundle": invocation.registry_bundle_ref,
            "basis.source.runtime_registry_bundle": invocation.registry_bundle_ref,
        },
        reason="foundry_selected_method_input_historical_lineage_mismatch",
    )


def _verify_selected_method_invocation_facts(
    store: CoreJSONArtifactStore, *, invocation: ProgramGraphInputInvocation
) -> None:
    """Join the immutable model declaration and period without current ABI use."""
    from polisyos.core.contracts import (
        ProgramGraph,
        load_program_graph_input_interface,
    )
    from polisyos.foundry.execute.model_input_requirements import (
        _require_selected_method_input_period,
        resolve_program_graph_input_declaration,
    )

    interface = load_program_graph_input_interface(store, invocation.interface_ref)
    selected = resolve_program_graph_input_declaration(
        store,
        program_graph_ref=invocation.program_graph_ref,
        exec_plan_ref=invocation.exec_plan_ref,
        registry_bundle_ref=invocation.registry_bundle_ref,
    )
    if (
        selected is None
        or interface.declaration_ref is None
        or interface.trinity_bundle_ref is None
        or artifact_ref_identity_key(interface.declaration_ref)
        != artifact_ref_identity_key(selected.declaration_ref)
        or artifact_ref_identity_key(interface.trinity_bundle_ref)
        != artifact_ref_identity_key(selected.trinity_bundle_ref)
        or interface.ports != selected.declaration.ports
    ):
        raise ValueError("foundry_selected_method_input_immutable_interface_mismatch")
    graph = validate_core_model_json_artifact(ProgramGraph, store, invocation.program_graph_ref)
    _require_selected_method_input_period(
        store,
        graph=graph,
        ports=tuple(port for port in interface.ports if port.carrier == "method_input"),
        steps=invocation.steps,
    )


def reconcile_selected_method_input_bindings(
    store: ArtifactStore,
    *,
    input_bindings_ref: FoundryInputBindingsRef | ArtifactRef,
    execute_request: ExecuteRequest | None = None,
    expected_invocation: ProgramGraphInputInvocation | None = None,
    effective_step: int | None = None,
    semantic_horizon_step: SemanticHorizonStepContext | None = None,
    historical_execution_ref: ArtifactRef | None = None,
) -> SelectedMethodInputResolution:
    """Replay selected sources and return exact, read-only method arguments.

    Live use rechecks the selected preflight against the current method ABI.
    An explicit historical execution instead joins immutable stored call facts;
    the unavailable full past ABI remains a declared candidate limitation.

    Args:
        store: Existing store containing the complete selected source graph.
        input_bindings_ref: Exact selected version-1.4 binding artifact.
        execute_request: Optional actual execution request to join to the basis.
        expected_invocation: Independently selected candidate and graph context.
        effective_step: Actual consumer step, if executing or reading a result.
        semantic_horizon_step: Existing horizon context; this profile is one step.
        historical_execution_ref: Actual persisted result for historical replay.

    Returns:
        Strict bindings, immutable global-slot map, records, and candidate notes.

    Raises:
        ValueError: If refs, source arithmetic, encoding, or actual values disagree.
    """
    core_store, bindings, manifest_ref, records = _load_selected_method_input_binding(
        store, input_bindings_ref
    )
    if execute_request is not None and artifact_ref_identity_key(
        execute_request.input_bindings_ref
    ) != artifact_ref_identity_key(input_bindings_ref):
        raise ValueError("foundry_selected_method_input_execution_binding_mismatch")
    prepared = _prepare_semantic_input_bindings(
        core_store,
        data_snapshot_ref=bindings.data_snapshot_ref,
        registry_bundle_ref=bindings.registry_bundle_ref,
        resolved_binding_manifest_ref=manifest_ref,
        rules=bindings.rules,
        execute_request=execute_request,
        effective_step=effective_step,
        semantic_horizon_step=semantic_horizon_step,
        expected_invocation=expected_invocation,
        historical_execution_ref=historical_execution_ref,
        historical_input_bindings_ref=input_bindings_ref,
    )
    facts = _replay_selected_method_input_values(core_store, bindings, records, prepared)
    nominal_unchecked = "semantic_input_limitation:method_nominal_abi_not_checked"
    return SelectedMethodInputResolution(
        bindings=facts.bindings,
        values=facts.values,
        records=facts.records,
        notes=tuple(note for note in facts.notes if note != nominal_unchecked)
        + (
            ("semantic_input_limitation:method_historical_abi_completeness_not_established",)
            if historical_execution_ref is not None
            else ()
        ),
    )


def _load_selected_method_input_binding(
    store: ArtifactStore,
    input_bindings_ref: FoundryInputBindingsRef | ArtifactRef,
) -> tuple[
    CoreJSONArtifactStore,
    FoundryInputBindings,
    ResolvedInputBindingManifestRef,
    tuple[FoundrySelectedMethodInput, ...],
]:
    core_store = resolve_core_json_profile_store(store)
    if core_store is None:
        raise ValueError("foundry_selected_method_input_reader_not_established")
    if input_bindings_ref.manifest_profile_sha256 is None:
        raise ValueError("foundry_selected_method_input_profile_required")
    bindings = load_input_bindings(core_store, input_bindings_ref)
    manifest_ref = bindings.resolved_binding_manifest_ref
    records = bindings.selected_method_inputs
    if bindings.schema_version != "1.4" or not records or manifest_ref is None:
        raise ValueError("foundry_selected_method_input_profile_required")
    return core_store, bindings, manifest_ref, records


def replay_selected_method_input_facts(
    store: ArtifactStore,
    *,
    input_bindings_ref: FoundryInputBindingsRef | ArtifactRef,
    expected_invocation: ProgramGraphInputInvocation,
) -> SelectedMethodInputFacts:
    """Replay a selection's source and NPY facts without admitting its use.

    A retained candidate may have its own selected inputs without an execution
    occurrence. This reader opens that selection's exact immutable parents; it
    does not substitute another candidate's execution or consult today's ABI.
    The caller must separately establish its historical subject and all current
    use gates. Nominal ABI is not checked and provider completeness remains
    unestablished; this reader makes no historical or current subject claim.

    Args:
        store: Existing store containing the complete selected source graph.
        input_bindings_ref: Exact selected version-1.4 binding artifact.
        expected_invocation: Core invocation from the caller's own subject join.

    Returns:
        Immutable values, source-bound records, and explicit fact-only limits.

    Raises:
        ValueError: If immutable parents, source facts, or physical values disagree.
    """
    core_store, bindings, manifest_ref, records = _load_selected_method_input_binding(
        store, input_bindings_ref
    )
    prepared = _prepare_semantic_input_binding_facts(
        core_store,
        data_snapshot_ref=bindings.data_snapshot_ref,
        registry_bundle_ref=bindings.registry_bundle_ref,
        resolved_binding_manifest_ref=manifest_ref,
        rules=bindings.rules,
        expected_invocation=expected_invocation,
    )
    return _replay_selected_method_input_values(core_store, bindings, records, prepared)


def _replay_selected_method_input_values(
    core_store: CoreJSONArtifactStore,
    bindings: FoundryInputBindings,
    records: tuple[FoundrySelectedMethodInput, ...],
    prepared: InputBindingsPreparation,
) -> SelectedMethodInputFacts:
    """Reconcile the shared immutable physical fact body for every purpose."""
    if (
        prepared.reused_bound_state_snapshot_ref is None
        or artifact_ref_identity_key(prepared.reused_bound_state_snapshot_ref)
        != artifact_ref_identity_key(bindings.bound_state_snapshot_ref)
        or len(records) != len(prepared.selected_method_inputs)
    ):
        raise ValueError("foundry_selected_method_input_prestate_mismatch")
    # The prestate remains the predecessor's exact selected artifact. Opening
    # its bytes catches removal/corruption without manufacturing new lineage.
    load_state_snapshot(core_store, snapshot_ref=bindings.bound_state_snapshot_ref)
    values: dict[str, np.ndarray] = {}
    for record, expected in zip(records, prepared.selected_method_inputs, strict=True):
        value = expected.value
        expected_digest = _selected_method_tensor_digest(value)
        if (
            artifact_ref_identity_key(record.model_input_obligation_ref)
            != artifact_ref_identity_key(expected.model_input_obligation_ref)
            or record.binding_id != expected.binding_id
            or record.port_id != expected.port_id
            or record.slot_id != expected.slot_id
            or record.canonical_value != expected.canonical_value
            or record.dtype != value.dtype.name
            or record.shape != value.shape
            or record.value_sha256 != expected_digest
        ):
            raise ValueError("foundry_selected_method_input_record_source_mismatch")
        ref = record.npy_value_ref
        if (
            ref.kind != "foundry.selected_method_input_value"
            or ref.media_type != "application/x-npy"
            or ref.manifest_profile_sha256 is None
            or core_store.get_manifest(ref).inputs != list(expected.lineage_inputs)
        ):
            raise ValueError("foundry_selected_method_input_value_lineage_mismatch")
        actual = load_tensor(
            core_store,
            ref,
            expected_shape=record.shape,
            expected_dtype=record.dtype,
            max_payload_bytes=value.nbytes + 16_384,
        )
        if _selected_method_tensor_digest(actual) != expected_digest:
            raise ValueError("foundry_selected_method_input_value_identity_mismatch")
        if record.slot_id in values:
            raise ValueError("foundry_selected_method_input_slot_duplicate")
        argument = np.frombuffer(actual.tobytes(order="C"), dtype=actual.dtype).reshape(
            actual.shape
        )
        values[record.slot_id] = argument
    limits = (
        *prepared.warnings,
        "method_external_reads_not_observed",
        "method_nominal_abi_not_checked",
        "method_provider_completeness_not_established",
    )
    return SelectedMethodInputFacts(
        bindings=bindings,
        values=MappingProxyType(values),
        records=records,
        notes=(
            "semantic_input_use:candidate_simulation_input_only",
            *(f"semantic_input_limitation:{code}" for code in dict.fromkeys(limits)),
        ),
    )


def reconcile_semantic_input_bindings(
    store: ArtifactStore,
    bindings: FoundryInputBindings,
    *,
    execute_request: ExecuteRequest | None = None,
    effective_step: int | None = None,
    semantic_horizon_step: SemanticHorizonStepContext | None = None,
    expected_invocation: ProgramGraphInputInvocation | None = None,
) -> tuple[str, ...]:
    """Replay exact semantics and verify the persisted physical state bytes."""
    if bindings.schema_version == "1.4":
        raise ValueError("foundry_selected_method_input_binding_ref_required")
    ref = bindings.resolved_binding_manifest_ref
    if ref is None:
        snapshot_manifest = store.get_manifest(bindings.data_snapshot_ref)
        snapshot_schema = snapshot_manifest.artifact_schema
        semantic_schema = (
            snapshot_schema is not None
            and snapshot_schema.name == DataSnapshot.ARTIFACT_SCHEMA_NAME
            and snapshot_schema.version == DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION
        )
        if bindings.data_snapshot_ref.manifest_profile_sha256 is not None:
            core_store = resolve_core_json_profile_store(store)
            if core_store is None:
                if semantic_schema:
                    raise ValueError("foundry_input_bindings_semantic_manifest_required")
                raise ValueError("foundry_input_bindings_semantic_reader_not_established")
            snapshot = validate_core_model_json_artifact(
                DataSnapshot, core_store, bindings.data_snapshot_ref
            )
            _require_semantic_snapshot_lineage_version(snapshot, snapshot_schema)
            if semantic_schema or _snapshot_requires_resolved_input_manifest(snapshot):
                raise ValueError("foundry_input_bindings_semantic_manifest_required")
        elif semantic_schema:
            raise ValueError("foundry_input_bindings_semantic_manifest_required")
        else:
            # Legacy unselected snapshots still need the same derived-payload
            # discriminator check as preparation. Plain legacy payloads retain
            # their existing behavior; no semantic authority is inferred.
            core_store = resolve_core_json_profile_store(store)
            if core_store is not None:
                snapshot = validate_core_model_json_artifact(
                    DataSnapshot, core_store, bindings.data_snapshot_ref
                )
                if _snapshot_requires_resolved_input_manifest(snapshot):
                    raise ValueError("foundry_input_bindings_semantic_manifest_required")
        if semantic_horizon_step is not None:
            raise ValueError("foundry_input_bindings_semantic_manifest_required")
        return ()
    if bindings.registered_sql_admission_ref is not None:
        raise ValueError("foundry_input_bindings_semantic_sql_replay_not_established")
    core_store = resolve_core_json_profile_store(store)
    if core_store is None:
        raise ValueError("foundry_input_bindings_semantic_reader_not_established")
    prepared = _prepare_semantic_input_bindings(
        core_store,
        data_snapshot_ref=bindings.data_snapshot_ref,
        registry_bundle_ref=bindings.registry_bundle_ref,
        resolved_binding_manifest_ref=ref,
        rules=bindings.rules,
        execute_request=execute_request,
        effective_step=effective_step,
        semantic_horizon_step=semantic_horizon_step,
        expected_invocation=expected_invocation,
    )
    from polisyos.foundry.execute._internal.snapshots import _flatten_state

    flat = dict(_flatten_state(prepared.materialized_state))
    encoded = BytesIO()
    np.savez(encoded, **flat)
    checksum = hashlib.sha256(encoded.getvalue()).hexdigest()
    state_ref = bindings.bound_state_snapshot_ref
    state = validate_core_model_json_artifact(StateSnapshot, core_store, state_ref)
    manifest = core_store.get_manifest(state_ref)
    expected_inputs = [
        input_ref_from_artifact_ref(bindings.data_snapshot_ref, role="input.data_snapshot_ref"),
        input_ref_from_artifact_ref(bindings.registry_bundle_ref, role="input.registry_bundle_ref"),
        input_ref_from_artifact_ref(state.state_ref, role="state_blob"),
    ]
    if (
        state.schema_version != "2.2"
        or manifest.artifact_schema
        != SchemaInfo(
            name="polisyos.core.StateSnapshot",
            version=StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION["2.2"],
        )
        or state.state_ref.kind != "foundry.state_blob"
        or state.state_ref.media_type != "application/x-npz"
        or state.state_ref.manifest_profile_sha256 is None
        or state.entry_count != len(flat)
        or state.step != int(np.asarray(prepared.materialized_state.step).item())
        or state.checksum_sha256 != checksum
        or state.state_ref.artifact_id.hex != checksum
        or state.lineage_inputs != expected_inputs
        or manifest.inputs != expected_inputs
        or not core_store.verify(state.state_ref).ok
    ):
        raise ValueError("foundry_input_bindings_semantic_state_replay_mismatch")
    return (
        "semantic_input_use:candidate_simulation_input_only",
        *(f"semantic_input_limitation:{code}" for code in prepared.warnings),
    )


def reconcile_explicit_initial_binding_slots(
    store: CoreJSONArtifactStore,
    *,
    input_bindings_ref: FoundryInputBindingsRef,
    expected_state_paths: Mapping[str, str],
) -> tuple[str, ...]:
    """Reconcile supplied decimal inputs in an exact legacy initial state.

    Args:
        store: Existing store containing the selected binding, data and state.
        input_bindings_ref: Exact selected legacy no-SQL binding artifact.
        expected_state_paths: Slot IDs and their physical destinations from
            the calling model interface.

    Returns:
        Sorted slot IDs whose explicit source values reproduce the persisted
        initial state exactly. This is physical input evidence only.

    Raises:
        ValueError: If selected lineage, destinations or persisted values disagree.
    """
    if not expected_state_paths:
        return ()
    if input_bindings_ref.manifest_profile_sha256 is None:
        raise ValueError("explicit_initial_binding_selected_profile_required")
    bindings = load_input_bindings(store, input_bindings_ref)
    return tuple(
        item.rule.target_slot_id
        for item in _replay_explicit_initial_bindings(
            store, input_bindings_ref, bindings, expected_state_paths
        )
    )


def _replay_explicit_initial_bindings(
    store: CoreJSONArtifactStore,
    input_bindings_ref: FoundryInputBindingsRef,
    bindings: FoundryInputBindings,
    expected_state_paths: Mapping[str, str],
) -> tuple[_ExplicitInitialBinding, ...]:
    """Read the physical predecessor values once for the calling operation."""
    if bindings.schema_version != "1.0":
        raise ValueError("explicit_initial_binding_legacy_profile_required")

    source_refs = {
        "input.data_snapshot_ref": bindings.data_snapshot_ref,
        "input.registry_bundle_ref": bindings.registry_bundle_ref,
    }
    _require_selected_binding_edges(
        store.get_manifest(input_bindings_ref),
        {**source_refs, "artifact.bound_state_snapshot_ref": bindings.bound_state_snapshot_ref},
    )
    state_manifest = store.get_manifest(bindings.bound_state_snapshot_ref)
    if state_manifest.artifact_schema != SchemaInfo(
        name="polisyos.core.StateSnapshot",
        version=StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION["2.2"],
    ):
        raise ValueError("explicit_initial_binding_state_profile_mismatch")
    _require_selected_binding_edges(state_manifest, source_refs)

    snapshot = _load_data_snapshot(store, bindings.data_snapshot_ref)
    payload = _load_binding_payload(store, snapshot)
    slot_registry = load_registry_bundle_content(store, bindings.registry_bundle_ref).slot_registry
    state = load_state_snapshot(store, snapshot_ref=bindings.bound_state_snapshot_ref)
    _validate_rules(bindings.rules, slot_registry)
    supplied: list[_ExplicitInitialBinding] = []
    for slot_id, path in sorted(expected_state_paths.items()):
        slot = slot_registry.slots.get(slot_id)
        if slot is None or not path or slot.state_path != path:
            raise ValueError(f"explicit_initial_binding_destination_mismatch:{slot_id}")
        writers = [
            rule
            for rule in bindings.rules
            if (destination := slot_registry.slots[rule.target_slot_id].state_path)
            and _binding_destinations_overlap(path, destination)
        ]
        if len(writers) > 1 or (writers and writers[0].target_slot_id != slot_id):
            raise ValueError(f"explicit_initial_binding_destination_conflict:{slot_id}")
        if not writers:
            continue
        rule = writers[0]
        if (
            not rule.required
            or rule.default_value is not None
            or not all(rule.source_path.split("."))
        ):
            continue
        raw = _resolve_source_path(payload, rule.source_path, missing=_MISSING)
        if raw is _MISSING:
            continue
        actual = np.asarray(get_state_path(state, path))
        policy = _SelectedBindingTensorPolicy(actual.shape, actual.dtype.name, Decimal(0))
        try:
            expected = _materialize_selected_binding_tensor(
                raw,
                rule=rule,
                slot=slot,
                target_tensor=actual,
                policy=policy,
            )
        except ValueError:
            # Legacy missing/null/coercion/default behavior cannot establish
            # physical supply for this supported explicit-input interface.
            continue
        if np.asarray(expected).tobytes() != actual.tobytes():
            raise ValueError(f"explicit_initial_binding_state_mismatch:{slot_id}")
        supplied.append(_ExplicitInitialBinding(rule, raw, policy))
    return tuple(supplied)


def _require_selected_binding_edges(
    manifest: ArtifactManifest,
    source_refs: Mapping[str, ArtifactRef],
    *,
    reason: str = "explicit_initial_binding_lineage_mismatch",
) -> None:
    for role, ref in source_refs.items():
        if ref.manifest_profile_sha256 is None or [
            edge for edge in manifest.inputs if edge.role == role
        ] != [input_ref_from_artifact_ref(ref, role=role)]:
            raise ValueError(f"{reason}:{role}")


def resolve_bound_state_snapshot_ref(
    store: CoreJSONArtifactStore,
    ref: FoundryInputBindingsRef | ArtifactRef,
) -> StateSnapshotRef:
    """Resolve the bound `StateSnapshotRef` and validate referenced artifacts.

    Args:
        store: CAS containing the input-binding artifact and the bound snapshot.
        ref: Input-binding artifact reference returned by
            `build_input_bindings()`.

    Returns:
        `StateSnapshotRef` that `execute()` can use as the simulation base.

    Raises:
        Exception: Propagates CAS read failures when either the original data
            snapshot or the bound state snapshot is missing.
    """

    bindings = load_input_bindings(store, ref)
    # Version 1.4 leaves the exact predecessor state unchanged. The actual
    # graph resolves its side-input values once, with the current invocation;
    # historical readers use the distinct selected-method resolver explicitly.
    if bindings.schema_version != "1.4":
        reconcile_semantic_input_bindings(store, bindings)
    _ensure_artifact_readable(store, bindings.data_snapshot_ref)
    _ensure_artifact_readable(store, bindings.bound_state_snapshot_ref)
    return bindings.bound_state_snapshot_ref


def extract_feedback_state(
    state: GlobalState,
    *,
    config: FeedbackConfig,
    metrics: Mapping[str, Any] | None = None,
) -> FeedbackStateSnapshot:
    """Extract the compact feedback vector from post-execution state and metrics."""

    metric_values = metrics or {}
    values = [
        _extract_feedback_scalar(
            state,
            metrics=metric_values,
            source_kind=spec.source_kind,
            source_ref=spec.source_ref,
            reduction=spec.reduction,
            transforms=spec.transforms,
        )
        for spec in config.variables
    ]
    return FeedbackStateSnapshot(
        variable_ids=[spec.variable_id for spec in config.variables],
        values=values,
        scales=[float(spec.scale) if spec.scale is not None else 1.0 for spec in config.variables],
        lower_bounds=[spec.lower_bound for spec in config.variables],
        upper_bounds=[spec.upper_bound for spec in config.variables],
        weights=[float(spec.weight) for spec in config.variables],
        notes=list(config.notes),
    )


def extract_feedback_diagnostics(
    state: GlobalState,
    *,
    config: FeedbackConfig,
    metrics: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Extract additional scalar diagnostics declared by the feedback config."""

    metric_values = metrics or {}
    diagnostics: dict[str, float] = {}
    for spec in config.diagnostics:
        diagnostics[spec.diagnostic_id] = _extract_feedback_scalar(
            state,
            metrics=metric_values,
            source_kind=spec.source_kind,
            source_ref=spec.source_ref,
            reduction=spec.reduction,
            transforms=spec.transforms,
        )
    return diagnostics


def inject_feedback_state(
    state: GlobalState,
    *,
    config: FeedbackConfig,
    snapshot: FeedbackStateSnapshot | list[float] | tuple[float, ...] | np.ndarray,
) -> tuple[GlobalState, dict[str, dict[str, object]]]:
    """Inject a compact feedback vector into state paths and parameter overrides."""

    resolved = (
        snapshot
        if isinstance(snapshot, FeedbackStateSnapshot)
        else FeedbackStateSnapshot(
            variable_ids=[spec.variable_id for spec in config.variables],
            values=[float(value) for value in np.asarray(snapshot, dtype=float).tolist()],
            scales=[
                float(spec.scale) if spec.scale is not None else 1.0 for spec in config.variables
            ],
            lower_bounds=[spec.lower_bound for spec in config.variables],
            upper_bounds=[spec.upper_bound for spec in config.variables],
            weights=[float(spec.weight) for spec in config.variables],
        )
    )
    if len(resolved.values) != len(config.variables):
        raise ValueError(
            "Feedback snapshot dimensionality does not match config variables: "
            f"{len(resolved.values)} != {len(config.variables)}"
        )

    overrides: dict[str, dict[str, object]] = {}
    updated_state = state
    for spec, value in zip(config.variables, resolved.values, strict=True):
        if spec.target_kind == "parameter_override":
            overrides.setdefault(spec.target_ref, {})[str(spec.target_param)] = float(value)
            continue
        target_value = get_state_path(updated_state, spec.target_ref)
        coerced = _coerce_feedback_target(float(value), target_value)
        updated_state = set_state_path(updated_state, spec.target_ref, coerced)

    feedback_state = FeedbackState(
        active=jnp.ones((len(resolved.values),), dtype=jnp.bool_),
        values=jnp.asarray(resolved.values, dtype=jnp.float32),
        scales=jnp.asarray(resolved.scales, dtype=jnp.float32),
        lower_bounds=jnp.asarray(
            [(-jnp.inf if value is None else value) for value in resolved.lower_bounds],
            dtype=jnp.float32,
        ),
        upper_bounds=jnp.asarray(
            [(jnp.inf if value is None else value) for value in resolved.upper_bounds],
            dtype=jnp.float32,
        ),
        weights=jnp.asarray(resolved.weights, dtype=jnp.float32),
        noise_estimate=jnp.zeros((len(resolved.values),), dtype=jnp.float32),
    )
    return updated_state.replace(feedback_state=feedback_state), overrides


def _load_data_snapshot(
    store: CoreJSONArtifactStore, data_snapshot_ref: ArtifactRef
) -> DataSnapshot:
    from polisyos.core.artifacts import validate_core_model_json_artifact

    _reconcile_artifact_ref(store, data_snapshot_ref, label="data snapshot")
    selected_parent_manifest = _verify_selected_data_snapshot_schema(store, data_snapshot_ref)
    snapshot = validate_core_model_json_artifact(DataSnapshot, store, data_snapshot_ref)
    parent_manifest = selected_parent_manifest or store.get_manifest(data_snapshot_ref)
    _require_semantic_snapshot_lineage_version(snapshot, parent_manifest.artifact_schema)
    if selected_parent_manifest is None:
        return snapshot

    if (
        selected_parent_manifest.artifact_schema is not None
        and selected_parent_manifest.artifact_schema.version
        in {
            DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
            DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION,
        }
    ):
        _verify_data_snapshot_owner_inputs(store, selected_parent_manifest, snapshot)
        return snapshot

    selected_nested_refs: dict[str, BaseModel] = {}
    for field_name in data_snapshot_reference_fields():
        nested_ref = getattr(snapshot, field_name)
        if nested_ref is None:
            continue
        allowed_roles = data_snapshot_reference_input_roles(field_name)
        if not allowed_roles:
            raise ValueError(
                f"DataSnapshot selected nested reference lineage role is not established: {field_name}"
            )
        try:
            normalized_ref = ArtifactRef.model_validate(nested_ref.model_dump(mode="python"))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"DataSnapshot selected nested reference is invalid: {field_name}"
            ) from exc
        parent_edges = [
            edge
            for edge in selected_parent_manifest.inputs
            if edge.role in allowed_roles and edge.artifact_id == normalized_ref.artifact_id
        ]
        if len(parent_edges) != 1 or parent_edges[0].manifest_profile_sha256 is None:
            raise ValueError(
                f"DataSnapshot selected nested reference lineage is not established: {field_name}"
            )
        selected_profile = parent_edges[0].manifest_profile_sha256
        if (
            normalized_ref.manifest_profile_sha256 is not None
            and normalized_ref.manifest_profile_sha256 != selected_profile
        ):
            raise ValueError(
                f"DataSnapshot selected nested reference profile differs from its parent: {field_name}"
            )
        selected_ref = normalized_ref.model_copy(
            update={"manifest_profile_sha256": selected_profile}
        )
        try:
            child_manifest = resolve_manifest_by_profile(
                store,
                selected_ref.artifact_id,
                selected_profile,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise ValueError(
                f"DataSnapshot selected nested reference profile does not resolve: {field_name}"
            ) from exc
        if (
            child_manifest.kind != selected_ref.kind
            or child_manifest.media_type != selected_ref.media_type
            or not store.verify(selected_ref).ok
        ):
            raise ValueError(
                f"DataSnapshot selected nested reference differs from its manifest: {field_name}"
            )
        selected_nested_refs[field_name] = type(nested_ref).model_validate(
            {
                **nested_ref.model_dump(mode="python"),
                "manifest_profile_sha256": selected_profile,
            }
        )
    return snapshot.model_copy(update=selected_nested_refs)


def _require_semantic_snapshot_lineage_version(
    snapshot: DataSnapshot,
    schema: SchemaInfo | None,
) -> bool:
    """Bind semantic owner variants to their actual outer manifest versions."""
    semantic_schema = (
        schema is not None
        and schema.name == DataSnapshot.ARTIFACT_SCHEMA_NAME
        and schema.version == DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION
    )
    semantic_lineage = isinstance(
        snapshot.source_lineage, AcquiredObservationSemanticInputDataSnapshotLineage
    )
    if semantic_schema != semantic_lineage:
        raise ValueError("DataSnapshot owner lineage version differs from its manifest schema")
    if isinstance(snapshot.source_lineage, DerivedModelInputDataSnapshotLineage) and (
        schema is None
        or schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
        or schema.version != DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION
    ):
        raise ValueError("DataSnapshot owner lineage version differs from its manifest schema")
    return semantic_lineage


def _snapshot_requires_resolved_input_manifest(snapshot: DataSnapshot) -> bool:
    """Identify semantic input use without conflating its distinct source owners."""
    return (
        isinstance(
            snapshot.source_lineage,
            (
                AcquiredObservationSemanticInputDataSnapshotLineage,
                DerivedModelInputDataSnapshotLineage,
            ),
        )
        or snapshot.data_ref.kind == DERIVED_MODEL_INPUT_PAYLOAD_KIND
    )


def _verify_selected_data_snapshot_schema(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
) -> ArtifactManifest | None:
    """Resolve supported owner schemas, including the actual default view."""
    if ref.manifest_profile_sha256 is None:
        manifest = store.get_manifest(ref)
        if not store.verify(ref).ok:
            raise ValueError("DataSnapshot default profile integrity failure")
        if (
            manifest.kind != ref.kind
            or manifest.media_type != ref.media_type
            or manifest.kind != DataSnapshot.ARTIFACT_KIND
            or manifest.media_type != DataSnapshot.ARTIFACT_MEDIA_TYPE
        ):
            raise ValueError("DataSnapshot default profile differs from its artifact contract")
        if manifest.artifact_schema is None or manifest.artifact_schema.version not in {
            DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
            DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION,
        }:
            return None
    else:
        try:
            manifest = resolve_manifest_by_profile(
                store,
                ref.artifact_id,
                ref.manifest_profile_sha256,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise ValueError("DataSnapshot selected manifest profile does not resolve") from exc
    if manifest.kind != ref.kind or manifest.media_type != ref.media_type:
        raise ValueError("DataSnapshot selected profile differs from its artifact contract")
    if not store.verify(ref).ok:
        raise ValueError("DataSnapshot selected profile integrity failure")
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema.name != DataSnapshot.ARTIFACT_SCHEMA_NAME
        or manifest.artifact_schema.version not in DataSnapshot.ARTIFACT_SCHEMA_VERSIONS
    ):
        raise ValueError("DataSnapshot selected manifest schema differs from its model owner")
    return manifest


def _verify_data_snapshot_owner_inputs(
    store: CoreJSONArtifactStore,
    manifest: ArtifactManifest,
    snapshot: DataSnapshot,
) -> None:
    """Reconcile schema-0.3 parent edges without changing child selectors."""
    schema_version = None if manifest.artifact_schema is None else manifest.artifact_schema.version
    semantic_lineage = isinstance(
        snapshot.source_lineage, AcquiredObservationSemanticInputDataSnapshotLineage
    )
    if (schema_version == DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION and semantic_lineage) or (
        schema_version == DATA_SNAPSHOT_SEMANTIC_INPUT_LINEAGE_SCHEMA_VERSION
        and not semantic_lineage
    ):
        raise ValueError("DataSnapshot owner lineage version differs from its manifest schema")
    try:
        expected = data_snapshot_owner_input_requirements(snapshot)
    except (TypeError, ValueError) as exc:
        raise ValueError("DataSnapshot owner-lineage contract is invalid") from exc
    if len(manifest.inputs) != len(expected):
        raise ValueError("DataSnapshot owner-lineage input denominator differs")
    unmatched = set(range(len(manifest.inputs)))
    for ref, role in expected:
        matches = [
            index
            for index in unmatched
            if manifest.inputs[index].artifact_id == ref.artifact_id
            and manifest.inputs[index].role == role
        ]
        if len(matches) != 1:
            raise ValueError("DataSnapshot owner-lineage input edge differs")
        edge = manifest.inputs[matches[0]]
        unmatched.remove(matches[0])
        try:
            default_ref = ArtifactRef.model_validate(
                ref.model_dump(mode="json") | {"manifest_profile_sha256": None}
            )
            default_manifest = store.get_manifest(default_ref)
            default_profile = artifact_manifest_profile_sha256(default_manifest)
            selected_profile = edge.manifest_profile_sha256 or default_profile
            ref_profile = ref.manifest_profile_sha256 or default_profile
            if (
                not selected_profile
                or selected_profile != ref_profile
                or default_manifest.kind != ref.kind
                or default_manifest.media_type != ref.media_type
            ):
                raise ValueError("DataSnapshot owner-lineage child profile differs")
            selected_ref = ref.model_copy(update={"manifest_profile_sha256": selected_profile})
            child_manifest = resolve_manifest_by_profile(
                store,
                selected_ref.artifact_id,
                selected_profile,
            )
            if (
                child_manifest.kind != ref.kind
                or child_manifest.media_type != ref.media_type
                or not store.verify(selected_ref).ok
            ):
                raise ValueError("DataSnapshot owner-lineage child ref differs")
        except (FileNotFoundError, TypeError, ValueError) as exc:
            raise ValueError("DataSnapshot owner-lineage child ref is unverified") from exc
    if unmatched:
        raise ValueError("DataSnapshot has undeclared owner-lineage input edges")


def _snapshot_binding_notes(snapshot: DataSnapshot) -> list[str]:
    notes: list[str] = []
    data_shape = str(snapshot.stats.get("data_shape", "")).strip()
    if data_shape:
        notes.append(f"snapshot.data_shape={data_shape}")
    for key in (
        "survey_year_field",
        "wave_field",
        "sample_weight_field",
        "inclusion_probabilities_field",
    ):
        value = str(snapshot.stats.get(key, "")).strip()
        if value:
            notes.append(f"snapshot.{key}={value}")
    return notes


def _snapshot_binding_warnings(snapshot: DataSnapshot) -> list[str]:
    data_shape = str(snapshot.stats.get("data_shape", "")).strip().lower()
    if data_shape != "survey_repeated_cross_section":
        return []
    return [
        (
            "Input snapshot is survey repeated cross-section; route it to "
            "transport/survey/HTE workflows, not panel SCM/DiD/econometrics"
        )
    ]


def _extract_feedback_scalar(
    state: GlobalState,
    *,
    metrics: Mapping[str, Any],
    source_kind: str,
    source_ref: str,
    reduction: str,
    transforms: list[Any],
) -> float:
    if source_kind == "state_path":
        source_value = get_state_path(state, source_ref)
    elif source_kind == "metric":
        if source_ref not in metrics:
            raise KeyError(f"Feedback metric '{source_ref}' is missing from execution metrics")
        source_value = metrics[source_ref]
    else:
        raise ValueError(f"Unsupported feedback source_kind: {source_kind}")

    reduced = _reduce_feedback_value(source_value, reduction=reduction, source_ref=source_ref)
    transformed = _apply_transform_chain(reduced, transforms)
    array = np.asarray(transformed, dtype=float)
    if array.ndim != 0:
        raise ValueError(
            f"Feedback source '{source_ref}' must reduce to a scalar, got shape {array.shape}"
        )
    return float(array.item())


def _reduce_feedback_value(value: Any, *, reduction: str, source_ref: str) -> float:
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        return float(array.item())
    if reduction == "identity":
        raise ValueError(f"Feedback source '{source_ref}' is non-scalar and requires a reduction")
    if reduction == "mean":
        return float(np.mean(array))
    if reduction == "sum":
        return float(np.sum(array))
    if reduction == "min":
        return float(np.min(array))
    if reduction == "max":
        return float(np.max(array))
    raise ValueError(f"Unsupported feedback reduction: {reduction}")


def _coerce_feedback_target(value: float, target: Any) -> Any:
    if isinstance(target, np.ndarray):
        broadcast = np.broadcast_to(value, target.shape)
        return np.asarray(broadcast, dtype=target.dtype)
    if isinstance(target, jnp.ndarray):
        broadcast = jnp.broadcast_to(jnp.asarray(value, dtype=target.dtype), target.shape)
        return jnp.asarray(broadcast, dtype=target.dtype)
    return type(target)(value)


def _reconcile_artifact_ref(
    store: ArtifactStore,
    ref: ArtifactRef,
    *,
    label: str,
) -> ArtifactManifest:
    """Require a typed artifact reference to agree with its immutable manifest."""

    manifest = store.get_manifest(ref)
    if ref.kind != manifest.kind:
        raise ValueError(f"{label} kind mismatch between typed ref and CAS manifest")
    if ref.media_type != manifest.media_type:
        raise ValueError(f"{label} media type mismatch between typed ref and CAS manifest")
    return manifest


def _decode_arrow_binding_payload(payload: bytes) -> dict[str, Any]:
    """Decode one Arrow IPC stream into the mapping shape used by bindings."""

    import pyarrow as pa

    try:
        table = pa.ipc.open_stream(payload).read_all()
        return table.to_pydict()
    except (OSError, ValueError, pa.ArrowException) as exc:
        raise ValueError("invalid Arrow IPC payload") from exc


def _load_binding_payload(store: CoreJSONArtifactStore, snapshot: DataSnapshot) -> Any:
    from polisyos.core.artifacts import load_core_json_artifact

    data_ref = snapshot.data_ref
    manifest = _reconcile_artifact_ref(store, data_ref, label="data snapshot payload")
    if data_ref.kind == "foundry.state_snapshot":
        if manifest.media_type != _JSON_MEDIA_TYPE:
            raise ValueError("foundry.state_snapshot media type must be application/json")
        return {}
    if data_ref.kind == "fabric.source_collection":
        from polisyos.fabric.ingestion import load_source_collection

        return load_source_collection(store, data_ref).model_dump(mode="json")
    payload = store.get_bytes(data_ref)
    if manifest.media_type == _JSON_MEDIA_TYPE:
        return load_core_json_artifact(store, data_ref, raw_payload_bytes=payload)
    if manifest.media_type == _ARROW_MEDIA_TYPE:
        return _decode_arrow_binding_payload(payload)
    raise ValueError(f"unsupported data snapshot payload media type: {manifest.media_type}")


def _prepare_rules(
    *,
    rules: list[FoundryInputBindingRule] | None,
    slot_registry: SlotRegistry,
    payload: Any,
    explicit_only: bool = False,
) -> list[FoundryInputBindingRule]:
    if explicit_only and rules is None:
        raise ValueError("semantic_binding_explicit_rules_required")
    if rules is not None and (rules or explicit_only):
        parsed = [FoundryInputBindingRule.model_validate(rule.model_dump()) for rule in rules]
        return sorted(parsed, key=lambda item: item.binding_id)
    auto = _auto_rules_from_payload(slot_registry=slot_registry, payload=payload)
    return sorted(auto, key=lambda item: item.binding_id)


def _recompute_registered_sql_state(
    store: CoreJSONArtifactStore,
    *,
    snapshot: DataSnapshot,
    payload: Any,
    slot_registry: SlotRegistry,
    rules: list[FoundryInputBindingRule],
) -> tuple[bytes, int]:
    """Recompute the bounded first-profile state without asserting authority.

    Callers must independently verify and bound the selected input bytes before
    supplying them. For this tabular profile, base-state construction does not
    read from the store. The emitted bytes are the existing NPZ codec, not a new
    wire profile.
    """
    from polisyos.foundry.execute._internal.snapshots import _flatten_state

    if (
        snapshot.data_ref.kind != "fabric.tabular_payload"
        or not isinstance(payload, list)
        or not payload
        or not rules
        or rules != sorted(rules, key=lambda rule: rule.binding_id)
    ):
        raise ValueError("registered_sql_binding_replay_profile_not_established")
    _validate_rules(rules, slot_registry)
    if any(
        _resolve_source_path(payload, rule.source_path, missing=_MISSING) is _MISSING
        for rule in rules
    ):
        raise ValueError("registered_sql_binding_source_read_not_established")
    replayed_base = _build_base_state(
        store=store, snapshot=snapshot, payload=payload, slot_registry=slot_registry, rules=rules
    )
    state, applied, errors, warnings = _materialize_state(
        base_state=replayed_base, rules=rules, slot_registry=slot_registry, payload=payload
    )
    if errors or warnings or applied != tuple(rule.binding_id for rule in rules):
        raise ValueError("registered_sql_binding_rule_replay_not_established")

    flat = dict(_flatten_state(state))
    encoded = BytesIO()
    np.savez(encoded, **flat)
    return encoded.getvalue(), len(flat)


def _reconcile_registered_sql_bound_state(
    store: CoreJSONArtifactStore,
    *,
    snapshot: DataSnapshot,
    payload: Any,
    slot_registry: SlotRegistry,
    rules: list[FoundryInputBindingRule],
    bound_state_ref: StateSnapshotRef,
    lineage_inputs: list[InputRef],
) -> None:
    """Compare build-time replay with the actual selected persisted state.

    This establishes candidate derivation at build time, not issuer authority
    or a current-use decision. A served consumer must boundedly reopen and replay
    its own selected input and state bytes.
    """
    from polisyos.core.artifacts import load_core_json_artifact

    encoded, entry_count = _recompute_registered_sql_state(
        store, snapshot=snapshot, payload=payload, slot_registry=slot_registry, rules=rules
    )
    expected_digest = hashlib.sha256(encoded).hexdigest()
    actual = StateSnapshot.model_validate(load_core_json_artifact(store, bound_state_ref))
    expected_inputs = [
        *lineage_inputs,
        input_ref_from_artifact_ref(actual.state_ref, role="state_blob"),
    ]
    manifest = store.get_manifest(bound_state_ref)
    if (
        actual.schema_version != "2.2"
        or actual.checksum_sha256 != expected_digest
        or str(actual.state_ref.artifact_id.hex) != expected_digest
        or actual.state_ref.kind != "foundry.state_blob"
        or actual.state_ref.media_type != "application/x-npz"
        or actual.state_ref.manifest_profile_sha256 is None
        or actual.entry_count != entry_count
        or actual.lineage_inputs != expected_inputs
        or manifest.inputs != expected_inputs
        or not store.verify(bound_state_ref).ok
        or not store.verify(actual.state_ref).ok
    ):
        raise ValueError("registered_sql_binding_state_replay_mismatch")


def _auto_rules_from_payload(
    *,
    slot_registry: SlotRegistry,
    payload: Any,
) -> list[FoundryInputBindingRule]:
    if not isinstance(payload, dict):
        return []
    rules: list[FoundryInputBindingRule] = []
    for slot_id in sorted(slot_registry.slots.keys()):
        slot = slot_registry.slots[slot_id]
        candidates = [slot.slot_id]
        if slot.state_path:
            candidates.append(slot.state_path)
        source_path = next((item for item in candidates if _path_exists(payload, item)), None)
        if source_path is None:
            continue
        rules.append(
            FoundryInputBindingRule(
                binding_id=f"auto.{slot.slot_id.replace('.', '_')}",
                source_path=source_path,
                target_slot_id=slot.slot_id,
                required=False,
                notes=["auto-generated from payload path"],
            )
        )
    return rules


def _validate_rules(
    rules: list[FoundryInputBindingRule],
    slot_registry: SlotRegistry,
    *,
    selected_tensor_policies: Mapping[str, _SelectedBindingTensorPolicy] | None = None,
) -> None:
    seen: set[str] = set()
    selected_destinations: set[str] = set()
    for rule in rules:
        if rule.binding_id in seen:
            raise ValueError(f"Duplicate binding_id: {rule.binding_id}")
        seen.add(rule.binding_id)
        if rule.target_slot_id not in slot_registry.slots:
            raise ValueError(
                f"Binding rule '{rule.binding_id}' references unknown slot_id "
                f"'{rule.target_slot_id}'"
            )
        if selected_tensor_policies is not None:
            if not rule.required or rule.default_value is not None:
                raise ValueError(f"semantic_binding_source_required:{rule.binding_id}")
            if not all(rule.source_path.split(".")):
                raise ValueError(f"semantic_binding_source_path_invalid:{rule.binding_id}")
            slot = slot_registry.slots[rule.target_slot_id]
            destination = slot.state_path or ""
            if not all(destination.split(".")):
                raise ValueError(f"semantic_binding_destination_invalid:{rule.target_slot_id}")
            if any(
                _binding_destinations_overlap(destination, other) for other in selected_destinations
            ):
                raise ValueError(f"semantic_binding_destination_conflict:{slot.state_path}")
            selected_destinations.add(destination)
    if selected_tensor_policies is not None and seen != selected_tensor_policies.keys():
        raise ValueError("semantic_binding_tensor_policy_set_mismatch")


def _binding_destinations_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}.") or right.startswith(f"{left}.")


def _build_base_state(
    *,
    store: CoreJSONArtifactStore,
    snapshot: DataSnapshot,
    payload: Any,
    slot_registry: SlotRegistry,
    rules: list[FoundryInputBindingRule],
) -> GlobalState:
    if snapshot.data_ref.kind == "foundry.state_snapshot":
        return load_state_snapshot(store, snapshot_ref=snapshot.data_ref)

    return _build_payload_base_state(payload=payload, rules=rules, slot_registry=slot_registry)


def _build_payload_base_state(
    *, payload: Any, rules: list[FoundryInputBindingRule], slot_registry: SlotRegistry
) -> GlobalState:
    """Shared empty-state layout derived from actual complete binding inputs."""

    n_agents, n_firms, n_cells, n_household_cells = _infer_entity_sizes(
        payload=payload,
        rules=rules,
        slot_registry=slot_registry,
    )
    return GlobalState.empty(
        n_agents=max(1, n_agents),
        n_firms=max(1, n_firms),
        n_cells=n_cells,
        n_household_cells=n_household_cells,
    )


def _infer_entity_sizes(
    *,
    payload: Any,
    rules: list[FoundryInputBindingRule],
    slot_registry: SlotRegistry,
) -> tuple[int, int, int, int]:
    n_agents = 1
    n_firms = 1
    n_cells = 0
    n_household_cells = 0
    for rule in rules:
        slot = slot_registry.slots.get(rule.target_slot_id)
        if slot is None:
            continue
        value = _resolve_source_path(payload, rule.source_path, missing=_MISSING)
        if value is _MISSING:
            value = rule.default_value
        size = _sequence_size(value)
        if slot.scope == SlotScope.PER_AGENT and size is not None:
            n_agents = max(n_agents, size)
        elif slot.scope == SlotScope.PER_FIRM and size is not None:
            n_firms = max(n_firms, size)
        elif slot.scope == SlotScope.PER_CELL and size is not None:
            family_path = slot.state_path or slot.slot_id
            if family_path.startswith(_CELL_PREFIX):
                n_cells = max(n_cells, size)
            elif family_path.startswith(_HOUSEHOLD_CELL_PREFIX):
                n_household_cells = max(n_household_cells, size)
    return n_agents, n_firms, n_cells, n_household_cells


def _sequence_size(value: Any) -> int | None:
    if isinstance(value, (str, bytes, bytearray)):
        return None
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            return None
        return int(value.shape[0])
    if isinstance(value, jnp.ndarray):
        if value.ndim == 0:
            return None
        return int(value.shape[0])
    return None


def _materialize_state(
    *,
    base_state: GlobalState,
    rules: list[FoundryInputBindingRule],
    slot_registry: SlotRegistry,
    payload: Any,
    selected_tensor_policies: Mapping[str, _SelectedBindingTensorPolicy] | None = None,
) -> tuple[GlobalState, tuple[str, ...], list[str], list[str]]:
    state = base_state
    applied: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    for rule in sorted(rules, key=lambda item: item.binding_id):
        slot = slot_registry.slots.get(rule.target_slot_id)
        if slot is None:
            errors.append(f"{rule.binding_id}: target slot missing '{rule.target_slot_id}'")
            continue
        if not slot.state_path:
            errors.append(f"{rule.binding_id}: slot '{slot.slot_id}' has no state_path")
            continue

        value = _resolve_source_path(payload, rule.source_path, missing=_MISSING)
        if value is _MISSING:
            if selected_tensor_policies is not None:
                errors.append(f"{rule.binding_id}: semantic_binding_source_missing")
                continue
            value = rule.default_value
            if value is None and not rule.required:
                warnings.append(
                    f"{rule.binding_id}: source_path '{rule.source_path}' missing; "
                    "optional rule skipped"
                )
                continue
            if value is None and rule.required:
                errors.append(
                    f"{rule.binding_id}: required source_path missing '{rule.source_path}'"
                )
                continue

        try:
            if selected_tensor_policies is None:
                transformed = _apply_transform_chain(value, rule.transforms)
                coerced = _coerce_to_slot_tensor(
                    transformed,
                    slot=slot,
                    target_tensor=get_state_path(state, slot.state_path),
                )
            else:
                coerced = _materialize_selected_binding_tensor(
                    value,
                    rule=rule,
                    slot=slot,
                    target_tensor=get_state_path(state, slot.state_path),
                    policy=selected_tensor_policies[rule.binding_id],
                )
            state = set_state_path(state, slot.state_path, coerced)
            applied.append(rule.binding_id)
        except Exception as exc:
            errors.append(f"{rule.binding_id}: {exc}")

    return state, tuple(applied), errors, warnings


def _materialize_selected_binding_tensor(
    value: object,
    *,
    rule: FoundryInputBindingRule,
    slot: SlotSpec,
    target_tensor: object,
    policy: _SelectedBindingTensorPolicy,
) -> np.ndarray:
    """Write one verified decimal input without legacy fallback or implicit reshaping."""
    source = np.asarray(value, dtype=object)
    target = np.asarray(target_tensor)
    if any(item is None for item in source.flat):
        raise ValueError("semantic_binding_source_null")
    if source.shape != policy.shape or target.shape != policy.shape:
        raise ValueError("semantic_binding_shape_mismatch")
    if (
        slot.value_type != SlotValueType.DECIMAL
        or target.dtype.kind != "f"
        or target.dtype.name != policy.dtype
    ):
        raise ValueError("semantic_binding_target_encoding_mismatch")
    if not policy.max_absolute_error.is_finite() or policy.max_absolute_error < 0:
        raise ValueError("semantic_binding_precision_policy_invalid")
    if any(
        not isinstance(item, int | float | Decimal | np.integer | np.floating)
        or isinstance(item, bool)
        for item in source.flat
    ):
        raise ValueError("semantic_binding_source_not_decimal")
    decimals = np.array([_to_decimal(item) for item in source.flat], dtype=object).reshape(
        source.shape
    )
    if not all(item.is_finite() for item in decimals.flat):
        raise ValueError("semantic_binding_source_not_finite")

    transforms = [(transform.op, transform.params) for transform in rule.transforms]
    multiplier = policy.fixed_unit_multiplier
    if multiplier is None:
        if transforms not in ([], [("identity", {})]):
            raise ValueError("semantic_binding_transform_mismatch")
        transformed = decimals
    else:
        if (
            not multiplier.is_finite()
            or multiplier <= 0
            or len(transforms) != 1
            or transforms[0][0] != "scale"
            or transforms[0][1].keys() != {"factor"}
            or _to_decimal(transforms[0][1]["factor"]) != multiplier
        ):
            raise ValueError("semantic_binding_transform_mismatch")
        digits = max((len(item.as_tuple().digits) for item in decimals.flat), default=1)
        context = Context(
            prec=digits + len(multiplier.as_tuple().digits), Emin=MIN_EMIN, Emax=MAX_EMAX
        )
        context.traps[Inexact] = True
        with localcontext(context):
            transformed = np.asarray(
                _apply_transform_chain(decimals, rule.transforms), dtype=object
            )

    return encode_selected_tensor(
        transformed,
        shape=policy.shape,
        dtype=policy.dtype,
        max_absolute_error=policy.max_absolute_error,
    )


def _apply_transform_chain(value: Any, transforms: list[Any]) -> Any:
    current = value
    for transform in transforms:
        op = getattr(transform, "op", "identity")
        params = getattr(transform, "params", {}) or {}
        current = _apply_transform(op=str(op), value=current, params=dict(params))
    return current


def _apply_transform(*, op: str, value: Any, params: dict[str, Any]) -> Any:
    if op == "identity":
        return value
    if op == "to_bool":
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        return _map_values(value, _to_bool)
    if op == "to_int":
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        return _map_values(value, _to_int)
    if op == "to_decimal":
        return _map_values(value, _to_decimal)
    if op == "fillna":
        fill = params.get("value")
        return _map_values(value, lambda item: fill if item is None else item)
    if op == "scale":
        factor = _to_decimal(params.get("factor", 1))
        return _map_values(value, lambda item: _to_decimal(item) * factor)
    if op == "offset":
        delta = _to_decimal(params.get("value", 0))
        return _map_values(value, lambda item: _to_decimal(item) + delta)
    if op == "clip":
        lower = params.get("min")
        upper = params.get("max")
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        return _map_values(
            value,
            lambda item: _clip_decimal(item, lower=lower, upper=upper),
        )
    if op == "round":
        fast = _apply_array_fast_path(op=op, value=value, params=params)
        if fast is not _MISSING:
            return fast
        digits = int(params.get("digits", 6))
        quant = Decimal(10) ** Decimal(-digits)
        return _map_values(value, lambda item: _to_decimal(item).quantize(quant))
    raise ValueError(f"Unsupported transform op: {op}")


def _map_values(value: Any, fn) -> Any:
    if isinstance(value, (list, tuple)):
        return [fn(item) for item in value]
    if isinstance(value, np.ndarray):
        return _map_array_values(value, fn)
    if isinstance(value, jnp.ndarray):
        return _map_array_values(np.asarray(value), fn)
    return fn(value)


def _map_array_values(value: np.ndarray, fn) -> Any:
    flat = [fn(item) for item in value.flat]
    if value.ndim == 0:
        return flat[0]
    reshaped = np.asarray(flat, dtype=object).reshape(value.shape)
    return _object_array_to_nested_list(reshaped)


def _object_array_to_nested_list(value: np.ndarray) -> Any:
    if value.ndim == 0:
        return value.reshape(()).item()
    if value.ndim == 1:
        return [item.item() if isinstance(item, np.generic) else item for item in value]
    return [_object_array_to_nested_list(row) for row in value]


def _apply_array_fast_path(*, op: str, value: Any, params: dict[str, Any]) -> Any:
    array = _as_vectorizable_array(value)
    if array is None:
        return _MISSING
    is_numpy, arr = array

    if op == "to_bool":
        return arr.astype(bool)
    if op == "to_int":
        return arr.astype(jnp.int32 if not is_numpy else np.int32)
    if op == "clip":
        lower = params.get("min")
        upper = params.get("max")
        clip_fn = np.clip if is_numpy else jnp.clip
        lower_value = None if lower is None else float(_to_decimal(lower))
        upper_value = None if upper is None else float(_to_decimal(upper))
        return clip_fn(arr, lower_value, upper_value)
    if op == "round":
        round_fn = np.round if is_numpy else jnp.round
        digits = int(params.get("digits", 6))
        return round_fn(arr, decimals=digits)
    return _MISSING


def _as_vectorizable_array(value: Any) -> tuple[bool, Any] | None:
    if isinstance(value, np.ndarray):
        if value.dtype == object:
            return None
        return True, value
    if isinstance(value, jnp.ndarray):
        if getattr(value, "dtype", None) is None:
            return None
        return False, value
    return None


def _clip_decimal(value: Any, *, lower: Any, upper: Any) -> Decimal:
    dec = _to_decimal(value)
    if lower is not None:
        dec = max(dec, _to_decimal(lower))
    if upper is not None:
        dec = min(dec, _to_decimal(upper))
    return dec


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "y"}:
            return True
        if token in {"0", "false", "no", "n", ""}:
            return False
    return bool(value)


def _to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if value is None:
        return 0
    return int(Decimal(str(value)))


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Cannot cast '{value}' to Decimal") from exc


def _coerce_to_slot_tensor(value: Any, *, slot: SlotSpec, target_tensor: Any):
    if slot.value_type == SlotValueType.VALUE_OUTER_SET:
        return _coerce_value_outer_set(value)

    target_arr = np.asarray(target_tensor)
    converted = _convert_slot_value(value=value, slot=slot)
    source_arr = np.asarray(converted)

    if target_arr.ndim == 0:
        scalar = source_arr.reshape(-1)[0] if source_arr.ndim > 0 else source_arr.item()
        return jnp.asarray(scalar, dtype=target_arr.dtype)

    if source_arr.ndim == 0:
        source_arr = np.full(target_arr.shape, source_arr.item(), dtype=source_arr.dtype)
    elif source_arr.shape != target_arr.shape:
        if source_arr.ndim == 1 and source_arr.shape[0] == target_arr.shape[0]:
            source_arr = source_arr.reshape(target_arr.shape)
        else:
            raise ValueError(
                f"shape mismatch for slot '{slot.slot_id}': expected {target_arr.shape}, "
                f"got {source_arr.shape}"
            )

    return jnp.asarray(source_arr, dtype=target_arr.dtype)


def _convert_slot_value(*, value: Any, slot: SlotSpec) -> Any:
    if slot.value_type == SlotValueType.BOOL:
        return _map_values(value, _to_bool)
    if slot.value_type == SlotValueType.INT:
        return _map_values(value, _to_int)
    if slot.value_type == SlotValueType.DECIMAL:
        return _map_values(value, _canonical_float)
    if slot.value_type == SlotValueType.STRING:
        return _map_values(value, lambda item: "" if item is None else str(item))
    if slot.value_type == SlotValueType.VALUE_OUTER_SET:
        return _coerce_value_outer_set(value)
    return value


def _coerce_value_outer_set(value: Any) -> ValueOuterSet:
    if isinstance(value, ValueOuterSet):
        return value
    if isinstance(value, str):
        return ValueOuterSet.from_persisted_payload(value)
    if isinstance(value, Mapping):
        return ValueOuterSet.from_persisted_payload(value)
    raise ValueError(f"Cannot cast '{type(value).__name__}' to ValueOuterSet")


def _canonical_float(value: Any) -> float:
    dec = _to_decimal(value).quantize(_FLOAT_QUANT, rounding=ROUND_HALF_EVEN)
    result = float(dec)
    if not np.isfinite(result):
        raise ValueError(f"Non-finite decimal value: {value}")
    return result


def _resolve_source_path(payload: Any, path: str, *, missing: Any) -> Any:
    if not path:
        return payload
    current = payload
    for token in path.split("."):
        try:
            current = _resolve_path_token(current, token)
        except KeyError:
            return missing
    return current


def _resolve_path_token(current: Any, token: str) -> Any:
    if isinstance(current, dict):
        if token not in current:
            raise KeyError(token)
        return current[token]
    if isinstance(current, list):
        if token.isdigit():
            idx = int(token)
            if idx < 0 or idx >= len(current):
                raise KeyError(token)
            return current[idx]
        values = []
        for item in current:
            values.append(_resolve_path_token(item, token))
        return values
    raise KeyError(token)


def _path_exists(payload: Any, path: str) -> bool:
    return _resolve_source_path(payload, path, missing=_MISSING) is not _MISSING


def _ensure_artifact_readable(store: ArtifactStore, ref: ArtifactRef) -> None:
    store.get_manifest(ref)
