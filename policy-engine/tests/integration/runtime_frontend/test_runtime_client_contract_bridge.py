from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
_DS19_COLLABORATION_UNITS = {
    "feature-collaboration",
    "transport-rest-collaboration",
    "transport-ws-collaboration",
}


def _paths_match(caller_path: str, contract_path: str) -> bool:
    caller_segments = caller_path.strip("/").split("/")
    contract_segments = contract_path.strip("/").split("/")
    if len(caller_segments) != len(contract_segments):
        return False
    return all(
        caller == contract
        or (caller.startswith("{") and caller.endswith("}"))
        or (contract.startswith("{") and contract.endswith("}"))
        for caller, contract in zip(caller_segments, contract_segments, strict=True)
    )


def _normalize_template_path(path: str) -> str:
    return re.sub(r"\$\{[^}]+\}", "{dynamic}", path.split("?", 1)[0])


def _dashboard_runtime_transports() -> set[tuple[str, str, str]]:
    source_root = REPO_ROOT / "apps" / "runtime-dashboard" / "src"
    transports: set[tuple[str, str, str]] = set()
    client_pattern = re.compile(
        r'runtimeApiClient\.(GET|POST|PUT|PATCH|DELETE)\(\s*["`]([^"`]+)["`]'
    )
    url_pattern = re.compile(r'buildRuntimeApiUrl\(\s*["`]([^"`]+)["`]')
    raw_fetch_pattern = re.compile(
        r'fetch\(\s*(["`])(/api/v1/.+?)\1\s*(?:,\s*\{(?P<options>.*?)\})?\s*\)',
        re.DOTALL,
    )
    channel_pattern = re.compile(
        r'buildRuntime(?:Stream|WebSocket)Url\(\s*(["`])(/api/v1/.+?)\1',
        re.DOTALL,
    )
    method_pattern = re.compile(r'method:\s*["\'](GET|POST|PUT|PATCH|DELETE)["\']')

    for path in source_root.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if ".test." in path.name or ".spec." in path.name or "src/test" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for match in client_pattern.finditer(text):
            transports.add((match.group(1), _normalize_template_path(match.group(2)), relative))
        for match in url_pattern.finditer(text):
            transports.add(("GET", _normalize_template_path(match.group(1)), relative))
        for match in raw_fetch_pattern.finditer(text):
            options = match.group("options") or ""
            method_match = method_pattern.search(options)
            method = method_match.group(1) if method_match else "GET"
            transports.add((method, _normalize_template_path(match.group(2)), relative))
        for match in channel_pattern.finditer(text):
            transports.add(("CHANNEL", _normalize_template_path(match.group(2)), relative))
    return transports


def _ds19_collaboration_strangle_is_merged(repo_root: Path) -> bool:
    register_path = (
        repo_root
        / "architecture"
        / "atlas_surfaces"
        / "frontend-disposition-register.json"
    )
    if not register_path.is_file():
        return False

    register = json.loads(register_path.read_text(encoding="utf-8"))
    assert register["register_id"] == "atlas-ds19-frontend-disposition"
    assert "deleting server endpoints from a frontend-only decision" in register[
        "authority"
    ]["may_not_use_for"]
    entries = {
        entry["unit_id"]: entry
        for entry in register["entries"]
        if entry.get("unit_id") in _DS19_COLLABORATION_UNITS
    }
    assert set(entries) == _DS19_COLLABORATION_UNITS
    for entry in entries.values():
        assert entry["disposition"] == "deleted"
        assert entry["strangle_status"] == "strangled"
        assert entry["owner_slice"] == "DS19"
        assert entry["decision_date"] == "2026-07-17"
    return True


def _assert_transport_residual_is_governed(
    unresolved: set[tuple[str, str, str]],
    *,
    ds19_strangle_merged: bool,
) -> None:
    if ds19_strangle_merged:
        assert not unresolved
        return

    assert unresolved
    assert all(
        (
            path.startswith("/api/v1/collaboration/")
            and "/features/collaboration/" in f"/{source}"
        )
        or (
            path == "/api/v1/collaboration/live"
            and source.endswith("/app/realtime/websocketTransport.ts")
        )
        for _method, path, source in unresolved
    )


