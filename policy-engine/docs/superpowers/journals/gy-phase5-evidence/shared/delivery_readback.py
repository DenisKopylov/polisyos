"""Read every committed delivery path back from the attached branch."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def git(*arguments: str) -> bytes:
    """Read local Git state without changing history or working files."""
    return subprocess.check_output(  # noqa: S603 — fixed local read operations.
        ["git", *arguments]  # noqa: S607 — configured local git executable.
    )


def main() -> None:
    """Prepare a staged-byte manifest, or verify its actual next commit."""
    mode, destination = sys.argv[1:]
    branch = git("symbolic-ref", "--short", "HEAD").decode().strip()
    if branch != "codex/gy-phase5-execution":
        raise ValueError("unexpected_branch_attachment")
    path = Path(destination)
    if mode == "prepare":
        names = [name.decode() for name in git(
            "diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z"
        ).split(b"\0") if name]
        removed = git("diff", "--cached", "--name-only", "--diff-filter=D", "-z")
        if not names or removed:
            raise ValueError("empty_or_unexpected_deleted_delivery")
        expected = {
            name: hashlib.sha256(git("show", ":" + name)).hexdigest()
            for name in sorted(names)
        }
        record = {
            "branch": branch,
            "parent": git("rev-parse", "HEAD").decode().strip(),
            "expected_staged_file_sha256": expected,
        }
        path.write_text(json.dumps(record, indent=2) + "\n")
    elif mode == "check":
        record = json.loads(path.read_text())
        commit = git("rev-parse", "HEAD").decode().strip()
        parent = git("rev-parse", "HEAD^").decode().strip()
        actual_names = {
            name.decode() for name in git(
                "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", commit
            ).split(b"\0") if name
        }
        actual = {
            name: hashlib.sha256(git("show", commit + ":" + name)).hexdigest()
            for name in sorted(actual_names)
        }
        expected = record["expected_staged_file_sha256"]
        result = {
            "branch": branch,
            "commit": commit,
            "parent": parent,
            "prepared_parent_matches": parent == record["parent"],
            "complete_commit_path_set_matches": actual_names == set(expected),
            "every_branch_blob_matches_prepared_staged_bytes": actual == expected,
            "branch_blob_sha256": actual,
            "expected_staged_file_sha256": expected,
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        if parent != record["parent"] or actual != expected:
            raise ValueError("delivered_branch_does_not_match_prepared_change")
    else:
        raise ValueError("unknown_delivery_action")


if __name__ == "__main__":
    main()
