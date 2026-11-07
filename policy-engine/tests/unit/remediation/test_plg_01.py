"""Behavioral witnesses for PLG-01 DomainPlugin discovery and source precedence."""

# Resource profile: L. These witnesses stop at discovery, metadata, and registry
# lifecycle; they do not construct JAX arrays, enter native pools, install packages,
# or run a simulation.

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from polisyos.core import discovery as core_discovery
from polisyos.core.discovery import discovery_module_name
from polisyos.foundry.plugins import discovery as plugin_discovery
from polisyos.foundry.plugins.core import (
    DomainPlugin,
    PluginCapability,
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
    messages = [str(record.message) for record in caught if "plg01-" in str(record.message)]
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
    source: str

    def __init__(
        self,
        name: str,
        events: list[str],
        dependencies: tuple[str, ...] = (),
    ) -> None:
        self._name = name
        self._events = events
        self._dependencies = dependencies
        self.source = "lifecycle"

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


def _source_plugin(name: str, source: str) -> _LifecyclePlugin:
    """Build one small ABI-valid plugin tagged with its discovery source."""
    plugin = _LifecyclePlugin(name, [])
    plugin.source = source
    return plugin


def _configure_prefix_candidate(
    monkeypatch: pytest.MonkeyPatch,
    distribution_name: str,
    plugin: DomainPlugin,
) -> None:
    """Expose one in-memory package through the real distribution-prefix path."""
    module_name = distribution_name.replace("-", "_")
    module = ModuleType(module_name)
    module.create_plugin = lambda: plugin
    original_import_module = plugin_discovery.importlib.import_module

    def import_module(name: str, package: str | None = None) -> ModuleType:
        if name == module_name:
            return module
        return original_import_module(name, package)

    monkeypatch.setattr(
        plugin_discovery.metadata,
        "distributions",
        lambda: [SimpleNamespace(name=distribution_name)],
    )
    monkeypatch.setattr(plugin_discovery.importlib, "import_module", import_module)


def test_discovery_orders_builtin_entry_point_dev_root_then_prefix_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """All four legacy sources retain declared precedence and local scope."""
    builtin = _source_plugin("plg01-shared", "builtin")
    entrypoint = _source_plugin("plg01-shared", "entrypoint")
    prefix = _source_plugin("plg01-shared", "prefix")
    dev_root = tmp_path / "declared"
    dev_root.mkdir()
    _write_dev_plugin(dev_root, "selected", "plg01-shared")

    class EntryPoint:
        name = "plg01-shared"
        value = "plg01_shared:Plugin"

        def load(self) -> DomainPlugin:
            return entrypoint

    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [builtin])
    monkeypatch.setattr(
        core_discovery,
        "list_entry_points",
        lambda *, group: [EntryPoint()] if group == "polisyos.plugins" else [],
    )
    _configure_prefix_candidate(monkeypatch, "plg01_prefix", prefix)

    plugins = plugin_discovery.discover_plugins(
        search_paths=[dev_root],
        package_prefix="plg01_",
    )

    sources = [
        cast("_LifecyclePlugin", plugin).source
        for plugin in plugins
        if plugin.metadata.name == "plg01-shared"
    ]
    assert sources == ["builtin", "entrypoint", "selected", "prefix"]


