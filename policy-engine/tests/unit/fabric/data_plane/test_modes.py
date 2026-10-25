"""Tests for data-plane execution modes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any, cast

import pytest

from polisyos.core.artifacts.manifest import ArtifactID
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.contracts import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)


def _fake_evidence_ref() -> SimpleNamespace:
    return SimpleNamespace(artifact_id=SimpleNamespace(hex="evidence-ref"))


def test_cursor_aware_registry_preserves_omitted_and_explicit_arguments() -> None:
    """Default-valued arguments retain presence when forwarded to the owner."""
    from polisyos.fabric.data_plane.modes import (
        _ArgumentNotProvided,
        _CursorAwareRegistry,
    )
    from polisyos.fabric.ingestion.ingestion_providers import _BatchConnectorRegistry

    get_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    connection_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    connector = SimpleNamespace(fetch=lambda *_args, **_kwargs: None)

    class RecordingRegistry:
        def get(self, *args: object, **kwargs: object) -> object:
            get_calls.append((args, dict(kwargs)))
            return connector

        async def get_connection(self, *args: object, **kwargs: object) -> object:
            connection_calls.append((args, dict(kwargs)))
            return object()

    proxy = _CursorAwareRegistry(cast("_BatchConnectorRegistry", RecordingRegistry()), {})
    proxy.get("omitted")
    proxy.get(
        "explicit-defaults",
        None,
        enable_cache=True,
        _registration_binding=None,
    )
    proxy.get(
        "explicit-keyword-defaults",
        version=None,
        enable_cache=True,
        _registration_binding=None,
    )
    binding = object()
    proxy.get(
        "non-defaults",
        "v2",
        enable_cache=False,
        _registration_binding=binding,
    )
    sentinel_instance = _ArgumentNotProvided()
    proxy.get(
        "sentinel-instance",
        sentinel_instance,
        enable_cache=sentinel_instance,
        _registration_binding=sentinel_instance,
    )

    connection_config = object()

    async def _get_connections() -> None:
        await proxy.get_connection("omitted")
        await proxy.get_connection("explicit-defaults", None, _registration_binding=None)
        await proxy.get_connection(
            "explicit-keyword-defaults", config=None, _registration_binding=None
        )
        await proxy.get_connection("non-defaults", connection_config, _registration_binding=binding)
        await proxy.get_connection(
            "sentinel-instance",
            sentinel_instance,
            _registration_binding=sentinel_instance,
        )

    asyncio.run(_get_connections())

    assert get_calls == [
        (("omitted",), {}),
        (
            ("explicit-defaults", None),
            {"enable_cache": True, "_registration_binding": None},
        ),
        (
            ("explicit-keyword-defaults", None),
            {"enable_cache": True, "_registration_binding": None},
        ),
        (
            ("non-defaults", "v2"),
            {"enable_cache": False, "_registration_binding": binding},
        ),
        (("sentinel-instance",), {}),
    ]
    assert connection_calls == [
        (("omitted",), {}),
        (("explicit-defaults", None), {"_registration_binding": None}),
        (("explicit-keyword-defaults", None), {"_registration_binding": None}),
        (("non-defaults", connection_config), {"_registration_binding": binding}),
        (("sentinel-instance",), {}),
    ]


def test_cursor_aware_registry_keeps_narrow_sibling_defaults_compatible() -> None:
    """Omitted defaults work with narrow registries while explicit values remain supplied."""
    from polisyos.fabric.data_plane.modes import _CursorAwareRegistry
    from polisyos.fabric.ingestion.ingestion_providers import _BatchConnectorRegistry

    connector = SimpleNamespace(fetch=lambda *_args, **_kwargs: None)

    class NarrowSiblingRegistry:
        def get(self, connector_id: str) -> object:
            del connector_id
            return connector

        async def get_connection(self, connector_id: str) -> object:
            del connector_id
            return object()

    proxy = _CursorAwareRegistry(cast("_BatchConnectorRegistry", NarrowSiblingRegistry()), {})
    proxy.get("sibling")
    asyncio.run(proxy.get_connection("sibling"))

    with pytest.raises(TypeError):
        proxy.get("sibling", enable_cache=True)
    with pytest.raises(TypeError):
        asyncio.run(proxy.get_connection("sibling", None))


def test_manifest_dataset_absence_and_explicit_empty_are_valid() -> None:
    from polisyos.fabric.ingestion import ConnectorManifestSpec

    assert ConnectorManifestSpec.from_mapping({}).datasets == []
    assert ConnectorManifestSpec.from_mapping({"datasets": []}).datasets == []


@pytest.mark.parametrize(
    "manifest",
    [
        {"datasets": None},
        {"datasets": ({"connector_id": "c", "dataset_id": "d"},)},
        {"datasets": [None]},
        {"datasets": [{"connector_id": "c"}]},
        {"datasets": [{"connector_id": "c", "dataset_id": "d", "filters": None}]},
        {"datasets": [{"connector_id": "c", "dataset_id": "d", "filters": []}]},
        {"datasets": [{"connector_id": "c", "dataset_id": "d"}], "retry_policy": []},
        {
            "datasets": [{"connector_id": "c", "dataset_id": "d"}],
            "allow_local_transform_dag": None,
        },
    ],
)
def test_manifest_parser_rejects_present_malformed_datasets(manifest: object) -> None:
    from polisyos.fabric.ingestion import ConnectorManifestSpec

    with pytest.raises(ValueError, match="connector manifest"):
        ConnectorManifestSpec.from_mapping(manifest)  # type: ignore[arg-type]


def test_manifest_dataset_mapping_carriers_use_one_parser(tmp_path: Path) -> None:
    from polisyos.fabric.data_plane.modes import _extract_datasets
    from polisyos.fabric.ingestion import ConnectorManifestSpec

    payload = {"datasets": [{"connector_id": " c ", "dataset_id": " d "}]}
    expected = [("c", "d")]
    mapping = MappingProxyType({"datasets": [MappingProxyType(payload["datasets"][0])]})
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    spec = ConnectorManifestSpec.from_mapping(payload)

    assert _extract_datasets(mapping) == expected
    assert _extract_datasets(manifest_path) == expected
    assert _extract_datasets(str(manifest_path)) == expected
    assert _extract_datasets(spec) == expected

    manifest_path.write_text('{"datasets": null}', encoding="utf-8")
    with pytest.raises(ValueError, match="datasets"):
        _extract_datasets(manifest_path)
    with pytest.raises(ValueError, match="datasets"):
        _extract_datasets(str(manifest_path))


def test_manifest_wrapper_rejects_present_non_mapping() -> None:
    from polisyos.fabric.ingestion.ingestion import _normalize_connector_manifest

    for invalid_wrapper in (None, []):
        with pytest.raises(ValueError, match="connector_manifest"):
            _normalize_connector_manifest({"connector_manifest": invalid_wrapper})


def test_manifest_accepts_valid_optional_filter_and_retry_values() -> None:
    from polisyos.fabric.ingestion import ConnectorManifestSpec

    spec = ConnectorManifestSpec.from_mapping(
        {
            "datasets": [
                {
                    "connector_id": "c",
                    "dataset_id": "d",
                    "filters": {"year": 2024},
                }
            ],
            "retry_policy": None,
            "allow_local_transform_dag": "false",
        }
    )
    assert spec.datasets[0].filters == {"year": ["2024"]}
    assert spec.retry_policy is None
    assert spec.allow_local_transform_dag is False


@pytest.mark.parametrize(
    "manifest",
    [
        {"streaming": None},
        {"streaming": []},
        {"streaming": {"window": None}, "streaming_window": {"strategy": "count"}},
        {"streaming_window": None},
        {"streaming": {"window": {"strategy": "not-a-window"}}},
    ],
)
def test_streaming_runtime_options_reject_present_malformed_metadata(
    manifest: dict[str, object],
) -> None:
    from polisyos.fabric.data_plane.modes import _stream_runtime_options_from_manifest

    with pytest.raises(ValueError):
        _stream_runtime_options_from_manifest(manifest)


def test_streaming_runtime_options_keep_absent_and_valid_window_semantics() -> None:
    from polisyos.core.contracts.cursor import WindowStrategy
    from polisyos.fabric.data_plane.modes import _stream_runtime_options_from_manifest

    assert (
        _stream_runtime_options_from_manifest({}).window_policy.strategy == WindowStrategy.TUMBLING
    )
    assert (
        _stream_runtime_options_from_manifest(
            {"streaming_window": {"strategy": "count", "size": 5}}
        ).window_policy.size
        == 5
    )


@pytest.mark.parametrize("mode", ["batch", "record", "replay", "streaming"])
def test_ingestion_modes_refuse_malformed_manifest_before_setup(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.fabric.data_plane import modes

    def _setup_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("malformed input reached setup before manifest validation")

    monkeypatch.setattr(modes, "_resolve_ingestion_dependencies", _setup_must_not_run)
    if mode == "streaming":
        monkeypatch.setattr(modes, "run_coro_sync", asyncio.run)

    mode_call = {
        "batch": modes.run_batch_incremental,
        "record": modes.run_record_mode,
        "replay": modes.run_replay_mode,
        "streaming": modes.run_streaming_windowed,
    }[mode]
    kwargs: dict[str, object] = {
        "connector_manifest": {"datasets": None},
        "source": "test",
        "license_name": "MIT",
        "cas_root": tmp_path / ".polisyos",
    }
    if mode == "replay":
        kwargs["replay_ref"] = "invalid-replay-ref"

    with pytest.raises(ValueError, match="datasets"):
        mode_call(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("mode", ["record", "replay"])
def test_record_and_replay_refuse_malformed_connection_config_before_setup(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.fabric.data_plane import modes

    def _setup_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("malformed connection config reached setup before validation")

    monkeypatch.setattr(modes, "_resolve_ingestion_dependencies", _setup_must_not_run)
    malformed_config: dict[str, object] = {"__unknown_connection_config_field__": True}
    if mode == "record":

        def call() -> object:
            return modes.run_record_mode(
                connector_manifest={"datasets": []},
                source="test",
                license_name="MIT",
                cas_root=tmp_path / ".polisyos",
                connection_config=malformed_config,
            )
    else:

        def call() -> object:
            return modes.run_replay_mode(
                connector_manifest={"datasets": []},
                source="test",
                license_name="MIT",
                cas_root=tmp_path / ".polisyos",
                replay_ref="invalid-replay-ref",
                connection_config=malformed_config,
            )

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        call()


@pytest.mark.parametrize("mode", ["batch", "record", "replay", "streaming"])
def test_ingestion_modes_refuse_structured_filter_before_setup(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.fabric.data_plane import modes

    def _setup_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("malformed filter reached setup before manifest validation")

    monkeypatch.setattr(modes, "_resolve_ingestion_dependencies", _setup_must_not_run)
    if mode == "streaming":
        monkeypatch.setattr(modes, "run_coro_sync", asyncio.run)

    mode_call = {
        "batch": modes.run_batch_incremental,
        "record": modes.run_record_mode,
        "replay": modes.run_replay_mode,
        "streaming": modes.run_streaming_windowed,
    }[mode]
    kwargs: dict[str, object] = {
        "connector_manifest": {
            "datasets": [
                {
                    "connector_id": "test.connector",
                    "dataset_id": "raw.dataset",
                    "filters": {"country": {"nested": "value"}},
                }
            ]
        },
        "source": "test",
        "license_name": "MIT",
        "cas_root": tmp_path / ".polisyos",
    }
    if mode == "replay":
        kwargs["replay_ref"] = "invalid-replay-ref"

    with pytest.raises(ValueError, match="filter"):
        mode_call(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("mode", ["batch", "record", "replay", "streaming"])
@pytest.mark.parametrize("json_number", ["NaN", "Infinity", "-Infinity", "1e9999"])
@pytest.mark.parametrize("container", ["scalar", "list"])
def test_ingestion_modes_refuse_non_finite_json_filters_before_setup(
    mode: str,
    json_number: str,
    container: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.fabric.data_plane import modes

    def _setup_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("non-finite filter reached setup before manifest validation")

    monkeypatch.setattr(modes, "_resolve_ingestion_dependencies", _setup_must_not_run)
    if mode == "streaming":
        monkeypatch.setattr(modes, "run_coro_sync", asyncio.run)

    mode_call = {
        "batch": modes.run_batch_incremental,
        "record": modes.run_record_mode,
        "replay": modes.run_replay_mode,
        "streaming": modes.run_streaming_windowed,
    }[mode]
    filter_value = f"[{json_number}]" if container == "list" else json_number
    manifest_path = tmp_path / "non-finite-filter.json"
    manifest_path.write_text(
        '{"datasets":[{"connector_id":"test.connector",'
        f'"dataset_id":"raw.dataset","filters":{{"year":{filter_value}}}'
        "}]}",
        encoding="utf-8",
    )
    kwargs: dict[str, object] = {
        "connector_manifest": manifest_path,
        "source": "test",
        "license_name": "MIT",
        "cas_root": tmp_path / ".polisyos",
    }
    if mode == "replay":
        kwargs["replay_ref"] = "invalid-replay-ref"

    with pytest.raises(ValueError, match="filter"):
        mode_call(**kwargs)  # type: ignore[arg-type]


def test_streaming_mode_refuses_malformed_metadata_before_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.fabric.data_plane import modes

    def _setup_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("malformed metadata reached setup before validation")

    monkeypatch.setattr(modes, "_resolve_ingestion_dependencies", _setup_must_not_run)
    monkeypatch.setattr(modes, "run_coro_sync", asyncio.run)

    with pytest.raises(ValueError, match="streaming"):
        modes.run_streaming_windowed(
            connector_manifest={"datasets": [], "streaming": None},
            source="test",
            license_name="MIT",
            cas_root=tmp_path / ".polisyos",
        )


class _NoopSimulator:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def __aenter__(self) -> _NoopSimulator:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class _ReplayStoreStub:
    def __init__(self, store: object) -> None:
        self._store = store

    def save_record_session(self, session: object) -> SimpleNamespace:
        del session
        return SimpleNamespace(artifact_id=ArtifactID.model_validate("sha256:" + "b" * 64))

    def load_record_session(self, artifact_id: object) -> object:
        del artifact_id
        return {"session": "replay"}

    def build_replay_fixture_dir(self, session: object, fixture_dir: object) -> None:
        del session, fixture_dir


@pytest.mark.parametrize("config_kind", ["mapping", "subclass", "none"])
def test_run_record_mode_uses_shared_blocking_bridge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    config_kind: str,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    class _CustomConnectionConfig(ConnectionConfig):
        pass

    connection_config_input: ConnectionConfig | dict[str, object] | None
    if config_kind == "mapping":
        connection_config_input = {"url": "https://example.test"}
    elif config_kind == "subclass":
        connection_config_input = _CustomConnectionConfig(url="https://example.test")
    else:
        connection_config_input = None

    blocking_calls: list[str] = []
    seen_connection_configs: list[ConnectionConfig | None] = []

    async def _fake_run_blocking_async(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del timeout_seconds
        blocking_calls.append(getattr(func, "__name__", type(func).__name__))
        return func(*args, **kwargs)

    def _fake_run_connectors_ingestion(**kwargs: Any) -> SimpleNamespace:
        seen_connection_configs.append(kwargs["connection_config"])
        return _fake_evidence_ref()

    monkeypatch.setattr(modes_mod, "run_blocking_async", _fake_run_blocking_async)
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        _fake_run_connectors_ingestion,
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.testing.simulator.APISimulator",
        _NoopSimulator,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.make_record_session",
        lambda **kwargs: dict(kwargs),
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.ReplayStore",
        _ReplayStoreStub,
    )

    result, record_ref = modes_mod.run_record_mode(
        connector_manifest={
            "datasets": [
                {"connector_id": "test.integration_mock", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        connection_config=connection_config_input,
    )

    assert blocking_calls == ["_fake_run_connectors_ingestion"]
    assert len(seen_connection_configs) == 1
    observed_config = seen_connection_configs[0]
    if config_kind == "mapping":
        assert isinstance(observed_config, ConnectionConfig)
        assert observed_config.url == "https://example.test"
        assert connection_config_input == {"url": "https://example.test"}
    else:
        assert observed_config is connection_config_input
    assert result.mode_effective == "record"
    assert record_ref == "sha256:" + "b" * 64


@pytest.mark.parametrize("config_kind", ["mapping", "subclass", "none"])
def test_run_replay_mode_uses_shared_blocking_bridge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    config_kind: str,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    class _CustomConnectionConfig(ConnectionConfig):
        pass

    connection_config_input: ConnectionConfig | dict[str, object] | None
    if config_kind == "mapping":
        connection_config_input = {"url": "https://example.test"}
    elif config_kind == "subclass":
        connection_config_input = _CustomConnectionConfig(url="https://example.test")
    else:
        connection_config_input = None

    blocking_calls: list[str] = []
    seen_connection_configs: list[ConnectionConfig | None] = []

    async def _fake_run_blocking_async(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del timeout_seconds
        blocking_calls.append(getattr(func, "__name__", type(func).__name__))
        return func(*args, **kwargs)

    def _fake_run_connectors_ingestion(**kwargs: Any) -> SimpleNamespace:
        seen_connection_configs.append(kwargs["connection_config"])
        return _fake_evidence_ref()

    monkeypatch.setattr(modes_mod, "run_blocking_async", _fake_run_blocking_async)
    monkeypatch.setattr(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        _fake_run_connectors_ingestion,
    )
    monkeypatch.setattr(
        "polisyos.fabric.connectors.testing.simulator.APISimulator",
        _NoopSimulator,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.ReplayStore",
        _ReplayStoreStub,
    )

    result = modes_mod.run_replay_mode(
        connector_manifest={
            "datasets": [
                {"connector_id": "test.integration_mock", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        connection_config=connection_config_input,
        replay_ref="sha256:" + ("0" * 64),
    )

    assert blocking_calls == ["_fake_run_connectors_ingestion"]
    assert len(seen_connection_configs) == 1
    observed_config = seen_connection_configs[0]
    if config_kind == "mapping":
        assert isinstance(observed_config, ConnectionConfig)
        assert observed_config.url == "https://example.test"
        assert connection_config_input == {"url": "https://example.test"}
    else:
        assert observed_config is connection_config_input
    assert result.mode_effective == "replay"


def test_run_replay_mode_does_not_fallback_to_live_after_fixture_failure(
    monkeypatch,
    tmp_path,
) -> None:
    """A missing/corrupt replay fixture must not invoke ordinary ingestion."""
    from polisyos.fabric.data_plane import modes as modes_mod

    async def _fail_replay_ingestion(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del func, args, timeout_seconds, kwargs
        raise RuntimeError("replay fixture missing")

    live_calls: list[bool] = []

    def _live_delegate(**kwargs: Any) -> Any:
        del kwargs
        live_calls.append(True)
        raise AssertionError("ordinary ingestion must not run in replay mode")

    monkeypatch.setattr(modes_mod, "run_blocking_async", _fail_replay_ingestion)
    monkeypatch.setattr(
        "polisyos.fabric.connectors.testing.simulator.APISimulator",
        _NoopSimulator,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.replay_store.ReplayStore",
        _ReplayStoreStub,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
        _live_delegate,
    )

    with pytest.raises(RuntimeError, match="replay fixture missing"):
        modes_mod.run_replay_mode(
            connector_manifest={
                "datasets": [
                    {"connector_id": "test.integration_mock", "dataset_id": "events"},
                ],
            },
            source="test",
            license_name="MIT",
            cas_root=tmp_path / ".polisyos",
            replay_ref="sha256:" + ("0" * 64),
        )

    assert live_calls == []


def _make_real_replay_case(tmp_path, fixture_body: bytes | None):
    import base64
    from datetime import UTC, datetime
    from typing import cast

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
    from polisyos.fabric.connectors.testing.simulator import (
        SimulatorFixture,
        _canonicalize_url,
        _request_hash,
    )
    from polisyos.fabric.data_plane.replay_store import RecordSession, ReplayStore
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies
    from polisyos.ir.connectors import (
        DataVersion,
        FetchResult,
        QualityTier,
        VersionStrategy,
    )

    connector_id = "test.http_replay"
    dataset_id = "rows"
    url = "https://replay-fixture.invalid/data"
    canonical_url = _canonicalize_url(url, None)
    request_hash = _request_hash("GET", canonical_url, "none", b"")
    fixtures = []
    if fixture_body is not None:
        fixtures.append(
            SimulatorFixture(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=base64.b64encode(fixture_body).decode("ascii"),
                captured_at="2026-09-26T00:00:00+00:00",
                request_url=canonical_url,
                request_method="GET",
                request_hash=request_hash,
                connector_id=connector_id,
                dataset_id=dataset_id,
            ).to_dict()
        )
    cas_root = tmp_path / "cas"
    replay_ref = ReplayStore(FileSystemCAS(cas_root)).save_record_session(
        RecordSession(session_id="test-replay-session", fixtures=fixtures)
    )

    class _HTTPFixtureConnector:
        metadata = None

        async def fetch(self, handle, request):
            import aiohttp

            del request
            async with aiohttp.ClientSession() as session:
                async with session.get(handle.config.url) as response:
                    rows = await response.json()
            now = datetime.now(UTC)
            digest = "sha256:" + "a" * 64
            return FetchResult(
                data=rows,
                row_count=len(rows),
                schema_id="test.http-replay",
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

    class _Registry:
        def get(self, requested_connector_id: str) -> _HTTPFixtureConnector:
            assert requested_connector_id == connector_id
            return _HTTPFixtureConnector()

        async def get_connection(
            self,
            requested_connector_id: str,
            config: ConnectionConfig,
        ) -> ConnectionHandle:
            return ConnectionHandle(connector_id=requested_connector_id, config=config)

        async def release_connection(
            self,
            requested_connector_id: str,
            handle: ConnectionHandle,
        ) -> None:
            del requested_connector_id, handle

    return {
        "cas_root": cas_root,
        "replay_ref": str(replay_ref.artifact_id),
        "dependencies": resolve_ingestion_dependencies(registry=cast("Any", _Registry())),
        "connection_config": ConnectionConfig(url=url),
        "connector_id": connector_id,
        "dataset_id": dataset_id,
        "url": url,
        "canonical_url": canonical_url,
    }


def _capture_replay_boundaries(monkeypatch):
    import aiohttp

    from polisyos.fabric.connectors.testing import simulator as simulator_mod

    simulators = []
    native_requests: list[tuple[str, str]] = []
    ordinary_ingestion_calls: list[bool] = []
    actual_simulator = simulator_mod.APISimulator

    def _capture_simulator(**kwargs):
        simulator = actual_simulator(**kwargs)
        simulators.append(simulator)
        return simulator

    async def _forbid_native_request(self, method: str, url: str, **kwargs):
        del self, kwargs
        native_requests.append((method, url))
        raise AssertionError("native transport must not run outside replay simulation")

    def _ordinary_ingestion(**kwargs):
        del kwargs
        ordinary_ingestion_calls.append(True)
        raise AssertionError("replay must not call ordinary ingestion")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _forbid_native_request)
    monkeypatch.setattr(simulator_mod, "APISimulator", _capture_simulator)
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
        _ordinary_ingestion,
    )
    return simulators, native_requests, ordinary_ingestion_calls


@pytest.mark.parametrize(
    ("fixture_body", "expected_error"),
    [
        (None, "missing"),
        (b"not-json", "corrupt"),
    ],
    ids=["missing-fixture", "corrupt-fixture"],
)
def test_run_replay_mode_fixture_failure_stays_in_replay_transport(
    monkeypatch,
    tmp_path,
    fixture_body,
    expected_error,
) -> None:
    """Real replay owner fails closed through the simulator, without live egress."""
    import json

    from polisyos.fabric.connectors.testing.simulator import MissingFixtureError
    from polisyos.fabric.data_plane import modes as modes_mod

    case = _make_real_replay_case(tmp_path, fixture_body)
    simulators, native_requests, ordinary_calls = _capture_replay_boundaries(monkeypatch)
    error_type = MissingFixtureError if expected_error == "missing" else json.JSONDecodeError

    with pytest.raises(error_type):
        modes_mod.run_replay_mode(
            connector_manifest={
                "datasets": [
                    {
                        "connector_id": case["connector_id"],
                        "dataset_id": case["dataset_id"],
                    }
                ],
            },
            source="test",
            license_name="MIT",
            cas_root=case["cas_root"],
            replay_ref=case["replay_ref"],
            connection_config=case["connection_config"],
            produce_snapshot=False,
            ingestion_dependencies=case["dependencies"],
        )

    assert len(simulators) == 1
    assert simulators[0].call_count == 1
    assert simulators[0].call_log[0]["url"] == case["canonical_url"]
    assert native_requests == []
    assert ordinary_calls == []


def test_run_replay_mode_uses_recorded_bytes_without_native_transport(
    monkeypatch,
    tmp_path,
) -> None:
    """A real stored response is replayed through the same runtime owner."""
    from polisyos.fabric.data_plane import modes as modes_mod

    case = _make_real_replay_case(tmp_path, b'[{"value":7}]')
    simulators, native_requests, ordinary_calls = _capture_replay_boundaries(monkeypatch)
    result = modes_mod.run_replay_mode(
        connector_manifest={
            "datasets": [
                {
                    "connector_id": case["connector_id"],
                    "dataset_id": case["dataset_id"],
                },
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=case["cas_root"],
        replay_ref=case["replay_ref"],
        connection_config=case["connection_config"],
        produce_snapshot=False,
        ingestion_dependencies=case["dependencies"],
    )

    assert result.mode_effective == "replay"
    assert result.datasets_fetched == 1
    assert result.evidence_bundle_ref is not None
    assert len(simulators) == 1
    assert simulators[0].call_count == 1
    assert simulators[0].call_log[0]["url"] == case["canonical_url"]
    assert native_requests == []
    assert ordinary_calls == []


def test_run_streaming_windowed_legacy_path_uses_async_store_adapter(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
    from polisyos.fabric.data_plane import modes as modes_mod

    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: Any, canon_spec: Any = None):
        seen_kinds.append(str(opts.kind))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    async def _fake_fetch_stream_for_dataset_async(
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        del kwargs
        return [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": True,
                "data": [{"value": 1}],
            }
        ]

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)
    monkeypatch.setattr(modes_mod, "_connector_is_registered", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset_async",
        _fake_fetch_stream_for_dataset_async,
    )
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coro: asyncio.run(coro))

    result = modes_mod.run_streaming_windowed(
        connector_manifest={
            "datasets": [
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        produce_snapshot=False,
    )

    assert result.mode_effective == "streaming_windowed"
    assert "fabric.stream_chunk" in seen_kinds


def test_run_streaming_windowed_persists_manifest_and_snapshot_via_async_store_adapter(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
    from polisyos.fabric.data_plane import modes as modes_mod

    seen_kinds: list[str] = []
    original_put_json = AsyncArtifactStoreAdapter.put_json

    async def _tracked_put_json(self, obj: object, opts: Any, canon_spec: Any = None):
        seen_kinds.append(str(opts.kind))
        return await original_put_json(self, obj, opts, canon_spec=canon_spec)

    async def _fake_fetch_stream_for_dataset_async(
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        del kwargs
        return [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": True,
                "data": [{"value": 1}],
            }
        ]

    monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)
    monkeypatch.setattr(modes_mod, "_connector_is_registered", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset_async",
        _fake_fetch_stream_for_dataset_async,
    )
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coro: asyncio.run(coro))

    result = modes_mod.run_streaming_windowed(
        connector_manifest={
            "datasets": [
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        produce_snapshot=True,
    )

    assert result.mode_effective == "streaming_windowed"
    assert "fabric.streaming_run_manifest" in seen_kinds
    assert "fabric.data_snapshot" in seen_kinds


def test_run_streaming_windowed_legacy_path_uses_async_fetch_helper(
    monkeypatch,
    tmp_path,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    async_calls: list[tuple[str, str]] = []

    async def _fake_fetch_stream_for_dataset_async(
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        async_calls.append((kwargs["connector_id"], kwargs["dataset_id"]))
        return [
            {
                "chunk_index": 0,
                "row_count": 1,
                "is_first": True,
                "is_last": True,
                "data": [{"value": 1}],
            }
        ]

    monkeypatch.setattr(modes_mod, "_connector_is_registered", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset_async",
        _fake_fetch_stream_for_dataset_async,
    )
    monkeypatch.setattr(
        modes_mod,
        "_fetch_stream_for_dataset",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("legacy sync fetch helper should not run inside async path")
        ),
    )
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coro: asyncio.run(coro))

    result = modes_mod.run_streaming_windowed(
        connector_manifest={
            "datasets": [
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        produce_snapshot=False,
    )

    assert result.mode_effective == "streaming_windowed"
    assert async_calls == [("legacy.stream", "events")]


def test_connector_is_registered_uses_explicit_registry_without_default_helper(
    monkeypatch,
) -> None:
    from polisyos.fabric.data_plane import modes as modes_mod

    registry = SimpleNamespace(
        get_entry=lambda connector_id: {"connector_id": connector_id},
    )

    monkeypatch.setattr(
        modes_mod,
        "_default_connector_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )

    assert modes_mod._connector_is_registered("stream.injected", registry=registry) is True


def test_stream_sanitizer_optional_field_membership_is_independent_of_batch_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown-schema rows are not made poisonous by technical batching."""
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.streaming import iter_record_batches

    rows = [
        {"id": "a", "value": 1.0, "note": "first"},
        {"id": "b", "value": 2.0, "note": "second"},
        {"id": "c", "value": 3.0},
    ]
    quarantine_records: list[tuple[str, dict[str, Any]]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        quarantine_records.append((str(record.reason), dict(record.context)))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    async def _run(batch_size: int) -> tuple[list[str], int]:
        accepted_ids: list[str] = []
        quarantined = 0
        async for batch in iter_record_batches(rows, batch_size=batch_size):
            valid_rows, _warnings, batch_quarantined = modes_mod._sanitize_stream_rows(
                batch,
                connector_id="test.stream",
                dataset_id="events",
                store=object(),
                chunk_index=0,
            )
            accepted_ids.extend(str(row["id"]) for row in valid_rows)
            quarantined += batch_quarantined
        return accepted_ids, quarantined

    observed = {batch_size: asyncio.run(_run(batch_size)) for batch_size in (1, 3)}

    # Without an admitted schema, shape variance is diagnostic rather than
    # evidence that the minority row is a poison message.
    expected = (["a", "b", "c"], 0)
    assert observed[1] == expected
    assert observed[3] == expected
    assert quarantine_records == []


def _presence_schema() -> DataSchema:
    return DataSchema(
        schema_id="test.stream.events",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=False),
            FieldSpec(
                name="note",
                data_type=SchemaType.STRING,
                nullable=False,
                presence="optional",
            ),
        ),
        primary_key=("id",),
        required_completeness=0.0,
    )


