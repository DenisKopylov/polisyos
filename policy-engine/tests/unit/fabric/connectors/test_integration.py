"""
Phase 2.12 Integration & Governance - verification suite.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, HealthStatus
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    FetchRequest,
    FetchResult,
    QualityTier,
    TrustLevel,
    VersionStrategy,
)

_FIXED_VERSION = DataVersion(
    strategy=VersionStrategy.TIMESTAMP,
    value="2024-06-15T12:00:00+00:00",
    timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
)

_MOCK_DATA = [
    {"agent_id": "a001", "age": 30, "income": 50000.0, "savings": 10000.0, "is_employed": True},
    {"agent_id": "a002", "age": 25, "income": 40000.0, "savings": 5000.0, "is_employed": True},
    {"agent_id": "a003", "age": 45, "income": 80000.0, "savings": 30000.0, "is_employed": False},
]


class MockIntegrationConnector:
    connector_id: ClassVar[str] = "test.integration_mock"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH | ConnectorCapability.CATALOG_BROWSE
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="integration_mock",
        version="1.0.0",
        namespace="test",
        source_name="Integration Test Mock",
        source_organization="Test Suite",
        trust_level=TrustLevel.HIGH,
        quality_tier=QualityTier.GOLD,
        capabilities=ConnectorCapability.FULL_FETCH.value,
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle):
        return None

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=_MOCK_DATA,
            row_count=len(_MOCK_DATA),
            schema_id="test.integration_mock.agents",
            schema_version="1.0.0",
            version=_FIXED_VERSION,
            fetched_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
            completeness=1.0,
            quality_flags=frozenset(),
        )

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> Any:
        from polisyos.fabric.connectors.types import ValidationResult

        return ValidationResult.success()


class TestEndToEndConnectorFlow:
    def test_fetch_request_is_hashable_and_cas_compatible(self) -> None:
        req1 = FetchRequest(
            dataset_id="test.integration_mock.agents",
            filters=(("step", ("0",)),),
        )
        req2 = FetchRequest(
            dataset_id="test.integration_mock.agents",
            filters=(("step", ("0",)),),
        )
        assert req1.cache_key == req2.cache_key
        assert req1.cache_key.startswith("sha256:")

    def test_fetch_returns_valid_result(self) -> None:
        connector = MockIntegrationConnector()
        config = ConnectionConfig(url="http://localhost:9999/mock")

        async def _run() -> FetchResult:
            handle = await connector.connect(config)
            request = FetchRequest(dataset_id="test.integration_mock.agents")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = asyncio.run(_run())
        assert result.row_count == 3
        assert result.completeness == 1.0
        assert result.schema_id == "test.integration_mock.agents"
        assert len(result.data) == 3
        assert all("agent_id" in row for row in result.data)

    def test_evidence_bundle_is_produced(self, tmp_path: Path) -> None:
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.ingestion import run_connectors_ingestion

        cas_root = tmp_path / ".polisyos"

        class DummyEntry:
            def __init__(self, config: ConnectionConfig) -> None:
                self.default_config = config

        class DummyRegistry:
            def __init__(self) -> None:
                self._connector = MockIntegrationConnector()
                self._entry = DummyEntry(ConnectionConfig(url="http://localhost:9999/mock"))

            def get(self, connector_id: str):
                return self._connector

            def get_entry(self, connector_id: str):
                return self._entry

            async def get_connection(self, connector_id: str, config: ConnectionConfig):
                return ConnectionHandle(connector_id=connector_id, config=config)

            async def release_connection(self, connector_id: str, handle: ConnectionHandle):
                return None

        manifest = {
            "datasets": [
                {
                    "connector_id": "test.integration_mock",
                    "dataset_id": "test.integration_mock.agents",
                    "filters": {"step": ["0"]},
                }
            ]
        }

        dummy_registry = DummyRegistry()

        from unittest.mock import patch

        with patch(
            "polisyos.fabric.ingestion.ConnectorRegistry.get_instance",
            return_value=dummy_registry,
        ):
            evidence_ref = run_connectors_ingestion(
                connector_manifest=manifest,
                cas_root=cas_root,
                source="integration_test",
                license_name="MIT",
            )

        assert evidence_ref is not None

        store = FileSystemCAS(cas_root)
        artifact_manifest = store.get_manifest(ArtifactID.model_validate(evidence_ref.artifact_id))
        assert artifact_manifest.kind == "fabric.evidence_bundle"
        assert evidence_ref.manifest_profile_sha256 is not None

        from polisyos.core.canon import from_canonical_bytes
        from polisyos.core.contracts.fabric import EvidenceBundle

        evidence_bundle = EvidenceBundle.model_validate(
            from_canonical_bytes(store.get_bytes(evidence_ref))
        )
        assert len(evidence_bundle.sources) == 1
        source_ref = evidence_bundle.sources[0]
        assert source_ref.kind == "connector_cache.payload"
        assert source_ref.manifest_profile_sha256 is not None
        assert store.verify(source_ref).ok is True

    def test_reopened_cache_hit_reaches_selected_snapshot_source_predicate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Join SQLite cache reuse to the real evidence and snapshot producers."""
        from datetime import timedelta

        from polisyos.core.artifacts import FileSystemCAS, input_ref_from_artifact_ref
        from polisyos.core.canon import from_canonical_bytes
        from polisyos.core.contracts.fabric import DataSnapshot, EvidenceBundle, RetrievalSummary
        from polisyos.fabric.connectors.cache import (
            CachingConnectorProxy,
            ConnectorCacheStore,
            TTLPolicy,
        )
        from polisyos.fabric.connectors.registry import ConnectorRegistry
        from polisyos.fabric.connectors.transform.pipeline import (
            DataTransform,
            TransformContext,
            TransformLineage,
            TransformPipeline,
        )
        from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
        from polisyos.fabric.ingestion import ingestion as ingestion_module
        from polisyos.fabric.ingestion import resolve_ingestion_dependencies
        from polisyos.fabric.ingestion.ingestion_providers import (
            resolve_ingestion_cache_namespace,
            resolve_ingestion_sidecar_scope,
        )
        from polisyos.ir.connectors import FetchRequest
        from polisyos.runtime.quality import semantic_epoch

        class Metrics:
            def __init__(self) -> None:
                self.slo_calls: list[tuple[str, str]] = []

            def record_slo_connector_request(self, status: str, *, connector_id: str) -> None:
                self.slo_calls.append((status, connector_id))

            def record_fabric_lineage_graph(self, **kwargs: object) -> None:
                del kwargs

        class AddAdjustedIncome(DataTransform):
            @property
            def name(self) -> str:
                return "add_adjusted_income"

            def apply(
                self,
                data: pd.DataFrame,
                context: TransformContext,
            ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
                del context
                started_at = datetime.now(UTC)
                transformed = data.copy()
                transformed["adjusted_income"] = transformed["income"] + 1
                return (
                    transformed,
                    TransformLineage(
                        stage_name=self.name,
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        input_row_count=len(data),
                        output_row_count=len(transformed),
                        parameters={},
                    ),
                    [],
                )

        def build_pipeline() -> TransformPipeline:
            return TransformPipeline().add_stage(AddAdjustedIncome())

        monkeypatch.setitem(
            ingestion_module._TRANSFORM_PIPELINE_REGISTRY,
            "r3-cache-derived-input",
            build_pipeline,
        )

        class CountingConnector(MockIntegrationConnector):
            connector_id: ClassVar[str] = "integration_mock"
            capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
            metadata: ClassVar[ConnectorMetadataSpec] = (
                MockIntegrationConnector.metadata.model_copy(
                    update={"capabilities": ConnectorCapability.FULL_FETCH.value}
                )
            )

            def __init__(self) -> None:
                super().__init__()
                self.fetch_count = 0

            async def fetch(self, handle, request):
                self.fetch_count += 1
                return await super().fetch(handle, request)

            async def health_check(self, handle) -> HealthStatus:
                del handle
                return HealthStatus(healthy=True, message="controlled fixture is ready")

        cas_root = tmp_path / "cas"
        metrics = Metrics()
        monkeypatch.setattr(
            "polisyos.fabric.connectors._registry_lifecycle._default_metrics",
            lambda: metrics,
        )
        monkeypatch.setattr(
            "polisyos.fabric.connectors.cache.proxy.get_metrics",
            lambda: metrics,
        )
        sidecar_scope = resolve_ingestion_sidecar_scope(cas_root)
        cache_namespace = "e02-joined-cache-route"
        resolved_namespace = resolve_ingestion_cache_namespace(
            cache_namespace,
            sidecar_scope=sidecar_scope,
        )
        connector = CountingConnector()
        registry = ConnectorRegistry()
        registry.register(
            CountingConnector,
            config=ConnectionConfig(url="http://localhost:9999/mock"),
            factory=lambda: connector,
        )
        dependencies = resolve_ingestion_dependencies(
            registry=registry,
            metrics=metrics,  # type: ignore[arg-type]
            store_factory=lambda root: FileSystemCAS(root),
        )

        def open_cache() -> ConnectorCacheStore:
            return ConnectorCacheStore(
                FileSystemCAS(sidecar_scope.base_root),
                TTLPolicy(ttl=timedelta(hours=1)),
                namespace=resolved_namespace,
                metrics=metrics,  # type: ignore[arg-type]
                tracer=dependencies.tracer,
            )

        cache = open_cache()
        registry.configure_cache(cache)
        manifest = {
            "datasets": [
                {
                    "connector_id": "integration_mock",
                    "dataset_id": "test.integration_mock.agents",
                    "filters": {"step": ["0"]},
                }
            ],
            "cache_policy": "ttl:3600",
            "transform_dag": "r3-cache-derived-input",
        }

        def ingest():
            return run_orchestrated_ingestion(
                connector_manifest=manifest,
                source="integration_test",
                license_name="MIT",
                cas_root=cas_root,
                ingestion_dependencies=dependencies,
                sidecar_scope=sidecar_scope,
                cache_namespace=cache_namespace,
            )

        first = ingest()
        assert first.evidence_bundle_ref is not None
        assert first.data_snapshot_ref is not None
        assert connector.fetch_count == 1
        cache_key = FetchRequest(
            dataset_id="test.integration_mock.agents",
            filters=(("step", ("0",)),),
        ).cache_key
        first_metadata = cache.get_metadata(cache_key)
        assert first_metadata is not None
        assert first_metadata.payload_ref.manifest_profile_sha256 is not None
        index_path = sidecar_scope.base_root / resolved_namespace / "cache_index.sqlite3"
        assert index_path.is_file()
        cache.close()

        reopened_cache = open_cache()
        registry.configure_cache(reopened_cache)
        persisted_metadata = reopened_cache.get_metadata(cache_key)
        assert persisted_metadata == first_metadata
        second = ingest()

        assert second.evidence_bundle_ref is not None
        assert second.data_snapshot_ref is not None
        assert second.evidence_bundle_ref.manifest_profile_sha256 is not None
        assert second.data_snapshot_ref.manifest_profile_sha256 is not None
        assert connector.fetch_count == 1
        assert metrics.slo_calls == [
            ("ok", "test.integration_mock@1.0.0"),
            ("ok", "test.integration_mock@1.0.0"),
        ]
        active_proxy = registry.get("integration_mock")
        assert isinstance(active_proxy, CachingConnectorProxy)
        assert active_proxy.hit_rate == 1.0

        store = FileSystemCAS(sidecar_scope.base_root)
        evidence = EvidenceBundle.model_validate(
            from_canonical_bytes(store.get_bytes(second.evidence_bundle_ref))
        )
        assert len(evidence.sources) == 1
        cache_payload_ref = persisted_metadata.payload_ref
        assert evidence.sources[0] != cache_payload_ref
        assert evidence.sources[0].manifest_profile_sha256 is not None
        assert store.get_manifest(evidence.sources[0]).inputs == [
            input_ref_from_artifact_ref(
                cache_payload_ref,
                role="connector_cache.raw_payload",
            )
        ]
        assert (
            reopened_cache.get(
                FetchRequest(
                    dataset_id="test.integration_mock.agents",
                    filters=(("step", ("0",)),),
                ),
                connector_id="integration_mock",
            ).metadata.payload_ref
            == cache_payload_ref
        )

        snapshot = DataSnapshot.model_validate(
            from_canonical_bytes(store.get_bytes(second.data_snapshot_ref))
        )
        assert snapshot.data_ref == evidence.sources[0]
        assert snapshot.evidence_ref == second.evidence_bundle_ref
        assert snapshot.quality_report_ref is not None
        assert snapshot.quality_report_ref.manifest_profile_sha256 is not None
        summary = RetrievalSummary.model_validate(
            from_canonical_bytes(store.get_bytes(snapshot.quality_report_ref))
        )
        assert summary.assessment_status == "not_assessed"
        assert summary.source_refs == evidence.sources == [snapshot.data_ref]

        # This shared profile predicate proves the persisted snapshot's typed
        # owner refs match its actual selected parent-manifest edges. It does
        # not assert a complete live-source or L5 admission.
        assert semantic_epoch._data_snapshot_manifest_inputs_match(
            store,
            second.data_snapshot_ref,
            snapshot,
        )
        stripped_owner = snapshot.data_ref.model_copy(update={"manifest_profile_sha256": None})
        assert not semantic_epoch._data_snapshot_manifest_inputs_match(
            store,
            second.data_snapshot_ref,
            snapshot.model_copy(update={"data_ref": stripped_owner}),
        )

        # The same selected cache source also remains valid when no transform
        # is requested. This path must preserve the raw selected ref directly,
        # without manufacturing a derived cache artifact or changing the index.
        manifest.pop("transform_dag")
        untransformed = ingest()
        assert untransformed.evidence_bundle_ref is not None
        assert untransformed.data_snapshot_ref is not None
        assert connector.fetch_count == 1
        assert metrics.slo_calls == [
            ("ok", "test.integration_mock@1.0.0"),
            ("ok", "test.integration_mock@1.0.0"),
            ("ok", "test.integration_mock@1.0.0"),
        ]
        untransformed_evidence = EvidenceBundle.model_validate(
            from_canonical_bytes(store.get_bytes(untransformed.evidence_bundle_ref))
        )
        assert untransformed_evidence.sources == [cache_payload_ref]
        untransformed_snapshot = DataSnapshot.model_validate(
            from_canonical_bytes(store.get_bytes(untransformed.data_snapshot_ref))
        )
        assert untransformed_snapshot.data_ref == cache_payload_ref
        assert untransformed_snapshot.evidence_ref == untransformed.evidence_bundle_ref
        assert untransformed_snapshot.quality_report_ref is not None
        untransformed_summary = RetrievalSummary.model_validate(
            from_canonical_bytes(store.get_bytes(untransformed_snapshot.quality_report_ref))
        )
        assert untransformed_summary.assessment_status == "not_assessed"
        assert untransformed_summary.source_refs == [cache_payload_ref]
        assert semantic_epoch._data_snapshot_manifest_inputs_match(
            store,
            untransformed.data_snapshot_ref,
            untransformed_snapshot,
        )
        assert (
            reopened_cache.get(
                FetchRequest(
                    dataset_id="test.integration_mock.agents",
                    filters=(("step", ("0",)),),
                ),
                connector_id="integration_mock",
            ).metadata.payload_ref
            == cache_payload_ref
        )
        reopened_cache.close()
        asyncio.run(registry.shutdown_async())

    def test_run_connectors_ingestion_uses_injected_registry_and_store_factory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.ingestion import run_connectors_ingestion

        class DummySpan:
            def __enter__(self) -> DummySpan:
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def set_attribute(self, key: str, value: object) -> None:
                del key, value

        class DummyTracer:
            def __init__(self) -> None:
                self.names: list[str] = []

            def start_as_current_span(self, name: str, attributes=None):
                del attributes
                self.names.append(name)
                return DummySpan()

        class DummyMetrics:
            def record_fabric_lineage_graph(self, **kwargs: object) -> None:
                del kwargs

        class DummyEntry:
            def __init__(self, config: ConnectionConfig) -> None:
                self.default_config = config

        class DummyRegistry:
            def __init__(self) -> None:
                self._connector = MockIntegrationConnector()
                self._entry = DummyEntry(ConnectionConfig(url="http://localhost:9999/mock"))

            def get(self, connector_id: str):
                del connector_id
                return self._connector

            def get_entry(self, connector_id: str):
                del connector_id
                return self._entry

            async def get_connection(self, connector_id: str, config: ConnectionConfig):
                return ConnectionHandle(connector_id=connector_id, config=config)

            async def release_connection(self, connector_id: str, handle: ConnectionHandle):
                del connector_id, handle
                return None

        cas_root = tmp_path / ".polisyos"
        build_calls: list[Path] = []
        manifest = {
            "datasets": [
                {
                    "connector_id": "test.integration_mock",
                    "dataset_id": "test.integration_mock.agents",
                }
            ]
        }
        tracer = DummyTracer()
        metrics = DummyMetrics()

        monkeypatch.setattr(
            "polisyos.fabric.ingestion.get_tracer",
            lambda: (_ for _ in ()).throw(AssertionError("global tracer should not be used")),
        )
        monkeypatch.setattr(
            "polisyos.fabric.ingestion.get_metrics",
            lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
        )
        monkeypatch.setattr(
            "polisyos.fabric.ingestion.ConnectorRegistry.get_instance",
            lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
        )

        evidence_ref = run_connectors_ingestion(
            connector_manifest=manifest,
            cas_root=cas_root,
            source="integration_test",
            license_name="MIT",
            registry=DummyRegistry(),
            tracer=tracer,
            metrics=metrics,
            store_factory=lambda root: build_calls.append(root) or FileSystemCAS(root),
        )

        assert evidence_ref is not None
        assert build_calls == [cas_root]
        assert tracer.names
        assert tracer.names[0] == "fabric.data_plane.ingest"


class TestLintConnectors:
    def test_detects_scientist_import(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "quality" / "lint"))
        from lint_connectors import scan

        bad_file = tmp_path / "bad_connector.py"
        bad_file.write_text(
            textwrap.dedent(
                """\
                from polisyos.scientist.orchestration.orchestrator import something
                from polisyos.fabric.connectors.base import FetchRequest
                """
            ),
            encoding="utf-8",
        )

        violations = scan(tmp_path)
        errors = [v for v in violations if not v.in_type_checking]

        assert len(errors) == 1
        assert "polisyos.scientist" in errors[0].imported_module
        assert errors[0].violated_law == "Law A (Import Gate)"
        assert errors[0].severity == "ERROR"

    def test_detects_foundry_import(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "quality" / "lint"))
        from lint_connectors import scan

        bad_file = tmp_path / "bad_connector.py"
        bad_file.write_text(
            textwrap.dedent(
                """\
                import polisyos.foundry.contracts.state
                """
            ),
            encoding="utf-8",
        )

        violations = scan(tmp_path)
        errors = [v for v in violations if not v.in_type_checking]

        assert len(errors) == 1
        assert "polisyos.foundry" in errors[0].imported_module
        assert errors[0].violated_law == "Law B (Foundry Purity)"

    def test_type_checking_import_is_warning(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "quality" / "lint"))
        from lint_connectors import scan

        guarded_file = tmp_path / "guarded_connector.py"
        guarded_file.write_text(
            textwrap.dedent(
                """\
                from __future__ import annotations
                from typing import TYPE_CHECKING

                if TYPE_CHECKING:
                    from polisyos.scientist.orchestration.orchestrator import SomeType

                class MyConnector:
                    pass
                """
            ),
            encoding="utf-8",
        )

        violations = scan(tmp_path)
        assert len(violations) == 1
        assert violations[0].in_type_checking is True
        assert violations[0].severity == "WARNING"

    def test_clean_file_produces_no_violations(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "quality" / "lint"))
        from lint_connectors import scan

        clean_file = tmp_path / "clean_connector.py"
        clean_file.write_text(
            textwrap.dedent(
                """\
                from polisyos.fabric.connectors.base import FetchRequest, FetchResult
                from polisyos.ir.connectors import ConnectorCapability

                class CleanConnector:
                    pass
                """
            ),
            encoding="utf-8",
        )

        violations = scan(tmp_path)
        assert violations == []

    def test_multiple_violations_in_one_file(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "quality" / "lint"))
        from lint_connectors import scan

        bad_file = tmp_path / "multi_bad.py"
        bad_file.write_text(
            textwrap.dedent(
                """\
                from polisyos.scientist.orchestration.orchestrator import Foo
                import polisyos.foundry.engine
                from polisyos.scientist.agents import Bar
                """
            ),
            encoding="utf-8",
        )

        violations = scan(tmp_path)
        errors = [v for v in violations if not v.in_type_checking]

        assert len(errors) == 3
        assert errors[0].lineno == 1
        assert errors[1].lineno == 2
        assert errors[2].lineno == 3

    def test_lint_connectors_cli_exit_code(self, tmp_path: Path) -> None:
        lint_script = (
            Path(__file__).resolve().parents[4]
            / "tools"
            / "quality"
            / "lint"
            / "lint_connectors.py"
        )
        if not lint_script.exists():
            pytest.skip("lint_connectors.py not found")

        clean_dir = tmp_path / "clean"
        clean_dir.mkdir()
        (clean_dir / "ok.py").write_text(
            "from polisyos.fabric.connectors.base import FetchRequest\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(lint_script), "--src-root", str(clean_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Expected 0, got {result.returncode}:\n{result.stdout}"

        dirty_dir = tmp_path / "dirty"
        dirty_dir.mkdir()
        (dirty_dir / "bad.py").write_text(
            "from polisyos.scientist.orchestration.orchestrator import X\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(lint_script), "--src-root", str(dirty_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"Expected 1, got {result.returncode}:\n{result.stdout}"
        assert "Law A" in result.stdout
