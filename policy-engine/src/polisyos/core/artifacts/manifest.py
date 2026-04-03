"""Public artifacts manifest module API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..components.ids import ComponentId
from .ids import ArtifactID


def utc_now() -> datetime:
    """Utc now helper."""
    return datetime.now(timezone.utc).replace(microsecond=0)


class SchemaInfo(BaseModel):
    """Schema info data model."""
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class CanonInfo(BaseModel):
    """Canon info data model."""
    model_config = ConfigDict(extra="forbid")
    name: str = "polisyos.canon.json"
    version: str = "0.1.0"
    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False

    @classmethod
    def from_spec(cls, spec: Any) -> "CanonInfo":
        return cls(
            name=getattr(spec, "name", cls.model_fields["name"].default),
            version=getattr(spec, "version", cls.model_fields["version"].default),
            forbid_floats=getattr(
                spec, "forbid_floats", cls.model_fields["forbid_floats"].default
            ),
            forbid_nan_inf=getattr(
                spec, "forbid_nan_inf", cls.model_fields["forbid_nan_inf"].default
            ),
            sort_keys=getattr(spec, "sort_keys", cls.model_fields["sort_keys"].default),
            separators=getattr(
                spec, "separators", cls.model_fields["separators"].default
            ),
            ensure_ascii=getattr(
                spec, "ensure_ascii", cls.model_fields["ensure_ascii"].default
            ),
        )


class GitInfo(BaseModel):
    """Git info data model."""
    model_config = ConfigDict(extra="forbid")
    commit: str
    dirty: bool = False


class ProducerInfo(BaseModel):
    """Producer info data model."""
    model_config = ConfigDict(extra="forbid")
    component: ComponentId | str
    version: str
    git: GitInfo | None = None

    @field_validator("component")
    @classmethod
    def _coerce_component_id(cls, value: ComponentId | str) -> ComponentId | str:
        if isinstance(value, ComponentId):
            return value
        if isinstance(value, str):
            try:
                return ComponentId.parse(value)
            except Exception:
                return value
        raise TypeError("component must be ComponentId or str")


class EnvInfo(BaseModel):
    """Env info data model."""
    model_config = ConfigDict(extra="forbid")
    python: str
    platform: str
    deps_lock_hash: str


class WarningRecord(BaseModel):
    """Warning record data model."""
    model_config = ConfigDict(extra="forbid")
    code: str
    msg: str
    data: dict[str, Any] | None = None


class IntegrityInfo(BaseModel):
    """Integrity info data model."""
    model_config = ConfigDict(extra="forbid")
    sha256: str
    optional: dict[str, str] | None = None


class InputRef(BaseModel):
    """Input ref data model."""
    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    role: str


class ArtifactRef(BaseModel):
    """Artifact ref data model."""
    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    kind: str
    media_type: str


class ArtifactManifest(BaseModel):
    """Artifact manifest data model."""
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

    integrity: IntegrityInfo
    warnings: list[WarningRecord] = Field(default_factory=list)
