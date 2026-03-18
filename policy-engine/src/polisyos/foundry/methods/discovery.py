"""
Method Discovery from Entry Points and File System.

This module implements automatic discovery of FoundryMethod classes from:
1. Python entry points (production mode) - deterministic, fast
2. File system scanning (development mode) - flexible, for rapid iteration

Architecture Notes:
- Discovery is a feeder for MethodRegistry
- All discovered classes must satisfy the FoundryMethod protocol
- Errors in individual files/modules do not crash the process
- Sources are processed in order; first registration wins by default
"""
from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
import inspect
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Iterator, Protocol, Sequence

from polisyos.common.logger import get_logger
from polisyos.core.discovery import (
    BaseDiscovery,
    DuplicatePolicy,
    discovery_module_name,
    format_traceback,
)
from polisyos.foundry.methods.base import (
    FoundryMethod,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.exceptions import (
    MethodAlreadyRegisteredError,
    MethodDefinitionError,
)
from polisyos.foundry.methods.registry import MethodRegistry

__all__ = [
    "DISCOVERY_MODULE_PREFIX",
    "ENTRY_POINT_GROUP",
    "DiscoveryError",
    "DiscoveryReport",
    "DiscoverySource",
    "DuplicatePolicy",
    "EntryPointSource",
    "FileSystemSource",
    "MethodDiscovery",
    "is_foundry_method",
]


# =============================================================================
# Constants
# =============================================================================

ENTRY_POINT_GROUP = "polisyos.methods"
"""Standard entry point group for PolicyOS method plugins."""

DISCOVERY_MODULE_PREFIX = "_polisyos_discovery_"
"""Prefix for dynamically imported dev-scan modules."""

_logger = get_logger(__name__)


@dataclass(slots=True)
class DiscoveryError:
    """
    Structured record for discovery failures.

    Attributes:
        source: Origin of the error (entry_point, filesystem, registry, source)
        item: Item being processed (entry point name, path, etc.)
        error_type: Exception class name
        message: Exception message
        traceback: Optional traceback string
        module_name: Optional module name involved
        file_path: Optional file path involved
        entry_point: Optional entry point name
    """

    source: str
    item: str | None
    error_type: str
    message: str
    traceback: str | None = None
    module_name: str | None = None
    file_path: str | None = None
    entry_point: str | None = None

    def summary(self) -> str:
        """Human-readable one-line summary."""
        item = self.item or "<unknown>"
        return f"{self.source}: {item} ({self.error_type}) {self.message}"


@dataclass(slots=True)
class DiscoveryReport:
    """
    Report of method discovery results.

    Attributes:
        registered: List of FQNs successfully registered
        duplicates: List of FQNs that were already registered
        errors: List of DiscoveryError records
        sources_processed: Number of discovery sources processed
    """

    registered: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    errors: list[DiscoveryError] = field(default_factory=list)
    sources_processed: int = 0

    @property
    def success(self) -> bool:
        """True if no errors occurred during discovery."""
        return len(self.errors) == 0

    @property
    def total_registered(self) -> int:
        """Total number of methods successfully registered."""
        return len(self.registered)

    @property
    def total_duplicates(self) -> int:
        """Total number of duplicate registrations skipped."""
        return len(self.duplicates)

    @property
    def total_errors(self) -> int:
        """Total number of errors encountered."""
        return len(self.errors)

    def merge(self, other: DiscoveryReport) -> DiscoveryReport:
        """Merge another report into this one."""
        self.registered.extend(other.registered)
        self.duplicates.extend(other.duplicates)
        self.errors.extend(other.errors)
        self.sources_processed += other.sources_processed
        return self

    def summary(self) -> str:
        """Generate a human-readable summary string."""
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"DiscoveryReport({status}): "
            f"{self.total_registered} registered, "
            f"{self.total_duplicates} duplicates, "
            f"{self.total_errors} errors"
        )

    def __repr__(self) -> str:
        return (
            f"DiscoveryReport("
            f"registered={self.total_registered}, "
            f"duplicates={self.total_duplicates}, "
            f"errors={self.total_errors}, "
            f"success={self.success})"
        )


# =============================================================================
# Discovery Source Protocol
# =============================================================================


