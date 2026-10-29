"""Bounded Python-code census and normal-exit origins for explicit witness processes.

Reuse C100's CPython 3.14 PY_START/DISABLE primitive: each non-target code
object dispatches once. Only selected owner code receives local return events.
Native calls, pre-start execution, abnormal exits and uninstrumented PIDs remain
unresolved. A completed census is independent of semantic test-oracle success.
"""

from __future__ import annotations

import ast
import atexit
import contextlib
import hashlib
import importlib.util
import json
import marshal
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from types import CodeType, FrameType, ModuleType
from typing import Any


class ActualCodeCapture:
    """Capture source-authenticated first-party code with bounded discovery cost.

    Attributes:
        root: Immutable-checkout root used to select first-party Python paths.
        index: Git blob identities created by source admission.
    """

    TOOL_ID = 3

    def __init__(self, root: Path, index: dict[str, str], output: Path) -> None:
        """Initialize a PID-local census without starting monitoring."""
        self.root = root.resolve()
        self.index = index
        self.output = output
        self.codes: dict[int, tuple[CodeType, dict[str, Any]]] = {}
        self.non_targets: dict[int, CodeType] = {}
        self.sources: dict[str, bytes] = {}
        self.source_identities: dict[str, dict[str, Any]] = {}
        self.compilations: dict[tuple[str, bool], list[CodeType]] = {}
        self.errors: list[dict[str, Any]] = []
        self.bindings: dict[int, tuple[object, object]] = {}
        self.callback_invocations = 0
        self.return_callbacks = 0
        self.targets: dict[int, CodeType] = {}
        self.target_predicate: Callable[[CodeType], bool] = lambda code: False
        self.return_consumer: Callable[[FrameType, object], None] | None = None
        self.assertion_config: Any = None
        self.compiler_identity: dict[str, Any] | None = None
        self.lock = threading.RLock()
        self.started = False

    def _error(self, reason: str, **details: object) -> None:
        self.errors.append({"reason": reason, "thread": threading.get_ident(), **details})

    def start(self) -> None:
        """Require the measured C100 runtime and an unused monitoring slot."""
        if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 14):
            raise RuntimeError("code_capture_requires_CPython_3_14")
        if sys.getprofile() is not None or threading.getprofile() is not None:
            raise RuntimeError("existing_profile_not_replaced")
        if sys.monitoring.get_tool(self.TOOL_ID) is not None:
            raise RuntimeError("monitoring_slot_already_owned")
        sys.monitoring.use_tool_id(self.TOOL_ID, "tc-sql-mc-bounded-code")
        events = sys.monitoring.events
        sys.monitoring.register_callback(self.TOOL_ID, events.PY_START, self._discover)
        sys.monitoring.register_callback(self.TOOL_ID, events.PY_RETURN, self._returned)
        self.started = True
        sys.monitoring.set_events(self.TOOL_ID, events.PY_START)

    def select_returns(
        self,
        predicate: Callable[[CodeType], bool],
        consumer: Callable[[FrameType, object], None],
        assertion_config: object,
    ) -> None:
        """Enable local returns for actual selected code, including earlier discoveries."""
        self.target_predicate = predicate
        self.return_consumer = consumer
        self.assertion_config = assertion_config
        for code in tuple(self.non_targets.values()):
            if predicate(code):
                self._enable_returns(code)
        for code, row in tuple(self.codes.values()):
            if predicate(code) and self._verify(code, row):
                self._enable_returns(code)

    def _enable_returns(self, code: CodeType) -> None:
        self.targets[id(code)] = code
        sys.monitoring.set_local_events(self.TOOL_ID, code, sys.monitoring.events.PY_RETURN)

    def _first_party(self, code: CodeType, frame: FrameType) -> bool:
        name = frame.f_globals.get("__name__", "")
        if isinstance(name, str) and any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in ("polisyos", "unit", "tests", "tools")
        ):
            return True
        # A foreign co_filename cannot hide a first-party module-origin claim.
        spec = frame.f_globals.get("__spec__")
        claims = (code.co_filename, frame.f_globals.get("__file__"), getattr(spec, "origin", None))
        for claim in claims:
            if not isinstance(claim, str):
                continue
            try:
                rel = Path(claim).resolve().relative_to(self.root).as_posix()
            except (OSError, ValueError):
                continue
            if rel.startswith(
                ("policy-engine/src/", "policy-engine/tests/", "policy-engine/tools/")
            ):
                return True
        return False

    def _entry(self, code: CodeType, frame: FrameType) -> dict[str, Any]:
        name = frame.f_globals.get("__name__")
        module = sys.modules.get(name)
        spec = frame.f_globals.get("__spec__")
        path = Path(code.co_filename)
        row: dict[str, Any] = {
            "filename": code.co_filename,
            "qualname": code.co_qualname,
            "module": name,
            "code_sha256": hashlib.sha256(marshal.dumps(code)).hexdigest(),
            "thread_ids": [threading.get_ident()],
            "source_read": "UNREAD",
            "native_calls": "unresolved_by_construction",
        }
        if not isinstance(module, ModuleType) or module.__dict__ is not frame.f_globals:
            row["origin_error"] = "module_globals_not_established"
        try:
            physical = path.resolve(strict=True)
            global_file = Path(frame.f_globals.get("__file__", "")).resolve(strict=True)
            origin = getattr(spec, "origin", None)
            script = name == "__main__" and spec is None
            if global_file != physical or (
                not script and (not origin or Path(origin).resolve(strict=True) != physical)
            ):
                row["origin_error"] = "actual_code_module_origin_mismatch"
            row["resolved_path"] = str(physical)
            key = str(physical)
            fresh = key not in self.sources
            if fresh:
                data = physical.read_bytes()
                self.sources[key] = data
                self.source_identities[key] = {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                    "git_blob": hashlib.sha1(
                        b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
                    ).hexdigest(),
                }
            identity = self.source_identities[key]
            row.update(
                source_read="READ" if fresh else "CACHED_BOUND_READ",
                source_sha256=identity["sha256"],
                source_bytes=identity["bytes"],
                source_read_receipt=key,
            )
            try:
                rel = physical.relative_to(self.root).as_posix()
            except ValueError:
                rel = None
            row["relative_path"] = rel
            if self._first_party(code, frame):
                # SHA-1 is only the Git identifier for the frozen source read.
                blob = identity["git_blob"]
                row.update(git_blob=blob, expected_blob=self.index.get(rel))
                if self.index.get(rel) != blob:
                    row["origin_error"] = "first_party_foreign_untracked_or_changed"
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            row.update(source_read="FAILED", source_read_error=type(exc).__name__)
        return row

    def _discover(self, code: CodeType, offset: int) -> object:
        del offset
        self.callback_invocations += 1
        frame = sys._getframe(1)
        if frame.f_code is not code:
            self._error("callback_frame_not_established")
            return sys.monitoring.DISABLE
        selected = self.target_predicate(code)
        if not selected and not self._first_party(code, frame):
            self.non_targets[id(code)] = code
            return sys.monitoring.DISABLE
        with self.lock:
            row = self._entry(code, frame)
            self.codes[id(code)] = (code, row)
            self.bindings[id(code)] = (
                sys.modules.get(frame.f_globals.get("__name__")),
                frame.f_globals,
            )
            if selected and self._verify(code, row):
                self._enable_returns(code)
        # PY_RETURN is local for targets; PY_START never repeats per code object.
        return sys.monitoring.DISABLE

    def _walk(self, code: CodeType) -> list[CodeType]:
        result = [code]
        for value in code.co_consts:
            if isinstance(value, CodeType):
                result.extend(self._walk(value))
        return result

    def _verify(self, code: CodeType, row: dict[str, Any]) -> bool:
        if row.get("origin_error") or row["source_read"] not in {"READ", "CACHED_BOUND_READ"}:
            row["compilation_match"] = False
            return False
        path = row["resolved_path"]
        flag = bool(
            self.assertion_config and self.assertion_config.getini("enable_assertion_pass_hook")
        )
        key = (path, flag)
        try:
            if key not in self.compilations:
                source = self.sources[path]
                candidates = self._walk(
                    compile(source, path, "exec", dont_inherit=True, optimize=sys.flags.optimize)
                )
                compiler = sys.modules.get("_pytest.assertion.rewrite")
                if compiler is not None and "/tests/" in path:
                    compiler_path = Path(compiler.__file__).resolve(strict=True)
                    self.compiler_identity = {
                        "path": str(compiler_path),
                        "sha256": hashlib.sha256(compiler_path.read_bytes()).hexdigest(),
                        "assertion_pass_hook": flag,
                    }
                    syntax = ast.parse(source, filename=path)
                    compiler.rewrite_asserts(syntax, source, path, self.assertion_config)
                    candidates.extend(
                        self._walk(
                            compile(
                                syntax, path, "exec", dont_inherit=True, optimize=sys.flags.optimize
                            )
                        )
                    )
                self.compilations[key] = candidates
            row["compilation_match"] = any(code == expected for expected in self.compilations[key])
        except Exception as exc:
            row.update(compilation_match=False, compilation_error=type(exc).__name__)
        return bool(row["compilation_match"])

    def _returned(self, code: CodeType, offset: int, value: object) -> None:
        del offset
        self.return_callbacks += 1
        frame = sys._getframe(1)
        entry = self.codes.get(id(code))
        if entry is None and frame.f_code is code:
            row = self._entry(code, frame)
            self.codes[id(code)] = (code, row)
            self.bindings[id(code)] = (
                sys.modules.get(frame.f_globals.get("__name__")),
                frame.f_globals,
            )
            if not self._verify(code, row):
                self._error("selected_return_origin_or_code_refused", qualname=code.co_qualname)
                return
            entry = self.codes[id(code)]
        if frame.f_code is not code or entry is None or entry[0] is not code:
            self._error("selected_return_code_not_captured")
            return
        row = entry[1]
        module, globals_identity = self.bindings[id(code)]
        if (
            frame.f_globals is not globals_identity
            or sys.modules.get(frame.f_globals.get("__name__")) is not module
        ):
            self._error("selected_return_module_globals_changed", qualname=code.co_qualname)
            return
        if sys.getprofile() is not None:
            self._error("selected_thread_private_profile_present")
            return
        if threading.get_ident() not in row["thread_ids"]:
            row["thread_ids"].append(threading.get_ident())
        if self.return_consumer is not None:
            try:
                self.return_consumer(frame, value)
            except Exception as exc:
                self._error("return_consumer_error", exception=type(exc).__name__)

    def stop(self) -> None:
        """Release global discovery and every locally enabled return event."""
        if self.started:
            sys.monitoring.set_events(self.TOOL_ID, 0)
            for code in self.targets.values():
                sys.monitoring.set_local_events(self.TOOL_ID, code, 0)
            sys.monitoring.free_tool_id(self.TOOL_ID)
            self.started = False

    def report(self) -> dict[str, Any]:
        """Reconcile actual captured code even when its module has since disappeared."""
        self.stop()
        rows = []
        for code, row in tuple(self.codes.values()):
            self._verify(code, row)
            rows.append(row)
        failures = [row for row in rows if not row.get("compilation_match")]
        return {
            "mechanism": "C100 CPython3.14 PY_START/DISABLE; selected local PY_RETURN",
            "pid": os.getpid(),
            "callback_invocations": self.callback_invocations,
            "distinct_captured_codes": len(rows),
            "distinct_disabled_non_targets": len(self.non_targets),
            "selected_return_callbacks": self.return_callbacks,
            "code_census_complete_for_observed_events": not failures and not self.errors,
            "codes": rows,
            "errors": self.errors,
            "assertion_compiler": self.compiler_identity,
            "source_reads": self.source_identities,
            "unresolved_by_construction": [
                "pre_start_execution",
                "post_stop_execution",
                "native_calls",
                "OS_device_reads",
                "uninstrumented_or_abnormally_exiting_PIDs",
                "semantic_test_oracles",
                "selected_owner_unwind_events",
            ],
        }


