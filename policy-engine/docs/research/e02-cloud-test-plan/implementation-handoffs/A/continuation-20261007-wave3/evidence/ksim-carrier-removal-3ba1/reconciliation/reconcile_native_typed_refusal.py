"""Read-only reconciliation of the frozen K_sim typed-refusal run.

This does not run pytest or modify its receipt, raw output, runtime, or test.
It reconstructs the exact standalone mutated N8 function compile and checks its
relative traceback line against the retained qualification/JUnit evidence.
"""
from __future__ import annotations

import ast
import dis
import hashlib
import json
import marshal
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

PROJECT = Path(__file__).resolve().parents[3]
BUILD = PROJECT / "_build/e02-A-continuation-20261007"
RUN = BUILD / "ksim-typed-refusal-native-3ba1"
EARLY_ERROR = BUILD / "ksim-typed-refusal-r1-3ba1"
FIRST_TYPED_ATTEMPT = BUILD / "ksim-persisted-blocker-r1-3ba1"
TARGET = "tests/unit/runtime/quality/test_generation_cycle.py::test_n8_recovers_persisted_candidate_only_blocker_after_lossy_projection"
RUNTIME_REL = Path("src/polisyos/runtime/quality/generation_cycle.py")
TEST_REL = Path("tests/unit/runtime/quality/test_generation_cycle.py")
EXPECTED_COMMIT = "3ba1deaa55c54971c3200269dc1c81680e3d7167"
EXPECTED_TREE = "abe1c8ae7ec1aa81a82cfc48dc07a8b5db3bc033"
BLOCKER = "simulation_only_k_sim_not_world_evidence"
GUARD_CODE = "value_conditional_requires_simulation_limitation"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return sha(path.read_bytes())


def git(expression: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", expression], cwd=PROJECT, text=True
    ).strip()


