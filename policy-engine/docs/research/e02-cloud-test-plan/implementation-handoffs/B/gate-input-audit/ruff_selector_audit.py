"""Measure Ruff selectors and retained diagnostics without running a lint gate.

The Git census is source-bound. ``--show-files`` observes the supplied live
checkout, so its bytes are separately reconciled with that Git snapshot.
No diagnostic verdict, inherited-red attribution, or policy exemption follows.
"""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import re
import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> bytes:
    """Read Git metadata using the fixed Git executable and argument vector."""
    # This reader accepts repository paths/refs, never shell command text.
    return subprocess.check_output(["/usr/bin/git", *args], cwd=root)  # noqa: S603


def digest(data: bytes) -> str:
    """Return the content identity of an observed artifact."""
    return hashlib.sha256(data).hexdigest()


def artifact(path: Path) -> dict[str, object]:
    """Describe exact retained bytes without duplicating their content."""
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": digest(data)}


def categories(paths: set[str]) -> dict[str, int]:
    """Count the complete supplied Git-relative set by product directory."""
    return dict(sorted(collections.Counter(p.split("/")[1] for p in paths).items()))


def main() -> None:
    """Emit bounded selector facts; do not execute Ruff diagnostics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--published-predecessor", required=True)
    parser.add_argument("--observed-source", required=True)
    parser.add_argument("--observed-log", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    root: Path = args.root.absolute()
    source: str = args.source
    scratch: Path = args.scratch.absolute()
    scratch.mkdir(parents=True, exist_ok=True)
    if git(root, "rev-parse", "HEAD").decode().strip() != source:
        raise SystemExit("Live HEAD differs from supplied source; no selector observation.")

    blobs: dict[str, str] = {}
    for row in git(root, "ls-tree", "-rz", source).decode().split("\0"):
        if row:
            metadata, path = row.split("\t", 1)
            blobs[path] = metadata.split()[2]
    tracked = set(blobs)
    python_paths = {p for p in tracked if p.endswith((".py", ".pyi"))}
    owner = "policy-engine/tools/devx/workspace/_repo_hygiene.py"
    constants: dict[str, tuple[str, ...]] = {}
    for node in ast.parse(git(root, "show", source + ":" + owner)).body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Tuple)
        ):
            constants[node.target.id] = ast.literal_eval(node.value)
    excludes = constants["PHASE8_LIMITED_PYTHON_SCOPE"]
    scope = tuple(p for p in constants["AUTHORED_PYTHON_FORMAT_SCOPE"] if p not in excludes)
    argv = [str(args.python.absolute()), "-m", "ruff", "check", "--no-cache", "--show-files"]
    for path in excludes:
        argv.extend(("--extend-exclude", path))
    argv.extend(scope)
    # argv is a supplied Python locator plus fixed Ruff metadata-only operation.
    shown = subprocess.run(  # noqa: S603
        argv, cwd=root / "policy-engine", capture_output=True, check=False
    )
    stdout = scratch / "lint-fast-show-files.stdout.txt"
    stderr = scratch / "lint-fast-show-files.stderr.txt"
    stdout.write_bytes(shown.stdout)
    stderr.write_bytes(shown.stderr)
    actual = {str(Path(p).relative_to(root)) for p in shown.stdout.decode().splitlines()}
    unmatched = sorted(actual - tracked)
    drift = []
    for path in sorted(actual & tracked):
        data = (root / path).read_bytes()
        # Git object identity is compared, never used as a semantic lint verdict.
        actual_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()  # noqa: S324
        if actual_blob != blobs[path]:
            drift.append(path)
    if (
        shown.returncode
        or unmatched
        or drift
        or git(root, "rev-parse", "HEAD").decode().strip() != source
    ):
        raise SystemExit("Selector discovery/source reconciliation failed; no complete count.")

    changes: dict[str, object] = {}
    for label, base, ref, separator in (
        ("observed_adjacent_snapshot", args.base, args.observed_source, ".."),
        ("current_fresh_base", args.base, source, ".."),
        ("published_closeout_command", args.published_predecessor, source, "..."),
    ):
        # Preserve the literal closeout selector: no deletion filter is invented.
        paths = {
            p
            for p in git(root, "diff", "--name-only", base + separator + ref).decode().splitlines()
            if p.startswith("policy-engine/") and p.endswith(".py")
        }
        changes[label] = {
            "base": base,
            "source": ref,
            "separator": separator,
            "paths": len(paths),
            "categories": categories(paths),
            "actual_current_lint_selector_overlap": len(paths & actual),
            "missing_in_live_checkout": sorted(p for p in paths if not (root / p).exists()),
        }
    log = args.observed_log.read_text()
    diagnostics = re.findall(
        r"^([A-Z]+\d{3}) (?:\[\*\] )?[^\n]*\n"
        r"(?:(?!^[A-Z]+\d{3} ).*\n)*?\s+--> ([^\n]+?):\d+:\d+\n",
        log,
        re.MULTILINE,
    )
    stated = re.search(r"^Found (\d+) errors\.$", log, re.MULTILINE)
    if stated is None or int(stated.group(1)) != len(diagnostics):
        raise SystemExit("Retained diagnostic census does not reconcile with full Ruff output.")
    diagnostic_paths = {p for _, p in diagnostics}
    inputs = [
        "AGENTS.md",
        "policy-engine/CONTRIBUTING.md",
        owner,
        "policy-engine/docs/reference/quality-gates.md",
        "policy-engine/docs/reference/repository-hygiene.md",
        "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/verification-and-closeout.md",
        "policy-engine/tools/devx/workspace/lint_fast.py",
        "policy-engine/tools/devx/workspace/lint_full.py",
        "policy-engine/tools/devx/workspace/benchmark_surfaces.py",
        "policy-engine/tools/devx/workspace/runtime_surface.py",
        "policy-engine/tools/devx/workspace/verify.py",
        "policy-engine/tools/devx/workspace/ci_parity.py",
        "policy-engine/.pre-commit-config.yaml",
        "policy-engine/ruff.toml",
        "policy-engine/architecture/tooling/ruff/generated.toml",
        "policy-engine/architecture/tooling/tool_config_split.toml",
        ".gitignore",
        "policy-engine/.gitignore",
    ]
    result = {
        "purpose": "selector_and_diagnostic_census_only",
        "source": source,
        "tree": git(root, "rev-parse", source + "^{tree}").decode().strip(),
        "tracked_py_pyi": len(python_paths),
        "changed_profiles": changes,
        "lint_fast_scope": scope,
        "existing_extend_excludes": excludes,
        "discovery": {
            "argv": argv,
            "cwd": str(root / "policy-engine"),
            "exit": shown.returncode,
            "stdout": artifact(stdout),
            "stderr": artifact(stderr),
        },
        "actual_inputs": {
            "count": len(actual),
            "categories": categories(actual),
            "suffixes": dict(sorted(collections.Counter(Path(p).suffix for p in actual).items())),
            "all_tracked_bytes_reconciled": True,
            "docs_paths": sum(p.startswith("policy-engine/docs/") for p in actual),
            "explicit_missing_operands": [
                p for p in scope if not (root / "policy-engine" / p).exists()
            ],
        },
        "retained_failure": {
            "artifact": artifact(args.observed_log),
            "diagnostics": len(diagnostics),
            "diagnostic_files": len(diagnostic_paths),
            "files_by_category": categories(diagnostic_paths),
            "diagnostics_by_category": dict(
                sorted(collections.Counter(p.split("/")[1] for _, p in diagnostics).items())
            ),
            "non_docs": [
                [code, path]
                for code, path in diagnostics
                if not path.startswith("policy-engine/docs/")
            ],
        },
        "source_inputs": [
            {"path": p, "source": source, "sha256": digest(git(root, "show", source + ":" + p))}
            for p in inputs
        ],
        "limitations": [
            "No lint diagnostic gate executed.",
            "Observed historical log lacks before/after source and argv capture.",
            "No inherited-red/disjoint attribution or policy exemption.",
            "Live filesystem and Git ignore policy observed only on this source snapshot.",
        ],
    }
    print(json.dumps(result, indent=2))  # noqa: T201 -- measurement CLI output


if __name__ == "__main__":
    main()
