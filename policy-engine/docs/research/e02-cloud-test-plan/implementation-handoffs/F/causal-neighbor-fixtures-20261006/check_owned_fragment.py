import pathlib,tomllib,json
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments,DEFAULT_POLICY
from tools.ops_runners.release.build_release_notes import structured_compatibility_changes,render_release_notes
root=pathlib.Path('/workspace/e02-F-graph-20261006/policy-engine');p=root/'release-fragments/unreleased/2026-10-06-causal-neighbor-fixtures.toml';f=tomllib.loads(p.read_text());f['__path__']=str(p)
errors,findings=_validate_fragments(root,tomllib.loads(DEFAULT_POLICY.read_text()),[f],breaking_classes=())
records=structured_compatibility_changes([f]);print(json.dumps({'records':records,'errors':[e.as_dict() for e in errors],'findings':[e.as_dict() for e in findings]},indent=2));print(render_release_notes('unreleased-causal-neighbor-fixtures',[f],'2026-10-06'))
assert len(records)==1 and records[0]['change_class']=='internal' and records[0]['impact']=='compatible' and not errors and not findings
