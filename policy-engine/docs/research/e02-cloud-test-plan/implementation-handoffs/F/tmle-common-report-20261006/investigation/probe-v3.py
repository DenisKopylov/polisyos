"""Actual existing consumer probes. No admission issuer, scheduler or source writes."""
from pathlib import Path
import asyncio, dataclasses, hashlib, json, logging, sys
import numpy as np
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.common.serialization import to_python_data
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.ir.analytics.causal import CausalMethod
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
OUT=Path('/tmp/e02-F-continuation-20261006/tmle-bridge-investigation')
mode=sys.argv[1]
rng=np.random.default_rng(73);n=120
w=rng.choice([-1.,1.],size=n);t=rng.binomial(1,.5,size=n).astype(float)
y=rng.binomial(1,.25+.1*w+.3*t).astype(float)
x=w[:,None]
params=dict(propensity_backend='logistic',outcome_backend='linear',calibration_mode='none',outcome_scaling='raw',crossfit_folds=3,n_repeats=2,random_seed=18,ci_mode='wald',inference_profile='regular_iid',coverage_guard='off',__disable_shared_nuisance_cache=True)
data=HTEObservationalData(outcome=y,treatment=t,covariates=x,feature_names=['w'],sample_ids=np.arange(n))
fqn=TMLEEstimator.signature.fqn
store=FileSystemCAS(OUT/(mode+'-cas'))
source=store.put_json(data.model_dump(mode='json'),PutOptions(kind='ir.observational_data',media_type='application/json'),canon_spec=CanonSpec(forbid_floats=False))
if mode in {'job','jobdefault'}:
 result=run_job(JobSpec(job_kind='method',method_fqn=fqn,method_params=(params if mode=='job' else {}),seed=18,input_refs={'causal_observational_data':source}),cas_root=store.root,method_state={'X':x,'treatment':t,'outcome':y})
 if mode=='job':
  assert len(result.issues)==1 and 'Unknown parameters' in result.issues[0]['message'] and 'inference_profile' in result.issues[0]['message'],result.issues
  print(json.dumps(dict(probe='actual_configured_MethodJob_parameter_refusal',fqn=fqn,issues=result.issues,signature_parameters=[x.name for x in TMLEEstimator.signature.parameters],native_fits_executed=0,claim='genuine current public parameter ABI gap')));raise SystemExit(0)
 assert not result.issues,result.issues
 saved=from_canonical_bytes(FileSystemCAS(store.root).get_bytes(result.method_result_ref))
 assert saved==to_python_data(result.final_state,sort_keys=True)
 assert 'result' in saved and 'report' not in saved and 'envelope' not in saved
 payload=saved['result'];assert payload['gate_eligible'] is False
 split=payload['nuisance_diagnostics']['split_manifest']
 assert len(split)==3 and all(len(row['folds'])==5 for row in split)
 assert all(sorted(i for fold in row['folds'] for i in fold['test_indices'])==list(range(n)) for row in split)
 print(json.dumps(dict(probe='actual_native_MethodJob_and_fresh_CAS_reader',fqn=fqn,output_keys=sorted(saved),result_status=payload['status'],ci=[payload['ci_lower'],payload['ci_upper']],ate=payload['ate'],report_absent=True,result_ref=result.method_result_ref.model_dump(mode='json'),evidence_ref=result.method_evidence_ref.model_dump(mode='json'),issues=result.issues,warnings=result.warnings,folds=5,repeats=3,native_tasks=15,execution_policy=payload['nuisance_diagnostics']['execution_policy'],claim='numerical synthetic producer only; not common admitted node/pool budget/identification')))
elif mode=='input':
 bundle=build_default_registry_bundle(store).bundle_ref
 run=RunContext.start(store=store,registry_bundle=bundle,run_id='input-probe')
 ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger('tmle.input.probe'))
 state=ExperimentState(run_id='input-probe',observational_data_ref=source,causal_method_fqn=fqn,causal_method_params=params,inputs={'registry_bundle_ref':bundle})
 try:owner._load_observational_data(ctx,state,fqn)
 except ValueError as exc:load_error=str(exc)
 else:raise AssertionError('TMLE source unexpectedly accepted by common input loader')
 try:TMLEEstimator.pure_step(data,params)
 except TypeError as exc:typed_error=str(exc)
 else:raise AssertionError('existing TMLE unexpectedly accepts typed HTE')
 assert getattr(HTEObservationalData,'contract_id',None) is None
 assert 'tmle' not in [method.value for method in CausalMethod]
 blockers=owner._causal_evaluation_safety_blockers(ctx,state,evaluator_owner_id=owner.RunCausalEvaluationNode().spec.metadata.component_id)
 assert blockers==('polisyos.eval_safety.execution_context_missing@1.0.0',),blockers
 print(json.dumps(dict(probe='actual_input_loader_and_authority_refusals',fqn=fqn,hte_typed_valid=True,hte_contract_id=None,common_load_error=load_error,typed_direct_error=typed_error,tmle_enum_absent=True,safety_blockers=blockers,claim='all refusals genuine current existing consumer calls; no fake admission positive')))
elif mode=='pool':
 from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool
 from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome,serialize_state
 from polisyos.scientist.orchestration.engine.runner.worker_pool import NodeTask
 bundle=build_default_registry_bundle(store).bundle_ref
 node=owner.RunCausalEvaluationNode()
 async def run():
  pool=LocalWorkerPool(max_workers=1)
  try:
   futures=[]
   for i in range(2):
    state=ExperimentState(run_id=f'tmle-real-common-{i}',observational_data_ref=source,causal_method_fqn=fqn,causal_method_params=params,inputs={'registry_bundle_ref':bundle})
    futures.append(await pool.submit(NodeTask(node_id=str(node.spec.metadata.component_id),alias=f'causal-{i}',params={},state_bytes=serialize_state(state),trace_carrier={},context_meta={'run_id':state.run_id,'store_backend':'filesystem','store_root':str(store.root),'registry_bundle_ref':bundle.model_dump(mode='json')})))
   outcomes=[deserialize_outcome(x) for x in await asyncio.wait_for(asyncio.gather(*futures),timeout=60)]
   for result in outcomes:
    assert result.status=='fail',result
    assert result.error.details['blocker_codes']==['polisyos.eval_safety.execution_context_missing@1.0.0'],result.error
   print(json.dumps(dict(probe='real_registered_common_node_via_existing_LocalWorkerPool',configured_budget=1,submitted=2,results=[dict(status=o.status,error=o.error.model_dump(mode='json')) for o in outcomes],registered_node=str(node.spec.metadata.component_id),source_ref=source.model_dump(mode='json'),native_fits_executed=0,claim='actual authority carrier refusal; not numerical/pool budget acceptance positive')))
  finally:await pool.shutdown()
 asyncio.run(run())
else:raise SystemExit('unknown probe')
