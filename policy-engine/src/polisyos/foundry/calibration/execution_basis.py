"""Content-bound input identity for persisted Foundry calibration runs.

This artifact records the exact run objects and ordered target bytes consumed by
``Calibrator``. It is an identity record only: source custody, measurement
units, physical time semantics, and an observation/noise law remain separate
claims and are not inferred here.
"""

from __future__ import annotations

import hashlib
import math
import platform
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, is_dataclass, replace
from dataclasses import fields as dataclass_fields
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, Generic, Literal, TypeVar, cast

import jax
import jaxlib
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    ArtifactRef,
    ArtifactStore,
    InputRef,
    PutOptions,
    SchemaInfo,
    SelectedProfileVerificationReader,
    read_core_json_artifact,
    resolve_manifest_by_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.foundry import ExecPlan

if TYPE_CHECKING:
    from polisyos.core.registry import RegistryBundleContent
    from polisyos.foundry.calibration.report import CalibrationReport


_ARTIFACT_KIND = "foundry.calibration_execution_input_basis"
_ARTIFACT_SCHEMA_NAME = "polisyos.foundry.CalibrationExecutionInputBasis"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_ORDERED_INPUT_KIND = "foundry.calibration_ordered_input"
_ORDERED_INPUT_SCHEMA = "polisyos.foundry.CalibrationOrderedBatchInput"

# Keep this full field roster beside the persisted contract.  The producer
# checks it against dataclasses.fields(CalibratorInputs); consumers validate
# the same frozen denominator without importing the fit implementation.
CALIBRATION_RUNTIME_INPUT_CONTRACT = (
    ("config", "fit_required", "selected_calibration_config"),
    ("program_graph", "fit_required", "selected_program_graph"),
    ("exec_plan", "fit_required", "selected_exec_plan"),
    ("base_state", "fit_required", "selected_base_state_snapshot"),
    ("mechanism_registry", "fit_required", "runtime_registry_member"),
    ("slot_registry", "fit_required", "runtime_registry_member"),
    ("merge_registry", "fit_required", "runtime_registry_member"),
    ("selector_field_registry", "fit_conditional", "runtime_registry_member"),
    ("parameter_loader", "fit_required", "resolved_parameter_inputs"),
    ("constraint_registry", "fit_conditional", "runtime_registry_member"),
    ("constraint_values", "fit_conditional", "in_memory_constraint_values"),
    ("raw_targets", "fit_conditional", "resolved_target_inputs"),
    ("controls_seq", "fit_conditional", "report_series_horizon"),
    ("udf_engine", "fit_conditional", "resolved_target_inputs"),
    ("target_fetcher", "fit_conditional", "resolved_target_inputs"),
    ("measurement_bundle", "fit_conditional", "measurement_target_bundle"),
    ("measurement_loss_config", "fit_conditional", "measurement_objective"),
    ("measurement_loss_adapter", "fit_conditional", "measurement_objective"),
    ("aux_loss_components", "fit_conditional", "auxiliary_objective"),
    ("exec_plan_ref", "provenance_only", "selected_exec_plan_ref"),
    ("registry_bundle_ref", "provenance_only", "selected_runtime_registry_bundle_ref"),
    ("mechanism_registry_ref", "provenance_only", "runtime_registry_member_ref"),
    ("units_registry", "provenance_only", "runtime_registry_member"),
    ("units_registry_ref", "provenance_only", "runtime_registry_member_ref"),
    ("base_state_snapshot_ref", "provenance_only", "selected_base_state_snapshot_ref"),
)
CALIBRATION_RUNTIME_INPUT_NAMES = tuple(row[0] for row in CALIBRATION_RUNTIME_INPUT_CONTRACT)
CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2 = (
    *CALIBRATION_RUNTIME_INPUT_CONTRACT,
    ("ordered_batch_profile", "fit_conditional", "ordered_batch_profile"),
)
CALIBRATION_RUNTIME_INPUT_NAMES_V1_2 = tuple(
    row[0] for row in CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2
)
RUNTIME_REGISTRY_MEMBER_CONTRACT = (
    (
        "mechanism_registry",
        "mechanism_registry",
        "ir.mechanism_registry",
        "polisyos.ir.kernel.MechanismTypeRegistry",
    ),
    ("slot_registry", "slot_registry", "ir.slot_registry", "polisyos.ir.kernel.SlotRegistry"),
    (
        "merge_registry",
        "merge_registry",
        "ir.merge_rule_registry",
        "polisyos.ir.kernel.MergeRuleRegistry",
    ),
    (
        "selector_field_registry",
        "selector_field_registry",
        "ir.selector_field_registry",
        "polisyos.ir.kernel.SelectorFieldRegistry",
    ),
    (
        "constraint_registry",
        "constraint_registry",
        "ir.constraint_registry",
        "polisyos.ir.kernel.ConstraintRegistry",
    ),
    ("units_registry", "units_registry", "ir.units_registry", "polisyos.ir.kernel.UnitsRegistry"),
)
RUNTIME_REGISTRY_MEMBER_INPUT_NAMES = tuple(row[0] for row in RUNTIME_REGISTRY_MEMBER_CONTRACT)


class CalibrationResolvedParameterInput(BaseModel):
    """Capture one parameter-loader result without retaining raw parameter values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=0, strict=True)
    node_id: str | None = None
    mechanism_type: str | None = None
    parameter_ids: tuple[str, ...] = ()
    source_ref: ArtifactRef | None = None
    source_payload_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    source_status: Literal[
        "selected_source_matched",
        "selected_source_mismatch",
        "in_memory_only",
        "not_established",
    ] = "not_established"
    payload_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    effective_parameter_values_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    status: Literal["content_bound", "not_established"]
    effective_values_status: Literal["content_bound", "not_established"] = "not_established"

    @model_validator(mode="after")
    def validate_status(self) -> CalibrationResolvedParameterInput:
        if self.source_status == "selected_source_matched":
            if self.source_ref is None or self.source_ref.manifest_profile_sha256 is None:
                raise ValueError("matched_parameter_source_requires_selected_ref")
            if (
                self.source_payload_sha256 is None
                or self.source_payload_sha256 != self.payload_sha256
            ):
                raise ValueError("matched_parameter_source_requires_matching_payload_digest")
        if self.source_status == "selected_source_mismatch" and self.source_ref is None:
            raise ValueError("mismatched_parameter_source_requires_ref")
        if self.source_status == "in_memory_only" and self.source_ref is not None:
            raise ValueError("in_memory_parameter_source_must_not_have_ref")
        if (
            self.source_status in {"in_memory_only", "not_established"}
            and self.source_payload_sha256 is not None
        ):
            raise ValueError("unmatched_parameter_source_must_not_have_source_digest")
        if (self.status == "content_bound") != (self.payload_sha256 is not None):
            raise ValueError("parameter_payload_status_must_match_digest_presence")
        if (self.effective_values_status == "content_bound") != (
            self.effective_parameter_values_sha256 is not None
        ):
            raise ValueError("effective_parameter_status_must_match_digest_presence")
        return self


class CalibrationParameterUnitIdentity(BaseModel):
    """Capture the parameter contract's declared unit without inventing a unit law."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str = Field(min_length=1)
    mechanism_type: str = Field(min_length=1)
    parameter_id: str = Field(min_length=1)
    value_type: str = Field(min_length=1)
    unit_id: str | None = None
    parameter_spec_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    parameter_spec_status: Literal[
        "selected_source_content_bound", "in_memory_content_bound", "not_established"
    ]
    unit_definition_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    unit_definition_status: Literal[
        "selected_source_content_bound",
        "in_memory_content_bound",
        "selected_source_missing",
        "not_established",
    ]
    status: Literal["parameter_spec_bound", "not_established"]

    @model_validator(mode="after")
    def validate_status(self) -> CalibrationParameterUnitIdentity:
        if (self.status == "parameter_spec_bound") != (self.parameter_spec_sha256 is not None):
            raise ValueError("parameter_unit_status_must_match_spec_digest")
        if (
            self.parameter_spec_status
            in {"selected_source_content_bound", "in_memory_content_bound"}
        ) != (self.parameter_spec_sha256 is not None):
            raise ValueError("parameter_spec_source_status_must_match_digest_presence")
        if (
            self.unit_definition_status
            in {"selected_source_content_bound", "in_memory_content_bound"}
        ) != (self.unit_definition_sha256 is not None):
            raise ValueError("unit_definition_status_must_match_digest_presence")
        if self.unit_definition_status == "selected_source_missing" and not self.unit_id:
            raise ValueError("missing_selected_unit_definition_requires_declared_unit_id")
        return self


