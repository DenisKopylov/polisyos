"""Recompute candidate blob provenance over the complete held14 supplier set."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REVISIONS = {
    "G": "93d6aa62a8d236667fdf322a5fc17962523b185e",
    "C05": "5ccbfa15c5671623a4c1ff7a3145460c5ca5a857",
    "proposal": "42987be62c48356211e1ce4397ca67cd45249997",
}
RESOURCE_PATH = "policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py"
REVIEW_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
    "C/orch02-r2-20261008/delivery/reviews/"
    "c05-independent-G-proposal-review-0e7a4658.json"
)


def _git(root: Path, *args: str) -> str | None:
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("git executable is unavailable")
    result = subprocess.run(  # noqa: S603 - fixed local, read-only Git blob queries.
        [git_executable, "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> None:
    """Compare each current supplier blob with all pinned source trees."""
    root = Path(__file__).resolve().parents[8]
    review = json.loads((root / REVIEW_PATH).read_text())
    paths: list[str] = review["held14supplier_paths"]
    counts = {"G-only": 0, "G": 0, "C05": 0, "neither_G_or_C05": 0}
    matching_paths: dict[str, list[str]] = {name: [] for name in counts}
    proposal_matches: list[str] = []

    for path in paths:
        candidate = _git(root, "hash-object", "--", path)
        if candidate is None:
            raise RuntimeError(f"Current supplier is missing: {path}")
        source_blobs = {
            name: _git(root, "rev-parse", f"{revision}:{path}")
            for name, revision in REVISIONS.items()
        }
        if path == RESOURCE_PATH:
            if candidate != source_blobs["G"]:
                raise RuntimeError("The G-only Catalog _resources.py blob changed")
            category = "G-only"
        elif candidate == source_blobs["G"]:
            category = "G"
        elif candidate == source_blobs["C05"]:
            category = "C05"
        else:
            category = "neither_G_or_C05"
        counts[category] += 1
        matching_paths[category].append(path)
        if candidate == source_blobs["proposal"]:
            proposal_matches.append(path)

    if len(paths) != 14 or sum(counts.values()) != len(paths):
        raise RuntimeError(f"Unexpected held supplier denominator: {len(paths)}")
    lines = [f"denominator={len(paths)} (review.json held14supplier_paths)"]
    for category, count in counts.items():
        lines.append(f"{category}={count}")
        for path in matching_paths[category]:
            lines.append(f"  {path}")
    lines.append(f"proposal_exact_matches={len(proposal_matches)}")
    for path in proposal_matches:
        lines.append(f"  {path}")
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
