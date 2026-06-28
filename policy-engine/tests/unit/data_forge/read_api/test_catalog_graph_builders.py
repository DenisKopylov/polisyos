from __future__ import annotations

from pathlib import Path

from polisyos.data_forge.read_api.catalog import (
    build_production_data_contract_catalog_graph,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_DATA_ROOT = (
    REPO_ROOT
    / "production_data"
    / "canonical"
    / "local_data_20260501"
    / "policy_engine_data"
)


def test_production_data_contract_catalog_graph_searches_real_curated_contracts(
    tmp_path: Path,
) -> None:
    graph = build_production_data_contract_catalog_graph(
        production_root=PRODUCTION_DATA_ROOT,
        graph_root=tmp_path,
    )

    hits = graph.search_datasets("nominal gdp worldbank", top_k=5, explain=True)
    hit_ids = [hit.id for hit in hits]

    assert "catalog://production-data/worldbank-wdi/ny-gdp-mktp-cd" in hit_ids
    selected = graph.resolve_fetch_target(
        "catalog://production-data/worldbank-wdi/ny-gdp-mktp-cd"
    )
    assert selected is not None
    assert selected.connector_id == "worldbank.wdi"
    assert selected.request_dataset_id == "NY.GDP.MKTP.CD"
