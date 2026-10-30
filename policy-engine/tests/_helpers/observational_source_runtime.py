"""Authenticated selected-Catalog Runtime fixtures for candidate source regressions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection
from tests._helpers.control_worker import stop_embedded_control_worker
from tests._helpers.runtime_http import (
    build_runtime_api_env,
    build_runtime_api_env_from_fixture_seed,
    close_runtime_api_env,
)
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)
from tests.unit.runtime.quality.test_catalog_source_identity import _selected_fixture


@contextmanager
def _selected_runtime_api_env(tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Reuse the actual test-owned Catalog and its typed selected-source owner."""
    code_root, owner_root, selected = _selected_fixture(tmp_path / "catalog")
    selection = CatalogServingSourceSelection(
        snapshot_root=selected.snapshot_root,
        source_owner_root=owner_root,
        database_relative_path=selected.database_relative_path,
        catalog_run_profile="prod_full",
    )
    env = build_runtime_api_env(
        tmp_path / "api",
        include_test_client=True,
        app_kwargs={"repo_root": code_root, "catalog_source_selection": selection},
    )
    try:
        source = env["app"].state._control_service._catalog_serving_source
        assert source.selection_basis == "explicit_path_candidate_only"
        assert source.database_path == selected.database_path
        assert source.source_owner_root == owner_root.resolve()
        yield {
            **env,
            "catalog_code_root": code_root,
            "catalog_selection": selection,
            "catalog_source": selected,
        }
    finally:
        close_runtime_api_env(env)


@pytest.fixture
def selected_source_runtime_api_env(tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Expose the same real selected-Catalog fixture to the legacy HTTP cohort."""
    with _selected_runtime_api_env(tmp_path) as env:
        yield env


@pytest.fixture
def scoped_source_runtime(tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Enter the actual authenticated app and retain its selected Catalog owner."""
    with _selected_runtime_api_env(tmp_path) as env:
        client, cell, provider = _build_secure_client(
            env,
            opa_client=_AllowOPA(),
            claims_by_token={},
            repo_root=env["catalog_code_root"],
            catalog_source_selection=env["catalog_selection"],
        )
        # TestClient only runs the real container startup inside its lifespan.
        # Read the new authenticated app's service after that startup completes.
        with client:
            service = client.app.state.runtime_container.control_service
            assert service is not None
            source = service._catalog_serving_source
            assert source.database_path == env["catalog_source"].database_path
            assert source.source_owner_root == env["catalog_source"].source_owner_root
            stop_embedded_control_worker(service)
            result = {**env, "client": client, "service": service, "cell": cell.cell_id}
            for label in ("a", "b"):
                token = _fixture_bearer("source-access-" + label)
                tenant = env["tenant_" + label]
                provider.put_claim(
                    token,
                    _claims(tenant_id=tenant, cell_id=cell.cell_id, jti="source-" + label),
                )
                result["headers_" + label] = {
                    "Authorization": "Bearer " + token,
                    "X-Tenant-ID": tenant,
                }
            try:
                yield result
            finally:
                stop_embedded_control_worker(service)


@contextmanager
def reopen_selected_source_runtime_api_env(
    seed: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """Enter a fresh real container over the same persisted CAS and selected Catalog tuple."""
    code_root = seed["catalog_code_root"]
    selection = seed["catalog_selection"]
    source = seed["catalog_source"]
    if not isinstance(code_root, Path) or type(selection) is not CatalogServingSourceSelection:
        raise TypeError("selected_source_reader_requires_exact_catalog_context")
    env = build_runtime_api_env_from_fixture_seed(
        seed,
        include_test_client=True,
        app_kwargs={"repo_root": code_root, "catalog_source_selection": selection},
    )
    try:
        client = env["client"]
        with client:
            container = env["app"].state.runtime_container
            service = container.control_service
            assert service is not None
            stop_embedded_control_worker(service)
            actual_source = service.catalog_serving_source
            assert actual_source.selection_basis == "explicit_path_candidate_only"
            assert actual_source.database_path == source.database_path
            assert actual_source.source_owner_root == source.source_owner_root
            assert actual_source == seed["app"].state._control_service.catalog_serving_source
            assert container.config.repo_root == code_root
            assert container.config.catalog_source_selection == selection
            assert env["cas_root"] == seed["cas_root"]
            assert env["app"] is not seed["app"]
            assert container is not seed["app"].state.runtime_container
            assert service is not seed["app"].state._control_service
            assert service._control_store is not seed["app"].state._control_service._control_store
            assert service._artifact_store is container.runtime_api_context.store
            assert service._core_runs_root == seed["app"].state._control_service._core_runs_root
            yield env
    finally:
        close_runtime_api_env(env)