def test_declared_dev_root_wins_duplicate_id_over_distribution_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The explicit root is admitted before a same-ID heuristic package."""
    _isolate_core_entry_points(monkeypatch)
    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    _write_dev_plugin(tmp_path, "declared", "plg01-shared")
    _configure_prefix_candidate(
        monkeypatch,
        "polisyos_plugin_plg01",
        _source_plugin("plg01-shared", "prefix"),
    )

    registry = PluginRegistry()
    registry.clear()

    with pytest.warns(RuntimeWarning, match="Could not register plg01-shared"):
        registered = plugin_discovery.auto_register_plugins(registry, search_paths=[tmp_path])

    assert registered == ["plg01-shared"]
    assert cast("_LifecyclePlugin", registry.get("plg01-shared")).source == "declared"
    registry.clear()


def test_malformed_distribution_candidate_is_rejected_before_registration(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed metadata is refused at discovery, before registry consumption."""

    class MalformedPlugin(_LifecyclePlugin):
        @property
        def metadata(self) -> PluginMetadata:
            return cast("PluginMetadata", {"name": "plg01-malformed"})

    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    _isolate_core_entry_points(monkeypatch)
    _configure_prefix_candidate(
        monkeypatch,
        "polisyos_plugin_malformed",
        MalformedPlugin("plg01-malformed", []),
    )

    registry = PluginRegistry()
    registry.clear()
    with caplog.at_level("WARNING", logger=plugin_discovery.__name__):
        registered = plugin_discovery.auto_register_plugins(registry)

    assert registered == []
    assert registry.list_plugins() == []
    assert "DomainPlugin.metadata must return PluginMetadata" in caplog.text
    registry.clear()


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
    entrypoint_plugins = [plugin for plugin in plugins if plugin.metadata.name == "entrypoint"]
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

    assert [plugin.metadata.name for plugin in plugins if plugin.metadata.name == "selected"] == [
        "selected"
    ]
    assert not marker.exists()


@pytest.mark.parametrize(
    "replacement",
    [
        "return object()",
        "return None",
        "return PluginMetadata(name=['unhashable'], version='1', description='bad')",
        "return PluginMetadata(name='bad', version='1', description='bad', dependencies=([],))",
    ],
    ids=["object", "none", "name-shape", "dependency-shape"],
)
def test_malformed_dev_candidate_never_blocks_later_usable_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, replacement: str
) -> None:
    """Materialized metadata must be usable before it reaches the registry."""
    _isolate_core_entry_points(monkeypatch)
    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    bad = _write_dev_plugin(tmp_path, "a_bad", "bad") / "plugin.py"
    if replacement.startswith("return PluginMetadata"):
        text = _PLUGIN_SOURCE_TEMPLATE.format(name="bad", source="a_bad")
        start = text.index("        return PluginMetadata(")
        end = text.index("\n\n    def create_initial_state", start)
        text = text[:start] + "        " + replacement + text[end:]
    else:
        text = replacement.replace("return ", "def create_plugin():\n    return ") + "\n"
    bad.write_text(text)
    _write_dev_plugin(tmp_path, "z_good", "later-good")
    registry = PluginRegistry()
    registry.clear()
    try:
        with pytest.warns(RuntimeWarning, match="a_bad"):
            assert plugin_discovery.auto_register_plugins(registry, [tmp_path]) == ["later-good"]
        assert registry.get("later-good").metadata.name == "later-good"
        assert [x.name for x in registry.list_plugins()] == ["later-good"]
    finally:
        registry.clear()


@pytest.mark.parametrize("failure", ["ValueError", "TypeError", "changed-name"])
def test_registration_uses_admitted_metadata_without_repeated_callback_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    """A source callback is not re-run after registration or inside diagnostics."""
    _isolate_core_entry_points(monkeypatch)
    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    path = _write_dev_plugin(tmp_path, "a_selected", "selected") / "plugin.py"
    source = _PLUGIN_SOURCE_TEMPLATE.format(name="selected", source="a_selected")
    source = source.replace(
        "    def metadata(self):\n",
        "    def metadata(self):\n"
        "        self.reads = getattr(self, 'reads', 0) + 1\n"
        "        if self.reads > 2:\n"
        + (
            "            return PluginMetadata(name='changed', version='1', description='changed')\n"
            if failure == "changed-name"
            else f"            raise {failure}('metadata callback re-entered')\n"
        ),
    )
    path.write_text(source)
    _write_dev_plugin(tmp_path, "z_good", "later-good")
    registry = PluginRegistry()
    registry.clear()
    try:
        registered = plugin_discovery.auto_register_plugins(registry, [tmp_path])
        assert registered == ["selected", "later-good"]
        assert [x.name for x in registry.list_plugins()] == registered
        assert registry.get("selected").reads == 2
        assert registry.get("later-good").source == "z_good"
        assert registry.with_tag("not-present") == []
        assert registry.with_capability(PluginCapability.AGENTS) == []
    finally:
        registry.clear()


