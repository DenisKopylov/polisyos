"""Validate the owned release fragment through the existing release policy."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments

root = Path.cwd()
fragment = root / "release-fragments/unreleased/2026-10-06-foundry-canonical-output-monitor.toml"
policy = tomllib.loads((root / "architecture/gates/compatibility_release.toml").read_text())
payload = tomllib.loads(fragment.read_text())
payload["__path__"] = str(fragment)
errors, findings = _validate_fragments(root, policy, [payload], breaking_classes=())
print(json.dumps({"scope": "owned fragment only; full release policy/global fragment set unrun",
                  "fragment": str(fragment), "errors": [error.as_dict() for error in errors],
                  "findings": [finding.as_dict() for finding in findings]}, indent=2))
raise SystemExit(bool(errors))
