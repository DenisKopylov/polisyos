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
    max_concurrency: int | None = None
    requests_per_hour: int | None = None
    supports_async_large_responses: bool = False
    schema_preflight: bool = False
    preferred_transport: str = "default"
    supports_content_constraints: bool = False
    supports_availability_constraints: bool = False
    supports_async_fetch: bool = False
    max_sync_cells: int | None = None
    max_async_cells: int | None = None
    capability_cache_ttl_hours: int | None = None
    negative_cache_ttl_hours: int | None = None
    dataset_discovery_hints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_organization: str = ""
    source_url: str = ""
    estimated_datasets: int | None = None


class SourceExecutionPolicy(BaseModel):
    """Normalized runtime execution policy derived from a source profile."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    max_concurrency: int = 1
    requests_per_hour: int | None = None
    supports_async_large_responses: bool = False
    schema_preflight: bool = False
    preferred_transport: str = "default"
    supports_content_constraints: bool = False
    supports_availability_constraints: bool = False
    supports_async_fetch: bool = False
    max_sync_cells: int | None = None
    max_async_cells: int | None = None
    capability_cache_ttl_hours: int = 24
    negative_cache_ttl_hours: int = 24


__all__ = ["AuthPolicy", "SourceExecutionPolicy", "SourceProfile"]
