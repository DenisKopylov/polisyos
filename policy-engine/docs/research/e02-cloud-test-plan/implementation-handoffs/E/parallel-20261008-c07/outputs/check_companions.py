import importlib, json, platform, tomllib
from importlib.metadata import version
from pathlib import Path
from polisyos.ir.migrations.base import CompatibilityMode, get_schema_rule, negotiate_schema_version
import polisyos.ir.migrations.schema_registry
from tools.ops_runners.release.build_release_notes import render_release_notes
root=Path('/dev/shm/e02-orch03-20261008/c07')
facade=importlib.import_module('polisyos.ir')
analytics=importlib.import_module('polisyos.ir.analytics')
checks=[]
for name,module in [('ValueArtifactSubject','polisyos.ir.analytics.uncertainty'),('ValueSubjectArtifactIdentity','polisyos.ir.analytics.uncertainty'),('ValueSubjectRelation','polisyos.ir.analytics.uncertainty'),('ValueArtifactSubjectRef','polisyos.ir.registry.refs'),('ValueSubjectRelationRef','polisyos.ir.registry.refs')]:
    owner=getattr(importlib.import_module(module),name)
    assert getattr(facade,name) is owner and getattr(analytics,name) is owner
    assert name in facade.__all__ and name in analytics.__all__
    assert Path(importlib.import_module(module).__file__).is_relative_to(root/'policy-engine/src')
    checks.append({'name':name,'owner':module,'canonical_identity':True})
for schema in ['value_artifact_subject','value_subject_relation']:
    rule=get_schema_rule(schema,'1.0')
    assert rule is not None and rule.mode is CompatibilityMode.NONE
    assert negotiate_schema_version(schema,'1.0','1.0').can_read
    assert not negotiate_schema_version(schema,'1.0','9.0').can_read
    checks.append({'schema':schema,'exact_read':True,'unknown_version_refused':True})
path=root/'policy-engine/release-fragments/unreleased/2026-10-08-c07-value-subject-relation.toml'
f=tomllib.loads(path.read_text());f['__path__']=str(path)
notes=render_release_notes('0.0.0-c07',[f],'2026-10-08')
assert 'nongating' in notes and 'Default manifest views only' in notes
assert f['owner']=='team-ir' and f['change_class']=='internal'
checks.append({'release_fragment':'PASS','rendered_notes':notes})
print(json.dumps({'source':'804a6aba31125372b0b57a10041c6d6aad375ad5','tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','checks':checks,'environment':{'python':platform.python_version(),'numpy':version('numpy'),'pydantic':version('pydantic'),'pytest':version('pytest'),'uncertainty_origin':importlib.import_module('polisyos.ir.analytics.uncertainty').__file__}},indent=2))
