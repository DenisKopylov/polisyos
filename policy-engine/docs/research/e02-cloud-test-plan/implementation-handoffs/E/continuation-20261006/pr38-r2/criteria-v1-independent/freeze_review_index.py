#!/usr/bin/env python3
"Index moderate review outputs and check immutable Git inputs, read-only."

import argparse
import copy
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def digest(payload: object) -> dict[str, object]:
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def verify(record: object, root: object) -> None:
    actual = digest((root / record["relative_path"]).read_bytes())
    if actual != {"bytes": record["bytes"], "sha256": record["sha256"]}:
        raise ValueError("Indexed review payload differs: " + record["relative_path"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--review-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    records = []
    for path in sorted(args.review_root.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.resolve() != args.output.resolve()
        ):
            record = {
                "source_path": str(path),
                "relative_path": path.relative_to(args.review_root).as_posix(),
                **digest(path.read_bytes()),
            }
            verify(record, args.review_root)
            records.append(record)
    snapshots = json.loads((args.review_root / "git-input-snapshot-index.json").read_text())
    for record in snapshots["records"]:
        payload = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [
                _resolve_executable("git"),
                "-C",
                str(args.repo),
                "show",
                record["source_sha"] + ":" + record["git_path"],
            ]
        )
        if (
            digest(payload)
            != {
                "bytes": record["bytes"],
                "sha256": record["sha256"],
            }
            or pathlib.Path(record["copied_path"]).read_bytes() != payload
        ):
            raise ValueError("Immutable Git snapshot differs: " + record["git_path"])
    negatives = []
    for field, wrong in [("bytes", -1), ("sha256", "0" * 64)]:
        bad = copy.deepcopy(records[0])
        bad[field] = wrong
        try:
            verify(bad, args.review_root)
        except ValueError as exc:
            negatives.append(
                {"control": "corrupt_" + field, "state": "REJECTED", "reason": str(exc)}
            )
        else:
            raise AssertionError("Corrupt publication index accepted: " + field)
    result = {
        "schema": "policyos.e02.independent-review-copy-index.v1",
        "reviewer": "/root/ddm_r2",
        "source_publication_sha": snapshots["source_sha"],
        "implementation_source_sha": "f445cbc3439b1539937e8e3f6df492bbd6c2e4a3",
        "scope": "Bounded criteria matrix, local recipes and Git publication review",
        "state": "PASS",
        "immutable_git_inputs_rechecked": len(snapshots["records"]),
        "file_count": len(records),
        "total_bytes": sum(record["bytes"] for record in records),
        "files": records,
        "negative_controls": negatives,
        "historical_902": "Superseded/nondeciding; exact ready draft bytes unavailable",
        "exclusions": [
            "index itself",
            "Python bytecode cache",
            "large ignored raw dump",
        ],
        "future_source_or_numeric_wave_claimed": False,
        "cleanup_candidates": [],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    _write_stdout(
        json.dumps(
            {k: result[k] for k in ["state", "file_count", "total_bytes", "negative_controls"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
