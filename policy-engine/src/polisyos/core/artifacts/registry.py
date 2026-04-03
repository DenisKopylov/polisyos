"""Define CAS payload contracts for composed IR registry bundles."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .manifest import ArtifactRef


class RegistryBundlePayload(BaseModel):
    """Reference each registry artifact that forms one immutable bundle snapshot."""
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
    """Attach the bundle artifact reference to its decomposed registry payload."""
    model_config = ConfigDict(extra="forbid")

    bundle_ref: ArtifactRef
