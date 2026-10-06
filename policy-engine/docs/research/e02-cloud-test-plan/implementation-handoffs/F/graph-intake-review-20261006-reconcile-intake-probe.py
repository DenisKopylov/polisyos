import json,logging,pathlib
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.artifacts.manifest import SchemaInfo,ArtifactRef
from polisyos.core.canon import CanonSpec,from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalGraphModel,load_causal_graph_model
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_METHOD_RESULT_REF,ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
store=FileSystemCAS(pathlib.Path('/workspace/e02-F-20261006-receipts/cau/reconcile-intake-cas'))
registry=build_default_registry_bundle(store).bundle_ref
run=RunContext.start(store=store,registry_bundle=registry,run_id='narrow-intake-independent')
ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger('narrow-intake-independent'))
MethodRegistry.get_instance().register(ReconcileCausalGraph,override=True)
def job(edge):
 graph=CausalGraphModel.model_validate({'graph_type':'dag','nodes':['X','Y'],'edges':[{'src':edge[0],'dst':edge[1],'data_confidence':.9,'combined_confidence':.9,'sources':['data']}]})
 request=GraphReconciliationData(data_graph=graph)
 source=store.put_json(request.model_dump(mode='json'),PutOptions(kind='tests.synthetic.graph_reconciliation_input',media_type='application/json',schema=SchemaInfo(name='tests.GraphReconciliationData',version='1.0')),canon_spec=CanonSpec(forbid_floats=False))
 result=run_job(JobSpec(job_kind='method',method_fqn=ReconcileCausalGraph.signature.fqn,input_refs={'graph_reconciliation_data':source},seed=23),cas_root=store.root,method_state=request)
 assert not result.issues and result.method_result_ref is not None,result.issues
 return graph,source,result
old,old_source,old_job=job(('X','Y'))
state=ExperimentState(run_id=run.run_id,artifacts_index={ARTIFACT_CAUSAL_METHOD_RESULT_REF:old_job.method_result_ref})
positive=ReconcileCausalGraphNode().execute(ctx,state);assert positive.status=='ok',positive.error
ref=positive.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
fresh=load_causal_graph_model(FileSystemCAS(store.root),ref);assert [(e.src,e.dst) for e in fresh.edges]==[('X','Y')]
manifest=store.get_manifest(ref);assert any(i.artifact_id==old_job.method_result_ref.artifact_id and i.role=='data_graph' for i in manifest.inputs)
new,new_source,new_job=job(('Y','X'))
changed=positive.state.model_copy(deep=True);changed.artifacts_index[ARTIFACT_CAUSAL_METHOD_RESULT_REF]=new_job.method_result_ref
negative=ReconcileCausalGraphNode().execute(ctx,changed)
negative_graph=load_causal_graph_model(FileSystemCAS(store.root),negative.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF])
missing=ArtifactRef.model_validate({'artifact_id':'sha256:'+'f'*64,'kind':'ir.causal_graph_model','media_type':'application/json'})
missing_state=ExperimentState(run_id=run.run_id,artifacts_index={ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF:missing})
missing_outcome=ReconcileCausalGraphNode().execute(ctx,missing_state)
result={'scope':'Known synthetic graph, real registered job -> CAS method payload -> existing node -> actual persisted fresh graph reader. No real-data or authority claim.', 'source':{'old':old_source.model_dump(mode='json'),'new':new_source.model_dump(mode='json')},'producer':{'fqn':ReconcileCausalGraph.signature.fqn,'old_method_result':old_job.method_result_ref.model_dump(mode='json'),'new_method_result':new_job.method_result_ref.model_dump(mode='json')},'positive':{'node_status':positive.status,'fresh_edges':[(e.src,e.dst) for e in fresh.edges],'actual_data_graph_manifest_input':True},'changed_source_control':{'node_status':negative.status,'requested_actual_source_edges':[(e.src,e.dst) for e in new.edges],'consumed_cached_edges':[(e.src,e.dst) for e in negative_graph.edges],'same_cached_ref':negative.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]==ref},'missing_ref_control':{'artifact_bytes_exist':store.contains(missing.artifact_id),'node_status':missing_outcome.status},'interpretation':'Observed presence-only cache admission; no downstream protected policy promotion measured. Source-aware cache invalidation and ref verification remain C/A/G consumer lifecycle dependencies.'}
print(json.dumps(result,indent=2))
assert negative.status=='ok' and negative_graph.edges[0].src=='X'
assert missing_outcome.status=='ok' and not store.contains(missing.artifact_id)
