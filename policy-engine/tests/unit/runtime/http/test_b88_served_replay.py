from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest

from polisyos.core.artifacts.manifest import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import EvidenceBundle
from polisyos.core.security.identity import PolicyOSRole
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    HealthStatus,
)
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
    FetchRequest,
    FetchResult,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)
from tests.unit.runtime.http.test_control_api import (
    _secure_control_client,
    _with_fresh_step_up,
)

_CONNECTOR_ID = "test.b88_served_replay@1.0.0"
_DATASET_ID = "rows"
_URL = "https://b88-replay.invalid/rows"


class _HTTPReplayConnector(BaseConnector[list[dict[str, Any]]]):
    connector_id: ClassVar[str] = "b88_served_replay"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="b88_served_replay",
        version="1.0.0",
        namespace="test",
        source_name="B88 served replay fixture",
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
        return HealthStatus(healthy=True, message="fixture connector")

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict[str, Any]]]:
        del request
        import aiohttp

        async with aiohttp.ClientSession() as session, session.get(
            handle.config.url
        ) as response:
            rows = await response.json()
        now = datetime.now(UTC)
        payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        return FetchResult(
            data=rows,
            row_count=len(rows),
            schema_id="test.b88.served-replay",
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=digest,
                timestamp=now,
                content_hash=digest,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.BRONZE,
        )

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        del config
        return ValidationResult.success()


@pytest.fixture(autouse=True)
def _fresh_connector_registry():
    ConnectorRegistry.reset_instance()
    ConnectorRegistry.get_instance(bootstrap=False)
    yield
    ConnectorRegistry.reset_instance()


def _register_connector() -> ConnectorRegistry:
    registry = ConnectorRegistry.get_instance(bootstrap=False)
    registry.register(_HTTPReplayConnector, config=ConnectionConfig(url=_URL))
    return registry


def _persist_session(cas_root, *, response_body: bytes | None) -> tuple[str, str]:
    request_url = _canonicalize_url(_URL, None)
    request_hash = _request_hash("GET", request_url, "none", b"")
    fixtures: list[dict[str, Any]] = []
    if response_body is not None:
        fixture = SimulatorFixture(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=base64.b64encode(response_body).decode("ascii"),
            captured_at="2026-09-28T00:00:00+00:00",
            request_url=request_url,
            request_method="GET",
            request_hash=request_hash,
            connector_id=_CONNECTOR_ID,
            dataset_id=_DATASET_ID,
        )
        fixtures.append(fixture.to_dict())
    ref = ReplayStore(FileSystemCAS(cas_root)).save_record_session(
        RecordSession(
            session_id="b88-served-replay-session",
            fixtures=fixtures,
            connector_datasets=[
                {"connector_id": _CONNECTOR_ID, "dataset_id": _DATASET_ID}
            ],
            recorded_at="2026-09-28T00:00:00+00:00",
        )
    )
    return str(ref.artifact_id), request_hash


def _capture_replay(monkeypatch: pytest.MonkeyPatch):
    import aiohttp

    from polisyos.fabric.connectors.testing import simulator as simulator_module

    simulators: list[APISimulator] = []
    native_requests: list[tuple[str, str]] = []
    original_simulator = simulator_module.APISimulator

    def capture_simulator(**kwargs: Any) -> APISimulator:
        simulator = original_simulator(**kwargs)
        simulators.append(simulator)
        return simulator

    async def forbid_native_request(self, method: str, url: str, **kwargs: Any):
        del self, kwargs
        native_requests.append((method, str(url)))
        raise AssertionError("replay must not reach the native network transport")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", forbid_native_request)
    monkeypatch.setattr(simulator_module, "APISimulator", capture_simulator)
    return simulators, native_requests


def _post_ingest(client, headers, *, replay_ref: str | None):
    return client.post(
        "/api/v1/control/data/ingest",
        headers=_with_fresh_step_up(client, headers),
        json={
            "datasets": [{"connector_id": _CONNECTOR_ID, "dataset_id": _DATASET_ID}],
            "source": "test",
            "license_name": "MIT",
            "execution_mode": "batch_full",
            "produce_data_snapshot": False,
            "replay_ref": replay_ref,
        },
    )


def _assert_evidence_contains_source_bytes(cas_root, evidence_bundle_ref: str, marker: bytes) -> None:
    store = FileSystemCAS(cas_root)
    bundle_ref = evidence_bundle_ref
    if not bundle_ref.startswith("sha256:"):
        bundle_ref = f"sha256:{bundle_ref}"
    bundle_id = ArtifactID.model_validate(bundle_ref)
    bundle = EvidenceBundle.model_validate(from_canonical_bytes(store.get_bytes(bundle_id)))
    assert bundle.sources
    assert bundle.provenance_ref is not None

    matching_sources = []
    for source_ref in bundle.sources:
        source_id = ArtifactID.model_validate(source_ref.artifact_id)
        payload = store.get_bytes(source_id)
        if marker in payload:
            matching_sources.append(source_id)
    assert len(matching_sources) == 1
    assert store.get_bytes(matching_sources[0])


