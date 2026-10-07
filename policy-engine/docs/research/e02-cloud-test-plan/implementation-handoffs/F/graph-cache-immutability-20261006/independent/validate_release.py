import hashlib,json,subprocess,tomllib
from pathlib import Path
from tools.ops_runners.release.build_release_notes import render_release_notes,structured_compatibility_changes
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
wd=Path('/workspace/e02-F-graph-20261006/policy-engine');out=Path('/workspace/e02-F-20261006-receipts/final-root/b220-independent-review');final='2137961b0d3a2b39b85c5a57bf774777d2a4204e';runtime='e2c4eb3142f329dfee798d22cea3ae1035306ab0';path='policy-engine/release-fragments/unreleased/2026-10-06-causal-graph-cache-rows.toml'
def git(*a):return subprocess.check_output(['git',*a],cwd=wd)
raw=git('show',final+':'+path);f=tomllib.loads(raw.decode());f['__path__']=path.removeprefix('policy-engine/')
policy=tomllib.loads(git('show',final+':policy-engine/architecture/gates/compatibility_release.toml').decode())
errors,findings=_validate_fragments(wd,policy,[f],breaking_classes=())
changes=structured_compatibility_changes([f]);rendered=render_release_notes('candidate',[f],'2026-10-06');(out/'release-rendered.md').write_text(rendered)
assert not errors and len(changes)==1 and changes[0]['change_class']=='python-public-api'
assert 'Structured Compatibility Changes' in rendered and 'detached' in rendered
changed=git('diff','--name-only',runtime,final).decode().splitlines();assert changed==[path]
original=tomllib.loads(git('show',runtime+':'+path).decode());original['__path__']=f['__path__'];assert structured_compatibility_changes([original])==[]
r={'outcome':'PASS','implementation_sha':final,'runtime_and_test_sha':runtime,'only_delta':changed,'fragment_sha256':hashlib.sha256(raw).hexdigest(),'fragment_bytes':len(raw),'structured_record_count':len(changes),'errors':[x.as_dict() for x in errors],'findings':[x.as_dict() for x in findings],'rendered_output':str(out/'release-rendered.md'),'historical_e2c_release_scope':'0structuredrecords: top-level classification ignored, metadata-only corrected at213','gate_scope':'Canonical _validate_fragments and release renderer on exactone ownedfragment+policy only; no whole repository release/architecture gate claim.'}
(out/'release-validation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
