"""Reconcile actual failing identities with the exact corrected controls."""
from __future__ import annotations
import ast
import json
import re
from pathlib import Path

ROOT = Path("_build/gy-gaps/d1/n9")
TEST = Path("tests/unit/runtime/quality/test_promotion_sequence.py")

def failed(run):
    return set(re.findall(r"^FAILED (\S+)", run["stdout"], re.MULTILINE))

def main():
    before = json.loads((ROOT / "final-focused.json").read_text())
    after = json.loads((ROOT / "final-corrected-controls.json").read_text())
    assert before["returncode"] == 1 and not before["timed_out"]
    assert after["returncode"] == 0 and not after["timed_out"] and not failed(after)
    functions = {node.name: node for node in ast.parse(TEST.read_text()).body if isinstance(node, ast.FunctionDef)}
    selected = set()
    for argument in after["command"]:
        if "::test_" not in argument:
            continue
        path, name = argument.split("::", 1)
        if "[" in name:
            selected.add(argument)
            continue
        parameters = []
        for decorator in functions[name].decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "parametrize":
                assert ast.literal_eval(decorator.args[0]) == "mutation"
                parameters.extend(ast.literal_eval(decorator.args[1]))
        assert parameters
        selected.update(f"{path}::{name}[{value}]" for value in parameters)
    observed = {f"{TEST}::test_n9_measurement_recomputes_full_authority_identity[{value}]" for value in re.findall(r"Valid CAS with changed (\w+) and intact", after["stdout"])}
    observed.update(argument for argument in after["command"] if "[contract_changed]" in argument)
    assert selected == observed == failed(before)
    removals = []
    for filename, identity in (
        ("source-replay-removal.json", f"{TEST}::test_n9_replays_current_measurement_source_at_admission[source_changed]"),
        ("contract-decision-removal.json", f"{TEST}::test_n9_measurement_refuses_out_of_contract_observations"),
    ):
        run = json.loads((ROOT / filename).read_text())
        assert run["returncode"] == 1 and not run["timed_out"]
        assert failed(run) == {identity}
        assert "AssertionError: assert <PromotionObligationStatus.SATISFIED" in run["stdout"]
        removals.append({"receipt": filename, "introduced_failure_identity": identity})
    print(json.dumps({"corrected_failure_identity_delta": sorted(selected), "unresolved_failure_identities": [], "crosscheck": "full failure lines == AST-expanded selected controls == observed mutation controls plus exact selected governing-contract case", "removal_deltas": removals}, indent=2))

if __name__ == "__main__":
    main()
