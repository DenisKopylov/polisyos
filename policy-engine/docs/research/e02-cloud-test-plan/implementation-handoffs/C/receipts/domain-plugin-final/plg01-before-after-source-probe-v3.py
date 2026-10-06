from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import logging
import subprocess
import tempfile
import warnings
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from polisyos.core import discovery as core_discovery
from polisyos.foundry.plugins import discovery as plugin_discovery
from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata, PluginRegistry

BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
CANDIDATE = "a452011da3de26d90877ae95ab10a72cce8e0b45"
DISCOVERY_PATH = "policy-engine/src/polisyos/foundry/plugins/discovery.py"
BASE_SOURCE = subprocess.check_output(
    ["git", "show", f"{BASE}:{DISCOVERY_PATH}"], text=True
)
base_module = ModuleType("plg01_base198_discovery")
base_module.__file__ = f"{BASE}:{DISCOVERY_PATH}"
exec(compile(BASE_SOURCE, base_module.__file__, "exec"), base_module.__dict__)

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
            description="scratch before/after discovery fixture",
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


entrypoint_class = type(
    "EpDependent",
    (FixturePlugin,),
    {
        "__init__": lambda self: FixturePlugin.__init__(
            self, "ep-dependent", "entrypoint", ("economics",)
        )
    },
)
entry_points = [Ep("zeta-good", entrypoint_class), Ep("alpha-bad", fail=True)]
distributions = [
    Dist("polisyos_plugin_zeta"),
    Dist("polisyos_plugin_beta"),
    Dist("polisyos_plugin_alpha"),
]
real_import_module = importlib.import_module


def run_case(label: str, implementation: ModuleType) -> dict:
    trace.clear()
    with tempfile.TemporaryDirectory(prefix=f"plg01-{label}-") as tmp:
        root = Path(tmp) / "dev"
        root.mkdir()
        broken = root / "00-broken"
        broken.mkdir()
        (broken / "plugin.py").write_text(
            "raise RuntimeError('dev-import-error')\n", encoding="utf-8"
        )
        shared = root / "10-shared"
        shared.mkdir()
        (shared / "plugin.py").write_text(
            "from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata\n"
            "class Plugin(DomainPlugin):\n"
            " @property\n"
            " def metadata(self): return PluginMetadata(name='shared', version='1', description='dev')\n"
            " def create_initial_state(self, config, rng_key): return None\n"
            " def get_mechanisms(self): return ()\n"
            " def get_reward_function(self): return lambda *_a, **_k: None\n"
            " def get_objectives(self): return {}\n"
            "def create_plugin():\n"
            " plugin = Plugin()\n"
            " plugin.origin = 'dev'\n"
            " return plugin\n",
            encoding="utf-8",
        )
        dev_zeta = root / "20-zeta"
        dev_zeta.mkdir()
        (dev_zeta / "plugin.py").write_text(
            "from polisyos.foundry.plugins.core import DomainPlugin, PluginMetadata\n"
            "class Plugin(DomainPlugin):\n"
            " @property\n"
            " def metadata(self): return PluginMetadata(name='dev-zeta', version='1', description='dev')\n"
            " def create_initial_state(self, config, rng_key): return None\n"
            " def get_mechanisms(self): return ()\n"
            " def get_reward_function(self): return lambda *_a, **_k: None\n"
            " def get_objectives(self): return {}\n"
            "def create_plugin(): return Plugin()\n",
            encoding="utf-8",
        )

        def fake_import_module(name: str, package=None):
            if name.startswith("polisyos_plugin_"):
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

        def record_warning(message, category, filename, lineno, file=None, line=None):
            del category, filename, lineno, file, line
            trace.append(f"warning:{message}")

        plugin_logger_names = {
            "polisyos.foundry.plugins.discovery",
            "plg01_base198_discovery",
        }
        handlers: list[tuple[logging.Logger, int, RecordHandler]] = []
        handler = RecordHandler()
        for logger_name in plugin_logger_names:
            logger = logging.getLogger(logger_name)
            handlers.append((logger, logger.level, handler))
            logger.addHandler(handler)
            logger.setLevel(logging.WARNING)

        registry = PluginRegistry()
        registry.clear()
        try:
            with (
                patch.object(
                    core_discovery.base.metadata,
                    "entry_points",
                    side_effect=lambda **_kwargs: list(reversed(entry_points)),
                ),
                patch.object(
                    importlib.metadata,
                    "distributions",
                    side_effect=lambda: list(reversed(distributions)),
                ),
                patch.object(importlib, "import_module", side_effect=fake_import_module),
                patch.object(warnings, "showwarning", side_effect=record_warning),
                warnings.catch_warnings(),
            ):
                warnings.simplefilter("always")
                registered = implementation.auto_register_plugins(registry, [root])
        finally:
            for logger, old_level, installed_handler in handlers:
                logger.removeHandler(installed_handler)
                logger.setLevel(old_level)

        shared_plugin = registry.get("shared")
        dependent = registry.get("ep-dependent")
        assert dependent.origin == "entrypoint"
        try:
            registry.unregister("economics")
        except ValueError as exc:
            dependency_refusal = str(exc)
            assert "depends on it" in dependency_refusal
        else:
            raise AssertionError("discovered entry-point dependent did not protect Economics")
        registry.unregister("ep-dependent")
        assert trace[-1] == "unload:ep-dependent", trace
        plugin_order = [item.name for item in registry.list_plugins()]
        result = {
            "implementation": label,
            "registered_order": registered,
            "registry_order_after_dependent_removal": plugin_order,
            "shared_duplicate_winner_origin": shared_plugin.origin,
            "dependency_refusal": dependency_refusal,
            "ordered_events": list(trace),
            "dep_import_input_order": [item.name for item in distributions],
        }
        registry.clear()
        return result


