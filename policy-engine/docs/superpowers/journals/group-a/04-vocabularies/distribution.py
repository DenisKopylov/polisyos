"""Complete package denominators and broader demand, without semantic zero inference."""
from collections import Counter
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
raw = json.loads((OUT / "raw/census.json").read_text())
summary = json.loads((OUT / "summary.json").read_text())
exact = json.loads((OUT / "exact-case-density.json").read_text())
trace_path = OUT.parent / "03-phase5/raw/trace.json"
trace = json.loads(trace_path.read_text())
index = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")) - {""}
baseline = set(trace["paths"])
additions = {p for p in index if p.startswith("policy-engine/docs/superpowers/journals/group-a/") or p.startswith("policy-engine/docs/superpowers/specs/2026-09-11-group-a-")}
assert index - additions == baseline
packages = Counter(p.split("/")[3] if len(p.split("/")) > 4 else "[root]" for p in raw["source_paths"])
rows = []
for package, denominator in sorted(packages.items()):
    row = {"package": package, "python_files": denominator}
    for term in exact["terms"]:
        row[term] = {"exact_case_files": exact["terms"][term]["by_package_files"].get(package, 0), "ast_identifier_files": summary["density"][term]["identifier_nodes"]["by_package_files"].get(package, 0), "ast_identifier_nodes": summary["density"][term]["identifier_nodes"]["by_package_nodes"].get(package, 0)}
    rows.append(row)
assert sum(r["python_files"] for r in rows) == len(raw["source_paths"])
assurance = []
pattern = re.compile(r"assurance[_ -]?levels?|limited assurance|reasonable assurance|\bISAE\b|\bSSAE\b", re.I)
for match in trace["text_matches"]:
    selected = [v for v in match["matches"] if pattern.search(v["text"])]
    if selected:
        assurance.append({"path": match["path"], "lines": [v["line"] for v in selected], "truncated_matching_lines": [v["line"] for v in selected if v["truncated"]]})
sources = [
    "policy-engine/src/polisyos/fabric/evidence/acquisition_assurance.py",
    "policy-engine/src/polisyos/fabric/evidence/ceiling_relations.py",
    "policy-engine/src/polisyos/lex/knowledge/multilingual_assurance.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/causal/estimand_compiler.py",
    "policy-engine/src/polisyos/ir/analytics/estimand.py",
    "policy-engine/src/polisyos/ir/analytics/normative_arbitration.py",
    "policy-engine/src/polisyos/scientist/nodes/builtins/governance/run_normative_arbitration.py",
    "policy-engine/src/polisyos/core/artifacts/write_contract.py",
    "policy-engine/src/polisyos/core/artifacts/ownership.py",
]
definitions = []
for path in sources:
    tree = ast.parse(subprocess.check_output(["git", "show", f"63bdb9640:{path}"], cwd=ROOT).decode())
    definitions.append({"path": path, "definitions": [{"name": n.name, "kind": type(n).__name__, "line": n.lineno} for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]})
out = {
    "base": raw["base"],
    "whole_tree_index_denominator": len(index - additions),
    "whole_tree_list_equals_index_excluding_analysis": True,
    "complete_source_package_distribution": rows,
    "four_terms": list(exact["terms"]),
    "assurance_query_scope": "12838 readable tracked text files out of 12900; register and ledger omitted from evidence matches; 62 undecodable files remain ambiguous",
    "assurance_matches": assurance,
    "assurance_query_limit": "The input trace limits displayed lines to 1000 characters; paths are navigation receipts, not a complete consumer or exact occurrence census. No zero inferred.",
    "selected_delivered_owner_ast_denominator": sources,
    "selected_owner_definitions": definitions,
    "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/"raw/census.json", OUT/"summary.json", OUT/"exact-case-density.json", trace_path]},
    "exit_code": 0,
}
(OUT/"distribution.json").write_text(json.dumps(out, indent=2)+"\n")
print(json.dumps({k:v for k,v in out.items() if k not in ["selected_owner_definitions", "assurance_matches"]}, indent=2))
