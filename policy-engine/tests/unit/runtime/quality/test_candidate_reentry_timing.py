"""Pure synthetic checks for the optional reentry timing observer."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from tests._helpers.candidate_reentry_timing import _PROFILES, _TimingObserver

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


def _nested_wrapper() -> int:
    def nested_target() -> int:
        return 1

    return nested_target()


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


def test_generic_model_input_profile_is_finite_and_covers_replay_fanout() -> None:
    targets = _PROFILES["generic_model_input_owner"]
    labels = tuple(target.label for target in targets)

    assert len(labels) == len(set(labels))
    assert len(targets) == 23
    assert {
        "model_input.handle_job",
        "model_input.handle_model_input_job",
        "model_input.run_n5",
        "candidate_action.reentry_context",
        "candidate_action.current_context",
        "candidate_route.resolve_reentry",
        "candidate_route.experiment_action_outcomes",
        "candidate_prior.owner",
        "candidate_basis.prepare_live",
        "candidate_handoff.compose",
        "candidate_handoff.currentness_callback",
        "candidate_reentry.prepare_owner",
        "candidate_reentry.revalidate_owner",
        "foundry.prepare_input_bindings",
    }.issubset(labels)
    assert all(target.module_name.startswith("polisyos.") for target in targets)


def test_missing_profile_targets_are_a_diagnostic_not_an_observer_failure(tmp_path) -> None:
    observer = _TimingObserver(
        {},
        tmp_path / "timing.json",
        profile="generic_model_input_owner",
        resolution_failures={"candidate_prior.owner": "LookupError: owner unavailable"},
    )
    assert not observer.enable()

    snapshot = observer.snapshot()
    assert snapshot["status"] == "instrumentation_unavailable"
    assert snapshot["target_resolution"] == "unavailable"
    assert snapshot["resolution_failures"] == {
        "candidate_prior.owner": "LookupError: owner unavailable"
    }


def test_nested_target_durations_are_reported_as_inclusive_and_overlapping(tmp_path) -> None:
    nested_code = next(
        value
        for value in _nested_wrapper.__code__.co_consts
        if type(value) is type(_nested_wrapper.__code__) and value.co_name == "nested_target"
    )
    observer = _TimingObserver(
        {
            "synthetic.wrapper": _nested_wrapper.__code__,
            "synthetic.nested": nested_code,
        },
        tmp_path / "timing.json",
        profile="generic_model_input_owner",
    )
    wrapper_code = observer.codes["synthetic.wrapper"]
    nested_code = observer.codes["synthetic.nested"]
    observer._safe_start(wrapper_code)
    observer._safe_start(nested_code)
    observer._safe_return(nested_code)
    observer._safe_return(wrapper_code)

    snapshot = observer.snapshot()
    assert "inclusive" in snapshot["timing_semantics"]
    assert "must not be summed" in snapshot["timing_semantics"]
    assert snapshot["targets"]["synthetic.wrapper"]["calls"] == 1
    assert snapshot["targets"]["synthetic.nested"]["calls"] == 1


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
    codes = {
        "synthetic.return": _recursive_descend.__code__,
        "synthetic.unwind": _recursive_unwind.__code__,
    }
    observer = _TimingObserver(
        codes,
        tmp_path / "timing.json",
    )
    assert observer.enable()
    events = sys.monitoring.events
    for code in codes.values():
        assert sys.monitoring.get_local_events(4, code) == (events.PY_START | events.PY_RETURN)
    assert sys.monitoring.get_events(4) == events.PY_UNWIND

    try:
        assert _recursive_descend(2) == 2
        with pytest.raises(RuntimeError) as caught:
            _recursive_unwind(2)
        assert caught.value is _SYNTHETIC_ERROR
        snapshot = observer.snapshot()
    finally:
        observer.cleanup()

    returned = snapshot["targets"]["synthetic.return"]
    unwound = snapshot["targets"]["synthetic.unwind"]
    assert (returned["calls"], returned["returns"], returned["active_calls"]) == (3, 3, 0)
    assert (unwound["calls"], unwound["unwinds"], unwound["active_calls"]) == (3, 3, 0)
    assert snapshot["selected_global_unwind_events_seen"] == 3

    assert sys.monitoring.get_tool(4) is None
    assert sys.monitoring.get_events(4) == 0
    for code in codes.values():
        assert sys.monitoring.get_local_events(4, code) == 0
    assert observer.cleanup_status == "complete"


def test_cleanup_continues_after_owned_cleanup_error_and_reports_partial_result(
    tmp_path, monkeypatch
) -> None:
    calls: list[tuple[object, ...]] = []

    class MonitoringStub:
        events = SimpleNamespace(PY_START=1, PY_RETURN=2, PY_UNWIND=4)

        def __init__(self) -> None:
            self.owner: str | None = "e02-candidate-reentry-timing"

        def get_tool(self, tool_id: int) -> str | None:
            assert tool_id == 4
            return self.owner

        def set_local_events(self, tool_id: int, code, event_mask: int) -> None:
            calls.append(("local", tool_id, code, event_mask))
            raise RuntimeError("local clear failed")

        def set_events(self, tool_id: int, event_mask: int) -> None:
            calls.append(("global", tool_id, event_mask))

        def register_callback(self, tool_id: int, event: int, callback) -> None:
            calls.append(("callback", tool_id, event, callback))

        def free_tool_id(self, tool_id: int) -> None:
            calls.append(("free", tool_id))
            self.owner = None

    monitoring = MonitoringStub()
    monkeypatch.setattr(sys, "monitoring", monitoring, raising=False)
    code = _never_called.__code__
    observer = _TimingObserver({"synthetic.selected": code}, tmp_path / "timing.json")
    observer._owned = True
    observer._enabled_local.append(code)
    observer._callbacks = {1: lambda: None, 2: lambda: None, 4: lambda: None}

    observer.cleanup()

    assert [call[0] for call in calls] == [
        "local",
        "global",
        "callback",
        "callback",
        "callback",
        "free",
    ]
    assert observer.cleanup_status == "completed_with_errors"
    assert observer.status == "instrumentation_cleanup_failed"
    assert observer.observer_errors == 1
    assert observer.cleanup_errors == [
        "clear local events for _never_called: RuntimeError: local clear failed"
    ]
    assert not observer._owned


def test_cleanup_does_not_touch_tool_id_after_ownership_changes(tmp_path, monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []

    class MonitoringStub:
        events = SimpleNamespace(PY_START=1, PY_RETURN=2, PY_UNWIND=4)

        def get_tool(self, tool_id: int) -> str:
            assert tool_id == 4
            return "another-owner"

        def set_local_events(self, *args) -> None:
            calls.append(("local", *args))

        def set_events(self, *args) -> None:
            calls.append(("global", *args))

        def register_callback(self, *args) -> None:
            calls.append(("callback", *args))

        def free_tool_id(self, *args) -> None:
            calls.append(("free", *args))

    monkeypatch.setattr(sys, "monitoring", MonitoringStub(), raising=False)
    code = _never_called.__code__
    observer = _TimingObserver({"synthetic.selected": code}, tmp_path / "timing.json")
    observer._owned = True
    observer._enabled_local.append(code)

    observer.cleanup()

    assert calls == []
    assert observer.cleanup_status == "ownership_changed"
    assert observer.status == "instrumentation_cleanup_failed"
    assert "ownership changed" in observer.reason
    assert not observer._owned


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
