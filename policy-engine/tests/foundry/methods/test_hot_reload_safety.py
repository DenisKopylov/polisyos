"""Tests for Phase 9.3 — hot reload thread safety and cache invalidation."""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from polisyos.foundry.methods.hot_reload import FoundryHotReloader, get_reload_version


@pytest.fixture()
def _fake_module():
    """Install and clean up a fake module in sys.modules."""
    name = "_test_hot_reload_fake_module"
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    yield name, mod
    sys.modules.pop(name, None)


@pytest.fixture()
def reloader():
    return FoundryHotReloader(watch_paths=[], registry=MagicMock())


def test_reload_invalidates_cache(reloader: FoundryHotReloader, _fake_module: tuple) -> None:
    """After a successful reload, CompilationCache.clear() must be called."""
    mod_name, mod = _fake_module

    with patch("importlib.reload", return_value=mod) as mock_reload, \
         patch(
             "polisyos.foundry.methods.compiler.get_global_cache"
         ) as mock_cache_fn:
        mock_cache = MagicMock()
        mock_cache.clear.return_value = 3
        mock_cache_fn.return_value = mock_cache

        result = reloader._reload_and_register(mod_name, Path("/fake/path.py"))

        assert result is True
        mock_reload.assert_called_once()
        mock_cache.clear.assert_called_once()


def test_reload_thread_safe(reloader: FoundryHotReloader, _fake_module: tuple) -> None:
    """Concurrent reloads must not corrupt registry or cache state."""
    mod_name, mod = _fake_module
    n_threads = 20
    errors: list[Exception] = []

    def do_reload() -> None:
        try:
            with patch("importlib.reload", return_value=mod), \
                 patch(
                     "polisyos.foundry.methods.compiler.get_global_cache"
                 ) as mock_cf:
                mock_cf.return_value = MagicMock(clear=MagicMock(return_value=0))
                reloader._reload_and_register(mod_name, Path("/fake/path.py"))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=do_reload) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert not errors, f"Concurrent reloads raised errors: {errors}"
    assert reloader.reload_version == n_threads


def test_reload_version_increments(reloader: FoundryHotReloader, _fake_module: tuple) -> None:
    """reload_version must increment on each successful reload."""
    mod_name, mod = _fake_module
    assert reloader.reload_version == 0

    with patch("importlib.reload", return_value=mod), \
         patch(
             "polisyos.foundry.methods.compiler.get_global_cache"
         ) as mock_cf:
        mock_cf.return_value = MagicMock(clear=MagicMock(return_value=0))

        reloader._reload_and_register(mod_name, Path("/x.py"))
        assert reloader.reload_version == 1

        reloader._reload_and_register(mod_name, Path("/y.py"))
        assert reloader.reload_version == 2


def test_reload_version_no_increment_on_failure(reloader: FoundryHotReloader) -> None:
    """reload_version must NOT increment on failed reload."""
    assert reloader.reload_version == 0

    with patch("importlib.reload", side_effect=ImportError("boom")):
        result = reloader._reload_and_register("nonexistent_module", Path("/x.py"))

    # Module not in sys.modules, so it tries spec_from_file_location which returns None
    assert reloader.reload_version == 0


def test_get_reload_version_no_global() -> None:
    """get_reload_version returns 0 when no global reloader is active."""
    with patch("polisyos.foundry.methods.hot_reload._global_reloader", None):
        assert get_reload_version() == 0
