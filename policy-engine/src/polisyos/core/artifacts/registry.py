"""Public artifacts registry module API."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .manifest import ArtifactRef


class RegistryBundlePayload(BaseModel):
    """Registry bundle payload public type."""
    model_config = ConfigDict(extra="forbid")
    slot_registry: ArtifactRef
    merge_registry: ArtifactRef
    constraint_registry: ArtifactRef
    selector_field_registry: ArtifactRef | None = None
    metric_registry: ArtifactRef | None = None
    mechanism_registry: ArtifactRef
    trust_registry: ArtifactRef | None = None
    units_registry: ArtifactRef | None = None
    predicate_registry: ArtifactRef | None = None
    privacy_registry: ArtifactRef | None = None


class RegistryBundle(RegistryBundlePayload):
    """Registry bundle data model."""
    model_config = ConfigDict(extra="forbid")

    bundle_ref: ArtifactRef
