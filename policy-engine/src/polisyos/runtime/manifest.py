"""Define the on-disk run manifest written by runtime entrypoints.

This schema predates the newer `core.contracts.runtime` API DTOs and remains a
stable boundary for persisted run directories, local debugging, and replay
bootstrap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.foundry import EnvironmentManifestRef


class ArtifactRef(BaseModel):
    """Reference one run-local artifact path and its logical type/media metadata."""

    artifact_type: str
    path: str | None = None
    relative_path: str | None = None
    media_type: str
    schema_version: str | None = None
    step: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    model_config = ConfigDict(extra="forbid")


class RunManifest(BaseModel):
    """Persist run lifecycle state, produced artifacts, budgets, and environment refs."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    parent_run_id: str | None = None
    status: str = "running"
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None
    generator: dict[str, str] = Field(default_factory=dict)
    budgets: dict[str, float] = Field(default_factory=dict)
    budget_usage: dict[str, float] = Field(default_factory=dict)
    pruning_reason: dict[str, Any] | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    environment_ref: EnvironmentManifestRef | None = Field(
        default=None,
        description="Reference to environment manifest captured at run start",
    )
    environment_fingerprint: str | None = Field(
        default=None,
        description="Fingerprint of critical environment factors",
    )
    run_root: str | None = None

    model_config = ConfigDict(extra="forbid")
