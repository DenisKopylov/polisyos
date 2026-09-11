"""Locate the strict example assertion separately from the general wire enum."""
import ast
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
selections = {
    "policy-engine/src/polisyos/core/contracts/decision_validity.py": {"DecisionValidityStatus", "EpochValidityBatchTarget"},
    "policy-engine/src/polisyos/runtime/http/openapi_contract.py": {"_epoch_validity_batch_example"},
    "policy-engine/tests/unit/runtime/http/test_runtime_api_contract_hardening.py": {"test_epoch_batch_success_example_is_owner_derived_and_strict", "test_epoch_validity_batch_success_example_matches_its_wire_contract"},
}
result = {"base": "63bdb9640", "complete_selected_definition_denominator": 5, "files": []}
for path, names in selections.items():
    source = subprocess.check_output(["git", "show", f"63bdb9640:{path}"], cwd=ROOT).decode()
    tree = ast.parse(source)
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == names
    result["files"].append({"path": path, "definitions": [{"name": n.name, "line": n.lineno, "assertions": [ast.unparse(a.test) for a in ast.walk(n) if isinstance(a, ast.Assert)], "string_values": sorted({s.value for s in ast.walk(n) if isinstance(s, ast.Constant) and isinstance(s.value, str) and len(s.value)<120}), "calls": sorted({ast.unparse(c.func) for c in ast.walk(n) if isinstance(c, ast.Call)})} for n in nodes]})
result["exit_code"] = 0
(OUT/"openapi-scope.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
