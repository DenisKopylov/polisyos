"""Reconcile commissioned rows and unwritten pytest identities at the lane base."""

# Constant Git argv, no shell; stdout is this research instrument's required receipt.
# ruff: noqa: S603, S607, T201
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "policy-engine" / "src"))
from polisyos.common.markdown import split_markdown_table_row  # noqa: E402 - repo root entry

reads = []
failed_reads = []
base = "034f30c64a79eb2020c04c6f0b0f07c90a74a1ee"
ids = (
    "ds8-public-case-publication",
    "ds8-signed-public-decision-surface",
    "ds10-public-decision-rendering",
    "DS11-PUBLIC-SIGNATURE-POPULATION",
    "DS11-GROUNDED-PERFORMANCE",
)
nodes = {
    "ds10-public-decision-rendering": (
        "tests/unit/runtime/http/test_public_export.py::test_public_decision_proj"
        "ection_is_custody_bound"
    ),
    "DS11-PUBLIC-SIGNATURE-POPULATION": (
        "tests/unit/runtime/http/test_public_export.py::test_first_governed_publi"
        "c_signature_is_custody_bound"
    ),
    "DS11-GROUNDED-PERFORMANCE": (
        "tests/integration/runtime_quality/test_first_governed_promotion.py::test"
        "_promoted_design_supplies_content_bound_public_performance_evidence"
    ),
}
listing = subprocess.check_output(
    ["git", "ls-tree", "-r", base, "--", "policy-engine/tests"], text=True
)
files = {}
for line in listing.splitlines():
    metadata, path = line.split("\t", 1)
    if path.endswith(".py"):
        files[path] = metadata.split()[2]
matched_names = {node.split("::")[-1]: [] for node in nodes.values()}
parse_errors = []
read_mismatches = []
for path, blob in files.items():
    try:
        data = (root / path).read_bytes()
    except OSError as exc:
        failed_reads.append({"path": path, "error": str(exc)})
        continue
    reads.append(
        {
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "operation": "read_bytes",
        }
    )
    local = hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
    ).hexdigest()
    if local != blob:
        read_mismatches.append(path)
        continue
    try:
        tree = ast.parse(data, filename=path)
    except SyntaxError as exc:
        parse_errors.append({"path": path, "error": str(exc)})
        continue
    for item in ast.walk(tree):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.casefold() in {
            name.casefold() for name in matched_names
        }:
            matched_names[
                next(name for name in matched_names if name.casefold() == item.name.casefold())
            ].append({"path": path, "line": item.lineno})
rows = {}
ledger = {}
for rel, target in [
    ("policy-engine/docs/plans/active/DEBT-REGISTER.md", rows),
    ("policy-engine/docs/plans/active/LEDGER.md", ledger),
]:
    data = subprocess.check_output(["git", "show", f"{base}:{rel}"], text=True)
    reads.append(
        {
            "path": rel,
            "revision": base,
            "sha256": hashlib.sha256(data.encode()).hexdigest(),
            "operation": "git show",
        }
    )
    for n, line in enumerate(data.splitlines(), 1):
        if not line.startswith("| "):
            continue
        cells = split_markdown_table_row(line)
        first_cell = cells[0].strip() if cells else ""
        for debt_id in ids:
            if first_cell == f"`{debt_id}`" or first_cell.startswith(f"[`{debt_id}`]("):
                target.setdefault(debt_id, []).append({"line": n, "text": line})
index = set(
    subprocess.check_output(
        ["git", "ls-files", "-z", "--", "policy-engine/tests"], text=True
    ).split("\0")
)
index = {path for path in index if path.endswith(".py")}
result = {
    "counterexample_before_search": (
        "A required function may exist in another tracked test module, as async "
        "or with different case; a missing named path alone does not establish "
        "its absence."
    ),
    "actual_inputs_read": reads,
    "failed_read_attempts": failed_reads,
    "independent_index_crosscheck": {
        "count": len(index),
        "index_only": sorted(index - set(files)),
        "tree_only": sorted(set(files) - index),
    },
    "unresolved_by_construction": [
        {
            "class": "dynamic_test_generation",
            "property": (
                "Static AST does not establish generated pytest identities or runtime collection."
            ),
        },
        {
            "class": "outside_tracked_test_selector",
            "property": (
                "Non-Python tests, untracked tests, external services and other authority"
                " documents are not interpreted."
            ),
        },
        {
            "class": "python_import_dependencies",
            "property": (
                "Canonical Markdown parser import dependencies are not independently "
                "content-bound by this script."
            ),
        },
        {
            "class": "non_atomic_observation",
            "property": (
                "Git tree/index and disk reads occur sequentially; later changes are not "
                "a reservation."
            ),
        },
    ],
    "base": base,
    "mode": "read-only AST + exact rows; no pytest execution",
    "denominator": {
        "path": "policy-engine/tests/**",
        "file_type": "all git-tree tracked .py files at base",
        "count": len(files),
        "path_set_sha256": hashlib.sha256(("\n".join(sorted(files)) + "\n").encode()).hexdigest(),
        "read_blob_mismatches": read_mismatches,
        "ast_parse_errors": parse_errors,
    },
    "required_nodes": {
        debt: {
            "selector": selector,
            "path_in_denominator": "policy-engine/" + selector.split("::")[0] in files,
            "same_name_ast_definitions_in_complete_denominator": matched_names[
                selector.split("::")[-1]
            ],
        }
        for debt, selector in nodes.items()
    },
    "register_denominator": (
        "Every Markdown table row in docs/plans/active/DEBT-REGISTER.md at base, "
        "exact first-cell identity filtered to commissioned five"
    ),
    "register_rows": rows,
    "ledger_denominator": (
        "Every Markdown table row in docs/plans/active/LEDGER.md at base, exact "
        "first-cell identity filtered to commissioned five"
    ),
    "ledger_rows": ledger,
}
result["status"] = (
    "UNRUN"
    if parse_errors or read_mismatches or failed_reads or index != set(files)
    else "complete_bounded_census"
)
result["row_identity_reconciled"] = all(
    len(rows.get(x, [])) == 1 and len(ledger.get(x, [])) == 1 for x in ids
)
print(json.dumps(result, indent=2))
raise SystemExit(
    0 if result["status"] == "complete_bounded_census" and result["row_identity_reconciled"] else 1
)
