"""Remove only the new fiscal nonzero-underflow refusal on actual native consumers."""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess

_GUARD = ast.parse(
    "if value == 0.0 and isinstance(raw_value, (Decimal, str)) and Decimal(raw_value) != 0:\n"
    "    return _INVALID\n"
).body[0]


def _scalar(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite": str(value)}
    return value


def pytest_configure(config):
    from polisyos.scientist.methods.search import objective
    from polisyos.scientist.methods.search.stopping import ImprovementPlateau, TargetAchieved

    root = Path("/dev/shm/e02-D-oct07-continuation")
    source = os.environ["E02_FISCAL_EXPECTED_SOURCE"]
    assert subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() == source
    path = root / "policy-engine/src/polisyos/scientist/methods/search/objective.py"
    data = path.read_bytes()
    qualified = subprocess.check_output(["git", "-C", str(root), "show", source + ":policy-engine/src/polisyos/scientist/methods/search/objective.py"])
    assert data == qualified and Path(objective.__file__).resolve() == path
    tree = ast.parse(data)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_read_metric_aliases")
    removed = []
    for node in ast.walk(function):
        if isinstance(node, ast.Try):
            guards = [item for item in node.body if isinstance(item, ast.If) and ast.dump(item, include_attributes=False) == ast.dump(_GUARD, include_attributes=False)]
            for guard in guards:
                node.body.remove(guard)
                removed.append(guard)
    assert len(removed) == 1, "exact one reviewed guard must be present"
    replacement = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(replacement, "<reviewed-single-fiscal-guard-removal>", "exec"), objective.__dict__)
    original = objective.BudgetDeficitObjective.evaluate

    def observed(self, results):
        actual = original(self, results)
        history = [{"objective_value": 0.0}, {"objective_value": actual.normalized_value}]
        plateau = ImprovementPlateau(patience=1, objective_unit="declared_fixture_float64_units").check(history, {})
        target = TargetAchieved(0.0).check(history, {})
        print("REMOVAL_FISCAL_OBSERVATION " + json.dumps({
            "source": source,
            "source_file_sha256": hashlib.sha256(data).hexdigest(),
            "removed_guard_count": len(removed),
            "actual_inputs": {key: {"type": type(value).__name__, "repr": str(value)} for key, value in results.items()},
            "raw_value": _scalar(actual.raw_value),
            "normalized_value": _scalar(actual.normalized_value),
            "is_satisfied": actual.is_satisfied,
            "actual_plateau": {"should_stop": plateau.should_stop, "reason": plateau.reason, "details": plateau.details},
            "actual_target_should_stop": target.should_stop,
            "retained": ["actual Gateway response-text decoder", "raw Decimal nonzero", "bool/finite/overflow and alias rules", "source/context/metric markers", "actual stopping implementations"]
        }, allow_nan=False))
        return actual

    objective.BudgetDeficitObjective.evaluate = observed