class DiscoverySource(Protocol):
    """
    Protocol for method discovery sources.

    Implementations must yield type objects that satisfy the FoundryMethod
    protocol. Sources may optionally expose an ``errors`` attribute containing
    ``DiscoveryError`` records.
    """

    def discover(self) -> Iterator[type[FoundryMethod]]:
        """Yield discovered method classes."""
        ...


# =============================================================================
# Method Detection Utilities
# =============================================================================


def is_foundry_method(cls: Any) -> bool:
    """
    Check if a class implements the FoundryMethod protocol.

    A valid FoundryMethod class must have:
    1. A ``signature`` class attribute of type MethodSignature
    2. A ``metadata`` class attribute of type MethodMetadata
    3. A ``pure_step`` static method
    4. Not be the FoundryMethod protocol class itself
    5. Not be an abstract base class
    """
    if not isinstance(cls, type):
        return False

    if cls is FoundryMethod:
        return False

    if not hasattr(cls, "signature"):
        return False
    sig = getattr(cls, "signature", None)
    if not isinstance(sig, MethodSignature):
        return False

    if not hasattr(cls, "metadata"):
        return False
    meta = getattr(cls, "metadata", None)
    if not isinstance(meta, MethodMetadata):
        return False

    if not hasattr(cls, "pure_step"):
        return False
    pure_step_attr = inspect.getattr_static(cls, "pure_step")
    if not isinstance(pure_step_attr, staticmethod):
        return False

    if inspect.isabstract(cls):
        return False

    return True


def _get_method_fqn_safe(cls: type) -> str:
    """Safely extract the FQN from a method class."""
    try:
        if hasattr(cls, "signature") and hasattr(cls.signature, "fqn"):
            return cls.signature.fqn
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Ignored exception: %s", exc)
    return f"{cls.__module__}.{cls.__name__}"


# =============================================================================
# Entry Point Source (Production)
# =============================================================================


class EntryPointSource:
    """
    Discover methods via Python entry points.

    Entry points can reference:
    1. A function (callable) with no required arguments returning method class(es)
    2. A module to scan for method classes
    3. A method class directly
    """

    def __init__(self, group: str = ENTRY_POINT_GROUP) -> None:
        self._group = group
        self._errors: list[DiscoveryError] = []

    @property
    def group(self) -> str:
        return self._group

    @property
    def errors(self) -> list[DiscoveryError]:
        return list(self._errors)

    def discover(self) -> Iterator[type[FoundryMethod]]:
        self._errors.clear()
        entry_points = self._get_entry_points()

        for ep in entry_points:
            try:
                yield from self._process_entry_point(ep)
            except Exception as exc:
                self._errors.append(
                    DiscoveryError(
                        source="entry_point",
                        item=ep.name,
                        error_type=type(exc).__name__,
                        message=str(exc),
                        traceback=format_traceback(),
                        module_name=getattr(ep, "value", None),
                        entry_point=ep.name,
                    )
                )
                _logger.warning(
                    "Failed to load entry point '%s' from group '%s': %s",
                    ep.name,
                    self._group,
                    exc,
                )

    def _get_entry_points(self) -> list[importlib.metadata.EntryPoint]:
        try:
            eps = importlib.metadata.entry_points(group=self._group)
            entries = list(eps)
        except TypeError:
            all_eps = importlib.metadata.entry_points()
            if hasattr(all_eps, "select"):
                entries = list(all_eps.select(group=self._group))
            else:
                entries = list(all_eps.get(self._group, []))

        return sorted(entries, key=lambda ep: (ep.name, ep.value))

    def _process_entry_point(
        self,
        ep: importlib.metadata.EntryPoint,
    ) -> Iterator[type[FoundryMethod]]:
        loaded = ep.load()

        if isinstance(loaded, type):
            if is_foundry_method(loaded):
                yield loaded
            return

        if inspect.ismodule(loaded):
            yield from self._scan_module(loaded)
            return

        if callable(loaded):
            yield from self._call_entry_point(loaded)
            return

    def _call_entry_point(self, func: Callable[..., Any]) -> Iterator[type[FoundryMethod]]:
        if not _callable_accepts_no_args(func):
            raise TypeError("Entry point callable must accept no required arguments")

        result = func()
        if result is None:
            return

        if isinstance(result, type) and is_foundry_method(result):
            yield result
            return

        if isinstance(result, (list, tuple, set, frozenset)):
            for item in result:
                if isinstance(item, type) and is_foundry_method(item):
                    yield item
            return

        if isinstance(result, Iterable) and not isinstance(result, (str, bytes)):
            for item in result:
                if isinstance(item, type) and is_foundry_method(item):
                    yield item
            return

    def _scan_module(self, module: ModuleType) -> Iterator[type[FoundryMethod]]:
        module_name = getattr(module, "__name__", "")

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if getattr(obj, "__module__", None) != module_name:
                continue
            if name.startswith("_"):
                continue
            if is_foundry_method(obj):
                yield obj