class CalibrationTargetInputIdentity(BaseModel):
    """Bind one report target to its ordered observed and time-axis bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str = Field(min_length=1, max_length=128)
    report_series_sha256: str = Field(pattern=_SHA256_PATTERN)
    observed_values_sha256: str = Field(pattern=_SHA256_PATTERN)
    report_time_axis_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    source_kind: Literal[
        "measurement_bundle",
        "caller_raw_targets",
        "target_fetcher_or_udf",
        "mixed_or_unknown",
        "ordered_batch_profile",
    ]
    source_time_axis: tuple[Any, ...] | None = None
    time_grain: str | None = None
    split_labels: tuple[str, ...] | None = None
    observation_ids: tuple[str, ...] | None = None
    identification_modes: tuple[str, ...] | None = None
    measurement_metadata_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    lineage_identifiers: tuple[str, ...] = ()
    source_attestation_status: Literal["not_established"] = "not_established"
    unit_status: Literal["not_established"] = "not_established"
    physical_time_status: Literal["not_established"] = "not_established"
    split_status: Literal["captured", "not_established"] = "not_established"


class CalibrationRuntimeInputBinding(BaseModel):
    """Record one declared CalibratorInputs field and its resolved content state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_name: str = Field(min_length=1)
    usage: Literal["fit_required", "fit_conditional", "provenance_only"]
    source_role: Literal[
        "selected_calibration_config",
        "selected_program_graph",
        "selected_exec_plan",
        "selected_base_state_snapshot",
        "runtime_registry_member",
        "resolved_parameter_inputs",
        "in_memory_constraint_values",
        "resolved_target_inputs",
        "report_series_horizon",
        "measurement_target_bundle",
        "measurement_objective",
        "auxiliary_objective",
        "selected_exec_plan_ref",
        "selected_runtime_registry_bundle_ref",
        "runtime_registry_member_ref",
        "selected_base_state_snapshot_ref",
        "ordered_batch_profile",
    ]
    status: Literal[
        "selected_source_matched",
        "selected_source_mismatch",
        "selected_source_absent",
        "in_memory_content_bound",
        "resolved_output_content_bound",
        "not_established",
        "absent",
        "not_consumed",
    ]
    value_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    source_ref: ArtifactRef | None = None
    source_payload_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    resolved_by: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_binding(self) -> CalibrationRuntimeInputBinding:
        if self.status == "selected_source_matched":
            if self.source_ref is None or self.source_ref.manifest_profile_sha256 is None:
                raise ValueError("matched_runtime_input_requires_selected_source_ref")
            if self.value_sha256 is None or self.value_sha256 != self.source_payload_sha256:
                raise ValueError("matched_runtime_input_requires_equal_content_digests")
        elif self.status == "selected_source_mismatch":
            if self.source_ref is None:
                raise ValueError("mismatched_runtime_input_requires_source_ref")
            if (
                self.value_sha256 is not None
                and self.source_payload_sha256 is not None
                and self.value_sha256 == self.source_payload_sha256
            ):
                raise ValueError("mismatched_runtime_input_cannot_have_equal_digests")
        elif self.status == "selected_source_absent":
            if self.source_ref is not None or self.value_sha256 is not None:
                raise ValueError("absent_runtime_input_source_cannot_have_content")
        elif self.status == "in_memory_content_bound":
            if self.value_sha256 is None or self.source_ref is not None:
                raise ValueError("in_memory_runtime_input_requires_only_value_digest")
        elif self.status == "resolved_output_content_bound":
            if not self.resolved_by or self.source_ref is not None:
                raise ValueError("resolved_runtime_input_requires_resolution_edges")
        elif self.status in {"absent", "not_consumed"}:
            if self.value_sha256 is not None or self.source_payload_sha256 is not None:
                raise ValueError("non_consumed_runtime_input_cannot_have_value_digest")
        if self.source_ref is None and self.source_payload_sha256 is not None:
            raise ValueError("runtime_source_digest_requires_source_ref")
        return self


_ScheduleStep = Annotated[int, Field(ge=0, strict=True)]
_KeyWord = Annotated[int, Field(ge=0, le=2**32 - 1, strict=True)]


class CalibrationOrderedBatchRow(BaseModel):
    """Bind one positional row to the selected snapshot actually consumed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_id: str = Field(min_length=1)
    state_snapshot_ref: ArtifactRef
    state_values_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_status: Literal["materialized_local_fit_input"] = "materialized_local_fit_input"

    @model_validator(mode="after")
    def validate_selected_state(self) -> CalibrationOrderedBatchRow:
        ref = self.state_snapshot_ref
        if ref.kind != "foundry.state_snapshot" or ref.media_type != "application/json":
            raise ValueError("ordered_batch_row_requires_selected_state_snapshot")
        return self


class CalibrationOrderedBatchBackendUnavailable(RuntimeError):
    """The selected numeric execution profile is unavailable to this reader."""


_CalibrationSourceT = TypeVar("_CalibrationSourceT")
_CalibrationModelT = TypeVar("_CalibrationModelT", bound=BaseModel)
CalibrationSourceStatus = Literal["matched", "not_established", "mismatch"]


@dataclass(frozen=True)
class CalibrationSourceRead(Generic[_CalibrationSourceT]):
    """Classify a selected read, never issuer authority or whole calibration validity."""

    status: CalibrationSourceStatus
    code: str
    ref: ArtifactRef | None = None
    manifest: ArtifactManifest | None = None
    value: _CalibrationSourceT | None = None
    error: BaseException | None = None

    def require_value(self) -> _CalibrationSourceT:
        """Keep old low-level access/backend exceptions; never return unqualified data."""
        if self.status != "matched":
            if isinstance(
                self.error,
                (FileNotFoundError, PermissionError, CalibrationOrderedBatchBackendUnavailable),
            ):
                raise self.error
            raise CalibrationSourceReadRefusal(self)
        return cast("_CalibrationSourceT", self.value)


class CalibrationSourceReadRefusal(ValueError):
    """Preserve a classified nested read through existing owner callback boundaries."""

    def __init__(self, result: CalibrationSourceRead[Any]) -> None:
        self.result = result
        super().__init__(result.code)


def classify_calibration_source_error(
    error: BaseException,
    *,
    role: str,
) -> CalibrationSourceRead[Any]:
    """Classify actual typed owner errors and explicit causes, never message keywords."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, CalibrationSourceReadRefusal):
            return current.result
        if isinstance(current, (FileNotFoundError, PermissionError, NotImplementedError)):
            return CalibrationSourceRead(
                "not_established", f"{role}:source_unavailable", error=error
            )
        if isinstance(current, CalibrationOrderedBatchBackendUnavailable):
            return CalibrationSourceRead(
                "not_established", "ordered_numeric_profile_unavailable", error=error
            )
        current = current.__cause__
    return CalibrationSourceRead("mismatch", f"{role}:source_invalid", error=error)


def _calibration_source_selection(
    *,
    role: str,
    ref: ArtifactRef | None,
    inputs: Sequence[InputRef] | None,
) -> tuple[ArtifactID, str]:
    """Require one exact selector without reading or inventing a default view."""

    def refuse(status: CalibrationSourceStatus, reason: str) -> None:
        raise CalibrationSourceReadRefusal(
            CalibrationSourceRead(status, f"{role}:{reason}", ref=ref)
        )

    artifact_id = None if ref is None else ref.artifact_id
    profile = None if ref is None else ref.manifest_profile_sha256
    if inputs is not None:
        edges = tuple(edge for edge in inputs if edge.role == role)
        if not edges:
            refuse("not_established", "selection_missing")
        if len(edges) != 1:
            refuse("mismatch", "selection_ambiguous")
        edge = edges[0]
        if ref is not None and (
            edge.artifact_id != ref.artifact_id
            or (
                edge.manifest_profile_sha256 is not None
                and profile is not None
                and edge.manifest_profile_sha256 != profile
            )
        ):
            refuse("mismatch", "selection_conflict")
        if edge.manifest_profile_sha256 is None or (ref is not None and profile is None):
            refuse("not_established", "requires_selected_profile")
        artifact_id, profile = edge.artifact_id, edge.manifest_profile_sha256
    if artifact_id is None:
        refuse("not_established", "selection_missing")
    if profile is None:
        refuse("not_established", "requires_selected_profile")
    assert artifact_id is not None
    assert profile is not None
    return artifact_id, profile


def _calibration_source_ref(raw: object | None) -> ArtifactRef | None:
    """Normalize syntax only; absence precedes typed validation, never qualifies bytes."""
    if raw is None:
        return None
    payload = raw.model_dump(mode="python") if isinstance(raw, BaseModel) else raw
    return ArtifactRef.model_validate(payload)


