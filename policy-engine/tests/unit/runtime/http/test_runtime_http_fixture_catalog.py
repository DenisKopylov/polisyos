"""Semantic admission of the shared runtime fixture's actual selected Catalog owner."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest


def test_shared_runtime_fixture_admits_owned_catalog_before_public_read(
    runtime_api_env: dict[str, Any], tmp_path: Path
) -> None:
    """Bind real case-owned bytes to the fixture service and retain strict source refusal."""
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogReadSourceError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection

    app = runtime_api_env["app"]
    container = app.state.runtime_container
    service = container.control_service
    assert service is app.state._control_service
    selection = container.config.catalog_source_selection
    assert type(selection) is CatalogServingSourceSelection
    assert service._catalog_source_selection is selection
    assert selection.source_owner_root is not None
    owner_root = selection.source_owner_root.resolve(strict=True)
    assert owner_root.is_relative_to(tmp_path.resolve(strict=True))
    snapshot_root = selection.snapshot_root.resolve(strict=True)
    assert snapshot_root.is_relative_to(owner_root)
    source = service.catalog_serving_source
    database_path = source.database_path.resolve(strict=True)
    assert database_path.is_relative_to(snapshot_root)
    graph = service._retrieval._dataset_catalog
    assert graph.database_path.resolve(strict=True) == database_path
    identity = graph.read_source_identity[0]
    assert identity.source_path == str(database_path)
    assert identity.byte_size == database_path.stat().st_size
    assert (
        identity.content_sha256
        == "sha256:" + hashlib.sha256(database_path.read_bytes()).hexdigest()
    )
    # The fixture reuses the existing published owner and teardown resource; it
    # does not create an extra DB copy or substitute a retrieval backend.
    published = runtime_api_env["_runtime_http_catalog_fixture"]
    assert published.database_path.resolve(strict=True) == database_path
    assert published.producer_graph is not graph
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/human-decisions/review-effectiveness"
    )
    assert response.status_code == 200, response.text
    assert response.json()["run_id"] == runtime_api_env["core_run_id"]
    # A genuinely absent case-owned input still fails the unchanged real owner.
    missing = tmp_path / "unavailable-catalog.duckdb"
    assert not missing.exists()
    with pytest.raises(CatalogReadSourceError, match="catalog_read_source_unavailable"):
        DatasetCatalogGraph(missing, tmp_path / "unavailable-index")