base_result = run_case("base198", base_module)
candidate_result = run_case("candidate", plugin_discovery)
assert base_result["shared_duplicate_winner_origin"] == "distribution-alpha", base_result
assert candidate_result["shared_duplicate_winner_origin"] == "dev", candidate_result
assert base_result["registered_order"] == [
    "economics",
    "ep-dependent",
    "shared",
    "dist-zeta",
    "dev-zeta",
]
assert candidate_result["registered_order"] == [
    "economics",
    "ep-dependent",
    "shared",
    "dev-zeta",
    "dist-zeta",
]
assert any("entrypoint-failure:alpha-bad" in event for event in base_result["ordered_events"] if event.startswith("log:"))
assert any("distribution-import-error:beta" in event for event in candidate_result["ordered_events"] if event.startswith("log:"))
assert any("dev-import-error" in event for event in base_result["ordered_events"] if event.startswith("warning:"))
assert any("dev-import-error" in event for event in candidate_result["ordered_events"] if event.startswith("warning:"))

base_source_hash = hashlib.sha256(BASE_SOURCE.encode()).hexdigest()
candidate_source_hash = subprocess.check_output(
    ["git", "rev-parse", f"{CANDIDATE}:{DISCOVERY_PATH}"], text=True
).strip()
print(
    json.dumps(
        {
            "result": "PASS",
            "base_commit": BASE,
            "base_discovery_source_sha256": base_source_hash,
            "candidate_commit": CANDIDATE,
            "candidate_discovery_blob": candidate_source_hash,
            "genuine_distribution_installed": False,
            "fake_distribution_import_order": [
                "polisyos_plugin_alpha",
                "polisyos_plugin_beta",
                "polisyos_plugin_zeta",
            ],
            "base": base_result,
            "candidate": candidate_result,
            "interpretation": "Identical light fixtures exercised exact-base and candidate source order/error isolation, duplicate precedence, and discovered dependency/load/unload. Prefix distribution ordering is deterministic; current intentional priority move puts declared dev roots before prefix-discovered distributions, changing the winner for a cross-source duplicate. A genuinely installed distribution was not installed or asserted.",
        },
        indent=2,
    )
)
