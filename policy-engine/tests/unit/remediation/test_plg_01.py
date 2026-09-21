"""Behavioral witnesses for the PLG-01 DomainPlugin discovery migration.

These tests deliberately exercise the legacy DomainPlugin boundary while keeping
the source fixtures small.  They are test-first: the ordering and duplicate
assertions describe the intended Core-discovery behavior and are expected to be
red until the adapter is migrated.
"""

# Resource profile: L. These witnesses stop at discovery, metadata, and registry
# lifecycle; they do not construct JAX arrays, enter native pools, install packages,
# or run a simulation.

from __future__ import annotations

import sys
from collections.abc import Iterator
from types import ModuleType
from pathlib import Path

import pytest

from polisyos.core import discovery as core_discovery
from polisyos.core.discovery import discovery_module_name
from polisyos.foundry.plugins import discovery as plugin_discovery
from polisyos.foundry.plugins.core import (
    DomainPlugin,
    PluginMetadata,
    PluginRegistry,
)
from polisyos.foundry.plugins.economics import EconomicsPlugin


_NO_MATCHING_PACKAGE_PREFIX = "plg01_no_matching_distribution_"
_CORE_PLUGIN_MODULE_PREFIX = "_polisyos_plugins_scan_"


_PLUGIN_SOURCE_TEMPLATE = """
from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata


class Plugin(DomainPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name={name!r},
            version="1.0",
            description="PLG-01 test plugin",
        )

    def create_initial_state(self, config, rng_key):
        return None

    def get_mechanisms(self):
        return ()

    def get_reward_function(self):
        return lambda *_args, **_kwargs: None

    def get_objectives(self):
        return {{}}


def create_plugin():
    plugin = Plugin()
    plugin.source = {source!r}
    return plugin
"""


def _write_dev_plugin(root: Path, directory: str, name: str) -> Path:
    plugin_dir = root / directory
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        _PLUGIN_SOURCE_TEMPLATE.format(name=name, source=directory),
        encoding="utf-8",
    )
    return plugin_dir


def _write_broken_plugin(root: Path, directory: str, message: str) -> Path:
    plugin_dir = root / directory
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        f"raise RuntimeError({message!r})\n",
        encoding="utf-8",
    )
    return plugin_dir


