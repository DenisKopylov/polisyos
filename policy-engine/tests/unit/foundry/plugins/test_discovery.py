"""Behavioral witnesses for the legacy DomainPlugin discovery boundary."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import jax
import jax.numpy as jnp
import pytest

from polisyos.core import discovery as core_discovery
from polisyos.foundry.plugins import api as plugin_api
from polisyos.foundry.plugins import discovery as plugin_discovery
from polisyos.foundry.plugins.api import PolisySimulator
from polisyos.foundry.plugins.core import DomainConfig, DomainPlugin, PluginMetadata, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin

_NO_MATCHING_PACKAGE_PREFIX = "plg01_no_matching_distribution_"


class _FixturePlugin(DomainPlugin):
    """Small runtime-consumable fixture that identifies its discovery source."""

    def __init__(self, name: str, source: str) -> None:
        self._name = name
        self.source = source

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version="1.0",
            description="DomainPlugin discovery fixture",
        )

    def create_initial_state(self, config, rng_key):
        return {"source": self.source, "agents": config.n_agents, "seed": int(rng_key[0])}

    def get_mechanisms(self):
        return ()

    def get_reward_function(self):
        return lambda *_args, **_kwargs: None

    def get_objectives(self):
        return {}


@pytest.fixture
def registry() -> Iterator[PluginRegistry]:
    """Provide an empty global registry and restore its lifecycle state."""

    value = PluginRegistry()
    value.clear()
    yield value
    value.clear()


def _isolate_nonbuiltin_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(plugin_discovery.metadata, "distributions", lambda: [])


def _write_fixture(root: Path, directory: str, name: str, source: str) -> None:
    plugin_dir = root / directory
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        f"""
from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata

class Plugin(DomainPlugin):
    @property
    def metadata(self):
        return PluginMetadata(name={name!r}, version="1.0", description="fixture")

    def create_initial_state(self, config, rng_key):
        return {{"source": {source!r}}}

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
""",
        encoding="utf-8",
    )


def test_simulator_discovery_is_stable_and_keeps_economics_abi(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry: PluginRegistry,
) -> None:
    """Reversed source enumeration still resolves stable IDs through the old ABI."""

    _isolate_nonbuiltin_sources(monkeypatch)
    _write_fixture(tmp_path, "zeta-source", "plg01-shared", "zeta")
    _write_fixture(tmp_path, "alpha-source", "plg01-shared", "alpha")

    class EntryPoint:
        def __init__(self, name, plugin_class):
            self.name = name
            self.value = f"{plugin_class.__module__}:{plugin_class.__name__}"
            self.plugin_class = plugin_class

        def load(self):
            return self.plugin_class

    class AlphaEntrypointPlugin(_FixturePlugin):
        def __init__(self):
            super().__init__("plg01-entry-alpha", "entrypoint-alpha")

    class ZetaEntrypointPlugin(_FixturePlugin):
        def __init__(self):
            super().__init__("plg01-entry-zeta", "entrypoint-zeta")

    # Core sorts entry points even when importlib supplies a reversed sequence.
    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda *args, **kwargs: [
            EntryPoint("zeta", ZetaEntrypointPlugin),
            EntryPoint("alpha", AlphaEntrypointPlugin),
        ],
    )
    real_auto_register = plugin_discovery.auto_register_plugins

    def discover_into_simulator(target_registry, search_paths=None):
        return real_auto_register(target_registry, search_paths=[tmp_path])

    monkeypatch.setattr(plugin_api, "auto_register_plugins", discover_into_simulator)
    original_iterdir = Path.iterdir

    def reverse_declared_root(path: Path):
        entries = list(original_iterdir(path))
        return iter(reversed(entries)) if path == tmp_path else iter(entries)

    monkeypatch.setattr(Path, "iterdir", reverse_declared_root)

    with pytest.warns(RuntimeWarning, match="Could not register plg01-shared"):
        simulator = PolisySimulator(registry)

    assert registry.get("plg01-shared").source == "alpha"
    assert isinstance(registry.get("economics"), EconomicsPlugin)
    assert isinstance(registry.get("plg01-entry-alpha"), _FixturePlugin)
    assert isinstance(registry.get("plg01-entry-zeta"), _FixturePlugin)
    assert [meta.name for meta in registry.list_plugins()] == [
        "economics",
        "plg01-entry-alpha",
        "plg01-entry-zeta",
        "plg01-shared",
    ]

    # Exercise the resolved Economics plugin through its declared DomainPlugin ABI.
    economics = registry.get("economics")
    state = economics.create_initial_state(
        DomainConfig(n_agents=10, max_agents=10),
        jax.random.PRNGKey(7),
    )
    observation_builder = economics.get_observation_builder()
    observations = observation_builder(state)
    reward = economics.get_reward_function().compute(state, state)
    assert observations.shape[0] == 10
    assert jnp.isfinite(reward).all()
    assert economics.get_mechanisms()
    assert "gdp" in economics.get_objectives()

    simulator.add_domain("economics", DomainConfig(n_agents=10, max_agents=10)).initialize(seed=7)
    assert simulator.get_state().get_domain("economics").n_agents == 10


def test_malformed_candidates_are_rejected_and_discovery_does_not_verify(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry: PluginRegistry,
) -> None:
    """Invalid metadata and forged candidate flags cannot mint registry verification."""

    _isolate_nonbuiltin_sources(monkeypatch)
    malformed = tmp_path / "malformed"
    malformed.mkdir()
    (malformed / "plugin.py").write_text(
        """
