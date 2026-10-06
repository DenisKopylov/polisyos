"""Invoke canonical fragment validation and rendering on the exact owned fragment."""

import json
import tomllib
from pathlib import Path

from tools.ops_runners.release.build_release_notes import render_release_notes
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments

product = Path.cwd()
path = product / "release-fragments/unreleased/2026-10-06-causal-confidence-issue-preservation.toml"
fragment = tomllib.loads(path.read_text())
fragment["__path__"] = str(path)
policy = tomllib.loads((product / "architecture/gates/compatibility_release.toml").read_text())
errors, findings = _validate_fragments(product, policy, [fragment], breaking_classes=())
rendered = render_release_notes("0.0.0-review", [fragment], "2026-10-06")
record = {
    "scope": "single owned fragment; not whole repository compatibility verdict",
    "path": str(path),
    "fragment_count": 1,
    "structured_changes": len(fragment["compatibility_change"]),
    "contract_errors": [item.as_dict() for item in errors],
    "findings": [item.as_dict() for item in findings],
    "rendered_release_notes": rendered,
}
print(json.dumps(record, indent=2))
assert not errors and not findings, record
