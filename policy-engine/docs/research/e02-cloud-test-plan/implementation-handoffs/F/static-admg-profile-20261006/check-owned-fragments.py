import pathlib,tomllib,json
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments, DEFAULT_POLICY
from tools.ops_runners.release.build_release_notes import structured_compatibility_changes, render_release_notes
root=pathlib.Path('/workspace/e02-F-graph-20261006/policy-engine');files=['2026-10-06-causal-graph-cache-rows.toml','2026-10-06-static-admg-profile.toml'];fragments=[]
for f in files:
 p=root/'release-fragments/unreleased'/f;x=tomllib.loads(p.read_text());x['__path__']=str(p);fragments.append(x)
policy=tomllib.loads(DEFAULT_POLICY.read_text());errors,findings=_validate_fragments(root,policy,fragments,breaking_classes=('internal',))
print(json.dumps({'structured':structured_compatibility_changes(fragments),'errors':[x.as_dict() for x in errors],'findings':[x.as_dict() for x in findings]},indent=2))
print(render_release_notes('unreleased-f-static-profile',fragments,'2026-10-06'))
assert len(structured_compatibility_changes(fragments))==2 and not errors and not findings
