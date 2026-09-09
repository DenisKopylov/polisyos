"""Reconcile the whole declared selector test wave with independently expanded AST identities."""
from __future__ import annotations
import ast
import itertools
import json
import re
from pathlib import Path


def outcomes(receipt):
    result = {}
    for line in receipt["stdout"].splitlines():
        match = re.match(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (tests/[^ ]+)", line)
        if match:
            status, identity = match.groups()
            if identity in result:
                raise ValueError("duplicate_outcome_identity:" + identity)
            result[identity] = status
    return result


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    folder = root / "_build/gy-gaps/c1/selector-return"
    receipts = {name: json.loads((folder / (name + ".json")).read_text()) for name in
                ("native-red", "bootstrap-pre-review-red-actual", "owner-first-green", "route-removal")}
    green = receipts["owner-first-green"]
    selected = [item for item in green["command"] if item.startswith("tests/")]
    files = {item.split("::")[0] for item in selected}
    definitions = {path: {node.name: node for node in ast.parse((root/path).read_text()).body
                         if isinstance(node, ast.FunctionDef)} for path in files}
    expected = []
    product_count = 0
    for selector in selected:
        path, name = selector.split("::")
        node = definitions[path][name]
        parameter_values = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "parametrize":
                assert isinstance(ast.literal_eval(decorator.args[0]), str)
                assert "," not in ast.literal_eval(decorator.args[0]), "extend independent identity expander for tuple parameters"
                assert not any(keyword.arg == "ids" for keyword in decorator.keywords)
                parameter_values.append(ast.literal_eval(decorator.args[1]))
        size = 1
        for values in parameter_values:
            size *= len(values)
        product_count += size
        if not parameter_values:
            expected.append(selector)
        else:
            expected.extend(selector + "[" + "-".join(str(value) for value in values) + "]"
                            for values in itertools.product(*reversed(parameter_values)))
    actual = outcomes(green)
    report = {"declared_command_receipt": "owner-first-green.json",
              "file_type_denominator": "complete Python ASTs of every file selected by that command",
              "source_files": sorted(files), "selected_function_count": len(selected),
              "ast_expanded_case_count": len(expected), "independent_product_count": product_count,
              "actual_unique_outcome_count": len(actual),
              "missing_outcomes": sorted(set(expected)-set(actual)),
              "unexpected_outcomes": sorted(set(actual)-set(expected)),
              "nonpassing": {key:value for key,value in actual.items() if value != "PASSED"},
              "comparisons": {}}
    assert len(expected) == len(set(expected)) == product_count
    assert set(expected) == set(actual) and all(value == "PASSED" for value in actual.values())
    for name, receipt in receipts.items():
        if name == "owner-first-green":
            continue
        measured = outcomes(receipt)
        assert measured and set(measured) <= set(actual)
        assert all(value == "FAILED" for value in measured.values()), (name, measured)
        report["comparisons"][name] = {"receipt": name + ".json",
            "baseline_missing_identities": sorted(set(measured)-set(actual)),
            "identities_changing_pass_to_fail": sorted(measured),
            "crashed_or_skipped_identities": []}
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
