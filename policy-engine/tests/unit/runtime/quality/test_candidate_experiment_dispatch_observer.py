from __future__ import annotations

import pytest

from tests._helpers.candidate_experiment_served_execution import (
    _observe_candidate_experiment_dispatch,
)


class _CodedDispatchError(RuntimeError):
    code = "candidate_experiment_dispatch_probe"


def test_dispatch_observer_records_bounded_cause_and_reraises_same_exception() -> None:
    def make_root_cause() -> ValueError:
        raise ValueError("source proof failed")

    try:
        make_root_cause()
    except ValueError as caught:
        root_cause = caught
    error = _CodedDispatchError("evaluation dispatch failed")
    error.__cause__ = root_cause
    failures = []
    expected_marker = object()

    def dispatch(*, marker: object) -> object:
        assert marker is expected_marker
        raise error

    observed = _observe_candidate_experiment_dispatch(dispatch, failures)
    with pytest.raises(_CodedDispatchError) as raised:
        observed(marker=expected_marker)

    assert raised.value is error
    assert len(failures) == 1
    failure = failures[0]
    assert [node.exception_type for node in failure.chain] == [
        f"{_CodedDispatchError.__module__}._CodedDispatchError",
        "builtins.ValueError",
    ]
    assert failure.chain[0].code == _CodedDispatchError.code
    assert failure.chain[0].message == "evaluation dispatch failed"
    assert failure.chain[1].message == "source proof failed"
    assert 0 < len(failure.chain[0].traceback_tail) <= 8
    assert any(frame.function == "dispatch" for frame in failure.chain[0].traceback_tail)
    assert 0 < len(failure.chain[1].traceback_tail) <= 8
    assert any(frame.function == "make_root_cause" for frame in failure.chain[1].traceback_tail)


def test_dispatch_observer_bounds_exception_messages_and_traceback_tail() -> None:
    error = RuntimeError("x" * 700)
    failures = []

    def dispatch() -> None:
        raise error

    observed = _observe_candidate_experiment_dispatch(dispatch, failures)
    with pytest.raises(RuntimeError) as raised:
        observed()

    assert raised.value is error
    assert len(failures[0].chain[0].message) == 512
    assert len(failures[0].chain[0].traceback_tail) <= 8


def test_dispatch_observer_diagnostic_failure_does_not_replace_original_error() -> None:
    class UninspectableCauseError(RuntimeError):
        def __getattribute__(self, name: str) -> object:
            if name == "__cause__":
                raise AssertionError("cause access failed")
            return super().__getattribute__(name)

    error = UninspectableCauseError("original dispatch error")
    failures = []

    def dispatch() -> None:
        raise error

    observed = _observe_candidate_experiment_dispatch(dispatch, failures)
    with pytest.raises(UninspectableCauseError) as raised:
        observed()

    assert raised.value is error
    assert failures == []
