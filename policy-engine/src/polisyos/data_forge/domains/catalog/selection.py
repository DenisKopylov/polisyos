"""Shared catalog-source selection and fail-closed seed expansion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, TypeVar, cast, get_args

from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
    CatalogSelectionError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class _CatalogSeedSource(Protocol):
    source_id: str
    enabled: bool
    seed_from: str | None


class _CatalogSelectableSource(_CatalogSeedSource, Protocol):
    wave: str
    execution_tier: str
    run_lane: str
    publish_blocking: bool
    allow_manual_backfill: bool


CatalogRunProfile = Literal[
    "prod_full",
    "prod_core_blocking",
    "rest_backfill",
    "catalog_refresh",
    "preflight_core",
    "observations_backfill",
]

_CATALOG_RUN_PROFILES = frozenset(get_args(CatalogRunProfile))

_CatalogSeedSourceT = TypeVar("_CatalogSeedSourceT", bound=_CatalogSeedSource)


def validate_catalog_run_profile(profile: str) -> CatalogRunProfile:
    """Validate one catalog run profile without substituting a default."""
    if profile not in _CATALOG_RUN_PROFILES:
        raise CatalogSelectionError("unsupported_run_profile", profile)
    return cast("CatalogRunProfile", profile)


def source_included_in_run_profile(
    source: _CatalogSelectableSource,
    profile: str,
) -> bool:
    """Return whether an enabled source participates in a validated run profile."""
    profile_name = validate_catalog_run_profile(profile)
    if not source.enabled:
        return False
    if profile_name == "prod_full":
        return True
    if profile_name == "prod_core_blocking":
        return source.publish_blocking
    if profile_name == "rest_backfill":
        return source.allow_manual_backfill
    if profile_name == "catalog_refresh":
        return source.run_lane in {"catalog", "enrichment"}
    if profile_name == "preflight_core":
        return source.publish_blocking and source.run_lane == "empirical"
    return source.execution_tier == "transport_ready" and source.run_lane == "empirical"


def select_catalog_sources[T: _CatalogSelectableSource](
    sources: tuple[T, ...],
    *,
    wave: str | None = None,
    run_profile: str = "prod_full",
) -> tuple[T, ...]:
    """Apply the canonical wave/profile predicate and resolve mandatory seed closure."""
    validated_profile = validate_catalog_run_profile(run_profile)
    selected = tuple(
        source
        for source in sources
        if (wave is None or source.wave.upper() == wave.upper())
        and source_included_in_run_profile(source, validated_profile)
    )
    return resolve_catalog_source_dependencies(sources, selected)


def resolve_catalog_source_dependencies(
    modules: tuple[_CatalogSeedSourceT, ...],
    selected: Sequence[_CatalogSeedSourceT],
) -> tuple[_CatalogSeedSourceT, ...]:
    """Expand selected sources through enabled, present, acyclic seed sources.

    The input order is retained in the result. A required seed that cannot be
    resolved raises the catalog's typed selection error instead of silently
    dropping the dependent source.
    """
    selected_ids = {module.source_id for module in selected}
    by_id = {module.source_id: module for module in modules}

    def resolve_seed(module: _CatalogSeedSourceT, path: tuple[str, ...]) -> None:
        seed_id = module.seed_from
        if seed_id is None or seed_id == "":
            return
        if seed_id in path:
            cycle = " -> ".join((*path, seed_id))
            raise CatalogSelectionError("dependency_cycle", cycle)
        seed_module = by_id.get(seed_id)
        if seed_module is None:
            raise CatalogSelectionError(
                "dependency_missing",
                f"source={module.source_id}/seed={seed_id}",
            )
        if not seed_module.enabled:
            raise CatalogSelectionError(
                "dependency_disabled",
                f"source={module.source_id}/seed={seed_id}",
            )
        selected_ids.add(seed_module.source_id)
        resolve_seed(seed_module, (*path, seed_id))

    for module in selected:
        resolve_seed(module, (module.source_id,))
    return tuple(module for module in modules if module.source_id in selected_ids)


__all__ = [
    "CatalogRunProfile",
    "resolve_catalog_source_dependencies",
    "select_catalog_sources",
    "source_included_in_run_profile",
    "validate_catalog_run_profile",
]
