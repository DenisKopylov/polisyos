from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.components.discovery import (
    ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    ENTRY_POINT_GROUP_IR_FRAGMENTS,
    ComponentDiscoveryManifest,
    discover_components,
)


@dataclass(frozen=True)
class _TestComponent:
    metadata: ComponentMetadata

    def create(self) -> object:
        return object()


class _FakeDistribution:
    def __init__(
        self,
        *,
        name: str,
        version: str,
        entry_points_text: str,
        direct_url_text: str | None = None,
    ) -> None:
        self.metadata = {"Name": name}
        self.version = version
        self._entry_points_text = entry_points_text
        self._direct_url_text = direct_url_text

    def read_text(self, filename: str) -> str | None:
        if filename == "entry_points.txt":
            return self._entry_points_text
        if filename == "direct_url.json":
            return self._direct_url_text
        return None


class _FakeEntryPoint:
    def __init__(self, *, group: str, name: str, loader, dist=None):
        self.group = group
        self.name = name
        self._loader = loader
        self.value = f"{name}:factory"
        self.module = name
        self.attr = "factory"
        self.dist = dist

    def load(self):
        return self._loader


class _FakeEntryPoints:
    def __init__(self, by_group: dict[str, list[_FakeEntryPoint]]) -> None:
        self._by_group = by_group

    def select(self, *, group: str):
        return list(self._by_group.get(group, []))


def _discover_manifest_for_distribution(
    monkeypatch,
    distribution: _FakeDistribution,
) -> ComponentDiscoveryManifest:
    component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.method.direct_url@1.0.0"),
            kind=ComponentKind.FOUNDRY_METHOD,
            abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.FOUNDRY_METHOD,
            deps=[],
        )
    )
    entry_point = _FakeEntryPoint(
        group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
        name="roads.method.direct_url",
        loader=lambda: component,
        dist=distribution,
    )
    monkeypatch.setattr(
        "polisyos.core.components.discovery.list_entry_points",
        lambda *, group: [entry_point],
    )
    report = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )
    assert report.manifest is not None
    return report.manifest


def test_discovery_entry_points_loads_components(monkeypatch) -> None:
    ir_component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.ir.test_fragment@1.0.0"),
            kind=ComponentKind.IR_FRAGMENT,
            abi_targets={"ir_abi": "1.x"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.IR_FRAGMENT,
            deps=[],
        )
    )
    method_component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.method.demo@1.0.0"),
            kind=ComponentKind.FOUNDRY_METHOD,
            abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.FOUNDRY_METHOD,
            deps=[],
        )
    )

    entry_points = _FakeEntryPoints(
        {
            ENTRY_POINT_GROUP_IR_FRAGMENTS: [
                _FakeEntryPoint(
                    group=ENTRY_POINT_GROUP_IR_FRAGMENTS,
                    name="roads.ir",
                    loader=lambda: ir_component,
                ),
            ],
            ENTRY_POINT_GROUP_FOUNDRY_METHODS: [
                _FakeEntryPoint(
                    group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
                    name="roads.method",
                    loader=lambda: method_component,
                ),
            ],
        }
    )

    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda: entry_points,
    )

    report = discover_components(
        groups=[ENTRY_POINT_GROUP_IR_FRAGMENTS, ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )

    ids = {str(item.metadata.component_id) for item in report.components}
    assert "roads.ir.test_fragment@1.0.0" in ids
    assert "roads.method.demo@1.0.0" in ids
    assert report.sources_processed == 2
    assert report.errors == []
    assert all(item.source.source_type == "entry_point" for item in report.components)


def test_discovery_builtin_loader_uses_component_path() -> None:
    component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.method.builtin@1.0.0"),
            kind=ComponentKind.FOUNDRY_METHOD,
            abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
            domains=["roads"],
            jurisdictions=[],
            tags=["builtin"],
            capabilities=Capability.FOUNDRY_METHOD,
            deps=[],
        )
    )

    report = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[("test.builtin:components", lambda: [component])],
    )

    assert [str(item.metadata.component_id) for item in report.components] == [
        "roads.method.builtin@1.0.0"
    ]
    assert report.components[0].source.source_type == "builtin_loader"
    assert report.components[0].source.location == "test.builtin:components"
    assert report.sources_processed == 1
    assert report.errors == []


