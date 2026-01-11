from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .manifest import ArtifactRef


class RegistryBundlePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_registry: ArtifactRef
    merge_registry: ArtifactRef
    constraint_registry: ArtifactRef
    selector_field_registry: ArtifactRef | None = None
    metric_registry: ArtifactRef | None = None
    mechanism_registry: ArtifactRef
    trust_registry: ArtifactRef | None = None
    units_registry: ArtifactRef | None = None


class RegistryBundle(RegistryBundlePayload):
    model_config = ConfigDict(extra="forbid")

    bundle_ref: ArtifactRef
