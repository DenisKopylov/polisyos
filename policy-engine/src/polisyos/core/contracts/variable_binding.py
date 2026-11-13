"""Versioned semantic and measurement contracts for model input binding.

These records identify meanings and representations. They do not establish
that an external measurement is scientifically equivalent to a model input;
Catalog assessment remains candidate-only until the actual source and model
owners admit the same selected artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.core.contracts.model_input_requirements import ModelInputPort

_SELECTED_PROFILE_SHA256 = r"^sha256:[0-9a-f]{64}$"
_NAMESPACED_ID = r"^[a-z][a-z0-9_.-]*$"
_SCOPED_CONDITION_KEYS = frozenset(
    {"unit", "population_ref", "jurisdiction_ref", "geography_ref", "time_period_basis"}
)


class SelectedVariableBindingRef(ArtifactRef):
    """Require an exact immutable CAS manifest view for a binding input."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    manifest_profile_sha256: str = Field(pattern=_SELECTED_PROFILE_SHA256, strict=True)


class VariableSemanticDefinitionRef(SelectedVariableBindingRef):
    """Selected CAS reference to one versioned semantic definition."""

    kind: Literal["catalog.variable_semantic_definition"] = "catalog.variable_semantic_definition"
    media_type: Literal["application/json"] = "application/json"


class VariableRepresentationRef(SelectedVariableBindingRef):
    """Selected CAS reference to one versioned measurement representation."""

    kind: Literal["catalog.variable_representation"] = "catalog.variable_representation"
    media_type: Literal["application/json"] = "application/json"


class MeasurementBindingProfileRef(SelectedVariableBindingRef):
    """Selected CAS reference to the required-axis policy for one model input."""

    kind: Literal["catalog.measurement_binding_profile"] = "catalog.measurement_binding_profile"
    media_type: Literal["application/json"] = "application/json"


class ScopedMeasurementOccurrenceRef(SelectedVariableBindingRef):
    """Exact selected Catalog occurrence materialized from an admitted epoch."""

    kind: Literal["catalog.scoped_measurement_occurrence"] = "catalog.scoped_measurement_occurrence"
    media_type: Literal["application/json"] = "application/json"


class ScopedCorrespondenceBasisRef(SelectedVariableBindingRef):
    """Exact selected relation basis for one Catalog occurrence and model port."""

    kind: Literal["catalog.scoped_correspondence_basis"] = "catalog.scoped_correspondence_basis"
    media_type: Literal["application/json"] = "application/json"


class MeasurementAxis(StrEnum):
    """Typed measurement axes checked by the selected binding profile."""

    QUANTITY_KIND = "quantity_kind"
    MEASURE_FORM = "measure_form"
    UNIT_ID = "unit_id"
    SCALE_TO_UNIT = "scale_to_unit"
    NUMERATOR_REF = "numerator_ref"
    DENOMINATOR_REF = "denominator_ref"
    TIME_SUPPORT = "time_support"
    TEMPORAL_GRANULARITY = "temporal_granularity"
    AGGREGATION = "aggregation"
    GRAIN = "grain"
    POPULATION_REF = "population_ref"
    METHODOLOGY_REF = "methodology_ref"


class ModelInputScope(BaseModel):
    """Exact population, geography, jurisdiction, and time scope of one port.

    ``period_basis`` is optional for legacy wire compatibility. A semantic
    measurement match must provide a supported basis explicitly; annual labels
    alone do not identify calendar versus fiscal periods.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    population_ref: str = Field(min_length=1, strict=True)
    geography_ref: str = Field(min_length=1, strict=True)
    jurisdiction_ref: str = Field(min_length=1, strict=True)
    period_start: date
    period_end: date
    time_role: Literal["observation_time", "valid_time"]
    period_basis: Literal["calendar_year", "fiscal_year", "unknown"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @field_validator("population_ref", "geography_ref", "jurisdiction_ref")
    @classmethod
    def _scope_refs_are_trimmed(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("model_input_scope_ref_must_be_trimmed")
        return value

    @model_validator(mode="after")
    def _period_is_ordered(self) -> ModelInputScope:
        if self.period_end < self.period_start:
            raise ValueError("model_input_scope_period_inverted")
        return self


class FixedUnitTransformWitness(BaseModel):
    """Source-owner evidence for the already-applied fixed multiplicative operator."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["polisyos.data_forge.fixed_unit_transform_evidence.v1"] = (
        "polisyos.data_forge.fixed_unit_transform_evidence.v1"
    )
    transform_ref: Literal["fabric://units/fixed-multiplicative/v1"] = (
        "fabric://units/fixed-multiplicative/v1"
    )
    executor_version: Literal["polisyos.fabric.units.fixed-multiplicative.v1"] = (
        "polisyos.fabric.units.fixed-multiplicative.v1"
    )
    binding_id: str = Field(pattern=r"^field-binding:sha256:[0-9a-f]{64}$", strict=True)
    raw_unit: str = Field(min_length=1, strict=True)
    canonical_unit: str = Field(min_length=1, strict=True)
    multiplier: str = Field(min_length=1, strict=True)
    definition_content_sha256: str = Field(pattern=_SELECTED_PROFILE_SHA256, strict=True)

    @field_validator("multiplier")
    @classmethod
    def _multiplier_is_finite_positive(cls, value: str) -> str:
        number = Decimal(value)
        if not number.is_finite() or number <= 0:
            raise ValueError("fixed_unit_transform_multiplier_must_be_finite_positive")
        return value


class ScopedSourceSelection(BaseModel):
    """Typed source-owner projection extracted from the selected admission passport."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_receipt_ref: SelectedVariableBindingRef
    source_passport_ref: SelectedVariableBindingRef
    source_boundary_candidate_ref: SelectedVariableBindingRef
    source_record_ref: SelectedVariableBindingRef
    epoch_id: int = Field(gt=0, strict=True)
    passport_id: str = Field(min_length=1, strict=True)
    dataset_id: str = Field(min_length=1, strict=True)
    dataset_version: str = Field(min_length=1, strict=True)
    source_watermark: str = Field(pattern=_SELECTED_PROFILE_SHA256, strict=True)
    measured_source_body_sha256: str | None = Field(
        default=None,
        pattern=_SELECTED_PROFILE_SHA256,
        strict=True,
        exclude_if=lambda value: value is None,
    )
    declared_source_condition: tuple[tuple[str, str], ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    declared_source_definition_ref: VariableSemanticDefinitionRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    declared_source_representation_ref: VariableRepresentationRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    observation_class: Literal["observed", "proxy", "derived", "model_output"]
    raw_field: str = Field(min_length=1, strict=True)
    canonical_variable: str = Field(min_length=1, strict=True)
    raw_unit: str = Field(min_length=1, strict=True)
    canonical_unit: str = Field(min_length=1, strict=True)
    unit_transform: Literal["identity", "fixed_multiplicative"]
    unit_transform_ref: str | None = Field(default=None, min_length=1, strict=True)
    binding_id: str = Field(pattern=r"^field-binding:sha256:[0-9a-f]{64}$", strict=True)
    aggregation_method: Literal["identity", "mean", "sum", "last"]
    is_proxy: bool

    @staticmethod
    def declared_condition_from_passport(
        passport_mapping: Mapping[str, object],
    ) -> tuple[tuple[str, str], ...]:
        """Return only scope coordinates bound to the source entry's identity."""
        return _declared_source_condition_from_passport(passport_mapping)

    @staticmethod
    def apply_declared_condition(
        condition: Mapping[str, object], declared: tuple[tuple[str, str], ...]
    ) -> dict[str, object]:
        """Merge source declarations, rejecting contradictory row coordinates."""
        return _apply_declared_source_condition(condition, declared)

    @model_validator(mode="after")
    def _selected_source_refs(self) -> ScopedSourceSelection:
        if any(
            ref.manifest_profile_sha256 is None
            for ref in (
                self.source_receipt_ref,
                self.source_passport_ref,
                self.source_boundary_candidate_ref,
                self.source_record_ref,
            )
        ):
            raise ValueError("scoped_source_selection_ref_unselected")
        if self.unit_transform == "identity" and self.raw_unit != self.canonical_unit:
            raise ValueError("scoped_source_identity_unit_mismatch")
        if self.unit_transform == "fixed_multiplicative" and (
            self.unit_transform_ref != "fabric://units/fixed-multiplicative/v1"
        ):
            raise ValueError("scoped_source_fixed_transform_unregistered")
        if (
            self.source_receipt_ref.kind != "epoch.activated_overlay_admission_receipt"
            or self.source_passport_ref.kind != "epoch.acquisition_passport_snapshot"
            or self.source_boundary_candidate_ref.kind
            != "epoch.acquisition_semantic_boundary_candidate"
        ):
            raise ValueError("scoped_source_selection_ref_kind_mismatch")
        keys = tuple(key for key, _value in self.declared_source_condition)
        if (
            keys != tuple(sorted(set(keys)))
            or any(key not in _SCOPED_CONDITION_KEYS - {"unit"} for key in keys)
            or any(
                not value or value != value.strip()
                for _key, value in self.declared_source_condition
            )
        ):
            raise ValueError("scoped_source_selection_declared_condition_invalid")
        return self


