"""Read-only Git selector/config census and locator/Trash availability snapshot.

This does not collect tests, run gates, discover dynamic imports, inspect private
data, or remove any file. The complete tracked set comes from one Git census;
declared historical selectors are compared with that set, without treating them
as an actual pytest collection. Filesystem locator facts describe observation
time rather than the committed Git tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
CONFIG = "933a0ef4f548eaa7e3c0f1c6324a0d4fe4729022"
CONFIG_PATHS = (
    "AGENTS.md",
    "policy-engine/CONTRIBUTING.md",
    "policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md",
    "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/verification-and-closeout.md",
    "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/method-decisions.md",
    "policy-engine/tools/devx/workspace/verify.py",
    "policy-engine/tools/devx/workspace/ci_parity.py",
    "policy-engine/tools/devx/workspace/_common.py",
    "policy-engine/tools/devx/architecture/guardrails.py",
    "policy-engine/tools/ops_runners/runtime/check_runtime_api_contract.py",
    "policy-engine/pytest.ini",
    "policy-engine/pyproject.toml",
    "policy-engine/uv.lock",
    "policy-engine/docs/reference/quality-gates.md",
    "policy-engine/docs/reference/merge-governance.md",
)


def git(root: Path, *args: str) -> bytes:
    # Read-only local Git metadata, with no checkout or mutation subcommand.
    return subprocess.check_output(["/usr/bin/git", *args], cwd=root)  # noqa: S603


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def locator(path: Path) -> dict[str, object]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"path": str(path), "kind": "missing"}
    kind = (
        "symlink"
        if stat.S_ISLNK(info.st_mode)
        else "directory"
        if stat.S_ISDIR(info.st_mode)
        else "regular"
        if stat.S_ISREG(info.st_mode)
        else "special"
    )
    result: dict[str, object] = {"path": str(path), "kind": kind}
    if kind == "symlink":
        result["symlink_target"] = os.readlink(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.absolute()
    product = root / "policy-engine"
    head = git(root, "rev-parse", "HEAD").decode().strip()
    tracked = set(git(root, "ls-tree", "-r", "--name-only", "-z", head).decode().split("\0"))
    tracked.discard("")
    changed = set(git(root, "diff", "--name-only", "-z", BASE + "..." + head).decode().split("\0"))
    changed.discard("")
    coverage_path = (
        "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"
    )
    coverage_raw = git(root, "show", head + ":" + coverage_path)
    coverage = json.loads(coverage_raw)
    selectors = {path for bundle in coverage["bundles"] for path in bundle["test_paths"]}
    source_bindings = []
    for path in CONFIG_PATHS:
        raw = git(root, "show", CONFIG + ":" + path)
        source_bindings.append({"path": path, "source_sha": CONFIG, "sha256": sha256(raw)})
    root_locators = (
        product / ".venv",
        product / ".mypy_cache",
        product / "_build",
        product / "_cache/ruff",
        product / "_cache/pytest",
        product / "_cache/benchmarks",
        product / "_cache/hypothesis",
        product / "node_modules",
        product / "apps/runtime-dashboard/node_modules",
        root / ".polisyos/e02-B-current/raw",
        root / ".polisyos/e02-B-current/tools",
    )
    trash_dirs = (
        Path.home() / ".local/share/Trash",
        Path.home() / ".Trash",
        Path("/workspace/.Trash"),
    )
    scopes = (
        "policy-engine/src/",
        "policy-engine/tests/",
        "policy-engine/tools/",
        "policy-engine/docs/",
    )
    output = {
        "schema": "policyos.e02.gate_input_observation.v1",
        "observation_utc": datetime.now(UTC).isoformat(),
        "root": str(root),
        "source_sha": head,
        "tree_sha": git(root, "rev-parse", head + "^{tree}").decode().strip(),
        "slice_base_sha": BASE,
        "config_source_bindings": source_bindings,
        "tracked_file_denominator": {
            "total": len(tracked),
            "suffix_counts": dict(
                sorted(Counter(Path(path).suffix or "<none>" for path in tracked).items())
            ),
            "changed_total": len(changed),
            "changed_by_declared_scope": {
                scope: sum(path.startswith(scope) for path in changed) for scope in scopes
            },
            "changed_python_paths": sum(
                path.startswith("policy-engine/") and path.endswith(".py") for path in changed
            ),
            "qualification": (
                "complete Git tree/change census; not a complete dynamic gate read set"
            ),
        },
        "historical_declared_selector_census": {
            "input": coverage_path + "@" + head,
            "input_sha256": sha256(coverage_raw),
            "declared_unique_paths": len(selectors),
            "tracked_present": len(selectors & tracked),
            "missing_paths": sorted(selectors - tracked),
            "qualification": (
                "historical global map, not current B-only collection or criterion closure"
            ),
        },
        "native_trash_availability": {
            "commands": {
                name: shutil.which(name)
                for name in ("trash", "trash-put", "gio", "kioclient5", "kioclient", "osascript")
            },
            "directories": [locator(path) for path in trash_dirs],
            "qualification": (
                "bounded executable/standard-path census; "
                "no alternate API or platform fallback established"
            ),
        },
        "root_locator_observations": [locator(path) for path in root_locators],
        "execution": {
            "gates_run": [],
            "tests_collected": False,
            "deletions": [],
            "new_worktrees": [],
        },
    }
    if git(root, "rev-parse", "HEAD").decode().strip() != head:
        raise RuntimeError(
            "root HEAD changed during read-only census; retain no mixed-head snapshot"
        )
    sys.stdout.write(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
