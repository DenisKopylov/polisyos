import copy
import hashlib
import json
import sys
from pathlib import Path


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


P = Path(__file__).parent


def validate(index: object) -> None:
    if not (index["total_files"] == len(index["files"])):
        raise AssertionError
    if not (index["total_bytes"] == sum(row["size_bytes"] for row in index["files"])):
        raise AssertionError
    for row in index["files"]:
        data = (P / row["path"]).read_bytes()
        if not (len(data) == row["size_bytes"]):
            raise AssertionError(row["path"] + " size")
        if not (hashlib.sha256(data).hexdigest() == row["sha256"]):
            raise AssertionError(row["path"] + " hash")


index = json.loads((P / "copy-index.json").read_text())
validate(index)
negatives = []
for field, value in [("size_bytes", -1), ("sha256", "0" * 64)]:
    corrupt = copy.deepcopy(index)
    corrupt["files"][0][field] = value
    try:
        validate(corrupt)
    except AssertionError:
        negatives.append({"corrupt_field": field, "outcome": "REJECTED"})
    else:
        raise AssertionError("corrupt deciding receipt admitted")
_write_stdout(
    json.dumps(
        {"validated_files": len(index["files"]), "negative_controls": negatives, "outcome": "PASS"},
        indent=2,
    )
)
