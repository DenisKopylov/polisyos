"""Read exact Git blobs into a fresh, explicitly chosen import-census output root."""

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

HISTORICAL_CANDIDATE = "539ee6d6aad7f9db4c03dc520fc515dabef8d799"
HISTORICAL_SLICE_BASE = "6c80d1ac520e78a7b79d02402031c5a1673a6161"
NAMED_REFS = frozenset({"origin/main", "origin/codex/e02-integration"})


def _admit_sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("Git object identity must be a complete lowercase commit SHA")
    return value


def _admit_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Git object path must be a nonempty relative string")
    path = Path(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {".", ".."} for part in path.parts)
        or path.as_posix() != value
        or value.startswith("-")
        or ":" in value
        or any(character.isspace() or character == "\0" for character in value)
    ):
        raise ValueError("Git object path must be a canonical relative file path")
    return value


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(  # noqa: S603 - Fixed verbs; refs and paths admitted before callbacks.
        ["/usr/bin/git", *args], cwd=repo, stderr=subprocess.PIPE
    ).decode()


def _resolve(repo: Path, value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Git reference must be a supported named ref or complete SHA")
    if value not in NAMED_REFS:
        _admit_sha(value)
    return _admit_sha(
        _git(repo, "rev-parse", "--verify", "--end-of-options", value + "^{commit}").strip()
    )


def _imports(repo: Path, ref: str, path: str) -> tuple[list[dict], str | None]:
    _admit_sha(ref)
    _admit_path(path)
    try:
        source = _git(repo, "show", f"{ref}:{path}")
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
    return rows, _git(repo, "rev-parse", f"{ref}:{path}").strip()


def build(repo: Path, candidate: str, bases: list[tuple[str, str]]) -> list[tuple[str, dict]]:
    # Admit the complete chosen object set before resolving any one reference.
    _admit_sha(candidate)
    for _, value in bases:
        if not isinstance(value, str) or value not in NAMED_REFS:
            _admit_sha(value)
    candidate = _resolve(repo, candidate)
    resolved = [(label, _resolve(repo, base)) for label, base in bases]
    summaries = []
    for label, base in resolved:
        paths = _git(
            repo, "diff", "--name-only", "--diff-filter=AMCR", base, candidate
        ).splitlines()
        py_paths = [p for p in paths if p.endswith(".py")]
        for path in py_paths:
            _admit_path(path)
        records = []
        for path in py_paths:
            before, base_blob = _imports(repo, base, path)
            after, candidate_blob = _imports(repo, candidate, path)
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
        summaries.append(
            (
                label,
                {
                    "base_sha": base,
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
                },
            )
        )
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--candidate", default=HISTORICAL_CANDIDATE)
    args = parser.parse_args()
    if not args.repo_root.is_absolute() or not args.repo_root.is_dir():
        raise ValueError("supply an existing absolute repository root")
    if not args.output_root.is_absolute() or args.output_root.exists():
        raise ValueError("supply a fresh absolute output root")
    if args.output_root.resolve().is_relative_to(args.repo_root.resolve()):
        raise ValueError("keep import-census output outside the repository")
    summaries = build(
        args.repo_root,
        args.candidate,
        [
            ("main", "origin/main"),
            ("fetched-G", "origin/codex/e02-integration"),
            ("slice-base", HISTORICAL_SLICE_BASE),
        ],
    )
    args.output_root.mkdir(parents=True, exist_ok=False)
    for label, summary in summaries:
        (args.output_root / f"all-python-{label}.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
        sys.stdout.write(
            str(label) + " " + str({k: v for k, v in summary.items() if k != "records"}) + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