def _read_calibration_source(
    store: ArtifactStore,
    *,
    role: str,
    decoder: Callable[[ArtifactRef, ArtifactManifest, Any], _CalibrationSourceT],
    ref: object | None = None,
    model: type[BaseModel] | None = None,
    inputs: Sequence[InputRef] | None = None,
    expected_kind: str | None = None,
    expected_schema: str | None = None,
    expected_media_type: str | None = "application/json",
    expected_versions: Collection[str] | None = None,
) -> CalibrationSourceRead[_CalibrationSourceT]:
    """Use Core's exact resolver/profile reader, then the canonical domain decoder.

    Missing selectors are candidate limitations even if a default view is readable.
    More than one edge or conflicting complete selections is a contradiction.
    No default manifest is inferred and no private source is granted access.
    """
    try:
        normalized_ref = _calibration_source_ref(ref)
        artifact_id, profile = _calibration_source_selection(
            role=role, ref=normalized_ref, inputs=inputs
        )
    except CalibrationSourceReadRefusal as error:
        return cast("CalibrationSourceRead[_CalibrationSourceT]", error.result)
    except (TypeError, ValueError) as error:
        classified = classify_calibration_source_error(error, role=role)
        return CalibrationSourceRead(classified.status, classified.code, error=error)
    ref = normalized_ref
    selected_ref = normalized_ref
    manifest = None
    reader = SelectedProfileVerificationReader(store)
    try:
        if any(not callable(getattr(store, name, None)) for name in ("get_manifest", "get_bytes")):
            return CalibrationSourceRead(
                "not_established", f"{role}:reader_capability_unavailable", ref=ref
            )
        try:
            manifest = resolve_manifest_by_profile(reader, artifact_id, profile)
        except TypeError:
            if not callable(getattr(store, "get_manifest_by_profile", None)):
                return CalibrationSourceRead(
                    "not_established", f"{role}:profile_reader_unavailable", ref=ref
                )
            raise
        selected_ref = ArtifactRef(
            artifact_id=artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=profile,
        )
        if ref is not None and (
            ref.kind != selected_ref.kind or ref.media_type != selected_ref.media_type
        ):
            return CalibrationSourceRead(
                "mismatch",
                f"{role}:reference_contract_mismatch",
                ref=selected_ref,
                manifest=manifest,
            )
        if (expected_kind is not None and manifest.kind != expected_kind) or (
            expected_media_type is not None and manifest.media_type != expected_media_type
        ):
            return CalibrationSourceRead(
                "mismatch", f"{role}:kind_media_mismatch", ref=selected_ref, manifest=manifest
            )
        schema = manifest.artifact_schema
        if (expected_schema is not None and (schema is None or schema.name != expected_schema)) or (
            expected_versions is not None
            and (schema is None or schema.version not in expected_versions)
        ):
            return CalibrationSourceRead(
                "mismatch", f"{role}:schema_mismatch", ref=selected_ref, manifest=manifest
            )
        # The existing Core owner validates the declaration and actual payload bytes.
        # Its candidate-only compatibility view is recorded, never admitted as matched.
        if manifest.media_type == "application/json":
            if not callable(getattr(store, "get_raw_manifest_bytes", None)):
                return CalibrationSourceRead(
                    "not_established",
                    f"{role}:reader_capability_unavailable",
                    ref=selected_ref,
                    manifest=manifest,
                )
            read = read_core_json_artifact(reader, selected_ref, allow_profile_absent=True)
            if read.status != "declared_bytes_conformant":
                return CalibrationSourceRead(
                    "not_established",
                    f"{role}:canonical_profile_unqualified",
                    ref=selected_ref,
                    manifest=manifest,
                )
            payload = (
                require_declared_profile(read)
                if model is None
                else validate_core_model_json_artifact(
                    model, reader, selected_ref, raw_payload_bytes=read.raw_payload_bytes
                )
            )
        else:
            if model is not None:
                raise ValueError("calibration_json_model_requires_json_media")
            if not callable(getattr(store, "verify", None)):
                return CalibrationSourceRead(
                    "not_established",
                    f"{role}:reader_capability_unavailable",
                    ref=selected_ref,
                    manifest=manifest,
                )
            payload = reader.get_bytes(selected_ref)
            # Generic CAS integrity is media-neutral. NPZ is decoded only by
            # its existing StateSnapshot owner, never by a JSON canon verifier.
            if not store.verify(selected_ref).ok:
                # Reopen required members; actual absence/denial stays typed.
                reader.get_manifest(selected_ref)
                reader.get_bytes(selected_ref)
                raise ValueError("calibration_source_integrity_failure")
        value = decoder(selected_ref, manifest, payload)
        return CalibrationSourceRead(
            "matched", f"{role}:selected_bytes_decoded", selected_ref, manifest, value
        )
    except (
        FileNotFoundError,
        PermissionError,
        NotImplementedError,
        CalibrationSourceReadRefusal,
        CalibrationOrderedBatchBackendUnavailable,
        TypeError,
        ValueError,
        KeyError,
    ) as error:
        classified = classify_calibration_source_error(error, role=role)
        return CalibrationSourceRead(
            classified.status, classified.code, selected_ref, manifest, error=error
        )


def _require_calibration_raw_result(
    value: Any,
    *,
    selected: ArtifactRef,
    manifest: ArtifactManifest,
    source_bytes: bytes,
    source_spec: CanonSpec | None,
) -> None:
    """Admit only selected metadata or the unchanged raw payload, across media.

    Core owns native canonical values; this helper does not define another codec.
    Pydantic projection is deliberately unavailable to this raw contract, including
    inside a Core-supported container. Domain JSON uses the required-model reader.
    """
    if isinstance(value, ArtifactRef):
        if value.model_dump(mode="python") != selected.model_dump(mode="python"):
            raise ValueError("calibration_raw_reference_does_not_match_selection")
        return
    if isinstance(value, ArtifactManifest):
        if value.model_dump(mode="python") != manifest.model_dump(mode="python"):
            raise ValueError("calibration_raw_manifest_does_not_match_selection")
        return
    active: set[int] = set()

    def refuse_models(item: Any) -> None:
        if isinstance(item, BaseModel):
            raise TypeError("calibration_domain_model_requires_typed_source_owner")
        if isinstance(item, Mapping):
            children = tuple(item.keys()) + tuple(item.values())
        elif is_dataclass(item) and not isinstance(item, type):
            children = tuple(getattr(item, field.name) for field in dataclass_fields(item))
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray, memoryview)
        ):
            children = item
        else:
            return
        identity = id(item)
        if identity in active:
            raise TypeError("calibration_raw_result_requires_native_tree")
        active.add(identity)
        try:
            for child in children:
                refuse_models(child)
        finally:
            active.remove(identity)

    refuse_models(value)
    if source_spec is None:
        # The actual binary owner already verified these bytes. No JSON canon is
        # required or invented for a producer NPZ.
        if type(value) is not bytes or value != source_bytes:
            raise TypeError("calibration_raw_result_requires_selected_binary_bytes")
    elif to_canonical_bytes(value, source_spec) != source_bytes:
        raise ValueError("calibration_raw_result_does_not_match_selected_payload")


def read_calibration_source(
    store: ArtifactStore,
    *,
    role: str,
    decoder: Callable[[ArtifactRef, ArtifactManifest, Any], _CalibrationSourceT],
    ref: object | None = None,
    inputs: Sequence[InputRef] | None = None,
    expected_kind: str | None = None,
    expected_schema: str | None = None,
    expected_media_type: str | None = "application/json",
    expected_versions: Collection[str] | None = None,
) -> CalibrationSourceRead[_CalibrationSourceT]:
    """Read raw canonical values, reference metadata or binary through their owner.

    The media-independent result contract permits the unchanged Core-native raw
    payload/bytes or exact selected ArtifactRef/ArtifactManifest metadata. Domain models and
    nested models require ``read_calibration_model_source`` with their actual owner.
    Metadata exemptions cannot replace the selected identity with another artifact.
    """

    def decode(
        selected: ArtifactRef, manifest: ArtifactManifest, payload: Any
    ) -> _CalibrationSourceT:
        source_spec = None
        if type(payload) is bytes:
            source_bytes = payload
        else:
            if manifest.canon is None:
                raise TypeError("calibration_native_owner_requires_declared_profile")
            source_spec = CanonSpec(**manifest.canon.model_dump(mode="python"))
            source_bytes = to_canonical_bytes(payload, source_spec)
        selected_before = selected.model_copy(deep=True)
        manifest_before = manifest.model_copy(deep=True)
        value = decoder(selected, manifest, payload)
        if selected != selected_before or manifest != manifest_before:
            raise ValueError("calibration_raw_decoder_changed_selected_metadata")
        _require_calibration_raw_result(
            value,
            selected=selected_before,
            manifest=manifest_before,
            source_bytes=source_bytes,
            source_spec=source_spec,
        )
        return value

    return _read_calibration_source(
        store,
        role=role,
        ref=ref,
        inputs=inputs,
        decoder=decode,
        expected_kind=expected_kind,
        expected_schema=expected_schema,
        expected_media_type=expected_media_type,
        expected_versions=expected_versions,
    )


