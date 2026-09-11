"""Read-only pinned census and AST admission trace for Group A scope research."""

from __future__ import annotations

import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parents[6]
REF = "63bdb9640"
OUT = Path(__file__).resolve().parent


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted(node.value)}.{node.attr}"
    return ast.dump(node, include_attributes=False)


def main() -> None:
    tree = git("ls-tree", "-r", "--name-only", "-z", REF, "policy-engine")
    tree_paths = {p.decode() for p in tree.split(b"\0") if p}
    archive = git("archive", "--format=tar", REF, "policy-engine")
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        archive_paths = {m.name for m in tar.getmembers() if m.isfile() or m.issym()}
        sources = {
            m.name: tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.isfile() and m.name.endswith(".py")
        }
    if tree_paths != archive_paths:
        raise RuntimeError("Independent ls-tree/archive denominator disagreement")
    prefixes = ("policy-engine/", "policy-engine/src/polisyos/", "policy-engine/tests/")
    denominators = {
        prefix: {
            "file_type": "tracked .py blobs",
            "ls_tree_count": sum(p.startswith(prefix) and p.endswith(".py") for p in tree_paths),
            "archive_count": sum(p.startswith(prefix) and p.endswith(".py") for p in archive_paths),
        }
        for prefix in prefixes
    }
    targets = {
        "ScopePredicateEvidenceResolver", "ScopeAdjudicationRecord",
        "ScopeAdjudicationClaimLifecycleConsumer", "ScopeAdjudicationCandidate",
        "build_scope_adjudication_candidate", "verify_scope_adjudication_candidate",
        "test_four_way_ruling_is_produced_consumed_and_plane_specific",
    }
    definition_hits, call_hits, import_hits, errors, test_defs = [], [], [], [], []
    trace_files = {
        "scope_adjudication.py", "run_lifecycle.py", "container.py",
        "workspace_loop_transition.py", "lifecycle_bridge.py", "owner_events.py",
    }
    trace = []
    for path, source in sorted(sources.items()):
        try:
            parsed = ast.parse(source, filename=path)
        except SyntaxError as exc:
            errors.append({"path": path, "error": str(exc)})
            continue
        for node in ast.walk(parsed):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in targets:
                    definition_hits.append({"path": path, "line": node.lineno, "name": node.name})
                if path.endswith("tests/unit/core/contracts/test_scope_adjudication.py") and node.name.startswith("test_"):
                    test_defs.append({"path": path, "line": node.lineno, "name": node.name})
                if Path(path).name in trace_files or (path.endswith("head_index.py") and node.name in {"append_verified_owner_event", "_verify_closed_head", "build_default_claim_ledger_owner"}):
                    trace.append({"path": path, "line": node.lineno, "end_line": node.end_lineno,
                                  "definition": node.name, "kind": type(node).__name__,
                                  "calls": [{"line": n.lineno, "target": dotted(n.func)} for n in ast.walk(node) if isinstance(n, ast.Call)]})
            if isinstance(node, ast.Call) and dotted(node.func).split(".")[-1] in targets:
                call_hits.append({"path": path, "line": node.lineno, "target": dotted(node.func)})
            if isinstance(node, ast.ImportFrom) and ("scope_adjudication" in (node.module or "") or any(n.name in targets for n in node.names)):
                import_hits.append({"path": path, "line": node.lineno, "module": node.module,
                                    "names": [{"name": n.name, "asname": n.asname} for n in node.names]})
    raw_dir = OUT / "raw"
    raw_dir.mkdir(exist_ok=True)
    raw = json.dumps(trace, indent=2) + "\n"
    (raw_dir / "ast-trace.json").write_text(raw)
    receipt = {
        "source_ref": git("rev-parse", REF).decode().strip(),
        "branch_observed": git("symbolic-ref", "--short", "HEAD").decode().strip(),
        "denominator_methods": ["git ls-tree -r --name-only -z", "git archive --format=tar; TarFile.getmembers"],
        "denominators": denominators, "parse_errors": errors,
        "definition_hits": definition_hits, "direct_syntactic_call_hits": call_hits,
        "import_hits": import_hits, "scope_unit_test_definitions": test_defs,
        "trace_receipt": {"path": "raw/ast-trace.json", "sha256": hashlib.sha256(raw.encode()).hexdigest()},
        "limitations": "AST direct syntax and import spellings; not reflective call-graph proof or dynamic execution; archive and ls-tree independently enumerate the same pinned git object, not independent source truth.",
    }
    (OUT / "census-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
