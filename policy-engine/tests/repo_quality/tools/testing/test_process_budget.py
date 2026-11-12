"""Real-child tests for the local process resource guard."""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

import psutil
import pytest

from tools.quality.testing import process_budget
from tools.quality.testing.process_budget import run_command


def _run(
    tmp_path: Path,
    command: list[str],
    *,
    wall_seconds: float = 5,
    max_rss_bytes: int = 512 * 1024 * 1024,
    disk_floor_bytes: int = 1,
    sample_interval_seconds: float = 0.05,
) -> dict[str, object]:
    return run_command(
        command,
        cwd=tmp_path,
        output_dir=tmp_path / "run-output",
        max_rss_bytes=max_rss_bytes,
        wall_seconds=wall_seconds,
        disk_floor_bytes=disk_floor_bytes,
        sample_interval_seconds=sample_interval_seconds,
    )


def test_process_budget_captures_combined_output_and_success(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        [sys.executable, "-u", "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
    )

    assert result["status"] == "PASS"
    assert result["actual_exit_code"] == 0
    assert result["primary_reason"] is None
    assert result["sigchld_disposition"] == "SIG_DFL"
    assert result["waitid_wnowait_available"] is True
    command_log = Path(str(result["command_log"]))
    assert command_log.read_text(encoding="utf-8").splitlines() == ["out", "err"]
    receipt = json.loads((tmp_path / "run-output" / "result.json").read_text(encoding="utf-8"))
    assert receipt["command"] == result["command"]


def test_process_budget_catches_child_after_stale_empty_census_and_cleans_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child_ready = tmp_path / "child-ready"
    root_identity = tmp_path / "root-identity"
    child_code = (
        "import os,signal,time; "
        "signal.signal(signal.SIGINT, signal.SIG_IGN); "
        f"open({str(child_ready)!r}, 'w').write(f'{{os.getpid()}} {{os.getpgrp()}} {{os.getsid(0)}}'); "
        "time.sleep(30)"
    )
    wait_loop = (
        f"while not os.path.exists({str(child_ready)!r}) and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)"
    )
    root_code = (
        "import os,subprocess,sys,time; "
        f"open({str(root_identity)!r}, 'w').write(f'{{os.getpid()}} {{os.getpgrp()}} {{os.getsid(0)}}'); "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        "deadline=time.monotonic()+5; "
        f"exec({wait_loop!r}); "
        "sys.exit(0)"
    )
    actual_observe = process_budget._observe_owned_group
    observations = 0
    child_seen_after_stale_empty = False
    observation_details: list[tuple[frozenset[int] | None, int | None]] = []
    signals: list[signal.Signals] = []
    term_observed_held_root_and_live_child: list[bool] = []

    def observe_after_one_stale_empty(
        root_pid: int, pgid: int, session_id: int
    ) -> process_budget._GroupObservation:
        nonlocal observations, child_seen_after_stale_empty
        observations += 1
        if observations == 1:
            return process_budget._GroupObservation(frozenset(), 0, None)
        current = actual_observe(root_pid, pgid, session_id)
        if child_ready.exists() and current.live_pids is not None:
            child_pid = int(child_ready.read_text(encoding="utf-8").split()[0])
            child_seen_after_stale_empty = (
                child_seen_after_stale_empty or child_pid in current.live_pids
            )
            observation_details.append((current.live_pids, child_pid))
        return current

    actual_signal = process_budget._signal_owned_group

    def signal_spy(
        process_handle: subprocess.Popen[bytes],
        pgid: int,
        session_id: int,
        sig: signal.Signals,
    ) -> bool:
        signals.append(sig)
        if sig == signal.SIGTERM:
            child_pid = int(child_ready.read_text(encoding="utf-8").split()[0])
            child_live = (
                psutil.pid_exists(child_pid)
                and psutil.Process(child_pid).status() != psutil.STATUS_ZOMBIE
            )
            term_observed_held_root_and_live_child.append(
                process_budget._peek_child_exit(process_handle.pid) is not None
                and process_handle.returncode is None
                and child_live
            )
        return actual_signal(process_handle, pgid, session_id, sig)

    monkeypatch.setattr(process_budget, "_observe_owned_group", observe_after_one_stale_empty)
    monkeypatch.setattr(process_budget, "_signal_owned_group", signal_spy)
    result = _run(tmp_path, [sys.executable, "-c", root_code], wall_seconds=10)

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "descendants_outlived_command_root"
    assert result["actual_exit_code"] == 0
    assert child_seen_after_stale_empty is True, observation_details
    assert signals == [signal.SIGINT, signal.SIGTERM]
    assert term_observed_held_root_and_live_child == [True]
    assert result["process_group_quiescence_observed"] is True
    root_pid, root_pgid, root_session = map(int, root_identity.read_text().split())
    child_pid, child_pgid, child_session = map(int, child_ready.read_text().split())
    assert root_pid == root_pgid == root_session
    assert child_pgid == root_pgid and child_session == root_session
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and psutil.pid_exists(child_pid):
        try:
            if psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        time.sleep(0.05)
    if psutil.pid_exists(child_pid):
        assert psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE


def test_process_budget_preserves_child_failure(tmp_path: Path) -> None:
    result = _run(tmp_path, [sys.executable, "-c", "raise SystemExit(17)"])

    assert result["status"] == "COMMAND_FAIL"
    assert result["actual_exit_code"] == 17
    assert result["primary_reason"] is None
    assert result["sigchld_disposition"] == "SIG_DFL"
    assert result["waitid_wnowait_available"] is True


@pytest.mark.parametrize("exit_code", [0, 17])
@pytest.mark.parametrize("sample_exception", [psutil.NoSuchProcess, psutil.ZombieProcess])
def test_process_budget_counts_wnowait_confirmed_root_exit_during_rss_sample_as_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    sample_exception: type[psutil.NoSuchProcess],
) -> None:
    real_peek = process_budget._peek_child_exit

    def root_exits_during_sample(root_pid: int) -> process_budget._Sample:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if real_peek(root_pid) is not None:
                raise process_budget._RssUnavailableError(
                    "root_rss_not_observed",
                    operation="memory_info",
                    pid=root_pid,
                    exception_type=sample_exception.__name__,
                )
            time.sleep(0.001)
        raise AssertionError("test child did not exit during root RSS sampling")

    monkeypatch.setattr(process_budget, "_sample_process_tree", root_exits_during_sample)
    result = _run(
        tmp_path,
        [sys.executable, "-c", f"raise SystemExit({exit_code})"],
        sample_interval_seconds=0.01,
    )

    expected_status = "PASS" if exit_code == 0 else "COMMAND_FAIL"
    assert result["status"] == expected_status
    assert result["primary_reason"] is None
    assert result["actual_exit_code"] == exit_code
    assert result["rss_measurement_failure"] is None
    assert result["rss_raced_process_count"] == 1
    assert result["process_group_quiescence_observed"] is True


