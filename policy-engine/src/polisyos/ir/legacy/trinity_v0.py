from __future__ import annotations

from typing import Any

from pydantic import Field

from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, KernelModel
from polisyos.ir.legacy.surface import (
    AdvisoryEntity,
    ConstraintSpec,
    InterventionSpec,
    ObjectiveSpec,
    TimeSemantics,
)

TRINITY_SCHEMA_VERSION = "1.0"


class SharedMetadata(KernelModel):
    """Metadata shared across all Trinity artifacts."""

    source_ir_ref: str | None = Field(
        None,
        description="CAS reference to original PolicySurfaceIR for traceability",
    )
    auxiliary_notes: list[str] = Field(default_factory=list)
    migration_version: str = Field(default="1.0")


class ProblemFrame(KernelModel):
    """
    The "What" - problem definition and success criteria.
    Immutable within an experiment context.
    """

    schema_version: str = Field(TRINITY_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")

    # Goals and KPIs
    kpis: list[ObjectiveSpec] = Field(
        default_factory=list,
        description="Key Performance Indicators (from objectives)",
    )
    constraints: list[ConstraintSpec] = Field(
        default_factory=list,
        description="Hard and soft constraints",
    )

    # Actors and context
    actors: list[AdvisoryEntity] = Field(
        default_factory=list,
        description="Stakeholders and agents involved",
    )
    problem_statement: str | None = Field(
        None,
        max_length=2000,
        description="Human-readable problem description (from narrative)",
    )

    # Categorization
    success_criteria_tags: list[str] = Field(default_factory=list)
    general_labels: list[str] = Field(
        default_factory=list,
        description="Unprefixed labels from legacy IR",
    )

    # Metadata
    metadata: SharedMetadata = Field(default_factory=SharedMetadata)


class PolicySpec(KernelModel):
    """
    The "How" - policy interventions and parameters.
    Subject to iteration and optimization.
    """

    schema_version: str = Field(TRINITY_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")

    # Interventions
    interventions: list[InterventionSpec] = Field(
        default_factory=list,
        description="Policy actions with parameters and schedules",
    )

    # Notes and labels
    implementation_notes: list[str] = Field(default_factory=list)
    policy_labels: list[str] = Field(default_factory=list)

    # Metadata
    metadata: SharedMetadata = Field(default_factory=SharedMetadata)


class ModelSpec(KernelModel):
    """
    The "Where" - world model configuration and assumptions.
    The "laboratory bench" for experiments.
    """

    schema_version: str = Field(TRINITY_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")

    # Data references
    data_snapshot_ref: str = Field(
        ...,
        pattern=ARTIFACT_ID_PATTERN,
        description="CAS reference to data snapshot",
    )
    registry_bundle_ref: str | None = Field(
        None,
        pattern=ARTIFACT_ID_PATTERN,
        description="CAS reference to mechanism/unit registries",
    )

    # Time configuration
    time_semantics: TimeSemantics | None = None

    # Notes and labels
    model_notes: list[str] = Field(default_factory=list)
    model_labels: list[str] = Field(default_factory=list)

    # Assumptions (future expansion)
    assumptions: dict[str, Any] = Field(
        default_factory=dict,
        description="Explicit model assumptions for sensitivity analysis",
    )

    # Metadata
    metadata: SharedMetadata = Field(default_factory=SharedMetadata)


class TrinityBundle(KernelModel):
    """
    Container for all three Trinity artifacts.
    Used for transport and as DecisionPacket input.
    """

    problem_frame: ProblemFrame
    policy_spec: PolicySpec
    model_spec: ModelSpec

    # Provenance
    source_schema_version: str = Field(
        default="2.0",
        description="Original PolicySurfaceIR schema version",
    )
