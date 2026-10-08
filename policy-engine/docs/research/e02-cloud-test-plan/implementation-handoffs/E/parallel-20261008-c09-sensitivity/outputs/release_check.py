import json
import sys
import tomllib
from pathlib import Path

root=Path.cwd()/'policy-engine'
sys.path.insert(0,str(root))
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
policy=tomllib.loads((root/'architecture/gates/compatibility_release.toml').read_text())
path=root/'release-fragments/unreleased/2026-10-08-c09-sensitivity-response-basis.toml'
fragment=tomllib.loads(path.read_text());fragment['__path__']=str(path.relative_to(root))
errors,findings=_validate_fragments(root,policy,[fragment],breaking_classes=())
print(json.dumps({'candidate_source_sha':'c9125bc5e4d2992adeae468a79189d1fa535c88b','companion_sha':'f2c102fa2ee588b91b2baaa8c9d1c393699838c0','fragment':fragment['__path__'],'errors':[vars(item) for item in errors],'findings':[vars(item) for item in findings],'denominator':{'fragment_count':1,'compatibility_rows':len(fragment['compatibility_change'])},'public_inventory':'not claimed; canonical classification packet pending'},indent=2))
sys.exit(bool(errors))
