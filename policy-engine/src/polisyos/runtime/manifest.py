"""Define the on-disk run manifest written by runtime entrypoints.

This schema predates the newer `core.contracts.runtime` API DTOs and remains a
stable boundary for persisted run directories, local debugging, and replay
bootstrap.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.foundry import EnvironmentManifestRef


class ArtifactRef(BaseModel):
    """Reference one run-local artifact path and its logical type/media metadata."""
    artifact_type: str
    path: Optional[str] = None
    relative_path: Optional[str] = None
    media_type: str
    schema_version: Optional[str] = None
    step: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(extra="forbid")


class RunManifest(BaseModel):
    """Persist run lifecycle state, produced artifacts, budgets, and environment refs."""
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    parent_run_id: Optional[str] = None
    status: str = "running"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None
    generator: Dict[str, str] = Field(default_factory=dict)
    budgets: Dict[str, float] = Field(default_factory=dict)
    budget_usage: Dict[str, float] = Field(default_factory=dict)
    pruning_reason: Optional[Dict[str, Any]] = None
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    environment_ref: EnvironmentManifestRef | None = Field(
        default=None,
        description="Reference to environment manifest captured at run start",
    )
    environment_fingerprint: str | None = Field(
        default=None,
        description="Fingerprint of critical environment factors",
    )
    run_root: Optional[str] = None

    model_config = ConfigDict(extra="forbid")
