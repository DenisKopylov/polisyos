"""Pure synthetic checks for the optional reentry timing observer."""

from __future__ import annotations

import sys

import pytest

from tests._helpers.candidate_reentry_timing import _TimingObserver

_SYNTHETIC_ERROR = RuntimeError("same exception object")


def _recursive_descend(depth: int) -> int:
    return 0 if depth == 0 else 1 + _recursive_descend(depth - 1)


def _recursive_unwind(depth: int) -> None:
    if depth:
        _recursive_unwind(depth - 1)
    else:
        raise _SYNTHETIC_ERROR


def _never_called() -> None:
    return None


def _require_free_tool_id() -> None:
    monitoring = getattr(sys, "monitoring", None)
    if monitoring is None:
        pytest.skip("sys.monitoring is unavailable")
    if monitoring.get_tool(4) is not None or monitoring.get_events(4):
        pytest.skip("monitoring tool ID 4 is occupied")


def test_recursive_timing_stack_counts_without_changing_result(tmp_path) -> None:
    observer = _TimingObserver(
        {"synthetic.descend": _recursive_descend.__code__}, tmp_path / "timing.json"
    )
    for _ in range(5):
        observer._safe_start(_recursive_descend.__code__)
    assert _recursive_descend(4) == 4
    for _ in range(5):
        observer._safe_return(_recursive_descend.__code__)

    row = observer.snapshot()["targets"]["synthetic.descend"]
    assert row["calls"] == 5
    assert row["returns"] == 5
    assert row["unwinds"] == 0
    assert row["active_calls"] == 0
    assert row["inclusive_wall_ns"] > 0
    assert row["observation"] == "observed"


def test_recursive_unwind_preserves_exception_and_balances_stack(tmp_path) -> None:
    observer = _TimingObserver(
        {"synthetic.unwind": _recursive_unwind.__code__}, tmp_path / "timing.json"
    )
    for _ in range(3):
        observer._safe_start(_recursive_unwind.__code__)
    with pytest.raises(RuntimeError) as caught:
        _recursive_unwind(2)
    assert caught.value is _SYNTHETIC_ERROR
    for _ in range(3):
        observer._safe_unwind(_recursive_unwind.__code__)

    snapshot = observer.snapshot()
    row = snapshot["targets"]["synthetic.unwind"]
    assert row["calls"] == 3
    assert row["unwinds"] == 3
    assert row["returns"] == 0
    assert row["active_calls"] == 0
    assert row["inclusive_wall_ns"] > 0
    assert snapshot["selected_global_unwind_events_seen"] == 3
    assert snapshot["global_unwind_handler_wall_ns"] > 0


def test_zero_calls_are_unobserved_not_pass(tmp_path) -> None:
    observer = _TimingObserver(
        {"synthetic.never_called": _never_called.__code__}, tmp_path / "timing.json"
    )
    row = observer.snapshot()["targets"]["synthetic.never_called"]
    assert row["calls"] == 0
    assert row["observation"] == "unobserved"


def test_equal_but_distinct_code_unwind_is_filtered_by_identity(tmp_path) -> None:
    code = _recursive_unwind.__code__
    clone = code.replace()
    assert clone == code
    assert clone is not code

    observer = _TimingObserver({"synthetic.unwind": code}, tmp_path / "timing.json")
    observer._safe_start(code)
    observer._safe_unwind(clone)
    snapshot = observer.snapshot()
    row = snapshot["targets"]["synthetic.unwind"]
    assert row["calls"] == 1
    assert row["unwinds"] == 0
    assert row["active_calls"] == 1
    assert snapshot["unmatched_ends"] == 0
    assert snapshot["selected_global_unwind_events_seen"] == 0
    observer._safe_return(code)


def test_duplicate_code_identity_for_two_labels_is_rejected(tmp_path) -> None:
    code = _recursive_descend.__code__
    with pytest.raises(ValueError, match="same code object"):
        _TimingObserver({"first": code, "second": code}, tmp_path / "timing.json")


def test_enable_installs_only_selected_local_events_and_cleans_up(tmp_path) -> None:
    _require_free_tool_id()
    observer = _TimingObserver(
        {"synthetic.never_called": _never_called.__code__}, tmp_path / "timing.json"
    )
    assert observer.enable()
    events = sys.monitoring.events
    assert sys.monitoring.get_local_events(4, _never_called.__code__) == (
        events.PY_START | events.PY_RETURN
    )
    assert sys.monitoring.get_events(4) == events.PY_UNWIND
    observer.cleanup()
    assert sys.monitoring.get_tool(4) is None
    assert sys.monitoring.get_events(4) == 0
    assert sys.monitoring.get_local_events(4, _never_called.__code__) == 0


def test_occupied_tool_id_is_left_untouched(tmp_path) -> None:
    monitoring = getattr(sys, "monitoring", None)
    if monitoring is None:
        pytest.skip("sys.monitoring is unavailable")
    if monitoring.get_tool(4) is not None or monitoring.get_events(4):
        pytest.skip("monitoring tool ID 4 is occupied")

    owner = "synthetic-owner"
    calls: list[int] = []

    def marker(code, *_):
        calls.append(id(code))

    monitoring.use_tool_id(4, owner)
    monitoring.register_callback(4, monitoring.events.PY_UNWIND, marker)
    monitoring.set_events(4, monitoring.events.PY_UNWIND)
    try:
        observer = _TimingObserver(
            {"synthetic.selected": _never_called.__code__}, tmp_path / "timing.json"
        )
        assert not observer.enable()
        assert observer.status == "instrumentation_unavailable"
        observer.cleanup()
        _never_called()
        with pytest.raises(RuntimeError) as caught:
            _recursive_unwind(0)
        assert caught.value is _SYNTHETIC_ERROR
        assert calls
        assert monitoring.get_tool(4) == owner
        assert monitoring.get_events(4) == monitoring.events.PY_UNWIND
        assert monitoring.get_local_events(4, _never_called.__code__) == 0
    finally:
        monitoring.set_events(4, 0)
        monitoring.register_callback(4, monitoring.events.PY_UNWIND, None)
        monitoring.free_tool_id(4)
