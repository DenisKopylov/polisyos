from __future__ import annotations

import tomllib
from pathlib import Path

from polisyos.core.components import (
    ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    ENTRY_POINT_GROUP_SCIENTIST_NODES,
    Capability,
    ComponentKind,
    ComponentProvider,
    DeclaredBuiltinLoader,
    DiscoveryDeclaredBuiltinLoaderIdentity,
    discover_components,
)
from polisyos.scientist.nodes import discover_scientist_nodes
from polisyos.scientist.nodes.components import (
    SCIENTIST_NODES_API_VERSION,
    builtin_node_components,
)
from polisyos.scientist.orchestration.engine.registry import (
    SCIENTIST_NODE_BUILTIN_LOADER,
    NodeRegistry,
    discover_nodes,
)


def _scientist_node_extension_point() -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[4]
    extension_points = tomllib.loads(
        (repo_root / "architecture/extension_points.toml").read_text(encoding="utf-8")
    )["extension_point"]
    matches = [
        row for row in extension_points if row.get("name") == "polisyos.scientist_nodes"
    ]
    if len(matches) != 1:
        raise AssertionError("Scientist node extension point must be unique")
    row = matches[0]
    target = row.get("builtin_loader")
    group = row.get("entry_point_group")
    dynamic_target = row.get("dynamic_import_target")
    if (
        not isinstance(target, str)
        or not isinstance(group, str)
        or not isinstance(dynamic_target, str)
    ):
        raise AssertionError(
            "Scientist extension point must declare a typed loader target and group"
        )
    return {
        "name": "polisyos.scientist_nodes",
        "builtin_loader": target,
        "entry_point_group": group,
        "dynamic_import_target": dynamic_target,
    }


def _assert_declared_loader_identity(report, *, name: str, target: str, group: str) -> None:
    assert report.manifest is not None
    identity = DiscoveryDeclaredBuiltinLoaderIdentity(
        name=name,
        target=target,
        group=group,
    )
    assert report.manifest.declared_builtin_loaders == (identity,)
    assert report.manifest.content_payload()["declared_builtin_loaders"] == [
        identity.as_dict()
    ]


def test_builtin_nodes_are_component_providers() -> None:
    components = builtin_node_components()
    component_ids = {str(component.metadata.component_id) for component in components}

    assert SCIENTIST_NODES_API_VERSION == ">=1.0.0,<2.0.0"
    assert "scientist.node_build_data_snapshot@1.0.0" in component_ids
    assert "scientist.node_run_policy_funnel_level5@1.0.0" not in component_ids
    for component in components:
        assert isinstance(component, ComponentProvider)
        assert component.metadata.kind is ComponentKind.SCIENTIST_NODE
        assert component.metadata.capabilities & Capability.SCIENTIST_NODE
        assert str(component.create().spec.metadata.component_id) == str(
            component.metadata.component_id
        )


def test_callable_builtin_loader_keeps_legacy_v1_manifest_shape() -> None:
    report = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[("legacy-empty", lambda: ())],
    )

    assert report.errors == []
    assert report.components == []
    assert report.manifest is not None
    assert report.manifest.schema_version == "policyos.component_discovery_manifest.v1"
    assert report.manifest.builtin_loaders == ("legacy-empty",)
    assert report.manifest.declared_builtin_loaders == ()
    assert "declared_builtin_loaders" not in report.manifest.content_payload()


def test_discover_nodes_loads_builtin_component_loader() -> None:
    registry = NodeRegistry()

    report = discover_nodes(
        registry,
        include_entry_points=False,
        include_dev_scan=False,
    )

    assert report.errors == []
    assert report.discovery_errors == []
    assert "scientist.node_build_data_snapshot@1.0.0" in report.registered
    node = registry.get("scientist.node_build_data_snapshot@1.0.0")
    assert node.spec.metadata.kind is ComponentKind.SCIENTIST_NODE


