import importlib.util,json,tempfile
from pathlib import Path
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.uncertainty import ValueArtifactSubject,persist_value_artifact_subject,resolve_value_subject_relation
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel
root=Path('/dev/shm/e02-orch03-20261008/c07')
spec=importlib.util.spec_from_file_location('pinned_source_fixture',root/'policy-engine/tests/unit/ir/test_value_subject_relation.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
scratch=Path(tempfile.mkdtemp(prefix='ref-probe2-',dir='/dev/shm/e02-orch03-20261008/c07-checks'))
missing=ArtifactRefModel(artifact_id='sha256:'+'e'*64,kind='synthetic.value_source',media_type='application/json')
# Preserve the first harness's measured out-of-profile producer normalization gap.
seeded=scratch/'nondefault-diagnostic'
store,subject,ident,native0=fixture._producer_pair(seeded)
store,_,ident,native1=fixture._producer_pair(seeded,native_changes={'source_refs':(missing,)})
requested_subject=persist_value_artifact_subject(store,ValueArtifactSubject.model_validate({**subject.model_dump(mode='python'),'source_refs':(missing,)}))
actual_inputs=store.get_manifest(str(native1.artifact_id)).model_dump(mode='json')['inputs']
assert native0.artifact_id==native1.artifact_id and getattr(native1,'manifest_profile_sha256',None) is None
actual_subject=[x['artifact_id'] for x in actual_inputs if x['role']=='value_subject'][0]
assert actual_subject != str(requested_subject.artifact_id)
results=[]
for name in ['missing_source','missing_model','actual_foreign_source','subject_outcome_contradicts_resolved_AST']:
    case=scratch/name
    if name=='missing_source': changes={'source_refs':(missing,)}
    elif name=='missing_model': changes={'model_ref':missing}
    elif name=='actual_foreign_source':
        store=FileSystemCAS(case/'cas')
        foreign=ArtifactRefModel.model_validate(put_json_artifact(store,{'rows':[[0,3],[1,9]],'fixture':'different_actual_source'},kind='synthetic.value_source',schema_name='synthetic.value_source',schema_version='1.0'))
        changes={'source_refs':(foreign,)}
    else: changes={'outcome':'foreign_outcome'}
    # Only one native output is published per isolated case: incoming refs point at its actual default manifest.
    store,subject,ident,native=fixture._producer_pair(case,native_changes=changes)
    try:
        resolve_value_subject_relation(store,identification_ref=ident,native_uncertainty_ref=native)
    except (FileNotFoundError,ValueError) as exc:
        results.append({'name':name,'status':'PASS','refusal':str(exc),'type':type(exc).__name__})
    else: raise AssertionError(name+' did not refuse')
print(json.dumps({'source':'804a6aba31125372b0b57a10041c6d6aad375ad5','tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','profile':'synthetic contract CAS mechanics, default view only, nongating; no scientific producer/admission claim','probes':results,'measured_C06_adapter_gap':{'old_and_changed_native_payload_ID':str(native1.artifact_id),'returned_IR_selector':getattr(native1,'manifest_profile_sha256',None),'requested_new_subject_ID':str(requested_subject.artifact_id),'resolved_default_subject_ID':actual_subject,'result':'Same native bytes plus changed lineage created another Core manifest view; IR writer returned old default ref. This overlap is outside C07 default-view scope and requires C06 to preserve producer-returned selector before C10 adopts such producer.'}},indent=2))
