"""Run one local command under measured process-tree and disk limits.

This is a coordinator-owned resource guard for a single already-admitted job. It
does not bootstrap environments, select tests, or establish product evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

_INT_GRACE_SECONDS = 2.0
_TERM_GRACE_SECONDS = 2.0
_KILL_GRACE_SECONDS = 2.0
_RESULT_SCHEMA = "policyos.process-budget-result.v1"


@dataclass(frozen=True)
class _Sample:
    rss_bytes: int
    observed_pids: tuple[int, ...]
    raced_pids: tuple[int, ...]


class _RssUnavailableError(RuntimeError):
    """Raised when a live process tree cannot be measured completely."""

    def __init__(
        self,
        reason: str,
        *,
        operation: str,
        pid: int | None,
        exception_type: str | None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.operation = operation
        self.pid = pid
        self.exception_type = exception_type

    def to_record(self) -> dict[str, str | int | None]:
        """Return compact failure provenance without process names or payloads."""
        return {
            "reason": self.reason,
            "operation": self.operation,
            "pid": self.pid,
            "exception_type": self.exception_type,
        }


@dataclass(frozen=True)
class _GroupObservation:
    live_pids: frozenset[int] | None
    scanned_pids: int
    unavailable_reason: str | None


class _OwnedGroupCleanupError(RuntimeError):
    """Carry partial census counts when an owned-group signal is refused."""

    def __init__(
        self,
        cause: RuntimeError,
        *,
        scans: int,
        scanned_pids: int,
        unavailable_reason: str | None,
        signal_name: str,
    ) -> None:
        super().__init__("owned_process_group_signal_unavailable")
        self.cause_type = type(cause).__name__
        self.scans = scans
        self.scanned_pids = scanned_pids
        self.unavailable_reason = unavailable_reason
        self.signal_name = signal_name


def _free_bytes(path: Path) -> int:
    """Return unprivileged free bytes for ``path``'s filesystem."""
    stat = os.statvfs(path)
    return stat.f_bavail * stat.f_frsize


def _sample_process_tree(root_pid: int) -> _Sample:
    """Sum RSS for the command root and its recursively observed descendants.

    Processes that exit during enumeration are recorded as races because a
    short-lived process can fall between samples. Access-denied members make
    the measurement unavailable; they are never treated as zero bytes.
    """
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess as exc:
        raise _RssUnavailableError(
            "process_disappeared",
            operation="root_process",
            pid=getattr(exc, "pid", None) or root_pid,
            exception_type=type(exc).__name__,
        ) from exc
    except psutil.AccessDenied as exc:
        raise _RssUnavailableError(
            "process_access_denied",
            operation="root_process",
            pid=getattr(exc, "pid", None),
            exception_type=type(exc).__name__,
        ) from exc

    try:
        members = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess as exc:
        raise _RssUnavailableError(
            "process_disappeared",
            operation="recursive_children",
            pid=getattr(exc, "pid", None) or root_pid,
            exception_type=type(exc).__name__,
        ) from exc
    except psutil.AccessDenied as exc:
        raise _RssUnavailableError(
            "process_access_denied",
            operation="recursive_children",
            pid=getattr(exc, "pid", None),
            exception_type=type(exc).__name__,
        ) from exc

    rss_bytes = 0
    observed_pids: list[int] = []
    raced_pids: list[int] = []
    root_rss_exception_type: str | None = None
    for member in members:
        try:
            rss_bytes += member.memory_info().rss
            observed_pids.append(member.pid)
        except (psutil.NoSuchProcess, psutil.ZombieProcess) as exc:
            raced_pids.append(member.pid)
            if member.pid == root_pid:
                root_rss_exception_type = type(exc).__name__
        except psutil.AccessDenied as exc:
            raise _RssUnavailableError(
                "rss_access_denied",
                operation="memory_info",
                pid=member.pid,
                exception_type=type(exc).__name__,
            ) from exc
    if root_pid not in observed_pids:
        raise _RssUnavailableError(
            "root_rss_not_observed",
            operation="memory_info",
            pid=root_pid,
            exception_type=root_rss_exception_type,
        )
    return _Sample(rss_bytes, tuple(observed_pids), tuple(raced_pids))


