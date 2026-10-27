from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.components.discovery import DiscoveredComponent, DiscoveryReport

import polisyos.core.components.discovery as discovery_module
from polisyos.core.components import ComponentEntry, ComponentRegistry
from polisyos.core.components._provider_origin import (
    _editable_script_record_name,
    _OriginError,
)
from polisyos.core.components.discovery import (
    ENTRY_POINT_GROUP_FABRIC_CONNECTORS,
    discover_components,
)
from polisyos.fabric.connectors._components_bootstrap import (
    bootstrap_components_into_registry,
)
from polisyos.fabric.connectors.components import ConnectorComponent


def _distribution_files(
    site: Path,
    module_text: str,
    target: str,
    *,
    metadata_name: str | None = "e02-provider-a",
    metadata_version: str | None = "1.0.0",
) -> tuple[Path, Path]:
    module_path = site / "provider_a_plugin.py"
    module_path.write_text(module_text)
    info = site / "provider_a-1.0.0.dist-info"
    info.mkdir()
    metadata_lines = ["Metadata-Version: 2.1"]
    if metadata_name is not None:
        metadata_lines.append(f"Name: {metadata_name}")
    if metadata_version is not None:
        metadata_lines.append(f"Version: {metadata_version}")
    (info / "METADATA").write_text("\n".join(metadata_lines) + "\n\n")
    entry_points = info / "entry_points.txt"
    entry_points.write_text(f"[{ENTRY_POINT_GROUP_FABRIC_CONNECTORS}]\ne02.provider_a = {target}\n")
    record = info / "RECORD"
    _write_record(site, record, (module_path, info / "METADATA", entry_points))
    return module_path, record


def _write_record(site: Path, record: Path, files: tuple[Path, ...]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for path in files:
        payload = path.read_bytes()
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        writer.writerow((path.relative_to(site).as_posix(), f"sha256={digest}", str(len(payload))))
    writer.writerow((record.relative_to(site).as_posix(), "", ""))
    record.write_text(stream.getvalue())


def _provider_module() -> str:
    return """from polisyos.fabric.connectors.components import connector_component_from_class
from dependency_b.connector import DelegatedConnector


def components():
    return (connector_component_from_class(DelegatedConnector),)
"""


def _dynamic_provider_module() -> str:
    return """from types import FunctionType


def _template():
    return ()


_dynamic_code = compile("def components(): return ()", __file__, "exec")
components = FunctionType(_dynamic_code.co_consts[0], globals())
"""


def _dependency_module() -> str:
    return """from datetime import UTC, datetime
from typing import ClassVar

from polisyos.fabric.connectors.base import (
    BaseConnector, ConnectionConfig, ConnectionHandle, FetchRequest, FetchResult, HealthStatus
)
from polisyos.ir.connectors import (
    ConnectorCapability, ConnectorMetadataSpec, DataVersion, QualityTier, TrustLevel,
    VersionStrategy, capabilities_from_flags
)


class DelegatedConnector(BaseConnector[dict[str, str]]):
    namespace: ClassVar[str] = "origin_test"
    short_id: ClassVar[str] = "delegated"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="Origin Test Connector",
        source_organization="Dependency B",
        source_url="https://example.invalid",
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
        return HealthStatus(healthy=True, message="ok")

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[dict[str, str]]:
        del handle, request
        now = datetime.now(UTC)
        content_hash = "sha256:" + ("0" * 64)
        return FetchResult(
            data={"status": "ok"},
            row_count=1,
            schema_id="origin-test.schema",
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=content_hash,
                timestamp=now,
                content_hash=content_hash,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
            bytes_transferred=1,
        )
"""


def _install_dependency(site: Path) -> None:
    package = site / "dependency_b"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "connector.py").write_text(_dependency_module())


