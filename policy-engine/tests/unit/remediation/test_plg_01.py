"""Behavioral witnesses for the PLG-01 DomainPlugin discovery migration.

These tests deliberately exercise the legacy DomainPlugin boundary while keeping
the source fixtures small.  They are test-first: the ordering and duplicate
assertions describe the intended Core-discovery behavior and are expected to be
red until the adapter is migrated.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from polisyos.foundry.plugins import discovery as plugin_discovery
from polisyos.foundry.plugins.core import (
    DomainPlugin,
    PluginMetadata,
    PluginRegistry,
)


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


def _isolate_non_dev_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the test focused on the explicitly supplied development source."""

    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    monkeypatch.setattr(
        plugin_discovery,
        "_discover_installed_plugins",
        lambda _prefix: [],
    )


def _reverse_root_iteration(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Make the source order adversarial so deterministic sorting is observable."""

    original_iterdir = Path.iterdir

    def reversed_iterdir(path: Path) -> Iterator[Path]:
        entries = list(original_iterdir(path))
        if path == root:
            return iter(reversed(entries))
        return iter(entries)

    monkeypatch.setattr(Path, "iterdir", reversed_iterdir)


def test_dev_plugins_preserve_domain_plugin_abi_and_stable_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Directory discovery returns DomainPlugins in reproducible source order."""

    _isolate_non_dev_sources(monkeypatch)
    _write_dev_plugin(tmp_path, "alpha", "alpha")
    _write_dev_plugin(tmp_path, "zeta", "zeta")
    _reverse_root_iteration(monkeypatch, tmp_path)

    plugins = plugin_discovery.discover_plugins(search_paths=[tmp_path])

    assert [plugin.metadata.name for plugin in plugins] == ["alpha", "zeta"]
    assert all(isinstance(plugin, DomainPlugin) for plugin in plugins)


def test_import_errors_are_reported_in_stable_source_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A bad source remains visible and error ordering does not depend on readdir."""

    _isolate_non_dev_sources(monkeypatch)
    _write_broken_plugin(tmp_path, "alpha-broken", "alpha-import-error")
    _write_broken_plugin(tmp_path, "zeta-broken", "zeta-import-error")
    _reverse_root_iteration(monkeypatch, tmp_path)
    modules_before = set(sys.modules)

    with pytest.warns(RuntimeWarning) as caught:
        plugins = plugin_discovery.discover_plugins(search_paths=[tmp_path])

    assert plugins == []
    messages = [str(record.message) for record in caught]
    assert len(messages) == 2
    assert messages == sorted(messages)
    assert "alpha-import-error" in messages[0]
    assert "zeta-import-error" in messages[1]
    leaked_modules = {
        name for name in set(sys.modules) - modules_before if name.startswith("plugin_")
    }
    assert leaked_modules == set()


def test_duplicate_ids_keep_deterministic_winner_and_visible_registration_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Duplicate DomainPlugin IDs do not silently depend on filesystem order."""

    _isolate_non_dev_sources(monkeypatch)
    _write_dev_plugin(tmp_path, "alpha-source", "shared")
    _write_dev_plugin(tmp_path, "zeta-source", "shared")
    _reverse_root_iteration(monkeypatch, tmp_path)

    registry = PluginRegistry()
    registry.clear()

    with pytest.warns(RuntimeWarning, match="Could not register shared"):
        registered = plugin_discovery.auto_register_plugins(
            registry,
            search_paths=[tmp_path],
        )

    assert registered == ["shared"]
    assert getattr(registry.get("shared"), "source") == "alpha-source"
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

    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
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

        def load(self):
            return EntryPointPlugin

    class FakePkgResources:
        working_set: tuple[object, ...] = ()

        @staticmethod
        def iter_entry_points(group: str):
            seen_groups.append(group)
            return [EntryPoint()]

    monkeypatch.setitem(sys.modules, "pkg_resources", FakePkgResources())
    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    monkeypatch.setattr(plugin_discovery, "_discover_directory_plugins", lambda _path: [])

    plugins = plugin_discovery.discover_plugins()

    assert seen_groups == ["polisyos.plugins"]
    assert [plugin.metadata.name for plugin in plugins] == ["entrypoint"]
    assert isinstance(plugins[0], DomainPlugin)
    assert plugin_discovery.CANONICAL_METHOD_ENTRY_POINT_GROUP != seen_groups[0]


def test_explicit_dev_root_does_not_import_unselected_sibling(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A declared dev root is bounded; sibling files are not an environment scan."""

    _isolate_non_dev_sources(monkeypatch)
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

    plugins = plugin_discovery.discover_plugins(search_paths=[declared_root])

    assert [plugin.metadata.name for plugin in plugins] == ["selected"]
    assert not marker.exists()
