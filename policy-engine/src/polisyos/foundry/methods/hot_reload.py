"""
Foundry Hot-Reload (dev mode).

``FoundryHotReloader`` watches catalog source directories for ``.py`` file
changes and automatically re-discovers / re-registers modified methods,
eliminating the need to restart the Python process during development.

Activation
----------
Set the environment variable ``FOUNDRY_HOT_RELOAD=1`` before importing
``polisyos.foundry`` — the reloader will start automatically — **or**
call ``start_hot_reload()`` explicitly:

::

    from polisyos.foundry.methods.hot_reload import start_hot_reload
    stop = start_hot_reload()   # returns a stop callback
    # ... develop ...
    stop()

Requirements
------------
- ``watchfiles`` package (``pip install 'polisyos[hotreload]'``).
- Python ≥ 3.11 (asyncio.timeout).

How it works
------------
1. The reloader runs ``watchfiles.awatch()`` in a background daemon thread.
2. On each ``.py`` change, it calls ``importlib.reload()`` on the affected
   module (best-effort; silently ignores reload failures).
3. After reload, ``MethodDiscovery`` re-scans the module for Foundry
   method classes and re-registers them (with ``override=True``).

Limitations
-----------
- Structural changes (e.g. renamed FQNs) are not auto-handled; old entries
  remain in the registry until the process restarts.
- Module-level side effects will re-execute on reload.
- Only ``*.py`` files under the watched path trigger reloads.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import os
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "FoundryHotReloader",
    "HotReloadDiff",
    "HotReloadFailureReport",
    "HotReloadReport",
    "HotReloadSandboxPolicy",
    "get_reload_version",
    "start_hot_reload",
    "stop_hot_reload",
]

_logger = logging.getLogger("foundry.hot_reload")
_HOT_RELOAD_FAILURES = (
    AttributeError,
    ImportError,
    KeyError,
    OSError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
)

# ---------------------------------------------------------------------------
# FoundryHotReloader
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HotReloadSandboxPolicy:
    """Bound the set of registry mutations a hot reload publication may perform."""

    allow_additions: bool = True
    allow_updates: bool = True
    allow_removals: bool = True


@dataclass(frozen=True, slots=True)
class HotReloadDiff:
    """Module-scoped method diff for one staged hot reload publication."""

    module_name: str
    added_methods: tuple[str, ...]
    updated_methods: tuple[str, ...]
    removed_methods: tuple[str, ...]
    unchanged_methods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HotReloadReport:
    """Structured report for the most recent successful reload publication."""

    module_name: str
    path: str
    diff: HotReloadDiff
    cache_invalidated: bool
    reload_version: int


@dataclass(frozen=True, slots=True)
class HotReloadFailureReport:
    """Structured diagnostic for the most recent failed reload attempt."""

    module_name: str
    path: str
    error_type: str
    message: str


class FoundryHotReloader:
    """
    Watches Foundry catalog directories and re-registers changed methods.

    Parameters
    ----------
    watch_paths:
        Directories to watch for ``.py`` file changes.
    registry:
        ``MethodRegistry`` to register discovered methods into.
        Defaults to ``get_registry()``.
    """

    def __init__(
        self,
        watch_paths: list[Path] | None = None,
        registry: Any | None = None,
        sandbox_policy: HotReloadSandboxPolicy | None = None,
    ) -> None:
        if watch_paths is None:
            watch_paths = self._default_catalog_paths()
        self._watch_paths = [Path(p) for p in watch_paths]
        self._registry = registry
        self._sandbox_policy = sandbox_policy or HotReloadSandboxPolicy()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._reload_lock = threading.RLock()
        self._reload_version: int = 0
        self._last_report: HotReloadReport | None = None
        self._last_failure: HotReloadFailureReport | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start watching in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="foundry-hot-reload",
            daemon=True,
        )
        self._thread.start()
        _logger.info(
            "Hot-reload started, watching: %s",
            [str(p) for p in self._watch_paths],
        )

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        _logger.info("Hot-reload stopped.")

    @property
    def reload_version(self) -> int:
        """Monotonically increasing counter, incremented on each successful reload."""
        with self._reload_lock:
            return self._reload_version

    @property
    def last_report(self) -> HotReloadReport | None:
        """Structured report for the last successful reload publication."""
        with self._reload_lock:
            return self._last_report

    @property
    def last_failure(self) -> HotReloadFailureReport | None:
        """Structured report for the last failed reload attempt."""
        with self._reload_lock:
            return self._last_failure

    def reload_module_at(self, path: Path) -> bool:
        """
        Manually reload the module at *path* and re-register its methods.

        Returns True on success, False on failure.
        """
        module_name = self._path_to_module_name(path)
        if module_name is None:
            return False
        return self._reload_and_register(module_name, path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Background loop — runs watchfiles.awatch synchronously via asyncio."""
        try:
            import asyncio

            asyncio.run(self._async_watch_loop())
        except ImportError:
            _logger.warning("watchfiles not installed; hot-reload disabled.")
        except (OSError, RuntimeError) as exc:
            _logger.warning("Hot-reload loop exited: %s", exc)

    async def _async_watch_loop(self) -> None:
        try:
            import watchfiles
        except ImportError:
            _logger.warning("watchfiles not installed. Run: pip install 'polisyos[hotreload]'")
            return

        async for changes in watchfiles.awatch(*self._watch_paths, stop_event=self._stop_event):
            for change_type, path_str in changes:
                path = Path(path_str)
                if path.suffix != ".py":
                    continue
                _logger.debug("Detected change: %s %s", change_type, path)
                module_name = self._path_to_module_name(path)
                if module_name:
                    self._reload_and_register(module_name, path)

    def _reload_and_register(self, module_name: str, path: Path) -> bool:
        """
        Reload one module via staged publication and re-register its methods.

        The live module reference in ``sys.modules`` is only replaced after the
        new module object has been executed successfully, validated for Foundry
        methods, registered into the registry, and the compilation cache has
        advanced to a new generation.
        """
        with self._reload_lock:
            previous_module = sys.modules.get(module_name)
            published_previous_entries: dict[str, Any] | None = None
            published_staged_fqns: set[str] = set()
            try:
                module = self._load_module_transactionally(module_name, path)
                foundry_methods = self._collect_foundry_methods(module)
                diff = self._build_reload_diff(module_name, foundry_methods)
                self._validate_reload_diff(diff)
                published_previous_entries, published_staged_fqns = self._publish_registry_diff(
                    module_name,
                    foundry_methods,
                    diff,
                )
                sys.modules[module_name] = module
                cache_invalidated = self._invalidate_cache()
                self._reload_version += 1
                self._last_report = HotReloadReport(
                    module_name=module_name,
                    path=str(path),
                    diff=diff,
                    cache_invalidated=cache_invalidated,
                    reload_version=self._reload_version,
                )
                _logger.info("Hot-reloaded: %s (version=%d)", module_name, self._reload_version)
                return True
            except _HOT_RELOAD_FAILURES as exc:
                if published_previous_entries is not None:
                    self._restore_registry_entries(
                        self._registry_or_default(),
                        published_previous_entries,
                        published_staged_fqns,
                    )
                if previous_module is not None:
                    sys.modules[module_name] = previous_module
                else:
                    sys.modules.pop(module_name, None)
                self._last_failure = HotReloadFailureReport(
                    module_name=module_name,
                    path=str(path),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
                _logger.warning("Failed to reload %s: %s", module_name, exc)
                return False

    def _invalidate_cache(self) -> bool:
        """Clear compilation cache after method reload to prevent stale hits."""
        try:
            from polisyos.foundry.methods.compiler import get_global_cache

            cleared = get_global_cache().invalidate_all()
            _logger.debug("Cleared %d compilation cache entries after reload", cleared)
            return True
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Compilation cache invalidation failed: {exc}") from exc

    def _load_module_transactionally(self, module_name: str, path: Path) -> Any:
        """
        Execute a fresh module object from disk without mutating ``sys.modules``.

        This avoids in-place ``importlib.reload()`` mutation of the previously
        published module object and gives hot reload a single publication point.
        """
        importlib.invalidate_caches()
        self._ensure_parent_package(module_name)
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not build import spec for {module_name} from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module

    def _collect_foundry_methods(self, module: Any) -> list[type]:
        """Return Foundry method classes declared directly in *module*."""
        from polisyos.foundry.methods.discovery import is_foundry_method

        methods: list[type] = []
        module_name = getattr(module, "__name__", "")
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if getattr(obj, "__module__", None) != module_name:
                continue
            if name.startswith("_"):
                continue
            if is_foundry_method(obj):
                methods.append(obj)
        return methods

    def _publish_registry_diff(
        self,
        module_name: str,
        foundry_methods: list[type],
        diff: HotReloadDiff,
    ) -> tuple[dict[str, Any], set[str]]:
        """Apply a module-scoped registry diff and roll back on failure."""
        reg = self._registry_or_default()
        staged_fqns = {method_class.signature.fqn for method_class in foundry_methods}
        previous_entries = {
            fqn: reg.get_entry(fqn) for fqn in self._module_registry_fqns(module_name) | staged_fqns
        }
        try:
            for fqn in diff.removed_methods:
                reg.unregister(fqn)
                _logger.debug("Unregistered stale hot-reload method: %s", fqn)
            for method_class in foundry_methods:
                reg.register(method_class, override=True)
                _logger.debug("Re-registered: %s", method_class.signature.fqn)
        except _HOT_RELOAD_FAILURES:
            self._restore_registry_entries(reg, previous_entries, staged_fqns)
            raise
        return previous_entries, staged_fqns

    def _restore_registry_entries(
        self,
        registry: Any,
        previous_entries: dict[str, Any],
        staged_fqns: set[str],
    ) -> None:
        """Best-effort rollback for a failed registry publication."""
        affected_fqns = set(previous_entries) | set(staged_fqns)
        for fqn in affected_fqns:
            registry.unregister(fqn)
        for entry in previous_entries.values():
            if entry is None:
                continue
            cached_class = getattr(entry, "_cached_class", None)
            if entry.loaded and cached_class is not None:
                registry.register(cached_class, override=True)
                continue
            registry.register_lazy(
                entry.signature,
                entry.metadata,
                entry.factory,
                override=True,
                import_target=entry.persistable_import_target,
            )

    def _build_reload_diff(self, module_name: str, foundry_methods: list[type]) -> HotReloadDiff:
        """Compute module-scoped add/update/remove sets before publication."""
        staged_by_fqn = {
            method_class.signature.fqn: method_class for method_class in foundry_methods
        }
        previous_entries = self._module_registry_entries(module_name)

        added = sorted(set(staged_by_fqn) - set(previous_entries))
        removed = sorted(set(previous_entries) - set(staged_by_fqn))
        updated: list[str] = []
        unchanged: list[str] = []
        for fqn in sorted(set(staged_by_fqn) & set(previous_entries)):
            previous = previous_entries[fqn]
            staged = staged_by_fqn[fqn]
            signature_changed = previous.signature.abi_digest() != staged.signature.abi_digest()
            metadata_changed = previous.metadata.stable_digest() != staged.metadata.stable_digest()
            if signature_changed or metadata_changed:
                updated.append(fqn)
            else:
                unchanged.append(fqn)

        return HotReloadDiff(
            module_name=module_name,
            added_methods=tuple(added),
            updated_methods=tuple(updated),
            removed_methods=tuple(removed),
            unchanged_methods=tuple(unchanged),
        )

    def _validate_reload_diff(self, diff: HotReloadDiff) -> None:
        """Fail closed when the staged reload attempts a disallowed mutation class."""
        if diff.added_methods and not self._sandbox_policy.allow_additions:
            raise RuntimeError(
                f"Hot reload additions blocked for {diff.module_name}: {list(diff.added_methods)}"
            )
        if diff.updated_methods and not self._sandbox_policy.allow_updates:
            raise RuntimeError(
                f"Hot reload updates blocked for {diff.module_name}: {list(diff.updated_methods)}"
            )
        if diff.removed_methods and not self._sandbox_policy.allow_removals:
            raise RuntimeError(
                f"Hot reload removals blocked for {diff.module_name}: {list(diff.removed_methods)}"
            )

    def _module_registry_entries(self, module_name: str) -> dict[str, Any]:
        """Return live registry entries currently published from *module_name*."""
        reg = self._registry_or_default()
        snapshot = reg.snapshot()
        entries: dict[str, Any] = {}
        for entry in snapshot.entries():
            if entry.import_module != module_name:
                continue
            live_entry = reg.get_entry(entry.fqn)
            if live_entry is not None:
                entries[entry.fqn] = live_entry
        return entries

    def _module_registry_fqns(self, module_name: str) -> set[str]:
        return set(self._module_registry_entries(module_name))

    def _registry_or_default(self) -> Any:
        from polisyos.foundry.methods.registry import get_registry

        return self._registry or get_registry()

    @staticmethod
    def _path_to_module_name(path: Path) -> str | None:
        """Convert a file path to a Python module name using sys.path."""
        path = path.resolve()
        for sys_path in sys.path:
            try:
                rel = path.relative_to(Path(sys_path).resolve())
                parts = list(rel.with_suffix("").parts)
                return ".".join(parts)
            except ValueError:
                continue
        return None

    @staticmethod
    def _ensure_parent_package(module_name: str) -> None:
        package_name, _, _ = module_name.rpartition(".")
        if package_name and package_name not in sys.modules:
            importlib.import_module(package_name)

    @staticmethod
    def _default_catalog_paths() -> list[Path]:
        """Return the default catalog directories to watch."""
        try:
            import polisyos.foundry.methods.catalog as _catalog_pkg

            catalog_dir = Path(_catalog_pkg.__file__).parent
            return [catalog_dir]
        except (ImportError, AttributeError, TypeError):
            return []


# ---------------------------------------------------------------------------
# Module-level start/stop helpers
# ---------------------------------------------------------------------------

_global_reloader: FoundryHotReloader | None = None
_global_reloader_lock = threading.Lock()


def start_hot_reload(
    watch_paths: list[Path] | None = None,
    registry: Any | None = None,
) -> Callable[[], None]:
    """
    Start the global Foundry hot-reloader.

    Parameters
    ----------
    watch_paths:
        Directories to watch.  Defaults to the ``catalog/`` package dir.
    registry:
        Registry to update.  Defaults to ``get_registry()``.

    Returns
    -------
    Callable
        A ``stop()`` function.  Call it to stop watching.
    """
    global _global_reloader
    with _global_reloader_lock:
        if _global_reloader is not None and _global_reloader._thread is not None:
            _global_reloader.stop()
        _global_reloader = FoundryHotReloader(watch_paths=watch_paths, registry=registry)
        _global_reloader.start()
    return stop_hot_reload


def stop_hot_reload() -> None:
    """Stop the global hot-reloader."""
    global _global_reloader
    with _global_reloader_lock:
        if _global_reloader is not None:
            _global_reloader.stop()
            _global_reloader = None


def get_reload_version() -> int:
    """Return the current reload version of the global reloader, or 0 if not active."""
    with _global_reloader_lock:
        if _global_reloader is not None:
            return _global_reloader.reload_version
        return 0


# ---------------------------------------------------------------------------
# Auto-start on FOUNDRY_HOT_RELOAD=1
# ---------------------------------------------------------------------------

if os.getenv("FOUNDRY_HOT_RELOAD", "").strip() in {"1", "true", "yes", "on"}:
    start_hot_reload()