def test_stream_sanitizer_bound_presence_accepts_missing_optional_and_rejects_null(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Optional absence is distinct from an explicit null value."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.data_plane import modes as modes_mod

    store = FileSystemCAS(tmp_path / "cas")
    records: list[tuple[str, dict[str, Any]]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        records.append((str(record.reason), dict(record.context)))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    valid_rows, _warnings, quarantined = modes_mod._sanitize_stream_rows(
        [
            {"id": "missing", "value": 1.0},
            {"id": "null", "value": 2.0, "note": None},
            {"id": "present", "value": 3.0, "note": "ok"},
        ],
        connector_id="test.stream",
        dataset_id="events",
        store=store,
        chunk_index=0,
        schema=_presence_schema(),
    )

    assert [row["id"] for row in valid_rows] == ["missing", "present"]
    assert quarantined == 1
    assert records == [
        (
            "poison_stream_message",
            {
                "chunk_index": 0,
                "row_index": 1,
                "non_nullable_fields": ["note"],
            },
        )
    ]


def test_stream_sanitizer_bound_presence_is_batch_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fixed contract, not batch majority, determines accepted membership."""
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.streaming import iter_record_batches

    rows = [
        {"id": "a", "value": 1.0, "note": "first"},
        {"id": "b", "value": 2.0, "note": "second"},
        {"id": "c", "value": 3.0},
    ]
    quarantine_records: list[dict[str, Any]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        quarantine_records.append(dict(record.context))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    async def _run(batch_size: int) -> tuple[list[str], int]:
        accepted_ids: list[str] = []
        quarantined = 0
        async for batch in iter_record_batches(rows, batch_size=batch_size):
            valid_rows, _warnings, batch_quarantined = modes_mod._sanitize_stream_rows(
                batch,
                connector_id="test.stream",
                dataset_id="events",
                store=object(),
                chunk_index=0,
                schema=_presence_schema(),
            )
            accepted_ids.extend(str(row["id"]) for row in valid_rows)
            quarantined += batch_quarantined
        return accepted_ids, quarantined

    observed = {batch_size: asyncio.run(_run(batch_size)) for batch_size in (1, 3)}

    assert observed == {1: (["a", "b", "c"], 0), 3: (["a", "b", "c"], 0)}
    assert quarantine_records == []


def test_stream_sanitizer_bound_presence_rejects_missing_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A required field omission remains a quarantined schema violation."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.data_plane import modes as modes_mod

    store = FileSystemCAS(tmp_path / "cas")
    records: list[dict[str, Any]] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        records.append(dict(record.context))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    valid_rows, _warnings, quarantined = modes_mod._sanitize_stream_rows(
        [{"id": "missing-value"}, {"id": "valid", "value": 1.0}],
        connector_id="test.stream",
        dataset_id="events",
        store=store,
        chunk_index=2,
        schema=_presence_schema(),
    )

    assert [row["id"] for row in valid_rows] == ["valid"]
    assert quarantined == 1
    assert records == [
        {
            "chunk_index": 2,
            "row_index": 0,
            "missing_required_fields": ["value"],
        }
    ]


def test_stream_sanitizer_keeps_non_finite_metric_guard_across_batch_sizes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Batch invariance must not weaken quarantine of non-finite metrics."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.streaming import iter_record_batches

    rows = [
        {"id": "ok", "value": 1.0},
        {"id": "bad", "value": float("nan")},
    ]
    store = FileSystemCAS(tmp_path / "cas")
    quarantine_reasons: list[str] = []

    def _capture_quarantine(
        store: Any,
        *,
        record: Any,
        raw_payload: Any | None = None,
        **kwargs: Any,
    ) -> None:
        del store, raw_payload, kwargs
        quarantine_reasons.append(str(record.reason))

    monkeypatch.setattr(modes_mod, "persist_quarantine_record", _capture_quarantine)

    async def _run(batch_size: int) -> tuple[list[str], int]:
        accepted_ids: list[str] = []
        quarantined = 0
        async for batch in iter_record_batches(rows, batch_size=batch_size):
            valid_rows, _warnings, batch_quarantined = modes_mod._sanitize_stream_rows(
                batch,
                connector_id="test.stream",
                dataset_id="events",
                store=store,
                chunk_index=0,
                schema=_presence_schema(),
            )
            accepted_ids.extend(str(row["id"]) for row in valid_rows)
            quarantined += batch_quarantined
        return accepted_ids, quarantined

    observed = {batch_size: asyncio.run(_run(batch_size)) for batch_size in (1, 3)}

    assert observed == {1: (["ok"], 1), 3: (["ok"], 1)}
    assert quarantine_reasons == ["non_finite_metric", "non_finite_metric"]


def test_fetch_stream_sync_bridge_preserves_typed_chunk_shape(monkeypatch) -> None:
    """The sync adapter returns the producer metadata and rows without reshaping."""
    from polisyos.fabric.data_plane import modes as modes_mod

    chunk: modes_mod._LegacyStreamChunk = {
        "chunk_index": 4,
        "row_count": 1,
        "is_first": True,
        "is_last": True,
        "data": [{"value": 3}],
    }

    async def _fetch(**_kwargs: object) -> list[modes_mod._LegacyStreamChunk]:
        return [chunk]

    monkeypatch.setattr(modes_mod, "_fetch_stream_for_dataset_async", _fetch)
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coro: asyncio.run(coro))

    result = modes_mod._fetch_stream_for_dataset(
        connector_id="legacy.stream",
        dataset_id="events",
        connector_manifest={},
        connection_config=None,
    )

    assert result == [chunk]
    assert result[0] is chunk


def test_fetch_stream_uses_registry_owned_connection_and_connector() -> None:
    """Streaming fetch and connection lifetime stay with the registry owner."""
    import asyncio

    from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
    from polisyos.fabric.connectors.types import DataChunk
    from polisyos.fabric.data_plane.modes import _fetch_stream_for_dataset_async
    from polisyos.ir.connectors import ConnectorCapability

    events: list[tuple[str, object]] = []
    config = ConnectionConfig(url="https://stream.test")
    handle = ConnectionHandle(connector_id="owner.stream", config=config)

    class SelectedConnector:
        capabilities = ConnectorCapability.STREAMING

        def fetch_stream(self, actual_handle: object, request: object):
            events.append(("fetch_stream", actual_handle))

            async def _chunks():
                yield DataChunk(
                    data=[{"value": 3}],
                    chunk_index=4,
                    row_count=1,
                    is_first=True,
                    is_last=True,
                )

            return _chunks()

    selected = SelectedConnector()

    class Registry:
        def get(self, connector_id: str) -> SelectedConnector:
            events.append(("get", connector_id))
            return selected

        def get_entry(self, connector_id: str) -> object:
            events.append(("get_entry", connector_id))
            return object()

        async def get_connection(
            self,
            connector_id: str,
            config: ConnectionConfig | None = None,
        ) -> ConnectionHandle:
            events.append(("get_connection", config))
            return handle

        async def release_connection(
            self,
            connector_id: str,
            actual_handle: ConnectionHandle,
        ) -> None:
            events.append(("release_connection", actual_handle))

    result = asyncio.run(
        _fetch_stream_for_dataset_async(
            connector_id="owner.stream",
            dataset_id="events",
            connector_manifest={},
            connection_config={"url": config.url},
            registry=Registry(),
        )
    )

    assert result == [
        {
            "chunk_index": 4,
            "row_count": 1,
            "is_first": True,
            "is_last": True,
            "data": [{"value": 3}],
        }
    ]
    assert events == [
        ("get_entry", "owner.stream"),
        ("get", "owner.stream"),
        ("get_connection", config),
        ("fetch_stream", handle),
        ("release_connection", handle),
    ]


def test_run_streaming_windowed_consumes_registered_and_legacy_result_summaries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Both stream producers feed the same manifest consumer summary."""
    from types import SimpleNamespace

    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane import streaming as streaming_mod
    from polisyos.fabric.data_plane.streaming import StreamDatasetRunResult

    captured_manifests: list[dict[str, object]] = []
    registry = object()
    monkeypatch.setattr(
        modes_mod,
        "_resolve_ingestion_dependencies",
        lambda _dependencies: SimpleNamespace(registry=registry),
    )
    monkeypatch.setattr(
        modes_mod,
        "_resolve_mode_sidecar_scope",
        lambda *_args, **_kwargs: SimpleNamespace(cursor_index_root=tmp_path / "cursor"),
    )
    monkeypatch.setattr(modes_mod, "_resolve_mode_store", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.cursor_store.CursorStore",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        modes_mod,
        "_connector_is_registered",
        lambda connector_id, **_kwargs: connector_id == "registered.stream",
    )
    monkeypatch.setattr(
        streaming_mod, "_resolve_stream_schema_binding", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(modes_mod, "_bind_stream_sanitizer", lambda _binding: object())

    async def _registered_result(
        *,
        connector_id: str,
        dataset_id: str,
        **_kwargs: object,
    ) -> StreamDatasetRunResult:
        return StreamDatasetRunResult(
            connector_id=connector_id,
            dataset_id=dataset_id,
            partition_key="default",
            chunk_refs=[object()],
            window_refs=[object()],
            cdc_event_refs=[object()],
            warnings=["registered result"],
            rows_emitted=4,
            chunks_processed=2,
            quarantined_rows=1,
            final_cursor_ref="registered-cursor",
        )

    async def _legacy_result(**_kwargs: object) -> modes_mod._LegacyStreamDatasetResult:
        return modes_mod._LegacyStreamDatasetResult(
            chunk_refs=[object()],
            window_refs=[object(), object()],
            cdc_event_refs=[],
            warnings=["legacy result"],
            rows_emitted=5,
            chunks_processed=3,
            quarantined_rows=2,
            final_cursor_ref="legacy-cursor",
        )

    monkeypatch.setattr(streaming_mod, "process_stream_dataset", _registered_result)
    monkeypatch.setattr(
        modes_mod,
        "_run_legacy_stream_dataset_from_fetch_async",
        _legacy_result,
    )

    async def _capture_manifest(
        *, manifest_payload: dict[str, object], **_kwargs: object
    ) -> object:
        captured_manifests.append(manifest_payload)
        return object()

    monkeypatch.setattr(modes_mod, "_persist_streaming_manifest_async", _capture_manifest)
    monkeypatch.setattr(
        "polisyos.fabric.evidence.build_evidence_bundle",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        "polisyos.fabric.evidence.persist_evidence_bundle",
        lambda *_args, **_kwargs: object(),
    )

    async def _run_blocking(func: Callable[..., object], *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    monkeypatch.setattr(modes_mod, "run_blocking_async", _run_blocking)
    monkeypatch.setattr(modes_mod, "run_coro_sync", lambda coroutine: asyncio.run(coroutine))

    result = modes_mod.run_streaming_windowed(
        connector_manifest={
            "datasets": [
                {"connector_id": "registered.stream", "dataset_id": "events"},
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
        },
        source="test",
        license_name="MIT",
        cas_root=tmp_path / ".polisyos",
        produce_snapshot=False,
    )

    assert result.mode_effective == "streaming_windowed"
    assert result.warnings == ["registered result", "legacy result"]
    assert result.cursor_ref == "legacy-cursor"
    assert captured_manifests == [
        {
            "source": "streaming_windowed:test",
            "license_name": "MIT",
            "datasets": [
                {"connector_id": "registered.stream", "dataset_id": "events"},
                {"connector_id": "legacy.stream", "dataset_id": "events"},
            ],
            "total_chunks": 5,
            "total_rows": 9,
            "total_windows": 3,
            "total_cdc_events": 1,
            "quarantined_rows": 3,
        }
    ]


def test_non_dict_stream_rows_reach_quarantine_and_require_index_only_at_emission(
    tmp_path: Path,
) -> None:
    """A scalar row stays available for quarantine; clean rows do not require a local index."""
    import asyncio

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.quarantine import list_quarantine_records
    from polisyos.fabric.data_plane.streaming import iter_record_batches

    async def _batches(rows: object) -> list[list[object]]:
        return [batch async for batch in iter_record_batches(rows, batch_size=8)]

    store = FileSystemCAS(tmp_path / "cas")
    batches = asyncio.run(_batches([{"id": "accepted"}, 17]))
    assert batches == [[{"id": "accepted"}, 17]]

    valid_rows, warnings, quarantined = modes_mod._sanitize_stream_rows(
        batches[0],
        connector_id="test.stream",
        dataset_id="events",
        store=store,
        chunk_index=0,
    )
    assert valid_rows == [{"id": "accepted"}]
    assert len(warnings) == 1
    assert quarantined == 1
    records = list_quarantine_records(store)
    assert len(records) == 1
    _, record = records[0]
    assert record.reason == "poison_stream_message"
    assert record.raw_payload_ref is not None

    clean_rows, _clean_warnings, clean_quarantined = modes_mod._sanitize_stream_rows(
        [{"id": "clean"}],
        connector_id="test.stream",
        dataset_id="events",
        store=object(),
        chunk_index=1,
    )
    assert clean_rows == [{"id": "clean"}]
    assert clean_quarantined == 0

    with pytest.raises(TypeError, match="IndexedArtifactStore"):
        modes_mod._sanitize_stream_rows(
            [17],
            connector_id="test.stream",
            dataset_id="events",
            store=object(),
            chunk_index=2,
        )


def test_legacy_stream_bridge_normalizes_chunk_index_before_quarantine(
    tmp_path: Path,
) -> None:
    """The legacy bridge normalizes connector chunk indexes before quarantine."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.connectors.types import DataChunk
    from polisyos.fabric.data_plane import modes as modes_mod
    from polisyos.fabric.data_plane.quarantine import list_quarantine_records
    from polisyos.ir.connectors import ConnectorCapability

    events: list[tuple[str, object]] = []
    handle = object()

    class SelectedConnector:
        capabilities = ConnectorCapability.STREAMING

        def fetch_stream(self, actual_handle: object, request: object):
            events.append(("fetch_stream", actual_handle))

            async def _chunks():
                chunk = DataChunk(
                    data=[17],
                    chunk_index=4,
                    row_count=1,
                    is_first=True,
                    is_last=True,
                )
                object.__setattr__(chunk, "chunk_index", "4")
                yield chunk

            return _chunks()

    selected = SelectedConnector()

    class Registry:
        def get(self, connector_id: str) -> SelectedConnector:
            events.append(("get", connector_id))
            return selected

        def get_entry(self, connector_id: str) -> object:
            events.append(("get_entry", connector_id))
            return object()

        async def get_connection(self, connector_id: str, config: object | None = None) -> object:
            events.append(("get_connection", config))
            return handle

        async def release_connection(self, connector_id: str, actual_handle: object) -> None:
            events.append(("release_connection", actual_handle))

    store = FileSystemCAS(tmp_path / "cas")
    result = asyncio.run(
        modes_mod._run_legacy_stream_dataset_from_fetch_async(
            store=store,
            connector_id="owner.stream",
            dataset_id="events",
            connector_manifest={},
            connection_config=None,
            registry=Registry(),
        )
    )

    records = list_quarantine_records(store)
    assert result.chunks_processed == 1
    assert result.quarantined_rows == 1
    assert len(records) == 1
    _, record = records[0]
    assert record.reason == "poison_stream_message"
    assert record.context["chunk_index"] == 4
    assert type(record.context["chunk_index"]) is int
    assert ("fetch_stream", handle) in events
