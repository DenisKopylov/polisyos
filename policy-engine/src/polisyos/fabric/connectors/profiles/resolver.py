"""Normalize ``SourceProfile`` definitions into connector runtime and planner contracts.

Use ``resolve_connection_config`` when opening a connector session and
``resolve_execution_policy`` when planning concurrency, async transport, and capability-cache
behavior for that source profile.
"""

from __future__ import annotations

from polisyos.fabric.connectors.base import ConnectionConfig

from .models import SourceExecutionPolicy, SourceProfile


def resolve_connection_config(profile: SourceProfile) -> ConnectionConfig:
    """Convert a ``SourceProfile`` into connector connection settings.

    Keeps only base URL, headers, auth mode, timeout, retry, and rate-limit values that concrete
    connectors need at connection time. Capability hints and async/backfill preferences remain in
    ``SourceExecutionPolicy``.
    """
    return ConnectionConfig(
        url=profile.base_url,
        headers=dict(profile.headers),
        auth_method=profile.auth_policy if profile.auth_policy != "none" else None,
        timeout_seconds=profile.timeout_seconds,
        max_retries=profile.max_retries,
        rate_limit_rps=profile.rate_limit_rps,
    )


def resolve_execution_policy(profile: SourceProfile) -> SourceExecutionPolicy:
    """Normalize planner-facing execution controls from a ``SourceProfile``.

    Fills transport defaults, clamps concurrency and cache TTLs to safe positive values, and
    carries through async / capability constraints into a frozen execution policy. These limits are
    planner inputs; final retry/circuit behavior is still enforced by connector runtime resilience.
    """
    preferred_transport = str(profile.preferred_transport or "default")
    preferred_core_transport = str(
        profile.preferred_core_transport or preferred_transport or "default"
    )
    preferred_backfill_transport = str(
        profile.preferred_backfill_transport
        or preferred_core_transport
        or preferred_transport
        or "default"
    )
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
        preferred_transport=preferred_transport,
        preferred_core_transport=preferred_core_transport,
        preferred_backfill_transport=preferred_backfill_transport,
        bulk_download_url=str(profile.bulk_download_url or ""),
        bulk_format=str(profile.bulk_format or ""),
        supports_content_constraints=bool(profile.supports_content_constraints),
        supports_availability_constraints=bool(profile.supports_availability_constraints),
        supports_async_fetch=bool(profile.supports_async_fetch),
        fallback_on_capability_failure=str(
            profile.fallback_on_capability_failure or "plan_without_capability"
        ),
        core_group_limit=(
            int(profile.core_group_limit)
            if profile.core_group_limit is not None
            else None
        ),
        backfill_group_limit=(
            int(profile.backfill_group_limit)
            if profile.backfill_group_limit is not None
            else None
        ),
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
        soft_negative_cache_ttl_hours=max(
            1,
            int(
                profile.soft_negative_cache_ttl_hours
                or profile.negative_cache_ttl_hours
                or 24
            ),
        ),
    )


__all__ = ["resolve_connection_config", "resolve_execution_policy"]
