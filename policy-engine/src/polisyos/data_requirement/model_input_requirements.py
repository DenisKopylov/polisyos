"""Typed source-selection requirements for the selected executable model."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputObligation,
    ModelInputObligationSet,
    ModelInputPort,
    ProgramGraphInputInterface,
)

from ._impl.models import DataRequirementScope


class CompiledModelInputRequirement(BaseModel):
    """Source-selection query for an exact missing model port and declared scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1, strict=True)
    obligation_ref: ArtifactRef
    port: ModelInputPort
    scope: DataRequirementScope

    @model_validator(mode="after")
    def _selected_obligation(self) -> CompiledModelInputRequirement:
        if (
            self.obligation_ref.kind != ModelInputObligation.ARTIFACT_KIND
            or self.obligation_ref.media_type != "application/json"
            or self.obligation_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_compiler_obligation_ref_invalid")
        return self


class ModelInputCompilationReport(BaseModel):
    """Candidate-only compilation of owner-produced executable model requirements."""

    ARTIFACT_KIND: ClassVar[str] = "data_requirement.model_input_compilation"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.data_requirement.ModelInputCompilationReport"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    authority_purpose: Literal["candidate_acquisition_routing_only"] = (
        "candidate_acquisition_routing_only"
    )
    context: ModelInputContext
    interface_ref: ArtifactRef
    obligation_set_ref: ArtifactRef
    requirements: tuple[CompiledModelInputRequirement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _selected_requirements(self) -> ModelInputCompilationReport:
        if (
            self.interface_ref.kind != ProgramGraphInputInterface.ARTIFACT_KIND
            or self.interface_ref.media_type != "application/json"
            or self.interface_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_compiler_interface_ref_invalid")
        if (
            self.obligation_set_ref.kind != ModelInputObligationSet.ARTIFACT_KIND
            or self.obligation_set_ref.media_type != "application/json"
            or self.obligation_set_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_compiler_obligation_set_ref_invalid")
        if (
            len({item.requirement_id for item in self.requirements}) != len(self.requirements)
            or len({item.port.port_id for item in self.requirements}) != len(self.requirements)
            or len({artifact_ref_identity_key(item.obligation_ref) for item in self.requirements})
            != len(self.requirements)
        ):
            raise ValueError("model_input_compiler_requirement_duplicate")
        return self