class ScopedMeasurementOccurrence(BaseModel):
    """One exact admitted Catalog row with its source refs and canonical value.

    This is a compact projection, not a copied source dataset. It links the
    projected value to the original selected raw CAS object, active receipt,
    passport, and boundary candidate. The Catalog owner writes it only after
    re-reading those inputs and the active row.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = "catalog.scoped_measurement_occurrence"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.ScopedMeasurementOccurrence"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "polisyos.catalog.scoped_measurement_occurrence.v1"
    }

    schema_version: Literal["polisyos.catalog.scoped_measurement_occurrence.v1"] = (
        "polisyos.catalog.scoped_measurement_occurrence.v1"
    )
    source_scope: ModelInputScope
    source_receipt_ref: SelectedVariableBindingRef
    source_passport_ref: SelectedVariableBindingRef
    source_boundary_candidate_ref: SelectedVariableBindingRef
    source_record_ref: SelectedVariableBindingRef
    observation_id: str = Field(min_length=1, strict=True)
    observation_content_sha256: str = Field(pattern=_SELECTED_PROFILE_SHA256, strict=True)
    dataset_id: str = Field(min_length=1, strict=True)
    dataset_version: str = Field(min_length=1, strict=True)
    source_watermark: str = Field(pattern=_SELECTED_PROFILE_SHA256, strict=True)
    raw_variable: str = Field(min_length=1, strict=True)
    canonical_variable: str = Field(min_length=1, strict=True)
    country_code: str = Field(min_length=1, strict=True)
    year: int | None = None
    survey_year: int | None = None
    wave: int | None = None
    observation_class: Literal["observed", "proxy", "derived", "model_output"]
    condition_json: str = Field(strict=True)
    acquisition_method: str = Field(min_length=1, strict=True)
    raw_values: tuple[str, ...] = Field(min_length=1)
    aggregation_method: Literal["identity", "mean", "sum", "last"]
    canonical_value: str = Field(min_length=1, strict=True)
    canonical_unit: str = Field(min_length=1, strict=True)
    unit_transform_evidence: FixedUnitTransformWitness | None = None

    @field_validator("condition_json")
    @classmethod
    def _condition_is_json_object(cls, value: str) -> str:
        import json

        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("scoped_measurement_occurrence_condition_invalid") from exc
        if not isinstance(decoded, dict):
            raise ValueError("scoped_measurement_occurrence_condition_not_object")
        return value

    @field_validator("raw_values")
    @classmethod
    def _raw_numeric_strings_are_finite(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        try:
            numbers = tuple(Decimal(item) for item in value)
        except (ArithmeticError, TypeError) as exc:
            raise ValueError("scoped_measurement_occurrence_numeric_value_invalid") from exc
        if any(not number.is_finite() for number in numbers):
            raise ValueError("scoped_measurement_occurrence_numeric_value_not_finite")
        return value

    @field_validator("canonical_value")
    @classmethod
    def _canonical_numeric_string_is_finite(cls, value: str) -> str:
        try:
            number = Decimal(value)
        except ArithmeticError as exc:
            raise ValueError("scoped_measurement_occurrence_numeric_value_invalid") from exc
        if not number.is_finite():
            raise ValueError("scoped_measurement_occurrence_numeric_value_not_finite")
        return value

    @model_validator(mode="after")
    def _source_refs_are_selected(self) -> ScopedMeasurementOccurrence:
        refs = (
            self.source_receipt_ref,
            self.source_passport_ref,
            self.source_boundary_candidate_ref,
            self.source_record_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("scoped_measurement_occurrence_source_ref_unselected")
        if self.unit_transform_evidence is not None and (
            self.unit_transform_evidence.canonical_unit != self.canonical_unit
        ):
            raise ValueError("scoped_measurement_occurrence_transform_unit_mismatch")
        return self


class ScopedCorrespondenceBasis(BaseModel):
    """Exact bounded basis that Foundry can independently reopen and replay."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = "catalog.scoped_correspondence_basis"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.ScopedCorrespondenceBasis"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "polisyos.catalog.scoped_correspondence_basis.v1"
    }

    schema_version: Literal["polisyos.catalog.scoped_correspondence_basis.v1"] = (
        "polisyos.catalog.scoped_correspondence_basis.v1"
    )
    profile_id: Literal["measurement_to_model.same_definition.v1"] = (
        "measurement_to_model.same_definition.v1"
    )
    occurrence_ref: ScopedMeasurementOccurrenceRef
    source_definition_ref: VariableSemanticDefinitionRef
    source_representation_ref: VariableRepresentationRef
    source_definition_evidence_refs: tuple[SelectedVariableBindingRef, ...] = Field(min_length=1)
    model_interface_ref: SelectedVariableBindingRef
    model_port_id: str = Field(min_length=1, strict=True)
    target_definition_ref: VariableSemanticDefinitionRef
    target_representation_ref: VariableRepresentationRef
    binding_profile_ref: MeasurementBindingProfileRef
    scope: ModelInputScope

    @model_validator(mode="after")
    def _basis_refs_are_selected(self) -> ScopedCorrespondenceBasis:
        refs = (
            self.occurrence_ref,
            self.source_definition_ref,
            self.source_representation_ref,
            *self.source_definition_evidence_refs,
            self.model_interface_ref,
            self.target_definition_ref,
            self.target_representation_ref,
            self.binding_profile_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("scoped_correspondence_basis_ref_unselected")
        return self


class ScopedCorrespondenceEvaluation(BaseModel):
    """Pure result of replaying one bounded selected correspondence basis."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["candidate", "refused"]
    semantic_correspondence: Literal["recomputed", "not_established"]
    recomputed_axes: tuple[MeasurementAxis, ...] = ()
    optional_unknown_axes: tuple[MeasurementAxis, ...] = ()
    limitation_codes: tuple[str, ...] = ()
    refusal_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _status_matches_predicate(self) -> ScopedCorrespondenceEvaluation:
        if self.status == "candidate" and (
            self.semantic_correspondence != "recomputed" or self.refusal_codes
        ):
            raise ValueError("scoped_correspondence_evaluation_candidate_invalid")
        if self.status == "refused" and not self.refusal_codes:
            raise ValueError("scoped_correspondence_evaluation_refusal_unexplained")
        return self


class VariableSemanticDefinition(BaseModel):
    """Immutable namespaced meaning, separate from labels and measurements."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = "catalog.variable_semantic_definition"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.VariableSemanticDefinition"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "polisyos.catalog.variable_semantic_definition.v1"
    }

    schema_version: Literal["polisyos.catalog.variable_semantic_definition.v1"] = (
        "polisyos.catalog.variable_semantic_definition.v1"
    )
    namespace: str = Field(pattern=_NAMESPACED_ID, strict=True)
    stable_id: str = Field(pattern=_NAMESPACED_ID, strict=True)
    revision: str = Field(min_length=1, strict=True)
    meaning: str = Field(min_length=1, max_length=2000, strict=True)
    definition_evidence_refs: tuple[SelectedVariableBindingRef, ...] = Field(min_length=1)


