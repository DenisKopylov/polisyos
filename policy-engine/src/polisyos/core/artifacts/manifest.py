from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .ids import ArtifactID


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class SchemaInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class CanonInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "polisyos.canon.json"
    version: str = "0.1.0"


class GitInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commit: str
    dirty: bool = False


class ProducerInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component: str
    version: str
    git: GitInfo | None = None


class EnvInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    python: str
    platform: str
    deps_lock_hash: str


class WarningRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    msg: str
    data: dict[str, Any] | None = None


class IntegrityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: str
    optional: dict[str, str] | None = None


class InputRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    role: str


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    kind: str
    media_type: str


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: ArtifactID
    kind: str
    media_type: str

    byte_size: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    schema: SchemaInfo | None = None
    canon: CanonInfo | None = None

    inputs: list[InputRef] = Field(default_factory=list)

    producer: ProducerInfo | None = None
    env: EnvInfo | None = None

    integrity: IntegrityInfo
    warnings: list[WarningRecord] = Field(default_factory=list)
