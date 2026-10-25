"""Behavioral tests for persistent selection-history output placement."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
from types import ModuleType

import pytest

from polisyos.foundry.methods.selection.history import (
    MethodExecutionRecord,
    SelectionHistoryStore,
)


@pytest.fixture
def history_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = importlib.import_module("polisyos.foundry.methods.selection.history")
    monkeypatch.setattr(module, "_GLOBAL_HISTORY", None)
    return module


def _record(*, success: bool, fingerprint: str) -> MethodExecutionRecord:
    return MethodExecutionRecord(
        method_fqn="tests.history.sample@1.0.0",
        timestamp=1.0 if success else 2.0,
        latency_ms=10.0 if success else 20.0,
        success=success,
        failure_type=None if success else "fixture_failure",
        query_fingerprint=fingerprint,
        loss_profile_id="fixture_profile",
        candidate_fqns=("tests.history.sample@1.0.0", "tests.history.alternative@1.0.0"),
        selected_rank=1,
        selection_propensity=0.75,
        advisor_score_vector={"tests.history.sample@1.0.0": 0.8},
        realized_loss_components={"fixture_loss": 0.1 if success else 0.9},
        shadow_loss_estimates={"tests.history.alternative@1.0.0": 0.4},
    )


def _clear_state_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "POLISYOS_FOUNDRY_STATE_HOME",
        "XDG_STATE_HOME",
        "LOCALAPPDATA",
    ):
        monkeypatch.delenv(variable, raising=False)


def _configure_root(
    monkeypatch: pytest.MonkeyPatch,
    history_module: ModuleType,
    *,
    platform: str,
    variable: str,
    value: str | Path,
) -> None:
    _clear_state_env(monkeypatch)
    monkeypatch.setattr(history_module.sys, "platform", platform)
    monkeypatch.setenv(variable, str(value))


@pytest.mark.parametrize(
    ("platform", "variable", "suffix"),
    [
        ("linux", "POLISYOS_FOUNDRY_STATE_HOME", "foundry/selection_history"),
        ("linux", "XDG_STATE_HOME", "polisyos/foundry/selection_history"),
        ("win32", "LOCALAPPDATA", "PolicyOS/foundry/selection_history"),
    ],
)
def test_all_configured_roots_canonicalize_symlinks_and_allow_missing_tail(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    variable: str,
    suffix: str,
) -> None:
    physical_root = tmp_path / "physical-root"
    physical_root.mkdir()
    alias = tmp_path / "configured-root"
    try:
        alias.symlink_to(physical_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    _configure_root(
        monkeypatch,
        history_module,
        platform=platform,
        variable=variable,
        value=alias,
    )

    resolved = history_module._default_selection_history_path()
    expected = (physical_root / suffix / "executions.jsonl").resolve(strict=False)
    assert resolved == expected
    assert not resolved.exists()


@pytest.mark.parametrize(
    ("platform", "variable"),
    [
        ("linux", "POLISYOS_FOUNDRY_STATE_HOME"),
        ("linux", "XDG_STATE_HOME"),
        ("win32", "LOCALAPPDATA"),
    ],
)
def test_all_configured_roots_reject_symlink_cycles(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    variable: str,
) -> None:
    first = tmp_path / "cycle-first"
    second = tmp_path / "cycle-second"
    try:
        first.symlink_to(second, target_is_directory=True)
        second.symlink_to(first, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    _configure_root(
        monkeypatch,
        history_module,
        platform=platform,
        variable=variable,
        value=first,
    )

    with pytest.raises(ValueError, match="physically resolvable"):
        history_module._default_selection_history_path()


@pytest.mark.parametrize(
    ("platform", "variable", "value"),
    [
        ("linux", "POLISYOS_FOUNDRY_STATE_HOME", ""),
        ("linux", "POLISYOS_FOUNDRY_STATE_HOME", "relative-root"),
        ("linux", "XDG_STATE_HOME", ""),
        ("linux", "XDG_STATE_HOME", "relative-root"),
        ("win32", "LOCALAPPDATA", ""),
        ("win32", "LOCALAPPDATA", "relative-root"),
    ],
)
def test_all_configured_roots_reject_empty_and_relative_values(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    variable: str,
    value: str,
) -> None:
    _configure_root(
        monkeypatch,
        history_module,
        platform=platform,
        variable=variable,
        value=value,
    )

    with pytest.raises(ValueError, match="absolute path"):
        history_module._default_selection_history_path()


def test_configured_root_rejects_nul_and_expanduser_failure(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="NUL"):
        history_module._resolve_configured_state_path(
            "/tmp/invalid\x00state",
            setting="test root",
        )

    original_expanduser = Path.expanduser

    def _expanduser(path: Path) -> Path:
        if str(path) == "~__codex_unexpandable_probe__":
            raise RuntimeError("no such user")
        return original_expanduser(path)

    monkeypatch.setattr(Path, "expanduser", _expanduser)
    with pytest.raises(ValueError, match="could not be expanded"):
        history_module._resolve_configured_state_path(
            "~__codex_unexpandable_probe__",
            setting="test root",
        )


def test_invalid_missing_tail_ancestor_refuses_instead_of_falling_back(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_ancestor = tmp_path / "regular-file"
    file_ancestor.write_text("not a directory", encoding="utf-8")
    _configure_root(
        monkeypatch,
        history_module,
        platform="linux",
        variable="POLISYOS_FOUNDRY_STATE_HOME",
        value=file_ancestor / "child",
    )

    with pytest.raises(ValueError, match="physically resolvable"):
        history_module._default_selection_history_path()


def test_platform_defaults_and_windows_missing_profile_refusal(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    _clear_state_env(monkeypatch)

    monkeypatch.setattr(history_module.sys, "platform", "darwin")
    mac_path = history_module._default_selection_history_path()
    assert mac_path == (
        home / "Library/Application Support/PolicyOS/foundry/selection_history/executions.jsonl"
    ).resolve(strict=False)

    monkeypatch.setattr(history_module.sys, "platform", "linux")
    linux_path = history_module._default_selection_history_path()
    assert linux_path == (
        home / ".local/state/polisyos/foundry/selection_history/executions.jsonl"
    ).resolve(strict=False)

    monkeypatch.setattr(history_module.sys, "platform", "win32")
    with pytest.raises(RuntimeError, match="LOCALAPPDATA"):
        history_module._default_selection_history_path()


def test_explicit_state_home_override_precedes_platform_profile(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "operator-selected-state"
    monkeypatch.setattr(history_module.sys, "platform", "linux")
    monkeypatch.setenv("POLISYOS_FOUNDRY_STATE_HOME", str(explicit))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "other-xdg"))

    assert history_module._default_selection_history_path() == (
        explicit / "foundry/selection_history/executions.jsonl"
    ).resolve(strict=False)


def test_custom_persist_path_remains_explicit_store_destination(tmp_path: Path) -> None:
    custom_path = tmp_path / "operator-selected" / "history.jsonl"
    expected = _record(success=False, fingerprint="custom-path-record")
    store = SelectionHistoryStore(persist_path=custom_path, auto_persist=True)
    store.record(expected)

    restored = SelectionHistoryStore(persist_path=custom_path)
    assert restored.import_jsonl() == 1
    assert restored.all_records() == [expected]
    assert store.persist_path == custom_path


def test_installed_origin_does_not_redirect_global_history_into_package_root(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "venv/lib/python3.14/site-packages"
    module_file = package_root / "polisyos/foundry/methods/selection/history.py"
    old_default = (
        package_root / "_build/benchmark-results/foundry/selection_history/executions.jsonl"
    )
    state_home = tmp_path / "user-state"
    monkeypatch.setattr(history_module, "__file__", str(module_file))
    monkeypatch.setattr(history_module, "_DEFAULT_HISTORY_PATH", old_default, raising=False)
    monkeypatch.setattr(history_module.sys, "platform", "linux")
    monkeypatch.delenv("POLISYOS_FOUNDRY_STATE_HOME", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))

    store = history_module.get_global_selection_history()
    store.record(_record(success=True, fingerprint="installed-origin"))

    assert store.persist_path == (
        state_home.resolve() / "polisyos/foundry/selection_history/executions.jsonl"
    )
    assert store.persist_path.is_file()
    assert not store.persist_path.is_relative_to(package_root)
    assert not old_default.exists()


def test_legacy_history_requires_explicit_lossless_adoption(
    history_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "checkout/policy-engine/src"
    legacy_path = source_root / (
        "_build/benchmark-results/foundry/selection_history/executions.jsonl"
    )
    rows = (
        _record(success=True, fingerprint="legacy-success"),
        _record(success=False, fingerprint="legacy-failure"),
    )
    legacy_bytes = "".join(row.model_dump_json() + chr(10) for row in rows).encode()
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_bytes(legacy_bytes)
    legacy_sha256 = hashlib.sha256(legacy_bytes).hexdigest()

    monkeypatch.setattr(history_module, "__file__", str(source_root / "polisyos/history.py"))
    monkeypatch.setattr(history_module, "_DEFAULT_HISTORY_PATH", legacy_path, raising=False)
    monkeypatch.setattr(history_module.sys, "platform", "linux")
    monkeypatch.delenv("POLISYOS_FOUNDRY_STATE_HOME", raising=False)
    state_home = tmp_path / "user-state"
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))

    store = history_module.get_global_selection_history()
    new_path = state_home.resolve() / "polisyos/foundry/selection_history/executions.jsonl"
    assert store.persist_path == new_path
    assert len(store) == 0
    assert not new_path.exists()
    assert hashlib.sha256(legacy_path.read_bytes()).hexdigest() == legacy_sha256

    assert store.import_jsonl(path=legacy_path) == 2
    assert store.export_jsonl() == new_path
    restored = SelectionHistoryStore(persist_path=new_path)
    assert restored.import_jsonl() == 2
    restored_rows = {row.query_fingerprint: row for row in restored.all_records()}
    assert set(restored_rows) == {"legacy-success", "legacy-failure"}
    assert restored_rows["legacy-success"].success is True
    assert restored_rows["legacy-failure"].success is False
    assert restored_rows["legacy-failure"].failure_type == "fixture_failure"
    assert restored_rows["legacy-failure"].selection_propensity == pytest.approx(0.75)
    assert hashlib.sha256(legacy_path.read_bytes()).hexdigest() == legacy_sha256
