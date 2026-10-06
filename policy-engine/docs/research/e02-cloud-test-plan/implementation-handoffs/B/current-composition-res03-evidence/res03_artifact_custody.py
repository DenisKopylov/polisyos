"""Read the actual retained RES-03 producer fixture; never claim served consumption."""
from __future__ import annotations
import hashlib,json,pathlib,subprocess,sys
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.core.security.tenant_context import tenant_scope
import polisyos.core.artifacts.store as owner
fixture=pathlib.Path(sys.argv[1]).resolve();producer_sha=sys.argv[2];destination=pathlib.Path(sys.argv[3]).resolve();destination.mkdir(parents=True,exist_ok=True)
source_path='policy-engine/src/polisyos/core/artifacts/store.py';source_bytes=pathlib.Path(owner.__file__).read_bytes()
assert source_bytes==subprocess.check_output(['git','show',producer_sha+':'+source_path])
selected_kinds={'scientist.experiment_state','scientist.workflow_report','foundry.simulation_result','foundry.exec_plan','foundry.input_bindings'}
store=FileSystemCAS(fixture);manifest_paths=sorted(fixture.rglob('*.manifest.json'));records=[];payloads={};manifests={}
with tenant_scope(None,tenant_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',cell_id='cell-a'):
 for path in manifest_paths:
  if '.view.' in path.name:continue
  manifest_json=json.loads(path.read_bytes())
  if manifest_json['kind'] not in selected_kinds:continue
  ref=ArtifactRef(artifact_id=manifest_json['artifact_id'],kind=manifest_json['kind'],media_type=manifest_json['media_type'])
  blob=store.get_bytes(ref);manifest=store.get_manifest(ref);payload=from_canonical_bytes(blob)
  assert hashlib.sha256(blob).hexdigest()==str(ref.artifact_id).split(':',1)[1]
  assert manifest.kind==ref.kind and manifest.media_type==ref.media_type
  assert manifest.tenant_context.tenant_id=='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' and manifest.tenant_context.cell_id=='cell-a'
  payloads.setdefault(ref.kind,[]).append(payload);manifests[ref.kind]=manifest
  copied=[]
  blob_path=path.with_name(path.name.replace('.manifest.json','.blob'))
  paths=[blob_path,path,*sorted(path.parent.glob(path.name.replace('.manifest.json','.view.*.manifest.json')))]
  for actual in paths:
   relative=actual.relative_to(fixture);target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);data=actual.read_bytes();target.write_bytes(data)
   copied.append({'path':str(relative),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
  records.append({'ref_as_read':ref.model_dump(mode='json'),'files':copied})
report,=payloads['scientist.workflow_report'];simulation_raw,=payloads['foundry.simulation_result'];simulation=SimulationResult.model_validate(simulation_raw)
final,= [s for s in payloads['scientist.experiment_state'] if s['artifacts_index'].get('simulation_result_ref')]
node_records={n['alias']:n for n in report['nodes']};sim_ref=final['artifacts_index']['simulation_result_ref']
assert report['run_id']==final['run_id']=='R_res03_real_route' and report['status']=='fail'
assert node_records['run_simulation']['status']=='ok' and any(r['artifact_id']==sim_ref['artifact_id'] for r in node_records['run_simulation']['artifacts'])
assert node_records['later_failure']['status']=='fail' and node_records['later_failure']['error']['code']=='res03.later_failure'
assert node_records['later_failure']['error']['details']['scope']['simulation_result_ref']==sim_ref['artifact_id']
assert node_records['dependent_after_failure']['status']=='skip' and node_records['dependent_after_failure']['skip_reason']=='upstream_failed' and not node_records['dependent_after_failure']['artifacts']
assert node_records['independent_sibling']['status']=='ok' and final['params']['res03_independent_ran'] is True
assert 'res03_dependent_output' not in final['params']
assert simulation.exec_plan_ref is not None
roles={i.role for i in manifests['foundry.simulation_result'].inputs}
assert {'exec_plan','input.input_bindings_ref','input.data_snapshot_ref','input.bound_state_snapshot_ref','state_snapshot'} <= roles
trace=fixture/'runs/R_res03_real_route/trace.jsonl';trace_bytes=trace.read_bytes();(destination/'trace.jsonl').write_bytes(trace_bytes)
print(json.dumps({'producer_source_sha':producer_sha,'readback_source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'store_module':owner.__file__,'store_sha256':hashlib.sha256(source_bytes).hexdigest(),'fixture':str(fixture),'guarded_scope':{'tenant_id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','cell_id':'cell-a'},'property':'real guarded producer artifact/report/state readback; no HTTP consumer execution','node_outcomes':{name:{'status':node_records[name]['status'],'skip_reason':node_records[name].get('skip_reason')} for name in ['run_simulation','later_failure','dependent_after_failure','independent_sibling']},'simulation_ref_as_persisted':sim_ref,'manifest_profile_limit':'Persisted producer refs in this fixture omit selected manifest profile; native default manifest reads are recorded as such, not converted into selected-view authority.','simulation_input_roles':sorted(roles),'manifest_file_denominator':len(manifest_paths),'retained_selected_kinds':sorted(selected_kinds),'artifacts':records,'trace':{'sha256':hashlib.sha256(trace_bytes).hexdigest(),'bytes':len(trace_bytes)},'served_consumer_executed':False},indent=2))
