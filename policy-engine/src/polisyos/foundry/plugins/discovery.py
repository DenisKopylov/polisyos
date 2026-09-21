"""Discover legacy Foundry domain plugins.

This package remains the agent-simulation domain-plugin compatibility layer.
Foundry method extensions use `polisyos.foundry.extensions` and the
`polisyos.foundry_methods` entry-point group instead.
"""

from __future__ import annotations

import importlib
import logging
import sys
import warnings
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path

from polisyos.core import discovery as core_discovery
from polisyos.foundry.plugins.core import DomainPlugin, PluginRegistry, get_registry

logger = logging.getLogger(__name__)

LEGACY_DOMAIN_PLUGIN_ENTRY_POINT_GROUP = "polisyos.plugins"
CANONICAL_METHOD_ENTRY_POINT_GROUP = "polisyos.foundry_methods"


def discover_plugins(
    search_paths: Sequence[str | Path] | None = None,
    package_prefix: str = "polisyos_plugin_",
) -> list[DomainPlugin]:
    """Discover and load plugins from built-ins, installed packages, and directories."""
    plugins: list[DomainPlugin] = []

    plugins.extend(_discover_builtin_plugins())
    plugins.extend(_discover_installed_plugins(package_prefix))

    if search_paths:
        for path in search_paths:
            plugins.extend(_discover_directory_plugins(Path(path)))

    return plugins


def _discover_builtin_plugins() -> list[DomainPlugin]:
    builtin_modules = [
        "polisyos.foundry.plugins.economics",
    ]

    plugins: list[DomainPlugin] = []
    for module_name in builtin_modules:
        try:
            module = importlib.import_module(module_name)
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, DomainPlugin)
                    and obj is not DomainPlugin
                ):
                    plugins.append(obj())
        except ImportError:
            continue

    return plugins


def _discover_installed_plugins(prefix: str) -> list[DomainPlugin]:
    plugins: list[DomainPlugin] = []

    try:
        entry_points = core_discovery.list_entry_points(
            group=LEGACY_DOMAIN_PLUGIN_ENTRY_POINT_GROUP,
        )
    except Exception:
        logger.warning(
            "Failed to enumerate plugin entry points for group %s",
            LEGACY_DOMAIN_PLUGIN_ENTRY_POINT_GROUP,
            exc_info=True,
        )
        entry_points = []

    for ep in entry_points:
        try:
            plugin_class = ep.load()
            if issubclass(plugin_class, DomainPlugin):
                plugins.append(plugin_class())
        except Exception:
            logger.warning("Failed to load plugin entry point '%s'", ep.name, exc_info=True)
            continue

    distributions = []
    try:
        distributions = sorted(
            (
                dist
                for dist in metadata.distributions()
                if _distribution_name(dist).startswith(prefix)
            ),
            key=_distribution_name,
        )
    except Exception:
        logger.warning("Failed to enumerate plugin distributions", exc_info=True)

    for dist in distributions:
        project_name = _distribution_name(dist)
        try:
            module = importlib.import_module(project_name.replace("-", "_"))
            if hasattr(module, "create_plugin"):
                plugins.append(module.create_plugin())
        except Exception:
            logger.warning("Failed to load plugin package '%s'", project_name, exc_info=True)
            continue

    return plugins


def _discover_directory_plugins(directory: Path) -> list[DomainPlugin]:
    plugins: list[DomainPlugin] = []

    if not directory.exists():
        return plugins

    if not directory.is_dir():
        return plugins

    for plugin_dir in sorted(directory.iterdir(), key=lambda path: path.name):
        if not plugin_dir.is_dir():
            continue

        plugin_file = plugin_dir / "plugin.py"
        if not plugin_file.exists():
            continue

        module_name = core_discovery.discovery_module_name(
            plugin_file,
            prefix="_polisyos_plugins_scan_",
            algorithm="sha1",
            digest_length=40,
        )
        try:
            module = core_discovery.load_module_from_file(
                plugin_file,
                module_name=module_name,
            )

            if hasattr(module, "create_plugin"):
                plugins.append(module.create_plugin())
            elif hasattr(module, "Plugin"):
                plugins.append(module.Plugin())
        except Exception as exc:
            warnings.warn(
                f"Failed to load plugin from {plugin_dir}: {exc}",
                RuntimeWarning,
            )
        finally:
            sys.modules.pop(module_name, None)

    return plugins


def _distribution_name(distribution: object) -> str:
    """Return an installed distribution name for deterministic prefix scanning."""
    name = getattr(distribution, "name", None)
    if name is None:
        name = getattr(distribution, "project_name", None)
    if name is None:
        metadata_obj = getattr(distribution, "metadata", None)
        metadata_get = getattr(metadata_obj, "get", None)
        if callable(metadata_get):
            name = metadata_get("Name")
    return str(name or "")


def auto_register_plugins(
    registry: PluginRegistry | None = None,
    search_paths: Sequence[str | Path] | None = None,
) -> list[str]:
    """Discover plugins and register them into the active plugin registry."""
    if registry is None:
        registry = get_registry()

    plugins = discover_plugins(search_paths)
    registered: list[str] = []

    for plugin in plugins:
        try:
            registry.register(plugin)
            registered.append(plugin.metadata.name)
        except ValueError as exc:
            warnings.warn(
                f"Could not register {plugin.metadata.name}: {exc}",
                RuntimeWarning,
            )

    return registered


def create_simple_plugin(
    name: str,
    version: str,
    state_class: type,
    mechanisms: Sequence,
    reward_fn,
    objectives: dict,
    **kwargs,
) -> DomainPlugin:
    """Create simple plugin."""
    from polisyos.foundry.plugins.core import PluginCapability, PluginMetadata

    class SimplePlugin(DomainPlugin):
        @property
        def metadata(self):
            return PluginMetadata(
                name=name,
                version=version,
                description=kwargs.get("description", ""),
                capabilities=(
                    PluginCapability.AGENTS,
                    PluginCapability.MECHANISMS,
                    PluginCapability.REWARDS,
                    PluginCapability.OBJECTIVES,
                ),
                **{k: v for k, v in kwargs.items() if k in ["author", "tags", "dependencies"]},
            )

        def create_initial_state(self, config, rng_key):
            return state_class.empty(config.n_agents, int(rng_key[0]), **config.parameters)

        def get_mechanisms(self):
            return mechanisms

        def get_reward_function(self):
            return reward_fn

        def get_objectives(self):
            return objectives

    return SimplePlugin()
