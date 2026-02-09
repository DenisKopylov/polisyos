"""
Phase 2.12 Integration & Governance - verification suite.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
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
    timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
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

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[list[dict]]:
        return FetchResult(
            data=_MOCK_DATA,
            row_count=len(_MOCK_DATA),
            schema_id="test.integration_mock.agents",
            schema_version="1.0.0",
            version=_FIXED_VERSION,
            fetched_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
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
        from polisyos.fabric.ingestion import run_connectors_ingestion
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.store import FileSystemCAS

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
        artifact_manifest = store.get_manifest(
            ArtifactID.model_validate(evidence_ref.artifact_id)
        )
        assert artifact_manifest.kind == "fabric.evidence_bundle"

    def test_scientist_isolation(self) -> None:
        import ast as _ast

        data_loader_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "polisyos"
            / "scientist"
            / "orchestrator"
            / "data_loader.py"
        )
        if not data_loader_path.exists():
            pytest.skip("data_loader.py not found - skipping isolation check")

        source = data_loader_path.read_text(encoding="utf-8")
        tree = _ast.parse(source)

        forbidden_imports: list[str] = []
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                if isinstance(node, _ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, _ast.Import):
                    for alias in node.names:
                        module = alias.name
                        if "fabric.connectors" in module:
                            forbidden_imports.append(module)
                    continue
                else:
                    continue
                if "fabric.connectors" in module:
                    forbidden_imports.append(module)

        assert forbidden_imports == [], (
            "Law A violation: data_loader.py imports fabric.connectors directly: "
            f"{forbidden_imports}"
        )


class TestLintConnectors:
    def test_detects_scientist_import(self, tmp_path: Path) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
        from lint_connectors import scan

        bad_file = tmp_path / "bad_connector.py"
        bad_file.write_text(
            textwrap.dedent(
                """\
                from polisyos.scientist.orchestrator import something
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
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
        from lint_connectors import scan

        bad_file = tmp_path / "bad_connector.py"
        bad_file.write_text(
            textwrap.dedent(
                """\
                import polisyos.foundry.domain.state
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
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
        from lint_connectors import scan

        guarded_file = tmp_path / "guarded_connector.py"
        guarded_file.write_text(
            textwrap.dedent(
                """\
                from __future__ import annotations
                from typing import TYPE_CHECKING

                if TYPE_CHECKING:
                    from polisyos.scientist.orchestrator import SomeType

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
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
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
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
        from lint_connectors import scan

        bad_file = tmp_path / "multi_bad.py"
        bad_file.write_text(
            textwrap.dedent(
                """\
                from polisyos.scientist.orchestrator import Foo
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
        lint_script = Path(__file__).resolve().parents[3] / "tools" / "lint_connectors.py"
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
            "from polisyos.scientist.orchestrator import X\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(lint_script), "--src-root", str(dirty_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, f"Expected 1, got {result.returncode}:\n{result.stdout}"
        assert "Law A" in result.stdout
