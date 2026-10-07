"""One-test N8 property-removal probe that recognizes the typed guard refusal.

It removes only the persisted K_sim merge in memory, then observes the exact
ValuePortObservation validation failure on the real N5-to-CAS-to-default-N8 path.
It does not edit production source or tests.
"""
from __future__ import annotations

import ast
import functools
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

TARGET_NODE = (
    "tests/unit/runtime/quality/test_generation_cycle.py::"
    "test_n8_recovers_persisted_candidate_only_blocker_after_lossy_projection"
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_REL = Path("src/polisyos/runtime/quality/generation_cycle.py")
TEST_REL = Path("tests/unit/runtime/quality/test_generation_cycle.py")
EXPECTED_RUNTIME_SHA256 = "a1b87490e228fc9364ef77955bb0d911eaa4571e093ee7183108d91b37681f6b"
EXPECTED_TEST_SHA256 = "d3dcd61ca85d388f346d3a6fbecfac15163c7ad0cdfe92db86c3c7ae66820b04"
EXPECTED_FUNCTION_SHA256 = "45a00dcb9ca34fdaebf5de0a00c128149bad82864c820e6d0ce281601d86d1fb"
EXPECTED_TARGET_FUNCTION_AST_SHA256 = "e67818e51a55d5a6771121960f0011a15c3fb989509a9781f8acbea042a6be19"
EXPECTED_CANDIDATE_SHA = "3ba1deaa55c54971c3200269dc1c81680e3d7167"
EXPECTED_CANDIDATE_TREE = "abe1c8ae7ec1aa81a82cfc48dc07a8b5db3bc033"
BLOCKER = "simulation_only_k_sim_not_world_evidence"
NEEDLE = "    blockers.update(persisted_blockers)\n"
REPLACEMENT = (
    '    blockers.update(persisted_blockers - {"simulation_only_k_sim_not_world_evidence"})\n'
)
QUALIFICATION_PATH = Path(__file__).with_name("qualification.json")

_STATE: dict[str, Any] = {
    "active": False,
    "events": {
        "n5_producer_calls": [],
        "default_n8_calls": [],
        "n8_cas_reads": [],
        "test_cas_readbacks": [],
    },
    "reports": [],
    "preflight": {},
    "restorers": [],
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _git_revision(expression: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", expression], cwd=PROJECT_ROOT, text=True
    ).strip()


def _function_source_sha256(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = next(
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )
    lines = source.splitlines(keepends=True)
    return _sha256("".join(lines[node.lineno - 1 : node.end_lineno]).encode())


def _target_test_details(source: str) -> tuple[str, int, str]:
    tree = ast.parse(source)
    target = next(
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "test_n8_recovers_persisted_candidate_only_blocker_after_lossy_projection"
    )
    target_ast_sha256 = _sha256(ast.dump(target, include_attributes=False).encode())
    expected_test = ast.parse(
        'assert "simulation_only_k_sim_not_world_evidence" in value.authority_blockers'
    ).body[0].test
    wanted = ast.dump(expected_test, include_attributes=False)
    assertions = [
        node for node in ast.walk(target)
        if isinstance(node, ast.Assert)
        and ast.dump(node.test, include_attributes=False) == wanted
    ]
    if len(assertions) != 1:
        raise pytest.UsageError(
            "N8 property-removal target must contain exactly one assertion on the value blocker"
        )
    assertion = assertions[0]
    expression = ast.get_source_segment(source, assertion.test)
    if expression is None:
        raise pytest.UsageError("N8 target value-blocker assertion source is unavailable")
    return target_ast_sha256, assertion.lineno, expression


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_safe(v) for v in value]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return _safe(dump(mode="json"))
        except TypeError:
            return _safe(dump())
    attrs = {}
    for name in ("artifact_id", "artifact_type", "content_hash", "schema_version"):
        if hasattr(value, name):
            attrs[name] = _safe(getattr(value, name))
    return attrs or repr(value)


def _ref_key(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"))


def _blockers(value: Any) -> list[str]:
    result = getattr(value, "authority_blockers", ())
    return sorted(str(item) for item in result)


def _packet_blockers(result: Any) -> list[str]:
    packet = getattr(result, "promotion_ready_value_packet", {}) or {}
    if not isinstance(packet, dict):
        return []
    return sorted(str(item) for item in packet.get("authority_blockers", ()))


def _runtime_guard_details(source: str) -> tuple[int, int]:
    tree = ast.parse(source)
    conditional = next(
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "_conditional_simulation_value_observation"
    )
    constructors = [
        node for node in ast.walk(conditional)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ValuePortObservation"
    ]
    if len(constructors) != 1:
        raise pytest.UsageError("N8 conditional path must have one typed value-carrier constructor")

    carrier = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ValuePortObservation"
    )
    validator = next(
        n for n in carrier.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "_verify_value_authority_shape"
    )
    guard_raises = []
    for node in ast.walk(validator):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        if not isinstance(node.exc.func, ast.Name) or node.exc.func.id != "ValueError":
            continue
        if node.exc.args and isinstance(node.exc.args[0], ast.Constant):
            if node.exc.args[0].value == "value_conditional_requires_simulation_limitation":
                guard_raises.append(node)
    if len(guard_raises) != 1:
        raise pytest.UsageError("ValuePortObservation limitation guard is absent or ambiguous")
    return constructors[0].lineno, guard_raises[0].lineno


def _validation_details(
    exc: BaseException,
    *,
    runtime_path: Path,
    constructor_line: int,
    guard_line: int,
) -> dict[str, Any]:
    errors_method = getattr(exc, "errors", None)
    errors = []
    if callable(errors_method):
        try:
            errors = errors_method(include_url=False, include_context=True, include_input=True)
        except TypeError:
            errors = errors_method()
        except Exception:
            errors = []
    summaries = []
    for error in errors:
        raw_input = error.get("input")
        input_summary = {}
        if isinstance(raw_input, dict):
            input_summary = {
                field: _safe(raw_input.get(field))
                for field in (
                    "status",
                    "candidate_id",
                    "value_ref",
                    "authority_blockers",
                    "evaluation_mode",
                    "decision_grade",
                    "world_model_record_content_hash",
                )
                if field in raw_input
            }
        context = error.get("ctx") or {}
        context_error = context.get("error")
        summaries.append(
            {
                "type": error.get("type"),
                "loc": _safe(error.get("loc", ())),
                "msg": error.get("msg"),
                "context_error": str(context_error) if context_error is not None else None,
                "input_summary": input_summary,
                "input_fields": sorted(str(key) for key in raw_input) if isinstance(raw_input, dict) else None,
            }
        )
    header = str(exc).splitlines()[0] if str(exc).splitlines() else ""
    model_name = header.rsplit(" for ", 1)[-1] if " for " in header else None
    frames = traceback.extract_tb(exc.__traceback__)
    n8_frames = [
        {"file": frame.filename, "line": frame.lineno, "function": frame.name}
        for frame in frames
        if Path(frame.filename).resolve() == runtime_path
        and frame.name == "_conditional_simulation_value_observation"
    ]
    constructor_hit = any(frame["line"] == constructor_line for frame in n8_frames)
    guard_code = "value_conditional_requires_simulation_limitation"
    exact_error = (
        isinstance(exc, PydanticValidationError)
        and type(exc).__name__ == "ValidationError"
        and type(exc).__module__ == "pydantic_core._pydantic_core"
        and model_name == "ValuePortObservation"
        and len(summaries) == 1
        and summaries[0]["type"] == "value_error"
        and guard_code in str(summaries[0]["msg"])
        and guard_code in str(summaries[0]["context_error"])
        and summaries[0]["input_summary"].get("status") == "value_conditional"
        and constructor_hit
    )
    return {
        "exception_class": type(exc).__name__,
        "exception_module": type(exc).__module__,
        "validation_model": model_name,
        "validation_errors": summaries,
        "n8_constructor_trace_frames": n8_frames,
        "expected_constructor_line": constructor_line,
        "constructor_frame_hit": constructor_hit,
        "typed_guard": "ValuePortObservation._verify_value_authority_shape",
        "typed_guard_code": guard_code,
        "typed_guard_source_line": guard_line,
        "expected_typed_carrier_refusal": exact_error,
        "exception_excerpt": "\n".join(str(exc).splitlines()[:5]),
    }


def _configure_runtime_mutation() -> None:
    import polisyos.runtime.quality.generation_cycle as module

    runtime_path = Path(module.__file__).resolve()
    test_path = PROJECT_ROOT / TEST_REL
    test_source = test_path.read_text()
    runtime_source = runtime_path.read_text()
    target_function_ast_sha256, target_assertion_line, target_assertion_source = (
        _target_test_details(test_source)
    )
    value_constructor_line, limitation_guard_line = _runtime_guard_details(runtime_source)
    function = module._conditional_simulation_value_observation
    function_source = "".join(inspect.getsourcelines(function)[0])
    source_digest = _function_source_sha256(function_source, function.__name__)
    if _git_revision("HEAD") != EXPECTED_CANDIDATE_SHA:
        raise pytest.UsageError("N8 property-removal probe candidate commit changed")
    if _git_revision("HEAD^{tree}") != EXPECTED_CANDIDATE_TREE:
        raise pytest.UsageError("N8 property-removal probe candidate tree changed")
    if _file_sha256(runtime_path) != EXPECTED_RUNTIME_SHA256:
        raise pytest.UsageError("N8 property-removal probe runtime source hash changed")
    if _file_sha256(test_path) != EXPECTED_TEST_SHA256:
        raise pytest.UsageError("N8 property-removal probe target test source hash changed")
    if target_function_ast_sha256 != EXPECTED_TARGET_FUNCTION_AST_SHA256:
        raise pytest.UsageError("N8 property-removal target test function AST changed")
    if source_digest != EXPECTED_FUNCTION_SHA256:
        raise pytest.UsageError("N8 property-removal probe N8 function hash changed")
    if function_source.count(NEEDLE) != 1:
        raise pytest.UsageError("N8 property-removal mutation seam is absent or ambiguous")

    mutated_source = function_source.replace(NEEDLE, REPLACEMENT, 1)
    if mutated_source == function_source or mutated_source.count(REPLACEMENT) != 1:
        raise pytest.UsageError("N8 property-removal mutation was not applied exactly once")
    code = compile(mutated_source, str(runtime_path), "exec")

    _STATE["preflight"] = {
        "candidate_sha": _git_revision("HEAD"),
        "candidate_tree": _git_revision("HEAD^{tree}"),
        "runtime_file": str(runtime_path),
        "runtime_sha256": _file_sha256(runtime_path),
        "target_test_file": str(test_path),
        "target_test_sha256": _file_sha256(test_path),
        "target_test_function_ast_sha256": target_function_ast_sha256,
        "target_assertion_line": target_assertion_line,
        "target_assertion_expression": target_assertion_source,
        "value_port_constructor_line": value_constructor_line,
        "value_port_limitation_guard_line": limitation_guard_line,
        "value_port_limitation_guard": "value_conditional_requires_simulation_limitation",
        "n8_function_source_sha256": source_digest,
        "mutant_function_source_sha256": _sha256(mutated_source.encode()),
        "expected_runtime_sha256": EXPECTED_RUNTIME_SHA256,
        "expected_test_sha256": EXPECTED_TEST_SHA256,
        "expected_n8_function_sha256": EXPECTED_FUNCTION_SHA256,
        "mutation": {
            "kind": "in_memory_single_statement_property_removal",
            "original": NEEDLE.rstrip("\n"),
            "replacement": REPLACEMENT.rstrip("\n"),
            "removed_only": BLOCKER,
            "retained_cas_payload_and_markers": True,
            "retained_all_other_bindings_and_blockers": True,
            "production_and_test_files_written": False,
        },
    }

    original_load = module.load_joint_simulation_result
    original_n5_call = module.JointSimulationPort.__call__
    original_n8_call = module._DefaultSimulationBoundFoundryValuePort.__call__
    original_function = module._conditional_simulation_value_observation

    @functools.wraps(original_load)
    def observed_load(*args: Any, **kwargs: Any) -> Any:
        loaded = original_load(*args, **kwargs)
        if _STATE["active"]:
            caller = sys._getframe(1).f_code.co_name
            ref = args[0] if args else kwargs.get("simulation_result_ref")
            event = {
                "caller": caller,
                "simulation_result_ref": _safe(ref),
                "simulation_result_ref_key": _ref_key(ref),
                "persisted_k_sim_marker_present": BLOCKER in _packet_blockers(loaded),
                "persisted_packet_blockers": _packet_blockers(loaded),
                "expected_content_bindings": {
                    key: _safe(kwargs.get(key))
                    for key in (
                        "expected_world_model_record_content_hash",
                        "expected_world_model_record_ref",
                        "expected_atom_ids",
                        "expected_selected_outcomes",
                        "expected_receipt_payload_hash",
                    )
                },
                "loaded_world_model_record_content_hash": _safe(
                    getattr(loaded, "world_model_record_content_hash", None)
                ),
            }
            if caller == "_conditional_simulation_value_observation":
                _STATE["events"]["n8_cas_reads"].append(event)
            elif caller == "test_n8_recovers_persisted_candidate_only_blocker_after_lossy_projection":
                _STATE["events"]["test_cas_readbacks"].append(event)
        return loaded

    @functools.wraps(original_n5_call)
    def observed_n5_call(self: Any, *args: Any, **kwargs: Any) -> Any:
        produced = original_n5_call(self, *args, **kwargs)
        if _STATE["active"]:
            ref = getattr(produced, "simulation_result_ref", None)
            _STATE["events"]["n5_producer_calls"].append(
                {
                    "producer_class": type(self).__name__,
                    "status": getattr(produced, "status", None),
                    "candidate_id": _safe(getattr(produced, "candidate_id", None)),
                    "world_model_record_content_hash": _safe(
                        getattr(produced, "world_model_record_content_hash", None)
                    ),
                    "simulation_ref": _safe(getattr(produced, "simulation_ref", None)),
                    "simulation_result_ref": _safe(ref),
                    "simulation_result_ref_key": _ref_key(ref),
                    "producer_k_sim_marker_present": BLOCKER in _blockers(produced),
                    "producer_authority_blockers": _blockers(produced),
                }
            )
        return produced

    @functools.wraps(original_n8_call)
    def observed_n8_call(self: Any, *args: Any, **kwargs: Any) -> Any:
        simulation = kwargs.get("simulation")
        candidate = kwargs.get("candidate")
        problem = kwargs.get("problem")
        ref = getattr(simulation, "simulation_result_ref", None)
        entry = {
            "consumer_class": type(self).__name__,
            "entered_before_original_call": True,
            "cycle_index": kwargs.get("cycle_index"),
            "simulation_status": getattr(simulation, "status", None),
            "candidate_id": _safe(getattr(candidate, "candidate_id", None)),
            "problem_id": _safe(getattr(problem, "design_problem_id", None)),
            "simulation_result_ref": _safe(ref),
            "simulation_result_ref_key": _ref_key(ref),
            "simulation_ref": _safe(getattr(simulation, "simulation_ref", None)),
            "world_model_record_content_hash": _safe(
                getattr(simulation, "world_model_record_content_hash", None)
            ),
            "n5_projected_blockers": _blockers(simulation),
            "outcome": "entered",
        }
        if _STATE["active"]:
            _STATE["events"]["default_n8_calls"].append(entry)
        try:
            result = original_n8_call(self, *args, **kwargs)
        except Exception as exc:
            if _STATE["active"]:
                entry["outcome"] = "raised"
                entry["exception"] = _validation_details(
                    exc,
                    runtime_path=Path(module.__file__).resolve(),
                    constructor_line=_STATE["preflight"]["value_port_constructor_line"],
                    guard_line=_STATE["preflight"]["value_port_limitation_guard_line"],
                )
            raise
        if _STATE["active"]:
            entry.update(
                {
                    "outcome": "returned",
                    "status": getattr(result, "status", None),
                    "consumer_k_sim_marker_present": BLOCKER in _blockers(result),
                    "consumer_authority_blockers": _blockers(result),
                }
            )
        return result

    module.load_joint_simulation_result = observed_load
    module.JointSimulationPort.__call__ = observed_n5_call
    module._DefaultSimulationBoundFoundryValuePort.__call__ = observed_n8_call
    exec(code, module.__dict__)

    def restore() -> None:
        module.load_joint_simulation_result = original_load
        module.JointSimulationPort.__call__ = original_n5_call
        module._DefaultSimulationBoundFoundryValuePort.__call__ = original_n8_call
        module._conditional_simulation_value_observation = original_function

    _STATE["restorers"].append(restore)
    _STATE["preflight"].update(
        {
            "mutant_function_installed_in_memory": True,
            "runtime_file_sha256_after_install": _file_sha256(runtime_path),
            "target_test_sha256_after_install": _file_sha256(test_path),
        }
    )


def pytest_collection_finish(session: pytest.Session) -> None:
    selected = [item.nodeid for item in session.items]
    if selected != [TARGET_NODE]:
        raise pytest.UsageError(
            "N8 property-removal plugin permits only the one unchanged target; "
            f"collected={selected!r}"
        )
    _STATE["collected_nodeids"] = selected


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.nodeid != TARGET_NODE:
        raise pytest.UsageError(f"unexpected property-removal target: {item.nodeid}")
    _configure_runtime_mutation()
    _STATE["active"] = True


@pytest.hookimpl(hookwrapper=True)
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    outcome = yield
    report = outcome.get_result()
    if item.nodeid == TARGET_NODE:
        error = call.excinfo.value if call.excinfo is not None else None
        _STATE["reports"].append(
            {
                "nodeid": item.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "exception_class": type(error).__name__ if error is not None else None,
                "exception_module": type(error).__module__ if error is not None else None,
                "exception_excerpt": "\n".join(str(error).splitlines()[:5]) if error is not None else None,
                "longrepr_sha256": _sha256(str(report.longrepr).encode()) if report.failed else None,
            }
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    for restore in reversed(_STATE["restorers"]):
        restore()
    runtime_path = PROJECT_ROOT / RUNTIME_REL
    test_path = PROJECT_ROOT / TEST_REL
    events = _STATE["events"]
    n5 = events["n5_producer_calls"]
    n8 = events["default_n8_calls"]
    n8_reads = events["n8_cas_reads"]
    test_reads = events["test_cas_readbacks"]
    reports = _STATE["reports"]
    call_reports = [r for r in reports if r["when"] == "call"]
    runtime_hash_after = _file_sha256(runtime_path)
    test_hash_after = _file_sha256(test_path)
    candidate_sha_after = _git_revision("HEAD")
    candidate_tree_after = _git_revision("HEAD^{tree}")
    candidate_unchanged = (
        candidate_sha_after == EXPECTED_CANDIDATE_SHA
        and candidate_tree_after == EXPECTED_CANDIDATE_TREE
    )
    tracked_sources_unchanged = (
        runtime_hash_after == _STATE["preflight"].get("runtime_sha256")
        and test_hash_after == _STATE["preflight"].get("target_test_sha256")
    )
    other_failed_reports = [
        r for r in reports if r["outcome"] == "failed" and r["nodeid"] != TARGET_NODE
    ]
    call_report = call_reports[0] if len(call_reports) == 1 else None
    n8_entry = n8[0] if len(n8) == 1 else {}
    refusal = n8_entry.get("exception", {})
    error_rows = refusal.get("validation_errors", [])
    error_input = error_rows[0].get("input_summary", {}) if len(error_rows) == 1 else {}
    same_ref = (
        len(n5) == 1
        and len(n8) == 1
        and len(n8_reads) == 1
        and n5[0]["simulation_result_ref_key"] == n8_entry.get("simulation_result_ref_key")
        and n5[0]["simulation_result_ref_key"] == n8_reads[0]["simulation_result_ref_key"]
    )
    binding_reconciled = (
        same_ref
        and bool(n8_reads[0].get("persisted_k_sim_marker_present"))
        and bool(n8_reads[0].get("expected_content_bindings", {}).get("expected_world_model_record_content_hash"))
        and bool(n8_reads[0].get("expected_content_bindings", {}).get("expected_atom_ids"))
        and bool(n8_reads[0].get("expected_content_bindings", {}).get("expected_selected_outcomes"))
        and n8_reads[0].get("expected_content_bindings", {}).get("expected_receipt_payload_hash")
        == n8_entry.get("simulation_ref")
        and n8_entry.get("simulation_ref") == n5[0].get("simulation_ref")
        and n8_reads[0].get("loaded_world_model_record_content_hash")
        == n8_reads[0].get("expected_content_bindings", {}).get("expected_world_model_record_content_hash")
        and n8_entry.get("candidate_id") == n5[0].get("candidate_id")
        and n8_entry.get("simulation_status") == "joint_simulated"
        and BLOCKER not in n8_entry.get("n5_projected_blockers", [])
    )
    carrier_input_matches = (
        error_input.get("status") == "value_conditional"
        and error_input.get("value_ref") == n5[0].get("simulation_result_ref", {}).get("artifact_id")
        and BLOCKER not in error_input.get("authority_blockers", [])
    ) if len(n5) == 1 else False
    report_matches = (
        call_report is not None
        and call_report["outcome"] == "failed"
        and call_report["exception_class"] == "ValidationError"
        and call_report["exception_module"] == "pydantic_core._pydantic_core"
        and "ValuePortObservation" in str(call_report["exception_excerpt"])
        and "value_conditional_requires_simulation_limitation" in str(call_report["exception_excerpt"])
    )
    expected_typed_refusal = (
        len(n8) == 1
        and n8_entry.get("entered_before_original_call") is True
        and n8_entry.get("outcome") == "raised"
        and refusal.get("expected_typed_carrier_refusal") is True
        and refusal.get("validation_model") == "ValuePortObservation"
        and refusal.get("typed_guard_code") == "value_conditional_requires_simulation_limitation"
        and refusal.get("constructor_frame_hit") is True
        and carrier_input_matches
        and report_matches
    )
    no_other_error = (
        _STATE.get("collected_nodeids") == [TARGET_NODE]
        and len(call_reports) == 1
        and not other_failed_reports
        and not events["test_cas_readbacks"]
        and expected_typed_refusal
    )
    exact_witness = (
        len(n5) == 1
        and n5[0].get("producer_k_sim_marker_present") is True
        and binding_reconciled
        and expected_typed_refusal
        and no_other_error
        and tracked_sources_unchanged
        and candidate_unchanged
    )
    result = {
        "schema": "e02-r1-ksim-removal-typed-refusal-v1",
        "qualification_status": "EXPECTED_TYPED_CARRIER_REFUSAL" if exact_witness else "INCOMPLETE_OR_UNEXPECTED_RESULT",
        "run_exit_code": exitstatus,
        "target": TARGET_NODE,
        "collected_nodeids": _STATE.get("collected_nodeids", []),
        "reports": reports,
        "original_value_assertion": {
            "file": str(TEST_REL),
            "line_derived_from_ast": _STATE["preflight"].get("target_assertion_line"),
            "expression": _STATE["preflight"].get("target_assertion_expression"),
            "reached": bool(events["test_cas_readbacks"]),
            "expected_typed_refusal_precedes_assertion": expected_typed_refusal,
        },
        "property_removal": {
            **_STATE["preflight"].get("mutation", {}),
            "n8_call_counted_before_call": len(n8) == 1 and n8_entry.get("entered_before_original_call") is True,
            "n8_reached_valueportobservation_constructor": refusal.get("constructor_frame_hit") is True,
            "typed_carrier_refused_without_k_sim_limitation": expected_typed_refusal and carrier_input_matches,
            "raw_cas_marker_preserved": len(n8_reads) == 1 and n8_reads[0].get("persisted_k_sim_marker_present") is True,
            "same_produced_and_content_bound_read_ref": same_ref,
            "no_other_test_or_error": no_other_error,
            "tracked_runtime_and_test_sources_unchanged": tracked_sources_unchanged,
            "frozen_candidate_unchanged": candidate_unchanged,
        },
        "runtime_observations": events,
        "counts": {
            "actual_n5_joint_simulation_producer_calls": len(n5),
            "actual_default_n8_entries_before_original_call": len(n8),
            "actual_default_n8_returns": sum(1 for row in n8 if row.get("outcome") == "returned"),
            "actual_default_n8_typed_refusals": sum(1 for row in n8 if row.get("outcome") == "raised"),
            "actual_content_bound_n8_cas_reads": len(n8_reads),
            "test_readback_cas_reads": len(test_reads),
            "test_targets": len(_STATE.get("collected_nodeids", [])),
            "other_test_targets": len([
                node for node in _STATE.get("collected_nodeids", []) if node != TARGET_NODE
            ]),
            "other_failed_test_reports": len(other_failed_reports),
        },
        "source_identity": {
            "candidate_sha_before_and_after": {
                "before": _STATE["preflight"].get("candidate_sha"),
                "after": candidate_sha_after,
            },
            "candidate_tree_before_and_after": {
                "before": _STATE["preflight"].get("candidate_tree"),
                "after": candidate_tree_after,
            },
            "runtime_file": str(runtime_path),
            "runtime_sha256_before_and_after": {
                "before": _STATE["preflight"].get("runtime_sha256"),
                "after": runtime_hash_after,
            },
            "target_test_file": str(test_path),
            "target_test_function_ast_sha256": _STATE["preflight"].get("target_test_function_ast_sha256"),
            "derived_value_blocker_assertion_line": _STATE["preflight"].get("target_assertion_line"),
            "value_port_constructor_line": _STATE["preflight"].get("value_port_constructor_line"),
            "value_port_limitation_guard_line": _STATE["preflight"].get("value_port_limitation_guard_line"),
            "target_test_sha256_before_and_after": {
                "before": _STATE["preflight"].get("target_test_sha256"),
                "after": test_hash_after,
            },
            "plugin_file": str(Path(__file__).resolve()),
            "plugin_sha256": _file_sha256(Path(__file__).resolve()),
        },
        "environment": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "pytest_version": pytest.__version__,
            "cwd": os.getcwd(),
            "argv": sys.argv,
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
            "NUMEXPR_NUM_THREADS": os.environ.get("NUMEXPR_NUM_THREADS"),
            "JAX_PLATFORMS": os.environ.get("JAX_PLATFORMS"),
        },
        "prior_attempt": {
            "classification": "HARNESS_UNQUALIFIED",
            "receipt": "_build/e02-A-continuation-20261007/ksim-persisted-blocker-r1-3ba1/receipt.json",
            "qualification": "_build/e02-A-continuation-20261007/ksim-persisted-blocker-r1-3ba1/qualification.json",
            "reason": "The earlier wrapper counted only successful returns, so a real N8 entry followed by the typed carrier refusal was omitted from its call count.",
        },
        "scope": {
            "mutation_is_in_memory_only": True,
            "tracked_runtime_or_test_file_modified": not tracked_sources_unchanged,
            "tests_executed_other_than_exact_target": False,
            "finding_class": "same K_sim propagation class, one layer deeper: the ValuePortObservation constructor independently refuses the conditional result when N8 loses the persisted limitation.",
            "bounded_claim": "The probe detects fail-closed typed-carrier behavior after removing N8's persisted blocker merge; it does not assert that the original target assertion ran, and it does not establish N9 authority/currentness.",
        },
    }
    QUALIFICATION_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("E02_KSIM_TYPED_REFUSAL_QUALIFICATION=" + json.dumps(result, sort_keys=True))
