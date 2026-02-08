from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"


class DigestSet(BaseModel):
    """Content digest set compatible with in-toto resource descriptors."""

    model_config = ConfigDict(extra="forbid")

    sha256: str = Field(..., pattern=_SHA256_HEX_PATTERN)


class Subject(BaseModel):
    """in-toto statement subject (attested artifact)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    digest: DigestSet


class BuilderInfo(BaseModel):
    """Builder identity for SLSA provenance run details."""

    model_config = ConfigDict(extra="forbid")

    id: str = "https://polisyos.io/builders/scientist-pipeline"
    version: dict[str, str] = Field(default_factory=dict)


class BuildMetadata(BaseModel):
    """SLSA metadata for invocation timing and id."""

    model_config = ConfigDict(extra="forbid")

    invocation_id: str
    started_on: datetime
    finished_on: datetime


class ResourceDescriptor(BaseModel):
    """Input/output dependency descriptor with integrity digest."""

    model_config = ConfigDict(extra="forbid")

    uri: str
    digest: DigestSet
    name: str | None = None
    annotations: dict[str, str] = Field(default_factory=dict)


class BuildDefinition(BaseModel):
    """SLSA build definition section."""

    model_config = ConfigDict(extra="forbid")

    build_type: str = "https://polisyos.io/PolicyAnalysisPipeline/v1"
    external_parameters: dict[str, Any] = Field(default_factory=dict)
    internal_parameters: dict[str, Any] = Field(default_factory=dict)
    resolved_dependencies: list[ResourceDescriptor] = Field(default_factory=list)


class RunDetails(BaseModel):
    """SLSA run details section."""

    model_config = ConfigDict(extra="forbid")

    builder: BuilderInfo
    metadata: BuildMetadata
    byproducts: list[ResourceDescriptor] = Field(default_factory=list)


class SLSAProvenancePredicate(BaseModel):
    """SLSA Provenance v1 predicate."""

    model_config = ConfigDict(extra="forbid")

    build_definition: BuildDefinition = Field(alias="buildDefinition")
    run_details: RunDetails = Field(alias="runDetails")


class InTotoStatement(BaseModel):
    """in-toto v1 Statement with SLSA provenance predicate."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type_: Literal["https://in-toto.io/Statement/v1"] = Field(
        default="https://in-toto.io/Statement/v1",
        alias="_type",
    )
    subject: list[Subject]
    predicate_type: Literal["https://slsa.dev/provenance/v1"] = Field(
        default="https://slsa.dev/provenance/v1",
        alias="predicateType",
    )
    predicate: SLSAProvenancePredicate
