"""Recompute the review receipt's moderate output identities."""

import hashlib
import json
import sys
from pathlib import Path


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def validate(path: object) -> dict[str, object]:
    document = json.loads(Path(path).read_text())
    for ref in document["output_refs"]:
        data = Path(ref["path"]).read_bytes()
        if len(data) != ref["bytes"] or hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise ValueError("output hash/size mismatch: " + ref["path"])
    for family in document["families"].values():
        if family["suite"]["failures"] or family["suite"]["errors"] or family["suite"]["skipped"]:
            raise ValueError("affected native suite did not fully pass")
    return {
        "ok": True,
        "refs": len(document["output_refs"]),
        "code_verdicts": {k: v["code_verdict"] for k, v in document["families"].items()},
    }


if __name__ == "__main__":
    _write_stdout(json.dumps(validate(sys.argv[1]), sort_keys=True))
