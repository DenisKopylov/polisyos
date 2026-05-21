from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tools.ops_runners.runtime.quality_benchmark_authority import (
    BenchmarkContaminationError,
    contamination_policy_from_catalog,
)


def _load_fixture_server_module():
    script_path = (
        Path(__file__).resolve().parents[4]
        / "apps"
        / "runtime-dashboard"
        / "scripts"
        / "serve_fixture_runtime_api.py"
    )
    spec = importlib.util.spec_from_file_location("serve_fixture_runtime_api", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_runtime_api_loader_uses_canonical_runtime_http_helper() -> None:
    module = _load_fixture_server_module()

    builder = module._load_fixture_builder()

    assert builder.__module__ == "_helpers.runtime_http"
    assert builder.__name__ == "build_runtime_api_env"


def test_fixture_runtime_api_metadata_rejects_authority_hidden_tokens() -> None:
    module = _load_fixture_server_module()
    authority_policy = contamination_policy_from_catalog()
    hidden_answer = next(iter(authority_policy.hidden_answers))
    sentinel = next(iter(authority_policy.sentinel_strings))

    payload = {
        "runtime": "fixture",
        "public_panel": {
            "summary": hidden_answer,
            "notes": [f"leaked sentinel {sentinel}"],
        },
    }

    with pytest.raises(BenchmarkContaminationError):
        module._assert_dashboard_fixture_clean(payload)
