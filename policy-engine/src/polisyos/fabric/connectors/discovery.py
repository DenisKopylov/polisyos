"""Automatic Connector Discovery System.

Discovers data source connectors through multiple mechanisms:
1. Built-in reference connectors (hardcoded module paths)
2. Entry points from installed packages (polisyos.connectors group)
3. Explicit module paths for development/testing
4. Explicit filesystem paths (dev-only, gated by env flag)

Design Goals:
- Zero-configuration for standard deployments
- Plugin-friendly architecture via setuptools entry_points
- Fail-safe discovery (log errors, continue with valid connectors)
- Support for lazy loading and hot-reloading
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Sequence

from polisyos.common.logger import get_logger

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import SourceConnector

logger = get_logger(__name__)

# Entry point group name for connector plugins
ENTRY_POINT_GROUP = "polisyos.connectors"

# Built-in connector modules to discover at startup
BUILTIN_CONNECTOR_MODULES: tuple[str, ...] = (
    "polisyos.fabric.connectors.reference",
    "polisyos.fabric.connectors.sources",
)

# Filesystem path discovery is dev-only
ALLOW_PATHS_ENV = "POLISYOS_ALLOW_CONNECTOR_PATHS"


@dataclass
class DiscoveryResult:
    """Result of connector discovery."""

    connector_class: type["SourceConnector"]
    source: str  # "builtin", "entrypoint", "explicit", "path"
    module_path: str
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiscoveryError:
    """Record of failed connector discovery."""

    source: str
    module_path: str
    error: str
    error_type: str
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorDiscovery:
    """
    Manages connector discovery from multiple sources.

    Singleton pattern for caching discovery results.

    Usage:
        discovery = ConnectorDiscovery()

        # Discover all connectors
        for connector_class in discovery.discover_all():
            registry.register(connector_class)

        # Check discovery errors
        for error in discovery.errors:
            logger.warning(f"Failed to load: {error.module_path}")
    """

    _instance: "ConnectorDiscovery | None" = None

    def __new__(cls) -> "ConnectorDiscovery":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._discovered: dict[str, DiscoveryResult] = {}
        self._errors: list[DiscoveryError] = []
        self._additional_modules: list[str] = []
        self._additional_paths: list[Path] = []
        self._initialized = True

    @property
    def discovered(self) -> dict[str, DiscoveryResult]:
        """Map of connector FQID -> DiscoveryResult."""
        return self._discovered.copy()

    @property
    def errors(self) -> list[DiscoveryError]:
        """List of discovery errors encountered."""
        return self._errors.copy()

    def add_module(self, module_path: str) -> None:
        """Add an additional module path to discover connectors from."""
        if module_path not in self._additional_modules:
            self._additional_modules.append(module_path)

    def add_path(self, path: Path) -> None:
        """Add a filesystem path to scan for connector modules (dev-only)."""
        if path not in self._additional_paths:
            self._additional_paths.append(path)

    def discover_all(
        self,
        *,
        refresh: bool = False,
        allow_paths: bool | None = None,
    ) -> Iterator[type["SourceConnector"]]:
        """
        Discover all available connectors.

        Discovery order:
        1. Built-in reference connectors
        2. Entry points from installed packages
        3. Explicitly added modules
        4. Explicitly added filesystem paths (dev-only)

        Args:
            refresh: If True, re-discover even if already discovered
            allow_paths: If True, allow filesystem path discovery

        Yields:
            Connector classes implementing SourceConnector protocol
        """
        if refresh:
            self._discovered.clear()
            self._errors.clear()

        allow_paths = self._paths_allowed(allow_paths)

        # 1. Built-in reference connectors
        yield from self._discover_builtin()

        # 2. Entry points
        yield from self._discover_entry_points()

        # 3. Explicit modules
        yield from self._discover_explicit_modules()

        # 4. Explicit paths (dev-only)
        if allow_paths:
            yield from self._discover_explicit_paths()
        elif self._additional_paths:
            logger.info(
                "Skipping connector path discovery (disabled).",
                env_flag=ALLOW_PATHS_ENV,
            )

    def _paths_allowed(self, allow_paths: bool | None) -> bool:
        if allow_paths is not None:
            return allow_paths
        env_value = os.getenv(ALLOW_PATHS_ENV, "").strip().lower()
        return env_value in {"1", "true", "yes"}

    def _discover_builtin(self) -> Iterator[type["SourceConnector"]]:
        """Discover built-in reference connectors."""
        for module_path in BUILTIN_CONNECTOR_MODULES:
            yield from self._discover_from_module(module_path, source="builtin")

    def _discover_entry_points(self) -> Iterator[type["SourceConnector"]]:
        """Discover connectors registered via entry points."""
        try:
            # Python 3.10+ API
            eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            # Python 3.9 compatibility
            all_eps = importlib.metadata.entry_points()
            eps = all_eps.get(ENTRY_POINT_GROUP, [])

        for ep in eps:
            try:
                connector_class = ep.load()

                if self._is_valid_connector(connector_class):
                    fqid = self._get_fqid(connector_class)

                    if fqid not in self._discovered:
                        self._discovered[fqid] = DiscoveryResult(
                            connector_class=connector_class,
                            source="entrypoint",
                            module_path=f"{ep.value} ({ep.name})",
                        )
                        logger.info(
                            "Discovered connector via entry point",
                            connector_id=fqid,
                            entry_point=ep.name,
                        )
                        yield connector_class
                else:
                    self._errors.append(
                        DiscoveryError(
                            source="entrypoint",
                            module_path=f"{ep.value} ({ep.name})",
                            error="Not a valid SourceConnector implementation",
                            error_type="ValidationError",
                        )
                    )
            except Exception as e:
                self._errors.append(
                    DiscoveryError(
                        source="entrypoint",
                        module_path=f"{ep.value} ({ep.name})",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                )
                logger.warning(
                    "Failed to load connector entry point",
                    entry_point=ep.name,
                    error=str(e),
                )

    def _discover_explicit_modules(self) -> Iterator[type["SourceConnector"]]:
        """Discover connectors from explicitly added modules."""
        for module_path in self._additional_modules:
            yield from self._discover_from_module(module_path, source="explicit")

    def _discover_explicit_paths(self) -> Iterator[type["SourceConnector"]]:
        """Discover connectors from explicitly added filesystem paths."""
        for path in self._additional_paths:
            yield from self._discover_from_path(path)

    def _discover_from_module(
        self,
        module_path: str,
        source: str,
    ) -> Iterator[type["SourceConnector"]]:
        """
        Discover connector classes from a module path.

        Scans the module for classes with connector_id, capabilities,
        and metadata class attributes (SourceConnector protocol compliance).
        """
        try:
            module = importlib.import_module(module_path)

            names = getattr(module, "__all__", None)
            restrict_to_module = names is None
            if names is None:
                names = dir(module)

            for name in names:
                obj = getattr(module, name, None)

                # Skip non-classes and imported classes
                if not isinstance(obj, type):
                    continue
                if restrict_to_module and getattr(obj, "__module__", None) != module_path:
                    continue

                if self._is_valid_connector(obj):
                    fqid = self._get_fqid(obj)

                    if fqid not in self._discovered:
                        self._discovered[fqid] = DiscoveryResult(
                            connector_class=obj,
                            source=source,
                            module_path=module_path,
                        )
                        logger.debug(
                            "Discovered connector",
                            connector_id=fqid,
                            module=module_path,
                            source=source,
                        )
                        yield obj

        except ImportError as e:
            self._errors.append(
                DiscoveryError(
                    source=source,
                    module_path=module_path,
                    error=str(e),
                    error_type="ImportError",
                )
            )
            logger.debug(
                "Could not import connector module",
                module=module_path,
                error=str(e),
            )

        except Exception as e:
            self._errors.append(
                DiscoveryError(
                    source=source,
                    module_path=module_path,
                    error=str(e),
                    error_type=type(e).__name__,
                )
            )
            logger.warning(
                "Error discovering connectors from module",
                module=module_path,
                error=str(e),
            )

    def _discover_from_path(self, path: Path) -> Iterator[type["SourceConnector"]]:
        """
        Discover connectors from a filesystem path.

        Scans for Python files and attempts to load them as modules.
        """
        if not path.exists():
            self._errors.append(
                DiscoveryError(
                    source="path",
                    module_path=str(path),
                    error="Path does not exist",
                    error_type="FileNotFoundError",
                )
            )
            return

        # Add path to sys.path temporarily
        path_str = str(path.parent if path.is_file() else path)
        original_path = sys.path.copy()

        try:
            if path_str not in sys.path:
                sys.path.insert(0, path_str)

            if path.is_file() and path.suffix == ".py":
                yield from self._load_connector_from_file(path)
            elif path.is_dir():
                for py_file in path.glob("**/*.py"):
                    if py_file.name.startswith("_"):
                        continue
                    yield from self._load_connector_from_file(py_file)
        finally:
            sys.path = original_path

    def _load_connector_from_file(self, file_path: Path) -> Iterator[type["SourceConnector"]]:
        """Load connector classes from a Python file (dev-only)."""
        module_name = self._unique_module_name(file_path)

        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            for name in dir(module):
                obj = getattr(module, name)

                if isinstance(obj, type) and self._is_valid_connector(obj):
                    fqid = self._get_fqid(obj)

                    if fqid not in self._discovered:
                        self._discovered[fqid] = DiscoveryResult(
                            connector_class=obj,
                            source="path",
                            module_path=str(file_path),
                        )
                        logger.debug(
                            "Discovered connector from file",
                            connector_id=fqid,
                            file=str(file_path),
                        )
                        yield obj
        except Exception as e:
            self._errors.append(
                DiscoveryError(
                    source="path",
                    module_path=str(file_path),
                    error=str(e),
                    error_type=type(e).__name__,
                )
            )
            logger.warning(
                "Error loading connector from file",
                file=str(file_path),
                error=str(e),
            )

    def _unique_module_name(self, file_path: Path) -> str:
        """Generate a unique module name to avoid sys.modules collisions."""
        payload = str(file_path.resolve()).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()[:12]
        return f"polisyos_dyn_{digest}"

    def _is_valid_connector(self, obj: type) -> bool:
        """
        Check if a class appears to implement SourceConnector protocol.

        Checks for required class attributes without instantiating.
        """
        required_attrs = ("connector_id", "capabilities", "metadata")

        for attr in required_attrs:
            if not hasattr(obj, attr):
                return False

        # Check for required methods
        required_methods = ("connect", "disconnect", "health_check", "fetch")

        for method in required_methods:
            if not hasattr(obj, method):
                return False
            # Verify it's a method (callable)
            if not callable(getattr(obj, method, None)):
                return False

        return True

    def _get_fqid(self, connector_class: type["SourceConnector"]) -> str:
        """Get fully qualified ID from connector class."""
        metadata = getattr(connector_class, "metadata", None)
        if metadata is not None and hasattr(metadata, "fully_qualified_id"):
            return metadata.fully_qualified_id

        # Fallback to connector_id
        connector_id = getattr(connector_class, "connector_id", "unknown")
        return connector_id

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None


def discover_connectors(
    *,
    refresh: bool = False,
    allow_paths: bool | None = None,
) -> Iterator[type["SourceConnector"]]:
    """
    Convenience function to discover all available connectors.

    Creates a ConnectorDiscovery instance and yields all discovered connectors.

    Args:
        refresh: If True, re-discover connectors
        allow_paths: If True, allow filesystem path discovery

    Yields:
        Connector classes implementing SourceConnector protocol
    """
    discovery = ConnectorDiscovery()
    yield from discovery.discover_all(refresh=refresh, allow_paths=allow_paths)


def discover_connectors_from_modules(
    modules: Sequence[str],
) -> Iterator[type["SourceConnector"]]:
    """
    Discover connectors from specific module paths.

    Args:
        modules: List of module paths to scan

    Yields:
        Connector classes implementing SourceConnector protocol
    """
    discovery = ConnectorDiscovery()

    for module_path in modules:
        discovery.add_module(module_path)

    yield from discovery._discover_explicit_modules()


def get_discovery_errors() -> list[DiscoveryError]:
    """Get list of all discovery errors encountered."""
    discovery = ConnectorDiscovery()
    return discovery.errors
