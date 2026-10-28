from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from _helpers.runtime_http import *  # noqa: F403 - pytest fixture barrel

from polisyos.runtime.http.app import create_runtime_api_app


@pytest.fixture
def runtime_openapi_app(tmp_path: Path, pytestconfig: pytest.Config) -> Iterator[Any]:
    """Build the real route/DTO app without materializing data-backed services.

    Metadata tests use the same app/export owners as the registered OpenAPI
    writer. They do not start the application lifespan or create a TestClient.
    Request tests must continue to use ``runtime_api_env`` with actual sources.
    """
    pytest.importorskip("fastapi")
    app = create_runtime_api_app(
        cas_root=tmp_path / "openapi-cas",
        core_runs_root=tmp_path / "openapi-runs",
        repo_root=Path(pytestconfig.rootpath).resolve(strict=True),
        enable_security_middlewares=False,
    )
    try:
        yield app
    finally:
        asyncio.run(app.state.runtime_container.shutdown(app))
