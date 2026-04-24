from __future__ import annotations

from contextlib import contextmanager

import pytest
from polisyos_tests_runtime_http_conftest import build_runtime_api_env

import polisyos.runtime.http.routes.runs as runs_routes
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None


class _MetricsStub:
    def ensure_initialized(self) -> None:
        return None


class _TracerStub:
    @contextmanager
    def start_as_current_span(self, _name: str, attributes=None):
        _ = attributes
        yield


class _IdentityProviderStub:
    def extract_user_claims(self, jwt_token: str, *, expected_cell_id: str | None = None):
        del jwt_token
        del expected_cell_id
        raise RuntimeError("not used in construction-only test")


class _OpaStub:
    async def check(self, authz_input):
        del authz_input
        raise RuntimeError("not used in construction-only test")


def test_artifact_endpoints_emit_immutable_cache_headers(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]

    response = client.get(f"/api/v1/artifacts/{artifact_id}")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, max-age=31536000, immutable"
    assert response.headers["ETag"].startswith("W/")
    assert "GMT" in response.headers["Last-Modified"]
    assert 'rel="download"' in response.headers["Link"]
    assert response.headers["X-API-Version"] == "1"


def test_artifact_content_negotiates_raw_representation(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["binary_artifact_id"]

    response = client.get(
        f"/api/v1/artifacts/{artifact_id}/content",
        headers={"Accept": "application/octet-stream"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert response.headers["Content-Disposition"].startswith("inline;")
    assert response.content == b"x" * 5000


def test_artifact_download_endpoint_returns_attachment(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["binary_artifact_id"]

    response = client.get(
        f"/api/v1/artifacts/{artifact_id}/download",
        headers={"Accept": "application/octet-stream"},
    )

    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert response.content == b"x" * 5000


def test_artifact_batch_endpoint_avoids_n_plus_one_fetches(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    response = client.post(
        "/api/v1/artifacts/batch",
        json={
            "artifact_ids": [
                runtime_api_env["workflow_report_artifact_id"],
                runtime_api_env["decision_packet_artifact_id"],
                runtime_api_env["workflow_report_artifact_id"],
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()["artifacts"]
    assert [item["artifact_id"] for item in payload] == [
        runtime_api_env["workflow_report_artifact_id"],
        runtime_api_env["decision_packet_artifact_id"],
        runtime_api_env["workflow_report_artifact_id"],
    ]


def test_runs_batch_endpoint_returns_multiple_run_details(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    response = client.post(
        "/api/v1/runs/batch",
        json={
            "run_ids": [
                runtime_api_env["core_run_id"],
                runtime_api_env["core_run_id_secondary"],
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()["runs"]
    assert [item["run_id"] for item in payload] == [
        runtime_api_env["core_run_id"],
        runtime_api_env["core_run_id_secondary"],
    ]
    assert '</api/v1/runs>; rel="collection"' in response.headers["Link"]


def test_run_detail_endpoint_emits_link_relations(runtime_api_env) -> None:
    client = runtime_api_env["client"]

    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}")

    assert response.status_code == 200
    links = response.headers["Link"]
    assert 'rel="collection"' in links
    assert f'</api/v1/runs/{runtime_api_env["core_run_id"]}>; rel="self"' in links
    assert f'</api/v1/runs/{runtime_api_env["core_run_id"]}/timeline>; rel="related"' in links
    assert (
        f"</api/v1/runs/{runtime_api_env['core_run_id']}/evidence-context>; "
        'rel="describedby"' in links
    )


def test_runtime_container_accepts_typed_test_overrides(tmp_path) -> None:
    metrics = _MetricsStub()
    tracer = _TracerStub()

    app = create_runtime_api_app(
        cas_root=tmp_path / ".polisyos",
        allow_fixture_identity=True,
        container_overrides=RuntimeContainerOverrides(
            runtime_metrics=metrics,
            runtime_tracer=tracer,
        ),
    )

    assert app.state.runtime_container.runtime_metrics is metrics
    assert app.state.runtime_container.runtime_tracer is tracer


def test_runtime_security_middlewares_receive_injected_metrics_provider(tmp_path) -> None:
    metrics = _MetricsStub()
    tracer = _TracerStub()
    registry = CellRegistry()
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=50)
    registry.register_cell(cell)
    registry.register_tenant(
        TenantSpec(
            tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            name="tenant-a",
            region="us-gov-west-1",
        ),
        cell.cell_id,
    )

    app = create_runtime_api_app(
        cas_root=tmp_path / ".polisyos",
        enable_security_middlewares=True,
        identity_provider=_IdentityProviderStub(),
        cell_registry=registry,
        opa_client=_OpaStub(),
        container_overrides=RuntimeContainerOverrides(
            runtime_metrics=metrics,
            runtime_tracer=tracer,
        ),
    )

    middleware_kwargs = {
        middleware.cls.__name__: getattr(middleware, "kwargs", {})
        for middleware in app.user_middleware
    }
    assert middleware_kwargs["JWTAuthMiddleware"]["metrics"] is metrics
    assert middleware_kwargs["CellRouterMiddleware"]["metrics"] is metrics


def test_runtime_lifecycle_health_tracks_startup_and_shutdown(tmp_path) -> None:
    if TestClient is None:  # pragma: no cover
        pytest.skip("fastapi test client is not installed")

    env = build_runtime_api_env(tmp_path, include_test_client=False)
    app = env["app"]

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["lifecycle"]["status"] == "ready"
        assert app.state.runtime_container.lifecycle.status == "ready"

    assert app.state.runtime_container.lifecycle.status == "stopped"


def test_api_version_headers_surface_deprecation_policy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("POLISYOS_RUNTIME_API_DEPRECATED", "1")
    monkeypatch.setenv("POLISYOS_RUNTIME_API_SUNSET", "Wed, 31 Dec 2026 23:59:59 GMT")
    env = build_runtime_api_env(tmp_path, include_test_client=True)

    response = env["client"].get(f"/api/v1/runs/{env['core_run_id']}")

    assert response.status_code == 200
    assert response.headers["X-API-Version"] == "1"
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Sunset"] == "Wed, 31 Dec 2026 23:59:59 GMT"


def test_runs_live_endpoint_advertises_sse_flow_control(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        runs_routes.LiveStreamPolicy,
        "from_env",
        classmethod(
            lambda cls: cls(
                min_interval_seconds=0.1,
                max_interval_seconds=0.1,
                keepalive_seconds=10.0,
                max_duration_seconds=0.15,
            )
        ),
    )
    env = build_runtime_api_env(tmp_path, include_test_client=True)

    with env["client"].stream("GET", "/api/v1/runs/live") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["Cache-Control"] == "no-cache, no-transform"
        assert response.headers["Connection"] == "keep-alive"
        assert response.headers["X-Accel-Buffering"] == "no"
        assert "adaptive;" in response.headers["X-SSE-Flow-Control"]
        assert "budget=0.15" in response.headers["X-SSE-Flow-Control"]

        chunks: list[str] = []
        for chunk in response.iter_text():
            if chunk:
                chunks.append(chunk)
            if "event: stream.timeout" in "".join(chunks):
                break

    payload = "".join(chunks)
    assert "event: snapshot" in payload
    assert "event: stream.timeout" in payload
    assert "stream_timeout_budget_exhausted" in payload