from polisyos.foundry.plugins.core import DomainPlugin
class Plugin(DomainPlugin):
    @property
    def metadata(self):
        return None
    def create_initial_state(self, config, rng_key): return None
    def get_mechanisms(self): return ()
    def get_reward_function(self): return lambda *_args, **_kwargs: None
    def get_objectives(self): return {}
def create_plugin(): return Plugin()
""",
        encoding="utf-8",
    )
    bad_object = tmp_path / "bad-object"
    bad_object.mkdir()
    (bad_object / "plugin.py").write_text(
        "def create_plugin(): return object()\n",
        encoding="utf-8",
    )

    forged = _FixturePlugin("plg01-forged-verification", "candidate")
    forged.verified = True
    monkeypatch.setattr(
        plugin_discovery,
        "_discover_entry_point_plugins",
        lambda: [forged],
    )

    with pytest.warns(RuntimeWarning) as caught:
        registered = plugin_discovery.auto_register_plugins(registry, [tmp_path])

    assert any(
        "PluginMetadata" in str(row.message) or "Could not register" in str(row.message)
        for row in caught
    )
    assert "malformed" not in registered
    assert "bad-object" not in registered
    assert "plg01-forged-verification" in registered
    assert registry.get("plg01-forged-verification").verified is True
    # The existing registry exposes availability only; candidate flags are not
    # an owner-issued admission or verification artifact.
    assert not hasattr(registry, "verified")
    assert not hasattr(registry, "verification")
    simulator = PolisySimulator(registry, auto_discover=False)
    assert "plg01-forged-verification" in [m.name for m in registry.list_plugins()]
    with pytest.raises(ValueError, match="Unknown domain 'bad-object'"):
        simulator.add_domain("bad-object")


def test_registry_rejects_non_domain_and_absent_metadata_values(
    registry: PluginRegistry,
) -> None:
    """The runtime registry validates identity before storing any candidate."""

    with pytest.raises(TypeError, match="Only DomainPlugin instances"):
        registry.register(object())  # type: ignore[arg-type]

    class MissingMetadata(_FixturePlugin):
        @property
        def metadata(self):
            return None

    with pytest.raises(TypeError, match="Plugin.metadata must return PluginMetadata"):
        registry.register(MissingMetadata("plg01-missing-metadata", "malformed"))

    assert registry.list_plugins() == []
