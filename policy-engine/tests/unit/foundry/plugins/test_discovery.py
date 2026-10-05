"""Behavioral tests for DomainPlugin discovery and its runtime consumer."""

from __future__ import annotations

import importlib
import importlib.metadata
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.foundry.plugins.api import PolisySimulator
from polisyos.foundry.plugins.core import (
    DomainConfig,
    DomainPlugin,
    PluginMetadata,
    PluginRegistry,
)
from polisyos.foundry.plugins.discovery import auto_register_plugins

_NO_MATCHING_PACKAGE_PREFIX = "plg01_no_matching_distribution_"


@pytest.fixture
def registry() -> Iterator[PluginRegistry]:
    """Provide an empty global registry and restore it after each case."""
    result = PluginRegistry()
    result.clear()
    yield result
    result.clear()


def _isolate_installed_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep filesystem-declaration tests independent of installed packages."""
    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "polisyos.foundry.plugins.discovery.metadata.distributions",
        lambda: [],
    )


def _write_plugin(root: Path, directory: str, plugin_name: str, source: str) -> Path:
    """Create one small DomainPlugin declaration under an explicit dev root."""
    plugin_dir = root / directory
    plugin_dir.mkdir(parents=True)
    plugin_file = plugin_dir / "plugin.py"
    plugin_file.write_text(
        """
from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata


class Plugin(DomainPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name=PLUGIN_NAME,
            version="1.0",
            description="discovery consumer fixture",
        )

    def create_initial_state(self, config, rng_key):
        return {"selected_source": SOURCE}

    def get_mechanisms(self):
        return ()

    def get_reward_function(self):
        return lambda *_args, **_kwargs: None

    def get_objectives(self):
        return {}


PLUGIN_NAME = __PLUGIN_NAME__
SOURCE = __SOURCE__


def create_plugin():
    return Plugin()
""".replace("__PLUGIN_NAME__", repr(plugin_name)).replace("__SOURCE__", repr(source)),
        encoding="utf-8",
    )
    return plugin_file


class _FixturePlugin(DomainPlugin):
    """Minimal runtime-consumable plugin used to distinguish source winners."""

    def __init__(self, plugin_name: str, source: str) -> None:
        self._plugin_name = plugin_name
        self._source = source

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._plugin_name,
            version="1.0",
            description="source-precedence fixture",
        )

    def create_initial_state(self, config, rng_key):
        return {"selected_source": self._source}

    def get_mechanisms(self):
        return ()

    def get_reward_function(self):
        return lambda *_args, **_kwargs: None

    def get_objectives(self):
        return {}


def test_malformed_plugin_is_rejected_before_simulator_consumption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry: PluginRegistry,
) -> None:
    """A plugin whose metadata producer raises cannot enter the runtime registry."""
    _isolate_installed_sources(monkeypatch)
    plugin_dir = tmp_path / "malformed"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(
        """
from polisyos.foundry.plugins.core import DomainPlugin


class Plugin(DomainPlugin):
    @property
    def metadata(self):
        raise RuntimeError("plg01 hostile metadata")

    def create_initial_state(self, config, rng_key):
        return None

    def get_mechanisms(self):
        return ()

    def get_reward_function(self):
        return lambda *_args, **_kwargs: None

    def get_objectives(self):
        return {}


def create_plugin():
    return Plugin()
