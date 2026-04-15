"""Tests for Phase 9.3 — hot reload thread safety and cache invalidation."""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.hot_reload import (
    FoundryHotReloader,
    HotReloadSandboxPolicy,
    get_reload_version,
)
from polisyos.foundry.methods.registry import registry_scope


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


@pytest.fixture()
def live_registry():
    with registry_scope() as reg:
        yield reg


def _make_method_class(module_name: str, fqn: str, *, description: str = "hot reload") -> type:
    namespace_name, version = fqn.split("@", 1)
    namespace, name = namespace_name.rsplit(".", 1)
    signature = MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata = MethodMetadata(description=description)

    method_class = type(
        f"Reloaded_{name}",
        (),
        {
            "__module__": module_name,
            "signature": signature,
            "metadata": metadata,
            "pure_step": staticmethod(lambda state, params: state),
        },
    )
    return method_class


def _make_module(module_name: str, *classes: type) -> types.ModuleType:
    module = types.ModuleType(module_name)
    for cls in classes:
        setattr(module, cls.__name__, cls)
    return module


def test_reload_invalidates_cache(reloader: FoundryHotReloader, _fake_module: tuple) -> None:
    """After a successful reload, cache generation invalidation must run."""
    mod_name, mod = _fake_module

    with patch.object(reloader, "_load_module_transactionally", return_value=mod) as mock_load, \
         patch(
             "polisyos.foundry.methods.compiler.get_global_cache"
         ) as mock_cache_fn:
        mock_cache = MagicMock()
        mock_cache.invalidate_all.return_value = 3
        mock_cache_fn.return_value = mock_cache

        result = reloader._reload_and_register(mod_name, Path("/fake/path.py"))

        assert result is True
        mock_load.assert_called_once()
        mock_cache.invalidate_all.assert_called_once()


def test_reload_thread_safe(reloader: FoundryHotReloader, _fake_module: tuple) -> None:
    """Concurrent reloads must not corrupt registry or cache state."""
    mod_name, mod = _fake_module
    n_threads = 20
    errors: list[Exception] = []

    def do_reload() -> None:
        try:
            reloader._reload_and_register(mod_name, Path("/fake/path.py"))
        except Exception as exc:
            errors.append(exc)

    with patch.object(reloader, "_load_module_transactionally", return_value=mod), \
         patch("polisyos.foundry.methods.compiler.get_global_cache") as mock_cf:
        mock_cf.return_value = MagicMock(invalidate_all=MagicMock(return_value=0))
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

    with patch.object(reloader, "_load_module_transactionally", return_value=mod), \
         patch(
             "polisyos.foundry.methods.compiler.get_global_cache"
         ) as mock_cf:
        mock_cf.return_value = MagicMock(invalidate_all=MagicMock(return_value=0))

        reloader._reload_and_register(mod_name, Path("/x.py"))
        assert reloader.reload_version == 1

        reloader._reload_and_register(mod_name, Path("/y.py"))
        assert reloader.reload_version == 2


def test_reload_version_no_increment_on_failure(reloader: FoundryHotReloader) -> None:
    """reload_version must NOT increment on failed reload."""
    assert reloader.reload_version == 0

    with patch.object(reloader, "_load_module_transactionally", side_effect=ImportError("boom")):
        result = reloader._reload_and_register("nonexistent_module", Path("/x.py"))

    assert result is False
    assert reloader.reload_version == 0


def test_failed_publication_keeps_previous_module(
    reloader: FoundryHotReloader,
    _fake_module: tuple,
) -> None:
    mod_name, previous = _fake_module
    staged = types.ModuleType(mod_name)

    with patch.object(reloader, "_load_module_transactionally", return_value=staged), \
         patch.object(reloader, "_publish_registry_diff", side_effect=RuntimeError("boom")):
        assert reloader._reload_and_register(mod_name, Path("/x.py")) is False

    assert sys.modules[mod_name] is previous


def test_get_reload_version_no_global() -> None:
    """get_reload_version returns 0 when no global reloader is active."""
    with patch("polisyos.foundry.methods.hot_reload._global_reloader", None):
        assert get_reload_version() == 0


def test_reload_recovers_after_failed_first_load(tmp_path) -> None:
    pkg = tmp_path / "xpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    module_path = pkg / "bad.py"
    module_path.write_text("def broken(:\n    pass\n")
    sys.path.insert(0, str(tmp_path))
    try:
        reloader = FoundryHotReloader(watch_paths=[pkg], registry=MagicMock())

        assert reloader.reload_module_at(module_path) is False
        assert "xpkg.bad" not in sys.modules

        module_path.write_text("value = 42\n")
        assert reloader.reload_module_at(module_path) is True
        assert sys.modules["xpkg.bad"].value == 42
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("xpkg.bad", None)
        sys.modules.pop("xpkg", None)


def test_reload_report_tracks_added_updated_and_removed_methods(live_registry) -> None:
    module_name = "_test_hot_reload_report"
    reloader = FoundryHotReloader(watch_paths=[], registry=live_registry)
    alpha_v1 = _make_method_class(module_name, "tests.reload.alpha@1.0.0", description="v1")
    beta_v1 = _make_method_class(module_name, "tests.reload.beta@1.0.0", description="v1")
    first_module = _make_module(module_name, alpha_v1, beta_v1)

    with patch.object(reloader, "_load_module_transactionally", return_value=first_module):
        assert reloader._reload_and_register(module_name, Path("/tmp/a.py")) is True

    assert "tests.reload.alpha@1.0.0" in live_registry
    assert "tests.reload.beta@1.0.0" in live_registry
    assert reloader.last_report is not None
    assert set(reloader.last_report.diff.added_methods) == {
        "tests.reload.alpha@1.0.0",
        "tests.reload.beta@1.0.0",
    }

    alpha_v2 = _make_method_class(module_name, "tests.reload.alpha@1.0.0", description="v2")
    gamma_v1 = _make_method_class(module_name, "tests.reload.gamma@1.0.0", description="v1")
    second_module = _make_module(module_name, alpha_v2, gamma_v1)

    with patch.object(reloader, "_load_module_transactionally", return_value=second_module):
        assert reloader._reload_and_register(module_name, Path("/tmp/b.py")) is True

    assert "tests.reload.alpha@1.0.0" in live_registry
    assert "tests.reload.beta@1.0.0" not in live_registry
    assert "tests.reload.gamma@1.0.0" in live_registry
    assert reloader.last_report is not None
    assert reloader.last_report.diff.updated_methods == ("tests.reload.alpha@1.0.0",)
    assert reloader.last_report.diff.removed_methods == ("tests.reload.beta@1.0.0",)
    assert reloader.last_report.diff.added_methods == ("tests.reload.gamma@1.0.0",)


def test_reload_sandbox_can_block_method_removals(live_registry) -> None:
    module_name = "_test_hot_reload_sandbox"
    reloader = FoundryHotReloader(
        watch_paths=[],
        registry=live_registry,
        sandbox_policy=HotReloadSandboxPolicy(allow_removals=False),
    )
    alpha_v1 = _make_method_class(module_name, "tests.reload.blocked@1.0.0")
    first_module = _make_module(module_name, alpha_v1)

    with patch.object(reloader, "_load_module_transactionally", return_value=first_module):
        assert reloader._reload_and_register(module_name, Path("/tmp/c.py")) is True

    empty_module = _make_module(module_name)
    with patch.object(reloader, "_load_module_transactionally", return_value=empty_module):
        assert reloader._reload_and_register(module_name, Path("/tmp/d.py")) is False

    assert "tests.reload.blocked@1.0.0" in live_registry
