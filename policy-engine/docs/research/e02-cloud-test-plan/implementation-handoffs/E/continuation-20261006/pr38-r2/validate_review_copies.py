"""Recompute portable review copy identities; deliberately corrupt one hash."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def validate(root: Path, records: list[dict]) -> None:
    for record in records:
        relative = Path(record["copied_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Review copy must be repository relative")
        payload = (root / relative).read_bytes()
        if len(payload) != record["bytes"]:
            raise ValueError(f"Review size mismatch: {relative}")
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError(f"Review digest mismatch: {relative}")


def main() -> None:
    here = Path(__file__).resolve()
    root = next(parent for parent in here.parents if (parent / "AGENTS.md").is_file())
    records = json.loads((here.parent / "independent-reviews/copy-index.json").read_text())[
        "records"
    ]
    validate(root, records)
    corrupted = [dict(record) for record in records]
    corrupted[0]["sha256"] = "0" * 64
    try:
        validate(root, corrupted)
    except ValueError:
        negative = "rejected"
    else:
        raise AssertionError("Integrity-valid marker must not replace content validation")
    sys.stdout.write(
        json.dumps({"copies": len(records), "recomputed": "PASS", "corrupt_digest": negative})
        + "\n"
    )


if __name__ == "__main__":
    main()