def test_process_budget_keeps_unconfirmed_root_rss_disappearance_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_pid: list[int] = []

    def unconfirmed_sample(root_process_id: int) -> process_budget._Sample:
        root_pid.append(root_process_id)
        raise process_budget._RssUnavailableError(
            "root_rss_not_observed",
            operation="memory_info",
            pid=root_process_id,
            exception_type="NoSuchProcess",
        )

    monkeypatch.setattr(process_budget, "_sample_process_tree", unconfirmed_sample)
    result = _run(tmp_path, [sys.executable, "-c", "import time; time.sleep(30)"])

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "rss_measurement_unavailable"
    assert result["rss_measurement_failure"] == {
        "reason": "root_rss_not_observed",
        "operation": "memory_info",
        "pid": root_pid[0],
        "exception_type": "NoSuchProcess",
    }
    assert result["actual_exit_code"] is not None
    assert result["process_group_quiescence_observed"] is True


def test_process_budget_keeps_unavailable_wait_status_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root_pid: list[int] = []
    peek_calls = 0

    def foreign_reap_sample(root_process_id: int) -> process_budget._Sample:
        assert root_process_id == root_pid[0]
        raise process_budget._RssUnavailableError(
            "root_rss_not_observed",
            operation="memory_info",
            pid=root_process_id,
            exception_type="ZombieProcess",
        )

    def unavailable_after_initial_peek(pid: int) -> object | None:
        nonlocal peek_calls
        if not root_pid:
            root_pid.append(pid)
        assert pid == root_pid[0]
        peek_calls += 1
        if peek_calls == 1:
            return None
        raise ChildProcessError("simulated foreign waitpid")

    monkeypatch.setattr(process_budget, "_sample_process_tree", foreign_reap_sample)
    monkeypatch.setattr(process_budget, "_peek_child_exit", unavailable_after_initial_peek)
    result = _run(
        tmp_path,
        [sys.executable, "-c", "import time; time.sleep(0.1); raise SystemExit(17)"],
    )

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "process_exit_measurement_unavailable"
    assert result["rss_measurement_failure"]["exception_type"] == "ZombieProcess"
    assert result["actual_exit_code"] == 17


