"""Find compatibility inputs without copying historical proof packets."""

import json
import os
import subprocess
from pathlib import Path


root = Path("architecture/policy_design_case")
globbed = {str(path) for path in root.rglob("*.json")}
walked = {str(Path(directory) / name) for directory, _, names in os.walk(root)
          for name in names if name.endswith(".json")}
assert globbed == walked, sorted(globbed.symmetric_difference(walked))
matches = set()
ambiguous = []


def visit(value, path):
    if isinstance(value, dict):
        if (value.get("schema_version") == "policyos.runtime.intervention_substrate_lift.v2"
                and "law_token" in value and "legal_threshold_evaluation" in value):
            matches.add(path)
        for nested in value.values():
            visit(nested, path)
    elif isinstance(value, list):
        for nested in value:
            visit(nested, path)


for path in sorted(globbed):
    try:
        visit(json.loads(Path(path).read_text()), path)
    except Exception as exc:
        ambiguous.append({"path": path, "error": str(exc)})
print(json.dumps({
    "denominator": "architecture/policy_design_case/**/*.json",
    "glob_count": len(globbed), "walk_count": len(walked), "identity_symmetric_difference": [],
    "matches": [{"path": path, "git_blob": subprocess.check_output(
        ["git", "hash-object", path], text=True).strip()} for path in sorted(matches)],
    "ambiguous": ambiguous,
}))