class _CaptureRegistry:
    def __init__(self) -> None:
        self.classes: dict[str, type] = {}

    def register(
        self,
        connector_class: type,
        config: object | None = None,
        *,
        override: bool = False,
        factory: object | None = None,
    ) -> str:
        del config, override, factory
        fqid = str(connector_class.metadata.fully_qualified_id)
        self.classes[fqid] = connector_class
        return fqid


def _discover_provider(
    site: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> DiscoveryReport:
    for module_name in (
        "provider_a_plugin",
        "dependency_b",
        "dependency_b.connector",
        "dependency_b.foreign_plugin",
    ):
        sys.modules.pop(module_name, None)
    monkeypatch.syspath_prepend(str(site))
    importlib.metadata.Distribution.discover(path=[str(site)])
    importlib.invalidate_caches()
    return discover_components(
        groups=[ENTRY_POINT_GROUP_FABRIC_CONNECTORS],
        include_dev_scan=False,
    )


def _candidate(report: DiscoveryReport, provider_name: str) -> DiscoveredComponent:
    return next(row for row in report.components if row.source.entry_point == provider_name)


def test_installed_provider_factory_delegates_to_exact_host_wrapper_and_real_bridge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    module_path, _ = _distribution_files(
        site,
        _provider_module(),
        "provider_a_plugin:components",
    )
    _install_dependency(site)
    report = _discover_provider(site, monkeypatch)
    candidate = _candidate(report, "e02.provider_a")

    assert report.manifest is not None
    assert report.manifest.schema_version == "policyos.component_discovery_manifest.v3"
    assert not report.manifest.is_bound
    assert report.manifest.content_payload()["provider_origin_bindings"]
    binding = candidate.source.provider_origin_binding
    assert binding is not None
    assert binding.status == "verified"
    assert binding.component_factory_status == "delegated"
    assert binding.component_factory_module == ConnectorComponent.create.__module__
    assert any(row.role == "provider_factory" and row.sha256 for row in binding.module_files)
    assert not any(
        row.relative_path.endswith("dependency_b/connector.py") for row in binding.module_files
    )
    assert module_path.name in {row.relative_path for row in binding.module_files}

    index = ComponentRegistry()
    index.register(
        ComponentEntry(
            metadata=candidate.metadata,
            component=candidate.component,
            source=candidate.source,
        )
    )
    registry = _CaptureRegistry()
    outcome = bootstrap_components_into_registry(index, registry)

    assert outcome.errors == []
    assert outcome.registered == ["origin_test.delegated@1.0.0"]
    assert registry.classes["origin_test.delegated@1.0.0"].__module__ == "dependency_b.connector"


@pytest.mark.parametrize(
    ("metadata_name", "metadata_version"),
    [
        (None, "1.0.0"),
        ("", "1.0.0"),
        (" ", "1.0.0"),
        ("bad/name", "1.0.0"),
        ("e02-provider-a", None),
        ("e02-provider-a", ""),
        ("e02-provider-a", " "),
        ("e02-provider-a", "not a version"),
    ],
)
def test_missing_or_invalid_distribution_identity_never_imports_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata_name: str | None,
    metadata_version: str | None,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(
        site,
        'raise AssertionError("provider target imported before identity admission")\n',
        "provider_a_plugin:components",
        metadata_name=metadata_name,
        metadata_version=metadata_version,
    )

    report = _discover_provider(site, monkeypatch)

    assert report.manifest is not None
    identity = next(row for row in report.manifest.entry_points if row.name == "e02.provider_a")
    assert not identity.distribution_identity_is_bound
    assert "provider_a_plugin" not in sys.modules
    assert not any(row.source.entry_point == "e02.provider_a" for row in report.components)
    assert any(
        error.error_type == "ProviderOriginNotEstablished" and error.item == "e02.provider_a"
        for error in report.errors
    ), report.errors


@pytest.mark.parametrize(
    ("group", "name", "value"),
    [
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, None, "provider_a_plugin:components"),
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, "", "provider_a_plugin:components"),
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, "e02.provider_a", None),
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, "e02.provider_a", ""),
        (None, "e02.provider_a", "provider_a_plugin:components"),
        ("", "e02.provider_a", "provider_a_plugin:components"),
    ],
)
def test_incomplete_entrypoint_fields_never_call_target_loader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    group: str | None,
    name: str | None,
    value: str | None,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(
        site,
        'raise AssertionError("provider target imported before identity admission")\n',
        "provider_a_plugin:components",
    )
    distribution = next(iter(importlib.metadata.Distribution.discover(path=[str(site)])))
    loads: list[bool] = []

    def load_target() -> object:
        loads.append(True)
        raise AssertionError("entry-point loader reached before identity admission")

    ep = SimpleNamespace(
        group=group,
        name=name,
        value=value,
        module="provider_a_plugin",
        attr="components",
        dist=distribution,
        load=load_target,
    )
    monkeypatch.setattr(discovery_module, "list_entry_points", lambda **_kwargs: [ep])

    report = _discover_provider(site, monkeypatch)

    assert report.manifest is not None
    assert len(report.manifest.entry_points) == 1
    assert not report.manifest.entry_points[0].distribution_identity_is_bound
    assert loads == []
    assert "provider_a_plugin" not in sys.modules
    assert not any(row.source.entry_point == name for row in report.components)
    assert any(error.error_type.startswith("ProviderOrigin") for error in report.errors), (
        report.errors
    )


