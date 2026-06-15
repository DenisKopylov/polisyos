"""Shared resolved-reference contract for runtime-quality dereferencing."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

RESOLVED_REF_CONTRACT_SCHEMA_VERSION = "policyos.core.contracts.resolved_ref.v1"


class ResolvedRef(BaseModel):
    """Dereferenced cross-slice reference with replay and authority metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str = Field(min_length=1)
    exists: bool
    artifact_path: str | None = None
    json_pointer: str | None = None
    content_hash: str | None = None
    producer_ref: str | None = None
    producer_type: str | None = None
    producer_root_refs: tuple[str, ...] = Field(default=())
    produced_at: str | None = None
    schema_version: str | None = None
    rule_version: str | None = None
    authority_boundary: dict[str, Any] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = Field(default=())
