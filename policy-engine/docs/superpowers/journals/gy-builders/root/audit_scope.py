"""Recompute the complete base-source byte denominator and protected write boundaries."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE = "07c89304d"


def git(*arguments: str) -> bytes:
    """Read ordinary local git state with no mutation or remote operation."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git_unavailable")
    # All arguments are literal read-only operations defined in this harness.
    return subprocess.check_output([executable, *arguments])  # noqa: S603


def main() -> None:
    """Compare every base src member independently with git's changed-path set."""
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    branch = git("symbolic-ref", "--short", "HEAD").decode().strip()
    if branch != "codex/gy-builders":
        raise ValueError("unexpected_branch_attachment")
    rows = git("ls-tree", "-rz", BASE, "--", "src/").split(b"\0")
    # ls-tree paths are relative to the current policy-engine directory.
    source: dict[str, str] = {}
    for row in filter(None, rows):
        metadata, path = row.split(b"\t", 1)
        _, kind, identity = metadata.split()
        if kind != b"blob":
            raise ValueError("ambiguous_source_member")
        source[path.decode()] = identity.decode()
    if not source:
        raise ValueError("empty_source_denominator")
    modified = set()
    for path, identity in source.items():
        payload = Path(path).read_bytes()
        actual = hashlib.sha1(
            b"blob " + str(len(payload)).encode() + b"\0" + payload, usedforsecurity=False
        ).hexdigest()
        if actual != identity:
            modified.add(path)
    git_modified = {
        path.removeprefix("policy-engine/")
        for path in git("diff", "--name-only", "--diff-filter=MD", BASE, "--", "src/")
        .decode().splitlines()
    }
    if modified != git_modified:
        raise ValueError("source_change_census_disagreement")
    if any(path.endswith(".py") for path in modified):
        raise ValueError("existing_python_owner_changed")
    protected = (
        "docs/plans/active/DEBT-REGISTER.md",
        "docs/plans/active/LEDGER.md",
    )
    for path in protected:
        if Path(path).read_bytes() != git("show", f"{BASE}:policy-engine/{path}"):
            raise ValueError(f"protected_file_changed:{path}")
    governed = git("diff", "--name-only", BASE, "--", "architecture/").decode().splitlines()
    if governed:
        raise ValueError("unexpected_governed_artifact_change")
    sys.stdout.write(json.dumps({
        "branch": branch,
        "base": git("rev-parse", BASE).decode().strip(),
        "source_denominator": "policy-engine/src/** base tracked blobs",
        "base_source_files": len(source),
        "base_python_files": sum(path.endswith(".py") for path in source),
        "changed_base_members": sorted(modified),
        "changed_base_python_members": [],
        "independent_byte_and_git_diff_comparison": "equal",
        "protected_debt_ledger_bytes": "unchanged",
        "changed_governed_artifacts": governed,
        "epoch_freshness": "not_claimed",
        "root": str(root),
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
