"""Resolve SourceProfile -> ConnectionConfig for connector use."""

from __future__ import annotations

from polisyos.fabric.connectors.base import ConnectionConfig

from .models import SourceExecutionPolicy, SourceProfile


def resolve_connection_config(profile: SourceProfile) -> ConnectionConfig:
    """Convert a SourceProfile to a ConnectionConfig usable by connectors."""
    return ConnectionConfig(
        url=profile.base_url,
        headers=dict(profile.headers),
        auth_method=profile.auth_policy if profile.auth_policy != "none" else None,
        timeout_seconds=profile.timeout_seconds,
        max_retries=profile.max_retries,
        rate_limit_rps=profile.rate_limit_rps,
    )


def resolve_execution_policy(profile: SourceProfile) -> SourceExecutionPolicy:
    """Convert a SourceProfile to a normalized execution policy."""
    return SourceExecutionPolicy(
        profile_id=profile.profile_id,
        max_concurrency=max(1, int(profile.max_concurrency or 1)),
        requests_per_hour=(
            int(profile.requests_per_hour)
            if profile.requests_per_hour is not None
            else None
        ),
        supports_async_large_responses=bool(profile.supports_async_large_responses),
        schema_preflight=bool(profile.schema_preflight),
        preferred_transport=str(profile.preferred_transport or "default"),
        supports_content_constraints=bool(profile.supports_content_constraints),
        supports_availability_constraints=bool(profile.supports_availability_constraints),
        supports_async_fetch=bool(profile.supports_async_fetch),
        max_sync_cells=(
            int(profile.max_sync_cells)
            if profile.max_sync_cells is not None
            else None
        ),
        max_async_cells=(
            int(profile.max_async_cells)
            if profile.max_async_cells is not None
            else None
        ),
        capability_cache_ttl_hours=max(1, int(profile.capability_cache_ttl_hours or 24)),
        negative_cache_ttl_hours=max(1, int(profile.negative_cache_ttl_hours or 24)),
    )


__all__ = ["resolve_connection_config", "resolve_execution_policy"]
