"""Compare the complete selected owner schedule with the selected residual set."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from census import ResearchReads, emit_result

ROOT = Path(__file__).resolve().parents[5]


def main() -> int:
    owner = "src/polisyos/runtime/quality/acquisition_planner.py"
    artifact = "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    measured = ResearchReads(ROOT)
    source, artifact_text = measured.text(owner), measured.text(artifact)
    comparison = {}
    if source is not None and artifact_text is not None:
        try:
            parsed = ast.parse(source)
            assignments = [
                node
                for node in parsed.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "_ACQUISITION_GAP_BASIS"
                    for t in node.targets
                )
            ]
            if len(assignments) != 1:
                raise ValueError("owner schedule assignment must be unique")
            basis = ast.literal_eval(assignments[0].value)
            independent = [key.value for key in assignments[0].value.keys]
            if set(basis) != set(independent):
                raise ValueError("independent schedule keys disagree")
            rows = json.loads(artifact_text)["growth_backlog"]
            ids = [row["variable_id"] for row in rows]
            comparison = {
                "schedule_row_denominator": len(basis),
                "backlog_row_denominator": len(ids),
                "complete_schedule_keys": sorted(basis),
                "independent_ast_keys": independent,
                "complete_backlog_keys": ids,
                "exact_intersection": sorted(set(basis) & set(ids)),
                "case_insensitive_intersection": sorted(
                    {key.casefold() for key in basis} & {key.casefold() for key in ids}
                ),
            }
        except Exception as exc:
            measured.fail(f"{owner} + {artifact}", "schedule/backlog interpretation", exc)
    result = {
        "counterexample_before_search": "An existing exact cost schedule may contain residuals "
        "despite missing surface fields; compare every key including case-insensitive identities.",
        "selector": [owner, artifact],
        "file_type_denominator": {".py": 1, ".json": 1},
        "exclusions": ["all other source files and artifacts", "runtime-computed schedules"],
        "unresolved_by_construction": [
            "unselected owner schedules in other files",
            "external or future owner schedules",
            "source interpretation, not runtime execution",
        ],
        **comparison,
        **measured.fields(),
    }
    return emit_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