class VariableRepresentation(BaseModel):
    """Versioned typed axes for a measurement of one semantic definition.

    `None` means that an axis is unknown or not supplied. The selected profile
    decides whether that is a refusal or a retained limitation; it is never a
    wildcard.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = "catalog.variable_representation"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.VariableRepresentation"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "2.0")
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "polisyos.catalog.variable_representation.v1",
        "2.0": "polisyos.catalog.variable_representation.v2",
    }

    schema_version: Literal[
        "polisyos.catalog.variable_representation.v1",
        "polisyos.catalog.variable_representation.v2",
    ] = "polisyos.catalog.variable_representation.v1"
    representation_id: str = Field(pattern=_NAMESPACED_ID, strict=True)
    revision: str = Field(min_length=1, strict=True)
    semantic_definition_ref: VariableSemanticDefinitionRef
    quantity_kind: (
        Literal["stock", "flow", "parameter", "outcome", "count", "index", "state", "categorical"]
        | None
    ) = None
    measure_form: Literal["absolute", "ratio", "rate", "index", "count"] | None = None
    unit_id: str | None = Field(default=None, min_length=1, strict=True)
    scale_to_unit: Decimal | None = None
    numerator_ref: VariableSemanticDefinitionRef | None = None
    denominator_ref: VariableSemanticDefinitionRef | None = None
    time_support: (
        Literal[
            "instant",
            "period_total",
            "period_average",
            "period_rate",
            "cumulative",
            "state_start",
            "state_end",
            "not_applicable",
        ]
        | None
    ) = None
    temporal_granularity: str | None = Field(default=None, min_length=1, strict=True)
    aggregation: Literal["identity", "mean", "sum", "last"] | None = None
    grain: tuple[str, ...] | None = None
    population_ref: str | None = Field(default=None, min_length=1, strict=True)
    methodology_ref: SelectedVariableBindingRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def _methodology_matches_transport_version(self) -> VariableRepresentation:
        if self.schema_version == "polisyos.catalog.variable_representation.v1" and (
            "methodology_ref" in self.model_fields_set
        ):
            raise ValueError("variable_representation_methodology_requires_v2")
        if self.methodology_ref is not None and self.methodology_ref.kind != "fabric.doc.raw":
            raise ValueError("variable_representation_methodology_document_kind_mismatch")
        return self

    @field_validator("scale_to_unit")
    @classmethod
    def _scale_is_finite_positive(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (not value.is_finite() or value <= 0):
            raise ValueError("variable_representation_scale_must_be_finite_positive")
        return value

    @field_validator("temporal_granularity", "population_ref")
    @classmethod
    def _optional_axis_text_is_trimmed(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise ValueError("variable_representation_axis_must_be_trimmed")
        return value

    @field_validator("grain")
    @classmethod
    def _grain_is_unique_and_trimmed(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        if any(not item or item != item.strip() for item in value):
            raise ValueError("variable_representation_grain_invalid")
        if len(set(value)) != len(value):
            raise ValueError("variable_representation_grain_duplicate")
        return value


_HARD_REQUIRED_AXES = frozenset(
    {
        MeasurementAxis.QUANTITY_KIND,
        MeasurementAxis.MEASURE_FORM,
        MeasurementAxis.UNIT_ID,
        MeasurementAxis.TIME_SUPPORT,
    }
)


class MeasurementBindingProfile(BaseModel):
    """Versioned, model-selected policy for required and optional axes."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = "catalog.measurement_binding_profile"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.catalog.MeasurementBindingProfile"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "2.0")
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "polisyos.catalog.measurement_binding_profile.v1",
        "2.0": "polisyos.catalog.measurement_binding_profile.v2",
    }

    schema_version: Literal[
        "polisyos.catalog.measurement_binding_profile.v1",
        "polisyos.catalog.measurement_binding_profile.v2",
    ] = "polisyos.catalog.measurement_binding_profile.v1"
    profile_id: str = Field(pattern=_NAMESPACED_ID, strict=True)
    revision: str = Field(min_length=1, strict=True)
    required_axes: tuple[MeasurementAxis, ...] = Field(min_length=4)
    optional_axes: tuple[MeasurementAxis, ...] = ()

    @model_validator(mode="after")
    def _profile_cannot_weaken_semantic_minima(self) -> MeasurementBindingProfile:
        required = frozenset(self.required_axes)
        optional = frozenset(self.optional_axes)
        if len(required) != len(self.required_axes) or len(optional) != len(self.optional_axes):
            raise ValueError("measurement_binding_profile_duplicate_axis")
        if required.intersection(optional):
            raise ValueError("measurement_binding_profile_axis_both_required_and_optional")
        if not _HARD_REQUIRED_AXES.issubset(required):
            raise ValueError("measurement_binding_profile_cannot_weaken_required_axes")
        if self.schema_version == "polisyos.catalog.measurement_binding_profile.v1" and (
            MeasurementAxis.METHODOLOGY_REF in required | optional
        ):
            raise ValueError("measurement_binding_profile_methodology_requires_v2")
        return self


def variable_representation_manifest_inputs(value: VariableRepresentation) -> tuple[InputRef, ...]:
    """Return exact declared dependencies for a selected measurement representation.

    The methodology document records the represented method's declared source,
    not verification of its scientific validity or authority.
    """
    inputs = [
        input_ref_from_artifact_ref(value.semantic_definition_ref, role="semantic_definition")
    ]
    if value.methodology_ref is not None:
        inputs.append(input_ref_from_artifact_ref(value.methodology_ref, role="methodology"))
    return tuple(inputs)


