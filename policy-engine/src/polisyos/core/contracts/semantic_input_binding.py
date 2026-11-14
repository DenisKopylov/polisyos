"""Exact candidate input selections consumed by the Foundry binding owner."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import (
    ArtifactStore,
    InputRef,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactManifest, SchemaInfo
from polisyos.core.artifacts.store import PutOptions

from .semantic_derived_binding import DerivedInputCorrespondenceRef, DerivedInputProfileRef
from .variable_binding import (
    ScopedCorrespondenceBasisRef,
    ScopedMeasurementOccurrenceRef,
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

    def lineage_inputs(self) -> list[InputRef]:
        """Return complete role-qualified arithmetic and semantic selections."""
        refs = (
            ("obligation", self.model_input_obligation_ref),
            ("interface", self.model_interface_ref),
            ("recipe", self.recipe_ref),
            ("certificate", self.certificate_ref),
            ("output", self.output_ref),
            ("correspondence", self.correspondence_ref),
            ("profile", self.profile_ref),
        )
        inputs = [
            input_ref_from_artifact_ref(ref, role=f"binding.{self.binding_id}.{role}")
            for role, ref in refs
        ]
        if self.derivation_bundle_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    self.derivation_bundle_ref, role=f"binding.{self.binding_id}.n7_bundle"
                )
            )
        return inputs


class ResolvedInputBindingManifest(BaseModel):
    """The selected measurement inputs and explicit retained predecessor rules.

    The listed refs identify what must be independently reopened and replayed.
    The manifest does not establish correspondence, permission, or currentness.
    """

    ARTIFACT_KIND: ClassVar[str] = "foundry.resolved_input_binding_manifest"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.core.ResolvedInputBindingManifest"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = ("1.0", "2.0")
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "1.0",
        "2.0": "2.0",
    }

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0", "2.0"] = "1.0"
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

    @model_validator(mode="after")
    def _require_exact_unique_selections(self) -> ResolvedInputBindingManifest:
        if self.schema_version == "1.0" and (
            not self.measurements or "derivations" in self.model_fields_set
        ):
            raise ValueError("resolved_input_binding_v1_requires_measurements_only")
        if self.schema_version == "2.0" and not self.derivations:
            raise ValueError("resolved_input_binding_v2_requires_derived_input")
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
    return value
