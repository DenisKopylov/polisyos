from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest

from polisyos.core.artifacts.manifest import ArtifactID
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    HealthStatus,
)
from polisyos.fabric.connectors.cache import ResultSerializer
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.testing.simulator import (
    APISimulator,
    SimulatorFixture,
    _canonicalize_url,
    _request_hash,
)
from polisyos.fabric.connectors.types import ValidationResult
from polisyos.fabric.data_plane.replay_store import RecordSession, ReplayStore
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    FetchResult,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)
from polisyos.runtime.http.services.control import ControlPlaneService
from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env
from tests.unit.runtime.http.test_control_api import _with_fresh_step_up
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)

_CONNECTOR_ID = "test.r13_tenant_custody@1.0.0"
_DATASET_ID = "rows"
_URL = "https://r13-custody.invalid/rows"


@pytest.fixture
def runtime_api_env(tmp_path):
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


class _TenantCustodyReplayConnector(BaseConnector[list[dict[str, Any]]]):
    connector_id: ClassVar[str] = "r13_tenant_custody"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[Any] = ConnectorMetadataSpec(
        connector_id="r13_tenant_custody",
        version="1.0.0",
        namespace="test",
        source_name="R13 tenant custody replay fixture",
        source_organization="PolicyOS test fixture",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        del handle
        return HealthStatus(healthy=True, message="replay fixture")

    async def fetch(self, handle: ConnectionHandle, request: Any) -> Any:
        del request
        import aiohttp

        async with aiohttp.ClientSession() as session, session.get(handle.config.url) as response:
            rows = await response.json()
        payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        return FetchResult(
            data=rows,
            row_count=len(rows),
            schema_id="test.r13.tenant-custody",
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=digest,
                timestamp=datetime.now(UTC),
                content_hash=digest,
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
        )

    @classmethod
    def validate_config(cls, config: ConnectionConfig):
        del config
        return ValidationResult.success()


def _auth_headers(token: str, tenant_id: str, *, client: Any) -> dict[str, str]:
    headers = _with_fresh_step_up(
        client,
        {
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": tenant_id,
        },
    )
    return headers


@pytest.fixture
def _r13_registered_connector(runtime_api_env: Any) -> ConnectorRegistry:
    del runtime_api_env
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    registry.register(
        _TenantCustodyReplayConnector,
        config=ConnectionConfig(url=_URL),
    )
    yield registry
    ConnectorRegistry.reset_instance()


@pytest.mark.usefixtures("_r13_registered_connector")
def test_served_replay_reads_owner_session_and_denies_foreign_tenant(
    runtime_api_env: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    token_a = _fixture_bearer("r13-custody-tenant-a")
    token_b = _fixture_bearer("r13-custody-tenant-b")
    tenant_a = runtime_api_env["tenant_a"]
    tenant_b = runtime_api_env["tenant_b"]
    provider.put_claim(
        token_a,
        _claims(
            tenant_id=tenant_a,
            cell_id=cell.cell_id,
            jti="jwt-r13-custody-a",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    provider.put_claim(
        token_b,
        _claims(
            tenant_id=tenant_b,
            cell_id=cell.cell_id,
            jti="jwt-r13-custody-b",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )

    import polisyos.fabric.connectors.testing.simulator as simulator_module

    simulator_instances: list[APISimulator] = []
    original_simulator = simulator_module.APISimulator

    def capture_simulator(**kwargs: Any) -> APISimulator:
        simulator = original_simulator(**kwargs)
        simulator_instances.append(simulator)
        return simulator

    monkeypatch.setattr(simulator_module, "APISimulator", capture_simulator)
    request_url = _canonicalize_url(_URL, None)
    request_hash = _request_hash("GET", request_url, "none", b"")
    response_body = b'[{"value": 1, "marker": "r13-tenant-a-replay"}]'
    session = RecordSession(
        session_id="r13-tenant-a-owner-session",
        fixtures=[
            SimulatorFixture(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=base64.b64encode(response_body).decode("ascii"),
                captured_at="2026-09-28T00:00:00+00:00",
                request_url=request_url,
                request_method="GET",
                request_hash=request_hash,
                connector_id=_CONNECTOR_ID,
                dataset_id=_DATASET_ID,
            ).to_dict()
        ],
        connector_datasets=[
            {"connector_id": _CONNECTOR_ID, "dataset_id": _DATASET_ID}
        ],
        recorded_at="2026-09-28T00:00:00+00:00",
    )

    with client:
        container = client.app.state.runtime_container
        assert isinstance(container.control_service, ControlPlaneService)
        store = container.runtime_api_context.store
        assert container.control_service._artifact_store is store
        with tenant_scope(None, tenant_id=tenant_a, cell_id=cell.cell_id):
            session_ref = ReplayStore(store).save_record_session(session)
        replay_ref = str(session_ref.artifact_id)

        def post(token: str, tenant_id: str):
            headers = _auth_headers(token, tenant_id, client=client)
            return client.post(
                "/api/v1/control/data/ingest",
                headers=headers,
                json={
                    "datasets": [
                        {"connector_id": _CONNECTOR_ID, "dataset_id": _DATASET_ID}
                    ],
                    "source": "r13-tenant-custody",
                    "license_name": "MIT",
                    "execution_mode": "batch_full",
                    "produce_data_snapshot": False,
                    "replay_ref": replay_ref,
                },
            )

        response_a = post(token_a, tenant_a)
        assert response_a.status_code == 200
        body_a = response_a.json()
        assert body_a["status"] == "completed"
        assert body_a["mode_effective"] == "replay"
        assert body_a["datasets_fetched"] == 1
        assert body_a["evidence_bundle_ref"] is not None
        assert len(simulator_instances) == 1
        assert simulator_instances[0].call_count == 1
        assert simulator_instances[0].call_log[0]["url"] == request_url
        assert simulator_instances[0].call_log[0]["hash"] == request_hash

        response_b = post(token_b, tenant_b)
        assert response_b.status_code == 403
        assert response_b.headers.get("content-type", "").startswith(
            "application/problem+json"
        )
        assert response_b.json()["code"] == "ingestion_artifact_ownership_denied"
        assert len(simulator_instances) == 1
        assert simulator_instances[0].call_count == 1



def _read_connector_cache_row(index_path: Path) -> tuple[str, str, str]:
    assert index_path.is_file(), f"served ingestion did not create {index_path}"
    with closing(sqlite3.connect(index_path.as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute(
            "SELECT cache_key, payload_artifact_id, dataset_id FROM cache_entries"
        ).fetchall()
    assert len(rows) == 1
    return tuple(str(value) for value in rows[0])


def _read_connector_cache_marker(
    store: Any,
    row: tuple[str, str, str],
    *,
    tenant_id: str,
    cell_id: str,
) -> str:
    _cache_key, payload_artifact_id, _dataset_id = row
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        result = ResultSerializer.deserialize(
            store.get_bytes(ArtifactID.model_validate(payload_artifact_id))
        )
    assert isinstance(result.data, list) and len(result.data) == 1
    return str(result.data[0]["marker"])


@pytest.mark.usefixtures("_r13_registered_connector")
def test_served_replay_keeps_connector_cache_sidecars_tenant_local(
    runtime_api_env: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recompute tenant-local cache writes from fixture-supplied auth claims.

    P37: tenant identity and authorization are fixture-supplied inputs from the
    test auth provider, not evidence of production identity issuance. The served
    responses, sidecar paths/index entries, and payload bytes are recomputed
    from runtime behavior. Production identity issuance and independent cache
    reader isolation remain not_established.
    """
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    token_a = _fixture_bearer("r13-cache-sidecar-tenant-a")
    token_b = _fixture_bearer("r13-cache-sidecar-tenant-b")
    tenant_a = str(runtime_api_env["tenant_a"])
    tenant_b = str(runtime_api_env["tenant_b"])
    provider.put_claim(
        token_a,
        _claims(
            tenant_id=tenant_a,
            cell_id=cell.cell_id,
            jti="jwt-r13-cache-sidecar-a",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    provider.put_claim(
        token_b,
        _claims(
            tenant_id=tenant_b,
            cell_id=cell.cell_id,
            jti="jwt-r13-cache-sidecar-b",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )

    import polisyos.fabric.connectors.testing.simulator as simulator_module

    simulators: list[APISimulator] = []
    original_simulator = simulator_module.APISimulator

    def capture_simulator(**kwargs: Any) -> APISimulator:
        simulator = original_simulator(**kwargs)
        simulators.append(simulator)
        return simulator

    monkeypatch.setattr(simulator_module, "APISimulator", capture_simulator)
    request_url = _canonicalize_url(_URL, None)
    request_hash = _request_hash("GET", request_url, "none", b"")

    def persist_session(store: Any, *, tenant_id: str, marker: str) -> str:
        response_body = json.dumps(
            [{"value": 1, "marker": marker}], separators=(",", ":")
        ).encode("utf-8")
        session = RecordSession(
            session_id=f"r13-{tenant_id}-cache-session",
            fixtures=[
                SimulatorFixture(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    body=base64.b64encode(response_body).decode("ascii"),
                    captured_at="2026-09-28T00:00:00+00:00",
                    request_url=request_url,
                    request_method="GET",
                    request_hash=request_hash,
                    connector_id=_CONNECTOR_ID,
                    dataset_id=_DATASET_ID,
                ).to_dict()
            ],
            connector_datasets=[
                {"connector_id": _CONNECTOR_ID, "dataset_id": _DATASET_ID}
            ],
            recorded_at="2026-09-28T00:00:00+00:00",
        )
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell.cell_id):
            ref = ReplayStore(store).save_record_session(session)
        return str(ref.artifact_id)

    def post(client: Any, token: str, tenant_id: str, replay_ref: str):
        return client.post(
            "/api/v1/control/data/ingest",
            headers=_auth_headers(token, tenant_id, client=client),
            json={
                "datasets": [
                    {"connector_id": _CONNECTOR_ID, "dataset_id": _DATASET_ID}
                ],
                "source": "r13-cache-sidecar",
                "license_name": "MIT",
                "execution_mode": "batch_full",
                "produce_data_snapshot": False,
                "replay_ref": replay_ref,
            },
        )

    with client:
        container = client.app.state.runtime_container
        assert isinstance(container.control_service, ControlPlaneService)
        store = container.runtime_api_context.store
        assert container.control_service._artifact_store is store
        store_root = Path(store.root).resolve()
        assert store_root == Path(runtime_api_env["cas_root"]).resolve()
        session_a_ref = persist_session(
            store, tenant_id=tenant_a, marker="tenant-a-cache-payload"
        )
        session_b_ref = persist_session(
            store, tenant_id=tenant_b, marker="tenant-b-cache-payload"
        )

        response_a_first = post(client, token_a, tenant_a, session_a_ref)
        assert response_a_first.status_code == 200, response_a_first.text
        assert response_a_first.json()["status"] == "completed"
        index_a = (
            store_root
            / "tenants"
            / tenant_a
            / "connector_cache"
            / "cache_index.sqlite3"
        )
        row_a_first = _read_connector_cache_row(index_a)
        assert row_a_first[2] == _DATASET_ID
        assert _read_connector_cache_marker(
            store, row_a_first, tenant_id=tenant_a, cell_id=cell.cell_id
        ) == "tenant-a-cache-payload"

        # Same-tenant control: a repeated served request remains usable and the
        # one logical cache key still resolves to tenant A's own result.
        response_a_again = post(client, token_a, tenant_a, session_a_ref)
        assert response_a_again.status_code == 200, response_a_again.text
        assert response_a_again.json()["status"] == "completed"
        row_a_control = _read_connector_cache_row(index_a)
        assert row_a_control[0] == row_a_first[0]
        assert _read_connector_cache_marker(
            store, row_a_control, tenant_id=tenant_a, cell_id=cell.cell_id
        ) == "tenant-a-cache-payload"

        # Tenant B makes the same connector request with its own authorized replay.
        # If sidecar scope is removed, this same cache key overwrites A's row.
        response_b = post(client, token_b, tenant_b, session_b_ref)
        assert response_b.status_code == 200, response_b.text
        assert response_b.json()["status"] == "completed"
        index_b = (
            store_root
            / "tenants"
            / tenant_b
            / "connector_cache"
            / "cache_index.sqlite3"
        )
        assert index_a != index_b
        row_a_after_b = _read_connector_cache_row(index_a)
        row_b = _read_connector_cache_row(index_b)
        assert row_a_after_b == row_a_control
        assert row_b[0] == row_a_control[0]
        assert row_b[1] != row_a_control[1]
        assert _read_connector_cache_marker(
            store, row_a_after_b, tenant_id=tenant_a, cell_id=cell.cell_id
        ) == "tenant-a-cache-payload"
        assert _read_connector_cache_marker(
            store, row_b, tenant_id=tenant_b, cell_id=cell.cell_id
        ) == "tenant-b-cache-payload"
        assert len(simulators) == 3
        assert all(simulator.call_count == 1 for simulator in simulators)