def load_variable_representation(
    store: CoreJSONArtifactStore,
    ref: VariableRepresentationRef,
) -> VariableRepresentation:
    """Load a selected representation and its v2 declared document dependencies.

    Legacy v1 retains its existing selected-payload checks. V2 additionally binds
    every declared dependency in the selected manifest and opens any methodology
    document's exact bytes. Document availability and identity establish neither
    external empirical validity nor permission for a new current use.

    Streaming Core owners verify the complete document through fixed-size reads;
    this bounds its payload working memory, not total bytes or time. A legacy
    reader without the existing stream protocol retains the full-byte fallback.

    Args:
        store: Existing Core artifact read owner.
        ref: Exact selected representation manifest view.

    Returns:
        Strictly validated representation with its unchanged declared semantics.

    Raises:
        ValueError: A v2 dependency, document profile, or document bytes disagree.
        OSError: Referenced artifact bytes are unavailable.
    """
    from polisyos.core.artifacts import (
        CoreJSONArtifactStreamingReader,
        artifact_manifest_profile_sha256,
        validate_core_model_json_artifact,
    )

    value = validate_core_model_json_artifact(VariableRepresentation, store, ref)
    if value.schema_version == "polisyos.catalog.variable_representation.v1":
        return value
    if tuple(store.get_manifest(ref).inputs) != variable_representation_manifest_inputs(value):
        raise ValueError("variable_representation_manifest_inputs_mismatch")
    validate_core_model_json_artifact(
        VariableSemanticDefinition, store, value.semantic_definition_ref
    )
    methodology = value.methodology_ref
    if methodology is not None:
        manifest = store.get_manifest(methodology)
        if (
            manifest.artifact_id != methodology.artifact_id
            or manifest.kind != methodology.kind
            or manifest.media_type != methodology.media_type
            or artifact_manifest_profile_sha256(manifest) != methodology.manifest_profile_sha256
        ):
            raise ValueError("variable_representation_methodology_profile_mismatch")
        if (
            manifest.artifact_schema is None
            or manifest.artifact_schema.name != "fabric.doc.raw"
            or manifest.artifact_schema.version != "1.0"
        ):
            raise ValueError("variable_representation_methodology_document_schema_mismatch")
        if isinstance(store, CoreJSONArtifactStreamingReader):
            # The existing owner checks the exact selected manifest, size and
            # full payload digest at EOF/context exit; no second codec or
            # caller-supplied integrity declaration stands in for that check.
            with store.open_member(methodology, "blob") as member:
                while member.read(64 * 1024):
                    pass
        else:
            raw = store.get_bytes(methodology)
            if hashlib.sha256(raw).hexdigest() != methodology.artifact_id.hex:
                raise ValueError("variable_representation_methodology_bytes_mismatch")
    return value


