"""Check only the owned compatibility fragment through canonical release policy."""
from pathlib import Path
import json
import tomllib
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
root = Path.cwd()
path = root / 'release-fragments/unreleased/2026-10-06-foundry-output-anomaly-count.toml'
policy = tomllib.loads((root / 'architecture/gates/compatibility_release.toml').read_text())
payload = tomllib.loads(path.read_text())
payload['__path__'] = str(path)
errors, findings = _validate_fragments(root, policy, [payload], breaking_classes=())
print(json.dumps({'scope': 'Owned fragment only, not global compatibility policy PASS',
                 'errors': [x.as_dict() for x in errors], 'findings': [x.as_dict() for x in findings]}, indent=2))
raise SystemExit(bool(errors))