# =============================================================================
# File System Source (Development Mode)
# =============================================================================


class FileSystemSource:
    """
    Discover methods by scanning directories.

    Uses importlib.import_module with a temporary namespace package prefix
    to ensure package-relative imports work and to avoid module name collisions.
    """

    DEFAULT_EXCLUDE_PATTERNS: frozenset[str] = frozenset(
        {
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "test_*",
            "*_test.py",
            "conftest.py",
        }
    )

    def __init__(
        self,
        paths: Sequence[Path],
        pattern: str = "*.py",
        exclude_patterns: frozenset[str] | None = None,
    ) -> None:
        self._paths = [Path(p) for p in paths]
        self._pattern = pattern
        self._exclude_patterns = (
            exclude_patterns if exclude_patterns is not None else self.DEFAULT_EXCLUDE_PATTERNS
        )
        self._loaded_modules: set[str] = set()
        self._errors: list[DiscoveryError] = []
        self._prefix_map: dict[Path, str] = {}
        self._base_is_package: dict[Path, bool] = {}

    @property
    def paths(self) -> list[Path]:
        return list(self._paths)

    @property
    def errors(self) -> list[DiscoveryError]:
        return list(self._errors)

    def discover(self) -> Iterator[type[FoundryMethod]]:
        self._errors.clear()
        for base_path in self._paths:
            if not base_path.exists():
                _logger.debug("Skipping non-existent path: %s", base_path)
                continue

            if not base_path.is_dir():
                _logger.debug("Skipping non-directory path: %s", base_path)
                continue

            import_root = self._import_root(base_path)

            with _temporary_sys_path(import_root):
                py_files = sorted(base_path.rglob(self._pattern))

                for py_file in py_files:
                    if self._should_skip_file(py_file, base_path=base_path):
                        continue

                    try:
                        module = self._load_module(py_file, base_path)
                        if module is not None:
                            yield from self._scan_module(module)
                    except SyntaxError as exc:
                        self._errors.append(
                            DiscoveryError(
                                source="filesystem",
                                item=str(py_file),
                                error_type=type(exc).__name__,
                                message=f"{exc.msg} (line {exc.lineno or 0})",
                                traceback=format_traceback(),
                                file_path=str(py_file),
                            )
                        )
                        _logger.warning(
                            "Syntax error in %s: %s (line %d)",
                            py_file,
                            exc.msg,
                            exc.lineno or 0,
                        )
                    except ImportError as exc:
                        self._errors.append(
                            DiscoveryError(
                                source="filesystem",
                                item=str(py_file),
                                error_type=type(exc).__name__,
                                message=str(exc),
                                traceback=format_traceback(),
                                file_path=str(py_file),
                            )
                        )
                        _logger.warning("Import error loading %s: %s", py_file, exc)
                    except Exception as exc:
                        self._errors.append(
                            DiscoveryError(
                                source="filesystem",
                                item=str(py_file),
                                error_type=type(exc).__name__,
                                message=str(exc),
                                traceback=format_traceback(),
                                file_path=str(py_file),
                            )
                        )
                        _logger.warning("Failed to load %s: %s", py_file, exc)

    def _should_skip_file(self, path: Path, *, base_path: Path) -> bool:
        path_name = path.name
        if path_name == "__init__.py":
            return True

        try:
            relative_parts = path.relative_to(base_path).parts
        except ValueError:
            relative_parts = path.parts

        for part in relative_parts:
            if _matches_any(part, self._exclude_patterns):
                return True

        if _matches_any(path_name, self._exclude_patterns):
            return True

        return False

    def _load_module(self, path: Path, base: Path) -> ModuleType | None:
        module_name, prefix, import_root = self._module_name_for(path, base)

        if module_name in self._loaded_modules:
            existing = sys.modules.get(module_name)
            if existing is not None:
                return existing
            self._loaded_modules.discard(module_name)

        self._ensure_prefix_package(prefix, import_root)

        try:
            module = importlib.import_module(module_name)
        except Exception:
            sys.modules.pop(module_name, None)
            self._loaded_modules.discard(module_name)
            raise

        self._loaded_modules.add(module_name)
        return module

    def _module_name_for(self, path: Path, base: Path) -> tuple[str, str, Path]:
        base_resolved = base.resolve()
        module_rel = self._module_relative_name(path, base_resolved)
        prefix = self._prefix_for_base(base_resolved)

        if self._is_base_package(base_resolved):
            import_root = base_resolved.parent
            module_name = f"{prefix}.{base_resolved.name}.{module_rel}"
        else:
            import_root = base_resolved
            module_name = f"{prefix}.{module_rel}"

        return module_name, prefix, import_root

    def _module_relative_name(self, path: Path, base: Path) -> str:
        try:
            relative = path.relative_to(base)
            parts = relative.with_suffix("").parts
        except ValueError:
            parts = (path.stem,)
        return ".".join(parts)

    def _prefix_for_base(self, base: Path) -> str:
        key = base.resolve()
        if key in self._prefix_map:
            return self._prefix_map[key]

        prefix = discovery_module_name(
            key,
            prefix=DISCOVERY_MODULE_PREFIX,
            algorithm="sha1",
            digest_length=10,
        )
        self._prefix_map[key] = prefix
        return prefix

    def _is_base_package(self, base: Path) -> bool:
        key = base.resolve()
        if key in self._base_is_package:
            return self._base_is_package[key]

        is_pkg = (key / "__init__.py").exists()
        self._base_is_package[key] = is_pkg
        return is_pkg

    def _import_root(self, base: Path) -> Path:
        base_resolved = base.resolve()
        if self._is_base_package(base_resolved):
            return base_resolved.parent
        return base_resolved

    def _ensure_prefix_package(self, prefix: str, root: Path) -> None:
        if prefix in sys.modules:
            pkg = sys.modules[prefix]
            existing_path = getattr(pkg, "__path__", None)
            if existing_path is None:
                pkg.__path__ = [str(root)]  # type: ignore[attr-defined]
            elif str(root) not in existing_path:
                existing_path.append(str(root))
            return

        import types

        pkg = types.ModuleType(prefix)
        pkg.__path__ = [str(root)]  # type: ignore[attr-defined]
        pkg.__package__ = prefix
        sys.modules[prefix] = pkg

    def _scan_module(self, module: ModuleType) -> Iterator[type[FoundryMethod]]:
        module_name = getattr(module, "__name__", "")

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if getattr(obj, "__module__", None) != module_name:
                continue
            if name.startswith("_"):
                continue
            if is_foundry_method(obj):
                yield obj