def test_extension_point_target_drives_real_builtin_provider_and_registry() -> None:
    extension = _scientist_node_extension_point()
    target = extension["builtin_loader"]
    group = extension["entry_point_group"]

    assert target == SCIENTIST_NODE_BUILTIN_LOADER
    assert group == ENTRY_POINT_GROUP_SCIENTIST_NODES
    assert extension["dynamic_import_target"] == (
        f"entry-point group {group} or builtin loader {target}"
    )

    loaded = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[DeclaredBuiltinLoader(target=target, group=group)],
    )
    assert loaded.errors == []
    assert loaded.manifest is not None
    assert loaded.manifest.builtin_loaders == (target,)
    _assert_declared_loader_identity(
        loaded,
        name=target,
        target=target,
        group=group,
    )
    assert all(row.group == group for row in loaded.manifest.components)
    assert "scientist.node_build_data_snapshot@1.0.0" in {
        str(row.metadata.component_id) for row in loaded.components
    }
    assert all(
        row.source.source_type == "builtin_loader" and row.source.group == group
        for row in loaded.components
    )
    assert all(isinstance(row.component, ComponentProvider) for row in loaded.components)

    registry = NodeRegistry()
    report = discover_nodes(
        registry,
        include_entry_points=False,
        include_builtin_nodes=True,
        include_dev_scan=False,
    )
    assert report.errors == []
    assert "scientist.node_build_data_snapshot@1.0.0" in report.registered
    node = registry.get("scientist.node_build_data_snapshot@1.0.0")
    assert node.spec.metadata.kind is ComponentKind.SCIENTIST_NODE


def test_invalid_declared_target_does_not_become_a_registered_provider() -> None:
    extension = _scientist_node_extension_point()
    declared_target = extension["builtin_loader"]
    wrong_target = declared_target.replace(
        "__polisyos_components__", "__missing_components__"
    )
    assert wrong_target != declared_target
    assert extension["builtin_loader"] == SCIENTIST_NODE_BUILTIN_LOADER

    report = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[
            DeclaredBuiltinLoader(
                target=wrong_target,
                group=extension["entry_point_group"],
            )
        ],
    )
    assert report.components == []
    assert len(report.errors) == 1
    assert report.manifest is not None
    assert report.manifest.is_bound is False
    _assert_declared_loader_identity(
        report,
        name=wrong_target,
        target=wrong_target,
        group=extension["entry_point_group"],
    )


def test_public_node_discovery_facade_returns_registry_and_report() -> None:
    registry, report = discover_scientist_nodes(include_dev_scan=False)

    assert report.errors == []
    assert "scientist.node_build_decision_packet@1.5.0" in {
        str(spec.metadata.component_id) for spec in registry.list()
    }


def test_declared_builtin_loader_rejects_mismatched_discovery_name() -> None:
    extension = _scientist_node_extension_point()
    target = extension["builtin_loader"]

    report = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[
            (
                "polisyos.scientist.nodes.components:wrong_export",
                DeclaredBuiltinLoader(
                    target=target,
                    group=extension["entry_point_group"],
                ),
            )
        ],
    )

    assert report.components == []
    assert len(report.errors) == 1
    assert report.errors[0].error_type == "ValueError"
    assert report.manifest is not None
    assert report.manifest.is_bound is False
    _assert_declared_loader_identity(
        report,
        name="polisyos.scientist.nodes.components:wrong_export",
        target=target,
        group=extension["entry_point_group"],
    )


def test_declared_builtin_loader_rejects_unregistered_group() -> None:
    extension = _scientist_node_extension_point()

    report = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[
            DeclaredBuiltinLoader(
                target=extension["builtin_loader"],
                group="polisyos.unregistered_group",
            )
        ],
    )

    assert report.components == []
    assert len(report.errors) == 1
    assert report.errors[0].error_type == "ValueError"
    assert report.manifest is not None
    assert report.manifest.is_bound is False
    _assert_declared_loader_identity(
        report,
        name=extension["builtin_loader"],
        target=extension["builtin_loader"],
        group="polisyos.unregistered_group",
    )