def test_entrypoint_identity_hash_must_match_recorded_declaration_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(
        site,
        'raise AssertionError("provider target imported before declaration binding")\n',
        "provider_a_plugin:components",
    )
    installed = next(iter(importlib.metadata.Distribution.discover(path=[str(site)])))
    loads: list[bool] = []

    class InconsistentDistribution:
        metadata = installed.metadata
        version = installed.version
        files = installed.files

        def read_text(self, filename: str) -> str | None:
            if filename == "entry_points.txt":
                return (
                    f"[{ENTRY_POINT_GROUP_FABRIC_CONNECTORS}]\n"
                    "e02.provider_a = provider_a_plugin:other\n"
                )
            return installed.read_text(filename)

        def locate_file(self, path: object) -> Path:
            return installed.locate_file(path)

    def load_target() -> object:
        loads.append(True)
        raise AssertionError("entry-point loader reached before declaration binding")

    ep = SimpleNamespace(
        group=ENTRY_POINT_GROUP_FABRIC_CONNECTORS,
        name="e02.provider_a",
        value="provider_a_plugin:components",
        module="provider_a_plugin",
        attr="components",
        dist=InconsistentDistribution(),
        load=load_target,
    )
    monkeypatch.setattr(discovery_module, "list_entry_points", lambda **_kwargs: [ep])

    report = _discover_provider(site, monkeypatch)

    assert loads == []
    assert "provider_a_plugin" not in sys.modules
    assert any(
        error.error_type == "ProviderOriginRefused"
        and error.message == "entrypoint_identity_declaration_bytes_mismatch"
        for error in report.errors
    ), report.errors


def test_foreign_target_and_record_byte_drift_are_refused_before_target_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _install_dependency(site)
    foreign = site / "dependency_b" / "foreign_plugin.py"
    foreign.write_text("raise AssertionError('foreign target was imported')\n")
    _distribution_files(
        site,
        _provider_module(),
        "dependency_b.foreign_plugin:components",
    )
    report = _discover_provider(site, monkeypatch)
    assert not any(row.source.entry_point == "e02.provider_a" for row in report.components)
    assert "dependency_b.foreign_plugin" not in sys.modules
    assert any(
        error.error_type.startswith("ProviderOrigin") and error.item == "e02.provider_a"
        for error in report.errors
    )

    second = tmp_path / "drifted"
    second.mkdir()
    module_path, _ = _distribution_files(
        second,
        _provider_module(),
        "provider_a_plugin:components",
    )
    _install_dependency(second)
    module_path.write_text(module_path.read_text() + "# changed after RECORD\n")
    drift_report = _discover_provider(second, monkeypatch)
    assert not any(row.source.entry_point == "e02.provider_a" for row in drift_report.components)
    assert "provider_a_plugin" not in sys.modules
    assert any(
        error.error_type.startswith("ProviderOrigin") and error.item == "e02.provider_a"
        for error in drift_report.errors
    )


