"""Optional, bounded timing for candidate-experiment reentry owner methods.

Enable with ``-p tests._helpers.candidate_reentry_timing`` and set
``E02_REENTRY_TIMING_OUTPUT`` to a JSON file in an existing run directory.
The default ``candidate_reentry`` profile preserves the original target set;
``E02_REENTRY_TIMING_PROFILE=generic_model_input_owner`` opts into a finite
profile for the model-input job and candidate-experiment owner path. Only
listed Python code objects receive local start/return events. Python unwind is
not locally selectable on the supported interpreter, so its callback is global
and immediately filters by code-object identity. Its observed handler time is
reported; no zero-overhead assumption is made. Target durations are inclusive:
wrapper and nested rows overlap and must not be summed as wall time.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TOOL_ID = 4
_TOOL_NAME = "e02-candidate-reentry-timing"


@dataclass(frozen=True, slots=True)
class _TargetSpec:
    """One exact module/class function target, optionally a nested code object."""

    label: str
    module_name: str
    owner_name: str | None
    function_name: str
    nested_function_name: str | None = None
    unwrap_decorator: bool = False


_TARGETS: tuple[_TargetSpec, ...] = (
    _TargetSpec(
        "acquisition_bridge.source_reentry_preflight",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "candidate_experiment_source_reentry_preflight",
    ),
    _TargetSpec(
        "acquisition_bridge.reconcile_reentry_budget",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "_reconcile_candidate_experiment_source_reentry_budget",
    ),
    _TargetSpec(
        "acquisition_bridge.prior_owner",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "_candidate_experiment_prior_owner",
    ),
    _TargetSpec(
        "candidate_action.current_action",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_current_candidate_experiment_action",
    ),
    _TargetSpec(
        "candidate_action.reentry_action",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_current_candidate_experiment_reentry_action",
    ),
    _TargetSpec(
        "candidate_action.select_outcome",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_select_current_candidate_experiment_outcome",
    ),
    _TargetSpec(
        "route_loop.resolve_reentry",
        "polisyos.runtime.quality.acquisition_route_loop",
        "AcquisitionRouteLoop",
        "_resolve_current_candidate_experiment_resolution",
    ),
)

_GENERIC_MODEL_INPUT_OWNER_TARGETS: tuple[_TargetSpec, ...] = (
    _TargetSpec(
        "model_input.handle_job",
        "polisyos.runtime.http.services.acquisition_action_service",
        "AcquisitionActionService",
        "handle_job",
    ),
    _TargetSpec(
        "model_input.handle_model_input_job",
        "polisyos.runtime.http.services.acquisition_action_service",
        "AcquisitionActionService",
        "_handle_model_input_use_job",
    ),
    _TargetSpec(
        "model_input.handle_job_currentness",
        "polisyos.runtime.http.services.acquisition_action_service",
        "AcquisitionActionService",
        "_handle_model_input_use_job",
        nested_function_name="require_current_action",
    ),
    _TargetSpec(
        "model_input.run_n5",
        "polisyos.runtime.http.services.model_input_successor_action",
        None,
        "_run_model_input_use_n5",
    ),
    _TargetSpec(
        "model_input.run_n5_currentness",
        "polisyos.runtime.http.services.model_input_successor_action",
        None,
        "_run_model_input_use_n5",
        nested_function_name="require_current_action",
    ),
    _TargetSpec(
        "candidate_evaluation.revalidate_wrapper",
        "polisyos.runtime.quality.acquisition_evaluation_dispatch",
        "CandidateExperimentEvaluationCurrentOwner",
        "revalidate",
    ),
    _TargetSpec(
        "candidate_evaluation.currentness_resolver",
        "polisyos.runtime.quality.acquisition_evaluation_dispatch",
        "CandidateExperimentEvaluationCurrentOwner",
        "currentness_resolver",
    ),
    _TargetSpec(
        "candidate_evaluation.revalidate_owner",
        "polisyos.runtime.quality.acquisition_evaluation_dispatch",
        None,
        "_revalidate_candidate_experiment_evaluation_owner",
    ),
    _TargetSpec(
        "candidate_action.reentry_context",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_current_candidate_experiment_reentry_action_context",
    ),
    _TargetSpec(
        "candidate_action.current_context",
        "polisyos.runtime.quality.candidate_acquisition_action",
        None,
        "_current_candidate_experiment_action_context",
    ),
    _TargetSpec(
        "candidate_route.resolve_reentry",
        "polisyos.runtime.quality.acquisition_route_loop",
        "AcquisitionRouteLoop",
        "_resolve_current_candidate_experiment_resolution",
    ),
    _TargetSpec(
        "candidate_route.experiment_action_outcomes",
        "polisyos.runtime.http.services.control.run_lifecycle",
        "AcquisitionRouteLoopAuthoritySink",
        "experiment_action_outcomes",
        unwrap_decorator=True,
    ),
    _TargetSpec(
        "candidate_prior.owner",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "_candidate_experiment_prior_owner",
    ),
    _TargetSpec(
        "candidate_prior.selected_evaluation_parts",
        "polisyos.runtime.quality.acquisition_evaluation",
        None,
        "resolve_selected_acquisition_evaluation_parts",
    ),
    _TargetSpec(
        "candidate_basis.prepare_live",
        "polisyos.runtime.quality.candidate_source_basis",
        None,
        "prepare_live_candidate_experiment_source_basis_values",
    ),
    _TargetSpec(
        "candidate_basis.prepare_values",
        "polisyos.runtime.quality.candidate_source_basis",
        None,
        "prepare_candidate_source_basis_values",
    ),
    _TargetSpec(
        "candidate_basis.verify_actual_world",
        "polisyos.runtime.quality.candidate_source_basis",
        None,
        "_verify_actual_world",
    ),
    _TargetSpec(
        "candidate_handoff.compose",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "_candidate_source_context_handoff",
    ),
    _TargetSpec(
        "candidate_handoff.currentness_callback",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "_candidate_source_context_handoff",
        nested_function_name="currentness_resolver",
    ),
    _TargetSpec(
        "candidate_handoff.verify_wrapper",
        "polisyos.runtime.quality.acquisition_world_growth",
        "AcquisitionWorldGrowthBridge",
        "verify_candidate_source_context_handoff",
    ),
    _TargetSpec(
        "candidate_reentry.prepare_owner",
        "polisyos.runtime.quality.acquisition_evaluation_dispatch",
        None,
        "prepare_candidate_experiment_reentry_owner",
    ),
    _TargetSpec(
        "candidate_reentry.revalidate_owner",
        "polisyos.runtime.quality.acquisition_evaluation_dispatch",
        None,
        "_revalidate_candidate_experiment_reentry_owner",
    ),
    _TargetSpec(
        "foundry.prepare_input_bindings",
        "polisyos.foundry.data_plane.bindings",
        None,
        "prepare_input_bindings",
    ),
)

_PROFILES: dict[str, tuple[_TargetSpec, ...]] = {
    "candidate_reentry": _TARGETS,
    "generic_model_input_owner": _GENERIC_MODEL_INPUT_OWNER_TARGETS,
}


def _declared_target_code(spec: _TargetSpec, module: types.ModuleType) -> types.CodeType:
    """Resolve one exact function or nested function code object statically."""
    if spec.owner_name is None:
        target: Any = vars(module).get(spec.function_name)
    else:
        owner = vars(module).get(spec.owner_name)
        if not isinstance(owner, type) or type(owner) is not type:
            raise LookupError(f"declared timing owner is not a native class: {spec.owner_name}")
        namespace = type.__dict__["__dict__"].__get__(owner, type)
        target = namespace.get(spec.function_name)
    if type(target) is not types.FunctionType:
        raise LookupError(f"declared timing target is not a function: {spec.label}")
    if spec.unwrap_decorator:
        target = vars(target).get("__wrapped__")
        if type(target) is not types.FunctionType:
            raise LookupError(
                f"declared timing target has no static wrapped function: {spec.label}"
            )
    code = target.__code__
    if spec.nested_function_name is not None:
        nested = tuple(
            value
            for value in code.co_consts
            if type(value) is types.CodeType and value.co_name == spec.nested_function_name
        )
        if len(nested) != 1:
            raise LookupError(f"declared nested timing target is not unique: {spec.label}")
        code = nested[0]
        expected_qualname = f"{target.__code__.co_qualname}.<locals>.{spec.nested_function_name}"
        if code.co_qualname != expected_qualname:
            raise LookupError(f"declared nested timing target changed: {spec.label}")
    if code.co_flags & (0x20 | 0x80 | 0x200):
        raise TypeError(f"declared timing target is not synchronous: {spec.label}")
    return code


def _resolve_code_objects(
    targets: tuple[_TargetSpec, ...] = _TARGETS,
) -> tuple[dict[str, types.CodeType], dict[str, str]]:
    """Resolve only declared code objects and retain soft per-target failures."""
    resolved: dict[str, types.CodeType] = {}
    modules: dict[str, types.ModuleType] = {}
    module_errors: dict[str, str] = {}
    failures: dict[str, str] = {}
    for spec in targets:
        try:
            if spec.module_name in module_errors:
                raise LookupError(module_errors[spec.module_name])
            module = modules.get(spec.module_name)
            if module is None:
                try:
                    module = importlib.import_module(spec.module_name)
                except Exception as exc:
                    reason = f"{type(exc).__name__}: {exc}"
                    module_errors[spec.module_name] = reason
                    raise LookupError(f"module unavailable: {reason}") from exc
                modules[spec.module_name] = module
            resolved[spec.label] = _declared_target_code(spec, module)
        except Exception as exc:
            failures[spec.label] = f"{type(exc).__name__}: {exc}"
    return resolved, failures


class _TimingObserver:
    """Observe selected code-object durations without inspecting call values."""

    def __init__(
        self,
        codes: dict[str, types.CodeType],
        output: Path,
        *,
        profile: str = "candidate_reentry",
        resolution_failures: dict[str, str] | None = None,
    ) -> None:
        self.codes = codes
        self.output = output
        self.profile = profile
        self.resolution_failures = dict(resolution_failures or {})
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
        self.cleanup_status = "not_started"
        self.cleanup_errors: list[str] = []
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
        if not self.codes:
            return self._unavailable("no declared timing target code objects resolved")
        monitoring = getattr(sys, "monitoring", None)
        if monitoring is None:
            return self._unavailable("sys.monitoring is unavailable")
        events = monitoring.events
        if monitoring.get_tool(_TOOL_ID) is not None or monitoring.get_events(_TOOL_ID):
            return self._unavailable("monitoring tool ID 4 is already occupied")
        if any(monitoring.get_local_events(_TOOL_ID, code) for code in self.codes.values()):
            return self._unavailable("tool ID 4 has pre-existing local events")
        try:
            monitoring.use_tool_id(_TOOL_ID, _TOOL_NAME)
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
                "profile": self.profile,
                "status": self.status,
                "reason": self.reason,
                "cleanup_status": self.cleanup_status,
                "cleanup_errors": list(self.cleanup_errors),
                "target_resolution": (
                    "unavailable"
                    if not self.codes
                    else "partial"
                    if self.resolution_failures
                    else "complete"
                ),
                "resolution_failures": dict(self.resolution_failures),
                "timing_semantics": (
                    "inclusive per-target wall time; wrapper and nested target rows overlap "
                    "and must not be summed as wall time"
                ),
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
        if monitoring is None:
            if self._owned:
                self.cleanup_status = "partial"
                self.cleanup_errors.append("sys.monitoring unavailable during cleanup")
                self.status = "instrumentation_cleanup_failed"
                if self.reason is None:
                    self.reason = self.cleanup_errors[-1]
                self.observer_errors += 1
            elif self.cleanup_status == "not_started":
                self.cleanup_status = "not_owned"
                if self.reason is None:
                    self.status = "finished"
            return
        if not self._owned:
            if self.cleanup_status == "not_started":
                self.cleanup_status = "not_owned"
            if self.reason is None:
                self.status = "finished"
            return

        ownership_changed = False

        def run_if_owned(operation: str, action: Any) -> None:
            """Run one cleanup action only while tool 4 still belongs to us."""
            nonlocal ownership_changed
            try:
                owner = monitoring.get_tool(_TOOL_ID)
            except Exception as exc:
                self.cleanup_errors.append(
                    f"check ownership before {operation}: {type(exc).__name__}: {exc}"
                )
                return
            if owner != _TOOL_NAME:
                ownership_changed = True
                return
            try:
                action()
            except Exception as exc:
                self.cleanup_errors.append(f"{operation}: {type(exc).__name__}: {exc}")

        for code in self._enabled_local:
            run_if_owned(
                f"clear local events for {code.co_qualname}",
                lambda code=code: monitoring.set_local_events(_TOOL_ID, code, 0),
            )
        run_if_owned("clear global events", lambda: monitoring.set_events(_TOOL_ID, 0))
        for event in self._callbacks:
            run_if_owned(
                f"clear callback for event {event}",
                lambda event=event: monitoring.register_callback(_TOOL_ID, event, None),
            )
        run_if_owned("free tool ID", lambda: monitoring.free_tool_id(_TOOL_ID))

        try:
            final_owner = monitoring.get_tool(_TOOL_ID)
        except Exception as exc:
            final_owner = _TOOL_NAME
            self.cleanup_errors.append(f"check final ownership: {type(exc).__name__}: {exc}")
        self._owned = final_owner == _TOOL_NAME
        if self._owned:
            self.cleanup_status = "partial"
            self.cleanup_errors.append("tool ID 4 still owned after cleanup")
        elif ownership_changed or final_owner not in (None, _TOOL_NAME):
            self.cleanup_status = "ownership_changed"
        elif self.cleanup_errors:
            self.cleanup_status = "completed_with_errors"
        else:
            self.cleanup_status = "complete"

        if self.cleanup_errors or ownership_changed:
            self.status = "instrumentation_cleanup_failed"
            if self.reason is None:
                details = "; ".join(self.cleanup_errors)
                if ownership_changed:
                    details = "; ".join(filter(None, (details, "tool ID 4 ownership changed")))
                self.reason = details or "tool ID 4 ownership changed during cleanup"
            self.observer_errors += len(self.cleanup_errors) or 1
        elif self.reason is None:
            self.status = "finished"


_observer: _TimingObserver | None = None


def pytest_configure(config: Any) -> None:
    """Enable the observer only when its output path is explicitly supplied."""
    global _observer
    output_value = os.environ.get("E02_REENTRY_TIMING_OUTPUT")
    if not output_value:
        return
    output = Path(output_value).expanduser()
    profile = os.environ.get("E02_REENTRY_TIMING_PROFILE", "candidate_reentry")
    targets = _PROFILES.get(profile)
    if targets is None:
        failures = {"<profile>": f"unknown profile {profile!r}; available={tuple(_PROFILES)}"}
        observer = _TimingObserver(
            {},
            output,
            profile=profile,
            resolution_failures=failures,
        )
        observer._unavailable("no declared timing target profile selected")
    else:
        codes, failures = _resolve_code_objects(targets)
        observer = _TimingObserver(
            codes,
            output,
            profile=profile,
            resolution_failures=failures,
        )
        if codes:
            observer.enable()
        else:
            observer._unavailable("no declared timing target code objects resolved")
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