@pytest.mark.parametrize("field", ["capabilities", "tags"])
def test_malformed_filter_metadata_is_refused_before_later_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    """Registry filtering must not discover malformed admitted metadata later."""
    _isolate_core_entry_points(monkeypatch)
    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    path = _write_dev_plugin(tmp_path, "a_bad", "bad") / "plugin.py"
    source = _PLUGIN_SOURCE_TEMPLATE.format(name="bad", source="a_bad")
    source = source.replace(
        'description="PLG-01 test plugin",', f'description="bad", {field}=None,'
    )
    path.write_text(source)
    _write_dev_plugin(tmp_path, "z_good", "later-good")
    registry = PluginRegistry()
    registry.clear()
    try:
        with pytest.warns(RuntimeWarning, match="a_bad"):
            assert plugin_discovery.auto_register_plugins(registry, [tmp_path]) == ["later-good"]
        assert registry.with_tag("not-present") == []
    finally:
        registry.clear()


def test_registry_snapshot_preserves_override_abi_and_detaches_returned_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Discovery retains one-argument overrides and registry-owned metadata."""
    _isolate_core_entry_points(monkeypatch)
    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", lambda: [])
    _write_dev_plugin(tmp_path, "selected", "selected")
    calls = []

    class RecordingRegistry(PluginRegistry):
        _instance = None

        def register(self, plugin: DomainPlugin) -> None:
            calls.append(plugin)
            super().register(plugin)

    registry = RecordingRegistry()
    registry.clear()
    try:
        assert plugin_discovery.auto_register_plugins(registry, [tmp_path]) == ["selected"]
        assert calls == [registry.get("selected")]
        exported = registry.list_plugins()[0]
        exported.name = "changed"
        exported.dependencies = ("missing",)
        assert registry.list_plugins()[0].name == "selected"
        assert registry.list_plugins()[0].dependencies == ()
        registry.unregister("selected")
        assert registry.list_plugins() == []
    finally:
        registry.clear()


def test_failed_load_is_retried_and_filtering_does_not_load() -> None:
    """Registration and metadata queries do not latch a failed lifecycle hook."""
    events = []

    class RetryingPlugin(_LifecyclePlugin):
        def on_load(self) -> None:
            self._events.append("load")
            if len(self._events) == 1:
                raise RuntimeError("temporary load failure")

    plugin = RetryingPlugin("retry", events)
    registry = PluginRegistry()
    registry.clear()
    try:
        registry.register(plugin)
        assert registry.with_tag("missing") == []
        assert registry.with_capability(PluginCapability.AGENTS) == []
        assert events == []
        with pytest.raises(RuntimeError, match="temporary load"):
            registry.get("retry")
        assert registry.get("retry") is plugin
        assert registry.get("retry") is plugin
        assert events == ["load", "load"]
    finally:
        registry.clear()


def test_one_pass_registration_keeps_missing_dependency_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Source order is not silently replaced by a dependency retry loader."""
    child = _LifecyclePlugin("child", [], dependencies=("parent",))
    parent = _LifecyclePlugin("parent", [])
    monkeypatch.setattr(plugin_discovery, "discover_plugins", lambda _paths: [child, parent])
    registry = PluginRegistry()
    registry.clear()
    try:
        with pytest.warns(RuntimeWarning, match="requires 'parent'"):
            assert plugin_discovery.auto_register_plugins(registry) == ["parent"]
        with pytest.raises(KeyError, match="child"):
            registry.get("child")
        assert registry.get("parent") is parent
    finally:
        registry.clear()
