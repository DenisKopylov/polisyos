"""Behavioral tests for DomainPlugin discovery and its runtime consumer."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from polisyos.foundry.plugins.api import PolisySimulator
from polisyos.foundry.plugins.core import DomainConfig, DomainPlugin, PluginRegistry
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


def test_registry_rejects_non_domain_objects_at_registration(
    registry: PluginRegistry,
) -> None:
    """The central registry refuses values outside the declared plugin ABI."""
    with pytest.raises(TypeError, match="DomainPlugin"):
        registry.register(object())  # type: ignore[arg-type]

    assert registry.list_plugins() == []
