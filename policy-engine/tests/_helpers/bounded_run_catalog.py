from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest


def bind_bounded_run_api_catalog(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Give run API tests a bounded catalog for eager retrieval construction.

    The empty epoch-zero graph exists only because the control service eagerly
    opens its retrieval catalog. It contains no source rows and cannot serve as
    admitted evidence, a run profile, or a scientific input.
    """
    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.runtime.quality import substrate_registry

    fixture_root = tmp_path / "run-api-catalog-bootstrap"
    graph_root = fixture_root / "graph"
    graph_root.mkdir(parents=True)
    catalog_path = graph_root / "catalog.duckdb"
    stats = build_graph(records=iter(()), db_path=catalog_path)
    if not catalog_path.is_file():
        raise RuntimeError("bounded run API catalog builder produced no DuckDB file")
    if any(
        (
            stats.datasets,
            stats.distributions,
            stats.metric_bindings,
            stats.schema_profiles,
            stats.entity_mappings,
            stats.alignment_hints,
        )
    ):
        raise RuntimeError("bounded run API catalog must remain empty")

    original_paths = substrate_registry.default_substrate_catalog_paths
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda repo_root: replace(
            original_paths(repo_root),
            l1_dcat_path=catalog_path,
        ),
    )
    monkeypatch.setattr(
        catalog_api,
        "default_acquisition_overlay_path",
        lambda _repo_root: fixture_root / "absent-overlay.duckdb",
    )

    empty_curated_hints = fixture_root / "empty-curated-hints"
    empty_curated_hints.mkdir()
    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(empty_curated_hints))
