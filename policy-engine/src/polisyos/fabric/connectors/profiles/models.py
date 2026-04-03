"""Source Profile models — reusable configurations for data source endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuthPolicy = Literal["none", "api_key", "bearer"]


class SourceProfile(BaseModel):
    """Reusable configuration for a concrete source endpoint or portal.

    A ``SourceProfile`` combines connector-family routing with transport,
    throttling, async-fetch, and cache semantics so ingestion planners can
    treat public APIs consistently.

    Key fields:
        connector_family: Connector namespace used to resolve implementation
        max_concurrency: Maximum simultaneous requests for this source
        requests_per_hour: Coarser quota ceiling for low-rate providers
        preferred_core_transport: Preferred path for regular workloads
        preferred_backfill_transport: Preferred path for large backfills
        supports_async_fetch: Whether the source exposes async/bulk fetch
        schema_preflight: Whether metadata should be checked before fetch
        capability_cache_ttl_hours: Positive capability cache horizon
        negative_cache_ttl_hours: Hard negative cache horizon
        soft_negative_cache_ttl_hours: Soft failure retry horizon
    """

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
    preferred_core_transport: str = ""
    preferred_backfill_transport: str = ""
    bulk_download_url: str = ""
    bulk_format: str = ""
    supports_content_constraints: bool = False
    supports_availability_constraints: bool = False
    supports_async_fetch: bool = False
    fallback_on_capability_failure: str = "plan_without_capability"
    core_group_limit: int | None = None
    backfill_group_limit: int | None = None
    max_sync_cells: int | None = None
    max_async_cells: int | None = None
    capability_cache_ttl_hours: int | None = None
    negative_cache_ttl_hours: int | None = None
    soft_negative_cache_ttl_hours: int | None = None
    dataset_discovery_hints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_organization: str = ""
    source_url: str = ""
    estimated_datasets: int | None = None


class SourceExecutionPolicy(BaseModel):
    """Normalized runtime execution policy derived from a source profile.

    This frozen model strips presentation-only profile fields and keeps the
    execution knobs needed by planners, schedulers, and capability caches.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    max_concurrency: int = 1
    requests_per_hour: int | None = None
    supports_async_large_responses: bool = False
    schema_preflight: bool = False
    preferred_transport: str = "default"
    preferred_core_transport: str = "default"
    preferred_backfill_transport: str = "default"
    bulk_download_url: str = ""
    bulk_format: str = ""
    supports_content_constraints: bool = False
    supports_availability_constraints: bool = False
    supports_async_fetch: bool = False
    fallback_on_capability_failure: str = "plan_without_capability"
    core_group_limit: int | None = None
    backfill_group_limit: int | None = None
    max_sync_cells: int | None = None
    max_async_cells: int | None = None
    capability_cache_ttl_hours: int = 24
    negative_cache_ttl_hours: int = 24
    soft_negative_cache_ttl_hours: int = 24


__all__ = ["AuthPolicy", "SourceExecutionPolicy", "SourceProfile"]