def test_served_replay_loads_the_cas_session_and_binds_fixture_output_to_evidence(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _register_connector()
    del registry
    fixture_body = b'[{"value":714,"marker":"b88-served-replay-positive"}]'
    replay_ref, request_hash = _persist_session(
        runtime_api_env["cas_root"], response_body=fixture_body
    )
    client, _cell_id, headers = _secure_control_client(
        runtime_api_env,
        role=PolicyOSRole.ANALYST,
        case_id="b88-served-replay-positive",
    )
    simulators, native_requests = _capture_replay(monkeypatch)
    ordinary_calls: list[bool] = []
    import polisyos.fabric.data_plane.orchestrator as orchestrator_module

    real_ordinary = orchestrator_module.run_orchestrated_ingestion

    def observe_ordinary(**kwargs: Any):
        ordinary_calls.append(True)
        return real_ordinary(**kwargs)

    monkeypatch.setattr(
        orchestrator_module,
        "run_orchestrated_ingestion",
        observe_ordinary,
    )
    with client:
        response = _post_ingest(client, headers, replay_ref=replay_ref)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["mode_effective"] == "replay"
    assert body["datasets_fetched"] == 1
    assert body["evidence_bundle_ref"] is not None
    assert len(simulators) == 1
    assert simulators[0].call_count == 1
    assert simulators[0].call_log[0]["method"] == "GET"
    assert simulators[0].call_log[0]["url"] == _canonicalize_url(_URL, None)
    assert simulators[0].call_log[0]["hash"] == request_hash
    assert native_requests == []
    assert ordinary_calls == []

    replayed = ReplayStore(FileSystemCAS(runtime_api_env["cas_root"])).load_record_session(
        ArtifactID.model_validate(replay_ref)
    )
    assert len(replayed.fixtures) == 1
    assert replayed.fixtures[0]["request_hash"] == request_hash
    assert base64.b64decode(replayed.fixtures[0]["body"]) == fixture_body
    _assert_evidence_contains_source_bytes(
        runtime_api_env["cas_root"],
        body["evidence_bundle_ref"],
        b"b88-served-replay-positive",
    )


@pytest.mark.parametrize(
    ("fixture_body", "expected_error"),
    [(None, "missing"), (b"not-json", "corrupt")],
    ids=["missing-request-fixture", "corrupt-response-bytes"],
)
def test_served_replay_fixture_failures_do_not_fall_back_to_ordinary_ingestion(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    fixture_body: bytes | None,
    expected_error: str,
) -> None:
    _register_connector()
    replay_ref, _request_hash = _persist_session(
        runtime_api_env["cas_root"], response_body=fixture_body
    )
    client, _cell_id, headers = _secure_control_client(
        runtime_api_env,
        role=PolicyOSRole.ANALYST,
        case_id=f"b88-served-replay-{expected_error}",
    )
    simulators, native_requests = _capture_replay(monkeypatch)
    ordinary_calls: list[bool] = []
    import polisyos.fabric.data_plane.orchestrator as orchestrator_module

    def forbidden_ordinary(**kwargs: Any):
        del kwargs
        ordinary_calls.append(True)
        raise RuntimeError("ordinary ingestion is forbidden after replay failure")

    monkeypatch.setattr(
        orchestrator_module,
        "run_orchestrated_ingestion",
        forbidden_ordinary,
    )
    with client:
        response = _post_ingest(client, headers, replay_ref=replay_ref)

    assert len(simulators) == 1
    assert simulators[0].call_count == 1
    assert simulators[0].call_log[0]["url"] == _canonicalize_url(_URL, None)
    assert native_requests == []
    assert ordinary_calls == []
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["mode_effective"] == "replay"
    assert body["datasets_fetched"] == 0
    assert body["evidence_bundle_ref"] is None


class _FakeResponse:
    def __init__(self, url: str, payload: bytes) -> None:
        self.url = url
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self._payload = payload

    async def json(self) -> Any:
        return json.loads(self._payload)

    async def text(self) -> str:
        return self._payload.decode("utf-8")

    async def read(self) -> bytes:
        return self._payload

    def raise_for_status(self) -> None:
        return None

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


def test_served_ordinary_ingestion_remains_available_without_replay_reference(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_connector()
    client, _cell_id, headers = _secure_control_client(
        runtime_api_env,
        role=PolicyOSRole.ANALYST,
        case_id="b88-served-replay-ordinary-control",
    )
    import aiohttp

    import polisyos.fabric.data_plane.orchestrator as orchestrator_module
    from polisyos.fabric.connectors.testing import simulator as simulator_module

    allowed_body = b'[{"value":715,"marker":"b88-ordinary-control"}]'
    observed_requests: list[tuple[str, str]] = []
    ordinary_calls: list[bool] = []
    simulators: list[APISimulator] = []
    original_simulator = simulator_module.APISimulator
    original_ordinary = orchestrator_module.run_orchestrated_ingestion

    def capture_simulator(**kwargs: Any) -> APISimulator:
        simulator = original_simulator(**kwargs)
        simulators.append(simulator)
        return simulator

    async def allow_exact_request(self, method: str, url: str, **kwargs: Any):
        del self, kwargs
        normalized = _canonicalize_url(str(url), None)
        observed_requests.append((method, normalized))
        if method != "GET" or normalized != _canonicalize_url(_URL, None):
            raise AssertionError(f"unexpected ordinary request: {method} {normalized}")
        return _FakeResponse(normalized, allowed_body)

    def observe_ordinary(**kwargs: Any):
        ordinary_calls.append(True)
        return original_ordinary(**kwargs)

    monkeypatch.setattr(aiohttp.ClientSession, "_request", allow_exact_request)
    monkeypatch.setattr(simulator_module, "APISimulator", capture_simulator)
    monkeypatch.setattr(
        orchestrator_module,
        "run_orchestrated_ingestion",
        observe_ordinary,
    )
    with client:
        response = _post_ingest(client, headers, replay_ref=None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["mode_effective"] == "batch_full"
    assert body["datasets_fetched"] == 1
    assert body["evidence_bundle_ref"] is not None
    assert ordinary_calls == [True]
    assert simulators == []
    assert observed_requests == [("GET", _canonicalize_url(_URL, None))]
    _assert_evidence_contains_source_bytes(
        runtime_api_env["cas_root"],
        body["evidence_bundle_ref"],
        b"b88-ordinary-control",
    )
