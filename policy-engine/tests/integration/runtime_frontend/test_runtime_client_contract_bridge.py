from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


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
