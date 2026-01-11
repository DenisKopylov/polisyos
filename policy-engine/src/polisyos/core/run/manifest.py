from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef, EnvInfo, ProducerInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None

    producer: ProducerInfo | None = None
    env: EnvInfo | None = None

    registry_bundle: ArtifactRef

    inputs: list[ArtifactRef] = Field(default_factory=list)
    outputs: list[ArtifactRef] = Field(default_factory=list)

    status: str = "running"
    errors: list[dict[str, Any]] = Field(default_factory=list)

    trace_ref: ArtifactRef | None = None