def test_editable_script_record_paths_are_confined_to_environment_bin() -> None:
    assert _editable_script_record_name("../../../bin/polisyos") == "../../../bin/polisyos"
    for value in (
        "/opt/polisyos",
        "../../../etc/passwd",
        "../../../bin/../payload",
        "../../../bin/subdir/polisyos",
    ):
        with pytest.raises(_OriginError) as exc_info:
            _editable_script_record_name(value)
        assert exc_info.value.code == "record_path_unsupported"


def test_editable_first_party_fabric_entries_use_canonical_dev_source() -> None:
    distribution = importlib.metadata.distribution("policy-engine")
    direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")
    dir_info = direct_url.get("dir_info")
    if not isinstance(dir_info, dict) or dir_info.get("editable") is not True:
        pytest.skip("the current PolicyOS host is not installed in its editable dev profile")

    report = discover_components(
        groups=[ENTRY_POINT_GROUP_FABRIC_CONNECTORS],
        include_dev_scan=False,
    )
    assert report.manifest is not None
    host_bindings = [
        row
        for row in report.manifest.provider_origin_bindings
        if row.distribution_name == "policy-engine"
    ]
    assert host_bindings
    assert all(row.status == "verified" for row in host_bindings)
    assert all(row.origin_basis == "canonical_dev_source" for row in host_bindings)
    assert all(row.record_sha256 and row.entry_points_sha256 for row in host_bindings)


def test_dynamic_callable_with_forged_filename_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(
        site,
        _dynamic_provider_module(),
        "provider_a_plugin:components",
    )
    _install_dependency(site)

    report = _discover_provider(site, monkeypatch)

    assert not any(row.source.entry_point == "e02.provider_a" for row in report.components)
    assert any(
        error.error_type == "ProviderOriginRefused"
        and error.item == "e02.provider_a"
        and error.message == "callable_code_not_in_module_source"
        for error in report.errors
    )


def test_provider_origin_does_not_claim_publisher_authenticity_from_mutable_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    module_path, record = _distribution_files(
        site,
        _provider_module(),
        "provider_a_plugin:components",
    )
    _install_dependency(site)
    module_path.write_text(module_path.read_text() + "# self-consistent RECORD rewrite\n")
    info = site / "provider_a-1.0.0.dist-info"
    _write_record(site, record, (module_path, info / "METADATA", info / "entry_points.txt"))

    report = _discover_provider(site, monkeypatch)
    candidate = _candidate(report, "e02.provider_a")
    assert candidate.source.provider_origin_binding is not None
    assert candidate.source.provider_origin_binding.status == "verified"
    assert candidate.source.provider_origin_binding.record_sha256


def test_bridge_still_rejects_wrong_abi_after_origin_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(site, _provider_module(), "provider_a_plugin:components")
    _install_dependency(site)
    candidate = _candidate(_discover_provider(site, monkeypatch), "e02.provider_a")
    assert candidate.source.provider_origin_binding is not None

    wrong_abi = candidate.metadata.model_copy(
        update={"abi_targets": {"fabric_connectors_api": ">=9.0.0,<10.0.0"}}
    )
    component = ConnectorComponent(
        metadata=wrong_abi,
        connector_class=candidate.component.connector_class,
    )
    index = ComponentRegistry()
    index.register(ComponentEntry(metadata=wrong_abi, component=component, source=candidate.source))
    registry = _CaptureRegistry()
    outcome = bootstrap_components_into_registry(index, registry)

    assert outcome.registered == []
    assert outcome.errors
    assert not registry.classes


