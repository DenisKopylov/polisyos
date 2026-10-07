"""Persisted temporal-chain controls on independently produced real native runs."""
from pathlib import Path
import hashlib, json, subprocess, sys, types
import numpy as np
from polisyos.core.artifacts import ArtifactRef, PutOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.trinity import TrinityBundle
from polisyos.foundry.execute.executor import load_state_snapshot
root=Path('/workspace/e02-E-pr38-r2-receipts/independent-ddm-reviewer/backtest')
source_sha='5ad90749c5ae745b1cb5345a5543b28dd19c2f76'
source_path='policy-engine/src/polisyos/scientist/methods/backtesting/native_replay.py'
source=subprocess.check_output(['git','show',source_sha+':'+source_path],cwd='/workspace/e02-E-backtest-20261006')
module=types.ModuleType('reviewed_native_replay_5ad')
module.__file__=source_sha+':'+source_path
module.__package__='polisyos.scientist.methods.backtesting'
sys.modules[module.__name__]=module
exec(compile(source,module.__file__,'exec'),module.__dict__)
module._validate_compiled_model=lambda *args, **kwargs: None
print("PROPERTY REMOVAL: actual plan→Trinity checks disabled; all carrier fields retained",flush=True)
load_native_forecast=module.load_native_forecast
print(json.dumps({'source_sha':source_sha,'source_path':source_path,'source_sha256':hashlib.sha256(source).hexdigest(),'overlay':'immutable exact Git blob; no author source modification'}),flush=True)
observations=json.loads((root/'native_K3/observations.json').read_text())
item=next(x for x in observations if x['name']=='native_K3_replica')
store=FileSystemCAS(root/'native_K3/cas')
forecast_ref=ArtifactRef(artifact_id=item['forecast_ref'],kind='scientist.backtest.native_forecast',media_type='application/json')
request_ref=ArtifactRef(artifact_id=item['request_ref'],kind='scientist.backtest.native_forecast_request',media_type='application/json')
forecast,request=load_native_forecast(store,forecast_ref,request_ref)
def test(name,update):
    candidate=forecast.model_copy(update=update)
    ref=store.put_json(candidate,PutOptions(kind='scientist.backtest.native_forecast',media_type='application/json',schema=SchemaInfo(name='polisyos.scientist.backtesting.NativeForecastTrajectory',version='1.0')),canon_spec=CanonSpec(forbid_floats=False))
    assert store.verify(ref).ok
    record={'name':name,'original_ref':str(forecast_ref.artifact_id),'candidate_ref':str(ref.artifact_id),'request_ref':str(request_ref.artifact_id),'hash_valid':True,'profile_times':request.profile.time_index}
    try:
        loaded,_=load_native_forecast(FileSystemCAS(store.root),ref,request_ref)
    except Exception as exc:
        record.update(accepted=False,exception=type(exc).__name__,message=str(exc))
    else:
        record.update(accepted=True,values=loaded.values,actual_snapshot_steps=[int(np.asarray(load_state_snapshot(store,snapshot_ref=s).step)) for s in loaded.state_snapshot_refs])
    print(json.dumps(record,sort_keys=True),flush=True)
    return record
records=[]
records.append(test('paired_whole_blocks_reversed',{'simulation_refs':list(reversed(forecast.simulation_refs)),'state_snapshot_refs':list(reversed(forecast.state_snapshot_refs)),'execution_bindings_refs':list(reversed(forecast.execution_bindings_refs)),'values':{'income':list(reversed(forecast.values['income']))}}))
records.append(test('second_block_duplicated',{'simulation_refs':[forecast.simulation_refs[1]]*2,'state_snapshot_refs':[forecast.state_snapshot_refs[1]]*2,'execution_bindings_refs':[forecast.execution_bindings_refs[1]]*2,'values':{'income':[forecast.values['income'][1]]*2}}))
records.append(test('initial_binding_substituted',{'input_bindings_ref':forecast.execution_bindings_refs[1]}))
original_trinity=TrinityBundle.model_validate(from_canonical_bytes(store.get_bytes(request.trinity_bundle_ref)))
policy=original_trinity.policy_spec.model_dump(mode='json')
policy['interventions'][0]['params']['rate']='0.5'
new_trinity=original_trinity.model_copy(update={'policy_spec':type(original_trinity.policy_spec).model_validate(policy)})
trinity_ref=store.put_json(new_trinity,PutOptions(kind='ir.trinity_bundle',media_type='application/json',schema=SchemaInfo(name='polisyos.ir.TrinityBundle',version=new_trinity.schema_version)),canon_spec=CanonSpec(forbid_floats=False))
new_request=request.model_copy(update={'trinity_bundle_ref':trinity_ref})
new_request_ref=store.put_json(new_request,PutOptions(kind='scientist.backtest.native_forecast_request',media_type='application/json',schema=SchemaInfo(name='polisyos.scientist.backtesting.NativeForecastRequest',version='1.0')),canon_spec=CanonSpec(forbid_floats=False))
new_forecast=forecast.model_copy(update={'request_ref':new_request_ref})
new_forecast_ref=store.put_json(new_forecast,PutOptions(kind='scientist.backtest.native_forecast',media_type='application/json',schema=SchemaInfo(name='polisyos.scientist.backtesting.NativeForecastTrajectory',version='1.0')),canon_spec=CanonSpec(forbid_floats=False))
model_record={'name':'unexecuted_trinity_substitution','old_trinity_ref':str(request.trinity_bundle_ref.artifact_id),'new_trinity_ref':str(trinity_ref.artifact_id),'candidate_ref':str(new_forecast_ref.artifact_id),'request_ref':str(new_request_ref.artifact_id),'hash_valid':store.verify(new_forecast_ref).ok,'declared_tax_rate':'.5','actually_executed_tax_rate':'.25'}
try: loaded,_=load_native_forecast(FileSystemCAS(store.root),new_forecast_ref,new_request_ref)
except Exception as exc: model_record.update(accepted=False,message=str(exc))
else: model_record.update(accepted=True,values=loaded.values)
print(json.dumps(model_record,sort_keys=True),flush=True);records.append(model_record)

records.append(test('first_block_duplicated',{'simulation_refs':[forecast.simulation_refs[0]]*2,'state_snapshot_refs':[forecast.state_snapshot_refs[0]]*2,'execution_bindings_refs':[forecast.execution_bindings_refs[0]]*2,'values':{'income':[forecast.values['income'][0]]*2}}))
for row in (x for x in observations if x['name']=='native_K3_replica'):
 fref=ArtifactRef(artifact_id=row['forecast_ref'],kind='scientist.backtest.native_forecast',media_type='application/json')
 rref=ArtifactRef(artifact_id=row['request_ref'],kind='scientist.backtest.native_forecast_request',media_type='application/json')
 positive,req=load_native_forecast(FileSystemCAS(store.root),fref,rref)
 assert positive.values=={'income':[1.5,1.0]}
 print(json.dumps({'name':'genuine_K3_fixed_read','run_id':req.run_id,'seed':req.seed,'forecast_ref':row['forecast_ref'],'values':positive.values}),flush=True)

(root/'order-falsifiers-removal.json').write_text(json.dumps(records,indent=2,sort_keys=True)+'\n')
assert all(not r['accepted'] for r in records), 'Persisted native temporal chain accepted structural substitution'
