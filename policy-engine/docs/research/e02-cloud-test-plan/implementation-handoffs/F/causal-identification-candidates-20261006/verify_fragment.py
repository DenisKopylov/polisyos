"""Scoped actual compatibility validator, not a whole-gate verdict."""
from __future__ import annotations

import json
from pathlib import Path
import tomllib

from tools.ops_runners.release.build_release_notes import structured_compatibility_changes
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments

ROOT = Path('/workspace/e02-F-tmle-20261006/policy-engine')
PATH = ROOT / 'release-fragments/unreleased/2026-10-06-causal-confidence-candidates.toml'
fragment = tomllib.loads(PATH.read_text())
fragment['__path__'] = str(PATH.relative_to(ROOT))
policy = tomllib.loads((ROOT / 'architecture/gates/compatibility_release.toml').read_text())
errors, findings = _validate_fragments(ROOT, policy, [fragment], breaking_classes=())
print(json.dumps({'fragments': 1, 'records': len(structured_compatibility_changes([fragment])),
                  'contract_errors': [item.as_dict() for item in errors],
                  'findings': [item.as_dict() for item in findings]}, indent=2))
raise SystemExit(1 if errors or findings else 0)
