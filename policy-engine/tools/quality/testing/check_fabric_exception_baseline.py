#!/usr/bin/env python3
"""Compare the legacy Fabric exception-text fingerprint with its recorded baseline."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

EXPECTED_MATCH_COUNT = 199
EXPECTED_OUTPUT_SHA256 = "8f96bc5692780655ad20a637b07f478686617f54a9e7d7d2d70ee38598499e7e"
MEASUREMENT_SCOPE = (
    "Partial coverage: normalized literal 'except Exception' text in rg-visible files "
    "under src/polisyos/fabric (all file types; rg ignore rules apply). Unmeasured: "
    "tuple/bare/aliased handlers, other exception syntax, ignored files, runtime "
    "exception safety, rollback correctness, and historical change attribution "
    "(this command compares count/digest, not baseline member identities). Comments/strings may match; "
    "this is a text fingerprint, not an AST handler census."
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare the legacy Fabric exception-text fingerprint; not runtime safety."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[3],
        help="Product root containing src/polisyos/fabric.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    search_root = Path("src") / "polisyos" / "fabric"
    print(MEASUREMENT_SCOPE)
    if not (repo_root / search_root).is_dir():
        print(
            f"[check_fabric_exception_baseline] UNRUN: no complete verdict; missing {repo_root / search_root}",
            file=sys.stderr,
        )
        return 2
    command = [
        "rg",
        "-n",
        "--color=never",
        r"except Exception(?:\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?",
        str(search_root),
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except (OSError, UnicodeError) as exc:
        print(
            f"[check_fabric_exception_baseline] UNRUN: no complete verdict; {exc}", file=sys.stderr
        )
        return 2
    if result.returncode not in {0, 1}:
        print("[check_fabric_exception_baseline] UNRUN: no complete verdict", file=sys.stderr)
        sys.stderr.write(result.stderr)
        if result.stdout:
            print("Partial coverage findings before scanner failure:", file=sys.stderr)
            sys.stderr.write(result.stdout)
        return 2

    lines = (
        []
        if not result.stdout
        else sorted(_normalize_match_line(line) for line in result.stdout.splitlines() if line)
    )
    output = "\n".join(lines)
    match_count = len(lines)
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()

    if match_count == EXPECTED_MATCH_COUNT and digest == EXPECTED_OUTPUT_SHA256:
        print(
            "[check_fabric_exception_baseline] passed: literal-text fingerprint unchanged "
            f"({match_count} matches)"
        )
        return 0

    print(
        "[check_fabric_exception_baseline] FAILED: literal-text fingerprint changed",
        file=sys.stderr,
    )
    print(
        f"expected count={EXPECTED_MATCH_COUNT} sha256={EXPECTED_OUTPUT_SHA256}",
        file=sys.stderr,
    )
    print(f"actual   count={match_count} sha256={digest}", file=sys.stderr)
    if output:
        print("\nCurrent matches:\n", file=sys.stderr)
        print(output, file=sys.stderr)
    return 1


def _normalize_match_line(line: str) -> str:
    return re.sub(r"^(.+?):\d+:", r"\1:", line, count=1)


if __name__ == "__main__":
    raise SystemExit(main())
