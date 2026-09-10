"""Reconcile retained pytest reports with current ASTs without importing runtime."""

from __future__ import annotations

import ast
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import re


EVIDENCE = Path("docs/superpowers/journals/gy-eight-gaps-evidence/c3/return")
COLLECTION = Path("tests/repo_quality/tools/test_layer3_gy_phase2_collection.py")
OWNER = Path("tools/quality/validation/check_layer3_gy_phase2_artifacts.py")
RECEIPTS = (
    "phase2-integrated-native.json",
    "phase2-history-red.json",
    "phase2-history-green-and-correction.json",
    "p28-native-red.json",
    "p28-native-current.json",
    "scm-p28-native-current.json",
    "scm-current-importer-boundaries.json",
    "scm-importer-companion-current.json",
)
SNAPSHOTS: dict[Path, bytes] = {}


def read(path: Path) -> str:
    if path not in SNAPSHOTS:
        SNAPSHOTS[path] = path.read_bytes()
    return SNAPSHOTS[path].decode()


def digest(path: Path) -> str:
    read(path)
    return hashlib.sha256(SNAPSHOTS[path]).hexdigest()


def static(node: ast.AST, symbols: dict[str, object]) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return symbols[node.id]
    if isinstance(node, ast.Attribute):
        return static(node.value, symbols)[node.attr]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [static(child, symbols) for child in node.elts]
        return {ast.List: list, ast.Tuple: tuple, ast.Set: set}[type(node)](values)
    if isinstance(node, ast.Dict):
        return {static(key, symbols): static(value, symbols) for key, value in zip(node.keys, node.values, strict=True)}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"tuple", "list"}:
        assert len(node.args) == 1 and not node.keywords
        return {"tuple": tuple, "list": list}[node.func.id](static(node.args[0], symbols))
    raise ValueError(f"static_expression_not_supported:{ast.dump(node)}")


def module(path: Path, inherited: dict[str, object] | None = None):
    tree = ast.parse(read(path), filename=str(path))
    symbols = dict(inherited or {})
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(target, ast.Name) for target in node.targets):
            try:
                value = static(node.value, symbols)
            except (KeyError, ValueError, TypeError):
                continue
            for target in node.targets:
                symbols[target.id] = value
    return tree, symbols


def parameter_id(value: object) -> str:
    assert isinstance(value, (str, int, float, bool)) or value is None, type(value)
    return value.encode("unicode_escape").decode("ascii") if isinstance(value, str) else str(value)


def expand(path: Path, tree: ast.Module, symbols: dict[str, object]) -> tuple[dict[str, set[str]], int]:
    functions = {}
    independent_count = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
            continue
        components = []
        lengths = []
        for decorator in reversed(node.decorator_list):
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "parametrize":
                continue
            names = static(decorator.args[0], symbols)
            names = [part.strip() for part in names.split(",")] if isinstance(names, str) else list(names)
            values = list(static(decorator.args[1], symbols))
            supplied_ids = next((static(kw.value, symbols) for kw in decorator.keywords if kw.arg == "ids"), None)
            if supplied_ids is not None:
                assert len(supplied_ids) == len(values)
            group = []
            for index, value in enumerate(values):
                cells = [value] if len(names) == 1 else list(value)
                assert len(cells) == len(names)
                group.append(parameter_id(supplied_ids[index]) if supplied_ids is not None else "-".join(map(parameter_id, cells)))
            assert len(group) == len(set(group)), "duplicate_param_id_requires_pytest_suffix_support"
            components.append(group)
            lengths.append(len(values))
        base = f"{path}::{node.name}"
        identities = {base + "[" + "-".join(parts) + "]" for parts in itertools.product(*components)} if components else {base}
        count = math.prod(lengths)
        assert len(identities) == count
        functions[node.name] = identities
        independent_count += count
    return functions, independent_count


def reported(receipt: dict[str, object]) -> tuple[dict[str, str], int]:
    assert receipt["timed_out"] is False
    rows = {}
    # Preserve the complete ID, including spaces inside parametrized source text.
    for line in receipt["stdout"].splitlines():
        match = re.fullmatch(r"(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (tests/.+)", line)
        if match:
            status, identity = match.groups()
            assert identity not in rows, identity
            rows[identity] = status
    progress = "".join(match.group(1) for line in receipt["stdout"].splitlines()
                       if (match := re.fullmatch(r"([.FEsxX]+)\s+\[\s*\d+%\]", line)))
    assert rows and len(progress) == len(rows), (len(progress), len(rows))
    expected = Counter({"PASSED": progress.count("."), "FAILED": progress.count("F"), "ERROR": progress.count("E"),
                        "SKIPPED": progress.count("s"), "XFAIL": progress.count("x"), "XPASS": progress.count("X")})
    assert Counter(rows.values()) == +expected
    assert (receipt["returncode"] == 0) == (not any(status in {"FAILED", "ERROR"} for status in rows.values()))
    return rows, len(progress)


