import os,runpy,logging,json,pathlib,copy,numpy as np
root=pathlib.Path.cwd();scratch=pathlib.Path('/workspace/e02-F-20261006-receipts/cau/scm-consumer-binding')
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
os.environ['POLISYOS_DOWHY_WORKER_PYTHON']=str(bridge._worker_directory()/'.venv/bin/python')
ns=runpy.run_path(str(root/'tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py'))
store,source,data,model,_=ns['_fit_real'](scratch/'cas',400)
from polisyos.ir.analytics.structural_causal_model import persist_structural_causal_model_spec
from polisyos.ir.analytics.causal_queries import CausalQueryResult,load_causal_query_result
from polisyos.ir.registry.refs import CausalQueryResultRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_QUERY_RESULT_REF
import polisyos.scientist.nodes.builtins.causal.run_causal_queries as owner
from polisyos.core.canon import from_canonical_bytes
ref=persist_structural_causal_model_spec(store,model);registry=build_default_registry_bundle(store).bundle_ref
run=RunContext.start(store=store,registry_bundle=registry,run_id='independent-scm-binding');ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger('independent-scm-binding'))
state=ExperimentState(run_id='independent-scm-binding',params={'random_seed':23,'structural_causal_model_ref':ref.model_dump(mode='json'),'causal_query':ns['_contrast']().model_dump(mode='json')})
positive=owner.RunCausalQueriesNode().execute(ctx,state);assert positive.status=='ok',positive.error
original_job=owner.run_job;record={}
def actual_job_then_corrupt_peer(*args,**kwargs):
 result=original_job(*args,**kwargs);assert not result.issues
 actual=CausalQueryResult.model_validate(result.final_state['query_result']);record['genuine_job_point']=actual.result_mean
 payload=from_canonical_bytes(store.get_bytes(result.method_result_ref));record['real_method_artifact_point']=payload['query_result']['result_mean']
 record['real_method_result_ref']=result.method_result_ref.model_dump(mode='json')
 altered=actual.model_copy(update={'result_mean':actual.result_mean+5.,'result_ci':(actual.result_mean+5.,actual.result_mean+5.)})
 # All actual source/ref/backend/result-kind markers, declared contrast and real draw
 # distribution stay intact; corrupt only the peer summary, not the genuine CAS job.
 result.final_state['query_result']=altered
 return result
owner.run_job=actual_job_then_corrupt_peer
negative=owner.RunCausalQueriesNode().execute(ctx,state)
record.update({'producer':'actual registered GCM job on genuine source-bound DoWhy0.14 fit','positive_node_status':positive.status,'negative_node_status':negative.status,'negative_error':str(negative.error),'same_source_and_worker_markers':True,'actual_method_result_artifact_unchanged':True})
if negative.status=='ok':
 persisted=load_causal_query_result(store,CausalQueryResultRef.model_validate(negative.state.artifacts_index[ARTIFACT_CAUSAL_QUERY_RESULT_REF].model_dump(mode='json')))
 record.update({'persisted_corrupt_point':persisted.result_mean,'actual_draw_mean':float(np.mean(persisted.result_distribution)),'gating':persisted.to_uncertainty_envelope().gate_eligible})
print(json.dumps(record,indent=2))
assert negative.status=='fail','Actual Scientist consumer persisted peer summary inconsistent with genuine job artifact and actual draws'
