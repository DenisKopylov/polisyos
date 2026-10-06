from pathlib import Path
import copy,json,tomllib
from tools.ops_runners.release import check_compatibility_release_gates as gate
from tools.ops_runners.release.build_release_notes import render_release_notes
root=Path('/workspace/e02-F-installed-worker-20261006/policy-engine')
path=root/'release-fragments/unreleased/2026-10-06-installed-dowhy-profile.toml'
policy=tomllib.loads((root/'architecture/gates/compatibility_release.toml').read_text())
fragment=tomllib.loads(path.read_text());fragment['__path__']=str(path)
notes=render_release_notes('0.1.0',[fragment],'2026-10-06')
errors,findings=gate._validate_fragments(root,policy,[fragment],breaking_classes=())
assert not errors,[e.as_dict() for e in errors]
corrupt=copy.deepcopy(fragment);del corrupt['compatibility_change'][0]['id']
rejected,_=gate._validate_fragments(root,policy,[corrupt],breaking_classes=())
assert any('id' in error.message for error in rejected)
print(json.dumps({'input_denominator':[str(path)],'policy':str(root/'architecture/gates/compatibility_release.toml'),'contract_errors':[e.as_dict() for e in errors],'findings':[f.as_dict() for f in findings],'negative_missing_id':[e.as_dict() for e in rejected],'outcome':'PASS','limit':'Owned one-fragment contract and realrelease renderer only; not a whole repository release readiness verdict.'},indent=2))
print(notes)