def main() -> None:
    _, owner_symbols = module(OWNER)
    tree, symbols = module(COLLECTION, {"checker": owner_symbols})
    functions, independent_count = expand(COLLECTION, tree, symbols)
    all_current = set().union(*functions.values())
    assert len(all_current) == independent_count
    results = {}
    summaries = []
    for name in RECEIPTS:
        path = EVIDENCE / name
        receipt = json.loads(read(path))
        rows, progress_count = reported(receipt)
        commands = [arg for arg in receipt["command"] if arg.startswith("tests/")]
        expected = set()
        for arg in commands:
            source, *selected = arg.split("::", 1)
            if source == str(COLLECTION):
                expected.update(functions[selected[0]] if selected else all_current)
            else:
                assert selected and "[" not in selected[0], "unmodeled_importer_parameter"
                expected.add(arg)
        missing = expected - rows.keys()
        extra = rows.keys() - expected
        assert not extra, (name, sorted(extra))
        if name != "phase2-integrated-native.json":
            assert not missing, (name, sorted(missing))
        else:
            # The current history/P28 functions were added after this original whole-file wave.
            # This is recorded evidence coverage, never a claim that current 48 cases ran then.
            assert rows.keys() <= all_current
        results[name] = rows
        summaries.append({"receipt": str(path), "sha256": digest(path), "returncode": receipt["returncode"],
                          "reported_outcomes": len(rows), "independent_progress_outcomes": progress_count,
                          "status_counts": dict(Counter(rows.values())),
                          "current_command_population": len(expected),
                          "current_identities_not_run_in_that_command": len(missing),
                          "unexpected_report_identities": sorted(extra)})

    native_names = RECEIPTS[:6]
    latest = {}
    for name in native_names:
        for identity, status in results[name].items():
            latest[identity] = (status, name)
    assert set(latest) == all_current, {"unrun_current": sorted(all_current - latest.keys()), "foreign": sorted(latest.keys() - all_current)}
    unresolved = {identity: value for identity, value in latest.items() if value[0] != "PASSED"}
    assert not unresolved, unresolved
    failures = {identity for name in native_names for identity, status in results[name].items() if status in {"FAILED", "ERROR"}}
    assert all(latest[identity][0] == "PASSED" for identity in failures)
    latest_basis = Counter(value[1] for value in latest.values())

    importer_red = results["scm-current-importer-boundaries.json"]
    importer_green = results["scm-importer-companion-current.json"]
    renames = {
        "tests/integration/foundry_scientist/test_method_node_bridge.py::test_foundry_method_registry_entry_executes_through_scientist_node":
        "tests/integration/foundry_scientist/test_method_node_bridge.py::test_foundry_method_bridge_refuses_absent_eval_safety_before_execution",
        "tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_estimate_consumes_real_foundry_method_output_with_measurement_authority":
        "tests/integration/runtime_quality/test_workspace_foundry_consumption.py::test_phase2_method_consumption_binds_real_source_and_reconciled_constraint_refusal",
        "tests/unit/scientist/methods/causal/test_causal_evaluation_node.py::test_causal_evaluation_node_success":
        "tests/unit/scientist/methods/causal/test_causal_evaluation_node.py::test_causal_evaluation_node_refuses_absent_eval_safety_before_execution",
    }
    renamed_failed = {renames.get(identity, identity) for identity, status in importer_red.items() if status == "FAILED"}
    assert renamed_failed == set(importer_green)
    assert set(importer_green.values()) == {"PASSED"}
    importer_current = {renames.get(identity, identity) for identity in importer_red}
    for identity in importer_current:
        source, name = identity.split("::")
        current_tree, _ = module(Path(source))
        selected = [node for node in current_tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(selected) == 1 and not selected[0].decorator_list, identity
    stale_names = {identity for identity in importer_red if identity in renames}
    assert len(stale_names) == len(renames)
    assert all(path.read_bytes() == raw for path, raw in SNAPSHOTS.items()), "input_changed"
    print(json.dumps({
        "scope": "Static current AST/parametrize expansion plus complete retained pytest summaries and independent progress counts; no runtime imports or rerun.",
        "sources": {str(path): digest(path) for path in (COLLECTION, OWNER)},
        "receipts": summaries,
        "collection": {"current_test_function_count": len(functions), "expanded_current_identity_count": len(all_current),
                       "independent_decorator_product_count": independent_count,
                       "latest_pass_coverage_count": len(latest), "latest_evidence_basis_counts": dict(latest_basis),
                       "unrun_current_identities": [], "unresolved_latest_failures": {},
                       "whole_current_file_rerun_claim": False,
                       "note": "The original whole-file invocation reported its then-existing subset. Later selected history/correction and P28/SCM waves jointly cover the current file, not one full final-source rerun."},
        "importers": {"original_selected_count": len(importer_red), "corrected_selected_count": len(importer_green),
                      "current_ast_and_command_and_report_identity_delta": [],
                      "renamed_test_identity_delta": renames,
                      "uncorrected_failed_identities": [],
                      "earlier_passing_controls_not_rerun_in_companion": len(importer_red) - len(importer_green)},
        "all_inputs_unchanged": True,
    }, indent=2))


if __name__ == "__main__":
    main()
