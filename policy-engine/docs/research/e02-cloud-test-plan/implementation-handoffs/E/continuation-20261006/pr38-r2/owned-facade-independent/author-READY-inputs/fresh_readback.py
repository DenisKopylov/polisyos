"""Fresh typed consumer readback of existing native pytest CAS; no execution."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.analytics.welfare import load_welfare_bundle
from polisyos.ir.registry.refs import WelfareBundleRef
from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as owner

OUT=Path(__file__).parent;CAS=OUT/'native-combined-basetemp/test_native_ge_preserves_empir0';DEST=OUT/'fresh-cas-readback';DEST.mkdir(exist_ok=True)
manifest_candidates=[]
for path in CAS.rglob('*.manifest.json'):
 data=json.loads(path.read_text())
 if data['kind']=='ir.welfare_bundle':manifest_candidates.append(data)
ids={data['artifact_id'] for data in manifest_candidates};assert len(ids)==1
ref=WelfareBundleRef(artifact_id=next(iter(ids)))
fresh=FileSystemCAS(CAS);bundle=load_welfare_bundle(fresh,ref)
outcomes_ref=owner.ArtifactRef.model_validate(bundle.diagnostics['draw_outcomes_ref'])
outcomes=owner._load_welfare_draw_outcomes(fresh,outcomes_ref)
samples=owner._load_verified_welfare_samples(fresh,bundle.sample_bundle_ref)
report=from_canonical_bytes(fresh.get_bytes(bundle.diagnostics['propagation_report_ref']))
expected=(np.random.default_rng(31415).random(128)>=.75).astype(int).tolist()
assert len(expected)==128 and sum(expected)==36
assert outcomes['requested_draw_count']==outcomes['attempted_draw_count']==128
assert outcomes['failed_draw_count']==36 and outcomes['successful_draw_count']==92
assert [row['sampled_input']['A'] for row in outcomes['sampled_inputs']]==[float(row) for row in expected]
assert samples.welfare_draws==(2.,)*92
assert bundle.credible_interval is None and bundle.robust_interval is None
assert report['draw_summary']['welfare_mean'] is None and report['draw_summary']['conditional_welfare_mean']==2.
assert all(failure['error_type']=='LinAlgError' for row in outcomes['failure_records'] for failure in row['output_outcomes'])
exports=[]
for name,artifact in [('bundle',ref),('draw-outcomes',outcomes_ref),('sample-bundle',bundle.sample_bundle_ref),('propagation-report',bundle.diagnostics['propagation_report_ref'])]:
 store_ref=owner.ArtifactRef.model_validate(artifact.model_dump()) if hasattr(artifact,'model_dump') else artifact
 payload=fresh.get_bytes(store_ref);target=DEST/(name+'.json');target.write_bytes(payload)
 manifest=fresh.get_manifest(store_ref);(DEST/(name+'.manifest.json')).write_text(json.dumps(manifest.model_dump(mode='json',by_alias=True),indent=2)+'\n')
 exports.append({'name':name,'ref':artifact.model_dump(mode='json') if hasattr(artifact,'model_dump') else artifact,'payload_sha256':hashlib.sha256(payload).hexdigest(),'payload_bytes':len(payload),'path':str(target.relative_to(OUT)),'manifest':str((DEST/(name+'.manifest.json')).relative_to(OUT))})
result={'schema':'policyos.e02.owned_facade_native_freshCAS_readback.v1','existing_native_CAS':str(CAS),'mode':'New FileSystemCAS resolves exact persisted artifacts; no producer reexecution','bundle_ref':ref.model_dump(mode='json'),'draw_outcomes_ref':outcomes_ref.model_dump(mode='json'),'sample_ref':bundle.sample_bundle_ref.model_dump(mode='json'),'requested':128,'attempted':128,'successful':92,'failed':36,'failure_type':'LinAlgError','native_evaluator':'PropagateWelfareNode GE np.linalg.inv(I-A); pe_response2, atomA0 gives welfare2, atomA1 singular','law':'One empirical typed BOOTSTRAP carrier atoms0,1 weights3,1; independent NumPy seed31415 inverse-CDF indices','expected_atom_rows':expected,'observed_atom_rows':[row['sampled_input']['A'] for row in outcomes['sampled_inputs']],'all_draw_outcomes_retained':True,'support_complete':outcomes['support_complete'],'gate_eligible':outcomes['gate_eligible'],'conditional_mean':report['draw_summary']['conditional_welfare_mean'],'unconditional_mean':report['draw_summary']['welfare_mean'],'credible_interval':bundle.credible_interval,'robust_interval':bundle.robust_interval,'input_binding_metadata':{key:value for key,value in outcomes.items() if 'law' in key or 'source' in key or 'carrier' in key},'exports':exports,'loaded_owner_source':{'path':owner.__file__,'sha256':hashlib.sha256(Path(owner.__file__).read_bytes()).hexdigest()},'limitations':'Generic operational native GE witness; no production history, served model/evaluator source authority, institutional profile or finding closure. Existing WelfareBundle public loader itself is a legacy payload reader; stricter outcome/sample consumer owns the independent lineage reconciliation checked here.'}
(OUT/'fresh-cas-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'requested':128,'successful':92,'failed':36,'conditional_mean':2.,'unconditional_mean':None,'export_count':len(exports)},indent=2))
