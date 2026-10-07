"""Recompute portable review copy identities; deliberately corrupt one hash."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def validate(root: Path, records: list[dict], revision: str = "HEAD") -> None:
    for record in records:
        relative = Path(record["copied_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Review copy must be repository relative")
        payload = (root / relative).read_bytes()
        if len(payload) != record["bytes"]:
            raise ValueError(f"Review size mismatch: {relative}")
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError(f"Review digest mismatch: {relative}")
        stored = subprocess.run(  # noqa: S603 -- read-only Git argv, never a shell
            [shutil.which("git") or "/usr/bin/git", "show", f"{revision}:{relative.as_posix()}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if stored.returncode or stored.stdout != payload:
            raise ValueError(f"Review copy unavailable or different in Git: {relative}")


def main() -> None:
    here = Path(__file__).resolve()
    root = next(parent for parent in here.parents if (parent / "AGENTS.md").is_file())
    records = json.loads((here.parent / "independent-reviews/copy-index.json").read_text())[
        "records"
    ]
    revision = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    validate(root, records, revision)
    negatives = {}
    for field, value in (("sha256", "0" * 64), ("bytes", -1)):
        corrupted = [dict(record) for record in records]
        corrupted[0][field] = value
        try:
            validate(root, corrupted, revision)
        except ValueError:
            negatives[field] = "rejected"
        else:
            raise AssertionError("Markers must not replace content validation")
    try:
        validate(root, records, "198076863e143dea9f89f02734b13d50dae3eed5")
    except ValueError:
        negatives["unpublished_git_copy"] = "rejected"
    else:
        raise AssertionError("Local bytes alone must not establish Git publication")
    sys.stdout.write(
        json.dumps(
            {
                "copies": len(records),
                "recomputed": "PASS",
                "git_revision": revision,
                "corrupt_controls": negatives,
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
