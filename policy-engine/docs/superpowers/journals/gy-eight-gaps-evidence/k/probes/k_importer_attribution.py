"""Reconcile an exact base/current importer failure without claiming disjointness."""

import ast
import json
from pathlib import Path
import re
import subprocess


root = Path.cwd()
base = root.parents[1] / "gygaps-lane-base" / "policy-engine"
relative = "tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py"
name = "test_claim_axes_round_trip_through_activated_writer_and_all_public_readers"
base_receipt = json.loads((base / "_build/gy-gaps/k-original-base-importer.json").read_text())
current_receipt = json.loads((root / "_build/gy-gaps/k/importer-current-attribution.json").read_text())
assert base_receipt["command"] == current_receipt["command"]
expected_command = [".venv/bin/python", "-m", "pytest", "-q", "-s", f"{relative}::{name}"]
assert base_receipt["command"] == expected_command
failure_sets = [sorted(set(re.findall(r"^FAILED (\S+)", receipt["stdout"], re.M))) for receipt in (base_receipt, current_receipt)]
reason = "ValueError: claim_adjudication_verified_rows_capability_required"
assert failure_sets[0] == failure_sets[1] == [f"{relative}::{name}"]
assert all(reason in receipt["stdout"] and receipt["returncode"] == 1 and not receipt["timed_out"] for receipt in (base_receipt, current_receipt))
base_sha = subprocess.check_output(["git", "-C", str(base), "rev-parse", "HEAD"], text=True).strip()
assert base_sha == "43580c80b8761d4aecb34ee3300f64d389be80c8"
assert not subprocess.check_output(["git", "-C", str(base), "status", "--porcelain"], text=True).strip()
node = next(node for node in ast.parse((root / relative).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
imports = [{"module": node.module, "names": [alias.name for alias in node.names], "line": node.lineno} for node in ast.walk(node) if isinstance(node, ast.ImportFrom)]
changed = set(subprocess.check_output(["git", "diff", "--name-only", "--relative"], text=True).splitlines())
intersection = sorted({"src/" + row["module"].replace(".", "/") + ".py" for row in imports if row["module"]} & changed)
assert intersection, "Do not infer disjointness from a reproduced failure"
print(json.dumps({
    "slice_base": base_sha, "exact_commands_equal": True, "complete_failure_identity_sets": failure_sets,
    "same_deciding_exception": reason, "complete_direct_imports_in_selected_test": imports,
    "changed_direct_inputs": intersection, "complete_transitive_input_denominator": "not_established",
    "P41_attribution": "not_established; reproduced but changed inputs intersect, so no inherited/disjoint claim",
    "base_tree_clean": True,
}, indent=2))
