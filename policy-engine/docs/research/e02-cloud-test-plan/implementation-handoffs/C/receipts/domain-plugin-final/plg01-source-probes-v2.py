from __future__ import annotations

import importlib
import json
import logging
import tempfile
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from polisyos.core import discovery as core_discovery
from polisyos.foundry.plugins import discovery as plugin_discovery
from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata, PluginRegistry

trace: list[str] = []


class FixturePlugin(DomainPlugin):
    def __init__(self, name: str, origin: str, dependencies: tuple[str, ...] = ()) -> None:
        self.name = name
        self.origin = origin
        self.dependencies = dependencies

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self.name,
            version="1.0",
            description="scratch discovery acceptance fixture",
            dependencies=self.dependencies,
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
        trace.append(f"load:{self.name}")

    def on_unload(self) -> None:
        trace.append(f"unload:{self.name}")


class Ep:
    def __init__(self, name: str, plugin_class=None, fail: bool = False) -> None:
        self.name = name
        self.value = f"scratch:{name}"
        self.plugin_class = plugin_class
        self.fail = fail

    def load(self):
        trace.append(f"ep-load:{self.name}")
        if self.fail:
            raise RuntimeError(f"entrypoint-failure:{self.name}")
        return self.plugin_class


class Dist:
    def __init__(self, name: str) -> None:
        self.name = name


class RecordHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        error = str(record.exc_info[1]) if record.exc_info else ""
        trace.append(f"log:{record.getMessage()}:{error}")


with tempfile.TemporaryDirectory(prefix="plg01-prefix-") as tmp:
    root = Path(tmp)
    declared_root = root / "dev"
    declared_root.mkdir()
    bad_dev = declared_root / "00-broken"
    bad_dev.mkdir()
    (bad_dev / "plugin.py").write_text(
        "raise RuntimeError('dev-import-error')\n", encoding="utf-8"
    )
    duplicate_dev = declared_root / "10-shared"
    duplicate_dev.mkdir()
    (duplicate_dev / "plugin.py").write_text(
        "from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata\n"
        "class Plugin(DomainPlugin):\n"
        " @property\n"
        " def metadata(self): return PluginMetadata(name='shared', version='1', description='dev')\n"
        " def create_initial_state(self, config, rng_key): return None\n"
        " def get_mechanisms(self): return ()\n"
        " def get_reward_function(self): return lambda *_a, **_k: None\n"
        " def get_objectives(self): return {}\n"
        "def create_plugin(): return Plugin()\n",
        encoding="utf-8",
    )

    ep_dependent = type(
        "EpDependent",
        (FixturePlugin,),
        {"__init__": lambda self: FixturePlugin.__init__(self, "ep-dependent", "entrypoint", ("economics",))},
    )
    eps = [Ep("zeta-good", ep_dependent), Ep("alpha-bad", fail=True)]
    fake_distributions = [
        Dist("polisyos_plugin_zeta"),
        Dist("polisyos_plugin_beta"),
        Dist("polisyos_plugin_alpha"),
    ]
    real_import_module = importlib.import_module
    distribution_imports: list[str] = []

    def fake_import_module(name: str, package=None):
        if name.startswith("polisyos_plugin_"):
            distribution_imports.append(name)
            trace.append(f"dist-import:{name}")
            if name == "polisyos_plugin_beta":
                raise RuntimeError("distribution-import-error:beta")
            if name == "polisyos_plugin_alpha":
                return SimpleNamespace(
                    create_plugin=lambda: FixturePlugin("shared", "distribution-alpha")
                )
            if name == "polisyos_plugin_zeta":
                return SimpleNamespace(
                    create_plugin=lambda: FixturePlugin("dist-zeta", "distribution-zeta")
                )
        return real_import_module(name, package)

    plugin_logger = logging.getLogger("polisyos.foundry.plugins.discovery")
    old_level = plugin_logger.level
    handler = RecordHandler()
    plugin_logger.addHandler(handler)
    plugin_logger.setLevel(logging.WARNING)
    registry = PluginRegistry()
    registry.clear()
    try:
        with (
            patch.object(
                core_discovery.base.metadata,
                "entry_points",
                side_effect=lambda **_kwargs: list(reversed(eps)),
            ),
            patch.object(
                plugin_discovery.metadata,
                "distributions",
                side_effect=lambda: list(reversed(fake_distributions)),
            ),
            patch.object(plugin_discovery.importlib, "import_module", side_effect=fake_import_module),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            registered = plugin_discovery.auto_register_plugins(registry, [declared_root])
    finally:
        plugin_logger.removeHandler(handler)
        plugin_logger.setLevel(old_level)

    warning_messages = [str(item.message) for item in caught]
    registry_order = [item.name for item in registry.list_plugins()]
    assert registered == ["economics", "ep-dependent", "shared", "dist-zeta"], registered
    assert registry_order == registered, registry_order
    assert distribution_imports == [
        "polisyos_plugin_alpha",
        "polisyos_plugin_beta",
        "polisyos_plugin_zeta",
    ], distribution_imports
    assert [event for event in trace if event.startswith("ep-load:")] == [
        "ep-load:alpha-bad",
        "ep-load:zeta-good",
    ], trace
    assert any("dev-import-error" in message for message in warning_messages), warning_messages
    assert any("Could not register shared" in message for message in warning_messages), warning_messages
    assert any("entrypoint-failure:alpha-bad" in event for event in trace), trace
    assert any("distribution-import-error:beta" in event for event in trace), trace
    assert registry.get("ep-dependent").origin == "entrypoint"
    assert trace[-1] == "load:ep-dependent", trace
    try:
        registry.unregister("economics")
    except ValueError as exc:
        assert "depends on it" in str(exc)
    else:
        raise AssertionError("discovered dependent did not protect its dependency")
    registry.unregister("ep-dependent")
    assert trace[-1] == "unload:ep-dependent", trace
    registry.clear()

    print(
        json.dumps(
            {
                "result": "PASS",
                "registered_order": registered,
                "registry_order": registry_order,
                "distribution_input_order": [item.name for item in fake_distributions],
                "distribution_import_order": distribution_imports,
                "entrypoint_input_order": [item.name for item in eps],
                "entrypoint_load_order": [event.removeprefix("ep-load:") for event in trace if event.startswith("ep-load:")],
                "warning_messages": warning_messages,
                "event_trace": trace,
                "genuine_distribution_installed": False,
                "interpretation": "Source-order, per-source error isolation, cross-source duplicate precedence, and lifecycle/dependency effects exercised with scratch fixtures; no distribution was installed.",
            },
            indent=2,
        )
    )