def _capture_generated_client_job_status_call(job_id: str) -> dict[str, object]:
    script = """
import { RuntimeApiClient } from "./packages/runtime-api-client/runtimeApiClient.js";

const calls = [];
const client = new RuntimeApiClient({
  baseUrl: "https://runtime.test/",
  fetchImpl: async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  },
});

await client.getControlJobStatus({ job_id: process.env.POLISYOS_JOB_ID });
console.log(JSON.stringify(calls[0]));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=REPO_ROOT,
        env={**os.environ, "POLISYOS_JOB_ID": job_id},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_generated_runtime_api_client_job_status_contract_hits_runtime_control_service(
    tmp_path,
) -> None:
    from _helpers.runtime_http import build_runtime_api_env

    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        client = env["client"]
        launch = client.post(
            "/api/v1/control/runs",
            json={
                "mode": "workflow",
                "data_source": {"data_snapshot_ref": env["root_artifact_id"]},
                "params": {"seed": 5},
            },
        )
        assert launch.status_code == 200
        job_id = launch.json()["job_id"]

        call = _capture_generated_client_job_status_call(job_id)
        parsed = urlparse(str(call["url"]))
        assert call["init"]["method"] == "GET"  # type: ignore[index]
        assert parsed.path == f"/api/v1/control/jobs/{job_id}"

        status = client.get(parsed.path)
        assert status.status_code == 200
        body = status.json()
        assert body["job_id"] == job_id
        assert body["kind"] == "workflow_run"
        assert body["effective_execution_profile"] == "dev"
    finally:
        client_close = getattr(env.get("client"), "close", None)
        if callable(client_close):
            client_close()
        service_close = getattr(
            getattr(env["app"].state, "_control_service", None),
            "close",
            None,
        )
        if callable(service_close):
            service_close()


def test_every_runtime_client_transport_has_openapi_or_governed_channel_contract() -> None:
    from polisyos.runtime.http.services.governed_projections import CHANNEL_REGISTRY

    spec = json.loads(
        (REPO_ROOT / "schemas" / "runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )
    openapi_operations = {
        (method.upper(), path)
        for path, path_item in spec["paths"].items()
        for method in path_item
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }
    channel_paths = {entry.path_template for entry in CHANNEL_REGISTRY}
    unresolved: set[tuple[str, str, str]] = set()

    for method, path, source in _dashboard_runtime_transports():
        if method == "CHANNEL":
            matched = any(_paths_match(path, contract_path) for contract_path in channel_paths)
        else:
            matched = any(
                method == contract_method and _paths_match(path, contract_path)
                for contract_method, contract_path in openapi_operations
            )
        if not matched:
            unresolved.add((method, path, source))

    _assert_transport_residual_is_governed(
        unresolved,
        ds19_strangle_merged=_ds19_collaboration_strangle_is_merged(REPO_ROOT),
    )


def test_transport_contract_accepts_zero_residual_after_verified_ds19_strangle(
    tmp_path: Path,
) -> None:
    register_path = (
        tmp_path
        / "architecture"
        / "atlas_surfaces"
        / "frontend-disposition-register.json"
    )
    register_path.parent.mkdir(parents=True)
    register_path.write_text(
        json.dumps(
            {
                "register_id": "atlas-ds19-frontend-disposition",
                "authority": {
                    "may_not_use_for": [
                        "deleting server endpoints from a frontend-only decision"
                    ]
                },
                "entries": [
                    {
                        "unit_id": unit_id,
                        "disposition": "deleted",
                        "strangle_status": "strangled",
                        "owner_slice": "DS19",
                        "decision_date": "2026-07-17",
                    }
                    for unit_id in _DS19_COLLABORATION_UNITS
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _ds19_collaboration_strangle_is_merged(tmp_path)
    _assert_transport_residual_is_governed(set(), ds19_strangle_merged=True)


def test_reference_shell_uses_only_shared_generated_client_home() -> None:
    shell_source = (REPO_ROOT / "apps" / "runtime-reference-shell" / "app.js").read_text(
        encoding="utf-8"
    )

    assert '../../packages/runtime-api-client/runtimeApiClient.js' in shell_source
    assert "runtime-dashboard/src/api/types" not in shell_source
    assert "runtime-dashboard/src/api/client" not in shell_source
    assert ".listGovernedProjections(" in shell_source


def test_committed_openapi_preserves_lex_truth_fields() -> None:
    spec = json.loads(
        (REPO_ROOT / "schemas" / "runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )
    result_properties = spec["components"]["schemas"]["LexSearchResultItem"]["properties"]

    assert {
        "trust_tier",
        "grounding_status",
        "canonical_status",
        "reference_resolution_status",
        "structure_quality",
        "constraint_type_canon",
        "route_class",
        "fused_confidence",
        "consistency_score",
        "hallucination_flags_json",
        "quality_band",
        "doc_id",
        "doc_family_id",
        "version_id",
        "jurisdiction",
        "top_domain",
        "effective_from",
        "effective_to",
        "temporal_state",
        "temporal_resolution_status",
        "temporal_source_scope",
        "temporal_source_kind",
        "temporal_confidence",
        "temporal_provenance_json",
        "provision_anchor",
    } <= set(result_properties)


def test_committed_openapi_has_governed_export_contracts() -> None:
    spec = json.loads(
        (REPO_ROOT / "schemas" / "runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )

    assert "/api/v1/exports/governed-projections" in spec["paths"]
    assert "/api/v1/exports/governed-projections/{projection_id}" in spec["paths"]
    assert "/api/v1/exports/channel-registry" in spec["paths"]
