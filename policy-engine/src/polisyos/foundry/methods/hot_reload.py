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
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable

__all__ = [
    "FoundryHotReloader",
    "get_reload_version",
    "start_hot_reload",
    "stop_hot_reload",
]

_logger = logging.getLogger("foundry.hot_reload")

# ---------------------------------------------------------------------------
# FoundryHotReloader
# ---------------------------------------------------------------------------


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
    ) -> None:
        if watch_paths is None:
            watch_paths = self._default_catalog_paths()
        self._watch_paths = [Path(p) for p in watch_paths]
        self._registry = registry
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._reload_lock = threading.RLock()
        self._reload_version: int = 0

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
        return self._reload_version

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
        except Exception as exc:
            _logger.debug("Hot-reload loop exited: %s", exc)

    async def _async_watch_loop(self) -> None:
        import asyncio
        try:
            import watchfiles
        except ImportError:
            _logger.warning(
                "watchfiles not installed. Run: pip install 'polisyos[hotreload]'"
            )
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
        """Reload module and re-register any Foundry methods found in it."""
        with self._reload_lock:
            try:
                if module_name in sys.modules:
                    module = importlib.reload(sys.modules[module_name])
                else:
                    spec = importlib.util.spec_from_file_location(module_name, path)
                    if spec is None or spec.loader is None:
                        return False
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)  # type: ignore[union-attr]

                self._register_from_module(module)
                self._invalidate_cache()
                self._reload_version += 1
                _logger.info("Hot-reloaded: %s (version=%d)", module_name, self._reload_version)
                return True
            except Exception as exc:
                _logger.warning("Failed to reload %s: %s", module_name, exc)
                return False

    def _invalidate_cache(self) -> None:
        """Clear compilation cache after method reload to prevent stale hits."""
        try:
            from polisyos.foundry.methods.compiler import get_global_cache
            cleared = get_global_cache().clear()
            _logger.debug("Cleared %d compilation cache entries after reload", cleared)
        except Exception as exc:
            _logger.debug("Cache invalidation skipped: %s", exc)

    def _register_from_module(self, module: Any) -> None:
        """Discover and re-register Foundry methods from a reloaded module."""
        from polisyos.foundry.methods.registry import get_registry
        from polisyos.foundry.methods.discovery import is_foundry_method

        reg = self._registry or get_registry()
        for name in dir(module):
            obj = getattr(module, name, None)
            if obj is None:
                continue
            try:
                if is_foundry_method(obj):
                    reg.register(obj, override=True)
                    _logger.debug("Re-registered: %s", obj.signature.fqn)
            except Exception as exc:
                _logger.debug("Skip %s.%s: %s", module.__name__, name, exc)

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
    def _default_catalog_paths() -> list[Path]:
        """Return the default catalog directories to watch."""
        try:
            import polisyos.foundry.methods.catalog as _catalog_pkg
            catalog_dir = Path(_catalog_pkg.__file__).parent
            return [catalog_dir]
        except Exception:
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
