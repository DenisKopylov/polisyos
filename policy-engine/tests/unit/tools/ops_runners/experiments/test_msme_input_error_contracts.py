from __future__ import annotations

import builtins
import importlib
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit


def _load_experiment_module(
    monkeypatch: pytest.MonkeyPatch, module_name: str
) -> ModuleType:
    experiment_dir = (
        Path(__file__).resolve().parents[5] / "tools" / "ops_runners" / "experiments"
    )
    monkeypatch.syspath_prepend(str(experiment_dir))
    return importlib.import_module(module_name)


def test_deadline_jsonl_reader_rejects_malformed_present_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Malformed supplied JSONL must not become an empty evidence sample."""
    runner = _load_experiment_module(monkeypatch, "run_msme_deadline_suite")
    path = tmp_path / "transport.jsonl"
    path.write_text('{"work_id":"not-selected"}\n{not-json}\n', encoding="utf-8")

    with pytest.raises(ValueError) as captured:
        runner.read_jsonl_sample(
            path,
            predicate=lambda row: row.get("work_id") == "selected",
            limit=10,
        )

    assert f"{path}:2" in str(captured.value)


def test_deadline_jsonl_reader_keeps_absence_distinct_from_bad_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An absent optional file stays empty; a supplied non-object row is invalid."""
    runner = _load_experiment_module(monkeypatch, "run_msme_deadline_suite")
    assert runner.read_jsonl_sample(tmp_path / "absent.jsonl") == []

    path = tmp_path / "wrong-shape.jsonl"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        runner.read_jsonl_sample(path)


def test_deadline_jsonl_reader_rejects_invalid_utf8(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = _load_experiment_module(monkeypatch, "run_msme_deadline_suite")
    path = tmp_path / "invalid-utf8.jsonl"
    path.write_bytes(b"\xff\n")

    with pytest.raises(UnicodeDecodeError):
        runner.read_jsonl_sample(path)


def test_frontier_probe_only_degrades_for_a_missing_selected_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transitive import defect is not equivalent to an absent optional backend."""
    runner = _load_experiment_module(monkeypatch, "run_msme_final_fresg_suite_v2")
    original_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "missing_optional_backend":
            raise ModuleNotFoundError(
                "No module named 'missing_optional_backend'",
                name="missing_optional_backend",
            )
        if name == "broken_optional_backend":
            raise ModuleNotFoundError(
                "No module named 'backend_dependency'",
                name="backend_dependency",
            )
        if name == "failing_optional_backend":
            raise RuntimeError("backend initialization failed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert runner._optional_module_available("missing_optional_backend") is False
    assert runner._optional_module_available("json") is True

    with pytest.raises(ModuleNotFoundError) as captured:
        runner._optional_module_available("broken_optional_backend")
    assert captured.value.name == "backend_dependency"
    with pytest.raises(RuntimeError, match="backend initialization failed"):
        runner._optional_module_available("failing_optional_backend")
