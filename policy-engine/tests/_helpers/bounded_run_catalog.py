from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest


def bind_bounded_run_api_catalog(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Give run API tests a bounded catalog for eager retrieval construction.

    The single zero-trust, unavailable fixture row exists only because the
    control service eagerly opens its retrieval catalog. It is not admitted
    source evidence and must not be used as a run profile or scientific input.
    """
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.runtime.quality import substrate_registry

    fixture_root = tmp_path / "run-api-catalog-bootstrap"
    curated_root = fixture_root / "fixture-contracts"
    curated_root.mkdir(parents=True)
    (curated_root / "data_contracts.json").write_text(
        json.dumps(
            {
                "contracts": [
                    {
                        "metric_id": "run_api_constructor_only",
                        "source_column": "unused_fixture_column",
                        "jurisdiction": "UA",
                        "granularity": "annual",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (curated_root / "source_bindings.json").write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "metric_id": "run_api_constructor_only",
                        "connector_id": "fixture.unavailable",
                        "dataset_id": "run-api-bootstrap-only-not-a-source",
                        "profile_id": "run-api-bootstrap-only",
                        "trust": 0.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    graph_root = fixture_root / "graph"
    graph = catalog_api.build_production_data_contract_catalog_graph(
        production_root=curated_root,
        graph_root=graph_root,
    )
    graph.close()
    catalog_path = graph_root / "catalog.duckdb"
    if not catalog_path.is_file():
        raise RuntimeError("bounded run API catalog builder produced no DuckDB file")

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