def test_discovery_entry_point_can_return_component_iterable(monkeypatch) -> None:
    components = [
        _TestComponent(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(f"roads.method.iterable_{idx}@1.0.0"),
                kind=ComponentKind.FOUNDRY_METHOD,
                abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
                domains=["roads"],
                jurisdictions=[],
                tags=[],
                capabilities=Capability.FOUNDRY_METHOD,
                deps=[],
            )
        )
        for idx in range(2)
    ]
    entry_points = _FakeEntryPoints(
        {
            ENTRY_POINT_GROUP_FOUNDRY_METHODS: [
                _FakeEntryPoint(
                    group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
                    name="roads.methods",
                    loader=lambda: components,
                ),
            ],
        }
    )

    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda: entry_points,
    )

    report = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )

    assert [str(item.metadata.component_id) for item in report.components] == [
        "roads.method.iterable_0@1.0.0",
        "roads.method.iterable_1@1.0.0",
    ]
    assert report.errors == []


def test_discovery_manifest_binds_entry_point_distribution_identity(monkeypatch) -> None:
    component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.method.bound@1.0.0"),
            kind=ComponentKind.FOUNDRY_METHOD,
            abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.FOUNDRY_METHOD,
            deps=[],
        )
    )
    entry_points_text = (
        "[polisyos.foundry_methods]\nroads.method.bound = roads.method.bound:factory\n"
    )
    distribution = _FakeDistribution(
        name="roads-foundry-methods",
        version="1.2.3",
        entry_points_text=entry_points_text,
    )
    entry_points = _FakeEntryPoints(
        {
            ENTRY_POINT_GROUP_FOUNDRY_METHODS: [
                _FakeEntryPoint(
                    group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
                    name="roads.method.bound",
                    loader=lambda: component,
                    dist=distribution,
                )
            ]
        }
    )
    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda: entry_points,
    )

    report = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )

    assert report.manifest is not None
    assert report.manifest.is_bound is False
    assert report.manifest.unbound_inputs == (
        "entry_point_source_byte_closure_not_established:"
        "polisyos.foundry_methods:roads.method.bound:roads.method.bound:factory",
    )
    assert len(report.manifest.entry_points) == 1
    identity = report.manifest.entry_points[0]
    assert identity.distribution_name == "roads-foundry-methods"
    assert identity.distribution_version == "1.2.3"
    assert identity.entry_points_sha256 == (
        "sha256:" + hashlib.sha256(entry_points_text.encode("utf-8")).hexdigest()
    )
    assert report.manifest.manifest_id.startswith("component_discovery_manifest_")
    encoded_manifest = json.dumps(
        report.manifest.content_payload(),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert report.manifest.manifest_id == (
        "component_discovery_manifest_" + hashlib.sha256(encoded_manifest).hexdigest()
    )
    predicate_rows = {
        row.predicate: row.classification for row in report.manifest.predicate_provenance
    }
    assert predicate_rows["entry_point_distribution_identity"] == "recomputed"
    assert predicate_rows["entry_point_source_byte_closure"] == "not_established"


def test_discovery_manifest_ignores_editable_checkout_address(
    monkeypatch,
    tmp_path: Path,
) -> None:
    first_checkout = tmp_path / "checkout-a" / "policy-engine"
    second_checkout = tmp_path / "checkout-b" / "policy-engine"
    first_checkout.mkdir(parents=True)
    second_checkout.mkdir(parents=True)
    source_bytes = b"same source bytes\n"
    (first_checkout / "source.py").write_bytes(source_bytes)
    (second_checkout / "source.py").write_bytes(source_bytes)
    assert first_checkout.resolve() != second_checkout.resolve()
    assert hashlib.sha256((first_checkout / "source.py").read_bytes()).digest() == hashlib.sha256(
        (second_checkout / "source.py").read_bytes()
    ).digest()
    entry_points_text = (
        "[polisyos.foundry_methods]\n"
        "roads.method.direct_url = roads.method.direct_url:factory\n"
    )

    first = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=json.dumps(
                {
                    "url": first_checkout.resolve().as_uri(),
                    "dir_info": {"editable": True},
                },
                separators=(",", ":"),
            ),
        ),
    )
    second = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=json.dumps(
                {
                    "url": second_checkout.resolve().as_uri(),
                    "dir_info": {"editable": True},
                },
                separators=(",", ":"),
            ),
        ),
    )

    assert first.entry_points[0].direct_url_sha256 is None
    assert second.entry_points[0].direct_url_sha256 is None
    assert first.content_payload() == second.content_payload()
    assert first.manifest_id == second.manifest_id


