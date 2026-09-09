"""Find compatibility inputs without copying historical proof packets."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

root = Path("architecture/policy_design_case")
globbed = {str(path) for path in root.rglob("*.json")}
walked = {str(Path(directory) / name) for directory, _, names in os.walk(root)
          for name in names if name.endswith(".json")}
if globbed != walked:
    raise ValueError(sorted(globbed.symmetric_difference(walked)))
matches: set[str] = set()
ambiguous: list[dict[str, str]] = []


def visit(value: object, path: str) -> None:
    if isinstance(value, dict):
        if (value.get("schema_version") == "policyos.runtime.intervention_substrate_lift.v2"
                and "law_token" in value and "legal_threshold_evaluation" in value):
            matches.add(path)
        for nested in value.values():
            visit(nested, path)
    elif isinstance(value, list):
        for nested in value:
            visit(nested, path)


def _git_blob(path: str) -> str:
    return subprocess.check_output(  # noqa: S603 - fixed local git argv; enumerated path is data.
        ["/usr/bin/git", "hash-object", path], text=True,
    ).strip()


for path in sorted(globbed):
    try:
        visit(json.loads(Path(path).read_text()), path)
    except Exception as exc:
        ambiguous.append({"path": path, "error": str(exc)})
sys.stdout.write(json.dumps({
    "denominator": "architecture/policy_design_case/**/*.json",
    "glob_count": len(globbed), "walk_count": len(walked), "identity_symmetric_difference": [],
    "matches": [{"path": path, "git_blob": _git_blob(path)} for path in sorted(matches)],
    "ambiguous": ambiguous,
}) + "\n")
