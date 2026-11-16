"""Exact candidate input selections consumed by the Foundry binding owner."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    InputRef,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactManifest, SchemaInfo
from polisyos.core.artifacts.store import PutOptions

from .entity_axis import SelectedEntityVectorSourceDescriptor
from .model_input_period_steps import ModelInputStepScope
from .semantic_derived_binding import DerivedInputCorrespondenceRef, DerivedInputProfileRef
from .variable_binding import (
    EntityVectorCorrespondenceBasisRef,
    ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrenceRef,
    SelectedEntityVectorSourceMeaningRef,
    SelectedVariableBindingRef,
)

RESOLVED_INPUT_BINDING_MANIFEST_ROLE = "input.resolved_binding_manifest_ref"
DERIVED_MODEL_INPUT_PAYLOAD_KIND = "runtime.quality.derived_semantic_input_payload"


class ResolvedInputBindingManifestRef(SelectedVariableBindingRef):
    """Exact CAS view of a resolved candidate input selection."""

    kind: Literal["foundry.resolved_input_binding_manifest"] = (
        "foundry.resolved_input_binding_manifest"
    )
    media_type: Literal["application/json"] = "application/json"


class ResolvedMeasurementInput(BaseModel):
    """Selected obligation, occurrence, proof and exact snapshot path for one rule."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding_id: str = Field(pattern=r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$")
    model_input_obligation_ref: SelectedVariableBindingRef
    selected_occurrence_ref: ScopedMeasurementOccurrenceRef
    correspondence_ref: ScopedCorrespondenceBasisRef
    source_path: str = Field(min_length=1, max_length=512)

    @field_validator("source_path")
    @classmethod
    def _require_exact_source_path(cls, path: str) -> str:
        if any(not part or part != part.strip() for part in path.split(".")):
            raise ValueError("resolved_input_binding_source_path_invalid")
        return path

    @model_validator(mode="after")
    def _require_selected_json_inputs(self) -> ResolvedMeasurementInput:
        if self.model_input_obligation_ref.kind != "runtime.quality.model_input_obligation":
            raise ValueError("resolved_input_binding_obligation_kind_mismatch")
        if self.model_input_obligation_ref.media_type != "application/json":
            raise ValueError("resolved_input_binding_requires_selected_json_inputs")
        return self

    def payload_occurrence_role(self) -> str:
        """Identify the source path derived from this exact occurrence."""
        return f"binding.{self.binding_id}.occurrence:{self.source_path}"


