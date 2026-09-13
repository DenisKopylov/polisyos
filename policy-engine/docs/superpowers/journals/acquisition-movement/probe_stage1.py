"""Read-only, bounded Stage 1 census; not a runtime or registration authority."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

from polisyos.common.markdown import split_markdown_table_row

ROOT = Path(__file__).resolve().parents[4]
ROWS = (
    "GY-GAP6",
    "ds15-gy-gap6-evidence-register-closure",
    "ds15-deterministic-admission-bundle-producer",
    "ds15-mandate-intake-has-no-registered-task",
    "ds15-signed-v2-delegation-mandate-owner-authority",
    "ds15-production-n13b-execution-handshake",
    "ds15-numeric-voi-metric-residual-granularity",
    "education-importer-provenance-neither-inherited-nor-excluded",
    "ds15-fresh-positive-production-route",
    "ds15-semantic-epoch-qualification-authority",
)
CALLS = {
    "AcquisitionActionService",
    "AcquisitionAdmissionBundleProducer",
    "build_production_world_bank_wdi_execution_port",
    "execute_live_catalog_acquisition",
    "reenter_after_active_acquisition_overlay",
    "CycleBoardMovementGap",
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main() -> int:
    result: dict[str, object] = {
        "purpose": "commissioned-row reconciliation and bounded structural discovery",
        "head": git("rev-parse", "HEAD").decode().strip(),
        "counterexamples": [
            "A commissioned name occurs only as a cross-reference, not a first-cell row.",
            "A strict production port or movement consumer exists under another class name.",
            "A direct call uses a case variant or an untracked Python member.",
        ],
        "actual_reads": [],
        "unreadable": [],
        "unresolved_by_construction": [
            "AST name/attribute matching does not resolve aliases, receiver types or runtime dispatch.",
            "Source census excludes non-Python files, external packages and unexecuted runtime state.",
            "Register bytes identify commissioned rows, not evidence that their claims hold.",
        ],
    }
    reads: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    def read(path: Path) -> str | None:
        try:
            raw = path.read_bytes()
            text = raw.decode()
        except (OSError, UnicodeError) as exc:
            errors.append({"path": str(path), "error": repr(exc)})
            return None
        reads.append({"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest()})
        return text

    register = ROOT / "docs/plans/active/DEBT-REGISTER.md"
    body = read(register)
    admitted_rows: dict[str, list[int]] = {key: [] for key in ROWS}
    prefix_crosscheck: dict[str, list[int]] = {key: [] for key in ROWS}
    if body is not None:
        for lineno, line in enumerate(body.splitlines(), 1):
            if line.startswith("|"):
                cells = split_markdown_table_row(line)
                first = cells[0].strip().strip("`") if cells else ""
                if first in admitted_rows:
                    admitted_rows[first].append(lineno)
            for key in ROWS:
                if line.startswith(f"| `{key}` |"):
                    prefix_crosscheck[key].append(lineno)
    result["commissioned_rows"] = {
        "denominator": "exact IDs in commission; first cells of docs/plans/active/DEBT-REGISTER.md (.md)",
        "declared_total": 10,
        "observed_total": len(admitted_rows),
        "row_lines": admitted_rows,
        "independent_prefix_crosscheck": prefix_crosscheck,
    }
    scopes = ("src", "tools", "tests")
    indexed = {
        p for p in git("ls-files", "-z", "--", *scopes).decode().split("\0")
        if p.endswith(".py")
    }
    tree = {
        p for p in git("ls-tree", "-r", "--name-only", "HEAD", "--", *scopes).decode().splitlines()
        if p.endswith(".py")
    }
    filesystem = {
        str(p.relative_to(ROOT)) for scope in scopes for p in (ROOT / scope).rglob("*.py")
        if p.is_file()
    }
    result["python_denominator"] = {
        "paths": "policy-engine/{src,tools,tests}/**/*.py",
        "file_type": ".py",
        "index_total": len(indexed),
        "pinned_tree_total": len(tree),
        "filesystem_total": len(filesystem),
        "index_tree_symmetric_difference": sorted(indexed ^ tree),
        "index_filesystem_symmetric_difference": sorted(indexed ^ filesystem),
    }
    shapes: dict[str, list[dict[str, object]]] = {"execution_ports": [], "authority_providers": []}
    calls: list[dict[str, object]] = []
    case_variants: list[dict[str, object]] = []
    for rel in sorted(indexed | filesystem):
        text = read(ROOT / rel)
        if text is None:
            continue
        try:
            module = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            errors.append({"path": rel, "error": repr(exc)})
            continue
        for node in ast.walk(module):
            if isinstance(node, ast.ClassDef):
                methods = {
                    child.name for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if {"execute", "reenter", "resume_reentry"} <= methods:
                    shapes["execution_ports"].append({"path": rel, "line": node.lineno, "class": node.name})
                if {"for_request", "for_job"} <= methods:
                    shapes["authority_providers"].append({"path": rel, "line": node.lineno, "class": node.name})
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else ""
                )
                record = {"path": rel, "line": node.lineno, "name": name}
                if name in CALLS:
                    calls.append(record)
                elif name.casefold() in {term.casefold() for term in CALLS}:
                    case_variants.append(record)
    result.update(actual_reads=reads, unreadable=errors, class_shapes=shapes,
                  selected_direct_calls=calls, case_variant_direct_calls=case_variants)
    complete = (
        not errors and indexed == tree == filesystem and admitted_rows == prefix_crosscheck
        and all(len(locations) == 1 for locations in admitted_rows.values())
        and len(ROWS) == 10
    )
    result["status"] = "bounded_census_complete" if complete else "UNRUN_partial_coverage"
    print(json.dumps(result, indent=2))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