def _isolate_core_entry_points(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests focused while exercising the Core metadata seam."""

    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda *args, **kwargs: [],
    )


def _reverse_root_iteration(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Make the source order adversarial so deterministic sorting is observable."""

    original_iterdir = Path.iterdir

    def reversed_iterdir(path: Path) -> Iterator[Path]:
        entries = list(original_iterdir(path))
        if root == path:
            return iter(reversed(entries))
        return iter(entries)

    monkeypatch.setattr(Path, "iterdir", reversed_iterdir)


def test_dev_plugins_preserve_domain_plugin_abi_and_stable_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Directory discovery returns DomainPlugins in reproducible source order."""

    _isolate_core_entry_points(monkeypatch)
    _write_dev_plugin(tmp_path, "alpha", "plg01-alpha")
    _write_dev_plugin(tmp_path, "zeta", "plg01-zeta")
    _reverse_root_iteration(monkeypatch, tmp_path)

    plugins = [
        plugin
        for plugin in plugin_discovery.discover_plugins(
            search_paths=[tmp_path],
            package_prefix=_NO_MATCHING_PACKAGE_PREFIX,
        )
        if plugin.metadata.name.startswith("plg01-")
    ]

    assert [plugin.metadata.name for plugin in plugins] == [
        "plg01-alpha",
        "plg01-zeta",
    ]
    assert all(isinstance(plugin, DomainPlugin) for plugin in plugins)


def test_dev_plugin_loading_uses_the_core_file_loader_seam(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The adapter delegates source-file loading to Core's shared primitive."""

    _isolate_core_entry_points(monkeypatch)
    plugin_file = _write_dev_plugin(tmp_path, "selected", "plg01-selected") / "plugin.py"
    calls: list[tuple[Path, str]] = []
    original_loader = core_discovery.load_module_from_file

    def recording_loader(path: Path, *, module_name: str) -> ModuleType:
        calls.append((path, module_name))
        return original_loader(path, module_name=module_name)

    monkeypatch.setattr(core_discovery, "load_module_from_file", recording_loader)

    plugins = [
        plugin
        for plugin in plugin_discovery.discover_plugins(
            search_paths=[tmp_path],
            package_prefix=_NO_MATCHING_PACKAGE_PREFIX,
        )
        if plugin.metadata.name == "plg01-selected"
    ]
    expected_module_name = core_discovery.discovery_module_name(
        plugin_file,
        prefix=_CORE_PLUGIN_MODULE_PREFIX,
        algorithm="sha1",
        digest_length=40,
    )

    assert [plugin.metadata.name for plugin in plugins] == ["plg01-selected"]
    assert calls == [(plugin_file, expected_module_name)]


def test_import_errors_are_reported_in_stable_source_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A bad source remains visible and error ordering does not depend on readdir."""

    _isolate_core_entry_points(monkeypatch)
    alpha_dir = _write_broken_plugin(
        tmp_path,
        "plg01-alpha-broken",
        "plg01-alpha-import-error",
    )
    zeta_dir = _write_broken_plugin(
        tmp_path,
        "plg01-zeta-broken",
        "plg01-zeta-import-error",
    )
    _reverse_root_iteration(monkeypatch, tmp_path)
    modules_before = set(sys.modules)

    with pytest.warns(RuntimeWarning) as caught:
        plugins = plugin_discovery.discover_plugins(
            search_paths=[tmp_path],
            package_prefix=_NO_MATCHING_PACKAGE_PREFIX,
        )

    assert [plugin for plugin in plugins if plugin.metadata.name.startswith("plg01-")] == []
    messages = [
        str(record.message)
        for record in caught
        if "plg01-" in str(record.message)
    ]
    assert len(messages) == 2
    assert messages == sorted(messages)
    assert "plg01-alpha-import-error" in messages[0]
    assert "plg01-zeta-import-error" in messages[1]

    broken_files = {alpha_dir / "plugin.py", zeta_dir / "plugin.py"}
    core_candidate_names = {
        discovery_module_name(
            path,
            prefix=_CORE_PLUGIN_MODULE_PREFIX,
            algorithm="sha1",
            digest_length=40,
        )
        for path in broken_files
    }
    assert core_candidate_names.isdisjoint(sys.modules)
    leaked_file_modules = {
        name
        for name in set(sys.modules) - modules_before
        if getattr(sys.modules[name], "__file__", None)
        and Path(sys.modules[name].__file__).resolve() in broken_files
    }
    assert leaked_file_modules == set()


def test_duplicate_ids_keep_deterministic_winner_and_visible_registration_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Duplicate DomainPlugin IDs do not silently depend on filesystem order."""

    _isolate_core_entry_points(monkeypatch)
    _write_dev_plugin(tmp_path, "alpha-source", "plg01-shared")
    _write_dev_plugin(tmp_path, "zeta-source", "plg01-shared")
    _reverse_root_iteration(monkeypatch, tmp_path)

    registry = PluginRegistry()
    registry.clear()

    with pytest.warns(RuntimeWarning, match="Could not register plg01-shared"):
        registered = plugin_discovery.auto_register_plugins(
            registry,
            search_paths=[tmp_path],
        )

    assert "plg01-shared" in registered
    assert registry.get("plg01-shared").source == "alpha-source"
    registry.clear()


class _LifecyclePlugin(DomainPlugin):
    def __init__(
        self,
        name: str,
        events: list[str],
        dependencies: tuple[str, ...] = (),
    ) -> None:
        self._name = name
        self._events = events
        self._dependencies = dependencies

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version="1.0",
            description="PLG-01 lifecycle witness",
            dependencies=self._dependencies,
        )

    def create_initial_state(self, config, rng_key):
        return None

    def get_mechanisms(self):
        return ()

    def get_reward_function(self):
        return lambda *_args, **_kwargs: None

    def get_objectives(self):
        return {}

    def on_load(self) -> None:
        self._events.append(f"{self._name}:load")

    def on_unload(self) -> None:
        self._events.append(f"{self._name}:unload")