class ResolvedDerivedInput(BaseModel):
    """An explicit derived output selection, never an acquired observation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding_id: str = Field(pattern=r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$")
    model_input_obligation_ref: SelectedVariableBindingRef
    model_interface_ref: SelectedVariableBindingRef
    model_port_id: str = Field(min_length=1, max_length=512)
    recipe_ref: SelectedVariableBindingRef
    certificate_ref: SelectedVariableBindingRef
    output_ref: SelectedVariableBindingRef
    year: int = Field(ge=1900, le=2200, strict=True)
    correspondence_ref: DerivedInputCorrespondenceRef
    profile_ref: DerivedInputProfileRef
    source_path: str = Field(min_length=1, max_length=512)
    derivation_bundle_ref: SelectedVariableBindingRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @field_validator("source_path")
    @classmethod
    def _require_exact_source_path(cls, path: str) -> str:
        if any(not part or part != part.strip() for part in path.split(".")):
            raise ValueError("resolved_input_binding_source_path_invalid")
        return path

    @model_validator(mode="after")
    def _require_selected_derived_inputs(self) -> ResolvedDerivedInput:
        for ref, kind in (
            (self.model_input_obligation_ref, "runtime.quality.model_input_obligation"),
            (self.model_interface_ref, "runtime.quality.program_graph_input_interface"),
            (self.recipe_ref, "polisyos.runtime.derivation_recipe"),
            (self.certificate_ref, "polisyos.runtime.derivation_certificate"),
            (self.output_ref, "polisyos.runtime.derived_economic_series"),
        ):
            if ref.kind != kind or ref.media_type != "application/json":
                raise ValueError("resolved_derived_input_kind_mismatch")
        if self.derivation_bundle_ref is not None and (
            self.derivation_bundle_ref.kind != "runtime.quality.n7_derivation_bundle"
            or self.derivation_bundle_ref.media_type != "application/json"
        ):
            raise ValueError("resolved_derived_input_bundle_kind_mismatch")
        return self

    def payload_output_role(self) -> str:
        """Identify the physical source path derived from this exact output."""
        return f"binding.{self.binding_id}.derived_output:{self.source_path}"

    def lineage_refs(self) -> tuple[tuple[SelectedVariableBindingRef, str], ...]:
        """Return exact references with their established binding-qualified roles."""
        refs = (
            ("obligation", self.model_input_obligation_ref),
            ("interface", self.model_interface_ref),
            ("recipe", self.recipe_ref),
            ("certificate", self.certificate_ref),
            ("output", self.output_ref),
            ("correspondence", self.correspondence_ref),
            ("profile", self.profile_ref),
        )
        selected = tuple((ref, f"binding.{self.binding_id}.{role}") for role, ref in refs)
        if self.derivation_bundle_ref is not None:
            selected += ((self.derivation_bundle_ref, f"binding.{self.binding_id}.n7_bundle"),)
        return selected

    def lineage_inputs(self) -> list[InputRef]:
        """Return complete role-qualified arithmetic and semantic selections."""
        return [input_ref_from_artifact_ref(ref, role=role) for ref, role in self.lineage_refs()]


class ResolvedDerivedInputAtStep(BaseModel):
    """An exact derived selection for one model-port read at one absolute step.

    The wrapper does not change the model port's immutable scope envelope.
    Core's selected-model resolver separately reopens the original obligation
    set and recomputes the exact scope before this row can count as supplied.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    step_scope: ModelInputStepScope
    selection: ResolvedDerivedInput

    @model_validator(mode="after")
    def _exact_selected_coordinate(self) -> ResolvedDerivedInputAtStep:
        if (
            self.selection.model_port_id != self.step_scope.port_id
            or self.selection.year != self.step_scope.scope.period_start.year
            or self.selection.year != self.step_scope.scope.period_end.year
        ):
            raise ValueError("resolved_step_input_coordinate_mismatch")
        return self

    def lineage_refs(self) -> tuple[tuple[SelectedVariableBindingRef, str], ...]:
        """Reuse the selected derivation's complete exact dependency references."""
        return self.selection.lineage_refs()

    def lineage_inputs(self) -> list[InputRef]:
        """Reuse the selected derivation's complete binding-qualified edges."""
        return self.selection.lineage_inputs()


class ResolvedEntityVectorInput(BaseModel):
    """Direct candidate vector selection, never a scalar or no-op derivation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    binding_id: str = Field(pattern=r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$")
    model_input_obligation_ref: SelectedVariableBindingRef
    model_interface_ref: SelectedVariableBindingRef
    model_port_id: str = Field(min_length=1, max_length=512)
    entity_axis_ref: SelectedVariableBindingRef
    source_descriptor: SelectedEntityVectorSourceDescriptor
    source_meaning_ref: SelectedEntityVectorSourceMeaningRef
    correspondence_ref: EntityVectorCorrespondenceBasisRef

    @model_validator(mode="after")
    def _selected_direct_vector_refs(self) -> ResolvedEntityVectorInput:
        for ref, kind in (
            (self.model_input_obligation_ref, "runtime.quality.model_input_obligation"),
            (self.model_interface_ref, "runtime.quality.program_graph_input_interface"),
            (self.entity_axis_ref, "foundry.selected_entity_axis"),
        ):
            if ref.kind != kind or ref.media_type != "application/json":
                raise ValueError("resolved_entity_vector_input_kind_mismatch")
        if self.model_port_id != self.model_port_id.strip():
            raise ValueError("resolved_entity_vector_input_port_invalid")
        return self

    def lineage_refs(self) -> tuple[tuple[ArtifactRef, str], ...]:
        """Return exact direct source and model-subject references."""
        return tuple(
            (ref, f"binding.{self.binding_id}.{role}")
            for ref, role in (
                (self.model_input_obligation_ref, "obligation"),
                (self.model_interface_ref, "interface"),
                (self.entity_axis_ref, "axis"),
                (self.source_descriptor.source_view_ref, "source_view"),
                (self.source_meaning_ref, "source_meaning"),
                (self.correspondence_ref, "correspondence"),
            )
        )

    def lineage_inputs(self) -> list[InputRef]:
        """Return the complete binding-qualified direct dependency inventory."""
        return [input_ref_from_artifact_ref(ref, role=role) for ref, role in self.lineage_refs()]


class ResolvedEntityVectorInputAtStep(BaseModel):
    """Direct vector selection for one independently resolved model step."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    step_scope: ModelInputStepScope
    selection: ResolvedEntityVectorInput

    @model_validator(mode="after")
    def _selected_port_matches_step(self) -> ResolvedEntityVectorInputAtStep:
        if self.selection.model_port_id != self.step_scope.port_id:
            raise ValueError("resolved_entity_vector_step_coordinate_mismatch")
        return self

    def lineage_refs(self) -> tuple[tuple[ArtifactRef, str], ...]:
        """Return the direct vector's exact model and source dependencies."""
        return self.selection.lineage_refs()

    def lineage_inputs(self) -> list[InputRef]:
        """Return the direct vector's complete role-qualified edges."""
        return self.selection.lineage_inputs()


