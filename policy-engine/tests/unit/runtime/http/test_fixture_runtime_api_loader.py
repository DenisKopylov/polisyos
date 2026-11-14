from __future__ import annotations

import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
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


def test_fixture_server_lifespan_closes_resources_before_fallback_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run Runtime shutdown before fixture cleanup and tolerate ExitStack fallback."""
    import asyncio
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    module = _load_fixture_server_module()
    events: list[str] = []

    @asynccontextmanager
    async def runtime_lifespan(_app: FastAPI):
        events.append("runtime_startup")
        try:
            yield
        finally:
            events.append("runtime_shutdown")

    app = FastAPI(lifespan=runtime_lifespan)
    patched_owner = type("FixturePatchTarget", (), {"value": "original"})()
    fixture_monkeypatch = pytest.MonkeyPatch()
    fixture_monkeypatch.setattr(patched_owner, "value", "fixture")
    env: dict[str, object] = {"_dashboard_fixture_monkeypatch": fixture_monkeypatch}

    close_fixture_env = module._close_dashboard_fixture_env

    def record_fixture_close(environment: dict[str, object]) -> None:
        events.append("fixture_close")
        close_fixture_env(environment)

    monkeypatch.setattr(module, "_close_dashboard_fixture_env", record_fixture_close)
    module._install_dashboard_fixture_lifespan_cleanup(app, env)

    async def exercise_lifespan() -> None:
        async with app.router.lifespan_context(app):
            events.append("runtime_active")

    asyncio.run(exercise_lifespan())
    assert events == ["runtime_startup", "runtime_active", "runtime_shutdown", "fixture_close"]
    assert patched_owner.value == "original"
    assert env["_runtime_api_env_closed"] is True
    assert "_dashboard_fixture_monkeypatch" not in env

    # ExitStack retains the fallback callback; its second close is harmless.
    module._close_dashboard_fixture_env(env)
    assert events[-1] == "fixture_close"
    assert patched_owner.value == "original"
    assert env["_runtime_api_env_closed"] is True


def test_fixture_runtime_api_script_serves_health_and_catalog_reads(tmp_path: Path) -> None:
    """Start the actual fixture server and read through its selected local Catalog."""
    script_path = (
        Path(__file__).resolve().parents[4]
        / "apps"
        / "runtime-dashboard"
        / "scripts"
        / "serve_fixture_runtime_api.py"
    )
    if not hasattr(signal, "SIGUSR1"):
        pytest.skip("the fixture origin checkpoint uses POSIX SIGUSR1")
    policy_engine_root = script_path.parents[3]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    metadata_path = tmp_path / "fixture-runtime.json"
    origin_capture_dir = tmp_path / "runtime-origin-capture"
    origin_capture_dir.mkdir()
    (origin_capture_dir / "sitecustomize.py").write_text(
        """\
import json, os, signal, sys

def _write_origins(_signum, _frame):
    path = os.environ.get("POLISYOS_TEST_RUNTIME_ORIGIN_OUTPUT")
    if not path:
        return
    prefixes = ("polisyos.", "tests.", "_helpers.", "tools.")
    rows = []
    for name, module in sorted(sys.modules.items()):
        if name.startswith(prefixes):
            origin = getattr(module, "__file__", None)
            if origin:
                rows.append({"module": name, "origin": os.path.realpath(origin)})
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as output:
        json.dump(rows, output, sort_keys=True, separators=(",", ":"))
    os.replace(temporary_path, path)

signal.signal(signal.SIGUSR1, _write_origins)
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path)
    origin_path = Path(
        env.get("POLISYOS_TEST_RUNTIME_ORIGIN_OUTPUT", str(tmp_path / "runtime-origins.json"))
    )
    env["POLISYOS_TEST_RUNTIME_ORIGIN_OUTPUT"] = str(origin_path)
    inherited_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(origin_capture_dir),
            str(policy_engine_root / "src"),
            str(policy_engine_root),
            str(policy_engine_root / "tests"),
            *([inherited_pythonpath] if inherited_pythonpath else []),
        ]
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(script_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--metadata-file",
            str(metadata_path),
        ],
        cwd=policy_engine_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def get_json(path: str) -> tuple[int, dict[str, object]]:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as response:
            return response.status, json.loads(response.read())

    try:
        deadline = time.monotonic() + 120
        health: tuple[int, dict[str, object]] | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.communicate(timeout=5)[0]
                pytest.fail(f"fixture server exited before health became ready:\n{output[-6000:]}")
            try:
                health = get_json("/health")
                break
            except urllib.error.HTTPError as error:
                pytest.fail(f"fixture server health request failed: {error.code} {error.read()!r}")
            except (OSError, urllib.error.URLError):
                time.sleep(0.5)
        assert health is not None, "fixture server did not become healthy within 120 seconds"
        assert health[0] == 200 and health[1]["status"] == "ok"

        status, catalog = get_json(
            "/api/v1/control/data/catalog/search?metric=us.macro&limit=5"
        )
        assert status == 200
        assert catalog["request"]["resource_kinds"] == ["dataset"]
        assert catalog["request"]["search"]["query_text"] == "us.macro"
        assert catalog["frontier"]["completeness_status"] == "producer_missing"
        assert metadata_path.is_file()
        json.loads(metadata_path.read_text(encoding="utf-8"))
        process.send_signal(signal.SIGUSR1)
        origin_deadline = time.monotonic() + 5
        while not origin_path.is_file() and time.monotonic() < origin_deadline:
            if process.poll() is not None:
                break
            time.sleep(0.1)
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            output = process.communicate(timeout=15)[0]
        except subprocess.TimeoutExpired:
            process.kill()
            output = process.communicate(timeout=5)[0]
            pytest.fail(f"fixture server did not stop after SIGTERM:\n{output[-6000:]}")
        expected_signal_exit = -signal.SIGTERM if os.name == "posix" else 0
        assert process.returncode in {0, expected_signal_exit}, (
            f"fixture server exited {process.returncode}:\n{output[-6000:]}"
        )
    assert origin_path.is_file(), "fixture process did not save loaded module origins"
    origins = {row["module"]: Path(row["origin"]) for row in json.loads(origin_path.read_text())}
    for module in ("polisyos.runtime.http.app", "polisyos.data_forge.domains.catalog.knowledge.search"):
        assert module in origins, f"fixture process did not import {module}"
        assert origins[module].is_relative_to(policy_engine_root / "src")
    assert "_helpers.runtime_http" in origins
    assert origins["_helpers.runtime_http"].is_relative_to(policy_engine_root / "tests")
