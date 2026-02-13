"""Source Profile models — reusable configurations for data source endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuthPolicy = Literal["none", "api_key", "bearer"]


class SourceProfile(BaseModel):
    """A named, reusable configuration for a specific data source endpoint."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str
    description: str = ""
    connector_family: str  # maps to connector namespace, e.g. "sdmx", "ckan"
    base_url: str
    headers: dict[str, str] = Field(default_factory=dict)
    auth_policy: AuthPolicy = "none"
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_rps: float | None = None
    dataset_discovery_hints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_organization: str = ""
    source_url: str = ""
    estimated_datasets: int | None = None


__all__ = ["AuthPolicy", "SourceProfile"]
