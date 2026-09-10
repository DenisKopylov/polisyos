"""Recompute the actual D1 defaults and complete remaining predecessor callers."""
from __future__ import annotations

import ast
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import tokenize

BASE = "504f995cd203f2efebee8566363b8987092e1e34"
TERMINALS = {"produce_from_catalog", "produce_from_fabric_fetch"}


def main() -> None:
    calls = importlib.import_module("tests.repo_quality.tools.test_gy_d1_catalog_wiring")
    sites, constructor_census = calls.constructor_census()
    roots = ["src", "tools", "tests"]
    paths = {p for p in subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *roots]
    ).decode().split("\0") if p.endswith(".py") and Path(p).is_file()}
    independent = {p for p in subprocess.check_output(
        ["rg", "--files", "--hidden", *roots]).decode().splitlines() if p.endswith(".py")}
    assert paths == independent, (sorted(paths-independent), sorted(independent-paths))
    ast_ids, token_ids, rows, snapshots, unreadables = set(), set(), [], {}, []
    for path in sorted(paths):
        try:
            raw = Path(path).read_bytes()
            source = raw.decode("utf-8")
            tree = ast.parse(source, filename=path)
            snapshots[path] = hashlib.sha256(raw).hexdigest()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = ast.unparse(node.func)
                if name.rsplit(".", 1)[-1] not in TERMINALS:
                    continue
                ast_ids.add((path, node.func.end_lineno, node.func.end_col_offset))
                rows.append({"path": path, "line": node.lineno, "call": name})
            tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline)
                      if t.type not in {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                                        tokenize.INDENT, tokenize.DEDENT}]
            for index, token in enumerate(tokens[:-1]):
                if (token.type == tokenize.NAME and token.string in TERMINALS
                        and tokens[index+1].string == "("
                        and (not index or tokens[index-1].string not in {"def", "class"})):
                    token_ids.add((path, *token.end))
        except (OSError, UnicodeError, SyntaxError) as exc:
            unreadables.append({"path": path, "status": "ambiguous", "error": repr(exc)})
    changed = [p for p, digest in snapshots.items()
               if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
    assert not unreadables and not changed and ast_ids == token_ids
    nl_path = "src/polisyos/runtime/http/services/control/nl_pipeline.py"
    nl = ast.parse(Path(nl_path).read_text())
    persist_calls = [node for node in ast.walk(nl) if isinstance(node, ast.Call)
                    and any(isinstance(arg, ast.Attribute) and arg.attr == "execute_fetch_plans"
                            for arg in node.args)]
    assert persist_calls and all(any(k.arg == "persist_payload" and isinstance(k.value, ast.Constant)
                                    and k.value.value is True for k in node.keywords)
                                for node in persist_calls)
    paths_changed = ["src/polisyos/fabric/retrieval/executor.py", nl_path]
    numstat = subprocess.check_output(["git", "diff", "--numstat", BASE, "--", *paths_changed], text=True)
    removed_numstat = sum(int(line.split("\t")[1]) for line in numstat.splitlines())
    patch = subprocess.check_output(["git", "diff", "--no-ext-diff", "--unified=0", BASE,
                                     "--", *paths_changed], text=True)
    removed_patch = sum(line.startswith("-") and not line.startswith("---") for line in patch.splitlines())
    assert removed_numstat == removed_patch and removed_patch > 0
    assert "_ = self._cas_root" not in Path(paths_changed[0]).read_text()
    production = [r for r in rows if r["path"].startswith("src/")]
    print(json.dumps({
        "receipt_id": "layer3-gy-d1-fabric-measurement-strangle",
        "predecessor_ref": "src/polisyos/runtime/quality/promotion_sequence.py@" + BASE,
        "replacement_ref": "src/polisyos/runtime/quality/promotion_sequence.py",
        "disposition": "fenced_default_flipped",
        "default_before": "catalog-only root could discharge current N9 MEASUREMENT; NL fetch persistence disabled",
        "default_after": "current N9 resolves full Fabric custody and source contract; actual NL fetch persists",
        "guard_ref": "tests/repo_quality/tools/test_gy_d1_catalog_wiring.py",
        "constructor_census": constructor_census,
        "constructor_identities": sorted(site.identity for site in sites),
        "predecessor_replacement_census": {
            "denominator": {"roots": roots, "type": "all current .py", "git": len(paths), "rg": len(independent)},
            "identities": {"ast": len(ast_ids), "tokenize": len(token_ids), "only_ast": sorted(ast_ids-token_ids),
                           "only_tokenize": sorted(token_ids-ast_ids)},
            "unreadables": unreadables, "changed_during_census": changed,
            "calls": sorted(rows, key=lambda r: (r["path"], r["line"]))},
        "remaining_production_callers": production,
        "remaining_callers_disposition": "Existing WorkspaceLoop Slice-0/catalog roots remain for their existing scope and are refused by current N9; no claim that whole production NL-to-promotion orchestration is complete.",
        "remaining_caller_route": "GY-PR1 measurement producer orchestration; architect-owned follow-up, no repair to closed Slice-0 tasks",
        "removed_loc": {"paths": paths_changed, "git_numstat": removed_numstat, "patch_lines": removed_patch},
        "verified_by": ["n9/catalog-only-red.json", "n9/final-focused.json",
                        "n9/final-corrected-controls.json",
                        "callers/final-baseline-complete.json"],
        "constructor_and_persistence_removal_evidence": "The complete caller gate executes each actual AST catalog-None and NL persist=False variant; its output records each actual N9 MEASUREMENT refusal alongside the positive, with plan markers unchanged. Test exit zero asserts these intended consumer refusals; it does not label the missing property satisfied.",
        "limitation": "Static receipt establishes defaults and complete lexical method callers. Actual constructor, source, contract and persistence removals provide the semantic proof; external L1 binding disagreement keeps D1 blocked.",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