def test_discovery_manifest_ignores_editable_direct_url_serialization(
    monkeypatch,
) -> None:
    entry_points_text = (
        "[polisyos.foundry_methods]\n"
        "roads.method.direct_url = roads.method.direct_url:factory\n"
    )
    compact = (
        '{"url":"file:///same/checkout/policy-engine",'
        '"dir_info":{"editable":true}}'
    )
    reordered = (
        "{\n"
        '  "dir_info": {\n'
        '    "editable": true\n'
        "  },\n"
        '  "url": "file:///same/checkout/policy-engine"\n'
        "}\n"
    )

    first = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=compact,
        ),
    )
    second = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=reordered,
        ),
    )

    assert first.entry_points[0].direct_url_sha256 is None
    assert second.entry_points[0].direct_url_sha256 is None
    assert first.content_payload() == second.content_payload()
    assert first.manifest_id == second.manifest_id


def test_discovery_manifest_records_editable_identity_as_not_established(
    monkeypatch,
) -> None:
    manifest = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=(
                "[polisyos.foundry_methods]\n"
                "roads.method.direct_url = roads.method.direct_url:factory\n"
            ),
            direct_url_text=(
                '{"url":"file:///checkout/policy-engine",'
                '"dir_info":{"editable":true}}'
            ),
        ),
    )

    assert len(manifest.entry_points) == 1
    identity = manifest.entry_points[0]
    assert identity.editable_install is True
    assert identity.direct_url_sha256 is None
    assert identity.source_byte_closure == "not_established"
    assert manifest.unbound_inputs == (
        "entry_point_source_byte_closure_not_established:"
        "polisyos.foundry_methods:roads.method.direct_url:"
        "roads.method.direct_url:factory",
    )
    predicate_rows = {
        row.predicate: row.classification for row in manifest.predicate_provenance
    }
    assert predicate_rows["entry_point_distribution_identity"] == "recomputed"
    assert predicate_rows["entry_point_source_byte_closure"] == "not_established"


def test_discovery_manifest_keeps_noneditable_direct_url_content_bound(
    monkeypatch,
) -> None:
    entry_points_text = (
        "[polisyos.foundry_methods]\n"
        "roads.method.direct_url = roads.method.direct_url:factory\n"
    )
    first_direct_url = (
        '{"url":"https://example.invalid/roads.whl",'
        '"dir_info":{"editable":false},'
        '"archive_info":{"hash":"sha256=aaaa"}}'
    )
    second_direct_url = first_direct_url.replace("sha256=aaaa", "sha256=bbbb")

    first = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=first_direct_url,
        ),
    )
    second = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=second_direct_url,
        ),
    )

    assert first.entry_points[0].editable_install is False
    assert first.entry_points[0].direct_url_sha256 == (
        "sha256:" + hashlib.sha256(first_direct_url.encode("utf-8")).hexdigest()
    )
    assert second.entry_points[0].direct_url_sha256 == (
        "sha256:" + hashlib.sha256(second_direct_url.encode("utf-8")).hexdigest()
    )
    assert first.entry_points[0].direct_url_sha256 != second.entry_points[0].direct_url_sha256
    assert first.manifest_id != second.manifest_id


def test_discovery_manifest_keeps_malformed_direct_url_bytes_bound(
    monkeypatch,
) -> None:
    entry_points_text = (
        "[polisyos.foundry_methods]\n"
        "roads.method.direct_url = roads.method.direct_url:factory\n"
    )
    first_direct_url = '{"url":"file:///unknown-a",'
    second_direct_url = '{"url":"file:///unknown-b",'

    first = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=first_direct_url,
        ),
    )
    second = _discover_manifest_for_distribution(
        monkeypatch,
        _FakeDistribution(
            name="roads-direct-url",
            version="1.0.0",
            entry_points_text=entry_points_text,
            direct_url_text=second_direct_url,
        ),
    )

    assert first.entry_points[0].editable_install is None
    assert second.entry_points[0].editable_install is None
    assert first.entry_points[0].direct_url_sha256 != second.entry_points[0].direct_url_sha256
    assert first.manifest_id != second.manifest_id


def test_discovery_manifest_orders_duplicate_entry_points_by_distribution(
    monkeypatch,
) -> None:
    component = _TestComponent(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("roads.method.duplicate@1.0.0"),
            kind=ComponentKind.FOUNDRY_METHOD,
            abi_targets={"foundry_methods_api": ">=3.5.0,<4.0.0"},
            domains=["roads"],
            jurisdictions=[],
            tags=[],
            capabilities=Capability.FOUNDRY_METHOD,
            deps=[],
        )
    )
    entry_points_text = (
        "[polisyos.foundry_methods]\nroads.method.duplicate = roads.method.duplicate:factory\n"
    )
    alpha = _FakeEntryPoint(
        group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
        name="roads.method.duplicate",
        loader=lambda: component,
        dist=_FakeDistribution(
            name="alpha-methods",
            version="1.0.0",
            entry_points_text=entry_points_text,
        ),
    )
    zeta = _FakeEntryPoint(
        group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
        name="roads.method.duplicate",
        loader=lambda: component,
        dist=_FakeDistribution(
            name="zeta-methods",
            version="1.0.0",
            entry_points_text=entry_points_text,
        ),
    )
    current = [zeta, alpha]
    monkeypatch.setattr(
        "polisyos.core.components.discovery.list_entry_points",
        lambda *, group: list(current),
    )

    first = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )
    current.reverse()
    second = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )

    assert first.manifest is not None
    assert second.manifest is not None
    assert first.manifest.manifest_id == second.manifest.manifest_id
    assert [row.distribution_name for row in first.manifest.entry_points] == [
        "alpha-methods",
        "zeta-methods",
    ]