def read_calibration_model_source(
    store: ArtifactStore,
    *,
    role: str,
    model: type[_CalibrationModelT],
    decoder: Callable[[ArtifactRef, ArtifactManifest, _CalibrationModelT], _CalibrationSourceT],
    ref: object | None = None,
    inputs: Sequence[InputRef] | None = None,
    expected_kind: str | None = None,
    expected_schema: str | None = None,
    expected_versions: Collection[str] | None = None,
) -> CalibrationSourceRead[_CalibrationSourceT]:
    """Admit modelled JSON through its required strict Core owner before consumption."""
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        raise TypeError("calibration_typed_source_requires_a_model_owner")

    def decode(
        selected: ArtifactRef, manifest: ArtifactManifest, payload: Any
    ) -> _CalibrationSourceT:
        if not isinstance(payload, model):
            raise TypeError("calibration_typed_source_owner_result_invalid")
        return decoder(selected, manifest, payload)

    return _read_calibration_source(
        store,
        role=role,
        model=model,
        ref=ref,
        inputs=inputs,
        decoder=decode,
        expected_kind=expected_kind,
        expected_schema=expected_schema,
        expected_media_type="application/json",
        expected_versions=expected_versions,
    )


def read_calibration_registry_source(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> CalibrationSourceRead[RegistryBundleContent]:
    """Reuse Core's registry composition with strictly read consumed model members."""
    from polisyos.core.artifacts import RegistryBundlePayload
    from polisyos.core.registry import RegistryBundleContent, load_registry_bundle_content

    def decode(
        selected: ArtifactRef, _manifest: ArtifactManifest, payload: Any
    ) -> RegistryBundleContent:
        # Derive the consumed denominator from the existing content contract.
        # Optional absent members are genuinely not loaded by that owner.
        members = {}
        for field in dataclass_fields(RegistryBundleContent):
            if field.name == "bundle_ref":
                continue
            member_ref = getattr(payload, field.name)
            if member_ref is not None:
                members[field.name] = member_ref
                read_calibration_source(
                    store,
                    role=field.name,
                    ref=member_ref,
                    expected_kind=member_ref.kind,
                    decoder=lambda _ref, _manifest, value: value,
                ).require_value()
        content = load_registry_bundle_content(store, selected)
        strict_values = {}
        for name, member_ref in members.items():
            model = type(getattr(content, name))
            strict_values[name] = read_calibration_model_source(
                store,
                role=name,
                ref=member_ref,
                expected_kind=member_ref.kind,
                model=model,
                decoder=lambda _ref, _manifest, value: value,
            ).require_value()
        return replace(content, **strict_values)

    return read_calibration_model_source(
        store,
        role="registry_bundle",
        ref=ref,
        expected_kind="core.registry_bundle",
        model=RegistryBundlePayload,
        decoder=decode,
    )


def record_calibration_source_error(
    error: BaseException,
    *,
    role: str,
    limitations: set[str],
    issues: set[str],
) -> None:
    """Keep one source classification across existing consumer-specific aliases."""
    result = classify_calibration_source_error(error, role=role)
    if result.status == "not_established":
        limitations.update(("source_execution_not_established", result.code))
    else:
        issues.update((role, result.code))


def _ordered_backend_name() -> str:
    try:
        return jax.default_backend()
    except (ImportError, RuntimeError) as exc:
        raise CalibrationOrderedBatchBackendUnavailable(
            "ordered_input_backend_unavailable"
        ) from exc


def _ordered_numeric_settings() -> dict[str, Any]:
    """Return the supported numeric and legacy-key algorithm context from JAX itself."""
    try:
        return {
            "jax_version": jax.__version__,
            "jaxlib_version": jaxlib.__version__,
            "jax_backend": _ordered_backend_name(),
            "platform_machine": platform.machine(),
            "jax_enable_x64": bool(jax.config.x64_enabled),
            "jax_default_prng_impl": str(jax.config.jax_default_prng_impl),
            "jax_threefry_partitionable": bool(jax.config.jax_threefry_partitionable),
            "jax_enable_custom_prng": bool(jax.config.jax_enable_custom_prng),
            "jax_legacy_prng_key": str(jax.config.jax_legacy_prng_key),
            "jax_safer_randint": bool(jax.config.jax_safer_randint),
            "jax_high_dynamic_range_gumbel": bool(jax.config.jax_high_dynamic_range_gumbel),
            "jax_random_seed_offset": int(jax.config.jax_random_seed_offset),
            "jax_threefry_gpu_kernel_lowering": bool(jax.config.jax_threefry_gpu_kernel_lowering),
            "jax_default_matmul_precision": jax.config.jax_default_matmul_precision,
            "jax_numpy_dtype_promotion": str(jax.config.jax_numpy_dtype_promotion),
            "jax_numpy_rank_promotion": str(jax.config.jax_numpy_rank_promotion),
            "jax_default_dtype_bits": str(jax.config.jax_default_dtype_bits),
        }
    except (AttributeError, TypeError, ValueError) as exc:
        raise CalibrationOrderedBatchBackendUnavailable(
            "ordered_numeric_settings_unavailable"
        ) from exc


class CalibrationOrderedBatchInput(BaseModel):
    """Typed ordered objective inputs; content capture supplies no sampling law."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    authority_purpose: Literal["local_fit_input_only"] = "local_fit_input_only"
    calibration_config_ref: ArtifactRef
    jax_version: str = Field(min_length=1)
    jaxlib_version: str = Field(min_length=1)
    jax_backend: str = Field(min_length=1)
    platform_machine: str = Field(min_length=1)
    jax_enable_x64: bool
    jax_default_prng_impl: Literal["threefry2x32"]
    jax_threefry_partitionable: bool
    jax_enable_custom_prng: Literal[False]
    jax_legacy_prng_key: Literal["allow"]
    jax_safer_randint: bool
    jax_high_dynamic_range_gumbel: bool
    jax_random_seed_offset: int
    jax_threefry_gpu_kernel_lowering: bool
    jax_default_matmul_precision: str | None = None
    jax_numpy_dtype_promotion: str
    jax_numpy_rank_promotion: str
    jax_default_dtype_bits: str
    profile_kind: Literal["ordered_scalar_mse_v1"] = "ordered_scalar_mse_v1"
    objective_kind: Literal["generic_weighted_mse_curvature_only"] = (
        "generic_weighted_mse_curvature_only"
    )
    key_policy: Literal["explicit_complete_fixed_row_keys_v1"] = (
        "explicit_complete_fixed_row_keys_v1"
    )
    inference_status: Literal["unavailable_generic_loss"] = "unavailable_generic_loss"
    target_id: str = Field(min_length=1)
    target_metric_id: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
    rows: tuple[CalibrationOrderedBatchRow, ...] = Field(min_length=1)
    row_times: tuple[_ScheduleStep, ...]
    row_times_dtype: str
    row_keys: tuple[tuple[_KeyWord, _KeyWord], ...]
    targets: tuple[float, ...]
    targets_dtype: str
    weights: tuple[float, ...]
    weights_dtype: str
    consumed_profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    loss_epsilon: float = Field(ge=0, allow_inf_nan=False)
    target_priority: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_ordered_inputs(self) -> CalibrationOrderedBatchInput:
        count = len(self.rows)
        if len({row.row_id for row in self.rows}) != count:
            raise ValueError("ordered_batch_row_ids_must_be_unique")
        if any(
            len(values) != count
            for values in (self.row_times, self.row_keys, self.targets, self.weights)
        ):
            raise ValueError("ordered_batch_inputs_must_have_exact_row_shape")
        if any(not math.isfinite(value) for value in (*self.targets, *self.weights)):
            raise ValueError("ordered_batch_numeric_inputs_must_be_finite")
        if any(value < 0 for value in self.weights) or not 0 < sum(self.weights) < math.inf:
            raise ValueError("ordered_batch_weights_require_positive_finite_support")
        for name in ("targets_dtype", "weights_dtype"):
            dtype = np.dtype(getattr(self, name))
            if dtype not in (np.dtype("float32"), np.dtype("float64")):
                raise ValueError("ordered_batch_targets_and_weights_require_float32_or_float64")
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            effective_weights = np.asarray(self.weights, dtype=np.float32)
            effective_support = np.sum(effective_weights, dtype=np.float32)
            effective_priority = np.asarray(self.target_priority, dtype=np.float32)
            effective_denominator = np.asarray(1.0 + self.loss_epsilon, dtype=np.float32)
        if (
            not np.all(np.isfinite(effective_weights))
            or not 0 < effective_support < np.inf
            or np.any((np.asarray(self.weights) > 0) & (effective_weights == 0))
        ):
            raise ValueError("ordered_batch_effective_weight_support_invalid")
        if not np.isfinite(effective_priority) or effective_priority <= 0:
            raise ValueError("ordered_batch_target_priority_not_representable")
        if not np.isfinite(effective_denominator) or effective_denominator <= 0:
            raise ValueError("ordered_batch_loss_denominator_not_representable")
        if np.dtype(self.row_times_dtype).kind not in "iu":
            raise ValueError("ordered_batch_schedule_dtype_must_be_integer")
        return self


class CalibrationExecutionInputBasis(BaseModel):
    """Persist identity of objects and target arrays consumed by one fit.

    ``input_capture_status`` concerns local content capture only. It does not
    authenticate external sources or certify units, valid time, split policy,
    calibration law, or authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.1"
    authority_purpose: Literal["execution_input_identity_only"] = "execution_input_identity_only"
    input_capture_status: Literal["content_bound", "limited"]
    calibration_config_ref: ArtifactRef
    exec_plan_ref: ArtifactRef | None = None
    exec_plan_sha256: str = Field(pattern=_SHA256_PATTERN)
    program_graph_ref: ArtifactRef
    program_graph_sha256: str = Field(pattern=_SHA256_PATTERN)
    program_graph_status: Literal[
        "selected_source_matched", "selected_source_mismatch", "in_memory_snapshot_only"
    ]
    exec_plan_source_status: Literal[
        "selected_source_matched", "selected_source_mismatch", "object_only"
    ]
    registry_bundle_ref: ArtifactRef | None = None
    registry_bundle_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    registry_bundle_status: Literal[
        "selected_source_matched",
        "selected_source_mismatch",
        "in_memory_content_bound",
        "not_established",
    ]
    mechanism_registry_ref: ArtifactRef | None = None
    mechanism_registry_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    mechanism_registry_status: Literal[
        "selected_source_matched",
        "selected_source_mismatch",
        "in_memory_content_bound",
        "not_established",
    ]
    unit_registry_ref: ArtifactRef | None = None
    unit_registry_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    unit_registry_status: Literal[
        "selected_source_matched",
        "selected_source_mismatch",
        "in_memory_content_bound",
        "not_established",
    ]
    exec_plan: ExecPlan
    base_state_snapshot_ref: ArtifactRef
    base_state_checksum_sha256: str = Field(pattern=_SHA256_PATTERN)
    base_state_source_status: Literal[
        "selected_source_matched", "selected_source_mismatch", "snapshot_materialized_only"
    ]
    target_order: tuple[str, ...]
    target_inputs: tuple[CalibrationTargetInputIdentity, ...]
    parameter_inputs: tuple[CalibrationResolvedParameterInput, ...] = ()
    parameter_unit_identities: tuple[CalibrationParameterUnitIdentity, ...] = ()
    calibrated_parameter_values_sha256: str = Field(pattern=_SHA256_PATTERN)
    report_envelope_sha256: Mapping[str, str] = Field(default_factory=dict)
    runtime_input_sha256: Mapping[str, str] = Field(default_factory=dict)
    runtime_input_roster: tuple[CalibrationRuntimeInputBinding, ...] = ()
    runtime_input_limitations: tuple[str, ...] = ()
    ordered_batch_input_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda x: x is None
    )
    ordered_batch_input_value_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
        exclude_if=lambda x: x is None,
    )
    _resolved_ordered_input: CalibrationOrderedBatchInput | None = PrivateAttr(default=None)
    _resolved_ordered_values: dict[str, Any] | None = PrivateAttr(default=None)

    @property
    def ordered_batch_profile(self) -> CalibrationOrderedBatchInput | None:
        """Return the owner-resolved input, never an unverified inline declaration."""
        return self._resolved_ordered_input

    source_attestation_status: Literal["not_established"] = "not_established"
    unit_status: Literal["not_established"] = "not_established"
    physical_time_status: Literal["not_established"] = "not_established"
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_capture(self) -> CalibrationExecutionInputBasis:
        target_ids = tuple(item.target_id for item in self.target_inputs)
        if len(set(self.target_order)) != len(self.target_order):
            raise ValueError("calibration_execution_target_order_must_be_unique")
        if len(set(target_ids)) != len(target_ids) or set(target_ids) != set(self.target_order):
            raise ValueError("calibration_execution_target_inputs_must_match_target_order")
        if tuple(item.ordinal for item in self.parameter_inputs) != tuple(
            range(len(self.parameter_inputs))
        ):
            raise ValueError("calibration_parameter_input_ordinals_must_be_contiguous")
        if any(not _is_sha256(value) for value in self.runtime_input_sha256.values()):
            raise ValueError("runtime_input_digests_must_be_sha256")
        roster_names = tuple(item.input_name for item in self.runtime_input_roster)
        if len(set(roster_names)) != len(roster_names):
            raise ValueError("calibration_runtime_input_roster_names_must_be_unique")
        if self.schema_version == "1.1" and roster_names != CALIBRATION_RUNTIME_INPUT_NAMES:
            raise ValueError("calibration_runtime_input_roster_must_cover_calibrator_inputs")
        if self.schema_version == "1.2" and roster_names != CALIBRATION_RUNTIME_INPUT_NAMES_V1_2:
            raise ValueError("calibration_runtime_input_roster_must_cover_calibrator_inputs")
        if self.schema_version == "1.0" and self.runtime_input_roster:
            raise ValueError("legacy_calibration_input_basis_cannot_claim_v1_1_roster")
        if self.schema_version in {"1.1", "1.2"} and self.runtime_input_sha256:
            raise ValueError("v1_1_runtime_input_roster_replaces_untyped_digest_map")
        if (self.schema_version == "1.2") != (self.ordered_batch_input_ref is not None):
            raise ValueError("v1_2_requires_selected_ordered_input_and_legacy_versions_forbid_it")
        if (self.ordered_batch_input_ref is not None) != (
            self.ordered_batch_input_value_sha256 is not None
        ):
            raise ValueError("ordered_input_ref_and_digest_must_coexist")
        if self.schema_version != "1.2" and any(
            target.source_kind == "ordered_batch_profile" for target in self.target_inputs
        ):
            raise ValueError("ordered_batch_observations_cannot_be_downgraded_to_scalar_basis")
        if any(not _is_sha256(value) for value in self.report_envelope_sha256.values()):
            raise ValueError("report_envelope_digests_must_be_sha256")
        if self.unit_status != "not_established":
            raise ValueError("external_unit_definition_status_is_not_produced_here")
        registry_status_pairs = (
            (self.registry_bundle_status, self.registry_bundle_sha256),
            (self.mechanism_registry_status, self.mechanism_registry_sha256),
            (self.unit_registry_status, self.unit_registry_sha256),
        )
        for status, digest in registry_status_pairs:
            if status in {"selected_source_matched", "in_memory_content_bound"} and digest is None:
                raise ValueError("registry_digest_required_for_content_bound_status")
            if status in {"not_established"} and digest is not None:
                raise ValueError("registry_digest_not_allowed_without_established_content")
        if (
            self.registry_bundle_status in {"selected_source_matched", "selected_source_mismatch"}
            and self.registry_bundle_ref is None
        ):
            raise ValueError("selected_registry_bundle_status_requires_ref")
        if (
            self.mechanism_registry_status
            in {"selected_source_matched", "selected_source_mismatch"}
            and self.mechanism_registry_ref is None
        ):
            raise ValueError("selected_mechanism_registry_status_requires_ref")
        if (
            self.unit_registry_status in {"selected_source_matched", "selected_source_mismatch"}
            and self.unit_registry_ref is None
        ):
            raise ValueError("selected_unit_registry_status_requires_ref")
        if self.input_capture_status == "content_bound":
            if self.runtime_input_limitations:
                raise ValueError("content_bound_capture_cannot_have_unbound_runtime_inputs")
            if any(
                item.status != "content_bound" or item.effective_values_status != "content_bound"
                for item in self.parameter_inputs
            ):
                raise ValueError("content_bound_capture_requires_resolved_parameter_digests")
        return self


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _canonical_value(value: object) -> object:
    """Return a JSON-safe value without stringifying unsupported objects."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non_finite_input_has_no_canonical_identity")
        return value
    if isinstance(value, Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, (datetime, date)):
        return {"$iso8601": value.isoformat()}
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="json"))
    if isinstance(value, np.ndarray):
        return {
            "$array": {
                "dtype": str(value.dtype),
                "shape": list(value.shape),
                "values": _canonical_value(value.tolist()),
            }
        }
    if isinstance(value, np.generic):
        return {
            "$numpy_scalar": {
                "dtype": str(value.dtype),
                "value": _canonical_value(value.item()),
            }
        }
    if isinstance(value, jax.Array):
        return _canonical_value(np.asarray(value))
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical_value(getattr(value, field.name))
            for field in dataclass_fields(value)
        }
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical_input_mapping_keys_must_be_strings")
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    raise TypeError(
        f"unsupported_canonical_input_type:{type(value).__module__}.{type(value).__qualname__}"
    )


def canonical_input_sha256(value: object) -> str:
    """Hash a finite JSON-compatible input using the repository encoder."""
    payload = to_canonical_bytes(_canonical_value(value), CanonSpec(forbid_floats=False))
    return hashlib.sha256(payload).hexdigest()


def reconcile_selected_runtime_input(
    binding: CalibrationRuntimeInputBinding,
    *,
    selected_ref: ArtifactRef | None,
    selected_value: object | None,
) -> Literal["matched", "not_established", "mismatch"]:
    """Recompute one captured runtime registry-member relation at a fresh consumer.

    The saved value digest is a capture of the object passed to calibration;
    this function resolves the independently selected member and compares its
    exact ref and canonical bytes against that capture.
    """
    if binding.source_role != "runtime_registry_member":
        raise ValueError("runtime_input_binding_is_not_registry_member")
    if binding.input_name not in RUNTIME_REGISTRY_MEMBER_INPUT_NAMES:
        raise ValueError("runtime_input_binding_registry_member_name_invalid")
    if selected_ref is None:
        if selected_value is not None:
            if binding.status == "selected_source_absent":
                return "mismatch"
            return "not_established"
        if binding.status == "selected_source_absent" and binding.source_ref is None:
            return "matched"
        if binding.status in {"in_memory_content_bound", "not_established", "absent"}:
            return "not_established"
        return "mismatch"
    if selected_value is None:
        return "mismatch"
    try:
        selected_digest = canonical_input_sha256(selected_value)
    except (TypeError, ValueError, OverflowError):
        return "not_established"
    if binding.value_sha256 is None:
        return "mismatch" if binding.status == "selected_source_absent" else "not_established"
    if binding.value_sha256 != selected_digest:
        return "mismatch"
    if binding.source_ref is None:
        return "not_established"
    if binding.source_ref != selected_ref:
        return "mismatch"
    if binding.source_payload_sha256 != selected_digest:
        return "mismatch"
    if binding.status == "selected_source_mismatch":
        return "mismatch"
    if selected_ref.manifest_profile_sha256 is None or binding.status != "selected_source_matched":
        return "not_established"
    return "matched"


def calibration_report_series_sha256(*, real: Sequence[float], time: Sequence[float] | None) -> str:
    """Hash exact ordered observed values and optional report time axis."""
    return canonical_input_sha256(
        {"real": list(real), "time": None if time is None else list(time)}
    )


def calibration_report_time_axis_sha256(time: Sequence[float] | None) -> str | None:
    """Hash an ordered report time axis, returning ``None`` when absent."""
    return None if time is None else canonical_input_sha256(list(time))


def _ordered_edge(inputs: Sequence[InputRef], role: str, expected: ArtifactRef) -> None:
    _calibration_source_selection(role=role, ref=expected, inputs=inputs)


def _ordered_json_payload(store: ArtifactStore, ref: ArtifactRef) -> Any:
    """Read selected JSON through the same typed availability owner as consumers."""
    return read_calibration_source(
        store,
        role="calibration_dependency",
        ref=ref,
        expected_kind=ref.kind,
        decoder=lambda _ref, _manifest, payload: payload,
    ).require_value()


def _resolve_ordered_input_values(
    store: ArtifactStore,
    profile: CalibrationOrderedBatchInput,
    *,
    inputs: Sequence[InputRef],
) -> dict[str, Any]:
    """Reopen the requested selected config and every row, before fit consumption."""
    from polisyos.core.contracts.foundry import StateSnapshot
    from polisyos.foundry.calibration.report import read_calibration_config_source
    from polisyos.foundry.execute import load_state_snapshot
    from polisyos.ir.analytics.calibration import TargetAlignConfig

    actual_settings = _ordered_numeric_settings()
    if any(getattr(profile, name) != value for name, value in actual_settings.items()):
        raise CalibrationOrderedBatchBackendUnavailable("ordered_input_numeric_profile_unavailable")
    config_ref = profile.calibration_config_ref
    config = read_calibration_config_source(store, ref=config_ref, inputs=inputs).require_value()
    if len(config.targets) != 1:
        raise ValueError("ordered_input_requires_one_configured_target")
    target = config.targets[0]
    if (
        target.target_id != profile.target_id
        or target.model_metric_path != profile.target_metric_id
        or target.loss.kind != "mse"
        or target.loss.relative
        or target.aggregation != "none"
        or target.loss.epsilon != profile.loss_epsilon
        or target.loss.weight != profile.target_priority
        or target.fabric_query is not None
        or target.fabric_metric is not None
        or target.align != TargetAlignConfig()
        or config.seed_strategy != "fixed"
        or config.multi_start is not None
        or config.grad_norm.enabled
        or config.prior_loss.enabled
        or config.constraint_loss.enabled
        or config.steps not in (None, len(profile.rows))
        or (
            config.time_axis is not None
            and list(config.time_axis) != [float(t) for t in profile.row_times]
        )
    ):
        raise ValueError("ordered_input_selected_config_does_not_match_request")
    roles = tuple(f"ordered_batch_row.{i}" for i in range(len(profile.rows)))
    edges = tuple(edge for edge in inputs if edge.role.startswith("ordered_batch_row."))
    if tuple(edge.role for edge in edges) != roles:
        raise ValueError("ordered_input_row_edges_must_be_complete_and_ordered")
    if len(inputs) != len(profile.rows) + 1:
        raise ValueError("ordered_input_has_unbound_manifest_edges")
    states = []
    for ordinal, (row, edge) in enumerate(zip(profile.rows, edges, strict=True)):
        _ordered_edge(inputs, roles[ordinal], row.state_snapshot_ref)
        snapshot = read_calibration_model_source(
            store,
            role=roles[ordinal],
            ref=row.state_snapshot_ref,
            expected_kind="foundry.state_snapshot",
            model=StateSnapshot,
            decoder=lambda _ref, _manifest, value: value,
        ).require_value()
        # This first full-row profile uses the current full-state writer;
        # historical bare blob lineage and sparse method slots are distinct contracts.
        if snapshot.schema_version != "2.2":
            raise ValueError("ordered_input_row_requires_full_state_snapshot_v2_2")
        if snapshot.step != profile.row_times[ordinal]:
            raise ValueError("ordered_input_row_schedule_does_not_match_selected_snapshot")
        _ordered_edge(
            store.get_manifest(row.state_snapshot_ref).inputs, "state_blob", snapshot.state_ref
        )
        state = load_state_snapshot(store, snapshot_ref=row.state_snapshot_ref)
        if canonical_input_sha256(state) != row.state_values_sha256:
            raise ValueError("ordered_input_row_state_values_mismatch")
        states.append(state)
    try:
        targets = np.asarray(profile.targets, dtype=np.dtype(profile.targets_dtype))
        weights = np.asarray(profile.weights, dtype=np.dtype(profile.weights_dtype))
        times = np.asarray(profile.row_times, dtype=np.dtype(profile.row_times_dtype))
        keys = np.asarray(profile.row_keys, dtype=np.uint32)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("ordered_input_array_representation_invalid") from exc
    if tuple(targets.tolist()) != profile.targets or tuple(weights.tolist()) != profile.weights:
        raise ValueError("ordered_input_values_do_not_match_declared_dtypes")
    values = {
        "row_ids": tuple(row.row_id for row in profile.rows),
        "states": jax.tree_util.tree_map(lambda *rows: np.stack(rows), *states),
        "row_times": times,
        "row_keys": keys,
        "target_path": profile.target_path,
        "targets": targets,
        "weights": weights,
    }
    if canonical_input_sha256(values) != profile.consumed_profile_sha256:
        raise ValueError("ordered_input_complete_profile_mismatch")
    return values


def put_calibration_ordered_batch_input(
    store: ArtifactStore,
    profile: CalibrationOrderedBatchInput,
    *,
    inputs: list[InputRef],
) -> ArtifactRef:
    """Publish the independently selected input that the producer will reopen and consume."""
    profile = CalibrationOrderedBatchInput.model_validate(profile.model_dump(mode="python"))
    _resolve_ordered_input_values(store, profile, inputs=inputs)
    return store.put_json(
        profile,
        PutOptions(
            kind=_ORDERED_INPUT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_ORDERED_INPUT_SCHEMA, version=profile.schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def resolve_calibration_ordered_batch_input(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> tuple[CalibrationOrderedBatchInput, dict[str, Any]]:
    """Read exact selected input bytes with the shared availability classification."""

    def decode(
        selected: ArtifactRef, manifest: ArtifactManifest, payload: Any
    ) -> tuple[CalibrationOrderedBatchInput, dict[str, Any]]:
        del selected
        profile = _decode_versioned_calibration_model(
            CalibrationOrderedBatchInput, manifest, payload
        )
        return profile, _resolve_ordered_input_values(store, profile, inputs=manifest.inputs)

    return read_calibration_model_source(
        store,
        role="calibration_ordered_input",
        ref=ref,
        expected_kind=_ORDERED_INPUT_KIND,
        expected_schema=_ORDERED_INPUT_SCHEMA,
        model=CalibrationOrderedBatchInput,
        decoder=decode,
    ).require_value()


def reconcile_ordered_batch_inputs(
    store: ArtifactStore,
    basis: CalibrationExecutionInputBasis,
    *,
    inputs: Sequence[InputRef],
) -> None:
    """Resolve an independent selected input; the basis cannot declare its own weights or keys."""
    if basis.ordered_batch_input_ref is None:
        return
    ref = basis.ordered_batch_input_ref
    _ordered_edge(inputs, "ordered_batch_input", ref)
    _ordered_edge(inputs, "calibration_config", basis.calibration_config_ref)
    profile, values = resolve_calibration_ordered_batch_input(store, ref)
    if profile.calibration_config_ref != basis.calibration_config_ref:
        raise ValueError("ordered_input_basis_config_ref_mismatch")
    digest = canonical_input_sha256(profile)
    if basis.ordered_batch_input_value_sha256 != digest:
        raise ValueError("ordered_input_basis_payload_digest_mismatch")
    binding = basis.runtime_input_roster[-1]
    if (
        binding.input_name != "ordered_batch_profile"
        or binding.status != "selected_source_matched"
        or binding.source_ref != ref
        or binding.value_sha256 != digest
        or binding.source_payload_sha256 != digest
    ):
        raise ValueError("ordered_input_runtime_roster_does_not_bind_selected_input")
    if basis.target_order != (profile.target_id,):
        raise ValueError("ordered_input_target_order_mismatch")
    target = basis.target_inputs[0]
    if (
        target.source_kind != "ordered_batch_profile"
        or canonical_input_sha256(profile.targets) != target.observed_values_sha256
        or calibration_report_time_axis_sha256([float(t) for t in profile.row_times])
        != target.report_time_axis_sha256
    ):
        raise ValueError("ordered_input_report_observation_identity_mismatch")
    basis._resolved_ordered_input = profile
    basis._resolved_ordered_values = values


def put_calibration_execution_input_basis(
    store: ArtifactStore,
    basis: CalibrationExecutionInputBasis,
    *,
    inputs: list[InputRef],
) -> ArtifactRef:
    """Persist a freshly validated basis; row identity is admitted before publication."""
    basis = CalibrationExecutionInputBasis.model_validate(basis.model_dump(mode="python"))
    if basis.ordered_batch_input_ref is not None:
        reconcile_ordered_batch_inputs(store, basis, inputs=inputs)
    return store.put_json(
        basis,
        PutOptions(
            kind=_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_ARTIFACT_SCHEMA_NAME, version=basis.schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _decode_versioned_calibration_model(
    model: type[_CalibrationModelT],
    manifest: ArtifactManifest,
    payload: Any,
) -> _CalibrationModelT:
    """Use the actual model version contract and bind the selected header to it."""
    if not isinstance(payload, model):
        raise TypeError("calibration_model_must_come_from_core_typed_json_reader")
    value = payload
    if manifest.artifact_schema is None or manifest.artifact_schema.version != getattr(
        value, "schema_version", None
    ):
        raise ValueError("calibration_selected_manifest_payload_version_mismatch")
    return value


def _decode_calibration_execution_input_basis(
    store: ArtifactStore,
    ref: ArtifactRef,
    manifest: ArtifactManifest,
    payload: Any,
) -> CalibrationExecutionInputBasis:
    basis = _decode_versioned_calibration_model(CalibrationExecutionInputBasis, manifest, payload)
    if basis.ordered_batch_input_ref is not None:
        if ref.manifest_profile_sha256 is None:
            raise ValueError("ordered_batch_basis_requires_selected_manifest_profile")
        reconcile_ordered_batch_inputs(store, basis, inputs=manifest.inputs)
    return basis


def read_calibration_execution_input_basis_source(
    store: ArtifactStore,
    *,
    ref: ArtifactRef | None = None,
    inputs: Sequence[InputRef] | None = None,
) -> CalibrationSourceRead[CalibrationExecutionInputBasis]:
    """Qualify exact selected basis bytes; a readable bare ID stays candidate-only."""
    return read_calibration_model_source(
        store,
        role="calibration_execution_input_basis",
        ref=ref,
        inputs=inputs,
        expected_kind=_ARTIFACT_KIND,
        expected_schema=_ARTIFACT_SCHEMA_NAME,
        model=CalibrationExecutionInputBasis,
        decoder=lambda selected, manifest, payload: _decode_calibration_execution_input_basis(
            store,
            selected,
            manifest,
            payload,
        ),
    )


def load_calibration_execution_input_basis(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> CalibrationExecutionInputBasis:
    """Read legacy scalar display bytes; only the source reader qualifies evidence."""
    manifest = store.get_manifest(ref)
    if manifest.kind != _ARTIFACT_KIND or manifest.media_type != "application/json":
        raise ValueError("calibration_execution_input_basis_kind_mismatch")
    schema = manifest.artifact_schema
    if schema is None or schema.name != _ARTIFACT_SCHEMA_NAME:
        raise ValueError("calibration_execution_input_basis_schema_mismatch")
    if schema.version not in {"1.0", "1.1"}:
        return read_calibration_execution_input_basis_source(store, ref=ref).require_value()
    payload = from_canonical_bytes(store.get_bytes(ref))
    if not store.verify(ref).ok:
        store.get_manifest(ref)
        store.get_bytes(ref)
        raise ValueError("calibration_execution_input_basis_integrity_failure")
    # This is the pre-existing legacy display interpretation, including selected
    # no-canon history. It is never used by welfare/autotune/response qualification.
    basis = CalibrationExecutionInputBasis.model_validate(payload)
    if basis.schema_version != schema.version:
        raise ValueError("calibration_selected_manifest_payload_version_mismatch")
    return basis


def read_calibration_report_source(
    store: ArtifactStore,
    *,
    ref: object | None = None,
    inputs: Sequence[InputRef] | None = None,
) -> CalibrationSourceRead[CalibrationReport]:
    """Read and decode one selected supported report without granting authority."""
    from polisyos.foundry.calibration.report import CalibrationReport

    def decode(
        selected: ArtifactRef, manifest: ArtifactManifest, payload: Any
    ) -> CalibrationReport:
        del selected
        return _decode_versioned_calibration_model(CalibrationReport, manifest, payload)

    return read_calibration_model_source(
        store,
        role="calibration_report",
        ref=ref,
        inputs=inputs,
        expected_kind="foundry.calibration_report",
        expected_schema="polisyos.foundry.CalibrationReport",
        model=CalibrationReport,
        decoder=decode,
    )


def reconcile_ordered_batch_report_identity(
    basis: CalibrationExecutionInputBasis,
    report: CalibrationReport,
) -> None:
    """Bind the typed report scope to the independently selected consumed input."""
    scope = report.ordered_batch_execution
    profile = basis.ordered_batch_profile
    if scope is not None:
        _calibration_source_selection(
            role="ordered_report_input", ref=scope.selected_input_ref, inputs=None
        )
    if (
        basis.schema_version != "1.2"
        or scope is None
        or profile is None
        or scope.selected_input_ref != basis.ordered_batch_input_ref
        or scope.consumed_profile_sha256 != profile.consumed_profile_sha256
    ):
        raise ValueError("ordered_report_does_not_bind_selected_consumed_input")
    if tuple(report.series_comparison) != basis.target_order:
        raise ValueError("ordered_report_target_order_mismatch")
    for target in basis.target_inputs:
        series = report.series_comparison[target.target_id]
        if (
            calibration_report_series_sha256(real=series.real, time=series.time)
            != target.report_series_sha256
        ):
            raise ValueError("ordered_report_observations_or_rows_mismatch")
    if canonical_input_sha256(report.calibrated_params) != basis.calibrated_parameter_values_sha256:
        raise ValueError("ordered_report_fitted_parameter_identity_mismatch")
    envelopes = {
        name: canonical_input_sha256(value)
        for name, value in (report.uncertainty_envelopes or {}).items()
    }
    if envelopes != dict(basis.report_envelope_sha256):
        raise ValueError("ordered_report_envelope_identity_mismatch")


def replay_ordered_batch_report_projection(
    store: ArtifactStore,
    basis_ref: ArtifactRef | None,
    report_ref: ArtifactRef,
) -> tuple[Literal["matched", "mismatch", "not_established"], tuple[str, ...]]:
    """Independently replay one selected final forward and its loss/metric projection.

    This does not rerun optimization or Hessian calculation, certify an optimum,
    or establish a sampling law. A different numeric runtime profile is unavailable.
    """
    import jax.numpy as jnp

    from polisyos.core.contracts.foundry import ProgramGraph, StateSnapshot
    from polisyos.foundry.calibration.calibrator import (
        OrderedBatchCalibrationProfile,
        _ordered_batch_parameter_dtype,
        _resolve_metric_path,
        evaluate_ordered_batch_objective,
    )
    from polisyos.foundry.calibration.pure_executor import (
        apply_trainable_values,
        compile_program,
    )
    from polisyos.foundry.calibration.report import (
        CalibrationReport,
        ordered_batch_fit_metrics,
        read_calibration_config_source,
    )
    from polisyos.foundry.execute import load_state_snapshot

    report_source = read_calibration_report_source(store, ref=report_ref)
    if report_source.status != "matched":
        return report_source.status, (report_source.code,)
    report = report_source.require_value()
    manifest = report_source.manifest
    assert manifest is not None
    if report.schema_version != "2.1" or report.ordered_batch_execution is None:
        return "mismatch", ("ordered_selected_report_manifest_invalid",)
    basis_source = read_calibration_execution_input_basis_source(
        store, ref=basis_ref, inputs=manifest.inputs
    )
    if basis_source.status != "matched":
        return basis_source.status, (basis_source.code,)
    basis = basis_source.require_value()
    basis_ref = basis_source.ref
    assert basis_ref is not None
    try:
        _ordered_edge(manifest.inputs, "calibration_config", basis.calibration_config_ref)
    except (TypeError, ValueError, KeyError) as error:
        result = classify_calibration_source_error(error, role="calibration_config")
        return result.status, (result.code,)
    profile = basis.ordered_batch_profile
    values = basis._resolved_ordered_values
    if profile is None or values is None:
        return "not_established", ("ordered_selected_input_not_resolved",)
    try:
        reconcile_ordered_batch_report_identity(basis, report)
    except (TypeError, ValueError, KeyError) as error:
        result = classify_calibration_source_error(
            error, role="ordered_report_selected_input_identity"
        )
        return result.status, (result.code,)
    if any(
        ref is None or ref.manifest_profile_sha256 is None
        for ref in (
            basis.exec_plan_ref,
            basis.program_graph_ref,
            basis.registry_bundle_ref,
            basis.base_state_snapshot_ref,
        )
    ):
        return "not_established", ("ordered_replay_requires_selected_common_sources",)
    try:
        config = read_calibration_config_source(
            store, ref=profile.calibration_config_ref
        ).require_value()
        graph = read_calibration_model_source(
            store,
            role="program_graph",
            ref=basis.program_graph_ref,
            expected_kind=basis.program_graph_ref.kind,
            model=ProgramGraph,
            decoder=lambda _ref, _manifest, value: value,
        ).require_value()
        plan = read_calibration_model_source(
            store,
            role="exec_plan",
            ref=basis.exec_plan_ref,
            expected_kind=basis.exec_plan_ref.kind,
            model=ExecPlan,
            decoder=lambda _ref, _manifest, value: value,
        ).require_value()
        registry = read_calibration_registry_source(
            store, basis.registry_bundle_ref
        ).require_value()
        if profile.target_path != _resolve_metric_path(
            config.targets[0].model_metric_path, registry.slot_registry
        ):
            return "mismatch", ("ordered_replay_target_path_configuration_mismatch",)
        state = read_calibration_model_source(
            store,
            role="base_state_snapshot",
            ref=basis.base_state_snapshot_ref,
            expected_kind="foundry.state_snapshot",
            model=StateSnapshot,
            decoder=lambda selected, _manifest, _payload: load_state_snapshot(
                store, snapshot_ref=selected
            ),
        ).require_value()
        consumed = OrderedBatchCalibrationProfile(
            **{
                name: (
                    jax.tree_util.tree_map(jnp.asarray, value)
                    if name == "states"
                    else jnp.asarray(value)
                    if name not in {"row_ids", "target_path"}
                    else value
                )
                for name, value in values.items()
            }
        )
        _ordered_edge(
            store.get_manifest(basis.exec_plan_ref).inputs, "program_graph", basis.program_graph_ref
        )
        if (
            plan.program_ref.artifact_id != basis.program_graph_ref.artifact_id
            or plan.program_ref.manifest_profile_sha256
            != basis.program_graph_ref.manifest_profile_sha256
        ):
            return "mismatch", ("ordered_replay_plan_graph_selection_mismatch",)
        parameter_calls = []
        basis_edges = store.get_manifest(basis_ref).inputs

        def load_parameters(ref: Any) -> Any:
            ordinal = len(parameter_calls)
            if ordinal >= len(basis.parameter_inputs):
                raise ValueError("ordered_replay_parameter_call_roster_mismatch")
            captured = basis.parameter_inputs[ordinal]
            if not isinstance(ref, ArtifactRef):
                raise ValueError("ordered_replay_parameter_source_not_a_reference")
            _calibration_source_selection(role=f"parameter_input.{ordinal}", ref=ref, inputs=None)
            _ordered_edge(basis_edges, f"parameter_input.{ordinal}", ref)
            if captured.source_ref != ref:
                raise ValueError("ordered_replay_parameter_selected_source_mismatch")
            payload = _ordered_json_payload(store, ref)
            digest = canonical_input_sha256(payload)
            if (
                captured.source_status != "selected_source_matched"
                or captured.payload_sha256 != digest
                or captured.source_payload_sha256 != digest
            ):
                raise ValueError("ordered_replay_parameter_payload_mismatch")
            parameter_calls.append(ref)
            return payload

        bundle = compile_program(
            graph,
            plan,
            mechanism_registry=registry.mechanism_registry,
            slot_registry=registry.slot_registry,
            merge_registry=registry.merge_registry,
            selector_field_registry=registry.selector_field_registry,
            base_state=state,
            parameter_loader=load_parameters,
            force_fidelity=config.fidelity.mode,
            default_temperature=config.fidelity.temperature,
            force_override=config.fidelity.force_override,
        )
        if len(parameter_calls) != len(basis.parameter_inputs):
            return "mismatch", ("ordered_replay_parameter_call_roster_mismatch",)
        names = [f"{bundle.nodes[h.node_index].node_id}.{h.field_name}" for h in bundle.trainables]
        if set(names) != set(report.calibrated_params) or len(names) != len(set(names)):
            return "mismatch", ("ordered_report_fitted_field_roster_mismatch",)
        dtype = _ordered_batch_parameter_dtype(consumed, bundle)
        fitted = [jnp.asarray(report.calibrated_params[name], dtype=dtype) for name in names]
        result = evaluate_ordered_batch_objective(
            consumed,
            bundle=apply_trainable_values(bundle, fitted),
            loss_config=config.targets[0].loss,
        )
        if not bool(result.valid):
            return "mismatch", ("ordered_selected_final_forward_numeric_invalid",)
        actual_model = [float(value) for value in np.asarray(result.predictions)]
        comparison = report.series_comparison[profile.target_id]
        if comparison.model != actual_model:
            return "mismatch", ("ordered_report_model_does_not_match_selected_final_forward",)
        priority = jnp.asarray(config.targets[0].loss.weight, dtype=jnp.float32)
        total = float(result.objective * priority)
        if (
            report.total_loss != total
            or dict(report.per_target_loss) != {profile.target_id: total}
            or dict(report.target_weights) != {profile.target_id: float(priority)}
        ):
            return "mismatch", ("ordered_report_loss_does_not_match_selected_objective",)
        metrics = ordered_batch_fit_metrics(actual_model, profile.targets, profile.weights)
        quality = report.fit_quality
        if (
            quality is None
            or quality.aggregate != metrics
            or dict(quality.per_target) != {profile.target_id: metrics}
        ):
            return "mismatch", ("ordered_report_metrics_do_not_match_selected_projection",)
    except (
        CalibrationOrderedBatchBackendUnavailable,
        FileNotFoundError,
        PermissionError,
        NotImplementedError,
        TypeError,
        ValueError,
        KeyError,
        OverflowError,
        FloatingPointError,
    ) as exc:
        result = classify_calibration_source_error(
            exc, role="ordered_final_forward_source_or_projection"
        )
        return result.status, (result.code,)
    except (ImportError, ModuleNotFoundError) as exc:
        return "not_established", (f"ordered_replay_backend_unavailable:{type(exc).__name__}",)
    except RuntimeError as exc:
        return "not_established", (
            f"ordered_final_forward_execution_unavailable:{type(exc).__name__}",
        )
    return "matched", ("ordered_hessian_is_unreplayed_curvature_diagnostic",)


__all__ = [
    "CalibrationSourceRead",
    "CalibrationSourceReadRefusal",
    "CalibrationSourceStatus",
    "classify_calibration_source_error",
    "read_calibration_source",
    "read_calibration_model_source",
    "read_calibration_registry_source",
    "read_calibration_execution_input_basis_source",
    "read_calibration_report_source",
    "record_calibration_source_error",
    "CalibrationExecutionInputBasis",
    "CalibrationOrderedBatchInput",
    "CalibrationOrderedBatchBackendUnavailable",
    "CalibrationOrderedBatchRow",
    "reconcile_ordered_batch_inputs",
    "reconcile_ordered_batch_report_identity",
    "replay_ordered_batch_report_projection",
    "put_calibration_ordered_batch_input",
    "resolve_calibration_ordered_batch_input",
    "CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2",
    "CALIBRATION_RUNTIME_INPUT_NAMES_V1_2",
    "CalibrationRuntimeInputBinding",
    "CalibrationParameterUnitIdentity",
    "CalibrationResolvedParameterInput",
    "CalibrationTargetInputIdentity",
    "CALIBRATION_RUNTIME_INPUT_CONTRACT",
    "CALIBRATION_RUNTIME_INPUT_NAMES",
    "RUNTIME_REGISTRY_MEMBER_CONTRACT",
    "RUNTIME_REGISTRY_MEMBER_INPUT_NAMES",
    "calibration_report_series_sha256",
    "calibration_report_time_axis_sha256",
    "canonical_input_sha256",
    "load_calibration_execution_input_basis",
    "put_calibration_execution_input_basis",
    "reconcile_selected_runtime_input",
]
