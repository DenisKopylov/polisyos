import importlib.util,json,tempfile
from pathlib import Path
from polisyos.ir.analytics.uncertainty import resolve_value_subject_relation
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel
root=Path('/dev/shm/e02-orch03-20261008/c07')
spec=importlib.util.spec_from_file_location('pinned_source_fixture',root/'policy-engine/tests/unit/ir/test_value_subject_relation.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
scratch=Path(tempfile.mkdtemp(prefix='ref-probe-',dir='/dev/shm/e02-orch03-20261008/c07-checks'))
results=[]
for name in ['missing_source','missing_model','actual_foreign_source','subject_outcome_contradicts_resolved_AST']:
    case=scratch/name
    store,subject,ident,native=fixture._producer_pair(case)
    missing=ArtifactRefModel(artifact_id='sha256:'+'e'*64,kind='synthetic.value_source',media_type='application/json')
    if name=='missing_source': changes={'source_refs':(missing,)}
    elif name=='missing_model': changes={'model_ref':missing}
    elif name=='actual_foreign_source':
        foreign=ArtifactRefModel.model_validate(put_json_artifact(store,{'rows':[[0,3],[1,9]],'fixture':'different_actual_source'},kind='synthetic.value_source',schema_name='synthetic.value_source',schema_version='1.0'))
        assert foreign.artifact_id != subject.source_refs[0].artifact_id
        changes={'source_refs':(foreign,)}
    else: changes={'outcome':'foreign_outcome'}
    store,_,ident,native=fixture._producer_pair(case,native_changes=changes)
    try:
        resolve_value_subject_relation(store,identification_ref=ident,native_uncertainty_ref=native)
    except (FileNotFoundError,ValueError) as exc:
        results.append({'name':name,'status':'PASS','refusal':str(exc),'type':type(exc).__name__})
    else: raise AssertionError(name+' did not refuse')
print(json.dumps({'source':'804a6aba31125372b0b57a10041c6d6aad375ad5','tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','profile':'synthetic contract CAS mechanics, nongating; no scientific producer/admission claim','probes':results},indent=2))