def test_discovery_manifest_binds_dev_root_and_contributed_bytes(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    components_file = root / "components.py"
    components_file.write_text("__polisyos_components__ = []\n", encoding="utf-8")

    first = discover_components(groups=[], include_dev_scan=True, dev_scan_paths=[root])
    first_manifest = first.manifest
    assert first_manifest is not None
    assert first_manifest.is_bound is False
    assert [row.root for row in first_manifest.dev_scan_roots] == [str(root.resolve())]
    assert len(first_manifest.dev_scan_files) == 1
    assert first_manifest.dev_scan_files[0].path == str(components_file.resolve())
    assert first_manifest.dev_scan_files[0].byte_count == len(components_file.read_bytes())
    predicate_rows = {
        row.predicate: row.classification for row in first_manifest.predicate_provenance
    }
    assert predicate_rows["development_scan_contributed_bytes"] == "recomputed"
    assert predicate_rows["development_scan_import_closure"] == "not_established"

    components_file.write_text(
        "# same discovery marker, different contributed bytes\n__polisyos_components__ = []\n",
        encoding="utf-8",
    )
    second = discover_components(groups=[], include_dev_scan=True, dev_scan_paths=[root])

    assert second.manifest is not None
    assert second.manifest.manifest_id != first_manifest.manifest_id
    assert second.manifest.dev_scan_files[0].sha256 != first_manifest.dev_scan_files[0].sha256


def test_discovery_manifest_marks_declared_missing_dev_root_unbound(tmp_path: Path) -> None:
    missing = tmp_path / "missing-pack-root"

    report = discover_components(groups=[], include_dev_scan=True, dev_scan_paths=[missing])

    assert report.manifest is not None
    assert report.manifest.is_bound is False
    assert report.manifest.dev_scan_roots[0].exists is False
    assert any(
        item.startswith("dev_scan_root_not_found:") for item in report.manifest.unbound_inputs
    )


def test_discovery_manifest_fails_closed_when_entry_point_enumeration_fails(
    monkeypatch,
) -> None:
    def _raise(*, group: str):
        raise RuntimeError(f"enumeration unavailable for {group}")

    monkeypatch.setattr(
        "polisyos.core.components.discovery.list_entry_points",
        _raise,
    )

    report = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )

    assert report.manifest is not None
    assert report.manifest.is_bound is False
    assert (
        "entry_point_group_enumeration_not_established:polisyos.foundry_methods"
        in report.manifest.unbound_inputs
    )
    predicates = {row.predicate: row.classification for row in report.manifest.predicate_provenance}
    assert predicates["entry_point_group_enumeration"] == "not_established"


def test_discovery_manifest_excludes_volatile_error_message_from_identity(
    monkeypatch,
) -> None:
    calls = iter(("first volatile detail", "second volatile detail"))

    class _VolatileEntryPoint(_FakeEntryPoint):
        def load(self):
            raise RuntimeError(next(calls))

    entry_points_text = (
        "[polisyos.foundry_methods]\nroads.method.volatile = roads.method.volatile:factory\n"
    )
    entry_point = _VolatileEntryPoint(
        group=ENTRY_POINT_GROUP_FOUNDRY_METHODS,
        name="roads.method.volatile",
        loader=None,
        dist=_FakeDistribution(
            name="roads-volatile",
            version="1.0.0",
            entry_points_text=entry_points_text,
        ),
    )
    monkeypatch.setattr(
        "polisyos.core.components.discovery.list_entry_points",
        lambda *, group: [entry_point],
    )

    first = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )
    second = discover_components(
        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
        include_dev_scan=False,
    )

    assert first.manifest is not None
    assert second.manifest is not None
    assert first.errors[0].message != second.errors[0].message
    assert first.manifest.manifest_id == second.manifest.manifest_id
    assert first.manifest.unbound_inputs == second.manifest.unbound_inputs
