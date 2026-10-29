"""Test-only non-blocking call-through observers for the R4 native-fit witness.

Proposed target: tests/_helpers/r4_native_fit_observer.py. This module records
actual calls and identities; it never holds a fit callback open or changes results.
"""

from __future__ import annotations

import ctypes
import hashlib
import inspect
import itertools
import os
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar


class FitObserver:
    """Record real ForestDR/GRFTree calls without holding their execution open."""

    def __init__(self, *, is_shared_worker: Callable[[], bool]) -> None:
        self.events: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
        self._is_shared_worker = is_shared_worker
        self._sequence = itertools.count(1)
        self._fit_call_ids = itertools.count(1)
        self.worker: dict[str, Any] | None = None

    def _stamp(self) -> dict[str, Any]:
        current = threading.current_thread()
        return {
            "pid": os.getpid(),
            "thread_id": current.ident,
            "native_thread_id": threading.get_native_id(),
            "thread_name": current.name,
            "monotonic_ns": time.monotonic_ns(),
            "thread_time_ns": time.thread_time_ns(),
            "is_current_shared_executor_worker": self._is_shared_worker(),
        }

    def _capture_worker_once(self) -> None:
        """Capture one Mach thread port from the actual outer-fit worker."""
        stamp = self._stamp()
        if self.worker is not None:
            return
        try:
            libc = ctypes.CDLL(None)
            pthread_self = libc.pthread_self
            pthread_self.argtypes = []
            pthread_self.restype = ctypes.c_void_p
            pthread_mach_thread_np = libc.pthread_mach_thread_np
            pthread_mach_thread_np.argtypes = [ctypes.c_void_p]
            pthread_mach_thread_np.restype = ctypes.c_uint
            pthread_value = pthread_self()
            mach_port = int(pthread_mach_thread_np(pthread_value))
            self.worker = {
                **stamp,
                "pthread_value": int(pthread_value or 0),
                "mach_thread_port": mach_port,
                "mach_port_error": None if mach_port else "pthread_mach_thread_np_returned_zero",
            }
        except Exception as exc:  # instrumentation failure must not change fit behavior
            self.worker = {
                **stamp,
                "pthread_value": None,
                "mach_thread_port": None,
                "mach_port_error": f"{type(exc).__name__}: {exc}",
            }
        self.events.put({"kind": "worker_identity", **self.worker})

    def wrap_forest_dr_fit(self, original: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap the outer model fit; record a return only after real success."""

        def observed(model: Any, /, *args: Any, **kwargs: Any) -> Any:
            self._capture_worker_once()
            entered = self._stamp()
            model_identity = id(model)
            fit_call_id = next(self._fit_call_ids)
            self.events.put(
                {
                    "sequence": next(self._sequence),
                    "kind": "fit_enter",
                    "fit_layer": "forest_dr",
                    "fit_call_id": fit_call_id,
                    "estimator_identity": model_identity,
                    "success": False,
                    **entered,
                }
            )
            result = original(model, *args, **kwargs)
            returned = self._stamp()
            self.events.put(
                {
                    "sequence": next(self._sequence),
                    "kind": "fit_return",
                    "fit_layer": "forest_dr",
                    "fit_call_id": fit_call_id,
                    "estimator_identity": model_identity,
                    "success": True,
                    **returned,
                }
            )
            return result

        return observed

    def wrap_grftree_fit(self, original: Callable[..., Any]) -> Callable[..., Any]:
        """Record every real GRFTree fit entry and natural successful return."""

        def observed(tree: Any, /, *args: Any, **kwargs: Any) -> Any:
            fit_call_id = next(self._fit_call_ids)
            started = self._stamp()
            tree_identity = id(tree)
            entry_sequence = next(self._sequence)
            self.events.put(
                {
                    "kind": "fit_enter",
                    "fit_layer": "grf_tree",
                    "sequence": entry_sequence,
                    "fit_call_id": fit_call_id,
                    "tree_identity": tree_identity,
                    "success": False,
                    "fit_started_ns": started["monotonic_ns"],
                    "thread_cpu_started_ns": started["thread_time_ns"],
                    **started,
                }
            )
            # Deliberately no try/except/finally around the estimator call. Its
            # original failure propagates unchanged and cannot yield a success row.
            result = original(tree, *args, **kwargs)
            finished = self._stamp()
            return_sequence = next(self._sequence)
            node_count, node_count_error = _read_node_count(tree)
            self.events.put(
                {
                    "kind": "fit_return",
                    "fit_layer": "grf_tree",
                    "sequence": return_sequence,
                    "fit_call_id": fit_call_id,
                    "tree_identity": tree_identity,
                    "success": True,
                    "node_count": node_count,
                    "node_count_error": node_count_error,
                    "fit_started_ns": started["monotonic_ns"],
                    "fit_finished_ns": finished["monotonic_ns"],
                    "thread_cpu_started_ns": started["thread_time_ns"],
                    "thread_cpu_finished_ns": finished["thread_time_ns"],
                    **finished,
                }
            )
            return result

        return observed


def _read_node_count(tree: Any) -> tuple[int | None, str | None]:
    """Best-effort telemetry after a successful fit; never changes its result."""
    try:
        fitted = getattr(tree, "tree_", None)
        if fitted is None:
            return None, None
        inner = getattr(fitted, "tree_", fitted)
        value = getattr(inner, "node_count", None)
        if type(value) is int and value >= 0:
            return value, None
        return None, None
    except Exception as exc:
        # This catches only observer introspection after the original fit returned.
        return None, f"{type(exc).__name__}: {exc}"


def source_file_record(path: str | Path) -> dict[str, Any]:
    """Return the observed source path and SHA-256 without importing its owner."""
    selected = Path(path).resolve()
    raw = selected.read_bytes()
    return {
        "path": str(selected),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


class _TimeValue(ctypes.Structure):
    """macOS ``time_value_t`` field layout used by THREAD_BASIC_INFO."""

    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("seconds", ctypes.c_int),
        ("microseconds", ctypes.c_int),
    ]


class _ThreadBasicInfo(ctypes.Structure):
    """40-byte macOS ``thread_basic_info_data_t`` layout from mach/thread_info.h."""

    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("user_time", _TimeValue),
        ("system_time", _TimeValue),
        ("cpu_usage", ctypes.c_uint),
        ("policy", ctypes.c_int),
        ("run_state", ctypes.c_int),
        ("flags", ctypes.c_int),
        ("suspend_count", ctypes.c_int),
        ("sleep_time", ctypes.c_int),
    ]


def mach_thread_basic_info_sample(port: int) -> dict[str, Any]:
    """Read one worker port; timestamp immediately after the Mach query."""
    result: dict[str, Any] = {
        "monotonic_ns": None,
        "return_code": None,
        "user_time_seconds": None,
        "user_time_microseconds": None,
        "system_time_seconds": None,
        "system_time_microseconds": None,
        "thread_cpu_microseconds": None,
        "returned_count": None,
        "struct_size_bytes": ctypes.sizeof(_ThreadBasicInfo),
        "error": None,
    }
    try:
        if ctypes.sizeof(_ThreadBasicInfo) != 40 or type(port) is not int or port <= 0:
            raise ValueError("mach_thread_basic_info_layout_or_port_not_established")
        libc = ctypes.CDLL(None)
        thread_info = libc.thread_info
        thread_info.argtypes = [
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
        ]
        thread_info.restype = ctypes.c_int
        words = (ctypes.c_uint * 10)()
        count = ctypes.c_uint(10)
        code = int(thread_info(port, 3, words, ctypes.byref(count)))
        result["monotonic_ns"] = time.monotonic_ns()
        result["return_code"] = code
        result["returned_count"] = int(count.value)
        if code != 0:
            return result
        info = ctypes.cast(words, ctypes.POINTER(_ThreadBasicInfo)).contents
        user_s = int(info.user_time.seconds)
        user_us = int(info.user_time.microseconds)
        system_s = int(info.system_time.seconds)
        system_us = int(info.system_time.microseconds)
        result.update(
            {
                "user_time_seconds": user_s,
                "user_time_microseconds": user_us,
                "system_time_seconds": system_s,
                "system_time_microseconds": system_us,
                "thread_cpu_microseconds": (user_s * 1_000_000 + user_us)
                + (system_s * 1_000_000 + system_us),
            }
        )
    except Exception as exc:
        result["monotonic_ns"] = time.monotonic_ns()
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def callable_record(callable_object: Callable[..., Any]) -> dict[str, Any]:
    """Bind a live callable identity to its source file, when available."""
    source_path = None
    source_hash = None
    try:
        source_path = Path(inspect.getsourcefile(callable_object) or "").resolve()
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    except (OSError, TypeError):
        pass
    return {
        "module": getattr(callable_object, "__module__", None),
        "qualname": getattr(callable_object, "__qualname__", None),
        "source_path": str(source_path) if source_path else None,
        "source_sha256": source_hash,
        "identity_repr": repr(callable_object),
    }