def _predicate_classification(report: DiscoveryReport, predicate: str) -> str:
    assert report.manifest is not None
    return next(
        row.classification
        for row in report.manifest.predicate_provenance
        if row.predicate == predicate
    )


def test_successful_empty_fabric_enumeration_is_explicit_and_accounted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(discovery_module, "list_entry_points", lambda **_kwargs: [])

    report = discover_components(
        groups=[ENTRY_POINT_GROUP_FABRIC_CONNECTORS],
        include_dev_scan=False,
    )

    assert report.manifest is not None
    assert report.manifest.entry_point_groups == (ENTRY_POINT_GROUP_FABRIC_CONNECTORS,)
    assert report.manifest.entry_points == ()
    assert report.manifest.provider_origin_bindings == ()
    assert _predicate_classification(report, "entry_point_group_enumeration") == "recomputed"
    assert (
        _predicate_classification(report, "fabric_provider_entrypoint_record_binding")
        == "recomputed"
    )
    assert _predicate_classification(report, "fabric_component_factory_dispatch") == "recomputed"
    assert report.manifest.is_bound


def test_partial_entrypoint_enumeration_cannot_green_provider_predicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(
        site,
        'raise AssertionError("partial enumeration must not load provider")\n',
        "provider_a_plugin:components",
    )
    distribution = next(iter(importlib.metadata.Distribution.discover(path=[str(site)])))
    ep = SimpleNamespace(
        group=ENTRY_POINT_GROUP_FABRIC_CONNECTORS,
        name="e02.provider_a",
        value="provider_a_plugin:components",
        module="provider_a_plugin",
        attr="components",
        dist=distribution,
        load=lambda: (_ for _ in ()).throw(AssertionError("partial provider was loaded")),
    )

    def incomplete_enumeration(**_kwargs: object) -> object:
        def rows() -> object:
            yield ep
            raise RuntimeError("entry-point enumeration interrupted")

        return rows()

    monkeypatch.setattr(discovery_module, "list_entry_points", incomplete_enumeration)
    report = _discover_provider(site, monkeypatch)

    assert report.manifest is not None
    assert report.manifest.entry_points == ()
    assert report.manifest.provider_origin_bindings == ()
    assert _predicate_classification(report, "entry_point_group_enumeration") == "not_established"
    assert (
        _predicate_classification(report, "fabric_provider_entrypoint_record_binding")
        == "not_established"
    )
    assert (
        _predicate_classification(report, "fabric_component_factory_dispatch") == "not_established"
    )
    assert any(error.error_type == "RuntimeError" for error in report.errors)
    assert not report.manifest.is_bound


def test_zero_component_provider_cannot_green_factory_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(site, "def components(): return ()\n", "provider_a_plugin:components")

    report = _discover_provider(site, monkeypatch)

    assert report.manifest is not None
    assert (
        _predicate_classification(report, "fabric_provider_entrypoint_record_binding")
        == "recomputed"
    )
    assert (
        _predicate_classification(report, "fabric_component_factory_dispatch") == "not_established"
    )
    binding_rows = [
        row for row in report.manifest.provider_origin_bindings if row.name == "e02.provider_a"
    ]
    assert len(binding_rows) == 1
    binding = binding_rows[0]
    assert binding.status == "verified"
    assert binding.component_id is None
    assert binding.component_factory_status == "not_established"
    assert any(error.error_type == "InvalidEntryPoint" for error in report.errors)
    assert not report.manifest.is_bound


