"""Resolve source locators from the complete observed immutable static trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Resolve exact Git path prefixes; keep the original observed output unchanged."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    marker = b'{\n  "schema": "policyos.e02.independent_static_derivation_trace.v1"'
    report = json.loads(raw[raw.index(marker) :])
    sha = report["target_sha"]
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ValueError("Git executable unavailable")

    def git(*argv: str) -> bytes:
        return subprocess.check_output([git_executable, "-C", str(args.repo), *argv])  # noqa: S603 - fixed immutable Git reads

    tracked = set(git("ls-tree", "-r", "--name-only", sha).decode().splitlines())
    origins = {}
    for missing in report["all_missing"]:
        for reference in missing["source_refs"]:
            locator = reference["locator"]
            matches = [
                path
                for path in tracked
                if locator == path
                or locator.startswith(path + "/")
                or locator.startswith(path + "#")
            ]
            if not matches:
                raise ValueError(f"No tracked source for locator: {locator}")
            origins[locator] = max(matches, key=len)
    identities = []
    for path in sorted(set(origins.values())):
        body = git("show", f"{sha}:{path}")
        identities.append(
            {"path": path, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
        )
    result = {
        "schema": "policyos.e02.independent_source_locator_normalization.v1",
        "target_sha": sha,
        "target_tree": report["target_tree"],
        "input": {
            "path": str(args.input),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "all_locator_origins": origins,
        "source_identities": identities,
        "qualification": (
            "Original c1 observer incorrectly appended .py to markdown annotation routes. "
            "Original source_refs locators, missing membership/counts, synthetic three-hop route, "
            "and observed actual failure remain unchanged and deciding. This normalizes only "
            "exact full source-locator path prefixes via complete pinned tracked membership."
        ),
    }
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
