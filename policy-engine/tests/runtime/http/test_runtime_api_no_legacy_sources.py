from __future__ import annotations

import json
from importlib.util import find_spec

import pytest

if find_spec("fastapi") is None:  # pragma: no cover - optional dependency guard
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.runtime.http.app import export_runtime_openapi_schema


def test_runs_endpoint_never_returns_legacy_runtime(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/runs?limit=50")
    assert response.status_code == 200
    payload = response.json()

    source_kinds = {item["source_kind"] for item in payload["runs"]}
    assert source_kinds == {"core_run"}
    assert payload["meta"]["source_kinds"] == ["core_run"]


def test_openapi_source_kind_enum_excludes_legacy_runtime() -> None:
    schema = export_runtime_openapi_schema()
    rendered = json.dumps(schema, sort_keys=True)
    assert "legacy_runtime" not in rendered
    assert "core_run" in rendered
