"""Independent actual typed-canonical decode to native fiscal/compound/stopping consumer."""
from __future__ import annotations
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.methods.search import objective as objective_module
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective, CompositeObjective
from polisyos.scientist.methods.search.stopping import ImprovementPlateau, TargetAchieved

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path("/dev/shm/e02-D-oct07-continuation")
paths = ["src/polisyos/scientist/methods/search/objective.py", "src/polisyos/scientist/methods/search/stopping.py", "src/polisyos/core/canon/canon_json.py", "src/polisyos/common/canonical.py"]

def hashes():
    result = {}
    for path in paths:
        data = (root / "policy-engine" / path).read_bytes()
        canonical = subprocess.check_output(["git", "-C", str(root), "show", args.source + ":policy-engine/" + path])
        assert data == canonical, "source dependency differs from pinned candidate: " + path
        result[path] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    assert Path(objective_module.__file__).resolve() == root / "policy-engine/src/polisyos/scientist/methods/search/objective.py"
    return result

before = hashes()
cases = [
    ("positive_tiny_balance", {"gov_balance": Decimal("1e-1000")}, "unavailable", None),
    ("negative_tiny_balance", {"gov_balance": Decimal("-1e-1000")}, "unavailable", None),
    ("positive_tiny_deficit", {"budget_deficit": Decimal("1e-1000")}, "unavailable", None),
    ("negative_tiny_deficit", {"budget_deficit": Decimal("-1e-1000")}, "unavailable", None),
    ("tiny_balance_alias_conflict", {"gov_balance": Decimal("1e-1000"), "government_balance": Decimal(0), "budget_deficit": 12}, "unavailable", None),
    ("legacy_numeric_string_tiny", {"budget_deficit": "-1e-1000"}, "unavailable", None),
    ("genuine_decimal_zero", {"budget_deficit": Decimal("0E-1000")}, "available", 0.0),
    ("genuine_integer_zero", {"gov_balance": 0, "budget_deficit": 12}, "available", 0.0),
    ("ordinary_decimal_balance", {"gov_balance": Decimal(-5)}, "available", 5.0),
    ("representable_small_deficit", {"budget_deficit": Decimal("1e-300")}, "available", 1e-300),
    ("malformed_present_no_fallback", {"gov_balance": "bad", "budget_deficit": 0}, "unavailable", None),
    ("boolean_false_not_zero", {"gov_balance": False}, "unavailable", None),
    ("null_balance_legacy_fallback", {"gov_balance": None, "budget_deficit": 12}, "available", 12.0),
]

def scalar(value):
    return value if math.isfinite(value) else {"nonfinite": str(value)}

rows = []
for name, source_input, expected, expected_value in cases:
    wire = to_canonical_bytes(source_input, CanonSpec(forbid_floats=False))
    decoded = from_canonical_bytes(wire)
    objective = BudgetDeficitObjective(threshold=0)
    actual = objective.evaluate(decoded)
    compound = CompositeObjective([objective]).evaluate(decoded)
    observed = "available" if math.isfinite(actual.raw_value) else "unavailable"
    history = [{"objective_value": 0.0}, {"objective_value": compound.normalized_value}]
    plateau = ImprovementPlateau(patience=1, objective_unit="declared_fixture_float64_units").check(history, {})
    target = TargetAchieved(0.0).check(history, {})
    matches = observed == expected and (expected_value is None or actual.raw_value == expected_value)
    if expected == "unavailable":
        matches = matches and not actual.is_satisfied and not compound.is_satisfied and not plateau.should_stop and not target.should_stop
    rows.append({"case": name, "wire_utf8": wire.decode(), "wire_sha256": hashlib.sha256(wire).hexdigest(), "actual_decoded_values": {key: {"type": type(value).__name__, "repr": str(value)} for key, value in decoded.items()}, "expected_state": expected, "expected_value": expected_value, "actual_state": observed, "actual_raw": scalar(actual.raw_value), "actual_satisfied": actual.is_satisfied, "actual_compound_raw": scalar(compound.raw_value), "plateau": {"should_stop": plateau.should_stop, "reason": plateau.reason, "details": plateau.details}, "target_should_stop": target.should_stop, "check": "PASS" if matches else "FAIL"})
after = hashes()
record = {"schema": "e02.D.fiscal_actual_canonical_decoder_review.v1", "source_sha": args.source, "source_tree": subprocess.check_output(["git", "-C", str(root), "rev-parse", args.source + "^{tree}"], text=True).strip(), "runtime": {"executable": sys.executable, "python": sys.version}, "inputs_before": before, "inputs_after": after, "source_unchanged": before == after, "cases": rows, "check_counts": {label: sum(row["check"] == label for row in rows) for label in ("PASS", "FAIL")}, "limits": ["Actual typed canonical bytes and decoder, existing fiscal/compound/stopping consumer; no mocked result or same-helper numerical oracle.", "Float64 original-nonzero admission only; missing fiscal issuer unit/sign/alias scientific law remains separate owner input.", "Already rounded zero cannot recover original lexeme; arbitrary precision aliases and other objective families outside this bounded claim."]}
args.output.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
print(json.dumps({"output": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "checks": record["check_counts"], "source_unchanged": record["source_unchanged"]}))
raise SystemExit(bool(record["check_counts"]["FAIL"]))
