from __future__ import annotations

import pytest
from polisyos_tests_runtime_http_conftest import build_runtime_api_env

from polisyos.runtime.http.app import create_runtime_api_app


def test_research_profile_rejects_execution_profile_downgrade(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": env["root_artifact_id"]},
            "execution_profile": "dev",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "execution_profile_downgrade_forbidden"


def test_research_profile_rejects_mock_nl_without_policy_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    response = client.post(
        "/api/v1/control/runs/nl",
        json={
            "request": "Research profile should not accept implicit mock mode",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "llm_model_unconfigured"


def test_policy_flags_are_fail_closed_without_privileged_principal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    response = client.post(
        "/api/v1/control/runs/nl",
        json={
            "request": "Explicitly request mock fallback",
            "policy_flags": {"allow_mock_fallback": True},
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "policy_flag_forbidden"


def test_research_profile_requires_durable_control_plane_without_waiver(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    with pytest.raises(RuntimeError):
        create_runtime_api_app(cas_root=tmp_path / ".polisyos")


def test_governed_profile_requires_security_chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "governed")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "postgres")
    monkeypatch.setenv("POLISYOS_CONTROL_POSTGRES_DSN", "postgresql://example.invalid/polisyos")
    with pytest.raises(RuntimeError):
        create_runtime_api_app(cas_root=tmp_path / ".polisyos")


def test_production_profile_rejects_embedded_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "production")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "postgres")
    monkeypatch.setenv("POLISYOS_CONTROL_POSTGRES_DSN", "postgresql://example.invalid/polisyos")
    with pytest.raises(RuntimeError):
        create_runtime_api_app(
            cas_root=tmp_path / ".polisyos",
            identity_provider=object(),
            cell_registry=object(),
            opa_client=object(),
        )


def test_dev_deployment_rejects_governed_run_without_durable_control_plane(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": env["root_artifact_id"]},
            "execution_profile": "governed",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "durable_worker_required"


def test_dev_deployment_rejects_research_run_without_durable_control_plane(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    client = env["client"]
    response = client.post(
        "/api/v1/control/runs",
        json={
            "data_source": {"data_snapshot_ref": env["root_artifact_id"]},
            "execution_profile": "research",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "durable_worker_required"
