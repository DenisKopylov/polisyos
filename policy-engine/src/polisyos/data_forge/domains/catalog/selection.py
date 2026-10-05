"""Shared catalog-source selection and fail-closed seed expansion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
    CatalogSelectionError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class _CatalogSeedSource(Protocol):
    source_id: str
    enabled: bool
    seed_from: str | None


_CatalogSeedSourceT = TypeVar("_CatalogSeedSourceT", bound=_CatalogSeedSource)


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
        if seed_id is None:
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


__all__ = ["resolve_catalog_source_dependencies"]
