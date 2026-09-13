"""Compare the complete owner cost schedule with the selected residual set."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]


def main() -> None:
    print("Counterexample before complete schedule comparison: an existing exact "
          "cost schedule may contain the residuals despite missing surface fields; "
          "compare every key, including case-insensitive identities.")
    owner = ROOT / "src/polisyos/runtime/quality/acquisition_planner.py"
    parsed = ast.parse(owner.read_text())
    assignments = [node for node in parsed.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_ACQUISITION_GAP_BASIS"
                           for t in node.targets)]
    assert len(assignments) == 1
    basis = ast.literal_eval(assignments[0].value)
    independent = [key.value for key in assignments[0].value.keys]
    assert set(basis) == set(independent)
    artifact = ROOT / "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    rows = json.loads(artifact.read_text())["growth_backlog"]
    ids = [row["variable_id"] for row in rows]
    result = {
        "file_type_denominator": {".py": 1, ".json": 1},
        "inputs": [{"path": str(path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for path in [owner, artifact]],
        "schedule_row_denominator": len(basis), "backlog_row_denominator": len(ids),
        "complete_schedule_keys": sorted(basis), "independent_ast_keys": independent,
        "complete_backlog_keys": ids,
        "exact_intersection": sorted(set(basis) & set(ids)),
        "case_insensitive_intersection": sorted(
            {key.casefold() for key in basis} & {key.casefold() for key in ids}),
        "unresolved_by_construction": ["external or future owner schedules",
                                      "source interpretation, not runtime execution"],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