def test_declared_builtin_loader_rejects_registered_group_kind_mismatch() -> None:
    extension = _scientist_node_extension_point()
    target = extension["builtin_loader"]
    wrong_group = ENTRY_POINT_GROUP_FOUNDRY_METHODS
    assert wrong_group != extension["entry_point_group"]

    report = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[DeclaredBuiltinLoader(target=target, group=wrong_group)],
    )

    assert report.components == []
    assert report.errors
    assert all(error.error_type == "ComponentKindMismatch" for error in report.errors)
    assert all(error.details["target"] == target for error in report.errors)
    assert all(error.details["group"] == wrong_group for error in report.errors)
    assert all(
        error.details["expected_kind"] == ComponentKind.FOUNDRY_METHOD.value
        for error in report.errors
    )
    assert all(
        error.details["actual_kind"] == ComponentKind.SCIENTIST_NODE.value
        for error in report.errors
    )
    assert report.manifest is not None
    assert report.manifest.is_bound is False
    _assert_declared_loader_identity(
        report,
        name=target,
        target=target,
        group=wrong_group,
    )
    assert (
        "discovery_error:builtin_loader:"
        f"{target}:0:ComponentKindMismatch:group={wrong_group}:"
        "expected_kind=foundry_method:actual_kind=scientist_node"
    ) in report.manifest.unbound_inputs


def test_declared_builtin_loader_missing_property_fails_closed() -> None:
    report = discover_components(
        groups=[],
        include_dev_scan=False,
        builtin_loaders=[
            DeclaredBuiltinLoader(
                target="missing-separator",
                group=ENTRY_POINT_GROUP_SCIENTIST_NODES,
            )
        ],
    )

    assert report.components == []
    assert len(report.errors) == 1
    assert report.errors[0].source == "builtin_loader"
    assert report.errors[0].error_type == "ValueError"
    assert report.manifest is not None
    assert report.manifest.is_bound is False
    _assert_declared_loader_identity(
        report,
        name="missing-separator",
        target="missing-separator",
        group=ENTRY_POINT_GROUP_SCIENTIST_NODES,
    )


def test_empty_declared_builtin_loader_binds_group_before_target_load(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "empty_builtin_fixture.py").write_text(
        "def empty_components():\n    return ()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    target = "empty_builtin_fixture:empty_components"
    groups = (
        ENTRY_POINT_GROUP_SCIENTIST_NODES,
        ENTRY_POINT_GROUP_FOUNDRY_METHODS,
    )
    reports = [
        discover_components(
            groups=[],
            include_dev_scan=False,
            builtin_loaders=[DeclaredBuiltinLoader(target=target, group=group)],
        )
        for group in groups
    ]

    for report, group in zip(reports, groups, strict=True):
        assert report.errors == []
        assert report.components == []
        assert report.manifest is not None
        assert report.manifest.is_bound is True
        assert report.manifest.schema_version == "policyos.component_discovery_manifest.v2"
        assert report.manifest.builtin_loaders == (target,)
        _assert_declared_loader_identity(
            report,
            name=target,
            target=target,
            group=group,
        )
    assert reports[0].manifest is not None
    assert reports[1].manifest is not None
    assert reports[0].manifest.manifest_id != reports[1].manifest.manifest_id
    assert (
        reports[0].manifest.content_payload()["declared_builtin_loaders"]
        != reports[1].manifest.content_payload()["declared_builtin_loaders"]
    )


def test_builtin_switch_stays_effective_when_entry_points_are_disabled() -> None:
    extension = _scientist_node_extension_point()
    assert extension["builtin_loader"] == SCIENTIST_NODE_BUILTIN_LOADER
    registry = NodeRegistry()

    report = discover_nodes(
        registry,
        include_entry_points=False,
        include_builtin_nodes=False,
        include_dev_scan=False,
    )

    assert report.errors == []
    assert report.discovery_errors == []
    assert report.registered == []
    assert registry.list() == []
