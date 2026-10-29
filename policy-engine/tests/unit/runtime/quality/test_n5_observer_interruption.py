"""Exercise the actual observer's interruption boundary without a fake N5 result."""

from __future__ import annotations

import sys

from polisyos.runtime.quality.n5_execution_basis import _ControllerExecutionObserver


def test_actual_controller_observer_records_lost_profiler_at_outer_exit() -> None:
    assert sys.getprofile() is None
    observer = _ControllerExecutionObserver()
    with observer:
        assert sys.getprofile() == observer._observe
        # Reproduce loss after the final numerical-scope check, while the outer
        # controller's result construction would still be running.
        sys.setprofile(None)
    assert sys.getprofile() is None
    assert observer.reason == "n5_execution_observer_interrupted"
    assert observer.completed is False


def test_actual_controller_observer_normal_exit_does_not_report_interruption() -> None:
    assert sys.getprofile() is None
    observer = _ControllerExecutionObserver()
    with observer:
        assert sys.getprofile() == observer._observe
    assert sys.getprofile() is None
    assert observer.reason is None
    assert observer.completed is True
