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
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

from polisyos.core import discovery as core_discovery
from polisyos.foundry.plugins.core import (
    DomainPlugin,
    PluginMetadata,
    PluginRegistry,
    get_registry,
)

logger = logging.getLogger(__name__)

LEGACY_DOMAIN_PLUGIN_ENTRY_POINT_GROUP = "polisyos.plugins"
CANONICAL_METHOD_ENTRY_POINT_GROUP = "polisyos.foundry_methods"


@dataclass(slots=True)
class _DomainPluginSource:
    """Adapt one legacy DomainPlugin source to Core's shared collector."""

    name: str
    loader: Callable[[], Sequence[DomainPlugin]]
    errors: list[core_discovery.DiscoveryError] = field(default_factory=list)

    def discover(self) -> Iterator[DomainPlugin]:
        """Load one source in its established position in the discovery order."""
        self.errors.clear()
        return iter(self.loader())


def discover_plugins(
    search_paths: Sequence[str | Path] | None = None,
    package_prefix: str = "polisyos_plugin_",
) -> list[DomainPlugin]:
    """Discover and load plugins from built-ins, installed packages, and directories."""
    sources = [
        _DomainPluginSource("builtin", _discover_builtin_plugins),
        _DomainPluginSource(
            "installed",
            lambda: _discover_installed_plugins(package_prefix),
        ),
    ]
    sources.extend(
        _DomainPluginSource(
            f"dev_path:{path}",
            lambda path=Path(path): _discover_directory_plugins(path),
        )
        for path in search_paths or ()
    )
    collector = core_discovery.BaseDiscovery[DomainPlugin, core_discovery.DiscoveryError](
        sources=sources,
        on_source_error=lambda source, exc: core_discovery.DiscoveryError(
            source=str(getattr(source, "name", type(source).__name__)),
            item=None,
            error_type=type(exc).__name__,
            message=str(exc),
            traceback=core_discovery.format_traceback(),
        ),
    )
    batches, _ = collector.collect()

    plugins: list[DomainPlugin] = []
    for batch in batches:
        plugins.extend(batch.items)
        for error in batch.errors:
            logger.warning(
                "Failed to discover plugins from %s: %s",
                error.source,
                error.message,
            )

    return plugins


def _discover_builtin_plugins() -> list[DomainPlugin]:
    builtin_modules = [
        "polisyos.foundry.plugins.economics",
    ]

    plugins: list[DomainPlugin] = []
    for module_name in builtin_modules:
        try:
            module = importlib.import_module(module_name)
            for name in sorted(dir(module)):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, DomainPlugin)
                    and obj is not DomainPlugin
                ):
                    try:
                        plugins.append(_coerce_domain_plugin(obj))
                    except Exception as exc:
                        logger.warning(
                            "Failed to load builtin plugin '%s.%s': %s",
                            module_name,
                            name,
                            exc,
                            exc_info=True,
                        )
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
            plugins.append(_coerce_domain_plugin(ep.load()))
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
                plugins.append(_coerce_domain_plugin(module.create_plugin()))
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
                candidate = module.create_plugin()
            elif hasattr(module, "Plugin"):
                candidate = module.Plugin()
            else:
                raise TypeError("plugin.py must expose create_plugin() or Plugin")

            plugins.append(_coerce_domain_plugin(candidate))
        except Exception as exc:
            warnings.warn(
                f"Failed to load plugin from {plugin_dir}: {exc}",
                RuntimeWarning,
            )
        finally:
            sys.modules.pop(module_name, None)

    return plugins


def _coerce_domain_plugin(candidate: object) -> DomainPlugin:
    """Materialize and validate one candidate against the preserved domain-plugin ABI."""
    if isinstance(candidate, type):
        if not issubclass(candidate, DomainPlugin):
            raise TypeError("plugin candidate class must inherit DomainPlugin")
        candidate = candidate()

    if not isinstance(candidate, DomainPlugin):
        raise TypeError("plugin candidate must be a DomainPlugin instance")

    if not isinstance(candidate.metadata, PluginMetadata):
        raise TypeError("DomainPlugin.metadata must return PluginMetadata")

    return candidate


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
        plugin_name = _safe_plugin_name(plugin)
        try:
            registry.register(plugin)
            registered.append(plugin_name)
        except Exception as exc:
            warnings.warn(
                f"Could not register {plugin_name}: {exc}",
                RuntimeWarning,
            )

    return registered


def _safe_plugin_name(plugin: DomainPlugin) -> str:
    """Return a warning label without trusting a candidate's metadata property."""
    try:
        name = plugin.metadata.name
    except Exception:
        name = None
    if isinstance(name, str) and name:
        return name
    return type(plugin).__name__


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
