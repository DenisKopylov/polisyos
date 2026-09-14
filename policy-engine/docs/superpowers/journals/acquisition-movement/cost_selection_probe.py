"""Internal Stage 2 cost-slot research, never an admission or generic absence gate."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "outliers"))
from census import ResearchReads, emit_result

ROOT = Path(__file__).resolve().parents[5]


def main() -> int:
    measured = ResearchReads(ROOT)
    inventory = measured.git(
        ["ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "*.py"]
    )
    selected = set((inventory or "").split("\0")) - {""}
    check = subprocess.run(
        ["rg", "--files", "--hidden", "-g", "*.py", "-0"],  # noqa: S607 - fixed read-only census
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    rg_paths = set(check.stdout.decode().split("\0")) - {""}
    enumeration = {
        "command": ["rg", "--files", "--hidden", "-g", "*.py", "-0"],
        "returncode": check.returncode,
        "stderr": check.stderr.decode(),
        "symmetric_difference": sorted(selected ^ rg_paths),
    }
    if check.returncode or selected != rg_paths:
        measured.fail(
            "repository Python inventory", "independent enumeration", ValueError(enumeration)
        )
    names = {
        "produce_acquisition_cost_basis_record",
        "load_planner_acquisition_cost_schedule",
        "PlannerAcquisitionCostSchedule",
        "PlannerAcquisitionCostScheduleRow",
    }
    calls, definitions, insensitive_hits, owner_assignments = [], [], [], []
    owner = "policy-engine/src/polisyos/runtime/quality/acquisition_planner.py"
    quote_pattern = re.compile(
        r"(?:cost.{0,20}quote|quote.{0,20}cost|acquisition.{0,20}quote|quote.{0,20}acquisition)",
        re.I,
    )
    quote_candidates = []
    for path in sorted(selected):
        text = measured.text(path)
        if text is None:
            continue
        try:
            tree = ast.parse(text, filename=path)
        except Exception as exc:
            measured.fail(path, "ast.parse", exc)
            continue
        aliases = {
            alias.asname or alias.name: alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name in names
            ):
                definitions.append({"path": path, "line": node.lineno, "name": node.name})
            if isinstance(node, ast.Call):
                value = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                value = aliases.get(value, value)
                if value in names:
                    calls.append(
                        {
                            "path": path,
                            "line": node.lineno,
                            "name": value,
                            "expression": ast.unparse(node),
                        }
                    )
            if (
                path == owner
                and isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "_ACQUISITION_GAP_BASIS"
                    for t in node.targets
                )
            ):
                owner_assignments.append(node)
        if any(name.casefold() in text.casefold() for name in names):
            insensitive_hits.append(path)
        if quote_pattern.search(text):
            quote_candidates.append(path)
    registry = (
        "policy-engine/architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
    )
    registry_text = measured.text(registry)
    comparison = {}
    try:
        if len(owner_assignments) != 1 or registry_text is None:
            raise ValueError("canonical inputs absent or ambiguous")
        basis = ast.literal_eval(owner_assignments[0].value)
        independent_keys = [node.value for node in owner_assignments[0].value.keys]
        if sorted(basis) != sorted(independent_keys):
            raise ValueError("independent AST dictionary key check differs")
        entries = json.loads(registry_text)["entries"]
        targets = [row["target_variable"] for row in entries]
        exact = sorted(set(basis) & set(targets))
        folded = sorted({key.casefold() for key in basis} & {key.casefold() for key in targets})
        comparison = {
            "schedule_row_denominator": len(basis),
            "registry_entry_denominator": len(entries),
            "complete_schedule_keys": sorted(basis),
            "independent_ast_keys": independent_keys,
            "complete_registry_targets": [
                {
                    "entry_id": row["entry_id"],
                    "target_variable": row["target_variable"],
                    "source_lane": row["source_lane"],
                }
                for row in entries
            ],
            "exact_intersection": exact,
            "case_insensitive_intersection": folded,
        }
    except Exception as exc:
        measured.fail(owner + " + " + registry, "canonical selector comparison", exc)
    return emit_result(
        {
            "counterexample_before_search": (
                "An existing externally supplied schedule caller or a canonical "
                "WDI target may already share an exact admitted cost row; enumerate all repository "
                "Python source and canonical entries, then check case-insensitive identities too."
            ),
            "registered_caller": "internal Stage 2 research; not a production admission command",
            "selector": (
                "all nonignored tracked/untracked repository .py files plus the exact "
                "canonical acquisition registry .json"
            ),
            "file_type_denominator": {".py": len(selected), ".json": 1},
            "independent_enumeration": enumeration,
            "definitions": definitions,
            "direct_ast_calls": calls,
            "case_insensitive_symbol_candidate_paths": insensitive_hits,
            "case_insensitive_quote_candidate_paths": quote_candidates,
            "canonical_comparison": comparison,
            "exclusions": [
                "ignored paths",
                "other file types",
                "external/institutional registries",
            ],
            "unresolved_by_construction": [
                "AST caller names do not settle arbitrary dynamic dispatch",
                "keyword candidates do not establish quote semantics",
                "non-Python and external owner capabilities are unselected",
                "Git/rg enumeration internal reads are outside file-content receipts",
                "source interpretation does not replay production behavior",
            ],
            **measured.fields(),
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