class ResolvedInputBindingManifest(BaseModel):
    """The selected measurement inputs and explicit retained predecessor rules.

    The listed refs identify what must be independently reopened and replayed.
    The manifest does not establish correspondence, permission, or currentness.
    Version 3 carries step-qualified derived annual method inputs.  Direct
    measurement step transport must not be represented by a no-op derivation.
    Version 4 selects direct candidate entity vectors against the original
    predecessor snapshot as context, without a copied or derived payload.
    Mixed scalar/vector manifests are not part of that bounded profile.
    """

    ARTIFACT_KIND: ClassVar[str] = "foundry.resolved_input_binding_manifest"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.ResolvedInputBindingManifest"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "2.0", "3.0", "4.0")
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "1.0",
        "2.0": "2.0",
        "3.0": "3.0",
        "4.0": "4.0",
    }

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0", "2.0", "3.0", "4.0"] = "1.0"
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )
    data_snapshot_ref: SelectedVariableBindingRef
    model_input_obligation_set_ref: SelectedVariableBindingRef
    measurements: tuple[ResolvedMeasurementInput, ...] = Field(
        default=(), max_length=32, exclude_if=lambda value: not value
    )
    retained_binding_ids: tuple[str, ...] = Field(default=(), max_length=32)
    derivations: tuple[ResolvedDerivedInput, ...] = Field(
        default=(), max_length=32, exclude_if=lambda value: not value
    )
    method_input_steps: tuple[ResolvedDerivedInputAtStep, ...] = Field(
        default=(), max_length=32, exclude_if=lambda value: not value
    )
    entity_vector_steps: tuple[ResolvedEntityVectorInputAtStep, ...] = Field(
        default=(), max_length=32, exclude_if=lambda value: not value
    )

    @model_validator(mode="after")
    def _require_exact_unique_selections(self) -> ResolvedInputBindingManifest:
        if self.schema_version != "4.0" and (
            self.entity_vector_steps or "entity_vector_steps" in self.model_fields_set
        ):
            raise ValueError("resolved_input_binding_vector_inputs_version_mismatch")
        if self.schema_version == "1.0" and (
            not self.measurements or "derivations" in self.model_fields_set
        ):
            raise ValueError("resolved_input_binding_v1_requires_measurements_only")
        if self.schema_version == "2.0" and not self.derivations:
            raise ValueError("resolved_input_binding_v2_requires_derived_input")
        if self.schema_version == "3.0":
            if not self.method_input_steps or any(
                name in self.model_fields_set for name in ("measurements", "derivations")
            ):
                raise ValueError("resolved_input_binding_v3_requires_step_inputs_only")
            step_keys = tuple(
                (row.step_scope.port_id, row.step_scope.step) for row in self.method_input_steps
            )
            if step_keys != tuple(sorted(set(step_keys))):
                raise ValueError("resolved_input_binding_step_inventory_invalid")
            paths = tuple(row.selection.source_path for row in self.method_input_steps)
            if len(set(paths)) != len(paths):
                raise ValueError("resolved_input_binding_step_source_path_duplicate")
        elif self.method_input_steps or "method_input_steps" in self.model_fields_set:
            raise ValueError("resolved_input_binding_step_inputs_version_mismatch")
        if self.schema_version == "4.0":
            if not self.entity_vector_steps or any(
                name in self.model_fields_set
                for name in ("measurements", "derivations", "method_input_steps")
            ):
                raise ValueError("resolved_input_binding_v4_requires_vectors_only")
            step_keys = tuple(
                (row.step_scope.port_id, row.step_scope.step) for row in self.entity_vector_steps
            )
            if step_keys != tuple(sorted(set(step_keys))):
                raise ValueError("resolved_input_binding_vector_step_inventory_invalid")
        if (
            self.data_snapshot_ref.kind != "fabric.data_snapshot"
            or self.data_snapshot_ref.media_type != "application/json"
        ):
            raise ValueError("resolved_input_binding_snapshot_kind_mismatch")
        if (
            self.model_input_obligation_set_ref.kind != "runtime.quality.model_input_obligation_set"
            or self.model_input_obligation_set_ref.media_type != "application/json"
        ):
            raise ValueError("resolved_input_binding_obligation_set_kind_mismatch")
        binding_ids = (
            *self.retained_binding_ids,
            *(item.binding_id for item in (*self.measurements, *self.derivations)),
            *(row.selection.binding_id for row in self.method_input_steps),
            *(row.selection.binding_id for row in self.entity_vector_steps),
        )
        if any(not key or key != key.strip() for key in binding_ids) or len(
            set(binding_ids)
        ) != len(binding_ids):
            raise ValueError("resolved_input_binding_ids_not_unique")
        return self

    def lineage_inputs(self) -> list[InputRef]:
        """Return all expected role-qualified edges in selected order."""
        inputs = [
            input_ref_from_artifact_ref(self.data_snapshot_ref, role="selected_data_snapshot"),
            input_ref_from_artifact_ref(
                self.model_input_obligation_set_ref, role="selected_obligation_set"
            ),
        ]
        for selection in self.measurements:
            inputs.extend(
                (
                    input_ref_from_artifact_ref(
                        selection.model_input_obligation_ref,
                        role=f"binding.{selection.binding_id}.obligation",
                    ),
                    input_ref_from_artifact_ref(
                        selection.selected_occurrence_ref,
                        role=f"binding.{selection.binding_id}.occurrence",
                    ),
                    input_ref_from_artifact_ref(
                        selection.correspondence_ref,
                        role=f"binding.{selection.binding_id}.correspondence",
                    ),
                )
            )
        for selection in self.derivations:
            inputs.extend(selection.lineage_inputs())
        for row in self.method_input_steps:
            inputs.extend(row.lineage_inputs())
        for row in self.entity_vector_steps:
            inputs.extend(row.lineage_inputs())
        return inputs

    def require_lineage(self, manifest: ArtifactManifest) -> None:
        """Require the selected CAS view to carry the complete exact edge set."""
        if manifest.inputs != self.lineage_inputs():
            raise ValueError("resolved_input_binding_manifest_lineage_mismatch")


