from __future__ import annotations

import json
import time

import pytest

try:  # pragma: no cover - optional dependency guard
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]

from polisyos_tests_runtime_http_conftest import build_runtime_api_env


def _launch_payload(env: dict[str, object]) -> dict[str, object]:
    return {
        "data_source": {"data_snapshot_ref": env["root_artifact_id"]},
    }


def test_control_run_launch_replays_idempotent_post(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "10")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    headers = {"X-Idempotency-Key": "run-launch-idem-001"}

    first = client.post("/api/v1/control/runs", json=_launch_payload(env), headers=headers)
    second = client.post("/api/v1/control/runs", json=_launch_payload(env), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers["X-Idempotent-Replay"] == "true"
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["job_id"] == first.json()["job_id"]


def test_control_run_launch_rate_limits_per_tenant(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "1")
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_WINDOW_SECONDS", "60")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]

    first = client.post("/api/v1/control/runs", json=_launch_payload(env))
    second = client.post("/api/v1/control/runs", json=_launch_payload(env))

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "rate_limit_exceeded"


def test_control_mutations_append_audit_trail(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "10")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]

    response = client.post(
        "/api/v1/control/runs",
        json=_launch_payload(env),
        headers={"X-Idempotency-Key": "audit-run-launch-001"},
    )

    assert response.status_code == 200
    audit_path = env["cas_root"] / "runtime" / "audit" / "mutations.jsonl"
    lines = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matching = [line for line in lines if line["endpoint"] == "/api/v1/control/runs"]

    assert matching
    assert matching[-1]["tenant_id"] == env["tenant_a"]
    assert matching[-1]["actor"] == "fixture-analyst"
    assert matching[-1]["outcome"] == "success"
    assert matching[-1]["resource_ids"]


def test_feedback_evaluate_mutation_is_audited(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "10")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]

    response = client.post(
        f"/api/v1/control/runs/{env['core_run_id']}/feedback/evaluate",
        headers={"X-Idempotency-Key": "audit-feedback-evaluate-001"},
    )

    assert response.status_code == 200
    audit_path = env["cas_root"] / "runtime" / "audit" / "mutations.jsonl"
    lines = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matching = [
        line
        for line in lines
        if line["endpoint"] == f"/api/v1/control/runs/{env['core_run_id']}/feedback/evaluate"
    ]

    assert matching
    assert matching[-1]["outcome"] == "success"
    assert env["core_run_id"] in matching[-1]["resource_ids"]


def test_control_store_timeout_opens_circuit_and_returns_503_or_504(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "10")
    monkeypatch.setenv("POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS", "0.05")
    monkeypatch.setenv("POLISYOS_RUNTIME_CONTROL_STORE_BREAKER_FAILURE_THRESHOLD", "1")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    app = env["app"]

    launch = client.post("/api/v1/control/runs", json=_launch_payload(env))
    assert launch.status_code == 200
    job_id = launch.json()["job_id"]

    store_target = app.state._control_service._control_store._target
    original_get_job = store_target.get_job

    def _slow_get_job(job_id_value: str):  # noqa: ANN001
        time.sleep(0.2)
        return original_get_job(job_id_value)

    monkeypatch.setattr(store_target, "get_job", _slow_get_job)

    first = client.get(f"/api/v1/control/jobs/{job_id}")
    second = client.get(f"/api/v1/control/jobs/{job_id}")

    assert first.status_code in {503, 504}
    assert first.json()["code"] in {
        "control_plane_store_timeout",
        "control_plane_store_unavailable",
    }
    assert second.status_code == 503
    assert second.json()["code"] == "control_plane_store_unavailable"


def test_feedback_evaluate_returns_504_when_cas_is_slow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_WRITE_RATE_LIMIT", "10")
    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "0.05")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    app = env["app"]

    store_target = app.state.runtime_api_ctx.feedback._store._target
    original_get_bytes = store_target.get_bytes

    def _slow_get_bytes(artifact_id):  # noqa: ANN001
        time.sleep(0.2)
        return original_get_bytes(artifact_id)

    monkeypatch.setattr(store_target, "get_bytes", _slow_get_bytes)

    response = client.post(f"/api/v1/control/runs/{env['core_run_id']}/feedback/evaluate")

    assert response.status_code == 504
    assert response.json()["code"] == "content_addressed_storage_timeout"


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_runtime_shutdown_cleans_up_worker_and_review_hub(tmp_path) -> None:
    env = build_runtime_api_env(tmp_path, include_test_client=False)
    app = env["app"]
    control_service = app.state._control_service

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/api/v1/review/live?channel=review.presence&review_id=run:{env['core_run_id']}:governance"
        ) as websocket:
            assert websocket.receive_json()["type"] == "presence.snapshot"
        assert app.state.review_collaboration_hub._subscribers == {}

    assert control_service._worker is not None
    assert control_service._worker._thread is not None
    assert not control_service._worker._thread.is_alive()
    assert app.state.review_collaboration_hub._subscribers == {}
