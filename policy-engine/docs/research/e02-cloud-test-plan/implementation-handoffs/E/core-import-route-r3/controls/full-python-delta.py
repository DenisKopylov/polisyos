import ast
import json
import subprocess
import sys
from pathlib import Path

repo = Path("/workspace/e02-E-cal-review-20261006")
output = Path("/workspace/e02-E-pr38-r3-receipts/imports-r4")


def _git(*args: str) -> str:
    return subprocess.check_output(  # noqa: S603 - Fixed read-only Git calls.
        ["/usr/bin/git", *args], cwd=repo, stderr=subprocess.PIPE
    ).decode()


def _imports(ref: str, path: str) -> tuple[list[dict], str | None]:
    try:
        source = _git("show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return [], None
    tree = ast.parse(source, filename=f"{ref}:{path}")
    rows = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and not node.level
            and node.module
            and node.module.startswith("polisyos.")
        ):
            rows.append(
                {
                    "target": node.module,
                    "symbols": sorted(n.name for n in node.names),
                    "line": node.lineno,
                }
            )
        elif isinstance(node, ast.Import):
            rows.extend(
                {"target": n.name, "symbols": [], "line": node.lineno}
                for n in node.names
                if n.name.startswith("polisyos.")
            )
    return rows, _git("rev-parse", f"{ref}:{path}").strip()


for label, base in [
    ("main", "origin/main"),
    ("fetched-G", "origin/codex/e02-integration"),
    ("slice-base", "6c80d1ac520e78a7b79d02402031c5a1673a6161"),
]:
    candidate = "539ee6d6aad7f9db4c03dc520fc515dabef8d799"
    paths = _git("diff", "--name-only", "--diff-filter=AMCR", base, candidate).splitlines()
    py_paths = [p for p in paths if p.endswith(".py")]
    records = []
    for path in py_paths:
        before, base_blob = _imports(base, path)
        after, candidate_blob = _imports(candidate, path)
        old = {(r["target"], tuple(r["symbols"])) for r in before}
        added = [r for r in after if (r["target"], tuple(r["symbols"])) not in old]
        kind = (
            "production_source"
            if path.startswith("policy-engine/src/")
            else "mirrored_test"
            if path.startswith("policy-engine/tests/")
            else "companion"
        )
        records.append(
            {
                "path": path,
                "kind": kind,
                "base_blob": base_blob,
                "candidate_blob": candidate_blob,
                "added_absolute_polisyos_import_rows": added,
            }
        )
    summary = {
        "base_sha": _git("rev-parse", base).strip(),
        "candidate_sha": candidate,
        "full_changed_path_count": len(paths),
        "changed_python_count": len(py_paths),
        "source_python_count": sum(r["kind"] == "production_source" for r in records),
        "test_python_count": sum(r["kind"] == "mirrored_test" for r in records),
        "companion_python_count": sum(r["kind"] == "companion" for r in records),
        "added_absolute_polisyos_import_rows": sum(
            len(r["added_absolute_polisyos_import_rows"]) for r in records
        ),
        "scope": (
            "Every changed .py blob read and parsed at both Git refs; "
            "test/companion import rows are a separate denominator "
            "from cross-root product module edges"
        ),
        "records": records,
    }
    (output / f"all-python-{label}.json").write_text(json.dumps(summary, indent=2) + "\n")
    sys.stdout.write(
        str(label) + " " + str({k: v for k, v in summary.items() if k != "records"}) + "\n"
    )