def test_process_budget_aborts_when_sampled_rss_exceeds_cap(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        [
            sys.executable,
            "-c",
            "import time; memory=bytearray(96*1024*1024); time.sleep(30)",
        ],
        max_rss_bytes=64 * 1024 * 1024,
        wall_seconds=10,
    )

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "rss_cap_observed"
    assert int(result["peak_sampled_process_tree_rss_bytes"] or 0) > 64 * 1024 * 1024
    assert result["actual_exit_code"] is not None


def test_process_budget_aborts_at_wall_limit_and_stops_grandchild_group(tmp_path: Path) -> None:
    grandchild_pid_file = tmp_path / "grandchild.pid"
    child = (
        "import os,time; "
        "memory=bytearray(64*1024*1024); "
        f"open({str(grandchild_pid_file)!r}, 'w').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    root = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "time.sleep(30)"
    )
    started = time.monotonic()
    result = _run(tmp_path, [sys.executable, "-c", root], wall_seconds=1.5)

    assert time.monotonic() - started < 8
    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "wall_time_cap"
    assert result["rss_sample_count"] > 0
    assert int(result["peak_sampled_process_tree_rss_bytes"] or 0) > 48 * 1024 * 1024
    assert result["process_group_quiescence_observed"] is True
    assert grandchild_pid_file.exists()
    grandchild_pid = int(grandchild_pid_file.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and psutil.pid_exists(grandchild_pid):
        try:
            if psutil.Process(grandchild_pid).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        time.sleep(0.05)
    if psutil.pid_exists(grandchild_pid):
        assert psutil.Process(grandchild_pid).status() == psutil.STATUS_ZOMBIE


def test_process_budget_holds_exited_root_until_ignoring_child_is_signaled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_file = tmp_path / "child-ready"
    root_identity_file = tmp_path / "root-identity"
    child = (
        "import os,signal,time; "
        "signal.signal(signal.SIGINT, signal.SIG_IGN); "
        f"open({str(ready_file)!r}, 'w').write(f'{{os.getpid()}} {{os.getpgrp()}} {{os.getsid(0)}}'); "
        "time.sleep(30)"
    )
    wait_loop = (
        f"while not os.path.exists({str(ready_file)!r}) and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)"
    )
    root = (
        "import os,signal,subprocess,sys,time; "
        "signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(0)); "
        f"open({str(root_identity_file)!r}, 'w').write(f'{{os.getpid()}} {{os.getpgrp()}} {{os.getsid(0)}}'); "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "deadline=time.monotonic()+5; "
        f"exec({wait_loop!r}); "
        "time.sleep(30)"
    )
    original_signal = process_budget._signal_owned_group
    signals: list[signal.Signals] = []
    term_observed_held_exited_root: list[bool] = []

    def signal_spy(
        process_handle: subprocess.Popen[bytes],
        pgid: int,
        session_id: int,
        sig: signal.Signals,
    ) -> bool:
        signals.append(sig)
        if sig == signal.SIGTERM:
            exit_observed = process_budget._peek_child_exit(process_handle.pid) is not None
            identity_still_held = process_handle.returncode is None
            term_observed_held_exited_root.append(exit_observed and identity_still_held)
        return original_signal(process_handle, pgid, session_id, sig)

    monkeypatch.setattr(process_budget, "_signal_owned_group", signal_spy)
    result = _run(tmp_path, [sys.executable, "-c", root], wall_seconds=2)

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "wall_time_cap"
    assert signals == [signal.SIGINT, signal.SIGTERM]
    assert term_observed_held_exited_root == [True]
    assert result["process_group_quiescence_observed"] is True
    root_pid, root_pgid, root_session = map(int, root_identity_file.read_text().split())
    child_pid, child_pgid, child_session = map(int, ready_file.read_text().split())
    assert root_pid == root_pgid == root_session
    assert child_pgid == root_pgid and child_session == root_session
    assert child_pid != root_pid


def test_process_budget_rechecks_exit_before_signaling_held_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    grandchild_pid_file = tmp_path / "grandchild.pid"
    grandchild_command = "import time; time.sleep(30)"
    root_command = (
        "import subprocess,sys,time; "
        f"child=subprocess.Popen([sys.executable, '-c', {grandchild_command!r}]); "
        f"open({str(grandchild_pid_file)!r}, 'w').write(str(child.pid)); "
        "time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", root_command],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 2
    while not grandchild_pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert grandchild_pid_file.exists()
    grandchild_pid = int(grandchild_pid_file.read_text(encoding="utf-8"))
    pgid = process_budget.os.getpgid(process.pid)
    session_id = process_budget.os.getsid(process.pid)
    assert pgid == session_id == process.pid
    real_peek = process_budget._peek_child_exit
    real_getpgid = process_budget.os.getpgid
    real_killpg = process_budget.os.killpg
    peek_calls = 0
    group_signals: list[tuple[int, signal.Signals]] = []

    def exit_between_peek_and_group_lookup(pid: int) -> int:
        if pid != process.pid:
            return real_getpgid(pid)
        process_budget.os.kill(pid, signal.SIGKILL)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if real_peek(pid) is not None:
                break
            time.sleep(0.01)
        raise ProcessLookupError(pid, "simulated Darwin zombie lookup race")

    def peek_with_exit_race(pid: int):
        nonlocal peek_calls
        peek_calls += 1
        if peek_calls == 1:
            return None
        return real_peek(pid)

    def record_group_signal(pgid_arg: int, sig: signal.Signals) -> None:
        group_signals.append((pgid_arg, sig))
        with suppress(ProcessLookupError):
            real_killpg(pgid_arg, sig)

    monkeypatch.setattr(process_budget, "_peek_child_exit", peek_with_exit_race)
    monkeypatch.setattr(process_budget.os, "getpgid", exit_between_peek_and_group_lookup)
    monkeypatch.setattr(process_budget.os, "killpg", record_group_signal)
    try:
        process_budget._signal_owned_group(process, pgid, session_id, signal.SIGTERM)
        assert peek_calls >= 2
        assert group_signals == [(pgid, signal.SIGTERM)]
        assert process.returncode is None
    finally:
        process.wait()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and psutil.pid_exists(grandchild_pid):
        try:
            if psutil.Process(grandchild_pid).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        time.sleep(0.05)
    if psutil.pid_exists(grandchild_pid):
        assert psutil.Process(grandchild_pid).status() == psutil.STATUS_ZOMBIE


def test_process_budget_rejects_below_floor_before_command_start(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist"
    result = _run(
        tmp_path,
        [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
        disk_floor_bytes=10**30,
    )

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "disk_floor_at_admission"
    assert result["actual_exit_code"] is None
    assert not marker.exists()


def test_process_budget_refuses_to_run_without_waitid_wnowait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "must-not-run"
    monkeypatch.setattr(process_budget.os, "waitid", None)
    result = _run(tmp_path, [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"])

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "waitid_wnowait_unavailable"
    assert result["waitid_wnowait_available"] is False
    assert not marker.exists()


def test_process_budget_refuses_sigchld_ignore_in_isolated_runner(tmp_path: Path) -> None:
    runner = Path(__file__).resolve().parents[4] / "tools/quality/testing/process_budget.py"
    output_dir = tmp_path / "sigchld-ignore-output"
    marker = tmp_path / "must-not-run-under-sigchld-ignore"
    command = [
        str(runner),
        "--output-dir",
        str(output_dir),
        "--cwd",
        str(tmp_path),
        "--max-rss-bytes",
        str(512 * 1024 * 1024),
        "--wall-seconds",
        "5",
        "--disk-floor-bytes",
        "1",
        "--",
        sys.executable,
        "-c",
        f"open({str(marker)!r}, 'w').write('ran')",
    ]
    isolated_runner = (
        "import runpy, signal, sys; "
        "signal.signal(signal.SIGCHLD, signal.SIG_IGN); "
        f"sys.argv = {command!r}; "
        "runpy.run_path(sys.argv[0], run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", isolated_runner],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 3, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "waitid_wnowait_unavailable"
    assert result["actual_exit_code"] is None
    assert result["waitid_wnowait_available"] is False
    assert result["sigchld_disposition"] == "SIG_IGN"
    assert not marker.exists()
    persisted = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    assert persisted == result


def test_process_budget_refuses_custom_sigchld_reaper_in_isolated_runner(tmp_path: Path) -> None:
    runner = Path(__file__).resolve().parents[4] / "tools/quality/testing/process_budget.py"
    output_dir = tmp_path / "sigchld-handler-output"
    marker = tmp_path / "must-not-run-under-sigchld-handler"
    command = [
        str(runner),
        "--output-dir",
        str(output_dir),
        "--cwd",
        str(tmp_path),
        "--max-rss-bytes",
        str(512 * 1024 * 1024),
        "--wall-seconds",
        "5",
        "--disk-floor-bytes",
        "1",
        "--",
        sys.executable,
        "-c",
        f"open({str(marker)!r}, 'w').write('ran')",
    ]
    isolated_runner = (
        "import os, runpy, signal, sys; "
        "def_reaper = 'def reap(signum, frame):\\n'"
        "'    try:\\n        os.waitpid(-1, os.WNOHANG)\\n'"
        "'    except ChildProcessError:\\n        pass\\n'; "
        "exec(def_reaper); signal.signal(signal.SIGCHLD, reap); "
        f"sys.argv = {command!r}; "
        "runpy.run_path(sys.argv[0], run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", isolated_runner],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 3, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "waitid_wnowait_unavailable"
    assert result["actual_exit_code"] is None
    assert result["waitid_wnowait_available"] is False
    assert result["sigchld_disposition"] == "custom_handler"
    assert not marker.exists()
    persisted = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
    assert persisted == result


def test_process_budget_records_rss_measurement_failure_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_root_pid: list[int] = []

    class DeniedRoot:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def children(self, *, recursive: bool) -> list[object]:
            assert recursive is True
            raise psutil.AccessDenied(pid=self.pid)

    def denied_process(pid: int) -> DeniedRoot:
        observed_root_pid.append(pid)
        return DeniedRoot(pid)

    def observe_root_until_exit(
        root_pid: int, pgid: int, session_id: int
    ) -> process_budget._GroupObservation:
        del pgid, session_id
        live_pids = (
            frozenset({root_pid})
            if process_budget._peek_child_exit(root_pid) is None
            else frozenset()
        )
        return process_budget._GroupObservation(live_pids, 1, None)

    monkeypatch.setattr(process_budget.psutil, "Process", denied_process)
    monkeypatch.setattr(process_budget, "_observe_owned_group", observe_root_until_exit)
    result = _run(tmp_path, [sys.executable, "-c", "import time; time.sleep(30)"])

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "rss_measurement_unavailable"
    assert result["rss_measurement_failure"] == {
        "reason": "process_access_denied",
        "operation": "recursive_children",
        "pid": observed_root_pid[0],
        "exception_type": "AccessDenied",
    }
    assert result["actual_exit_code"] is not None
    persisted = json.loads((tmp_path / "run-output" / "result.json").read_text(encoding="utf-8"))
    assert persisted["rss_measurement_failure"] == result["rss_measurement_failure"]


def test_process_budget_records_partial_census_when_group_signal_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_root_pids: list[int] = []

    def sample_process_tree(root_pid: int) -> process_budget._Sample:
        return process_budget._Sample(0, (root_pid,), ())

    def observe_owned_root(
        root_pid: int, pgid: int, session_id: int
    ) -> process_budget._GroupObservation:
        del pgid, session_id
        observed_root_pids.append(root_pid)
        return process_budget._GroupObservation(frozenset({root_pid}), 7, None)

    def fail_group_signal(
        process_handle: subprocess.Popen[bytes],
        pgid: int,
        session_id: int,
        sig: signal.Signals,
    ) -> bool:
        del process_handle, pgid, session_id, sig
        raise RuntimeError("injected failure containing fake-secret")

    monkeypatch.setattr(process_budget, "_sample_process_tree", sample_process_tree)
    monkeypatch.setattr(process_budget, "_observe_owned_group", observe_owned_root)
    monkeypatch.setattr(process_budget, "_signal_owned_group", fail_group_signal)
    result = _run(
        tmp_path,
        [sys.executable, "-c", "import time; time.sleep(30)"],
        wall_seconds=0.15,
        sample_interval_seconds=0.02,
    )

    assert result["status"] == "RESOURCE_ABORT"
    assert result["primary_reason"] == "wall_time_cap"
    assert result["cleanup_runtime_error"] == {
        "type": "RuntimeError",
        "operation": "signal_owned_group",
        "pid": observed_root_pids[0],
        "signal": "SIGINT",
    }
    assert result["process_group_scan_count"] == 1
    assert result["process_table_pids_scanned"] == 7
    assert result["process_group_quiescence_observed"] is False
    assert result["actual_exit_code"] is not None
    assert "fake-secret" not in json.dumps(result)


def test_process_budget_cli_runs_explicit_command_after_separator(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[4] / "tools/quality/testing/process_budget.py"
    output_dir = tmp_path / "cli-output"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--output-dir",
            str(output_dir),
            "--cwd",
            str(tmp_path),
            "--max-rss-bytes",
            str(512 * 1024 * 1024),
            "--wall-seconds",
            "5",
            "--disk-floor-bytes",
            "1",
            "--",
            sys.executable,
            "-c",
            "print('cli-ok')",
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "PASS"
    assert (output_dir / "command.log").read_text(encoding="utf-8").strip() == "cli-ok"