def top_function(source: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def compact_report(report: dict) -> dict:
    return {
        "nodeid": report.get("nodeid"),
        "when": report.get("when"),
        "outcome": report.get("outcome"),
        "exception_class": report.get("exception_class"),
        "exception_module": report.get("exception_module"),
        "exception_excerpt": report.get("exception_excerpt"),
        "longrepr_sha256": report.get("longrepr_sha256"),
    }


def main() -> None:
    q_path = RUN / "qualification.json"
    receipt_path = RUN / "receipt.json"
    junit_path = RUN / "junit.xml"
    q = json.loads(q_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    runtime_path = PROJECT / RUNTIME_REL
    test_path = PROJECT / TEST_REL
    plugin_path = Path(q["source_identity"]["plugin_file"])
    plugin_source = plugin_path.read_text()
    frozen_runtime_bytes = subprocess.check_output(
        ["git", "show", f"{EXPECTED_COMMIT}:policy-engine/{RUNTIME_REL.as_posix()}"], cwd=PROJECT
    )
    frozen_test_bytes = subprocess.check_output(
        ["git", "show", f"{EXPECTED_COMMIT}:policy-engine/{TEST_REL.as_posix()}"], cwd=PROJECT
    )
    runtime_source = frozen_runtime_bytes.decode()
    test_source = frozen_test_bytes.decode()
    function_node = top_function(
        runtime_source, "_conditional_simulation_value_observation"
    )
    function_lines = runtime_source.splitlines(keepends=True)
    function_source = "".join(
        function_lines[function_node.lineno - 1 : function_node.end_lineno]
    )
    function_digest = sha(function_source.encode())

    plugin_tree = ast.parse(plugin_source)
    constants = {}
    for node in plugin_tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    needle = constants["NEEDLE"]
    replacement = constants["REPLACEMENT"]
    if function_source.count(needle) != 1:
        raise SystemExit("Reconciliation stopped: the pinned in-memory mutation seam is not unique")
    mutant_source = function_source.replace(needle, replacement, 1)
    mutant_function = top_function(mutant_source, "_conditional_simulation_value_observation")
    constructor_calls = [
        node for node in ast.walk(mutant_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ValuePortObservation"
    ]
    if len(constructor_calls) != 1:
        raise SystemExit("Reconciliation stopped: the mutated function has no unique typed-carrier constructor")
    relative_constructor_line = constructor_calls[0].lineno
    absolute_constructor_line = constructor_calls[0].lineno + function_node.lineno - 1
    context_offset = function_node.lineno - 1

    compiled_module = compile(mutant_source, str(runtime_path), "exec")
    code_objects = [
        const for const in compiled_module.co_consts
        if hasattr(const, "co_name")
        and const.co_name == "_conditional_simulation_value_observation"
    ]
    if len(code_objects) != 1:
        raise SystemExit("Reconciliation stopped: compiled standalone N8 code object is ambiguous")
    code_object = code_objects[0]
    compiled_line_starts = sorted({line for _, line in dis.findlinestarts(code_object) if line is not None})

    test_function = top_function(
        test_source, "test_n8_recovers_persisted_candidate_only_blocker_after_lossy_projection"
    )
    test_function_ast_sha256 = sha(ast.dump(test_function, include_attributes=False).encode())
    wanted_assertion = ast.dump(
        ast.parse(f'assert "{BLOCKER}" in value.authority_blockers').body[0].test,
        include_attributes=False,
    )
    target_assertions = [
        node for node in ast.walk(test_function)
        if isinstance(node, ast.Assert)
        and ast.dump(node.test, include_attributes=False) == wanted_assertion
    ]
    if len(target_assertions) != 1:
        raise SystemExit("Reconciliation stopped: frozen target does not have one exact value blocker assertion")
    target_assertion_line = target_assertions[0].lineno
    target_assertion_source = ast.get_source_segment(test_source, target_assertions[0].test)

    q_events = q["runtime_observations"]
    n5 = q_events["n5_producer_calls"]
    n8 = q_events["default_n8_calls"]
    n8_reads = q_events["n8_cas_reads"]
    reports = q["reports"]
    call_reports = [item for item in reports if item.get("when") == "call"]
    n8_entry = n8[0] if len(n8) == 1 else {}
    exception = n8_entry.get("exception", {})
    errors = exception.get("validation_errors", [])
    error = errors[0] if len(errors) == 1 else {}
    error_input = error.get("input_summary", {})
    cas_read = n8_reads[0] if len(n8_reads) == 1 else {}
    producer = n5[0] if len(n5) == 1 else {}
    expected_bindings = cas_read.get("expected_content_bindings", {})
    report = call_reports[0] if len(call_reports) == 1 else {}

    junit = ET.parse(junit_path).getroot()
    testcases = list(junit.iter("testcase"))
    target_cases = [tc for tc in testcases if tc.attrib.get("name") == TARGET.rsplit("::", 1)[-1]]
    junit_failures = [
        {"message": node.attrib.get("message", ""), "text_sha256": sha((node.text or "").encode())}
        for tc in target_cases
        for node in (tc.find("failure"),)
        if node is not None
    ]

    candidate_sha = git("HEAD")
    candidate_tree = git("HEAD^{tree}")
    n8_trace = exception.get("n8_constructor_trace_frames", [])
    observed_frame = next(
        (frame for frame in n8_trace if frame.get("function") == "_conditional_simulation_value_observation"),
        {},
    )
    ref_key_matches = (
        len(n5) == 1 and len(n8) == 1 and len(n8_reads) == 1
        and producer.get("simulation_result_ref_key") == n8_entry.get("simulation_result_ref_key")
        and producer.get("simulation_result_ref_key") == cas_read.get("simulation_result_ref_key")
    )
    receipt_hash_matches = (
        producer.get("simulation_ref")
        and producer.get("simulation_ref") == n8_entry.get("simulation_ref")
        and producer.get("simulation_ref") == expected_bindings.get("expected_receipt_payload_hash")
    )
    world_hash_matches = (
        expected_bindings.get("expected_world_model_record_content_hash")
        and expected_bindings.get("expected_world_model_record_content_hash")
        == cas_read.get("loaded_world_model_record_content_hash")
        and error_input.get("world_model_record_content_hash")
        == cas_read.get("loaded_world_model_record_content_hash")
    )
    model_ref_matches = (
        producer.get("simulation_result_ref", {}).get("artifact_id")
        == error_input.get("value_ref")
    )
    exact_validation = (
        exception.get("exception_class") == "ValidationError"
        and exception.get("exception_module") == "pydantic_core._pydantic_core"
        and exception.get("validation_model") == "ValuePortObservation"
        and len(errors) == 1
        and error.get("type") == "value_error"
        and error.get("loc") == []
        and GUARD_CODE in str(error.get("msg"))
        and GUARD_CODE in str(error.get("context_error"))
        and error_input.get("status") == "value_conditional"
        and error_input.get("authority_blockers") == []
        and BLOCKER not in error_input.get("authority_blockers", [])
        and n8_entry.get("entered_before_original_call") is True
        and n8_entry.get("outcome") == "raised"
        and exception.get("typed_guard") == "ValuePortObservation._verify_value_authority_shape"
        and exception.get("typed_guard_source_line") == 1389
    )
    trace_mapping_matches = (
        function_node.lineno == 5741
        and absolute_constructor_line == 5866
        and context_offset == 5740
        and relative_constructor_line == 126
        and code_object.co_firstlineno == 1
        and relative_constructor_line in compiled_line_starts
        and observed_frame.get("file") == str(runtime_path)
        and observed_frame.get("function") == "_conditional_simulation_value_observation"
        and observed_frame.get("line") == relative_constructor_line
    )
    test_scope_matches = (
        q.get("target") == TARGET
        and q.get("collected_nodeids") == [TARGET]
        and len(testcases) == 1
        and len(target_cases) == 1
        and len(junit_failures) == 1
        and len(call_reports) == 1
        and report.get("outcome") == "failed"
        and report.get("exception_class") == "ValidationError"
        and report.get("exception_module") == "pydantic_core._pydantic_core"
        and "ValuePortObservation" in str(report.get("exception_excerpt"))
        and GUARD_CODE in str(report.get("exception_excerpt"))
        and q.get("counts", {}).get("other_test_targets") == 0
        and q.get("counts", {}).get("other_failed_test_reports") == 0
        and q.get("counts", {}).get("test_readback_cas_reads") == 0
    )
    producer_read_binding_matches = (
        len(n5) == 1
        and producer.get("producer_class") == "JointSimulationPort"
        and producer.get("producer_k_sim_marker_present") is True
        and BLOCKER in producer.get("producer_authority_blockers", [])
        and producer.get("status") == "joint_simulated"
        and n8_entry.get("simulation_status") == "joint_simulated"
        and n8_entry.get("candidate_id") == producer.get("candidate_id")
        and BLOCKER not in n8_entry.get("n5_projected_blockers", [])
        and len(n8_reads) == 1
        and cas_read.get("caller") == "_conditional_simulation_value_observation"
        and cas_read.get("persisted_k_sim_marker_present") is True
        and BLOCKER in cas_read.get("persisted_packet_blockers", [])
        and expected_bindings.get("expected_world_model_record_content_hash")
        and expected_bindings.get("expected_world_model_record_ref")
        and expected_bindings.get("expected_atom_ids")
        and expected_bindings.get("expected_selected_outcomes")
        and ref_key_matches
        and receipt_hash_matches
        and world_hash_matches
        and model_ref_matches
    )
    frozen_sources_match = (
        candidate_sha == EXPECTED_COMMIT
        and candidate_tree == EXPECTED_TREE
        and q.get("source_identity", {}).get("candidate_sha_before_and_after", {}).get("before") == EXPECTED_COMMIT
        and q.get("source_identity", {}).get("candidate_sha_before_and_after", {}).get("after") == EXPECTED_COMMIT
        and q.get("source_identity", {}).get("candidate_tree_before_and_after", {}).get("before") == EXPECTED_TREE
        and q.get("source_identity", {}).get("candidate_tree_before_and_after", {}).get("after") == EXPECTED_TREE
        and file_hash(runtime_path) == q.get("source_identity", {}).get("runtime_sha256_before_and_after", {}).get("before")
        and sha(plugin_path.read_bytes()) == q.get("source_identity", {}).get("plugin_sha256")
        and sha(frozen_runtime_bytes) == q.get("source_identity", {}).get("runtime_sha256_before_and_after", {}).get("before")
        and sha(frozen_test_bytes) == q.get("source_identity", {}).get("target_test_sha256_before_and_after", {}).get("before")
        and test_function_ast_sha256 == q.get("source_identity", {}).get("target_test_function_ast_sha256")
        and target_assertion_line == q.get("source_identity", {}).get("derived_value_blocker_assertion_line")
        and function_digest == "45a00dcb9ca34fdaebf5de0a00c128149bad82864c820e6d0ce281601d86d1fb"
    )
    independently_reconciled = all(
        [exact_validation, trace_mapping_matches, test_scope_matches, producer_read_binding_matches, frozen_sources_match]
    )

    prior_attempts = {}
    for label, directory in (
        ("initial_property_removal", FIRST_TYPED_ATTEMPT),
        ("missing_plugin_harness_error", EARLY_ERROR),
    ):
        entries = {}
        for name in ("stdout.txt", "stderr.txt", "receipt.json", "qualification.json", "junit.xml"):
            path = directory / name
            if path.exists() and path.is_file():
                entries[name] = {"sha256": file_hash(path), "bytes": path.stat().st_size}
        prior_attempts[label] = {"path": str(directory.relative_to(PROJECT)), "files": entries}
    early_receipt = json.loads((EARLY_ERROR / "receipt.json").read_text())
    early_stderr = (EARLY_ERROR / "stderr.txt").read_text()

    receipt = {
        "schema": "e02-ksim-typed-refusal-independent-reconciliation-v1",
        "classification": "independently_reconciled_expected_typed_carrier_refusal" if independently_reconciled else "not_established",
        "independently_reconciled": independently_reconciled,
        "original_plugin_qualification_status": q.get("qualification_status"),
        "original_constructor_frame_boolean": exception.get("constructor_frame_hit"),
        "reconciliation_fixes_only_source_to_compiled_line_mapping": trace_mapping_matches,
        "result": {
            "typed_refusal_is_expected_property_removal_falsifier": independently_reconciled,
            "runtime_or_product_failure": False if independently_reconciled else None,
            "original_target_assertion_reached": False,
            "boundary": "The persisted K_sim merge was removed in memory. N8 read the unchanged content-bound N5 artifact and recovered its marker, then the actual ValuePortObservation validator refused the conditional output because the projected limitation set was empty.",
            "limitation": "This establishes fail-closed behavior at the typed carrier one layer below the original K_sim assertion; it does not establish N9 signature/currentness or production authority.",
        },
        "line_mapping": {
            "runtime_file": str(runtime_path),
            "function": "_conditional_simulation_value_observation",
            "original_function_first_source_line": function_node.lineno,
            "original_constructor_source_line": absolute_constructor_line,
            "original_context_offset": context_offset,
            "standalone_function_source_first_line": 1,
            "mutated_ast_constructor_relative_line": relative_constructor_line,
            "compiled_code_firstlineno": code_object.co_firstlineno,
            "compiled_code_line_starts": compiled_line_starts,
            "observed_traceback_frame": observed_frame,
            "mapping_matches": trace_mapping_matches,
            "mutated_function_source_sha256": sha(mutant_source.encode()),
            "reconstructed_mutated_code_object_marshal_sha256": sha(marshal.dumps(code_object)),
            "original_function_source_sha256": function_digest,
            "plugin_compile_path_verified": all(
                marker in plugin_source
                for marker in (
                    'function_source = "".join(inspect.getsourcelines(function)[0])',
                    'mutated_source = function_source.replace(NEEDLE, REPLACEMENT, 1)',
                    'compile(mutated_source, str(runtime_path), "exec")',
                    'exec(code, module.__dict__)',
                )
            ),
            "actual_runtime_code_object_retained_by_original_run": False,
            "reconstruction_basis": "The exact pinned plugin and source deterministically reconstruct the same standalone function compilation; its relative constructor line equals the retained traceback line and filename/function.",
        },
        "typed_validation": {
            "class": exception.get("exception_class"),
            "module": exception.get("exception_module"),
            "model": exception.get("validation_model"),
            "error_count": len(errors),
            "error": error,
            "guard_code": GUARD_CODE,
            "guard_validator": exception.get("typed_guard"),
            "guard_source_line": exception.get("typed_guard_source_line"),
            "constructor_trace_matches": exception.get("constructor_frame_hit"),
            "exact_validation_shape_matches": exact_validation,
        },
        "n5_to_cas_to_n8_binding": {
            "producer_event": producer,
            "n8_entry_event": n8_entry,
            "n8_content_bound_cas_read": cas_read,
            "same_artifact_ref": ref_key_matches,
            "same_receipt_payload_hash": receipt_hash_matches,
            "world_model_hash_reconciles": world_hash_matches,
            "carrier_value_ref_matches_artifact_id": model_ref_matches,
            "all_bindings_and_marker_match": producer_read_binding_matches,
        },
        "scope_and_reports": {
            "target": TARGET,
            "junit_testcases": len(testcases),
            "target_testcases": len(target_cases),
            "junit_failures": junit_failures,
            "pytest_reports": [compact_report(item) for item in reports],
            "only_target_selected": q.get("collected_nodeids") == [TARGET],
            "no_other_test_targets_or_errors": test_scope_matches,
        },
        "source_identity": {
            "commit": candidate_sha,
            "tree": candidate_tree,
            "runtime_sha256_from_frozen_git_blob": sha(frozen_runtime_bytes),
            "runtime_sha256_worktree_now": file_hash(runtime_path),
            "runtime_worktree_matches_frozen": file_hash(runtime_path) == sha(frozen_runtime_bytes),
            "target_test_sha256_from_frozen_git_blob": sha(frozen_test_bytes),
            "target_test_sha256_worktree_now": file_hash(test_path),
            "target_test_worktree_matches_frozen_now": file_hash(test_path) == sha(frozen_test_bytes),
            "target_test_sha256_recorded_during_run": q.get("source_identity", {}).get("target_test_sha256_before_and_after", {}).get("before"),
            "target_test_function_ast_sha256_from_frozen_git_blob": test_function_ast_sha256,
            "derived_target_assertion_line_from_frozen_ast": target_assertion_line,
            "derived_target_assertion_source": target_assertion_source,
            "target_test_source_diverged_after_run": file_hash(test_path) != sha(frozen_test_bytes),
            "plugin_path": str(plugin_path),
            "plugin_sha256": file_hash(plugin_path),
            "native_run_receipt_sha256": file_hash(receipt_path),
            "native_run_qualification_sha256": file_hash(q_path),
            "native_run_junit_sha256": file_hash(junit_path),
            "native_run_stdout_sha256": file_hash(RUN / "stdout.txt"),
            "native_run_exit_code": receipt.get("exit_code"),
            "run_source_hashes_match_frozen_git_blobs": frozen_sources_match,
        },
        "preserved_attempts": {
            "native_typed_refusal_run": {
                "path": str(RUN.relative_to(PROJECT)),
                "receipt_sha256": file_hash(receipt_path),
                "qualification_sha256": file_hash(q_path),
                "junit_sha256": file_hash(junit_path),
                "stdout_sha256": file_hash(RUN / "stdout.txt"),
            },
            "prior_attempts": prior_attempts,
            "missing_plugin_attempt": {
                "classification": "harness_error_before_test_collection",
                "argv_plugin": next((a for a in early_receipt.get("argv", []) if str(a).startswith("pytest_")), None),
                "exit_code": early_receipt.get("exit_code"),
                "module_not_found_observed": "No module named 'pytest_ksim_persisted_blocker_removal'" in early_stderr,
                "test_execution_claim": "No test ran in this attempt.",
            },
            "source_outputs_modified_by_reconciler": False,
            "post_run_test_worktree_change_observed": file_hash(test_path) != sha(frozen_test_bytes),
            "historical_run_reconciled_against_frozen_commit_bytes": True,
        },
    }
    output = Path(__file__).with_name("native-run-reconciliation.json")
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "independently_reconciled": independently_reconciled, "classification": receipt["classification"], "checks": {"line_mapping": trace_mapping_matches, "typed_validation": exact_validation, "n5_cas_n8": producer_read_binding_matches, "test_scope": test_scope_matches, "frozen_source": frozen_sources_match}}, sort_keys=True))


if __name__ == "__main__":
    main()
