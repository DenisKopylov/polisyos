"""Small helpers for static catalog source-module declarations."""

from __future__ import annotations

from polisyos.data_forge.domains.catalog.source_modules import (
    CatalogExecutionTier,
    CatalogHistoryPolicy,
    CatalogRunLane,
    CatalogSourceModuleSpec,
)


def source(
    source_id: str,
    *,
    family: str,
    wave: str,
    endpoint: str,
    connector_id: str,
    profile_id: str = "",
    execution_tier: CatalogExecutionTier = "catalog",
    run_lane: CatalogRunLane | None = None,
    publish_blocking: bool = False,
    update_frequency: str = "",
    metrics_required: bool = False,
    seed_from: str | None = None,
    require_curated_resources: bool = False,
    history_policy: CatalogHistoryPolicy = "full_snapshot",
    allow_manual_backfill: bool = False,
    default_lookback_days: int | None = None,
    max_rows_per_snapshot: int | None = None,
    max_bytes_per_snapshot: int | None = None,
    enabled: bool = True,
) -> CatalogSourceModuleSpec:
    """Build a static source-module spec with legacy registry defaults."""
    normalized_lane = run_lane or ("catalog" if execution_tier == "catalog" else "empirical")
    return CatalogSourceModuleSpec(
        source_id=source_id,
        family=family,
        wave=wave,
        connector_id=connector_id,
        profile_id=profile_id,
        endpoint=endpoint,
        enabled=enabled,
        execution_tier=execution_tier,
        run_lane=normalized_lane,
        publish_blocking=publish_blocking,
        update_frequency=update_frequency,
        metrics_required=metrics_required,
        seed_from=seed_from,
        require_curated_resources=require_curated_resources,
        history_policy=history_policy,
        allow_manual_backfill=allow_manual_backfill,
        default_lookback_days=default_lookback_days,
        max_rows_per_snapshot=max_rows_per_snapshot,
        max_bytes_per_snapshot=max_bytes_per_snapshot,
    )


__all__ = ["source"]
