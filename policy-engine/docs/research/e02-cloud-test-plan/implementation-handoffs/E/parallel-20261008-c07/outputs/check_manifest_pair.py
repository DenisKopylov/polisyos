import hashlib,importlib.util,json,tempfile
from pathlib import Path
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.uncertainty import resolve_value_subject_relation
from polisyos.ir.registry.refs import ArtifactRefModel
root=Path('/dev/shm/e02-orch03-20261008/c07')
spec=importlib.util.spec_from_file_location('pinned_source_fixture',root/'policy-engine/tests/unit/ir/test_value_subject_relation.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
scratch=Path(tempfile.mkdtemp(prefix='manifest-pair-',dir='/dev/shm/e02-orch03-20261008/c07-checks'))
original=FileSystemCAS.put_json
refs=[]
def observe_actual_put(self,data,opts=None,**kwargs):
    result=original(self,data,opts,**kwargs)
    if result.kind=='ir.uncertainty_envelope': refs.append(result)
    return result
FileSystemCAS.put_json=observe_actual_put
try:
    store,subject,ident,native0=fixture._producer_pair(scratch)
    missing=ArtifactRefModel(artifact_id='sha256:'+'e'*64,kind='synthetic.value_source',media_type='application/json')
    store,_,ident,native1=fixture._producer_pair(scratch,native_changes={'source_refs':(missing,)})
finally: FileSystemCAS.put_json=original
assert len(refs)==2 and refs[0].artifact_id==refs[1].artifact_id
assert refs[0].manifest_profile_sha256 is None and refs[1].manifest_profile_sha256 is not None
fresh=FileSystemCAS(store.root)
assert fresh.get_bytes(refs[0])==fresh.get_bytes(refs[1])
manifests=[fresh.get_manifest(r).model_dump(mode='json') for r in refs]
assert manifests[0]['inputs'] != manifests[1]['inputs']
default=resolve_value_subject_relation(fresh,identification_ref=ident,native_uncertainty_ref=native1)
assert default.resolved_subject==subject
try:
    resolve_value_subject_relation(fresh,identification_ref=ident,native_uncertainty_ref=refs[1])
except ValueError as exc:
    assert str(exc)=='value_subject_selected_manifest_view_unsupported'
    refusal=str(exc)
else: raise AssertionError('C07 admitted explicit selected ref')
print(json.dumps({'source':'804a6aba31125372b0b57a10041c6d6aad375ad5','tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','probe':'Observed original Core put_json return before canonical IR normalization; actual writes/readers execute, no replacement producer or fabricated success','actual_Core_refs':[r.model_dump(mode='json') for r in refs],'actual_IR_returned_ref':native1.model_dump(mode='json'),'actual_reopened_manifests':manifests,'bytes_sha256':hashlib.sha256(fresh.get_bytes(refs[1])).hexdigest(),'default_reader_resolved_subject':default.resolved_subject.model_dump(mode='json'),'explicit_selected_ref_refusal':refusal,'conclusion':'Default reader is mechanical/content-bound only; producer selector loss remains C06 dependency, producer currentness/view composition not established; no scientific admission.'},indent=2))
