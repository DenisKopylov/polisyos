"""Behavioral controls for physical-worker fixture budgets and cleanup."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests._helpers import worker_transport_wait as wait


class _Process:
    exitcode = None

    def __init__(self, alive=True, survives_kill=False):
        self.alive, self.survives_kill, self.actions = alive, survives_kill, []

    def is_alive(self):
        return self.alive

    def join(self, seconds):
        self.actions.append(("join", seconds))

    def terminate(self):
        self.actions.append(("terminate",))

    def kill(self):
        self.actions.append(("kill",))
        if not self.survives_kill:
            self.alive = False


class _Pipe:
    def __init__(self, clock, ready=999, eof=False):
        self.clock, self.ready, self.eof = clock, ready, eof
        self.message = ("result", b"exact-worker-result")

    def poll(self, seconds):
        self.clock[0] += seconds
        return self.clock[0] >= self.ready

    def recv(self):
        if self.eof:
            raise EOFError
        return self.message


def test_worker_fixture_wait_accepts_late_real_message_and_refuses_absence(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(wait, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    pipe = _Pipe(clock, ready=25.095)
    assert wait.receive_worker_message(pipe, _Process()) is pipe.message
    assert 25 <= clock[0] < wait.WORKER_OUTCOME_WAIT_SECONDS
    clock[0] = 0
    with pytest.raises(AssertionError, match="exited without"):
        wait.receive_worker_message(_Pipe(clock), _Process(alive=False))
    assert clock[0] == 0.1
    clock[0] = 0
    with pytest.raises(AssertionError, match="deadline expired"):
        wait.receive_worker_message(_Pipe(clock), _Process())
    assert 35 <= clock[0] < 35.000001
    clock[0] = 0
    with pytest.raises(AssertionError, match="closed without"):
        wait.receive_worker_message(_Pipe(clock, ready=0, eof=True), _Process(alive=False))
    pipe = _Pipe(clock, ready=0)
    assert wait.receive_worker_message(pipe, _Process(alive=False)) is pipe.message


def test_worker_fixture_cleanup_reaps_or_fails_with_bounded_escalation():
    process = _Process()
    wait.reap_worker_process(process)
    assert process.actions == [
        ("join", 10.0),
        ("terminate",),
        ("join", 5.0),
        ("kill",),
        ("join", 5.0),
    ]
    with pytest.raises(AssertionError, match="remained live"):
        wait.reap_worker_process(_Process(survives_kill=True))
