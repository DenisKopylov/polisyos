"""One-test, in-memory N8 persisted-K_sim blocker removal qualification plugin.

Loaded only by the root-owned R1 run. It changes one in-memory line in
_conditional_simulation_value_observation and records the actual N5/N8/CAS
path for the single pinned target. It never edits tracked source or tests.
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
from typing import Any

import pytest

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


def _configure_runtime_mutation() -> None:
    import polisyos.runtime.quality.generation_cycle as module

    runtime_path = Path(module.__file__).resolve()
    test_path = PROJECT_ROOT / TEST_REL
    test_source = test_path.read_text()
    target_function_ast_sha256, target_assertion_line, target_assertion_source = (
        _target_test_details(test_source)
    )
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
                    "simulation_result_ref": _safe(ref),
                    "simulation_result_ref_key": _ref_key(ref),
                    "producer_k_sim_marker_present": BLOCKER in _blockers(produced),
                    "producer_authority_blockers": _blockers(produced),
                }
            )
        return produced

    @functools.wraps(original_n8_call)
    def observed_n8_call(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_n8_call(self, *args, **kwargs)
        if _STATE["active"]:
            simulation = kwargs.get("simulation")
            ref = getattr(simulation, "simulation_result_ref", None)
            _STATE["events"]["default_n8_calls"].append(
                {
                    "consumer_class": type(self).__name__,
                    "cycle_index": kwargs.get("cycle_index"),
                    "simulation_result_ref": _safe(ref),
                    "simulation_result_ref_key": _ref_key(ref),
                    "n5_projected_blockers": _blockers(simulation),
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
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    outcome = yield
    report = outcome.get_result()
    if item.nodeid == TARGET_NODE:
        _STATE["reports"].append(
            {
                "nodeid": item.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "longrepr": str(report.longrepr) if report.failed else None,
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
    failing_call = next((r for r in call_reports if r["outcome"] == "failed"), None)
    failure_text = failing_call["longrepr"] or "" if failing_call else ""
    assertion_line = _STATE["preflight"].get("target_assertion_line")
    expected_assertion = (
        failing_call is not None
        and assertion_line is not None
        and f"test_generation_cycle.py:{assertion_line}" in failure_text
        and BLOCKER in failure_text
    )
    same_ref = (
        len(n5) == 1
        and len(n8_reads) == 1
        and len(test_reads) == 1
        and n5[0]["simulation_result_ref_key"] == n8_reads[0]["simulation_result_ref_key"]
        and n5[0]["simulation_result_ref_key"] == test_reads[0]["simulation_result_ref_key"]
    )
    exact_witness = (
        len(n5) == 1
        and len(n8) == 1
        and len(n8_reads) == 1
        and len(test_reads) == 1
        and n5[0]["producer_k_sim_marker_present"]
        and n8_reads[0]["persisted_k_sim_marker_present"]
        and test_reads[0]["persisted_k_sim_marker_present"]
        and BLOCKER not in n8[0]["consumer_authority_blockers"]
        and same_ref
        and expected_assertion
        and tracked_sources_unchanged
        and candidate_unchanged
        and len(call_reports) == 1
        and not other_failed_reports
        and _STATE.get("collected_nodeids") == [TARGET_NODE]
    )
    result = {
        "schema": "e02-r1-ksim-persisted-blocker-removal-v1",
        "qualification_status": "EXPECTED_PROPERTY_REMOVAL_DETECTED" if exact_witness else "INCOMPLETE_OR_UNEXPECTED_RESULT",
        "run_exit_code": exitstatus,
        "target": TARGET_NODE,
        "collected_nodeids": _STATE.get("collected_nodeids", []),
        "reports": reports,
        "expected_unchanged_assertion": {
            "file": str(TEST_REL),
            "line": _STATE["preflight"].get("target_assertion_line"),
            "expression": _STATE["preflight"].get("target_assertion_expression"),
            "failed_as_expected": expected_assertion,
        },
        "property_removal": {
            **_STATE["preflight"].get("mutation", {}),
            "mutant_removed_from_n8_output": bool(n8) and BLOCKER not in n8[0]["consumer_authority_blockers"],
            "raw_cas_marker_preserved": bool(n8_reads) and n8_reads[0]["persisted_k_sim_marker_present"],
            "same_n5_result_ref_produced_read_by_n8_and_test": same_ref,
            "tracked_runtime_and_test_sources_unchanged": tracked_sources_unchanged,
            "frozen_candidate_unchanged": candidate_unchanged,
        },
        "runtime_observations": events,
        "counts": {
            "actual_n5_joint_simulation_producer_calls": len(n5),
            "actual_default_n8_consumer_calls": len(n8),
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
        "scope": {
            "mutation_is_in_memory_only": True,
            "tracked_runtime_or_test_file_modified": not tracked_sources_unchanged,
            "tests_executed_other_than_exact_target": False,
            "semantic_claim": "N8's persisted K_sim blocker propagation is required by the unchanged assertion in this real N5->CAS->default-N8 fixture.",
            "authority_claim": "This test remains a candidate-grade simulation limitation test; it does not establish N9 signature/currentness or production authority.",
        },
    }
    QUALIFICATION_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("E02_KSIM_PROPERTY_REMOVAL_QUALIFICATION=" + json.dumps(result, sort_keys=True))
