"""Define CAS manifest/reference models that encode artifact lineage and ABI hints.

`ArtifactManifest` is the durable sidecar contract stored next to each blob in
`FileSystemCAS`. `ArtifactRef`/`InputRef` form the lineage boundary consumed by
runtime APIs, registry bundles, and governance reports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ..components.ids import ComponentId
from .ids import ArtifactID


def utc_now() -> datetime:
    """Return a UTC timestamp rounded to whole seconds for manifest defaults."""
    return datetime.now(UTC).replace(microsecond=0)


class SchemaInfo(BaseModel):
    """Identify the schema contract that describes an artifact payload."""

    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class CanonInfo(BaseModel):
    """Record the canonicalization rules used before hashing/storing JSON payloads."""

    model_config = ConfigDict(extra="forbid")
    name: str = "polisyos.canon.json"
    version: str = "0.2.0"
    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    exclude_none: bool = True
    max_depth: int = 128
    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False

    @classmethod
    def from_spec(cls, spec: Any) -> CanonInfo:
        """Build manifest canon metadata from a duck-typed canonicalization spec."""
        return cls(
            name=getattr(spec, "name", cls.model_fields["name"].default),
            version=getattr(spec, "version", cls.model_fields["version"].default),
            forbid_floats=getattr(spec, "forbid_floats", cls.model_fields["forbid_floats"].default),
            forbid_nan_inf=getattr(
                spec, "forbid_nan_inf", cls.model_fields["forbid_nan_inf"].default
            ),
            exclude_none=getattr(spec, "exclude_none", cls.model_fields["exclude_none"].default),
            max_depth=getattr(spec, "max_depth", cls.model_fields["max_depth"].default),
            sort_keys=getattr(spec, "sort_keys", cls.model_fields["sort_keys"].default),
            separators=getattr(spec, "separators", cls.model_fields["separators"].default),
            ensure_ascii=getattr(spec, "ensure_ascii", cls.model_fields["ensure_ascii"].default),
        )


class GitInfo(BaseModel):
    """Capture producer git provenance attached to a manifest."""

    model_config = ConfigDict(extra="forbid")
    commit: str
    dirty: bool = False


class ProducerInfo(BaseModel):
    """Identify the component/version that produced an artifact."""

    model_config = ConfigDict(extra="forbid")
    component: ComponentId | str
    version: str
    git: GitInfo | None = None

    @field_validator("component")
    @classmethod
    def _coerce_component_id(cls, value: ComponentId | str) -> ComponentId | str:
        """Preserve invalid legacy strings but coerce valid component IDs."""
        if isinstance(value, ComponentId):
            return value
        if isinstance(value, str):
            try:
                return ComponentId.parse(value)
            except Exception:
                return value
        raise TypeError("component must be ComponentId or str")


class EnvInfo(BaseModel):
    """Summarize the runtime environment fingerprint persisted with a manifest."""

    model_config = ConfigDict(extra="forbid")
    python: str
    platform: str
    deps_lock_hash: str


class WarningRecord(BaseModel):
    """Attach non-fatal producer/runtime warnings to an artifact manifest."""

    model_config = ConfigDict(extra="forbid")
    code: str
    msg: str
    data: dict[str, Any] | None = None


class ArtifactRetentionPolicyInfo(BaseModel):
    """Persist retention policy metadata resolved at write time."""

    model_config = ConfigDict(extra="forbid")

    scope: str
    retention_days: int = Field(ge=0)
    delete_on_expiry: bool = True


class ArtifactEncryptionPolicyInfo(BaseModel):
    """Persist at-rest encryption requirements and verification status."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "none"
    enforced: bool = False
    verified: bool = False
    key_reference: str | None = None


class ArtifactGovernanceInfo(BaseModel):
    """Persist governance metadata propagated into stored artifacts."""

    model_config = ConfigDict(extra="forbid")

    classification: str = "public"
    column_classification: dict[str, str] = Field(default_factory=dict)
    retention: ArtifactRetentionPolicyInfo | None = None
    encryption: ArtifactEncryptionPolicyInfo | None = None


class IntegrityInfo(BaseModel):
    """Persist the expected payload digest and optional extra integrity metadata."""

    model_config = ConfigDict(extra="forbid")
    sha256: str
    optional: dict[str, str] | None = None


class ArtifactTenantContextInfo(BaseModel):
    """Persist the tenant/cell context that owned an authority-bearing write."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    cell_id: str | None = None


class ArtifactSameInputClosureInfo(BaseModel):
    """Summarize the same-input closure identity carried by runtime authority."""

    model_config = ConfigDict(extra="forbid")

    closure_id: str
    status: str
    closure_sha256: str | None = None
    run_id: str
    job_id: str
    tenant_id: str
    cell_id: str | None = None
    evidence_input_refs: tuple[str, ...] = Field(default=())


class ArtifactAuthorityInfo(BaseModel):
    """Link a CAS artifact manifest to its runtime authority records."""

    model_config = ConfigDict(extra="forbid")

    authority_envelope_ref: str
    diagnostic_event_ref: str
    manifest_ref: str
    payload_sha256: str


class InputRef(BaseModel):
    """Declare one upstream artifact edge in a manifest lineage DAG."""

    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    role: str

    @field_serializer("artifact_id")
    def _serialize_artifact_id(self, value: object) -> str:
        return str(value)


class ArtifactRef(BaseModel):
    """Reference an artifact across service, registry, and governance boundaries."""

    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    kind: str
    media_type: str

    @field_serializer("artifact_id")
    def _serialize_artifact_id(self, value: object) -> str:
        return str(value)


class ArtifactManifest(BaseModel):
    """Describe one CAS object, its ABI hints, and its direct lineage inputs.

    The manifest is immutable once written next to the content-addressed blob.
    `artifact_id` must match the blob bytes, and `inputs` encodes direct
    upstream dependencies used by lineage reconstruction.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    artifact_id: ArtifactID
    kind: str
    media_type: str

    byte_size: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    artifact_schema: SchemaInfo | None = Field(default=None, alias="schema")
    canon: CanonInfo | None = None

    inputs: list[InputRef] = Field(default_factory=list)

    producer: ProducerInfo | None = None
    env: EnvInfo | None = None
    governance: ArtifactGovernanceInfo | None = None
    tenant_context: ArtifactTenantContextInfo | None = None
    same_input_closure: ArtifactSameInputClosureInfo | None = None
    authority: ArtifactAuthorityInfo | None = None

    integrity: IntegrityInfo
    warnings: list[WarningRecord] = Field(default_factory=list)

    @field_serializer("artifact_id")
    def _serialize_artifact_id(self, value: object) -> str:
        return str(value)