""",
        encoding="utf-8",
    )

    with pytest.warns(RuntimeWarning) as caught:
        auto_register_plugins(
            registry,
            search_paths=[tmp_path],
        )

    assert any("plg01 hostile metadata" in str(record.message) for record in caught)
    assert "malformed" not in [metadata.name for metadata in registry.list_plugins()]
    simulator = PolisySimulator(registry, auto_discover=False)
    with pytest.raises(ValueError, match="Unknown domain 'malformed'"):
        simulator.add_domain("malformed")


def test_missing_dev_root_cannot_register_or_be_consumed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry: PluginRegistry,
) -> None:
    """An absent declared root does not make a requested domain available."""
    _isolate_installed_sources(monkeypatch)

    auto_register_plugins(
        registry,
        search_paths=[tmp_path / "missing-root"],
    )

    simulator = PolisySimulator(registry, auto_discover=False)
    with pytest.raises(ValueError, match="Unknown domain 'plg01-missing'"):
        simulator.add_domain("plg01-missing")


def test_duplicate_identity_uses_ordered_winner_in_simulator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry: PluginRegistry,
) -> None:
    """Duplicate names resolve by stable source order at the runtime consumer."""
    _isolate_installed_sources(monkeypatch)
    _write_plugin(tmp_path, "alpha-source", "plg01-shared", "alpha-source")
    _write_plugin(tmp_path, "zeta-source", "plg01-shared", "zeta-source")

    original_iterdir = Path.iterdir

    def reversed_root_iteration(path: Path) -> Iterator[Path]:
        entries = list(original_iterdir(path))
        return iter(reversed(entries)) if path == tmp_path else iter(entries)

    monkeypatch.setattr(Path, "iterdir", reversed_root_iteration)

    with pytest.warns(RuntimeWarning, match="Could not register plg01-shared"):
        registered = auto_register_plugins(registry, search_paths=[tmp_path])

    assert registered.count("plg01-shared") == 1
    simulator = PolisySimulator(registry, auto_discover=False)
    simulator.add_domain("plg01-shared", DomainConfig(n_agents=1)).initialize(seed=7)
    assert simulator.get_state().get_domain("plg01-shared") == {"selected_source": "alpha-source"}


def test_explicit_entrypoint_and_dev_plugins_precede_prefix_duplicates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry: PluginRegistry,
) -> None:
    """Both explicit declaration types outrank heuristic distribution scanning."""
    entrypoint_name = "plg01-entrypoint-shared"
    dev_name = "plg01-dev-shared"
    entrypoint_plugin = _FixturePlugin(entrypoint_name, "explicit-entrypoint")
    heuristic_entrypoint = _FixturePlugin(entrypoint_name, "prefix-entrypoint")
    heuristic_dev = _FixturePlugin(dev_name, "prefix-dev")
    _write_plugin(tmp_path, "declared-dev", dev_name, "explicit-dev")

    class EntryPoint:
        name = "plg01-explicit-entrypoint"

        def load(self):
            return entrypoint_plugin

    # Return both heuristic package names in reverse source-identity order.
    monkeypatch.setattr(
        "polisyos.foundry.plugins.discovery.core_discovery.list_entry_points",
        lambda **_kwargs: [EntryPoint()],
    )
    original_distributions = importlib.metadata.distributions
    monkeypatch.setattr(
        "polisyos.foundry.plugins.discovery.metadata.distributions",
        lambda: [
            SimpleNamespace(name="polisyos_plugin_dev_heuristic"),
            SimpleNamespace(name="polisyos_plugin_entrypoint_heuristic"),
        ],
    )
    heuristic_modules = {
        "polisyos_plugin_dev_heuristic": heuristic_dev,
        "polisyos_plugin_entrypoint_heuristic": heuristic_entrypoint,
    }
    original_import_module = importlib.import_module

    def import_heuristic_or_module(module_name: str):
        plugin = heuristic_modules.get(module_name)
        if plugin is not None:
            return SimpleNamespace(create_plugin=lambda: plugin)
        return original_import_module(module_name)

    monkeypatch.setattr(
        "polisyos.foundry.plugins.discovery.importlib.import_module",
        import_heuristic_or_module,
    )

    # Reverse the directory enumeration too; explicit precedence is categorical,
    # and each loader must not inherit the caller's filesystem iteration order.
    original_iterdir = Path.iterdir

    def reversed_root_iteration(path: Path) -> Iterator[Path]:
        entries = list(original_iterdir(path))
        return iter(reversed(entries)) if path == tmp_path else iter(entries)

    monkeypatch.setattr(Path, "iterdir", reversed_root_iteration)

    with pytest.warns(RuntimeWarning) as caught:
        registered = auto_register_plugins(registry, search_paths=[tmp_path])

    # The metadata patch models discovery only. Restore it before the real
    # simulator initializes JAX, which independently enumerates entry points.
    monkeypatch.setattr(
        "polisyos.foundry.plugins.discovery.metadata.distributions",
        original_distributions,
    )
    monkeypatch.setattr(
        "polisyos.foundry.plugins.discovery.importlib.import_module",
        original_import_module,
    )

    duplicate_warnings = [
        record for record in caught if issubclass(record.category, RuntimeWarning)
    ]
    assert len(duplicate_warnings) == 2
    warning_messages = [str(record.message) for record in duplicate_warnings]
    assert any(f"Could not register {entrypoint_name}" in message for message in warning_messages)
    assert any(f"Could not register {dev_name}" in message for message in warning_messages)
    assert registered.count(entrypoint_name) == 1
    assert registered.count(dev_name) == 1
    simulator = PolisySimulator(registry, auto_discover=False)
    simulator.add_domain(entrypoint_name, DomainConfig(n_agents=1))
    simulator.add_domain(dev_name, DomainConfig(n_agents=1))
    simulator.initialize(seed=7)
    assert simulator.get_state().get_domain(entrypoint_name) == {
        "selected_source": "explicit-entrypoint"
    }
    assert simulator.get_state().get_domain(dev_name) == {"selected_source": "explicit-dev"}


def test_registry_rejects_non_domain_objects_at_registration(
    registry: PluginRegistry,
) -> None:
    """The central registry refuses values outside the declared plugin ABI."""
    with pytest.raises(TypeError, match="DomainPlugin"):
        registry.register(object())  # type: ignore[arg-type]

    assert registry.list_plugins() == []