def _waitid_supported() -> bool:
    """Return whether WNOWAIT can hold a child's PID until group cleanup ends."""
    return callable(getattr(os, "waitid", None)) and all(
        hasattr(os, name) for name in ("P_PID", "WEXITED", "WNOHANG", "WNOWAIT")
    )


def _peek_child_exit(pid: int) -> Any | None:
    """Observe child exit status without reaping its session-leader PID."""
    if not _waitid_supported():
        raise RuntimeError("waitid_wnowait_unavailable")
    info = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    if info is None or info.si_pid == 0:
        return None
    return info


def _observe_owned_group(root_pid: int, pgid: int, session_id: int) -> _GroupObservation:
    """Enumerate live members by process-group and session identity.

    WNOWAIT keeps the command root's PID reserved even after it exits. This
    permits safe group signaling until cleanup is finished and prevents the
    numeric PGID from being reused for an unrelated process group.
    """
    try:
        root_exited = _peek_child_exit(root_pid) is not None
    except (ChildProcessError, OSError, RuntimeError):
        return _GroupObservation(None, 0, "waitid_membership_probe_unavailable")

    live_pids: set[int] = set() if root_exited else {root_pid}
    scanned_pids = 0
    try:
        for member in psutil.process_iter(["pid"]):
            scanned_pids += 1
            pid = member.info.get("pid")
            if pid is None or pid == root_pid:
                continue
            try:
                member_pgid = os.getpgid(pid)
                member_session = os.getsid(pid)
            except ProcessLookupError:
                continue
            except PermissionError:
                return _GroupObservation(None, scanned_pids, "process_group_identity_access_denied")
            if member_pgid != pgid or member_session != session_id:
                continue
            try:
                status = member.status()
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            except psutil.AccessDenied:
                return _GroupObservation(None, scanned_pids, "process_group_status_access_denied")
            if status != psutil.STATUS_ZOMBIE:
                live_pids.add(pid)
    except psutil.Error:
        return _GroupObservation(None, scanned_pids, "process_table_enumeration_unavailable")
    return _GroupObservation(frozenset(live_pids), scanned_pids, None)


def _signal_owned_group(
    process: subprocess.Popen[bytes], pgid: int, session_id: int, sig: signal.Signals
) -> bool:
    """Signal only the verified session/process group whose root is unreaped."""
    try:
        root_exit = _peek_child_exit(process.pid)
    except (ChildProcessError, OSError, RuntimeError) as exc:
        raise RuntimeError("refusing group signal without a waitable session leader") from exc
    if process.returncode is not None:
        raise RuntimeError("refusing group signal after the session leader was reaped")
    try:
        actual_pgid = os.getpgid(process.pid)
        actual_session = os.getsid(process.pid)
    except ProcessLookupError as exc:
        # Darwin may hide process-group queries for an exited zombie. WNOWAIT
        # still reserves this Popen PID; start_new_session created pgid=sid=pid.
        try:
            root_exit_after_lookup = _peek_child_exit(process.pid)
        except (ChildProcessError, OSError, RuntimeError) as peek_error:
            raise RuntimeError(
                "refusing group signal without a waitable session leader"
            ) from peek_error
        if root_exit is None and root_exit_after_lookup is None:
            raise RuntimeError("refusing group signal without a held session leader") from exc
        if process.returncode is not None:
            raise RuntimeError("refusing group signal after the session leader was reaped") from exc
        actual_pgid = pgid
        actual_session = session_id
    except PermissionError as exc:
        raise RuntimeError("refusing group signal when leader identity is unreadable") from exc
    if actual_pgid != pgid or actual_session != session_id or pgid != process.pid:
        raise RuntimeError("refusing to signal a process group no longer owned by this run")
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise RuntimeError("owned process group signal was denied") from exc
    return True