def test_domain_plugin_dependencies_and_lifecycle_remain_intact() -> None:
    """The discovery move must not change registry dependency or hook semantics."""

    events: list[str] = []
    dependency = _LifecyclePlugin("dependency", events)
    dependent = _LifecyclePlugin("dependent", events, dependencies=("dependency",))
    registry = PluginRegistry()
    registry.clear()

    registry.register(dependency)
    registry.register(dependent)
    assert registry.get("dependent") is dependent
    assert events == ["dependent:load"]

    with pytest.raises(ValueError, match="depends on it"):
        registry.unregister("dependency")

    registry.unregister("dependent")
    registry.unregister("dependency")
    assert events == ["dependent:load", "dependent:unload"]


def test_legacy_entry_point_group_and_domain_plugin_abi_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Declared ``polisyos.plugins`` entry points still construct DomainPlugins."""

    seen_groups: list[str] = []

    class EntryPointPlugin(DomainPlugin):
        @property
        def metadata(self) -> PluginMetadata:
            return PluginMetadata(
                name="entrypoint",
                version="1.0",
                description="PLG-01 entry point witness",
            )

        def create_initial_state(self, config, rng_key):
            return None

        def get_mechanisms(self):
            return ()

        def get_reward_function(self):
            return lambda *_args, **_kwargs: None

        def get_objectives(self):
            return {}

    class EntryPoint:
        name = "entrypoint"
        value = "plg01_entrypoint:EntryPointPlugin"

        def load(self):
            return EntryPointPlugin

    def fake_entry_points(*, group: str):
        seen_groups.append(group)
        return [EntryPoint()]

    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        fake_entry_points,
    )

    plugins = plugin_discovery.discover_plugins(
        package_prefix=_NO_MATCHING_PACKAGE_PREFIX,
    )

    assert seen_groups == ["polisyos.plugins"]
    entrypoint_plugins = [
        plugin for plugin in plugins if plugin.metadata.name == "entrypoint"
    ]
    assert len(entrypoint_plugins) == 1
    assert isinstance(entrypoint_plugins[0], DomainPlugin)
    assert seen_groups[0] != plugin_discovery.CANONICAL_METHOD_ENTRY_POINT_GROUP


def test_builtin_economics_plugin_preserves_domain_abi_and_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real builtin plugin remains a DomainPlugin through registry lifecycle."""

    _isolate_core_entry_points(monkeypatch)
    plugins = plugin_discovery.discover_plugins(
        package_prefix=_NO_MATCHING_PACKAGE_PREFIX,
    )
    economics = next(plugin for plugin in plugins if isinstance(plugin, EconomicsPlugin))

    assert isinstance(economics, DomainPlugin)
    assert economics.metadata.name == "economics"
    assert callable(economics.get_reward_function)
    assert callable(economics.get_objectives)

    lifecycle: list[str] = []
    monkeypatch.setattr(economics, "on_load", lambda: lifecycle.append("load"))
    monkeypatch.setattr(economics, "on_unload", lambda: lifecycle.append("unload"))

    registry = PluginRegistry()
    registry.clear()
    registry.register(economics)
    assert registry.get("economics") is economics
    registry.unregister("economics")
    assert lifecycle == ["load", "unload"]


def test_explicit_dev_root_does_not_import_unselected_sibling(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A declared dev root is bounded; sibling files are not an environment scan."""

    _isolate_core_entry_points(monkeypatch)
    declared_root = tmp_path / "declared"
    unselected_root = tmp_path / "unselected"
    declared_root.mkdir()
    unselected_root.mkdir()
    _write_dev_plugin(declared_root, "selected", "selected")
    marker = tmp_path / "unselected-imported"
    (unselected_root / "unwanted" / "plugin.py").parent.mkdir()
    (unselected_root / "unwanted" / "plugin.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n",
        encoding="utf-8",
    )

    plugins = plugin_discovery.discover_plugins(
        search_paths=[declared_root],
        package_prefix=_NO_MATCHING_PACKAGE_PREFIX,
    )

    assert [
        plugin.metadata.name
        for plugin in plugins
        if plugin.metadata.name == "selected"
    ] == ["selected"]
    assert not marker.exists()