def _snapshot_origins(root: Path, index: dict[str, str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    # Freeze membership before iterating: background imports may mutate sys.modules.
    modules = tuple(sys.modules.items())
    for name, module in sorted(modules):
        if module is None:
            continue
        project = any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in ("polisyos", "unit", "tests", "tools")
        )
        try:
            raw = getattr(module, "__file__", None)
            paths = list(getattr(module, "__path__", ()) or ())
        except Exception as exc:
            if project:
                entries.append(
                    {
                        "module": name,
                        "verdict": "project_origin_attribute_error",
                        "exception": type(exc).__name__,
                    }
                )
            continue
        if raw is None and not project:
            continue
        row: dict[str, Any] = {
            "module": name,
            "file": str(raw) if raw else None,
            "namespace_paths": [str(p) for p in paths],
        }
        if raw:
            path = Path(raw)
            if path.suffix == ".pyc":
                with contextlib.suppress(ValueError):
                    path = Path(importlib.util.source_from_cache(str(path)))
            try:
                physical = path.resolve(strict=True)
                rel = physical.relative_to(root).as_posix()
                if not rel.startswith(
                    ("policy-engine/src/", "policy-engine/tests/", "policy-engine/tools/")
                ):
                    if not project:
                        continue
                    raise ValueError("foreign_project_origin")
                data = physical.read_bytes()
                blob = hashlib.sha1(
                    b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
                ).hexdigest()
                row.update(
                    relative_path=rel,
                    sha256=hashlib.sha256(data).hexdigest(),
                    bytes=len(data),
                    git_blob=blob,
                    expected_blob=index.get(rel),
                    verdict="MATCH" if index.get(rel) == blob else "MISMATCH_OR_UNTRACKED",
                )
            except (OSError, ValueError, RuntimeError) as exc:
                if not project:
                    continue
                row.update(
                    verdict="foreign_or_unreadable_project_origin", exception=type(exc).__name__
                )
            entries.append(row)
        elif project:
            try:
                valid = bool(paths) and all(
                    Path(p).resolve(strict=True).is_relative_to(root / "policy-engine")
                    for p in paths
                )
            except (OSError, RuntimeError):
                valid = False
            row["verdict"] = (
                "NAMESPACE_IN_CHECKOUT" if valid else "foreign_or_unreadable_project_origin"
            )
            entries.append(row)
    return entries


CAPTURE: ActualCodeCapture | None = None
if os.environ.get("E02C_OUT") and os.environ.get("E02C_ROOT") and os.environ.get("E02C_INDEX"):
    _ROOT = Path(os.environ["E02C_ROOT"]).resolve()
    _OUT = Path(os.environ["E02C_OUT"])
    _PHASE = os.environ.get("E02C_PHASE", "unknown")
    _INDEX = json.loads(Path(os.environ["E02C_INDEX"]).read_bytes())
    CAPTURE = ActualCodeCapture(_ROOT, _INDEX, _OUT)
    CAPTURE.start()

    def _finish() -> None:
        assert CAPTURE is not None
        payload = {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "phase": _PHASE,
            "executable": sys.executable,
            "entries": _snapshot_origins(_ROOT, _INDEX),
            "actual_code_capture": CAPTURE.report(),
            "boundary": "normally exiting PID; actual PY_START code since startup plus final module-origin snapshot; native and absent PIDs remain unresolved",
        }
        target = _OUT / "origins" / f"{_PHASE}-{os.getpid()}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Compact source-generated output; individual deterministic gzip if needed later.
        target.write_text(json.dumps(payload, sort_keys=True) + "\n")

    atexit.register(_finish)
