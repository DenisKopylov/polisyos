"""Read-only survey instrument. AST occurrence evidence is not reachability proof.

Use from policy-engine. Every output names its complete file denominator. No
register/ledger text is admitted into the evidence corpus. Cache is local raw
measurement material; source is re-bound to the pinned base before reuse.
"""

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import pickle
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
BASE = "fc823071a7b6f2c9a573172aec3499ad6d138c0f"
RAW = Path(__file__).resolve().parent / "raw"
PREFIXES = ("src/", "tests/", "tools/", "architecture/")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def tracked():
    return sorted(git("ls-tree", "-r", "--name-only", BASE, "--", ".").splitlines())


def source_paths():
    paths = [p for p in tracked() if p.endswith(".py") and p.startswith(PREFIXES)]
    walked = sorted(str(Path(directory, name).relative_to(ROOT))
                    for prefix in PREFIXES
                    for directory, _, names in os.walk(ROOT / prefix)
                    for name in names if name.endswith(".py"))
    if paths != walked:
        raise RuntimeError(json.dumps({"tree_only": sorted(set(paths)-set(walked)),
                                       "filesystem_only": sorted(set(walked)-set(paths))}))
    return paths


def ast_inventory():
    RAW.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "diff", "--exit-code", BASE, "--", *PREFIXES],
                   cwd=ROOT, check=True, stdout=subprocess.PIPE)
    paths = source_paths()
    identity = hashlib.sha256("\n".join(paths).encode()).hexdigest()
    cache = RAW / "ast-cache.pickle"
    if cache.exists():
        inventory = pickle.loads(cache.read_bytes())
        if inventory["base"] == BASE and inventory["path_sha256"] == identity:
            return inventory
    result = []
    failures = []
    for path in paths:
        try:
            tree = ast.parse((ROOT/path).read_text(), filename=path)
        except Exception as error:
            failures.append({"path": path, "error": str(error)})
            continue
        visitor_nodes = []
        class Walk(ast.NodeVisitor):
            def generic_visit(self, node):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Call)):
                    visitor_nodes.append((type(node).__name__, node.lineno, node.col_offset))
                super().generic_visit(node)
        Walk().visit(tree)
        standard_nodes = [(type(n).__name__, n.lineno, n.col_offset) for n in ast.walk(tree)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Call))]
        assert sorted(standard_nodes) == sorted(visitor_nodes), path
        parents = {child: n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Call,
                                     ast.Import, ast.ImportFrom, ast.AnnAssign)):
                continue
            name = node.name if hasattr(node, "name") else ast.unparse(node.func) if isinstance(node, ast.Call) else ast.unparse(node)
            parent = parents.get(node)
            while parent is not None and not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                parent = parents.get(parent)
            result.append({"path": path, "line": node.lineno, "end": node.end_lineno,
                           "kind": type(node).__name__, "name": name,
                           "enclosing": getattr(parent, "name", None)})
    inventory = {"base": BASE, "path_sha256": identity, "paths": paths,
                 "ambiguities": failures, "records": result,
                 "ast_walk_and_visitor_identity_equal": True}
    cache.write_bytes(pickle.dumps(inventory))
    (RAW/"python-denominator.json").write_text(json.dumps(
        {k:v for k,v in inventory.items() if k!="records"}, indent=2)+"\n")
    return inventory


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["ast", "body", "text", "docs", "json", "denominator"])
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--path")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if args.mode in {"ast", "body", "denominator"}:
        inventory = ast_inventory()
        paths = [p for p in inventory["paths"] if not args.source_only or p.startswith("src/")]
        path_set = set(paths)
        records = [x for x in inventory["records"] if x["path"] in path_set]
        selected = [x for x in records if re.search(args.query, x["name"])
                    and (not args.path or x["path"] == args.path)]
        if args.mode == "body":
            selected = [x | {"body": "\n".join((ROOT/x["path"]).read_text().splitlines()[x["line"]-1:x["end"]])}
                        for x in selected if x["kind"] in {"FunctionDef", "AsyncFunctionDef", "ClassDef"}]
        if args.mode == "denominator":
            selected = []
        emit({"base": BASE, "file_type": ".py", "prefixes": ["src/"] if args.source_only else PREFIXES,
              "file_count": len(paths), "path_sha256": hashlib.sha256("\n".join(paths).encode()).hexdigest(),
              "full_python_denominator_sha256": inventory["path_sha256"],
              "path_enumeration": "git ls-tree equals independent os.walk",
              "node_enumeration": "ast.walk equals independent NodeVisitor, sync+async",
              "ambiguities": inventory["ambiguities"],
              "definition_distribution": dict(sorted(Counter(x["path"].split('/')[2] if x["path"].startswith('src/') else x['path'].split('/')[0]
                    for x in records if x["kind"] in {"FunctionDef", "AsyncFunctionDef", "ClassDef"}).items())),
              "query": args.query, "matches": selected})
    elif args.mode == "json":
        path = Path(args.query)
        emit({"evidence": f"{path}@{BASE}", "value": json.loads((ROOT/path).read_text())})
    else:
        paths = tracked()
        if args.mode == "docs":
            paths = [p for p in paths if p.startswith(("docs/plans/active/", "docs/reference/", "docs/research/", "docs/system-design-decisions/"))
                     and p.endswith((".md", ".json", ".yaml", ".yml"))
                     and not p.endswith(("/DEBT-REGISTER.md", "/LEDGER.md"))]
        else:
            paths = [p for p in paths if p.startswith(PREFIXES) and p.endswith((".py", ".json", ".toml", ".md", ".yaml", ".yml"))]
        if args.path:
            paths = [args.path]
        if args.path:
            independent = [args.path] if args.path in git("ls-files", "--", args.path).splitlines() else []
        else:
            roots = ("docs/plans/active/", "docs/reference/", "docs/research/", "docs/system-design-decisions/") if args.mode == "docs" else PREFIXES
            extensions = (".md", ".json", ".yaml", ".yml") if args.mode == "docs" else (".py", ".json", ".toml", ".md", ".yaml", ".yml")
            independent = sorted(str(Path(directory, name).relative_to(ROOT))
                for prefix in roots for directory, _, names in os.walk(ROOT/prefix)
                for name in names if name.endswith(extensions)
                and not (args.mode == "docs" and name in {"DEBT-REGISTER.md", "LEDGER.md"}))
        if independent != sorted(paths):
            raise RuntimeError(json.dumps({"tree_only":sorted(set(paths)-set(independent)),
                                           "filesystem_only":sorted(set(independent)-set(paths))}))
        matches, unreadable = [], []
        for path in paths:
            try:
                for n, line in enumerate((ROOT/path).read_text().splitlines(), 1):
                    if re.search(args.query, line, re.I):
                        matches.append({"path":path,"line":n,"text":line})
            except Exception as error:
                unreadable.append({"path":path,"error":str(error)})
        emit({"base":BASE,"path_count":len(paths),"enumerated_paths":paths,
              "denominator":"complete pinned Git tree filtered by declared prefixes/extensions",
              "independent_filesystem_identity_equal":True,
              "unreadable":unreadable,"query":args.query,
              "distribution":dict(sorted(Counter(x['path'] for x in matches).items())),"matches":matches})


if __name__ == "__main__":
    main()
