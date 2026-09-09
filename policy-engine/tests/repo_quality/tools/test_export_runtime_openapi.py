"""Exercise the real OpenAPI generator's assigned output boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ops_runners.runtime import export_runtime_openapi as exporter


def test_real_openapi_export_confines_app_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep the complete live schema while confining app construction writes."""
    from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract

    output_root = tmp_path / "assigned"
    output = output_root / "runtime_api_v1.openapi.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["export_runtime_openapi", "--output", str(output)])
    assert exporter.main() == 0
    schema = json.loads(output.read_text(encoding="utf-8"))
    assert not validate_runtime_openapi_contract(schema)
    outside = sorted(
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file() and not path.is_relative_to(output_root)
    )
    assert outside == [], f"openapi_app_artifacts_escaped_assigned_output: {outside}"
    assert sorted(path.relative_to(output_root).as_posix()
                  for path in output_root.rglob("*") if path.is_file()) == [output.name]