def persist_resolved_input_binding_manifest(
    store: ArtifactStore, value: ResolvedInputBindingManifest
) -> ResolvedInputBindingManifestRef:
    """Persist an explicit candidate selection with its exact lineage."""
    ref = store.put_json(
        value,
        PutOptions(
            kind=value.ARTIFACT_KIND,
            media_type=value.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=value.ARTIFACT_SCHEMA_NAME, version=value.schema_version),
            inputs=value.lineage_inputs(),
        ),
        return_selected_profile=True,
    )
    return ResolvedInputBindingManifestRef.model_validate(ref.model_dump(mode="python"))


def load_resolved_input_binding_manifest(
    store: ArtifactStore, ref: ResolvedInputBindingManifestRef
) -> ResolvedInputBindingManifest:
    """Load exact typed bytes and reconcile the manifest view's role edges."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("resolved_input_binding_manifest_profile_required")
    value = validate_core_model_json_artifact(ResolvedInputBindingManifest, store, ref)
    value.require_lineage(store.get_manifest(ref))
    if value.schema_version in {"3.0", "4.0"}:
        from .semantic_step_binding import recompute_resolved_step_input_coverage

        # A partial selection is candidate staging.  This checks exact selected
        # subjects; execution additionally requires source/NPY replay and full
        # computed coverage before reserving numerical work.
        recompute_resolved_step_input_coverage(store, value)
    return value
