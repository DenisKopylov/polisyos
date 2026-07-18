from __future__ import annotations

import pytest
from polisyos_tests_runtime_http_conftest import build_runtime_api_env

from polisyos.core.contracts.control import PolicyFlags
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.execution_policy import (
    ExecutionProfileError,
    PolicyFlagForbiddenError,
    RuntimeExecutionPolicyResolver,
    RuntimePrincipal,
)


def test_research_profile_rejects_execution_profile_downgrade(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    del tmp_path
    resolver = RuntimeExecutionPolicyResolver.from_env()

    with pytest.raises(ExecutionProfileError) as exc:
        resolver.resolve(requested_profile="dev")

    assert exc.value.code == "execution_profile_downgrade_forbidden"


def test_research_profile_rejects_mock_nl_without_policy_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    del tmp_path
    policy = RuntimeExecutionPolicyResolver.from_env().resolve(
        requested_profile=None,
        policy_flags=PolicyFlags(),
    )

    assert policy.effective_profile == "research"
    assert policy.mock_fallback_allowed is False


def test_policy_flags_are_fail_closed_without_privileged_principal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    monkeypatch.setenv("POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE", "1")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    del tmp_path
    resolver = RuntimeExecutionPolicyResolver.from_env()

    with pytest.raises(PolicyFlagForbiddenError) as exc:
        resolver.resolve(
            requested_profile=None,
            policy_flags=PolicyFlags(allow_mock_fallback=True),
            principal=RuntimePrincipal(),
        )

    assert exc.value.code == "policy_flag_forbidden"


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


def test_dev_fixture_identity_cannot_request_governed_run(
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
    assert response.json()["code"] == "fixture_identity_profile_forbidden"


def test_dev_fixture_identity_cannot_request_research_run(
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
    assert response.json()["code"] == "fixture_identity_profile_forbidden"
