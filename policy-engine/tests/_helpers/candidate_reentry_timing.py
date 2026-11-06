"""Optional, bounded timing for candidate-experiment reentry owner methods.

Enable with ``-p tests._helpers.candidate_reentry_timing`` and set
``E02_REENTRY_TIMING_OUTPUT`` to a JSON file in an existing run directory.
Only the listed Python code objects receive local start/return events. Python
unwind is not locally selectable on the supported interpreter, so its callback
is global and immediately filters by code-object identity. Its observed handler
time is reported; no zero-overhead assumption is made.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import threading
import time
import types
from contextlib import suppress
from pathlib import Path
from typing import Any

_TOOL_ID = 4
_TARGETS: tuple[tuple[str, str, str | None, str], ...] = (
    (
        "acquisition_bridge.source_reentry_preflight",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "candidate_experiment_source_reentry_preflight",
    ),
    (
        "acquisition_bridge.reconcile_reentry_budget",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "_reconcile_candidate_experiment_source_reentry_budget",
    ),
    (
        "acquisition_bridge.prior_owner",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "_candidate_experiment_prior_owner",
    ),
    (
        "candidate_action.current_action",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_current_candidate_experiment_action",
    ),
    (
        "candidate_action.reentry_action",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_current_candidate_experiment_reentry_action",
    ),
    (
        "candidate_action.select_outcome",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_select_current_candidate_experiment_outcome",
    ),
    (
        "route_loop.resolve_reentry",
        "polisyos.runtime.quality.acquisition_route_loop",
        "AcquisitionRouteLoop",
        "_resolve_current_candidate_experiment_resolution",
    ),
)


def _resolve_code_objects() -> dict[str, types.CodeType]:
    """Resolve only the declared synchronous owner methods."""
    resolved: dict[str, types.CodeType] = {}
    modules: dict[str, types.ModuleType] = {}
    class_dict_descriptor = type.__dict__["__dict__"]
    for label, module_name, owner_name, function_name in _TARGETS:
        module = modules.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
            modules[module_name] = module
        if owner_name is None:
            target: Any = vars(module).get(function_name)
        else:
            owner = vars(module).get(owner_name)
            if not isinstance(owner, type) or type(owner) is not type:
                raise LookupError(f"declared timing owner is not a native class: {owner_name}")
            namespace = class_dict_descriptor.__get__(owner, type)
            target = namespace.get(function_name)
        if type(target) is not types.FunctionType:
            raise LookupError(f"declared timing target is not a function: {label}")
        if target.__code__.co_flags & (0x20 | 0x80 | 0x200):
            raise TypeError(f"declared timing target is not synchronous: {label}")
        resolved[label] = target.__code__
    return resolved


class _TimingObserver:
    """Observe selected code-object durations without inspecting call values."""

    def __init__(self, codes: dict[str, types.CodeType], output: Path) -> None:
        self.codes = codes
        self.output = output
        self.code_by_identity: dict[int, tuple[types.CodeType, str]] = {}
        for label, code in codes.items():
            identity = id(code)
            existing = self.code_by_identity.get(identity)
            if existing is not None and existing[0] is code:
                raise ValueError(f"multiple labels refer to the same code object: {label}")
            self.code_by_identity[identity] = (code, label)
        self.lock = threading.RLock()
        self.stacks: dict[tuple[int, int], list[int]] = {}
        self.rows = {
            label: {
                "calls": 0,
                "returns": 0,
                "unwinds": 0,
                "inclusive_wall_ns": 0,
                "max_wall_ns": 0,
            }
            for label in codes
        }
        self.status = "not_started"
        self.reason: str | None = None
        self.observer_errors = 0
        self.unmatched_ends = 0
        self.selected_global_unwind_events_seen = 0
        self.global_unwind_handler_wall_ns = 0
        self._owned = False
        self._enabled_local: list[types.CodeType] = []
        self._callbacks: dict[int, Any] = {}
        self._snapshot_stop = threading.Event()
        self._snapshot_thread: threading.Thread | None = None

    def enable(self) -> bool:
        """Install callbacks only when tool slot 4 is entirely available."""
        monitoring = getattr(sys, "monitoring", None)
        if monitoring is None:
            return self._unavailable("sys.monitoring is unavailable")
        events = monitoring.events
        if monitoring.get_tool(_TOOL_ID) is not None or monitoring.get_events(_TOOL_ID):
            return self._unavailable("monitoring tool ID 4 is already occupied")
        if any(monitoring.get_local_events(_TOOL_ID, code) for code in self.codes.values()):
            return self._unavailable("tool ID 4 has pre-existing local events")
        try:
            monitoring.use_tool_id(_TOOL_ID, "e02-candidate-reentry-timing")
            self._owned = True
            self._callbacks = {
                events.PY_START: lambda code, *args: self._safe_start(code, *args),
                events.PY_RETURN: lambda code, *args: self._safe_return(code, *args),
                events.PY_UNWIND: lambda code, *args: self._safe_unwind(code, *args),
            }
            for event, callback in self._callbacks.items():
                monitoring.register_callback(_TOOL_ID, event, callback)
            for code in self.codes.values():
                monitoring.set_local_events(_TOOL_ID, code, events.PY_START | events.PY_RETURN)
                self._enabled_local.append(code)
            # CPython 3.14 does not permit PY_UNWIND as a local event. This
            # global exception-only callback filters by exact code identity.
            monitoring.set_events(_TOOL_ID, events.PY_UNWIND)
            self.status = "active"
            self._snapshot_thread = threading.Thread(
                target=self._snapshot_loop,
                name="e02-reentry-timing-snapshot",
                daemon=True,
            )
            self._snapshot_thread.start()
            return True
        except Exception as exc:
            self._unavailable(f"monitoring setup failed: {type(exc).__name__}: {exc}")
            self.cleanup()
            return False

    def _unavailable(self, reason: str) -> bool:
        self.status = "instrumentation_unavailable"
        self.reason = reason
        return False

    def _identity_label(self, code: types.CodeType) -> str | None:
        entry = self.code_by_identity.get(id(code))
        if entry is None or entry[0] is not code:
            return None
        return entry[1]

    def _safe_start(self, code: types.CodeType, *_: object) -> None:
        try:
            label = self._identity_label(code)
            if label is None:
                return
            now = time.perf_counter_ns()
            key = (threading.get_ident(), id(code))
            with self.lock:
                self.stacks.setdefault(key, []).append(now)
                self.rows[label]["calls"] += 1
        except Exception:
            self.observer_errors += 1

    def _safe_return(self, code: types.CodeType, *_: object) -> None:
        self._safe_end(code, "returns")

    def _safe_unwind(self, code: types.CodeType, *_: object) -> None:
        # Identity filtering is intentionally the first callback operation.
        label = self._identity_label(code)
        if label is None:
            return
        started = time.perf_counter_ns()
        try:
            with self.lock:
                self.selected_global_unwind_events_seen += 1
            self._safe_end_for_label(code, label, "unwinds")
        except Exception:
            self.observer_errors += 1
        finally:
            elapsed = time.perf_counter_ns() - started
            with self.lock:
                self.global_unwind_handler_wall_ns += elapsed

    def _safe_end(self, code: types.CodeType, outcome: str) -> None:
        label = self._identity_label(code)
        if label is None:
            return
        self._safe_end_for_label(code, label, outcome)

    def _safe_end_for_label(self, code: types.CodeType, label: str, outcome: str) -> None:
        try:
            now = time.perf_counter_ns()
            key = (threading.get_ident(), id(code))
            with self.lock:
                starts = self.stacks.get(key)
                if not starts:
                    self.unmatched_ends += 1
                    return
                elapsed = now - starts.pop()
                if not starts:
                    self.stacks.pop(key, None)
                row = self.rows[label]
                row[outcome] += 1
                row["inclusive_wall_ns"] += elapsed
                row["max_wall_ns"] = max(row["max_wall_ns"], elapsed)
        except Exception:
            self.observer_errors += 1

    def snapshot(self) -> dict[str, object]:
        now = time.perf_counter_ns()
        with self.lock:
            active: dict[str, dict[str, int]] = {
                label: {"active_calls": 0, "current_wall_ns": 0} for label in self.codes
            }
            for (thread_id, code_identity), starts in self.stacks.items():
                del thread_id
                label = self.code_by_identity[code_identity][1]
                active[label]["active_calls"] += len(starts)
                active[label]["current_wall_ns"] += sum(now - started for started in starts)
            return {
                "schema_version": 1,
                "status": self.status,
                "reason": self.reason,
                "python": sys.version.split()[0],
                "tool_id": _TOOL_ID,
                "unwind_scope": "global event; exact code-object identity filter",
                "selected_global_unwind_events_seen": self.selected_global_unwind_events_seen,
                "global_unwind_handler_wall_ns": self.global_unwind_handler_wall_ns,
                "global_unwind_handler_timing": "callback body only; dispatch cost is not measured",
                "observer_errors": self.observer_errors,
                "unmatched_ends": self.unmatched_ends,
                "targets": {
                    label: {
                        "code": {
                            "qualname": self.codes[label].co_qualname,
                            "file": self.codes[label].co_filename,
                            "line": self.codes[label].co_firstlineno,
                        },
                        **row,
                        **active[label],
                        "observation": "observed" if row["calls"] else "unobserved",
                    }
                    for label, row in self.rows.items()
                },
            }

    def flush(self) -> None:
        """Atomically replace the caller-owned compact JSON output."""
        payload = json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"))
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.output.parent,
                prefix=f".{self.output.name}.",
                suffix=".pending",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(payload)
                handle.write("\n")
            os.replace(temp_path, self.output)
        except OSError:
            if temp_path is not None:
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)
            with self.lock:
                self.observer_errors += 1

    def _snapshot_loop(self) -> None:
        while not self._snapshot_stop.wait(30):
            self.flush()

    def cleanup(self) -> None:
        """Disable only this observer's callbacks and local event masks."""
        self._snapshot_stop.set()
        if self._snapshot_thread is not None and self._snapshot_thread.is_alive():
            self._snapshot_thread.join(timeout=1)
        monitoring = getattr(sys, "monitoring", None)
        if monitoring is not None and self._owned:
            try:
                for code in self._enabled_local:
                    monitoring.set_local_events(_TOOL_ID, code, 0)
                monitoring.set_events(_TOOL_ID, 0)
                for event in (
                    monitoring.events.PY_START,
                    monitoring.events.PY_RETURN,
                    monitoring.events.PY_UNWIND,
                ):
                    monitoring.register_callback(_TOOL_ID, event, None)
                monitoring.free_tool_id(_TOOL_ID)
            except Exception:
                with self.lock:
                    self.observer_errors += 1
            self._owned = False
        self.status = "finished" if self.reason is None else self.status


_observer: _TimingObserver | None = None


def pytest_configure(config: Any) -> None:
    """Enable the observer only when its output path is explicitly supplied."""
    global _observer
    output_value = os.environ.get("E02_REENTRY_TIMING_OUTPUT")
    if not output_value:
        return
    output = Path(output_value).expanduser()
    try:
        codes = _resolve_code_objects()
    except Exception as exc:
        observer = _TimingObserver({}, output)
        observer._unavailable(f"target resolution failed: {type(exc).__name__}: {exc}")
    else:
        observer = _TimingObserver(codes, output)
        observer.enable()
    observer.flush()
    _observer = observer
    try:
        config.pluginmanager.register(observer, "e02-candidate-reentry-timing")
    except Exception as exc:
        observer.cleanup()
        observer._unavailable(f"pytest plugin registration failed: {type(exc).__name__}: {exc}")
        observer.flush()


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Persist final measurements and release monitoring resources."""
    del session, exitstatus
    if _observer is not None:
        _observer.cleanup()
        _observer.flush()
