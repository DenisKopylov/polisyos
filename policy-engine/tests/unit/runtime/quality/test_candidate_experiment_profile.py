"""Best-effort first-stage cProfile preserves the exercised call outcome."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests._helpers.candidate_experiment_served_execution import (
    _run_current_action_with_profile_best_effort,
)


def test_current_action_profile_is_noop_without_path(tmp_path: Path) -> None:
    result = object()

    assert (
        _run_current_action_with_profile_best_effort(
            lambda: result,
            profile_path=None,
        )
        is result
    )
    assert tuple(tmp_path.iterdir()) == ()


def test_current_action_profile_returns_same_object_and_writes_compact_outputs(
    tmp_path: Path,
) -> None:
    result = object()
    profile_path = tmp_path / "profile"
    observer_profiles: list[object] = []

    def operation() -> object:
        observer_profiles.append(sys.getprofile())
        return result

    assert (
        _run_current_action_with_profile_best_effort(
            operation,
            profile_path=profile_path,
        )
        is result
    )
    observer_profiles.append(sys.getprofile())

    assert observer_profiles == [None, None]
    assert {path.name for path in profile_path.iterdir()} == {
        "current-action.pstats",
        "current-action-top25.txt",
        "status.json",
    }
    status = json.loads((profile_path / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "PROFILED"
    assert status["outcome"] == "returned"
    assert status["total_calls"] > 0
    assert (profile_path / "current-action-top25.txt").stat().st_size < 8192


def test_current_action_profile_preserves_the_original_exception_object(
    tmp_path: Path,
) -> None:
    expected = RuntimeError("sentinel failure")

    def operation() -> object:
        raise expected

    with pytest.raises(RuntimeError) as captured:
        _run_current_action_with_profile_best_effort(
            operation,
            profile_path=tmp_path / "profile",
        )

    assert captured.value is expected
    status = json.loads((tmp_path / "profile/status.json").read_text(encoding="utf-8"))
    assert status["status"] == "PROFILED"
    assert status["outcome"] == "raised"
    assert status["exception_type"] == "RuntimeError"
    assert sys.getprofile() is None


def test_current_action_profile_skips_without_replacing_existing_profiler(
    tmp_path: Path,
) -> None:
    previous = sys.getprofile()
    calls: list[object] = []

    def existing_profiler(frame, event, arg) -> None:
        return None

    try:
        sys.setprofile(existing_profiler)
        result = object()
        assert (
            _run_current_action_with_profile_best_effort(
                lambda: result,
                profile_path=tmp_path / "profile",
            )
            is result
        )
        assert sys.getprofile() is existing_profiler
        calls.append(sys.getprofile())
    finally:
        sys.setprofile(previous)

    assert calls == [existing_profiler]
    status = json.loads((tmp_path / "profile/status.json").read_text(encoding="utf-8"))
    assert status["status"] == "SKIP"
    assert status["reason"] == "existing_profiler_active"
    assert {path.name for path in (tmp_path / "profile").iterdir()} == {"status.json"}


@pytest.mark.parametrize("raises", [False, True])
def test_current_action_profile_write_failure_does_not_mask_operation(
    tmp_path: Path,
    raises: bool,
) -> None:
    profile_path = tmp_path / "not-a-directory"
    profile_path.write_text("block directory creation", encoding="utf-8")
    result = object()
    expected = RuntimeError("original failure")

    def operation() -> object:
        if raises:
            raise expected
        return result

    if raises:
        with pytest.raises(RuntimeError) as captured:
            _run_current_action_with_profile_best_effort(
                operation,
                profile_path=profile_path,
            )
        assert captured.value is expected
    else:
        assert (
            _run_current_action_with_profile_best_effort(
                operation,
                profile_path=profile_path,
            )
            is result
        )

    assert sys.getprofile() is None
