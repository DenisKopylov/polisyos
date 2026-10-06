from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def runtime_api_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[dict[str, Any]]:
    from tests._helpers import runtime_http
    from tests._helpers.bounded_run_catalog import bind_bounded_run_api_catalog

    if runtime_http.TestClient is None:
        pytest.skip("fastapi is not installed")
    bind_bounded_run_api_catalog(tmp_path=tmp_path, monkeypatch=monkeypatch)
    env = runtime_http.build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        runtime_http.close_runtime_api_env(env)


def test_runs_api_emits_only_core_run_source_kind(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/runs?limit=50")
    assert response.status_code == 200

    payload = response.json()
    assert payload["meta"]["source_kinds"] == ["core_run"]
    assert payload["page"]["total"] >= 2

    for run in payload["runs"]:
        assert run["source_kind"] == "core_run"


def test_run_details_payload_has_no_legacy_artifact_paths(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")
    assert response.status_code == 200

    payload = response.json()["run"]
    assert payload["source_kind"] == "core_run"
    assert "legacy_artifact_paths" not in payload
