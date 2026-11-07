"""Native installed-metadata witnesses for legacy DomainPlugin discovery.

The temporary distribution below is an explicitly declared test fixture on
``sys.path``. It is not evidence about unrelated installed distributions.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
from dataclasses import replace
from importlib import metadata
from pathlib import Path
from textwrap import dedent
from types import ModuleType, SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.plugins import discovery as plugin_discovery
from polisyos.foundry.plugins.api import PolisySimulator
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.discovery import discover_plugins
from polisyos.foundry.plugins.economics import EconomicsPlugin

_DISTRIBUTION = "plg01-native-installed-fixture"
_MODULE = "plg01_native_installed_fixture"
_PLUGIN = "plg01-native-economics"
_ENTRY_POINT = "plg01_native_economics"
_GROUP = "polisyos.plugins"


def _write_installed_fixture(root: Path, *, group: str = _GROUP) -> tuple[Path, str]:
    """Write a tiny importable provider and real dist-info entrypoint metadata."""
    module_source = dedent(
        f"""\
        from dataclasses import replace

        from polisyos.foundry.plugins.economics import EconomicsPlugin


        class NativeEconomicsPlugin(EconomicsPlugin):
            @property
            def metadata(self):
                return replace(super().metadata, name={_PLUGIN!r})
        """
    )
    module_path = root / f"{_MODULE}.py"
    module_path.write_text(module_source, encoding="utf-8")

    dist_info = root / f"{_DISTRIBUTION.replace('-', '_')}-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {_DISTRIBUTION}\nVersion: 1.0\n\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        f"[{group}]\n{_ENTRY_POINT} = {_MODULE}:NativeEconomicsPlugin\n",
        encoding="utf-8",
    )
    return module_path, hashlib.sha256(module_source.encode("utf-8")).hexdigest()


def test_declared_entry_point_reaches_native_economics_simulator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared installed test distribution reaches the real simulator state/run."""
    module_path, expected_module_sha256 = _write_installed_fixture(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    matching = [
        entry_point
        for entry_point in metadata.entry_points(group=_GROUP)
        if entry_point.name == _ENTRY_POINT
    ]
    assert len(matching) == 1
    entry_point = matching[0]
    assert entry_point.group == _GROUP
    assert entry_point.value == f"{_MODULE}:NativeEconomicsPlugin"
    assert entry_point.dist is not None
    assert entry_point.dist.metadata["Name"] == _DISTRIBUTION
    assert entry_point.dist.version == "1.0"

    provider_class = entry_point.load()
    provider_module = importlib.import_module(_MODULE)
    assert provider_class.__module__ == _MODULE
    assert Path(provider_module.__file__).resolve() == module_path.resolve()
    assert hashlib.sha256(module_path.read_bytes()).hexdigest() == expected_module_sha256

    registry = PluginRegistry()
    registry.clear()
    try:
        simulator = PolisySimulator(registry=registry, auto_discover=True)
        resolved = registry.get(_PLUGIN)
        assert isinstance(resolved, provider_class)
        assert resolved.metadata.name == _PLUGIN

        n_agents = 12
        max_agents = 24
        seed = 731
        simulator.add_domain(
            _PLUGIN,
            DomainConfig(n_agents=n_agents, max_agents=max_agents),
        )
        simulator.set_objective("native_gdp", _PLUGIN, "gdp")
        simulator.initialize(seed=seed)

        initial_state = simulator._state.get_domain(_PLUGIN)
        expected_plugin = provider_class()
        _, domain_key = jax.random.split(jax.random.PRNGKey(seed))
        expected_state = expected_plugin.create_initial_state(
            DomainConfig(n_agents=n_agents, max_agents=max_agents),
            domain_key,
        )
        assert initial_state.n_agents == n_agents
        assert initial_state.max_agents == max_agents
        np.testing.assert_array_equal(initial_state.agents.wealth, expected_state.agents.wealth)

        result = simulator.run(n_steps=2, seed=seed)
        final_state = result.final_state.get_domain(_PLUGIN)
        # The declared Economics profile advances only the composite clock.
        assert int(result.final_state.time_step) == 2
        assert int(final_state.time_step) == int(initial_state.time_step) == 0
        assert final_state.n_agents == n_agents
        assert final_state.max_agents == max_agents
        assert result.n_steps == 2
        assert result.trajectory is not None and len(result.trajectory) == 3
        assert "native_gdp" in result.objectives
        assert bool(jnp.isfinite(result.objectives["native_gdp"]))
    finally:
        registry.clear()
        sys.modules.pop(_MODULE, None)


def test_wrong_group_entry_point_is_not_admitted_as_domain_plugin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real dist-info declaration under another group does not satisfy the ABI."""
    _write_installed_fixture(tmp_path, group="polisyos.foundry_methods")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop(_MODULE, None)

    assert not any(
        entry_point.name == _ENTRY_POINT for entry_point in metadata.entry_points(group=_GROUP)
    )
    assert not any(
        plugin.metadata.name == _PLUGIN
        for plugin in discover_plugins(package_prefix="plg01_no_matching_native_fixture_")
    )
    assert _MODULE not in sys.modules


class _NamedEconomicsPlugin(EconomicsPlugin):
    """Real DomainPlugin implementation with a test-specific registry identity."""

    def __init__(self, name: str = "plg01-declared-later-good") -> None:
        super().__init__()
        self._test_name = name

    @property
    def metadata(self):
        return replace(super().metadata, name=self._test_name)


def test_builtin_import_error_is_reported_and_later_declared_and_dev_sources_survive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed builtin source is visible while later independent sources load."""
    dev_dir = tmp_path / "dev" / "selected"
    dev_dir.mkdir(parents=True)
    (dev_dir / "plugin.py").write_text(
        dedent(
            """\
            from polisyos.foundry.plugins.economics import EconomicsPlugin
            from dataclasses import replace

            class DevPlugin(EconomicsPlugin):
                @property
                def metadata(self):
                    return replace(super().metadata, name="plg01-dev-later-good")

            def create_plugin():
                return DevPlugin()
            """
        ),
        encoding="utf-8",
    )

    original_import = plugin_discovery.importlib.import_module

    def import_module(name, package=None):
        if name == "polisyos.foundry.plugins.economics":
            raise ImportError("bounded PLG-01 builtin import failure")
        return original_import(name, package)

    class EntryPoint:
        name = "plg01-declared-later-good"
        value = "fixture:Plugin"

        def load(self):
            return _NamedEconomicsPlugin

    monkeypatch.setattr(plugin_discovery.importlib, "import_module", import_module)
    monkeypatch.setattr(
        "polisyos.core.discovery.base.metadata.entry_points",
        lambda *args, **kwargs: [EntryPoint()],
    )
    with caplog.at_level("WARNING", logger=plugin_discovery.logger.name):
        plugins = discover_plugins(
            search_paths=[tmp_path / "dev"],
            package_prefix="plg01_no_matching_native_fixture_",
        )

    names = {plugin.metadata.name for plugin in plugins}
    assert "plg01-dev-later-good" in names
    assert "plg01-declared-later-good" in names
    assert "bounded PLG-01 builtin import failure" in caplog.text
    assert "polisyos.foundry.plugins.economics" in caplog.text


@pytest.mark.parametrize("bad_result", [None, object()], ids=["none", "object"])
def test_prefix_factory_failure_does_not_hide_later_prefix_plugin(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    bad_result: object,
) -> None:
    """Each prefix factory is isolated and the next valid distribution is retained."""
    good_name = "plg01-prefix-later-good"
    distributions = [
        SimpleNamespace(name="plg01-prefix-a-bad"),
        SimpleNamespace(name="plg01-prefix-z-good"),
    ]
    modules: dict[str, ModuleType] = {}
    for distribution, candidate in zip(
        distributions,
        (bad_result, _NamedEconomicsPlugin(good_name)),
    ):
        module_name = distribution.name.replace("-", "_")
        module = ModuleType(module_name)
        module.create_plugin = lambda candidate=candidate: candidate
        modules[module_name] = module

    monkeypatch.setattr(plugin_discovery.metadata, "distributions", lambda: distributions)
    real_import_module = plugin_discovery.importlib.import_module

    def import_module(name: str, package: str | None = None):
        if name in modules:
            return modules[name]
        return real_import_module(name, package)

    monkeypatch.setattr(plugin_discovery.importlib, "import_module", import_module)
    with caplog.at_level("WARNING", logger=plugin_discovery.logger.name):
        plugins = plugin_discovery._discover_distribution_plugins("plg01-prefix-")

    assert [plugin.metadata.name for plugin in plugins] == [good_name]
    assert "plg01-prefix-a-bad" in caplog.text


def test_discovery_does_not_swallow_base_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source isolation boundary catches ordinary errors, not BaseException."""

    def interrupted_builtin():
        raise KeyboardInterrupt("PLG-01 sentinel interruption")

    monkeypatch.setattr(plugin_discovery, "_discover_builtin_plugins", interrupted_builtin)
    with pytest.raises(KeyboardInterrupt, match="PLG-01 sentinel interruption"):
        discover_plugins(package_prefix="plg01_no_matching_native_fixture_")