# =============================================================================
# Method Discovery Orchestrator
# =============================================================================


class MethodDiscovery:
    """
    Discovers methods from multiple sources and registers them.

    Duplicate handling is configurable via ``on_duplicate``.
    """

    def __init__(
        self,
        registry: MethodRegistry | None = None,
        *,
        on_duplicate: DuplicatePolicy | str = DuplicatePolicy.WARN,
    ) -> None:
        self._registry = registry if registry is not None else MethodRegistry.get_instance()
        self._sources: list[DiscoverySource] = []
        self._duplicate_policy = _normalize_duplicate_policy(on_duplicate)

    @property
    def registry(self) -> MethodRegistry:
        return self._registry

    @property
    def sources(self) -> list[DiscoverySource]:
        return list(self._sources)

    @property
    def duplicate_policy(self) -> DuplicatePolicy:
        return self._duplicate_policy

    def add_source(self, source: DiscoverySource) -> MethodDiscovery:
        self._sources.append(source)
        return self

    def add_entry_points(self, group: str = ENTRY_POINT_GROUP) -> MethodDiscovery:
        self._sources.append(EntryPointSource(group))
        return self

    def add_directory(self, path: Path, pattern: str = "*.py") -> MethodDiscovery:
        self._sources.append(FileSystemSource([path], pattern))
        return self

    def add_directories(self, paths: Sequence[Path], pattern: str = "*.py") -> MethodDiscovery:
        self._sources.append(FileSystemSource(paths, pattern))
        return self

    def discover_all(self, *, cleanup_modules: bool = False) -> DiscoveryReport:
        report = DiscoveryReport()
        collector = BaseDiscovery[type[FoundryMethod], DiscoveryError](
            sources=self._sources,
            on_source_error=lambda source, exc: DiscoveryError(
                source="source",
                item=type(source).__name__,
                error_type=type(exc).__name__,
                message=str(exc),
                traceback=format_traceback(),
            ),
        )
        batches, sources_processed = collector.collect()
        report.sources_processed = sources_processed

        for batch in batches:
            for method_class in batch.items:
                self._register_method(method_class, report)
            report.errors.extend(batch.errors)

        if report.total_registered > 0:
            _logger.info(
                "Discovery complete: %d registered, %d duplicates, %d errors",
                report.total_registered,
                report.total_duplicates,
                report.total_errors,
            )

        if cleanup_modules:
            _cleanup_discovery_modules()

        return report

    def _register_method(
        self,
        method_class: type[FoundryMethod],
        report: DiscoveryReport,
    ) -> None:
        fqn = _get_method_fqn_safe(method_class)

        try:
            registered_fqn = self._registry.register(method_class)
            report.registered.append(registered_fqn)
            _logger.debug("Registered method: %s", registered_fqn)

        except MethodAlreadyRegisteredError as exc:
            self._handle_duplicate(fqn, exc, report)

        except (TypeError, MethodDefinitionError) as exc:
            report.errors.append(
                DiscoveryError(
                    source="registry",
                    item=fqn,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            _logger.warning("Invalid method %s: %s", fqn, exc)

        except Exception as exc:
            report.errors.append(
                DiscoveryError(
                    source="registry",
                    item=fqn,
                    error_type=type(exc).__name__,
                    message=str(exc),
                    traceback=format_traceback(),
                )
            )
            _logger.error("Failed to register %s: %s", fqn, exc)

    def _handle_duplicate(
        self,
        fqn: str,
        exc: MethodAlreadyRegisteredError,
        report: DiscoveryReport,
    ) -> None:
        if self._duplicate_policy in {DuplicatePolicy.WARN, DuplicatePolicy.ERROR}:
            report.duplicates.append(fqn)

        if self._duplicate_policy == DuplicatePolicy.ERROR:
            report.errors.append(
                DiscoveryError(
                    source="registry",
                    item=fqn,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            _logger.error("Duplicate method detected: %s", fqn)
        elif self._duplicate_policy == DuplicatePolicy.WARN:
            _logger.warning("Skipped duplicate method: %s", fqn)
        else:
            _logger.debug("Ignored duplicate method: %s", fqn)


# =============================================================================
# Helpers
# =============================================================================


def _normalize_duplicate_policy(policy: DuplicatePolicy | str) -> DuplicatePolicy:
    if isinstance(policy, DuplicatePolicy):
        return policy

    try:
        return DuplicatePolicy(policy)
    except ValueError as exc:
        raise ValueError(
            f"Invalid duplicate policy: {policy!r}. "
            f"Expected one of: {[p.value for p in DuplicatePolicy]}"
        ) from exc


def _cleanup_discovery_modules() -> None:
    """Remove dynamically loaded discovery modules from sys.modules."""
    to_remove = [
        name for name in sys.modules
        if name.startswith(DISCOVERY_MODULE_PREFIX)
    ]
    for name in to_remove:
        sys.modules.pop(name, None)


def _callable_accepts_no_args(func: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return True

    for param in sig.parameters.values():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if param.default is inspect._empty:
            return False
    return True


@contextlib.contextmanager
def _temporary_sys_path(path: Path) -> Iterator[None]:
    path_str = str(path)
    original = sys.path.copy()
    if path_str and path_str not in sys.path:
        sys.path.insert(0, path_str)
    try:
        yield
    finally:
        sys.path = original


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)
