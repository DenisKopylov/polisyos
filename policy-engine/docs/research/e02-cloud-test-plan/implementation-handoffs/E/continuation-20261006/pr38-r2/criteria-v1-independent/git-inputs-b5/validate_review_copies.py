"""Verify current review copies or explicitly replay immutable historical Git bytes."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _git_bytes(root: Path, arguments: list[str]) -> bytes:
    executable = shutil.which("git")
    if executable is None:
        raise ValueError("Git executable unavailable")
    completed = subprocess.run(  # noqa: S603 - fixed read-only Git argv; never a shell
        [str(Path(executable).resolve()), *arguments],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError("Review revision or copy is unavailable in Git")
    return completed.stdout


def _revision(root: Path, revision: str, *, historical: bool) -> str:
    if (
        not revision
        or revision.startswith("-")
        or any(character.isspace() or character == "\0" for character in revision)
    ):
        raise ValueError("Review revision must be a Git revision, never an option")
    if historical and re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("Historical replay requires an exact immutable commit SHA")
    resolved = (
        _git_bytes(root, ["rev-parse", "--verify", "--end-of-options", revision + "^{commit}"])
        .decode()
        .strip()
    )
    if re.fullmatch(r"[0-9a-f]{40}", resolved) is None:
        raise ValueError("Review revision did not resolve to one immutable commit")
    return resolved


def validate(
    root: Path,
    records: list[dict[str, object]],
    revision: str = "HEAD",
    *,
    historical: bool = False,
) -> None:
    """Bind hash and size to Git, requiring live equality unless replay is explicit.

    Historical mode makes no claim about the current working copies. It exists so
    utility corrections preserve the original publication's immutable evidence.
    """
    for record in records:
        copied_path = record.get("copied_path")
        declared_size = record.get("bytes")
        declared_digest = record.get("sha256")
        if not isinstance(copied_path, str):
            raise ValueError("Review copy path must be a string")
        relative = Path(copied_path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or copied_path.startswith("-")
            or ":" in copied_path
            or any(character.isspace() or character == "\0" for character in copied_path)
        ):
            raise ValueError("Review copy must be repository relative")
        if type(declared_size) is not int or declared_size < 0:
            raise ValueError(f"Review size declaration invalid: {relative}")
        if (
            not isinstance(declared_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", declared_digest) is None
        ):
            raise ValueError(f"Review digest declaration invalid: {relative}")
    resolved = _revision(root, revision, historical=historical)
    for record in records:
        relative = Path(record["copied_path"])
        declared_size = record["bytes"]
        declared_digest = record["sha256"]
        stored = _git_bytes(root, ["show", f"{resolved}:{relative.as_posix()}"])
        if len(stored) != declared_size:
            raise ValueError(f"Review size mismatch: {relative}")
        if hashlib.sha256(stored).hexdigest() != declared_digest:
            raise ValueError(f"Review digest mismatch: {relative}")
        if not historical and (root / relative).read_bytes() != stored:
            raise ValueError(f"Review current copy differs from pinned Git: {relative}")


def main() -> None:
    here = Path(__file__).resolve()
    root = next(parent for parent in here.parents if (parent / "AGENTS.md").is_file())
    records = json.loads((here.parent / "independent-reviews/copy-index.json").read_text())[
        "records"
    ]
    arguments = sys.argv[1:]
    historical = "--historical" in arguments
    revisions = [argument for argument in arguments if argument != "--historical"]
    if len(revisions) > 1:
        raise ValueError("Provide one review revision")
    revision = revisions[0] if revisions else "HEAD"
    validate(root, records, revision, historical=historical)
    negatives = {}
    for field, value in (("sha256", "0" * 64), ("bytes", -1)):
        corrupted = [dict(record) for record in records]
        corrupted[0][field] = value
        try:
            validate(root, corrupted, revision, historical=historical)
        except ValueError:
            negatives[field] = "rejected"
        else:
            raise AssertionError("Markers must not replace content validation")
    try:
        validate(
            root,
            records,
            "198076863e143dea9f89f02734b13d50dae3eed5",
            historical=historical,
        )
    except ValueError:
        negatives["unpublished_git_copy"] = "rejected"
    else:
        raise AssertionError("Local bytes alone must not establish Git publication")
    sys.stdout.write(
        json.dumps(
            {
                "copies": len(records),
                "recomputed": "PASS",
                "git_revision": _revision(root, revision, historical=historical),
                "verification_scope": "historical_git_bytes" if historical else "current_and_git",
                "corrupt_controls": negatives,
            }
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