def _wait_group_empty(
    process: subprocess.Popen[bytes], pgid: int, session_id: int, timeout_seconds: float
) -> tuple[bool, int, int, str | None]:
    """Wait bounded time for all non-zombie members except a held root."""
    deadline = time.monotonic() + timeout_seconds
    scans = 0
    scanned_pids = 0
    unavailable_reason: str | None = None
    consecutive_empty_scans = 0
    while time.monotonic() < deadline:
        observation = _observe_owned_group(process.pid, pgid, session_id)
        scans += 1
        scanned_pids += observation.scanned_pids
        if observation.unavailable_reason is not None:
            unavailable_reason = observation.unavailable_reason
            consecutive_empty_scans = 0
        elif observation.live_pids == frozenset():
            consecutive_empty_scans += 1
            if consecutive_empty_scans >= 2:
                return True, scans, scanned_pids, unavailable_reason
        else:
            consecutive_empty_scans = 0
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    observation = _observe_owned_group(process.pid, pgid, session_id)
    scans += 1
    scanned_pids += observation.scanned_pids
    if observation.unavailable_reason is not None:
        unavailable_reason = observation.unavailable_reason
        consecutive_empty_scans = 0
    elif observation.live_pids == frozenset():
        consecutive_empty_scans += 1
    else:
        consecutive_empty_scans = 0
    return consecutive_empty_scans >= 2, scans, scanned_pids, unavailable_reason


