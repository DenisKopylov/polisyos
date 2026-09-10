"""Lane-local macOS process-tree observer; never inspect argv, environment or content.

Samples are observed lower bounds for cumulative counters: an unknown descendant
that starts and exits between samples can be missed. Known descendants remain
tracked after reparenting. RSS is the maximum simultaneous sampled sum, not a sum
of per-process lifetime peaks. Native disk bytes are distinct from artifact sizes.
The observer and its numeric-only ``ps`` subprocesses are outside the worker tree.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import math
import os
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

_U64_FIELDS = [
    "ri_user_time",
    "ri_system_time",
    "ri_pkg_idle_wkups",
    "ri_interrupt_wkups",
    "ri_pageins",
    "ri_wired_size",
    "ri_resident_size",
    "ri_phys_footprint",
    "ri_proc_start_abstime",
    "ri_proc_exit_abstime",
    "ri_child_user_time",
    "ri_child_system_time",
    "ri_child_pkg_idle_wkups",
    "ri_child_interrupt_wkups",
    "ri_child_pageins",
    "ri_child_elapsed_abstime",
    "ri_diskio_bytesread",
    "ri_diskio_byteswritten",
]


class _RUsageInfoV2(ctypes.Structure):
    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [
        (name, ctypes.c_uint64) for name in _U64_FIELDS
    ]


class _MachTimebase(ctypes.Structure):
    _fields_: ClassVar = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]


@dataclass(frozen=True)
class ProfileLimits:
    """Predeclared ceilings; polling can overshoot a ceiling by one sample interval."""

    max_wall_seconds: float
    max_rss_bytes: int | None = None
    max_disk_write_bytes: int | None = None
    sample_interval_seconds: float = 0.25
    shutdown_grace_seconds: float = 2.0

    def __post_init__(self) -> None:
        for value in (
            self.max_wall_seconds,
            self.sample_interval_seconds,
            self.shutdown_grace_seconds,
        ):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("telemetry_time_limit_invalid")
        for value in (self.max_rss_bytes, self.max_disk_write_bytes):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError("telemetry_byte_limit_invalid")


def read_process_usage(pid: int) -> dict[str, Any]:
    """Read SDK-defined v2 native counters; unavailable values are explicitly null."""
    empty = {
        "pid": pid,
        "status": "ambiguous",
        "errno": None,
        "start_identity": None,
        "exited": None,
        "rss_bytes": None,
        "footprint_bytes": None,
        "cpu_user_seconds": None,
        "cpu_system_seconds": None,
        "disk_read_bytes": None,
        "disk_write_bytes": None,
    }
    if sys.platform != "darwin":
        return {**empty, "reason": "native_platform_unavailable"}
    try:
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        read = library.proc_pid_rusage
        read.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        read.restype = ctypes.c_int
        native = _RUsageInfoV2()
        if read(pid, 2, ctypes.byref(native)) != 0:
            return {**empty, "reason": "native_read_failed", "errno": ctypes.get_errno()}
        system = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        timebase = _MachTimebase()
        timebase_read = system.mach_timebase_info
        timebase_read.argtypes = [ctypes.POINTER(_MachTimebase)]
        timebase_read.restype = ctypes.c_int
        if timebase_read(ctypes.byref(timebase)) != 0 or timebase.denom == 0:
            return {**empty, "reason": "native_timebase_unavailable"}
    except (AttributeError, OSError) as exc:
        return {**empty, "reason": "native_binding_unavailable", "error_class": type(exc).__name__}
    return {
        "pid": pid,
        "status": "measured",
        "errno": None,
        "start_identity": int(native.ri_proc_start_abstime),
        "exited": bool(native.ri_proc_exit_abstime),
        "rss_bytes": int(native.ri_resident_size),
        "footprint_bytes": int(native.ri_phys_footprint),
        "cpu_user_seconds": native.ri_user_time * timebase.numer / timebase.denom / 1e9,
        "cpu_system_seconds": native.ri_system_time * timebase.numer / timebase.denom / 1e9,
        "cpu_user_absolute_ticks": int(native.ri_user_time),
        "cpu_system_absolute_ticks": int(native.ri_system_time),
        "cpu_timebase_numer": timebase.numer,
        "cpu_timebase_denom": timebase.denom,
        "disk_read_bytes": int(native.ri_diskio_bytesread),
        "disk_write_bytes": int(native.ri_diskio_byteswritten),
    }


def _process_table() -> dict[int, int]:
    """Enumerate only PID and parent PID; never request commands or environment."""
    result = subprocess.run(
        ["/bin/ps", "-axo", "pid=,ppid="],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError("process_inventory_unavailable")
    pairs = [tuple(map(int, line.split())) for line in result.stdout.splitlines() if line.strip()]
    if any(len(pair) != 2 for pair in pairs) or len({pair[0] for pair in pairs}) != len(pairs):
        raise ValueError("process_inventory_ambiguous")
    return dict(pairs)


def _descendant_pids(root_pid: int, table: dict[int, int]) -> set[int]:
    descendants: set[int] = set()
    frontier = {root_pid}
    while frontier:
        children = {pid for pid, parent in table.items() if parent in frontier}
        frontier = children - descendants - {root_pid}
        descendants.update(frontier)
    return descendants


def sqlite_completion_reader(
    path: Path, *, terminal_statuses: Sequence[str] = ("completed",)
) -> Callable[[], int]:
    """Return a read-only work_items.status counter with independent row reconciliation."""
    statuses = tuple(terminal_statuses)
    if not statuses or any(not isinstance(value, str) for value in statuses):
        raise ValueError("checkpoint_terminal_status_invalid")

    def completed() -> int:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1) as con:
            placeholders = ",".join("?" for _ in statuses)
            count = con.execute(
                "SELECT COUNT(*) FROM work_items WHERE status IN (" + placeholders + ")",  # noqa: S608 - placeholders only.
                statuses,
            ).fetchone()[0]
            rows = con.execute("SELECT rowid,status FROM work_items").fetchall()
        identities = {row[0] for row in rows if row[1] in statuses}
        if count != len(identities):
            raise ValueError("checkpoint_count_reconciliation_failed")
        return count

    return completed


def _completion(reader: Callable[[], int] | None) -> tuple[int | None, str]:
    if reader is None:
        return None, "not_requested"
    try:
        count = reader()
        if type(count) is not int or count < 0:
            raise ValueError("checkpoint_count_invalid")
        return count, "measured"
    except Exception:
        return None, "ambiguous"


def profile_module(
    module: str,
    module_args: Sequence[str],
    *,
    cwd: Path,
    output_root: Path,
    limits: ProfileLimits,
    completion_reader: Callable[[], int] | None = None,
    interrupt_requested: Callable[[], bool] | None = None,
    synthetic: bool = False,
) -> dict[str, Any]:
    """Launch one module in an owned group and emit safe process-tree samples.

    Child stdout/stderr are discarded. The child owns its application artifacts;
    neither its arguments nor its inherited environment enter this receipt.
    Returns a numeric/status summary. The caller owns persistence of that summary.
    """
    if type(synthetic) is not bool or not isinstance(module, str) or not module:
        raise ValueError("telemetry_launch_declaration_invalid")
    output_root.mkdir(parents=True, exist_ok=False)
    logical_cpus = os.cpu_count()
    physical_memory = None
    try:
        observation = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if observation.returncode == 0 and observation.stdout.strip().isdigit():
            physical_memory = int(observation.stdout.strip()) or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    hardware = {
        "logical_cpu_count": logical_cpus,
        "physical_memory_bytes": physical_memory,
        "logical_cpu_source": "os.cpu_count",
        "physical_memory_source": "sysctl.hw.memsize",
        "status": "measured" if logical_cpus and physical_memory else "ambiguous",
    }
    started = time.monotonic()
    observer_started = time.process_time()
    process = subprocess.Popen(  # noqa: S603 - explicit caller module argv, never shell.
        [sys.executable, "-m", module, *module_args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        result = _profile_process(
            process,
            output_root=output_root,
            limits=limits,
            completion_reader=completion_reader,
            interrupt_requested=interrupt_requested,
            synthetic=synthetic,
            started=started,
            observer_started=observer_started,
        )
        result["hardware_observation"] = hardware
        cpu_user, cpu_system = result["cpu_user_seconds"], result["cpu_system_seconds"]
        result["worker_cpu_capacity_fraction"] = (
            (cpu_user + cpu_system) / result["wall_seconds"] / logical_cpus
            if cpu_user is not None and cpu_system is not None and logical_cpus
            else None
        )
        peak = result["peak_summed_rss_bytes"]
        result["peak_worker_rss_physical_memory_fraction"] = (
            peak / physical_memory if peak is not None and physical_memory else None
        )
        return result
    except BaseException as exc:
        # Observation failure must stop paid work; never expose exception content.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=limits.shutdown_grace_seconds)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=2)
        raise RuntimeError("telemetry_observer_failed:" + type(exc).__name__) from None


def _profile_process(
    process: subprocess.Popen,
    *,
    output_root: Path,
    limits: ProfileLimits,
    completion_reader: Callable[[], int] | None,
    interrupt_requested: Callable[[], bool] | None,
    synthetic: bool,
    started: float,
    observer_started: float,
) -> dict[str, Any]:
    latest: dict[tuple[int, int], dict[str, Any]] = {}
    known: dict[int, int] = {}
    peak_rss = 0
    peak_footprint = 0
    max_descendants = 0
    sample_count = 0
    ambiguous_count = 0
    stop_reason: str | None = None
    stop_at: float | None = None
    shutdown_level = 0
    sample_gaps: list[float] = []
    last_sample_at: float | None = None
    final: dict[str, Any] = {}
    cumulative_fields = (
        "cpu_user_seconds",
        "cpu_system_seconds",
        "disk_read_bytes",
        "disk_write_bytes",
    )

    def request_stop(reason: str) -> None:
        nonlocal stop_reason, stop_at
        if stop_reason is None:
            stop_reason = reason
            stop_at = time.monotonic()
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGINT)

    with (output_root / "samples.jsonl").open("x", encoding="utf-8") as stream:
        while True:
            try:
                now = time.monotonic()
                if last_sample_at is not None:
                    sample_gaps.append(now - last_sample_at)
                last_sample_at = now
                try:
                    table = _process_table()
                    descendants = _descendant_pids(process.pid, table)
                    inventory_status = "measured"
                except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                    table = {}
                    descendants = set()
                    inventory_status = "ambiguous"
                candidates = descendants | set(known) | {process.pid}
                readings: list[dict[str, Any]] = []
                for pid in sorted(candidates):
                    if pid not in table and pid in known:
                        continue
                    value = read_process_usage(pid)
                    if value["status"] == "measured":
                        identity = value["start_identity"]
                        if pid in known and known[pid] != identity and pid not in descendants:
                            continue  # A recycled PID is not the previously observed process.
                        known[pid] = identity
                        key = (pid, identity)
                        previous = latest.get(key)
                        if previous is not None and any(
                            value[field] < previous[field] for field in cumulative_fields
                        ):
                            value = {**value, "status": "ambiguous", "reason": "counter_regressed"}
                        else:
                            latest[key] = value
                    readings.append(value)
                valid = [value for value in readings if value["status"] == "measured"]
                observed_errors = sum(value["status"] != "measured" for value in readings)
                ambiguous_count += observed_errors + int(inventory_status != "measured")
                active = [value for value in valid if not value["exited"]]
                rss = sum(value["rss_bytes"] for value in active) if valid else None
                footprint = sum(value["footprint_bytes"] for value in active) if valid else None
                totals = {
                    field: sum(value[field] for value in latest.values()) if latest else None
                    for field in cumulative_fields
                }
                completed, completed_status = _completion(completion_reader)
                descendant_count = sum(value["pid"] != process.pid for value in active)
                final = {
                    "schema_version": "corr.process_resource_sample.v1",
                    "synthetic": synthetic,
                    "elapsed_seconds": now - started,
                    "inventory_status": inventory_status,
                    "measurement_status": "ambiguous" if observed_errors else inventory_status,
                    "processes": readings,
                    "descendant_count": descendant_count,
                    "summed_rss_bytes": rss,
                    "summed_footprint_bytes": footprint,
                    **totals,
                    "completed_work_count": completed,
                    "completed_work_count_status": completed_status,
                    "stop_reason": stop_reason,
                }
                stream.write(json.dumps(final, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                sample_count += 1
                peak_rss = max(peak_rss, rss or 0)
                peak_footprint = max(peak_footprint, footprint or 0)
                max_descendants = max(max_descendants, descendant_count)
                returncode = process.poll()  # Reap only after the native terminal snapshot.
                if returncode is not None and not active:
                    break
                if stop_reason is None:
                    if interrupt_requested is not None and interrupt_requested():
                        request_stop("interrupted")
                    elif now - started >= limits.max_wall_seconds:
                        request_stop("max_wall_seconds")
                    elif (
                        limits.max_rss_bytes is not None
                        and rss is not None
                        and rss > limits.max_rss_bytes
                    ):
                        request_stop("max_rss_bytes")
                    elif (
                        limits.max_disk_write_bytes is not None
                        and totals["disk_write_bytes"] is not None
                        and totals["disk_write_bytes"] > limits.max_disk_write_bytes
                    ):
                        request_stop("max_disk_write_bytes")
                if stop_at is not None:
                    since_stop = time.monotonic() - stop_at
                    if since_stop > limits.shutdown_grace_seconds and shutdown_level == 0:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGTERM)
                        shutdown_level = 1
                    if since_stop > limits.shutdown_grace_seconds + 1 and shutdown_level == 1:
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                        shutdown_level = 2
                    if since_stop > limits.shutdown_grace_seconds + 3:
                        stop_reason = "shutdown_not_established"
                        break
                time.sleep(max(0, limits.sample_interval_seconds - (time.monotonic() - now)))
            except KeyboardInterrupt:
                request_stop("interrupted")
    return {
        "schema_version": "corr.process_resource_profile.v1",
        "synthetic": synthetic,
        "authority_status": "candidate_measurement",
        "status": "stopped"
        if stop_reason
        else ("completed" if process.returncode == 0 else "failed"),
        "stop_reason": stop_reason,
        "returncode": process.poll(),
        "wall_seconds": time.monotonic() - started,
        "monotonic_started_seconds": started,
        "cpu_user_seconds": final.get("cpu_user_seconds"),
        "cpu_system_seconds": final.get("cpu_system_seconds"),
        "disk_read_bytes": final.get("disk_read_bytes"),
        "disk_write_bytes": final.get("disk_write_bytes"),
        "peak_summed_rss_bytes": peak_rss if latest else None,
        "peak_summed_footprint_bytes": peak_footprint if latest else None,
        "max_descendant_count": max_descendants,
        "observed_process_identity_count": len(latest),
        "sample_count": sample_count,
        "ambiguous_observation_count": ambiguous_count,
        "max_sample_gap_seconds": max(sample_gaps, default=None),
        "requested_sample_interval_seconds": limits.sample_interval_seconds,
        "completed_work_count": final.get("completed_work_count"),
        "completed_work_count_status": final.get("completed_work_count_status", "ambiguous"),
        "observer_scope": "excluded_from_worker_tree",
        "observer_cpu_seconds": time.process_time() - observer_started,
        "observer_cpu_scope": "observer_process_only_excludes_ps_subprocesses",
        "cumulative_counter_scope": "observed_process_lifetimes_lower_bound",
        "memory_peak_scope": "simultaneous_sampled_sum_not_lifetime_peak",
        "short_lived_child_coverage": "ambiguous_if_created_and_exited_between_samples",
        "checkpoint_scope": "caller_declared_terminal_statuses",
        "raw_child_output": "discarded",
    }
