from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import (
    RuntimeContainerConfig,
    RuntimeServiceContainer,
    resolve_control_service,
)
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.quality.substrate_registry import DEFAULT_L1_DCAT_PATH


def test_runtime_source_root_is_bound_through_container_startup(tmp_path: Path) -> None:
    """Bind one explicit source root through app composition and service startup."""
    cas_root = tmp_path / "runtime-cas"
    core_runs_root = tmp_path / "runtime-runs"
    source_root = tmp_path / "selected-source"
    source_root.mkdir()
    fixture_catalog_root = tmp_path / "fixture-catalog"
    fixture_catalog = catalog_api.build_slice0_fixture_catalog_graph(fixture_catalog_root)
    fixture_catalog.close()
    selected_catalog_path = source_root / DEFAULT_L1_DCAT_PATH
    selected_catalog_path.parent.mkdir(parents=True)
    (fixture_catalog_root / "catalog.duckdb").replace(selected_catalog_path)

    config_values = {
        "cas_root": cas_root,
        "core_runs_root": core_runs_root,
    }
    assert RuntimeContainerConfig(**config_values).repo_root is None
    configured = RuntimeContainerConfig(**config_values, repo_root=source_root)
    assert configured.repo_root == source_root.resolve(strict=True)

    with pytest.raises(TypeError, match="runtime_source_repo_root_must_be_path"):
        RuntimeContainerConfig(**config_values, repo_root=str(source_root))
    with pytest.raises(ValueError, match="runtime_source_repo_root_must_be_absolute"):
        RuntimeContainerConfig(**config_values, repo_root=Path("relative-source-root"))
    with pytest.raises(ValueError, match="runtime_source_repo_root_invalid"):
        RuntimeContainerConfig(**config_values, repo_root=tmp_path / "missing-source")

    app = create_runtime_api_app(
        cas_root=cas_root,
        core_runs_root=core_runs_root,
        repo_root=source_root,
    )
    container = cast("RuntimeServiceContainer", app.state.runtime_container)
    assert container.config.repo_root == source_root.resolve(strict=True)
    assert container.config.cas_root == cas_root
    assert container.config.core_runs_root == core_runs_root
    assert selected_catalog_path.is_file()

    with TestClient(app) as client:
        service = resolve_control_service(client.app)
        assert isinstance(service, ControlPlaneService)
        assert service._repo_root == source_root.resolve(strict=True)  # noqa: SLF001
        assert service._catalog_serving_source.repo_root == source_root.resolve(strict=True)  # noqa: SLF001
        assert service._catalog_serving_source.database_path == selected_catalog_path  # noqa: SLF001
        assert service._cas_root == cas_root  # noqa: SLF001
        assert service._core_runs_root == core_runs_root  # noqa: SLF001
        assert client.get("/health").status_code == 200

    with pytest.raises(ValueError, match="runtime_source_repo_root_invalid"):
        create_runtime_api_app(
            cas_root=tmp_path / "bad-cas",
            core_runs_root=tmp_path / "bad-runs",
            repo_root=tmp_path / "missing-app-source",
        )