def _wait_child_exit(pid: int, timeout_seconds: float) -> bool:
    """Wait for a child to exit without releasing its PID reservation."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if _peek_child_exit(pid) is not None:
                return True
        except (ChildProcessError, OSError, RuntimeError):
            return False
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    try:
        return _peek_child_exit(pid) is not None
    except (ChildProcessError, OSError, RuntimeError):
        return False


def _stop_owned_root_only(pid: int) -> list[str]:
    """Stop only the unreaped Popen child when its group identity is unverified."""
    escalations: list[str] = []
    for sig, grace, label in (
        (signal.SIGINT, _INT_GRACE_SECONDS, "SIGINT"),
        (signal.SIGTERM, _TERM_GRACE_SECONDS, "SIGTERM"),
        (signal.SIGKILL, _KILL_GRACE_SECONDS, "SIGKILL"),
    ):
        try:
            _peek_child_exit(pid)
        except (ChildProcessError, OSError, RuntimeError):
            return escalations
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return escalations
        escalations.append(label)
        if _wait_child_exit(pid, grace):
            return escalations
    return escalations


def _stop_owned_group(
    process: subprocess.Popen[bytes], pgid: int, session_id: int
) -> tuple[bool, list[str], int, int, str | None]:
    """Stop the command group with bounded INT, TERM, and KILL grace periods."""
    escalations: list[str] = []
    scans = 0
    scanned_pids = 0
    unavailable_reason: str | None = None

    for sig, grace, label in (
        (signal.SIGINT, _INT_GRACE_SECONDS, "SIGINT"),
        (signal.SIGTERM, _TERM_GRACE_SECONDS, "SIGTERM"),
        (signal.SIGKILL, _KILL_GRACE_SECONDS, "SIGKILL"),
    ):
        observation = _observe_owned_group(process.pid, pgid, session_id)
        scans += 1
        scanned_pids += observation.scanned_pids
        if observation.unavailable_reason is not None:
            unavailable_reason = observation.unavailable_reason
        elif observation.live_pids == frozenset():
            empty, confirm_scans, confirm_pids, confirm_issue = _wait_group_empty(
                process, pgid, session_id, 0.11
            )
            scans += confirm_scans
            scanned_pids += confirm_pids
            if confirm_issue is not None:
                unavailable_reason = confirm_issue
            if empty:
                return True, escalations, scans, scanned_pids, unavailable_reason
        escalations.append(label)
        try:
            _signal_owned_group(process, pgid, session_id, sig)
        except RuntimeError as exc:
            raise _OwnedGroupCleanupError(
                exc,
                scans=scans,
                scanned_pids=scanned_pids,
                unavailable_reason=unavailable_reason,
                signal_name=label,
            ) from exc
        empty, wait_scans, wait_scanned, wait_unavailable = _wait_group_empty(
            process, pgid, session_id, grace
        )
        scans += wait_scans
        scanned_pids += wait_scanned
        if wait_unavailable is not None:
            unavailable_reason = wait_unavailable
        if empty:
            return True, escalations, scans, scanned_pids, unavailable_reason
    return False, escalations, scans, scanned_pids, unavailable_reason


def _result_bytes(result: dict[str, Any]) -> bytes:
    return (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_result(path: Path, result: dict[str, Any]) -> None:
    path.write_bytes(_result_bytes(result))


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    output_dir: Path,
    max_rss_bytes: int,
    wall_seconds: float,
    disk_floor_bytes: int,
    sample_interval_seconds: float = 0.5,
) -> dict[str, Any]:
    """Run one command and record a compact resource result.

    The caller chooses an explicit command and already-prepared environment.
    The output directory must be new and on the same filesystem as ``cwd`` so
    disk-floor samples govern both command scratch and captured output.
    """
    if not command or any(not isinstance(argument, str) for argument in command):
        raise ValueError("command must contain one or more string arguments")
    if (
        max_rss_bytes <= 0
        or not math.isfinite(wall_seconds)
        or wall_seconds <= 0
        or disk_floor_bytes < 0
    ):
        raise ValueError("resource caps must be positive and disk floor non-negative")
    if not math.isfinite(sample_interval_seconds) or sample_interval_seconds <= 0:
        raise ValueError("sample interval must be positive")

    resolved_cwd = cwd.resolve(strict=True)
    if not resolved_cwd.is_dir():
        raise ValueError(f"working directory is not a directory: {resolved_cwd}")
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError(f"output directory must be absent: {output_dir}")
    resolved_output = output_dir.resolve(strict=False)
    if resolved_output.exists():
        raise ValueError(f"output directory must be absent: {resolved_output}")
    output_parent = resolved_output.parent
    if not output_parent.is_dir():
        raise ValueError(f"output parent must already exist: {output_parent}")
    if output_parent.stat().st_dev != resolved_cwd.stat().st_dev:
        raise ValueError("output directory and working directory must share a filesystem")

    resolved_output.mkdir()
    command_log = resolved_output / "command.log"
    result_path = resolved_output / "result.json"
    started_at = time.monotonic()
    free_before: int | None = None
    free_after: int | None = None
    min_free_observed: int | None = None
    peak_rss_bytes: int | None = None
    sample_count = 0
    raced_process_count = 0
    process: subprocess.Popen[bytes] | None = None
    actual_exit_code: int | None = None
    primary_reason: str | None = None
    cleanup_escalations: list[str] = []
    process_group_clean: bool | None = None
    process_group_scan_count = 0
    process_table_pids_scanned = 0
    process_group_measurement_issue: str | None = None
    rss_measurement_failure: dict[str, str | int | None] | None = None
    cleanup_runtime_error: dict[str, str | int | None] | None = None
    waitid_wnowait_available = _waitid_supported()
    limitations = [
        "RSS is sampled; short-lived processes may fall between samples.",
        "Summed per-process RSS can double-count shared pages and is conservative.",
        "Only the command root and psutil-observed recursive descendants are counted.",
        "A child that changes process group or session can escape this cleanup boundary.",
        "Two empty scans indicate observed group quiescence, not proof that every descendant stopped.",
        "Live-group absence is established by a psutil process-table scan; access-denied scans remain unresolved.",
        "The runner passes through the current environment and does not record its values.",
    ]

    try:
        try:
            free_before = _free_bytes(resolved_cwd)
        except OSError:
            primary_reason = "disk_measurement_unavailable"
        min_free_observed = free_before
        if free_before is not None and free_before < disk_floor_bytes:
            primary_reason = "disk_floor_at_admission"
        if primary_reason is None and not waitid_wnowait_available:
            primary_reason = "waitid_wnowait_unavailable"
        if primary_reason is None:
            with command_log.open("xb") as combined_output:
                process = subprocess.Popen(  # noqa: S603 -- explicit coordinator-supplied local argv; no shell.
                    list(command),
                    cwd=resolved_cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=combined_output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    pgid = os.getpgid(process.pid)
                    session_id = os.getsid(process.pid)
                except ProcessLookupError:
                    try:
                        exited_before_identity_probe = _peek_child_exit(process.pid) is not None
                    except (ChildProcessError, OSError, RuntimeError):
                        exited_before_identity_probe = False
                    if exited_before_identity_probe:
                        # start_new_session establishes pgid=sid=pid; WNOWAIT
                        # confirms that this exact PID remains reserved.
                        pgid = session_id = process.pid
                    else:
                        pgid = session_id = -1
                if pgid != process.pid or session_id != process.pid:
                    primary_reason = "process_group_identity_unavailable"
                    cleanup_escalations = _stop_owned_root_only(process.pid)
                    process_group_clean = False
                else:
                    started = time.monotonic()
                    root_exit_observed = False
                    while True:
                        elapsed = time.monotonic() - started
                        try:
                            root_exit_observed = _peek_child_exit(process.pid) is not None
                        except (ChildProcessError, OSError, RuntimeError):
                            primary_reason = "process_exit_measurement_unavailable"
                            break
                        if root_exit_observed:
                            break
                        try:
                            sample = _sample_process_tree(process.pid)
                        except _RssUnavailableError as exc:
                            rss_measurement_failure = exc.to_record()
                            try:
                                root_exit_observed = _peek_child_exit(process.pid) is not None
                            except (ChildProcessError, OSError, RuntimeError):
                                primary_reason = "process_exit_measurement_unavailable"
                            if not root_exit_observed and primary_reason is None:
                                primary_reason = "rss_measurement_unavailable"
                            break
                        sample_count += 1
                        raced_process_count += len(sample.raced_pids)
                        peak_rss_bytes = max(peak_rss_bytes or 0, sample.rss_bytes)
                        try:
                            free_now = _free_bytes(resolved_cwd)
                        except OSError:
                            primary_reason = "disk_measurement_unavailable"
                            break
                        min_free_observed = (
                            free_now
                            if min_free_observed is None
                            else min(min_free_observed, free_now)
                        )

                        if free_now < disk_floor_bytes:
                            primary_reason = "disk_floor_during_run"
                            break
                        if sample.rss_bytes > max_rss_bytes:
                            primary_reason = "rss_cap_observed"
                            break
                        if elapsed >= wall_seconds:
                            primary_reason = "wall_time_cap"
                            break
                        delay = min(sample_interval_seconds, wall_seconds - elapsed)
                        time.sleep(max(0.0, delay))

                    if primary_reason is None and root_exit_observed:
                        observation = _observe_owned_group(process.pid, pgid, session_id)
                        process_group_scan_count += 1
                        process_table_pids_scanned += observation.scanned_pids
                        if observation.unavailable_reason is not None:
                            process_group_measurement_issue = observation.unavailable_reason
                            primary_reason = "process_group_membership_unavailable"
                        elif observation.live_pids:
                            primary_reason = "descendants_outlived_command_root"
                        else:
                            (
                                process_group_clean,
                                confirm_scans,
                                confirm_pids_scanned,
                                confirm_issue,
                            ) = _wait_group_empty(process, pgid, session_id, 0.11)
                            process_group_scan_count += confirm_scans
                            process_table_pids_scanned += confirm_pids_scanned
                            if confirm_issue is not None:
                                process_group_measurement_issue = confirm_issue
                            if not process_group_clean:
                                primary_reason = (
                                    "process_group_membership_unavailable"
                                    if confirm_issue is not None
                                    else "descendants_outlived_command_root"
                                )

                    if primary_reason is not None:
                        try:
                            (
                                process_group_clean,
                                cleanup_escalations,
                                cleanup_scans,
                                cleanup_pids_scanned,
                                cleanup_issue,
                            ) = _stop_owned_group(process, pgid, session_id)
                            process_group_scan_count += cleanup_scans
                            process_table_pids_scanned += cleanup_pids_scanned
                            if cleanup_issue is not None:
                                process_group_measurement_issue = cleanup_issue
                        except _OwnedGroupCleanupError as exc:
                            process_group_scan_count += exc.scans
                            process_table_pids_scanned += exc.scanned_pids
                            if exc.unavailable_reason is not None:
                                process_group_measurement_issue = exc.unavailable_reason
                            elif process_group_measurement_issue is None:
                                process_group_measurement_issue = (
                                    "owned_process_group_signal_unavailable"
                                )
                            cleanup_runtime_error = {
                                "type": exc.cause_type,
                                "operation": "signal_owned_group",
                                "pid": process.pid,
                                "signal": exc.signal_name,
                            }
                            process_group_clean = False
                            cleanup_escalations = _stop_owned_root_only(process.pid)
                        except RuntimeError as exc:
                            process_group_clean = False
                            if process_group_measurement_issue is None:
                                process_group_measurement_issue = (
                                    "owned_process_group_signal_unavailable"
                                )
                            cleanup_runtime_error = {
                                "type": type(exc).__name__,
                                "operation": "stop_owned_group",
                                "pid": process.pid,
                            }
                            cleanup_escalations = _stop_owned_root_only(process.pid)
                    actual_exit_code = process.wait()

        try:
            free_after = _free_bytes(resolved_cwd)
            min_free_observed = (
                free_after if min_free_observed is None else min(min_free_observed, free_after)
            )
        except OSError:
            if primary_reason is None:
                primary_reason = "disk_measurement_unavailable"
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        status = (
            "RESOURCE_ABORT"
            if primary_reason is not None
            else ("PASS" if actual_exit_code == 0 else "COMMAND_FAIL")
        )
        result: dict[str, Any] = {
            "schema": _RESULT_SCHEMA,
            "status": status,
            "primary_reason": primary_reason,
            "command": list(command),
            "cwd": str(resolved_cwd),
            "actual_exit_code": actual_exit_code,
            "wall_seconds_limit": wall_seconds,
            "elapsed_seconds": elapsed_seconds,
            "rss_cap_bytes": max_rss_bytes,
            "peak_sampled_process_tree_rss_bytes": peak_rss_bytes,
            "rss_sample_count": sample_count,
            "rss_raced_process_count": raced_process_count,
            "sample_interval_seconds": sample_interval_seconds,
            "disk_probe_path": str(resolved_cwd),
            "disk_free_bytes_before": free_before,
            "disk_free_bytes_min_observed": min_free_observed,
            "disk_free_bytes_after": free_after,
            "disk_floor_bytes": disk_floor_bytes,
            "command_log": str(command_log) if command_log.exists() else None,
            "process_group_quiescence_observed": process_group_clean,
            "process_group_observation_method": "two_consecutive_empty_process_table_scans",
            "process_group_scan_count": process_group_scan_count,
            "process_table_pids_scanned": process_table_pids_scanned,
            "process_group_measurement_issue": process_group_measurement_issue,
            "rss_measurement_failure": rss_measurement_failure,
            "cleanup_runtime_error": cleanup_runtime_error,
            "waitid_wnowait_available": waitid_wnowait_available,
            "cleanup_signals": cleanup_escalations,
            "limitations": limitations,
        }
        _write_result(result_path, result)
        return result
    except BaseException:
        if process is not None and process.returncode is None:
            with suppress(OSError, RuntimeError, subprocess.TimeoutExpired):
                _stop_owned_group(process, process.pid, process.pid)
            with suppress(OSError, subprocess.SubprocessError):
                process.wait()
        raise


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments, run the child command, and return a status code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--max-rss-bytes", type=_positive_int, required=True)
    parser.add_argument("--wall-seconds", type=_positive_float, required=True)
    parser.add_argument("--disk-floor-bytes", type=_nonnegative_int, required=True)
    parser.add_argument("--sample-interval-seconds", type=_positive_float, default=0.5)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("provide a command after --")

    try:
        result = run_command(
            command,
            cwd=args.cwd,
            output_dir=args.output_dir,
            max_rss_bytes=args.max_rss_bytes,
            wall_seconds=args.wall_seconds,
            disk_floor_bytes=args.disk_floor_bytes,
            sample_interval_seconds=args.sample_interval_seconds,
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"process_budget: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["status"] == "RESOURCE_ABORT":
        return 3
    if result["status"] == "COMMAND_FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
