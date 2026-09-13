"""Read-only bounded census for the two acquisition movement outliers."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent / "raw"
OUT.mkdir(exist_ok=True)


def receipt(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    selectors = ["src", "tools", "tests"]
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", *selectors], cwd=ROOT
    ).decode().split("\0")
    source_set = {p for p in tracked if p.endswith(".py")}
    tree = subprocess.check_output(
        ["git", "ls-tree", "-rz", "--name-only", "HEAD", "--", *selectors], cwd=ROOT
    ).decode().split("\0")
    tree_set = {p for p in tree if p.endswith(".py")}
    print("Counterexample before census: an aliased, differently cased or later producer "
          "may already bind metric residuals to a real VOI decision and expected value/cost. "
          "AST direct/attribute calls and case-insensitive semantic tokens are measured; "
          "dynamic dispatch and external stores remain unresolved_by_construction.")
    names = {"plan_evidence_acquisition", "plan_requirement_gap_acquisition",
             "derive_growth_backlog", "plan_from_required_data"}
    calls, defs, reads, ambiguous, token_hits = [], [], [], [], []
    pattern = re.compile(r"\b(?:evsi|evpi|expected_value|expected_cost|value_of_information)\b", re.I)
    for relative in sorted(source_set):
        path = ROOT / relative
        try:
            source = path.read_text()
            reads.append(receipt(path))
            parsed = ast.parse(source, filename=relative)
        except Exception as exc:
            ambiguous.append({"path": relative, "error": repr(exc)})
            continue
        aliases = {}
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    aliases[alias.asname or alias.name] = alias.name
        for node in ast.walk(parsed):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.casefold() in names:
                defs.append({"path": relative, "line": node.lineno, "name": node.name})
            if isinstance(node, ast.Call):
                name = (node.func.id if isinstance(node.func, ast.Name) else
                        node.func.attr if isinstance(node.func, ast.Attribute) else "")
                resolved = aliases.get(name, name)
                if resolved.casefold() in names:
                    calls.append({"path": relative, "line": node.lineno,
                                  "name": resolved, "call": ast.unparse(node)})
        if pattern.search(source):
            token_hits.append(relative)
    artifact = ROOT / "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
    data = json.loads(artifact.read_text())
    backlog = data["growth_backlog"]
    keys = sorted({key for row in backlog for key in row})
    independent_ids = [row["variable_id"] for row in data["reverse_demand_residuals"]]
    absent_keys = ["voi_ranking_ref", "decision_owner_ref", "decision_ref", "ranking_ref",
                   "owner_decision", "expected_value", "expected_cost", "cost_basis"]
    rows = {"artifact": receipt(artifact), "row_denominator": len(backlog),
            "row_ids": [row["variable_id"] for row in backlog], "keys": keys,
            "independent_reverse_residual_ids": independent_ids,
            "residual_symmetric_difference": sorted(set(independent_ids) ^
                                                     {row["variable_id"] for row in backlog}),
            "distributions": {key: dict(Counter(str(row.get(key)) for row in backlog))
                              for key in ["voi_owner_fit", "authority_boundary", "ranking_method",
                                          "binding_confidence", "ranking_score", "voi_owner_ref"]},
            "key_occurrences_case_insensitive": {
                key: sum(any(k.casefold() == key for k in row) for row in backlog)
                for key in absent_keys}}
    result = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"],cwd=ROOT,text=True).strip(),
              "selector": selectors, "file_type_denominator": {".py": len(source_set)},
              "independent_tree_difference": sorted(source_set ^ tree_set),
              "successful_reads": reads, "ambiguous": ambiguous, "definitions": defs,
              "calls": calls, "case_insensitive_semantic_token_files": token_hits,
              "numeric_rows": rows,
              "unresolved_by_construction": ["dynamic Python dispatch", "non-Python producers",
                  "external artifact stores", "semantic meaning not established by token matching",
                  "unselected authority documents", "historical education native/Git input closure"]}
    (OUT / "census.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {
        "successful_reads", "case_insensitive_semantic_token_files"}}, indent=2))


if __name__ == "__main__":
    main()
