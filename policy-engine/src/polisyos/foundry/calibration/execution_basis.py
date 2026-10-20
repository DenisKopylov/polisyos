"""Content-bound input identity for persisted Foundry calibration runs.

This artifact records the exact run objects and ordered target bytes consumed by
``Calibrator``. It is an identity record only: source custody, measurement
units, physical time semantics, and an observation/noise law remain separate
claims and are not inferred here.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

import jax
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactRef, ArtifactStore, InputRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.foundry import ExecPlan

_ARTIFACT_KIND = "foundry.calibration_execution_input_basis"
_ARTIFACT_SCHEMA_NAME = "polisyos.foundry.CalibrationExecutionInputBasis"
_ARTIFACT_SCHEMA_VERSION = "1.1"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"

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


class CalibrationExecutionInputBasis(BaseModel):
    """Persist identity of objects and target arrays consumed by one fit.

    ``input_capture_status`` concerns local content capture only. It does not
    authenticate external sources or certify units, valid time, split policy,
    calibration law, or authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.1"
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
        if self.schema_version == "1.0" and self.runtime_input_roster:
            raise ValueError("legacy_calibration_input_basis_cannot_claim_v1_1_roster")
        if self.schema_version == "1.1" and self.runtime_input_sha256:
            raise ValueError("v1_1_runtime_input_roster_replaces_untyped_digest_map")
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


def put_calibration_execution_input_basis(
    store: ArtifactStore,
    basis: CalibrationExecutionInputBasis,
    *,
    inputs: list[InputRef],
) -> ArtifactRef:
    """Persist one typed calibration execution-input basis with exact input edges."""
    return store.put_json(
        basis,
        PutOptions(
            kind=_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_ARTIFACT_SCHEMA_NAME, version=_ARTIFACT_SCHEMA_VERSION),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def load_calibration_execution_input_basis(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> CalibrationExecutionInputBasis:
    """Read and validate a persisted calibration execution-input basis."""
    manifest = store.get_manifest(ref)
    if manifest.kind != _ARTIFACT_KIND or manifest.media_type != "application/json":
        raise ValueError("calibration_execution_input_basis_kind_mismatch")
    schema = manifest.artifact_schema
    if schema is None or schema.name != _ARTIFACT_SCHEMA_NAME:
        raise ValueError("calibration_execution_input_basis_schema_mismatch")
    if not store.verify(ref).ok:
        raise ValueError("calibration_execution_input_basis_integrity_failure")
    payload = from_canonical_bytes(store.get_bytes(ref))
    basis = CalibrationExecutionInputBasis.model_validate(payload)
    if basis.schema_version != schema.version:
        raise ValueError("calibration_execution_input_basis_schema_version_mismatch")
    return basis


__all__ = [
    "CalibrationExecutionInputBasis",
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
