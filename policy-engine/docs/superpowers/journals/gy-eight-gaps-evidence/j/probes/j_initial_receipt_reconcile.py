"""Reconcile the complete pre-plugin J receipts without importing their tests."""

from __future__ import annotations

import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import tokenize


RECEIPTS = (
    "_build/gy-gaps/j/initial-owner-red.json",
    "_build/gy-gaps/j/history-native-red.json",
    "_build/gy-gaps/j/initial-owner-correction.json",
)


def source_expansion(nodeid: str, pins: dict) -> set[str]:
    path, name = nodeid.split("::")
    raw = Path(path).read_bytes()
    source = raw.decode()
    tree = ast.parse(source)
    candidates = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    independent = re.findall(rf"^(?:async\s+)?def\s+({re.escape(name)})\s*\(", source, re.M)
    assert len(candidates) == len(independent) == 1, nodeid
    node = candidates[0]
    pins[path] = hashlib.sha256(raw).hexdigest()
    parameters = [d for d in node.decorator_list if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "parametrize"]
    if not parameters:
        return {nodeid}
    assert len(parameters) == 1, "scope requires one explicit literal parameter basis"
    decorator = parameters[0]
    assert len(decorator.args) == 2 and not decorator.keywords
    argument = ast.literal_eval(decorator.args[0])
    values = ast.literal_eval(decorator.args[1])
    assert isinstance(argument, str) and isinstance(values, list) and all(isinstance(x, str) for x in values)
    assert values and len(values) == len(set(values))
    segment = "\n".join(source.splitlines()[decorator.lineno - 1:decorator.end_lineno])
    literal_tokens = [ast.literal_eval(t.string) for t in tokenize.generate_tokens(io.StringIO(segment).readline) if t.type == tokenize.STRING]
    assert literal_tokens == [argument, *values], "independent literal token basis differs"
    return {f"{nodeid}[{value}]" for value in values}


def reconcile(path: str, pins: dict) -> tuple[dict, dict[str, str]]:
    raw = Path(path).read_bytes()
    receipt = json.loads(raw)
    assert receipt["timed_out"] is False and "-rA" in receipt["command"]
    selected = [arg for arg in receipt["command"] if arg.startswith("tests/") and "::" in arg]
    assert selected and len(selected) == len(set(selected))
    expected = set().union(*(source_expansion(node, pins) for node in selected))
    text = receipt["stdout"]
    assert len(re.findall(r"^=+ short test summary info =+$", text, re.M)) == 1
    summary = re.split(r"(?m)^=+ short test summary info =+$", text)[1]
    rows = re.findall(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (tests/[^\n]+)$", summary, re.M)
    rows = [(status, value.split(" - ", 1)[0]) for status, value in rows]
    actual = {node: status for status, node in rows}
    assert len(actual) == len(rows) and set(actual) == expected, {"receipt": path, "unreported": sorted(expected - set(actual)), "unexpected": sorted(set(actual) - expected)}
    assert set(actual.values()) <= {"PASSED", "FAILED"}, "unexpected report arm must be explicitly reconciled"
    failure_section = re.search(r"(?ms)^=+ FAILURES =+\n(.*?)(?=^=+ (?:PASSES|short test summary info) =+$)", text)
    headers = re.findall(r"^_+ (test_\S+) _+$", failure_section.group(1), re.M) if failure_section else []
    failure_identities = set()
    for header in headers:
        matches = [node for node in expected if node.split("::", 1)[1] == header]
        assert len(matches) == 1, {"unmapped_failure": header}
        failure_identities.add(matches[0])
    assert len(headers) == len(failure_identities)
    assert failure_identities == {node for node, state in actual.items() if state == "FAILED"}
    progress = "".join(re.findall(r"^([.FEsxX]+)\s+\[\s*\d+%\]$", text, re.M))
    progress_counts = Counter(progress)
    expected_counts = Counter({"F": len(failure_identities), ".": len(expected - failure_identities)})
    assert +progress_counts == +expected_counts, "independent complete progress outcome totals differ"
    assert {node for node, state in actual.items() if state == "PASSED"} == expected - failure_identities
    assert receipt["returncode"] == (1 if failure_identities else 0)
    assert not receipt["stderr"], "nonempty stderr needs separate disposition"
    return {
        "receipt": path, "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "started_utc": receipt["started_utc"], "elapsed_seconds": receipt["elapsed_seconds"],
        "returncode": receipt["returncode"],
        "command_definition_denominator": len(selected),
        "expanded_ast_and_literal_token_denominator": len(expected),
        "complete_rA_identity_denominator": len(actual),
        "independent_progress_denominator": len(progress),
        "passed": len(expected - failure_identities), "failed": len(failure_identities),
        "summary_vs_expansion_identity_delta": [], "summary_vs_failure_header_identity_delta": [],
    }, actual


def main() -> None:
    pins, reports, outcomes = {}, [], []
    for path in RECEIPTS:
        report, result = reconcile(path, pins)
        reports.append(report)
        outcomes.append(result)
    before = outcomes[0] | outcomes[1]
    assert set(outcomes[0]).isdisjoint(outcomes[1])
    assert set(before) == set(outcomes[2])
    assert set(outcomes[2].values()) == {"PASSED"}
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == value for path, value in pins.items())
    print(json.dumps({
        "mode": "receipt_and_source_identity_reconciliation_no_product_imports_or_tests",
        "receipts": reports,
        "red_union_vs_correction_added": [], "red_union_vs_correction_lost": [],
        "failed_to_passed": sum(state == "FAILED" for state in before.values()),
        "passed_to_passed": sum(state == "PASSED" for state in before.values()),
        "current_definition_crosscheck_source_sha256": pins,
        "source_epoch_limit": "These pre-plugin receipts do not pin full executing source hashes. Their distinct timestamps/commands/results are preserved; current AST/token checks establish matching selected definitions and literal history identities only, not byte equality with the old execution source or final-wave verification.",
        "retention": "Print from original receipts; do not retain a duplicate derived JSON or source snapshot.",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