class MeasurementCorrespondenceResult(BaseModel):
    """Scoped structural assessment that never grants an executable binding."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["polisyos.catalog.measurement_correspondence_result.v1"] = (
        "polisyos.catalog.measurement_correspondence_result.v1"
    )
    status: Literal["candidate", "refused"]
    source_observation_id: str = Field(min_length=1, strict=True)
    source_definition_ref: VariableSemanticDefinitionRef
    source_representation_ref: VariableRepresentationRef
    model_interface_ref: SelectedVariableBindingRef
    model_port_id: str = Field(min_length=1, strict=True)
    target_definition_ref: VariableSemanticDefinitionRef | None = None
    target_representation_ref: VariableRepresentationRef | None = None
    binding_profile_ref: MeasurementBindingProfileRef | None = None
    occurrence_ref: ScopedMeasurementOccurrenceRef | None = None
    correspondence_basis_ref: ScopedCorrespondenceBasisRef | None = None
    recomputed_axes: tuple[MeasurementAxis, ...] = ()
    optional_unknown_axes: tuple[MeasurementAxis, ...] = ()
    limitation_codes: tuple[str, ...] = ()
    refusal_codes: tuple[str, ...] = ()
    semantic_correspondence: Literal["recomputed", "not_established"] = "not_established"
    independent_origin: Literal["not_established"] = "not_established"
    source_currentness: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _status_matches_recomputed_disposition(self) -> MeasurementCorrespondenceResult:
        if self.status == "candidate" and (
            self.refusal_codes
            or self.semantic_correspondence != "recomputed"
            or self.occurrence_ref is None
            or self.correspondence_basis_ref is None
            or self.target_definition_ref is None
            or self.target_representation_ref is None
            or self.binding_profile_ref is None
        ):
            raise ValueError("measurement_correspondence_candidate_not_recomputed")
        if self.status == "refused" and not self.refusal_codes:
            raise ValueError("measurement_correspondence_refusal_requires_reason")
        if len(set(self.recomputed_axes)) != len(self.recomputed_axes):
            raise ValueError("measurement_correspondence_recomputed_axis_duplicate")
        if len(set(self.optional_unknown_axes)) != len(self.optional_unknown_axes):
            raise ValueError("measurement_correspondence_optional_axis_duplicate")
        return self


def scoped_measurement_occurrence_manifest_inputs(
    occurrence: ScopedMeasurementOccurrence,
) -> tuple[InputRef, ...]:
    """Return the exact role-qualified source edges for one occurrence artifact."""

    return (
        input_ref_from_artifact_ref(occurrence.source_receipt_ref, role="active_receipt"),
        input_ref_from_artifact_ref(occurrence.source_passport_ref, role="source_passport"),
        input_ref_from_artifact_ref(
            occurrence.source_boundary_candidate_ref, role="source_boundary_candidate"
        ),
        input_ref_from_artifact_ref(occurrence.source_record_ref, role="source_record"),
    )


def scoped_correspondence_basis_manifest_inputs(
    basis: ScopedCorrespondenceBasis,
) -> tuple[InputRef, ...]:
    """Return the exact role-qualified edges that the relation reader must reopen."""

    return (
        input_ref_from_artifact_ref(basis.occurrence_ref, role="selected_source_occurrence"),
        input_ref_from_artifact_ref(basis.source_definition_ref, role="source_definition"),
        input_ref_from_artifact_ref(basis.source_representation_ref, role="source_representation"),
        *tuple(
            input_ref_from_artifact_ref(ref, role=f"source_definition_evidence:{index}")
            for index, ref in enumerate(basis.source_definition_evidence_refs)
        ),
        input_ref_from_artifact_ref(basis.model_interface_ref, role="selected_model_interface"),
        input_ref_from_artifact_ref(basis.target_definition_ref, role="model_port_definition"),
        input_ref_from_artifact_ref(
            basis.target_representation_ref, role="model_port_representation"
        ),
        input_ref_from_artifact_ref(basis.binding_profile_ref, role="selected_binding_profile"),
    )


def _declared_source_condition_from_passport(
    passport: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    entry = passport.get("source_authority_entry")
    if entry is None:
        if passport.get("schema_version") == "polisyos.runtime.acquisition_admission_passport.v3":
            raise ValueError("scoped_source_declaration_entry_missing")
        return ()
    if passport.get(
        "schema_version"
    ) != "polisyos.runtime.acquisition_admission_passport.v3" or not isinstance(entry, Mapping):
        raise ValueError("scoped_source_declaration_carrier_invalid")
    identity = {str(key): value for key, value in entry.items() if key != "entry_id"}
    if entry.get("entry_id") != "acquisition-authority:" + _catalog_content_sha256(
        identity
    ) or entry.get("entry_id") != passport.get("authority_entry_id"):
        raise ValueError("scoped_source_declaration_entry_identity_mismatch")
    registration = passport.get("registration")
    scope = entry.get("source_measure_scope")
    if (
        not isinstance(registration, Mapping)
        or not isinstance(scope, Mapping)
        or entry.get("source_lane") != passport.get("source_lane")
        or entry.get("target_variable") != passport.get("variable_id")
        or entry.get("landing_dataset_id") != registration.get("catalog_dataset_id")
        or entry.get("landing_distribution_id") != registration.get("distribution_id")
    ):
        raise ValueError("scoped_source_declaration_registration_mismatch")
    coordinates = {
        "population_ref": scope.get("population"),
        "jurisdiction_ref": scope.get("jurisdiction_ref"),
        "geography_ref": scope.get("geography_ref"),
        "time_period_basis": scope.get("time_period_basis"),
    }
    if not isinstance(coordinates["population_ref"], str) or not coordinates["population_ref"]:
        raise ValueError("scoped_source_declaration_population_missing")
    if any(
        value is not None and (not isinstance(value, str) or not value or value != value.strip())
        for value in coordinates.values()
    ):
        raise ValueError("scoped_source_declaration_coordinate_invalid")
    if coordinates["geography_ref"] is not None and not scope.get("source_geography_id"):
        raise ValueError("scoped_source_declaration_geography_identity_missing")
    return tuple(
        sorted((key, value) for key, value in coordinates.items() if isinstance(value, str))
    )


def _apply_declared_source_condition(
    condition: Mapping[str, object], declared: tuple[tuple[str, str], ...]
) -> dict[str, object]:
    result = dict(condition)
    for key, value in declared:
        if key in result and result[key] != value:
            raise ValueError("scoped_source_declaration_row_conflict")
        result[key] = value
    return result


def scoped_source_selection_from_passport_mapping(
    passport_mapping: Mapping[str, object],
    *,
    source_receipt_ref: SelectedVariableBindingRef,
    source_passport_ref: SelectedVariableBindingRef,
    source_boundary_candidate_ref: SelectedVariableBindingRef,
    source_record_ref: SelectedVariableBindingRef,
) -> ScopedSourceSelection:
    """Rebuild the minimal source mapping from one verified persisted passport.

    The caller must first load the exact passport and source-boundary candidate
    through their existing CAS owners. This adapter checks the source-owner
    field-binding identity and its selected references; it does not assert that
    a provider's meaning is scientifically true.
    """

    schema_version = passport_mapping.get("schema_version")
    if schema_version not in {
        "polisyos.runtime.acquisition_admission_passport.v1",
        "polisyos.runtime.acquisition_admission_passport.v2",
        "polisyos.runtime.acquisition_admission_passport.v3",
    }:
        raise ValueError("scoped_source_passport_schema_unrecognized")
    registration = passport_mapping.get("registration")
    if not isinstance(registration, Mapping):
        raise ValueError("scoped_source_passport_registration_missing")
    binding = registration.get("field_binding")
    if not isinstance(binding, Mapping):
        raise ValueError("scoped_source_passport_field_binding_missing")
    copied_binding = passport_mapping.get("field_binding")
    if copied_binding is not None and copied_binding != binding:
        raise ValueError("scoped_source_passport_binding_projection_mismatch")

    binding_id = binding.get("binding_id")
    recomputed_binding_id = "field-binding:" + _catalog_content_sha256(
        {str(key): value for key, value in binding.items() if key != "binding_id"}
    )
    if binding_id != recomputed_binding_id:
        raise ValueError("scoped_source_passport_binding_identity_mismatch")
    dataset_id = registration.get("catalog_dataset_id")
    canonical_variable = binding.get("canonical_variable")
    if (
        binding.get("dataset_id") != dataset_id
        or registration.get("metric_id") != canonical_variable
    ):
        raise ValueError("scoped_source_passport_registration_binding_mismatch")

    passport_boundary_ref = passport_mapping.get("semantic_boundary_candidate_ref")
    if not isinstance(passport_boundary_ref, Mapping):
        raise ValueError("scoped_source_passport_boundary_ref_missing")
    boundary_ref = ArtifactRef.model_validate(passport_boundary_ref)
    if not _same_artifact_without_profile(boundary_ref, source_boundary_candidate_ref):
        raise ValueError("scoped_source_passport_boundary_ref_mismatch")
    raw_artifact_id = passport_mapping.get("raw_artifact_id")
    live_source = passport_mapping.get("live_source_execution")
    expected_record_id = (
        raw_artifact_id
        if live_source is None
        else live_source.get("normalized_data_artifact_id")
        if isinstance(live_source, Mapping)
        else None
    )
    if str(source_record_ref.artifact_id) != str(expected_record_id):
        raise ValueError("scoped_source_passport_raw_record_ref_mismatch")

    measured_body_sha256 = None
    if isinstance(live_source, Mapping):
        measured_profile = passport_mapping.get("measured_profile")
        raw_ref = live_source.get("raw_artifact_ref")
        if not isinstance(measured_profile, Mapping) or not isinstance(raw_ref, Mapping):
            raise ValueError("scoped_source_live_selected_carriers_missing")
        raw_selected = ArtifactRef.model_validate(raw_ref)
        measured_body_sha256 = measured_profile.get("sample_content_sha256")
        if (
            raw_selected.manifest_profile_sha256 is None
            or raw_selected.kind != "fabric.acquisition.raw_evidence"
            or raw_selected.media_type != "application/json"
            or str(raw_selected.artifact_id) != str(raw_artifact_id)
            or str(raw_artifact_id) != passport_mapping.get("source_watermark")
            or live_source.get("raw_body_sha256") != passport_mapping.get("source_watermark")
            or not isinstance(measured_body_sha256, str)
        ):
            raise ValueError("scoped_source_live_selected_carriers_mismatch")

    declared_condition = _declared_source_condition_from_passport(passport_mapping)
    source_entry = passport_mapping.get("source_authority_entry")
    declared_definition = None
    declared_representation = None
    if isinstance(source_entry, Mapping):
        definition_ref = source_entry.get("source_semantic_definition_ref")
        representation_ref = source_entry.get("source_representation_ref")
        if definition_ref is not None:
            declared_definition = VariableSemanticDefinitionRef.model_validate(definition_ref)
        if representation_ref is not None:
            declared_representation = VariableRepresentationRef.model_validate(representation_ref)

    return ScopedSourceSelection(
        source_receipt_ref=source_receipt_ref,
        source_passport_ref=source_passport_ref,
        source_boundary_candidate_ref=source_boundary_candidate_ref,
        source_record_ref=source_record_ref,
        epoch_id=passport_mapping["epoch_id"],
        passport_id=passport_mapping["passport_id"],
        dataset_id=dataset_id,
        dataset_version=passport_mapping["dataset_version"],
        source_watermark=passport_mapping["source_watermark"],
        measured_source_body_sha256=measured_body_sha256,
        declared_source_condition=declared_condition,
        declared_source_definition_ref=declared_definition,
        declared_source_representation_ref=declared_representation,
        observation_class=passport_mapping["observation_class"],
        raw_field=binding["raw_field"],
        canonical_variable=canonical_variable,
        raw_unit=binding["raw_unit"],
        canonical_unit=binding["canonical_unit"],
        unit_transform=binding["unit_transform"],
        unit_transform_ref=binding.get("unit_transform_ref"),
        binding_id=binding_id,
        aggregation_method=binding["aggregation_method"],
        is_proxy=binding["is_proxy"],
    )


def replay_scoped_measurement_occurrence(
    raw_source_body: bytes,
    *,
    observation_id: str,
    source_selection: ScopedSourceSelection,
    unit_transform_evidence: FixedUnitTransformWitness | None,
) -> ScopedMeasurementOccurrence:
    """Reconstruct one Catalog occurrence from the verified measurement rows.

    The caller must load and qualify the raw bytes and ``ScopedSourceSelection``
    from the exact source record and admission passport. This function independently
    repeats the registered finite raw-field projection so consumers do not trust
    values or coordinates asserted only by the occurrence artifact.

    Args:
        raw_source_body: Raw local rows or owner-replayed normalized live rows.
        observation_id: Row identity selected from the active Catalog projection.
        source_selection: Typed field mapping from that exact admission passport.
        unit_transform_evidence: Exact unit-witness recomputed by the admitted operator.

    Returns:
        ScopedMeasurementOccurrence: Independently replayed selected row and lineage.
    """

    if not raw_source_body or not observation_id.strip():
        raise ValueError("scoped_occurrence_replay_input_missing")
    raw_sha256 = "sha256:" + hashlib.sha256(raw_source_body).hexdigest()
    expected_measurement_hash = (
        source_selection.measured_source_body_sha256 or source_selection.source_watermark
    )
    if raw_sha256 != expected_measurement_hash:
        raise ValueError("scoped_occurrence_replay_watermark_mismatch")
    if source_selection.unit_transform == "fixed_multiplicative":
        if unit_transform_evidence is None:
            raise ValueError("scoped_occurrence_replay_transform_evidence_missing")
        if (
            unit_transform_evidence.binding_id != source_selection.binding_id
            or unit_transform_evidence.raw_unit != source_selection.raw_unit
            or unit_transform_evidence.canonical_unit != source_selection.canonical_unit
        ):
            raise ValueError("scoped_occurrence_replay_transform_binding_mismatch")
    elif unit_transform_evidence is not None:
        raise ValueError("scoped_occurrence_replay_unexpected_transform_evidence")

    try:
        payload = json.loads(raw_source_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("scoped_occurrence_replay_source_not_json") from exc
    if isinstance(payload, Mapping):
        raw_rows: tuple[Mapping[str, object], ...] = (payload,)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        if not payload or not all(isinstance(row, Mapping) for row in payload):
            raise ValueError("scoped_occurrence_replay_source_not_tabular")
        raw_rows = tuple(row for row in payload if isinstance(row, Mapping))
    else:
        raise ValueError("scoped_occurrence_replay_source_not_tabular")

    multiplier = (
        Decimal(unit_transform_evidence.multiplier)
        if unit_transform_evidence is not None
        else Decimal("1")
    )
    grouped: dict[
        tuple[str, int | None, int | None, int | None, str],
        tuple[list[float], list[str]],
    ] = {}
    for index, raw_row in enumerate(raw_rows):
        if source_selection.raw_field not in raw_row:
            raise ValueError(f"scoped_occurrence_replay_raw_field_missing:{index}")
        raw_value = raw_row[source_selection.raw_field]
        if isinstance(raw_value, bool):
            raise ValueError(f"scoped_occurrence_replay_numeric_value_invalid:{index}")
        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"scoped_occurrence_replay_numeric_value_invalid:{index}") from exc
        if not math.isfinite(numeric_value):
            raise ValueError(f"scoped_occurrence_replay_numeric_value_not_finite:{index}")
        raw_decimal = Decimal(str(numeric_value))
        if unit_transform_evidence is not None:
            numeric_value = float(multiplier * raw_decimal)
        if not math.isfinite(numeric_value):
            raise ValueError(f"scoped_occurrence_replay_canonical_value_not_finite:{index}")

        country_code = str(raw_row.get("country_code") or "unknown")
        year = _replay_optional_int(raw_row.get("year"), field="year")
        survey_year = _replay_optional_int(raw_row.get("survey_year"), field="survey_year")
        wave = _replay_optional_int(raw_row.get("wave"), field="wave")
        condition = raw_row.get("condition_json", {})
        if isinstance(condition, str):
            try:
                condition = json.loads(condition)
            except json.JSONDecodeError as exc:
                raise ValueError(f"scoped_occurrence_replay_condition_invalid:{index}") from exc
        if not isinstance(condition, Mapping):
            raise ValueError(f"scoped_occurrence_replay_condition_invalid:{index}")
        condition_payload = _apply_declared_source_condition(
            condition, source_selection.declared_source_condition
        )
        if "unit" in condition_payload:
            expected_declared_unit = (
                source_selection.raw_unit
                if unit_transform_evidence is not None
                else source_selection.canonical_unit
            )
            if condition_payload["unit"] != expected_declared_unit:
                raise ValueError(f"scoped_occurrence_condition_unit_mismatch:{index}")
        if unit_transform_evidence is not None:
            condition_payload["unit"] = source_selection.canonical_unit
        condition_json = json.dumps(
            condition_payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        key = (country_code, year, survey_year, wave, condition_json)
        values, raw_values = grouped.setdefault(key, ([], []))
        values.append(numeric_value)
        raw_values.append(format(raw_decimal, "f"))

    for key in sorted(grouped, key=lambda item: tuple(str(part) for part in item)):
        values, raw_values = grouped[key]
        if source_selection.aggregation_method == "identity":
            if len(values) != 1:
                raise ValueError("scoped_occurrence_replay_identity_not_unique")
            canonical_value = values[0]
        elif source_selection.aggregation_method == "mean":
            canonical_value = sum(values) / len(values)
        elif source_selection.aggregation_method == "sum":
            canonical_value = sum(values)
        else:
            canonical_value = values[-1]
        country_code, year, survey_year, wave, condition_json = key
        identity: dict[str, object] = {
            "epoch_id": source_selection.epoch_id,
            "dataset_id": source_selection.dataset_id,
            "raw_field": source_selection.raw_field,
            "canonical_variable": source_selection.canonical_variable,
            "country_code": country_code,
            "year": year,
            "survey_year": survey_year,
            "wave": wave,
            "condition_json": condition_json,
            "value": canonical_value,
            "raw_body_sha256": raw_sha256,
            "binding_id": source_selection.binding_id,
        }
        if unit_transform_evidence is not None:
            identity["unit_transform_evidence"] = unit_transform_evidence.model_dump(mode="json")
        row_id = "acquisition-observation:" + _catalog_content_sha256(identity)
        if row_id != observation_id:
            continue

        occurrence_payload: dict[str, object] = {
            "observation_id": row_id,
            "dataset_id": source_selection.dataset_id,
            "raw_variable": source_selection.raw_field,
            "canonical_var": source_selection.canonical_variable,
            "country_code": country_code,
            "year": year,
            "survey_year": survey_year,
            "wave": wave,
            "value": canonical_value,
            "condition_json": condition_json,
            "acquisition_method": (
                f"registered_{source_selection.unit_transform}_"
                f"{source_selection.aggregation_method}_lift"
            ),
            "source_watermark": source_selection.source_watermark,
            "dataset_version": source_selection.dataset_version,
            "observation_class": source_selection.observation_class,
        }
        if unit_transform_evidence is not None:
            occurrence_payload["unit_transform_evidence"] = unit_transform_evidence.model_dump(
                mode="json"
            )
        row_content_sha256 = _catalog_content_sha256(occurrence_payload)
        source_scope = _scope_from_occurrence_fields(
            country_code=country_code,
            year=year,
            survey_year=survey_year,
            wave=wave,
            condition_json=condition_json,
        )
        return ScopedMeasurementOccurrence(
            source_scope=source_scope,
            source_receipt_ref=source_selection.source_receipt_ref,
            source_passport_ref=source_selection.source_passport_ref,
            source_boundary_candidate_ref=source_selection.source_boundary_candidate_ref,
            source_record_ref=source_selection.source_record_ref,
            observation_id=row_id,
            observation_content_sha256=row_content_sha256,
            dataset_id=source_selection.dataset_id,
            dataset_version=source_selection.dataset_version,
            source_watermark=source_selection.source_watermark,
            raw_variable=source_selection.raw_field,
            canonical_variable=source_selection.canonical_variable,
            country_code=country_code,
            year=year,
            survey_year=survey_year,
            wave=wave,
            observation_class=source_selection.observation_class,
            condition_json=condition_json,
            acquisition_method=str(occurrence_payload["acquisition_method"]),
            raw_values=tuple(raw_values),
            aggregation_method=source_selection.aggregation_method,
            canonical_value=str(canonical_value),
            canonical_unit=source_selection.canonical_unit,
            unit_transform_evidence=unit_transform_evidence,
        )
    raise ValueError("scoped_occurrence_replay_selected_observation_missing")


def evaluate_scoped_correspondence_basis(
    *,
    basis: ScopedCorrespondenceBasis,
    occurrence_ref: ScopedMeasurementOccurrenceRef,
    occurrence: ScopedMeasurementOccurrence,
    replayed_occurrence: ScopedMeasurementOccurrence,
    source_selection: ScopedSourceSelection,
    source_definition_ref: VariableSemanticDefinitionRef,
    source_definition: VariableSemanticDefinition,
    source_representation_ref: VariableRepresentationRef,
    source_representation: VariableRepresentation,
    target_definition_ref: VariableSemanticDefinitionRef,
    target_definition: VariableSemanticDefinition,
    target_representation_ref: VariableRepresentationRef,
    target_representation: VariableRepresentation,
    binding_profile_ref: MeasurementBindingProfileRef,
    profile: MeasurementBindingProfile,
    model_interface_ref: SelectedVariableBindingRef,
    model_port: ModelInputPort,
) -> ScopedCorrespondenceEvaluation:
    """Recompute the finite same-definition relation from owner-loaded objects.

    All referenced bytes and the raw source occurrence must be reopened by the
    caller. This pure predicate contains no CAS or Catalog access and is shared
    by the source owner and Foundry consumer. The finite projection rule admits
    one unchanged provider value or an explicitly matching row aggregation;
    neither establishes the provider's upstream empirical estimand.
    """

    refusals: list[str] = []
    if source_selection.declared_source_condition:
        declared_definition = source_selection.declared_source_definition_ref
        declared_representation = source_selection.declared_source_representation_ref
        if declared_definition is None or declared_representation is None:
            refusals.append("source_declared_definition_not_established")
        else:
            if artifact_ref_identity_key(declared_definition) != artifact_ref_identity_key(
                source_definition_ref
            ):
                refusals.append("source_declared_definition_ref_mismatch")
            if artifact_ref_identity_key(declared_representation) != artifact_ref_identity_key(
                source_representation_ref
            ):
                refusals.append("source_declared_representation_ref_mismatch")
    if occurrence != replayed_occurrence:
        refusals.append("source_occurrence_raw_replay_mismatch")
    if artifact_ref_identity_key(occurrence_ref) != artifact_ref_identity_key(basis.occurrence_ref):
        refusals.append("basis_occurrence_ref_mismatch")
    if any(
        artifact_ref_identity_key(left) != artifact_ref_identity_key(right)
        for left, right in (
            (basis.source_definition_ref, source_definition_ref),
            (basis.source_representation_ref, source_representation_ref),
            (basis.target_definition_ref, target_definition_ref),
            (basis.target_representation_ref, target_representation_ref),
            (basis.binding_profile_ref, binding_profile_ref),
            (basis.model_interface_ref, model_interface_ref),
        )
    ):
        refusals.append("basis_selected_ref_mismatch")
    if basis.model_port_id != model_port.port_id:
        refusals.append("basis_model_port_identity_mismatch")
    if (
        artifact_ref_identity_key(model_port.semantic_definition_ref)
        != artifact_ref_identity_key(target_definition_ref)
        or artifact_ref_identity_key(model_port.representation_ref)
        != artifact_ref_identity_key(target_representation_ref)
        or artifact_ref_identity_key(model_port.binding_profile_ref)
        != artifact_ref_identity_key(binding_profile_ref)
        or model_port.scope != basis.scope
    ):
        refusals.append("basis_model_port_selection_mismatch")
    if (
        artifact_ref_identity_key(source_definition_ref)
        != artifact_ref_identity_key(target_definition_ref)
        or source_definition != target_definition
    ):
        refusals.append("same_definition_profile_requires_exact_definition")
    if (
        _namespaced_semantic_id(source_definition) != source_selection.canonical_variable
        or occurrence.canonical_variable != source_selection.canonical_variable
        or occurrence.raw_variable != source_selection.raw_field
        or occurrence.dataset_id != source_selection.dataset_id
        or occurrence.dataset_version != source_selection.dataset_version
        or occurrence.source_watermark != source_selection.source_watermark
        or occurrence.observation_class != source_selection.observation_class
        or artifact_ref_identity_key(occurrence.source_receipt_ref)
        != artifact_ref_identity_key(source_selection.source_receipt_ref)
        or artifact_ref_identity_key(occurrence.source_passport_ref)
        != artifact_ref_identity_key(source_selection.source_passport_ref)
        or artifact_ref_identity_key(occurrence.source_boundary_candidate_ref)
        != artifact_ref_identity_key(source_selection.source_boundary_candidate_ref)
        or artifact_ref_identity_key(occurrence.source_record_ref)
        != artifact_ref_identity_key(source_selection.source_record_ref)
    ):
        refusals.append("source_owner_mapping_occurrence_mismatch")
    if (
        source_representation.semantic_definition_ref != source_definition_ref
        or target_representation.semantic_definition_ref != target_definition_ref
        or source_definition_ref != target_definition_ref
    ):
        refusals.append("representation_definition_ref_mismatch")
    if (
        tuple(basis.source_definition_evidence_refs)
        != tuple(source_definition.definition_evidence_refs)
        or not source_definition.definition_evidence_refs
    ):
        refusals.append("source_definition_evidence_ref_mismatch")
    if occurrence.source_scope != basis.scope:
        refusals.append("source_occurrence_scope_mismatch")
    for representation, scope, refusal_code in (
        (
            source_representation,
            occurrence.source_scope,
            "source_representation_population_scope_mismatch",
        ),
        (
            target_representation,
            model_port.scope,
            "target_representation_population_scope_mismatch",
        ),
    ):
        if (
            representation.population_ref is not None
            and representation.population_ref != scope.population_ref
        ):
            refusals.append(refusal_code)
    # Identity reads one already-produced value. Its provider may describe that
    # value as a mean, total, or another estimand; passthrough does not recompute
    # that upstream operation. A performed row aggregation needs the matching
    # declared operation in this bounded profile. Different compositions need
    # their own typed rule, not an alias or a replacement numerical value.
    if occurrence.aggregation_method == "identity":
        if len(occurrence.raw_values) != 1:
            refusals.append("source_occurrence_identity_not_unique")
    elif source_representation.aggregation != occurrence.aggregation_method:
        refusals.append("source_occurrence_aggregation_not_established")
    if (
        source_representation.unit_id != occurrence.canonical_unit
        or source_representation.unit_id != source_selection.canonical_unit
        or target_representation.unit_id != model_port.unit_id
    ):
        refusals.append("source_or_model_unit_mismatch")
    if (
        occurrence.source_scope.period_basis != "calendar_year"
        or basis.scope.period_basis != "calendar_year"
        or model_port.scope.period_basis != "calendar_year"
    ):
        refusals.append("calendar_year_period_basis_not_established")
    if (
        occurrence.year is None
        or occurrence.survey_year is not None
        or occurrence.wave is not None
        or occurrence.source_scope.period_start != date(occurrence.year, 1, 1)
        or occurrence.source_scope.period_end != date(occurrence.year, 12, 31)
    ):
        refusals.append("calendar_year_source_scope_mismatch")
    if source_selection.is_proxy or source_selection.observation_class != "observed":
        refusals.append("source_measurement_not_exact_observed")

    compared, optional_unknown, axis_refusals = _compare_axes(
        source_representation,
        target_representation,
        profile,
    )
    refusals.extend(axis_refusals)
    if refusals:
        return ScopedCorrespondenceEvaluation(
            status="refused",
            semantic_correspondence="not_established",
            recomputed_axes=compared,
            optional_unknown_axes=optional_unknown,
            refusal_codes=tuple(dict.fromkeys(refusals)),
        )
    return ScopedCorrespondenceEvaluation(
        status="candidate",
        semantic_correspondence="recomputed",
        recomputed_axes=compared,
        optional_unknown_axes=optional_unknown,
        limitation_codes=(
            "external_empirical_origin_not_established",
            "source_currentness_not_established",
            *(
                ("optional_axis_unknown:methodology_ref",)
                if MeasurementAxis.METHODOLOGY_REF in optional_unknown
                else ()
            ),
        ),
    )


def _scope_from_occurrence_fields(
    *,
    country_code: str,
    year: int | None,
    survey_year: int | None,
    wave: int | None,
    condition_json: str,
) -> ModelInputScope:
    try:
        condition = json.loads(condition_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("scoped_occurrence_scope_condition_invalid") from exc
    unknown_keys = set(condition) - _SCOPED_CONDITION_KEYS
    if unknown_keys:
        raise ValueError("scoped_occurrence_condition_scope_unrecognized")
    population_ref = condition.get("population_ref") if isinstance(condition, Mapping) else None
    jurisdiction_ref = condition.get("jurisdiction_ref") if isinstance(condition, Mapping) else None
    time_period_basis = (
        condition.get("time_period_basis") if isinstance(condition, Mapping) else None
    )
    geography_ref = condition.get("geography_ref") if isinstance(condition, Mapping) else None
    if not isinstance(population_ref, str) or not population_ref.strip():
        raise ValueError("scoped_occurrence_population_missing")
    if not isinstance(jurisdiction_ref, str) or not jurisdiction_ref.strip():
        raise ValueError("scoped_occurrence_jurisdiction_missing")
    if time_period_basis in (None, "unknown"):
        raise ValueError("scoped_occurrence_period_basis_not_established")
    if time_period_basis != "calendar_year":
        raise ValueError("scoped_occurrence_period_basis_unsupported")
    if survey_year is not None or wave is not None:
        raise ValueError("scoped_occurrence_competing_time_coordinate_unsupported")
    if country_code == "unknown" or type(year) is not int:
        raise ValueError("scoped_occurrence_annual_scope_not_established")
    if geography_ref is None:
        geography_ref = country_code
    elif (
        not isinstance(geography_ref, str)
        or not geography_ref.strip()
        or geography_ref != geography_ref.strip()
    ):
        raise ValueError("scoped_occurrence_geography_ref_invalid")
    return ModelInputScope(
        population_ref=population_ref,
        geography_ref=geography_ref,
        jurisdiction_ref=jurisdiction_ref,
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        time_role="observation_time",
        period_basis=time_period_basis,
    )


def _replay_optional_int(value: object, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, (bool, float)):
        raise ValueError("scoped_occurrence_time_coordinate_invalid")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not value or value != value.strip():
            raise ValueError("scoped_occurrence_time_coordinate_invalid")
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError("scoped_occurrence_time_coordinate_invalid") from exc
        if str(parsed) != value:
            raise ValueError("scoped_occurrence_time_coordinate_invalid")
        return parsed
    raise ValueError(f"scoped_occurrence_time_coordinate_invalid:{field}")


def _catalog_content_sha256(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256((encoded + "\n").encode("utf-8")).hexdigest()


def _namespaced_semantic_id(value: VariableSemanticDefinition) -> str:
    return f"{value.namespace}.{value.stable_id}"


def _same_artifact_without_profile(left: ArtifactRef, right: ArtifactRef) -> bool:
    return (
        str(left.artifact_id),
        left.kind,
        left.media_type,
    ) == (
        str(right.artifact_id),
        right.kind,
        right.media_type,
    )


def _compare_axes(
    source: VariableRepresentation,
    target: VariableRepresentation,
    profile: MeasurementBindingProfile,
) -> tuple[tuple[MeasurementAxis, ...], tuple[MeasurementAxis, ...], tuple[str, ...]]:
    required = set(profile.required_axes)
    if (
        source.measure_form in {"ratio", "rate"}
        or target.measure_form in {"ratio", "rate"}
        or source.denominator_ref is not None
        or target.denominator_ref is not None
    ) and MeasurementAxis.DENOMINATOR_REF not in required:
        return (), (), ("profile_denominator_axis_not_required",)
    if (
        source.measure_form in {"ratio", "rate"}
        or target.measure_form in {"ratio", "rate"}
        or source.numerator_ref is not None
        or target.numerator_ref is not None
    ) and MeasurementAxis.NUMERATOR_REF not in required:
        return (), (), ("profile_numerator_axis_not_required",)

    compared: list[MeasurementAxis] = []
    optional_unknown: list[MeasurementAxis] = []
    refusals: list[str] = []
    for axis in profile.required_axes:
        source_value = _representation_axis_value(source, axis)
        target_value = _representation_axis_value(target, axis)
        if source_value is None or target_value is None:
            refusals.append(f"required_axis_unknown:{axis.value}")
        else:
            compared.append(axis)
            if source_value != target_value:
                refusals.append(f"required_axis_mismatch:{axis.value}")
    for axis in profile.optional_axes:
        source_value = _representation_axis_value(source, axis)
        target_value = _representation_axis_value(target, axis)
        if source_value is None or target_value is None:
            optional_unknown.append(axis)
        elif source_value != target_value:
            refusals.append(f"optional_axis_mismatch:{axis.value}")
        else:
            compared.append(axis)
    return tuple(compared), tuple(optional_unknown), tuple(refusals)


def _representation_axis_value(
    value: VariableRepresentation, axis: MeasurementAxis
) -> object | None:
    raw = getattr(value, axis.value)
    if isinstance(raw, ArtifactRef):
        return artifact_ref_identity_key(raw)
    if isinstance(raw, tuple):
        return raw or None
    return raw


__all__ = [
    "FixedUnitTransformWitness",
    "MeasurementAxis",
    "MeasurementBindingProfile",
    "MeasurementBindingProfileRef",
    "MeasurementCorrespondenceResult",
    "ModelInputScope",
    "ScopedCorrespondenceBasis",
    "ScopedCorrespondenceBasisRef",
    "ScopedCorrespondenceEvaluation",
    "ScopedMeasurementOccurrence",
    "ScopedMeasurementOccurrenceRef",
    "ScopedSourceSelection",
    "SelectedVariableBindingRef",
    "VariableRepresentation",
    "VariableRepresentationRef",
    "VariableSemanticDefinition",
    "VariableSemanticDefinitionRef",
    "evaluate_scoped_correspondence_basis",
    "load_variable_representation",
    "replay_scoped_measurement_occurrence",
    "scoped_correspondence_basis_manifest_inputs",
    "scoped_measurement_occurrence_manifest_inputs",
    "scoped_source_selection_from_passport_mapping",
    "variable_representation_manifest_inputs",
]
