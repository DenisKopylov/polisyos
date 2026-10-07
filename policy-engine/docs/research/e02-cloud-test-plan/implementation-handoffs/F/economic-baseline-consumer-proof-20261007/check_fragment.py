from pathlib import Path
import tomllib,json,hashlib
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
root=Path('/workspace/e02-F-economics-20261006/policy-engine');p=root/'release-fragments/unreleased/2026-10-07-economic-baseline-consumer-proof.toml';policy=root/'architecture/gates/compatibility_release.toml'
fragment=tomllib.loads(p.read_text());fragment['_path']=str(p)
errors,findings=_validate_fragments(root,tomllib.loads(policy.read_text()),[fragment],breaking_classes=())
print(json.dumps({'source_sha':'193b3582a72c640c1d06a131f93502654a77a36a','scope':'Canonical complete fragment validator on exactly the unique internal test/documentation fragment; not full repository release or architecture gate.','inputs':[{'path':str(x),'bytes':len(x.read_bytes()),'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in [p,policy]],'errors':[x.as_dict() for x in errors],'findings':[x.as_dict() for x in findings]},ensure_ascii=False,indent=2));assert not errors