def test_duplicate_entrypoint_declaration_is_a_typed_refusal_before_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    module_path, record = _distribution_files(
        site,
        'raise AssertionError("malformed declaration target imported")\n',
        "provider_a_plugin:components",
    )
    info = site / "provider_a-1.0.0.dist-info"
    declaration = info / "entry_points.txt"
    declaration.write_text(
        f"[{ENTRY_POINT_GROUP_FABRIC_CONNECTORS}]\n"
        "e02.provider_a = provider_a_plugin:components\n"
        "e02.provider_a = provider_a_plugin:components\n"
    )
    _write_record(site, record, (module_path, info / "METADATA", declaration))
    distribution = next(iter(importlib.metadata.Distribution.discover(path=[str(site)])))
    loads: list[bool] = []

    def load_target() -> object:
        loads.append(True)
        raise AssertionError("malformed declaration reached the provider loader")

    ep = SimpleNamespace(
        group=ENTRY_POINT_GROUP_FABRIC_CONNECTORS,
        name="e02.provider_a",
        value="provider_a_plugin:components",
        module="provider_a_plugin",
        attr="components",
        dist=distribution,
        load=load_target,
    )
    monkeypatch.setattr(discovery_module, "list_entry_points", lambda **_kwargs: [ep])

    report = _discover_provider(site, monkeypatch)

    assert report.manifest is not None
    assert loads == []
    binding = report.manifest.provider_origin_bindings[0]
    assert binding.status == "refused"
    assert binding.reason_code == "entrypoint_declaration_malformed"
    assert any(
        error.error_type == "ProviderOriginRefused"
        and error.message == "entrypoint_declaration_malformed"
        for error in report.errors
    ), report.errors
    assert not report.manifest.is_bound


@pytest.mark.parametrize(
    ("group", "name", "value", "field_name"),
    [
        (None, "e02.provider_a", "provider_a_plugin:components", "group"),
        (0, "e02.provider_a", "provider_a_plugin:components", "group"),
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, None, "provider_a_plugin:components", "name"),
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, 0, "provider_a_plugin:components", "name"),
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, "e02.provider_a", None, "value"),
        (ENTRY_POINT_GROUP_FABRIC_CONNECTORS, "e02.provider_a", 0, "value"),
    ],
)
def test_failure_binding_preserves_missing_entrypoint_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    group: object,
    name: object,
    value: object,
    field_name: str,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    _distribution_files(
        site,
        'raise AssertionError("incomplete entrypoint target imported")\n',
        "provider_a_plugin:components",
    )
    distribution = next(iter(importlib.metadata.Distribution.discover(path=[str(site)])))
    ep = SimpleNamespace(
        group=group,
        name=name,
        value=value,
        module="provider_a_plugin",
        attr="components",
        dist=distribution,
        load=lambda: (_ for _ in ()).throw(AssertionError("loader must not run")),
    )
    monkeypatch.setattr(discovery_module, "list_entry_points", lambda **_kwargs: [ep])

    report = _discover_provider(site, monkeypatch)

    assert report.manifest is not None
    binding = report.manifest.provider_origin_bindings[0]
    assert getattr(binding, field_name) is None
    assert getattr(binding, field_name) != "None"


def test_malformed_sibling_factory_result_is_counted_and_limits_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    source = _provider_module().replace(
        "return (connector_component_from_class(DelegatedConnector),)",
        "return (connector_component_from_class(DelegatedConnector), object())",
    )
    _distribution_files(site, source, "provider_a_plugin:components")
    _install_dependency(site)

    report = _discover_provider(site, monkeypatch)

    assert report.manifest is not None
    assert (
        _predicate_classification(report, "fabric_provider_entrypoint_record_binding")
        == "recomputed"
    )
    assert (
        _predicate_classification(report, "fabric_component_factory_dispatch") == "not_established"
    )
    assert any(error.error_type == "InvalidEntryPointResult" for error in report.errors)
    assert (
        len(
            [
                row
                for row in report.manifest.provider_origin_bindings
                if row.name == "e02.provider_a" and row.component_id
            ]
        )
        == 1
    )
    assert not report.manifest.is_bound
