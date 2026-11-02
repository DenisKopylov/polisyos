"""Tests for record/replay mode and deterministic regression comparison."""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, IntegrityInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import EvidenceBundle
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    HealthStatus,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.testing.simulator import (
    APISimulator,
    MissingFixtureError,
    SimulatorFixture,
    SimulatorMode,
    _canonicalize_url,
    _request_hash,
)
from polisyos.fabric.connectors.types import ValidationResult
from polisyos.fabric.data_plane.modes import run_replay_mode
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.fabric.data_plane.regression import (
    RegressionIssueCategory,
    RegressionResult,
    categorize_regression_exception,
    compare_artifact_hashes,
    compare_ingestion_runs,
)
from polisyos.fabric.data_plane.replay_store import (
    RecordSession,
    ReplayStore,
    collect_fixtures_from_dir,
    make_record_session,
)
from polisyos.fabric.ingestion import resolve_ingestion_dependencies
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

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# ReplayStore tests
# ---------------------------------------------------------------------------


class TestReplayStore:
    def test_save_and_load_session_roundtrip(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        replay_store = ReplayStore(store)

        session = RecordSession(
            session_id="sess_001",
            fixtures=[
                {
                    "connector_id": "worldbank.wdi",
                    "dataset_id": "NY.GDP.MKTP.CD",
                    "request_hash": "abc123",
                    "url": "https://api.worldbank.org/v2/...",
                    "method": "GET",
                    "status": 200,
                    "body_b64": "eyJkYXRhIjogW119",
                }
            ],
            connector_datasets=[{"connector_id": "worldbank.wdi", "dataset_id": "NY.GDP.MKTP.CD"}],
            recorded_at="2026-02-12T10:00:00Z",
        )

        ref = replay_store.save_record_session(session)
        assert ref is not None
        assert ref.artifact_id is not None

        loaded = replay_store.load_record_session(ref.artifact_id)
        assert loaded.session_id == "sess_001"
        assert len(loaded.fixtures) == 1
        assert loaded.fixtures[0]["connector_id"] == "worldbank.wdi"
        assert loaded.recorded_at == "2026-02-12T10:00:00Z"

    def test_empty_session(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        replay_store = ReplayStore(store)

        session = RecordSession(session_id="empty_sess")
        ref = replay_store.save_record_session(session)
        loaded = replay_store.load_record_session(ref.artifact_id)

        assert loaded.session_id == "empty_sess"
        assert loaded.fixtures == []
        assert loaded.connector_datasets == []

    @pytest.mark.parametrize("unsafe_part", ["connector", "dataset", "request_hash", "symlink"])
    def test_fixture_materialization_admits_all_paths_before_owned_root_writes(
        self, tmp_path: Path, unsafe_part: str
    ) -> None:
        from polisyos.fabric.connectors.testing.simulator import ReplayFixtureIdentityError

        target = tmp_path / "fixtures"
        outside = tmp_path / "owned-outside"
        fixture = SimulatorFixture(
            status_code=200,
            headers={},
            body="",
            captured_at="2026-10-01T00:00:00Z",
            request_url="https://fixture.invalid/rows",
            request_method="GET",
            request_hash="safe-hash",
            connector_id="source",
            dataset_id="rows",
        )
        bad = fixture.to_dict()
        if unsafe_part == "connector":
            bad["connector_id"] = str(outside)
        elif unsafe_part == "dataset":
            bad["dataset_id"] = "../../owned-outside"
        elif unsafe_part == "request_hash":
            bad["request_hash"] = "../../../owned-outside/escaped"
        else:
            outside.mkdir()
            (target / "source").mkdir(parents=True)
            (target / "source" / "rows").symlink_to(outside, target_is_directory=True)
        session = RecordSession(session_id="unsafe-layout", fixtures=[fixture.to_dict(), bad])
        with pytest.raises(ReplayFixtureIdentityError, match="fixture_root"):
            ReplayStore(FileSystemCAS(tmp_path / "cas")).build_replay_fixture_dir(session, target)
        assert not list(target.rglob("*.json")), "known invalid layouts must not partially publish"
        assert not outside.exists() or not list(outside.rglob("*.json"))

    def test_nested_dataset_namespace_stays_supported_within_fixture_root(self, tmp_path: Path):
        fixture = SimulatorFixture(
            status_code=200,
            headers={},
            body="",
            captured_at="2026-10-01T00:00:00Z",
            request_url="https://fixture.invalid/rows",
            request_method="GET",
            request_hash="nested-hash",
            connector_id="source",
            dataset_id="collection/rows",
        )
        target = tmp_path / "fixtures"
        ReplayStore(FileSystemCAS(tmp_path / "cas")).build_replay_fixture_dir(
            RecordSession(session_id="nested", fixtures=[fixture.to_dict()]), target
        )
        assert SimulatorFixture.read(target / "source/collection/rows/nested-hash.json") == fixture

    def test_session_wire_versions_preserve_legacy_bytes_and_reject_unknown_format(
        self, tmp_path: Path
    ) -> None:
        from polisyos.core.artifacts.manifest import SchemaInfo
        from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
        from polisyos.core.canon import CanonSpec

        store = FileSystemCAS(tmp_path / "cas")
        replay_store = ReplayStore(store)
        legacy = RecordSession(session_id="legacy-wire")
        legacy_ref = store.put_json(
            legacy.to_dict(),
            ArtifactWriteOptions(
                kind="fabric.record_session",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.RecordSession", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        legacy_bytes = store.get_bytes(legacy_ref)
        assert replay_store.load_record_session(legacy_ref) == legacy
        assert store.get_bytes(legacy_ref) == legacy_bytes
        assert store.get_manifest(legacy_ref).artifact_schema.version == "1.0"
        current_ref = replay_store.save_record_session(legacy)
        assert current_ref.artifact_id == legacy_ref.artifact_id
        assert current_ref.manifest_profile_sha256 != legacy_ref.manifest_profile_sha256
        assert store.get_manifest(current_ref).artifact_schema.version == "2.0"
        assert replay_store.load_record_session(current_ref) == legacy
        assert store.get_manifest(legacy_ref.artifact_id).artifact_schema.version == "1.0"
        assert store.get_bytes(legacy_ref) == legacy_bytes
        unknown_ref = store.put_json(
            RecordSession(session_id="unknown-wire").to_dict(),
            ArtifactWriteOptions(
                kind="fabric.record_session",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.RecordSession", version="99.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="record_session_schema_unsupported"):
            replay_store.load_record_session(unknown_ref)

    def test_accepts_protocol_backed_store_proxy(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        backing_store = FileSystemCAS(cas_root)

        class _ProtocolStoreProxy:
            def __init__(self, wrapped: FileSystemCAS) -> None:
                self._wrapped = wrapped

            def has(self, artifact_id):
                return self._wrapped.has(artifact_id)

            def get_bytes(self, artifact_id):
                return self._wrapped.get_bytes(artifact_id)

            def get_manifest(self, artifact_id):
                return self._wrapped.get_manifest(artifact_id)

            def get_raw_manifest_bytes(
                self,
                artifact_id: ArtifactID | ArtifactRef | str,
                *,
                manifest_profile_sha256: str | None = None,
            ) -> bytes:
                return self._wrapped.get_raw_manifest_bytes(
                    artifact_id,
                    manifest_profile_sha256=manifest_profile_sha256,
                )

            def put_bytes(self, data, opts):
                return self._wrapped.put_bytes(data, opts)

            def put_json(self, obj, opts, canon_spec=None, **kwargs):
                return self._wrapped.put_json(obj, opts, canon_spec=canon_spec, **kwargs)

            def verify(self, artifact_id):
                return self._wrapped.verify(artifact_id)

            def iter_artifact_ids(self):
                return self._wrapped.iter_artifact_ids()

        replay_store = ReplayStore(_ProtocolStoreProxy(backing_store))

        session = RecordSession(session_id="proxy_sess")
        ref = replay_store.save_record_session(session)
        loaded = replay_store.load_record_session(ref.artifact_id)

        assert loaded.session_id == "proxy_sess"

    def test_build_replay_fixture_dir(self, tmp_path: Path):
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        replay_store = ReplayStore(store)

        # Create a session with a fixture that SimulatorFixture can parse
        fixture_dict = {
            "connector_id": "test.conn",
            "dataset_id": "ds1",
            "request_hash": "hash123",
            "url": "https://example.com/api",
            "method": "GET",
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body_b64": "eyJvayI6IHRydWV9",
        }
        session = RecordSession(
            session_id="fixture_sess",
            fixtures=[fixture_dict],
        )

        target = tmp_path / "replay_fixtures"
        target.mkdir()

        # Mock SimulatorFixture where it's actually imported (lazy import inside method)
        with patch("polisyos.fabric.connectors.testing.simulator.SimulatorFixture") as MockFixture:
            mock_instance = MagicMock()
            mock_instance.connector_id = "test.conn"
            mock_instance.dataset_id = "ds1"
            mock_instance.request_hash = "hash123"
            MockFixture.from_dict.return_value = mock_instance

            result = replay_store.build_replay_fixture_dir(session, target)

        assert result == target
        MockFixture.from_dict.assert_called_once_with(fixture_dict)
        mock_instance.write.assert_called_once()


# ---------------------------------------------------------------------------
# collect_fixtures_from_dir tests
# ---------------------------------------------------------------------------


class TestCollectFixtures:
    def test_empty_dir(self, tmp_path: Path):
        fixtures = collect_fixtures_from_dir(tmp_path)
        assert fixtures == []

    def test_nonexistent_dir(self, tmp_path: Path):
        fixtures = collect_fixtures_from_dir(tmp_path / "nonexistent")
        assert fixtures == []

    def test_invalid_json_skipped(self, tmp_path: Path):
        fixture_dir = tmp_path / "conn" / "ds"
        fixture_dir.mkdir(parents=True)
        (fixture_dir / "bad.json").write_text("not valid json")

        fixtures = collect_fixtures_from_dir(tmp_path)
        assert fixtures == []


# ---------------------------------------------------------------------------
# make_record_session tests
# ---------------------------------------------------------------------------


class TestMakeRecordSession:
    def test_make_session_empty(self, tmp_path: Path):
        session = make_record_session(
            session_id="test_session",
            fixture_root=tmp_path,
        )
        assert session.session_id == "test_session"
        assert session.fixtures == []
        assert session.recorded_at != ""

    def test_make_session_with_connector_datasets(self, tmp_path: Path):
        session = make_record_session(
            session_id="test_session",
            fixture_root=tmp_path,
            connector_datasets=[
                {"connector_id": "a.b", "dataset_id": "d1"},
            ],
        )
        assert len(session.connector_datasets) == 1


# ---------------------------------------------------------------------------
# Regression comparison tests
# ---------------------------------------------------------------------------


class TestRegressionComparison:
    def test_matching_results(self):
        r1 = IngestionResult(datasets_fetched=2, warnings=["w1", "w2"])
        r2 = IngestionResult(datasets_fetched=2, warnings=["w2", "w1"])
        result = compare_ingestion_runs(r1, r2)
        assert result.match is True
        assert result.mismatches == []

    def test_mismatched_datasets_fetched(self):
        r1 = IngestionResult(datasets_fetched=3)
        r2 = IngestionResult(datasets_fetched=2)
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert len(result.mismatches) == 1
        assert "datasets_fetched" in result.mismatches[0]

    def test_mismatched_evidence_presence(self):
        mock_ref = MagicMock()
        r1 = IngestionResult(evidence_bundle_ref=mock_ref)
        r2 = IngestionResult(evidence_bundle_ref=None)
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert any("evidence_bundle_ref" in m for m in result.mismatches)

    def test_mismatched_snapshot_presence(self):
        mock_ref = MagicMock()
        r1 = IngestionResult(data_snapshot_ref=mock_ref)
        r2 = IngestionResult(data_snapshot_ref=None)
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert any("data_snapshot_ref" in m for m in result.mismatches)

    def test_mismatched_warnings(self):
        r1 = IngestionResult(warnings=["w1", "w2"])
        r2 = IngestionResult(warnings=["w1", "w3"])
        result = compare_ingestion_runs(r1, r2)
        assert result.match is False
        assert any("warnings" in m for m in result.mismatches)

    def test_regression_result_is_frozen(self):
        result = RegressionResult(match=True, mismatches=[])
        with pytest.raises(AttributeError):
            result.match = False  # type: ignore[misc]

    def test_mismatch_result_is_categorized(self):
        r1 = IngestionResult(datasets_fetched=1)
        r2 = IngestionResult(datasets_fetched=2)
        result = compare_ingestion_runs(r1, r2)

        assert result.issue_categories == (RegressionIssueCategory.COMPARISON_MISMATCH,)


def _artifact_manifest(payload: bytes, *, kind: str) -> ArtifactManifest:
    artifact_id = ArtifactID.from_sha256_hex(sha256(payload).hexdigest())
    return ArtifactManifest(
        artifact_id=artifact_id,
        kind=kind,
        media_type="application/octet-stream",
        byte_size=len(payload),
        integrity=IntegrityInfo(sha256=artifact_id.hex),
    )


class TestArtifactHashComparison:
    def test_matching_hashes(self):
        mock_store = MagicMock()
        record_manifest = _artifact_manifest(b"same payload", kind="record")
        replay_manifest = _artifact_manifest(b"same payload", kind="replay")
        mock_store.get_manifest.side_effect = [record_manifest, replay_manifest]
        mismatches = compare_artifact_hashes(mock_store, "ref1", "ref2", label="test")
        assert record_manifest.kind != replay_manifest.kind
        assert record_manifest.artifact_id == replay_manifest.artifact_id
        assert mismatches == []

    def test_mismatched_hashes(self):
        mock_store = MagicMock()
        record_manifest = _artifact_manifest(b"record payload", kind="record")
        replay_manifest = _artifact_manifest(b"replay payload", kind="replay")
        mock_store.get_manifest.side_effect = [record_manifest, replay_manifest]
        mismatches = compare_artifact_hashes(mock_store, "ref1", "ref2", label="test")
        assert len(mismatches) == 1
        assert "content_hash" in mismatches[0]
        assert record_manifest.artifact_id.hex in mismatches[0]
        assert replay_manifest.artifact_id.hex in mismatches[0]

    def test_comparison_error_handled(self):
        mock_store = MagicMock()
        mock_store.get_manifest.side_effect = RuntimeError("not found")
        mismatches = compare_artifact_hashes(mock_store, "ref1", "ref2")
        assert len(mismatches) == 1
        assert "failed" in mismatches[0]
        assert "internal_error" in mismatches[0]

    def test_fixture_missing_errors_are_typed(self):
        assert categorize_regression_exception(FileNotFoundError("missing")) == (
            RegressionIssueCategory.FIXTURE_MISSING
        )


class _NamespaceReplayConnector(BaseConnector[list[dict[str, Any]]]):
    """Use the actual registry and HTTP replay boundary for two source namespaces."""

    connector_id: ClassVar[str] = "namespace_replay"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="namespace_replay",
        version="1.0.0",
        namespace="test",
        source_name="Finite replay namespace fixture",
        source_organization="PolicyOS test fixture",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.BRONZE,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    def __init__(self) -> None:
        self.fetches: list[str] = []
        self.responses: dict[str, list[dict[str, Any]]] = {}
        self.shared_request = False

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        del handle
        return HealthStatus(healthy=True)

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict[str, Any]]]:
        import aiohttp

        self.fetches.append(request.dataset_id)
        url = f"{handle.config.url}/{'left' if self.shared_request else request.dataset_id}"
        async with aiohttp.ClientSession() as session, session.get(url) as response:
            rows = await response.json()
        self.responses[request.dataset_id] = rows
        now = datetime.now(UTC)
        digest = "sha256:" + sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        return FetchResult(
            data=rows,
            row_count=len(rows),
            schema_id="test.namespace-replay",
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


@pytest.mark.parametrize(
    "layout",
    [
        "unique",
        "legacy",
        "record_single_namespace",
        "ambiguous",
        "ambiguous_equal_payload",
        "unknown",
        "session_undeclared",
        "missing",
        "corrupt",
        "swapped_hashes",
        "disguised_duplicate",
        "shared_request_missing_source",
        "cross_source_request",
        "warm_cache",
        "warm_cache_corrupt",
        "missing_warm_cache",
        "warm_cache_refuses_bypass",
    ],
)
def test_replay_dispatches_only_declared_unambiguous_request_namespaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
) -> None:
    """Recorded namespaces reach real ingestion and fresh evidence without live fallback."""
    import aiohttp

    registry = ConnectorRegistry()
    connector = _NamespaceReplayConnector()
    connector.shared_request = layout in {"shared_request_missing_source", "cross_source_request"}
    config = ConnectionConfig(url="https://namespace-replay.invalid")
    registered_id = registry.register(
        _NamespaceReplayConnector,
        config=config,
        factory=lambda: connector,
    )
    # The warm-cache route uses the connector's admitted runtime owner so that
    # the cache receipt owner gate also reaches its intended positive branch.
    connector_id = connector.connector_id if "warm_cache" in layout else registered_id
    pairs = [{"connector_id": connector_id, "dataset_id": name} for name in ("left", "right")]
    if layout == "missing_warm_cache":
        pairs = pairs[:1]
    fixtures: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs):
        if layout == "missing_warm_cache":
            continue
        request_name = (
            "left"
            if layout in {"ambiguous", "ambiguous_equal_payload", "disguised_duplicate"}
            else pair["dataset_id"]
        )
        url = _canonicalize_url(f"{config.url}/{request_name}")
        payload = json.dumps(
            [{"marker": f"recorded-{pair['dataset_id']}", "value": index}]
        ).encode()
        if layout == "ambiguous_equal_payload":
            payload = b'[{"marker":"same-recorded-payload","value":0}]'
        if layout in {"corrupt", "warm_cache_corrupt"} and index == 1:
            payload = b"not-json"
        if layout in {"missing", "shared_request_missing_source"} and index == 1:
            continue
        fixture_dataset_id = pair["dataset_id"]
        if layout == "unknown" and index == 1:
            fixture_dataset_id = "undeclared"
        elif layout == "record_single_namespace":
            fixture_dataset_id = "left"
        fixtures.append(
            SimulatorFixture(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=base64.b64encode(payload).decode("ascii"),
                captured_at="2026-10-01T00:00:00+00:00",
                request_url=url,
                request_method="GET",
                request_hash=_request_hash("GET", url, "none", b""),
                connector_id=connector_id,
                dataset_id=fixture_dataset_id,
            ).to_dict()
        )
    if layout == "swapped_hashes":
        fixtures[0]["request_hash"], fixtures[1]["request_hash"] = (
            fixtures[1]["request_hash"],
            fixtures[0]["request_hash"],
        )
    elif layout == "disguised_duplicate":
        fixtures[1]["request_hash"] = _request_hash(
            "GET", _canonicalize_url(f"{config.url}/right"), "none", b""
        )
    cas_root = tmp_path / "cas"
    cache = None
    if "warm_cache" in layout:
        from polisyos.fabric.connectors.cache import (
            CachingConnectorProxy,
            ConnectorCacheStore,
            TTLPolicy,
        )

        cache = ConnectorCacheStore(FileSystemCAS(cas_root), TTLPolicy(ttl=timedelta(hours=1)))
        registry.configure_cache(cache)
        for pair in pairs:
            now = datetime.now(UTC)
            warm_rows = [{"marker": f"another-session-{pair['dataset_id']}", "value": 99}]
            digest = "sha256:" + sha256(json.dumps(warm_rows).encode()).hexdigest()
            request = FetchRequest(
                dataset_id=pair["dataset_id"],
                filters=(),
                include_metadata=True,
                include_schema=True,
                retryable=None,
                page_size=None,
            )
            metadata = cache.put(
                request,
                FetchResult(
                    data=warm_rows,
                    row_count=1,
                    schema_id="test.namespace-replay",
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
                ),
                connector_id=connector_id,
                source_config=config,
            )
            assert metadata.payload_ref.manifest_profile_sha256
        assert isinstance(registry.get(connector_id), CachingConnectorProxy)
    replay_store = ReplayStore(FileSystemCAS(cas_root))
    declarations = pairs
    if layout == "legacy":
        declarations = []
    elif layout == "session_undeclared":
        declarations = pairs[:1]
    record_session = RecordSession(
        session_id=f"namespaces-{layout}", fixtures=fixtures, connector_datasets=declarations
    )
    if layout in {"legacy", "record_single_namespace"}:
        from polisyos.core.artifacts.manifest import SchemaInfo
        from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
        from polisyos.core.canon import CanonSpec

        for fixture in fixtures:
            fixture.pop("request_body_kind", None)
            fixture.pop("request_body", None)
        session_ref = FileSystemCAS(cas_root).put_json(
            record_session.to_dict(),
            ArtifactWriteOptions(
                kind="fabric.record_session",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.RecordSession", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
    else:
        session_ref = replay_store.save_record_session(record_session)
    native_calls: list[str] = []
    ordinary_calls: list[bool] = []

    async def forbid_native(self, method: str, url: str, **kwargs: object) -> None:
        del self, method, kwargs
        native_calls.append(url)
        raise AssertionError("replay reached live transport")

    def forbid_ordinary(**kwargs: object) -> None:
        del kwargs
        ordinary_calls.append(True)
        raise AssertionError("replay reached ordinary ingestion")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", forbid_native)
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion", forbid_ordinary
    )
    if cache is not None:
        from polisyos.fabric.connectors.base import _get_fetch_source_namespace
        from polisyos.fabric.ingestion.ingestion import _sync_fetch_with_receipt

        cached_connector = registry.get(connector_id)
        actual_receipt_fetch = cached_connector.fetch_with_receipt
        receipt_scopes: list[tuple[str, str] | None] = []

        async def observe_receipt(handle, selected_request, **kwargs):
            receipt_scopes.append(_get_fetch_source_namespace())
            return await actual_receipt_fetch(handle, selected_request, **kwargs)

        monkeypatch.setattr(cached_connector, "fetch_with_receipt", observe_receipt)
        _warm_result, receipt = _sync_fetch_with_receipt(
            registry,
            connector_id,
            cached_connector,
            request,
            connection_config=config,
            cas_store=FileSystemCAS(cas_root),
        )
        assert receipt.lookup_outcome == "hit"
        assert receipt_scopes == [(connector_id, request.dataset_id)]
        assert _get_fetch_source_namespace() is None
        if layout == "warm_cache_refuses_bypass":
            actual_get = registry.get

            def ignore_bypass(owner: str, *args: object, **kwargs: object):
                del args, kwargs
                return actual_get(owner, enable_cache=True)

            monkeypatch.setattr(registry, "get", ignore_bypass)

    def replay() -> IngestionResult:
        try:
            return run_replay_mode(
                connector_manifest={"datasets": pairs},
                source="agency",
                license_name="MIT",
                cas_root=cas_root,
                replay_ref=str(session_ref.artifact_id),
                connection_config=config,
                produce_snapshot=False,
                ingestion_dependencies=resolve_ingestion_dependencies(registry=registry),
            )
        finally:
            if cache is not None:
                for pair in pairs:
                    warm_request = FetchRequest(
                        dataset_id=pair["dataset_id"],
                        filters=(),
                        include_metadata=True,
                        include_schema=True,
                        retryable=None,
                        page_size=None,
                    )
                    unchanged = cache.get(
                        warm_request, connector_id=connector_id, source_config=config
                    )
                    assert unchanged is not None
                    assert unchanged.result.data == [
                        {"marker": f"another-session-{pair['dataset_id']}", "value": 99}
                    ], "replay must preserve ordinary cache bytes, including after partial failure"

    try:
        if layout in {"ambiguous", "ambiguous_equal_payload", "unknown", "session_undeclared"}:
            with pytest.raises(ValueError, match="namespace"):
                replay()
            assert connector.fetches == [], "namespace admission must precede ingestion"
        elif layout in {"swapped_hashes", "disguised_duplicate"}:
            with pytest.raises(ValueError, match="request"):
                replay()
            assert connector.fetches == [], "request identity admission must precede ingestion"
        elif layout in {"missing", "shared_request_missing_source", "record_single_namespace"}:
            with pytest.raises(MissingFixtureError, match="namespace"):
                replay()
            assert connector.fetches == [], "a declared missing source is known before ingestion"
        elif layout == "cross_source_request":
            with pytest.raises(MissingFixtureError, match="namespace"):
                replay()
            assert connector.fetches == ["left", "right"]
            assert connector.responses == {"left": [{"marker": "recorded-left", "value": 0}]}
        elif layout == "missing_warm_cache":
            with pytest.raises(MissingFixtureError):
                replay()
            assert connector.fetches == ["left"]
        elif layout == "warm_cache_refuses_bypass":
            with pytest.raises(
                ValueError, match="record_replay_connector_cache_bypass_unavailable"
            ):
                replay()
            assert connector.fetches == []
        elif layout in {"corrupt", "warm_cache_corrupt"}:
            with pytest.raises(json.JSONDecodeError):
                replay()
            assert connector.fetches == ["left", "right"]
        else:
            result = replay()
            assert result.mode_effective == "replay" and result.datasets_fetched == 2
            assert result.evidence_bundle_ref is not None
            fresh = FileSystemCAS(cas_root)
            bundle = EvidenceBundle.model_validate(
                from_canonical_bytes(fresh.get_bytes(result.evidence_bundle_ref.artifact_id))
            )
            assert bundle.provenance_ref is not None
            context = bundle.execution_context
            assert context is not None and context.mode == "replay"
            assert context.capture_session_id == record_session.session_id
            selected_session = context.selected_record_session_ref
            assert selected_session is not None
            assert selected_session.artifact_id == session_ref.artifact_id
            assert selected_session.manifest_profile_sha256 is not None
            selected_provenance = ArtifactRef(
                artifact_id=ArtifactID.model_validate(bundle.provenance_ref.artifact_id),
                kind="fabric.provenance_graph",
                media_type="application/json",
                manifest_profile_sha256=bundle.provenance_ref.manifest_profile_sha256,
            )
            assert selected_provenance.manifest_profile_sha256 is not None
            provenance = from_canonical_bytes(fresh.get_bytes(selected_provenance))
            assert provenance["metadata"]["source"] == "agency"
            assert provenance["metadata"]["execution_mode"] == "replay"
            assert provenance["activities"][0]["parameters"]["execution_context"] == (
                context.model_dump(mode="json")
            )
            from polisyos.fabric.evidence import load_provenance_graph
            from polisyos.fabric.provenance.core import ProvenanceCoreRef

            fresh_graph = load_provenance_graph(
                fresh, ProvenanceCoreRef.from_dict(bundle.provenance_ref.model_dump())
            )
            assert fresh_graph.metadata["execution_mode"] == "replay"
            for emitted_ref in [result.evidence_bundle_ref, selected_provenance, *bundle.sources]:
                emitted_manifest = fresh.get_manifest(emitted_ref)
                session_inputs = [
                    edge
                    for edge in emitted_manifest.inputs
                    if edge.role == "fabric.ingestion.record_session"
                ]
                assert len(session_inputs) == 1
                assert session_inputs[0].artifact_id == selected_session.artifact_id
                assert session_inputs[0].manifest_profile_sha256 == (
                    selected_session.manifest_profile_sha256
                )
            payloads = [fresh.get_bytes(ref.artifact_id) for ref in bundle.sources]
            for name in ("left", "right"):
                assert sum(f"recorded-{name}".encode() in payload for payload in payloads) == 1
            assert connector.responses == {
                "left": [{"marker": "recorded-left", "value": 0}],
                "right": [{"marker": "recorded-right", "value": 1}],
            }
            assert connector.fetches == ["left", "right"]
        assert native_calls == [] and ordinary_calls == []
        if cache is not None:
            assert isinstance(registry.get(connector_id), CachingConnectorProxy)
            assert _get_fetch_source_namespace() is None

    finally:
        registry.shutdown()
        if cache is not None:
            cache.close()


@pytest.mark.asyncio
async def test_replay_namespace_map_is_frozen_and_unknown_hash_has_no_default_fallback(
    tmp_path: Path,
) -> None:
    """Mutation and a populated default directory cannot redirect admitted replay."""
    import aiohttp

    url = "https://namespace-replay.invalid/admitted"
    request_hash = _request_hash("GET", _canonicalize_url(url), "none", b"")
    namespace_map = {request_hash: ("declared", "rows")}
    fixture = SimulatorFixture(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body=base64.b64encode(b'{"marker":"admitted"}').decode("ascii"),
        captured_at="2026-10-01T00:00:00+00:00",
        request_url=url,
        request_method="GET",
        request_hash=request_hash,
        connector_id="declared",
        dataset_id="rows",
    )
    fixture.write(tmp_path / "declared" / "rows" / f"{request_hash}.json")
    simulator = APISimulator(
        fixture_root=tmp_path,
        connector_id="default",
        dataset_id="rows",
        fixture_namespaces=namespace_map,
    )
    namespace_map[request_hash] = ("default", "rows")
    unknown_url = "https://namespace-replay.invalid/unknown"
    unknown_hash = _request_hash("GET", _canonicalize_url(unknown_url), "none", b"")
    namespace_map[unknown_hash] = ("default", "rows")
    # This real fixture is deliberately outside the frozen admitted map.
    fixture.write(tmp_path / "default" / "rows" / f"{unknown_hash}.json")

    async with simulator, aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert await response.json() == {"marker": "admitted"}
        with pytest.raises(MissingFixtureError, match="namespace"):
            async with session.get(unknown_url):
                pytest.fail("unknown hash reached a default namespace fixture")


@pytest.mark.asyncio
async def test_recorded_post_identity_reconciles_actual_canonical_body_and_source_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actual local HTTP capture persists a body-bound request and replays without egress."""
    import aiohttp
    from aiohttp import web

    from polisyos.fabric.connectors import base as connector_base

    observed: list[tuple[str, list[tuple[str, str]], object]] = []

    async def receive(request: web.Request) -> web.Response:
        body = await request.json()
        observed.append((request.method, list(request.query.items()), body))
        return web.json_response({"received": body})

    app = web.Application()
    app.router.add_post("/rows", receive)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None and site._server.sockets
    port = site._server.sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}/rows"
    body = {"b": 2, "a": "recorded"}
    fixture_root = tmp_path / "fixtures"
    try:
        simulator = APISimulator(mode=SimulatorMode.RECORD, fixture_root=fixture_root)
        with connector_base._bind_fetch_source_namespace("actual-source", "actual-dataset"):
            async with simulator, aiohttp.ClientSession() as client:
                async with client.post(url, json=body, params={"q": "one"}) as response:
                    assert await response.json() == {"received": body}
        assert observed == [("POST", [("q", "one")], body)]
        fixtures = collect_fixtures_from_dir(fixture_root)
        assert len(fixtures) == 1
        recorded = SimulatorFixture.from_dict(fixtures[0])
        assert (recorded.connector_id, recorded.dataset_id) == ("actual-source", "actual-dataset")
        assert recorded.request_body_kind == "json"
        assert base64.b64decode(recorded.request_body, validate=True) == b'{"a":"recorded","b":2}'

        async def forbid_native(*args: object, **kwargs: object) -> None:
            del args, kwargs
            pytest.fail("replay attempted native egress")

        monkeypatch.setattr(aiohttp.ClientSession, "_request", forbid_native)
        replay = APISimulator(
            fixture_root=fixture_root,
            connector_id="actual-source",
            dataset_id="actual-dataset",
        )
        async with replay, aiohttp.ClientSession() as client:
            async with client.post(
                url, json={"a": "recorded", "b": 2}, params={"q": "one"}
            ) as response:
                assert await response.json() == {"received": body}
            with pytest.raises(MissingFixtureError):
                async with client.post(url, json={"a": "changed", "b": 2}, params={"q": "one"}):
                    pytest.fail("changed request body consumed the recorded response")
        assert observed == [("POST", [("q", "one")], body)]
        assert connector_base._get_fetch_source_namespace() is None
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_record_namespace_escape_refuses_before_native_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import aiohttp

    from polisyos.fabric.connectors.base import _bind_fetch_source_namespace
    from polisyos.fabric.connectors.testing.simulator import ReplayFixtureIdentityError

    native_calls: list[bool] = []

    async def forbidden_native(*args: object, **kwargs: object):
        del args, kwargs
        native_calls.append(True)
        raise AssertionError("unsupported fixture namespace reached native transport")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", forbidden_native)
    simulator = APISimulator(
        mode=SimulatorMode.RECORD,
        fixture_root=tmp_path / "fixtures",
        require_source_namespace=True,
    )
    async with simulator:
        with _bind_fetch_source_namespace("later-source", "../../owned-outside"):
            async with aiohttp.ClientSession() as client:
                with pytest.raises(ReplayFixtureIdentityError, match="fixture_root"):
                    await client.get("https://fixture.invalid/rows")
    assert native_calls == [] and simulator.call_count == 0


def test_record_mode_admits_later_namespace_before_any_ingestion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.fabric.connectors.testing.simulator import ReplayFixtureIdentityError
    from polisyos.fabric.data_plane.modes import run_record_mode

    calls: list[bool] = []

    def forbidden_ingestion(**kwargs: object):
        del kwargs
        calls.append(True)
        raise AssertionError("unsupported later source partially executed")

    monkeypatch.setattr("polisyos.fabric.ingestion.run_connectors_ingestion", forbidden_ingestion)
    with pytest.raises(ReplayFixtureIdentityError, match="fixture_root"):
        run_record_mode(
            connector_manifest={
                "datasets": [
                    {"connector_id": "first", "dataset_id": "rows"},
                    {"connector_id": "later", "dataset_id": "../../owned-outside"},
                ]
            },
            source="agency",
            license_name="MIT",
            cas_root=tmp_path / "cas",
            ingestion_dependencies=resolve_ingestion_dependencies(registry=ConnectorRegistry()),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_generic_rest_record_and_fresh_replay_scope_health_and_both_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unmodified REST health and fetch methods cross actual record/session/replay owners."""
    import aiohttp
    from aiohttp import web

    from polisyos.fabric.connectors import pool as pool_module
    from polisyos.fabric.connectors.base import _get_fetch_source_namespace
    from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector
    from polisyos.fabric.data_plane.modes import run_record_mode

    class LeftREST(GenericRESTConnector):
        connector_id: ClassVar[str] = "local_record_left"
        metadata: ClassVar[ConnectorMetadataSpec] = GenericRESTConnector.metadata.model_copy(
            update={"connector_id": "local_record_left", "namespace": "test"}
        )

    class RightREST(GenericRESTConnector):
        connector_id: ClassVar[str] = "local_record_right"
        metadata: ClassVar[ConnectorMetadataSpec] = GenericRESTConnector.metadata.model_copy(
            update={"connector_id": "local_record_right", "namespace": "test"}
        )

    observed: list[tuple[str, list[tuple[str, str]]]] = []

    async def receive(request: web.Request) -> web.Response:
        name = request.match_info["source"]
        query = list(request.query.items())
        observed.append((name, query))
        rows = [] if not query else [{"marker": f"actual-{name}", "value": 1}]
        return web.json_response({"data": rows})

    app = web.Application()
    app.router.add_get("/{source}", receive)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None and site._server.sockets
    port = site._server.sockets[0].getsockname()[1]
    actual_pool_config = pool_module.PoolConfig
    monkeypatch.setattr(
        pool_module,
        "PoolConfig",
        lambda **kwargs: actual_pool_config(**kwargs, acquire_timeout_seconds=0.2),
    )
    registries: list[ConnectorRegistry] = []

    def registry_and_manifest() -> tuple[ConnectorRegistry, dict[str, Any]]:
        registry = ConnectorRegistry()
        registries.append(registry)
        pairs = []
        for name, connector_class in (("left", LeftREST), ("right", RightREST)):
            connector_id = registry.register(
                connector_class,
                config=ConnectionConfig(
                    url=f"http://127.0.0.1:{port}/{name}",
                    timeout_seconds=1.0,
                    headers={"X-REST-PageSize": "2", "X-REST-PageSizeParam": "per_page"},
                ),
            )
            pairs.append({"connector_id": connector_id, "dataset_id": "rows"})
        return registry, {"datasets": pairs}

    cas_root = tmp_path / "cas"
    original_save_session = ReplayStore.save_record_session
    legacy_views: list[ArtifactRef] = []

    def save_after_same_payload_legacy(self, session, **kwargs):
        from polisyos.core.artifacts import PutOptions, SchemaInfo
        from polisyos.core.canon import CanonSpec

        legacy_views.append(
            FileSystemCAS(cas_root).put_json(
                session.to_dict(),
                PutOptions(
                    kind="fabric.record_session",
                    media_type="application/json",
                    schema=SchemaInfo(name="polisyos.fabric.RecordSession", version="1.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        )
        return original_save_session(self, session, **kwargs)

    monkeypatch.setattr(ReplayStore, "save_record_session", save_after_same_payload_legacy)
    try:
        record_registry, manifest = registry_and_manifest()
        recorded, replay_ref = await asyncio.to_thread(
            run_record_mode,
            connector_manifest=manifest,
            source="agency",
            license_name="MIT",
            cas_root=cas_root,
            produce_snapshot=False,
            ingestion_dependencies=resolve_ingestion_dependencies(registry=record_registry),
        )
        assert recorded.mode_effective == "record" and recorded.evidence_bundle_ref is not None
        selected_session = recorded.record_session_selected_ref
        assert selected_session is not None
        assert selected_session.artifact_id == legacy_views[0].artifact_id
        assert selected_session.manifest_profile_sha256 != (legacy_views[0].manifest_profile_sha256)
        assert replay_ref is None, "legacy ID alone selects v1, not this producer's v2 view"
        assert recorded.record_session_ref is None
        expected_calls = [
            ("left", []),
            ("left", [("page", "1"), ("per_page", "2")]),
            ("right", []),
            ("right", [("page", "1"), ("per_page", "2")]),
        ]
        assert observed == expected_calls
        session = ReplayStore(FileSystemCAS(cas_root)).load_record_session(selected_session)
        assert len(session.fixtures) == 4
        for pair in manifest["datasets"]:
            own = [
                fixture
                for fixture in session.fixtures
                if fixture["connector_id"] == pair["connector_id"]
            ]
            assert len(own) == 2 and all(fixture["dataset_id"] == "rows" for fixture in own)

        async def forbid_native(*args: object, **kwargs: object) -> None:
            del args, kwargs
            pytest.fail("fresh REST replay attempted native egress")

        monkeypatch.setattr(aiohttp.ClientSession, "_request", forbid_native)
        replay_registry, replay_manifest = registry_and_manifest()
        replayed = await asyncio.to_thread(
            run_replay_mode,
            connector_manifest=replay_manifest,
            source="agency",
            license_name="MIT",
            cas_root=cas_root,
            replay_ref=selected_session,
            produce_snapshot=False,
            ingestion_dependencies=resolve_ingestion_dependencies(registry=replay_registry),
        )
        assert replayed.mode_effective == "replay" and replayed.datasets_fetched == 2
        assert observed == expected_calls
        assert replayed.evidence_bundle_ref is not None
        fresh = FileSystemCAS(cas_root)
        bundle = EvidenceBundle.model_validate(
            from_canonical_bytes(fresh.get_bytes(replayed.evidence_bundle_ref.artifact_id))
        )
        payloads = [fresh.get_bytes(ref.artifact_id) for ref in bundle.sources]
        assert sum(b"actual-left" in payload for payload in payloads) == 1
        assert sum(b"actual-right" in payload for payload in payloads) == 1
        assert fresh.get_manifest(selected_session).artifact_schema.version == "2.0"
        assert fresh.get_manifest(selected_session.artifact_id).artifact_schema.version == "1.0"
        assert bundle.execution_context is not None
        assert bundle.execution_context.selected_record_session_ref == selected_session
        recorded_bundle = EvidenceBundle.model_validate(
            from_canonical_bytes(fresh.get_bytes(recorded.evidence_bundle_ref))
        )
        assert recorded_bundle.execution_context is not None
        assert recorded_bundle.execution_context.mode == "record"
        assert recorded_bundle.execution_context.capture_session_id == session.session_id
        assert recorded_bundle.execution_context.selected_record_session_ref is None
        session_inputs = fresh.get_manifest(selected_session).inputs
        assert any(
            edge.artifact_id == recorded.evidence_bundle_ref.artifact_id
            and edge.manifest_profile_sha256 == recorded.evidence_bundle_ref.manifest_profile_sha256
            for edge in session_inputs
        )
        assert _get_fetch_source_namespace() is None
    finally:
        for registry in registries:
            await registry.shutdown_async()
        await runner.cleanup()
