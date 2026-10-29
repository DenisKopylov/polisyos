"""Pytest session/owner-observation plugin; never changes product functions."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from types import CodeType, FrameType
from typing import Any

import pytest
from sitecustomize import CAPTURE

_ROOT = Path(os.environ["E02C_ROOT"]).resolve()
_OUT = Path(os.environ["E02C_OUT"])
_PHASE = os.environ["E02C_PHASE"]
_EVENTS = []
_ITEMS = []
_REPORTS = []
_COLLECTION_COMPARISON = None
_LOCK = threading.Lock()


def _json_value(value: object) -> Any:
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, (tuple, list)):
        return [_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    return str(value)


def _record_return(frame: FrameType, arg: object) -> None:
    code = frame.f_code
    name = code.co_name
    filename = code.co_filename.replace("\\", "/")
    item = None
    try:
        if name == "test_in_place_config_aba_cannot_change_driver_database" and filename.endswith(
            "/tests/unit/fabric/test_registered_sql_capture.py"
        ):
            values = frame.f_locals
            result = values.get("actual")
            data = getattr(result, "data", None)
            item = {
                "oracle": "sql_aba",
                "opened_paths": _json_value(values.get("actual_paths")),
                "driver_queries": _json_value(values.get("driver_queries")),
                "data_rows": _json_value(data["income"].tolist()) if data is not None else None,
            }
        elif name in (
            "test_actual_workflow_creation_reopens_sql_history_and_current_use",
            "test_workflow_refuses_admitted_source_for_a_different_use",
        ) and filename.endswith("/tests/unit/scientist/adapters/test_registered_sql_snapshot.py"):
            values = frame.f_locals

            def error_code(key: str) -> str | None:
                info = values.get(key)
                return (
                    getattr(getattr(info, "value", None), "code", None)
                    if info is not None
                    else None
                )

            item = {
                "oracle": name,
                "persisted_inputs": _json_value(values.get("inputs")),
                "bad_history_code": error_code("bad_history"),
                "withdrawn_code": error_code("withdrawn"),
                "wrong_purpose_code": error_code("refused"),
            }
        elif (
            name == "test_refused_sampling_law_precedes_irrelevant_binding_and_never_evaluates"
            and filename.endswith("/tests/unit/foundry/uncertainty/test_joint_law_admission.py")
        ):
            values = frame.f_locals
            result = values.get("result")
            envelope = getattr(result, "envelope", None)
            item = {
                "oracle": "mc_refusal",
                "route": values.get("route"),
                "fault": values.get("fault"),
                "kind": values.get("kind"),
                "failure": values.get("failure"),
                "calls": len(values.get("calls", ())),
                "signature_reads": len(values.get("signature_reads", ())),
                "diagnostics": _json_value(getattr(result, "diagnostics", None)),
                "metadata": _json_value(getattr(envelope, "metadata", None)),
                "gate_eligible": getattr(envelope, "gate_eligible", None),
            }
        elif (
            name == "get_result"
            and filename.endswith(
                "/tests/integration/runtime/http/test_registered_sql_live_grant.py"
            )
            and isinstance(arg, dict)
        ):
            item = {
                "oracle": "served_debug",
                "artifact_ref": _json_value(arg.get("artifact_ref")),
                "source_use": _json_value(arg.get("exante_source_use")),
                "simulation_result": _json_value(arg.get("simulation_result")),
            }
        elif (
            name == "request"
            and filename.endswith("/httpx/_client.py")
            and getattr(arg, "status_code", None) is not None
        ):
            request = getattr(arg, "request", None)
            item = {
                "oracle": "http_response",
                "status": getattr(arg, "status_code", None),
                "path": getattr(getattr(request, "url", None), "path", None),
            }
        elif name == "read_registered_sql_source_use" and filename.endswith(
            "/runtime/http/services/debug_registered_sql.py"
        ):
            item = {
                "owner": name,
                "status": getattr(arg, "status", None),
                "reason_codes": _json_value(getattr(arg, "reason_codes", None)),
                "recomputed_mean_change": getattr(arg, "recomputed_mean_change", None),
            }
        elif name == "read_source_current_use" and filename.endswith(
            "/scientist/validation/decision_validity.py"
        ):
            item = {
                "owner": name,
                "status": getattr(arg, "status", None),
                "generation": getattr(arg, "generation", None),
                "basis_digest": getattr(arg, "basis_digest", None),
                "reason_codes": _json_value(getattr(arg, "reason_codes", None)),
            }
        elif name == "dispatch_once" and filename.endswith(
            "/runtime/http/services/control_worker.py"
        ):
            item = {"owner": name, "returned": _json_value(arg)}
        elif (
            name == "issue_debug_execution_input_identity"
            and filename.endswith("/runtime/quality/owned_execution_identity.py")
            and isinstance(arg, tuple)
            and len(arg) == 2
        ):
            closure = arg[0]
            members = getattr(closure, "members", ())
            item = {
                "owner": name,
                "closure_sha256": getattr(closure, "closure_sha256", None),
                "run_id": getattr(closure, "run_id", None),
                "job_id": getattr(closure, "job_id", None),
                "roles": [getattr(m, "role", None) for m in members],
                "restricted_execution": [
                    _json_value(getattr(m, "value", None))
                    for m in members
                    if getattr(m, "name", None) == "restricted_execution"
                ],
            }
        if item is not None:
            item["pid"] = os.getpid()
            item["thread"] = threading.get_ident()
            with _LOCK:
                _EVENTS.append(item)
    except Exception as exc:
        with _LOCK:
            _EVENTS.append(
                {"owner": name, "observer_error": type(exc).__name__, "pid": os.getpid()}
            )


def _selected_return(code: CodeType) -> bool:
    """Select the existing semantic owner/test return predicates, never all calls."""
    filename = code.co_filename.replace("\\", "/")
    pairs = (
        (
            "test_in_place_config_aba_cannot_change_driver_database",
            "/tests/unit/fabric/test_registered_sql_capture.py",
        ),
        (
            "test_actual_workflow_creation_reopens_sql_history_and_current_use",
            "/tests/unit/scientist/adapters/test_registered_sql_snapshot.py",
        ),
        (
            "test_workflow_refuses_admitted_source_for_a_different_use",
            "/tests/unit/scientist/adapters/test_registered_sql_snapshot.py",
        ),
        (
            "test_refused_sampling_law_precedes_irrelevant_binding_and_never_evaluates",
            "/tests/unit/foundry/uncertainty/test_joint_law_admission.py",
        ),
        ("get_result", "/tests/integration/runtime/http/test_registered_sql_live_grant.py"),
        ("request", "/httpx/_client.py"),
        ("read_registered_sql_source_use", "/runtime/http/services/debug_registered_sql.py"),
        ("read_source_current_use", "/scientist/validation/decision_validity.py"),
        ("dispatch_once", "/runtime/http/services/control_worker.py"),
        ("issue_debug_execution_input_identity", "/runtime/quality/owned_execution_identity.py"),
    )
    return any(code.co_name == name and filename.endswith(suffix) for name, suffix in pairs)


def pytest_configure(config: pytest.Config) -> None:
    """Attach bounded owner returns to the startup first-party code census."""
    if CAPTURE is None or not CAPTURE.started:
        raise pytest.UsageError("startup_actual_code_capture_missing")
    if _PHASE in {"served", "sql_aba", "sql_workflow", "sql_purpose", "mc_refusal"}:
        CAPTURE.select_returns(_selected_return, _record_return, config)
    else:
        CAPTURE.assertion_config = config


def pytest_collection_finish(session: pytest.Session) -> None:
    """Bind actual ordered collection to the complete frozen expected node set."""
    global _COLLECTION_COMPARISON
    _ITEMS.extend(item.nodeid for item in session.items)
    expected = json.loads((_OUT / "pins.json").read_text())["expected_nodes"][_PHASE]
    _COLLECTION_COMPARISON = {
        "expected_count": len(expected),
        "actual_count": len(_ITEMS),
        "exact_order_match": expected == _ITEMS,
        "missing": sorted(set(expected) - set(_ITEMS)),
        "unexpected": sorted(set(_ITEMS) - set(expected)),
    }
    if expected != _ITEMS:
        raise pytest.UsageError(
            "source_collection_mismatch:" + json.dumps(_COLLECTION_COMPARISON, sort_keys=True)
        )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record separate setup/call/teardown semantic outcomes."""
    _REPORTS.append(
        {
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "duration_seconds": report.duration,
        }
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Retain semantic evidence separately from the normal-exit code census."""
    if CAPTURE is not None:
        CAPTURE.stop()
    config = session.config
    plugins = []
    for name, plugin in config.pluginmanager.list_name_plugin():
        module = getattr(plugin, "__module__", getattr(plugin, "__name__", None))
        filename = getattr(plugin, "__file__", None)
        plugins.append(
            {
                "name": str(name),
                "module": str(module) if module else None,
                "file": str(filename) if filename else None,
            }
        )
    payload = {
        "phase": _PHASE,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "argv": list(config.invocation_params.args),
        "rootpath": str(config.rootpath),
        "inipath": str(config.inipath) if config.inipath else None,
        "exitstatus": int(exitstatus),
        "collection": _ITEMS,
        "collection_comparison": _COLLECTION_COMPARISON,
        "reports": _REPORTS,
        "plugins": plugins,
        "owner_events": _EVENTS,
        "bounded_code_capture": {
            "origin_file": f"origins/{_PHASE}-{os.getpid()}.json",
            "completion": "normal_exit_receipt_required",
            "captured_codes_at_sessionfinish": len(CAPTURE.codes) if CAPTURE else None,
            "discovery_callbacks": CAPTURE.callback_invocations if CAPTURE else None,
            "return_callbacks": CAPTURE.return_callbacks if CAPTURE else None,
        },
        "limits": "Bounded local monitoring return callbacks are observational and cover named test/owner/HTTP calls in the pytest PID and existing or subsequently created threads; partial locals on failure are not a passing oracle. No world/provider authority or whole-program readset is claimed.",
    }
    path = _OUT / "observations" / f"{_PHASE}-pytest-{os.getpid()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
