"""Admit pytest-owned native Catalog bytes through the real selected-source owner."""

from __future__ import annotations

from pathlib import Path

from polisyos.core.contracts import CatalogRunProfile
from polisyos.runtime.quality.substrate_registry import (
    CatalogServingSourcePaths,
    CatalogServingSourceSelection,
    resolve_catalog_serving_source,
)


def admit_fixture_catalog_source(
    *,
    repo_root: Path,
    database_path: Path,
    catalog_run_profile: CatalogRunProfile = "preflight_core",
) -> CatalogServingSourcePaths:
    """Admit the actual existing fixture path without copying bytes or identities."""

    root = repo_root.resolve(strict=True)
    relative = database_path.absolute().relative_to(repo_root.absolute())
    snapshot = root
    if database_path.parent.name == "graph" and database_path.parent.parent.name == "datasets":
        snapshot = database_path.parents[2].resolve(strict=False)
        relative = Path("datasets/graph") / database_path.name
    selection = CatalogServingSourceSelection(
        snapshot_root=snapshot,
        database_relative_path=relative,
        catalog_run_profile=catalog_run_profile,
    )
    return resolve_catalog_serving_source(
        root, selection=selection, requested_profile=catalog_run_profile
    )
