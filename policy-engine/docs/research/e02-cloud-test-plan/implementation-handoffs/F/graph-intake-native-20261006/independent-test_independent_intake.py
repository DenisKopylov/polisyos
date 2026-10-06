"""Independent finite graph/CAS predicates, without constructing a fake backend."""
import logging
from hashlib import sha256
import pytest
from polisyos.core.artifacts.manifest import ArtifactRef,SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.canon import CanonSpec,from_canonical_bytes,to_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.protocols import GraphReconciliationData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_graph import CausalGraphModel,load_causal_graph_model,persist_causal_graph_model
from polisyos.ir.analytics.literature import LiteratureCausalPrior,LiteratureEdgePrior,persist_literature_causal_prior
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_METHOD_RESULT_REF as METHOD,ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF as OUTPUT,ARTIFACT_LITERATURE_PRIOR_REF as PRIOR
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

def graph(*,reverse=False,graph_type='dag',marks=('tail','arrow'),lag=None):
 return CausalGraphModel.model_validate({'graph_type':graph_type,'nodes':['X','Y'],'edges':[{'src':'Y' if reverse else 'X','dst':'X' if reverse else 'Y','mark_src':marks[0],'mark_dst':marks[1],'lag':lag,'data_confidence':.9,'combined_confidence':.9,'sources':['data']}]})
def context(path):
 store=FileSystemCAS(path/'cas');registry=build_default_registry_bundle(store).bundle_ref
 run=RunContext.start(store=store,registry_bundle=registry,run_id='independent-intake')
 return ExecutionContext(store=store,run=run,logger=logging.getLogger('independent-intake'))
def state(g=None):return ExperimentState(run_id='independent-intake',params={'data_causal_graph':(g or graph()).model_dump(mode='json')})
def execute(ctx,s):return ReconcileCausalGraphNode().execute(ctx,s)
def read(ctx,outcome):
 assert outcome.status=='ok',outcome.error
 fresh=FileSystemCAS(ctx.store.root);ref=outcome.state.artifacts_index[OUTPUT];out=load_causal_graph_model(fresh,ref)
 request=ArtifactRef.model_validate(out.metadata['reconciliation_request_ref']);payload=from_canonical_bytes(fresh.get_bytes(request))
 assert fresh.verify(request).ok
 assert sha256(to_canonical_bytes(payload,CanonSpec(forbid_floats=False))).hexdigest()==out.metadata['reconciliation_request_sha256']
 assert any(i.artifact_id==request.artifact_id and i.role=='reconciliation_request' for i in fresh.get_manifest(ref).inputs)
 return out

def test_real_method_job_and_explicit_current_input_precedence(tmp_path):
 ctx=context(tmp_path);request=GraphReconciliationData(data_graph=graph());MethodRegistry.get_instance().register(ReconcileCausalGraph,override=True)
 source=ctx.store.put_json(request.model_dump(mode='json'),PutOptions(kind='tests.synthetic.graph_input',media_type='application/json',schema=SchemaInfo(name='tests.GraphInput',version='1.0')),canon_spec=CanonSpec(forbid_floats=False))
 actual=run_job(JobSpec(job_kind='method',method_fqn=ReconcileCausalGraph.signature.fqn,input_refs={'graph_reconciliation_data':source},seed=41),cas_root=ctx.store.root,method_state=request)
 assert not actual.issues and actual.method_result_ref is not None
 original=execute(ctx,ExperimentState(run_id='independent-intake',artifacts_index={METHOD:actual.method_result_ref}))
 assert [(e.src,e.dst) for e in read(ctx,original).edges]==[('X','Y')]
 current=original.state.model_copy(deep=True);current.params['data_causal_graph']=graph(reverse=True).model_dump(mode='json')
 assert [(e.src,e.dst) for e in read(ctx,execute(ctx,current)).edges]==[('Y','X')]
 current.params['data_causal_graph']={'invalid':True}
 assert execute(ctx,current).status=='fail' # real fallback source may not rescue explicit malformed input

@pytest.mark.parametrize('fault',['kind','schema','media_type','payload','corrupt_blob'])
def test_actual_cached_cas_binding_cannot_be_relabelled(tmp_path,fault):
 ctx=context(tmp_path);s=state()
 ref=ctx.store.put_bytes(to_canonical_bytes({'fake':True} if fault=='payload' else graph(reverse=True).model_dump(mode='json'),CanonSpec(forbid_floats=False)),PutOptions(kind='tests.fake' if fault=='kind' else 'ir.causal_graph_model',media_type='text/plain' if fault=='media_type' else 'application/json',schema=SchemaInfo(name='tests.fake' if fault=='schema' else 'ir.causal_graph_model',version='1.0')))
 if fault=='corrupt_blob':ctx.store._paths(ref.artifact_id)[0].write_bytes(b'{"coherent_shape_but_wrong_content":true}')
 s.artifacts_index[OUTPUT]=ref
 assert execute(ctx,s).status=='fail'

@pytest.mark.parametrize('fault',['kind','schema','payload','corrupt_blob'])
def test_actual_method_cas_binding_must_be_selected_and_verified(tmp_path,fault):
 ctx=context(tmp_path);payload={'reconciled_graph':graph().model_dump(mode='json')} if fault!='payload' else {'invalid':True}
 ref=ctx.store.put_json(payload,PutOptions(kind='tests.fake' if fault=='kind' else 'scientist.method_result.causal.prior',media_type='application/json',schema=SchemaInfo(name='tests.fake' if fault=='schema' else 'polisyos.scientist.MethodResult',version='0.1.0')),canon_spec=CanonSpec(forbid_floats=False))
 if fault=='corrupt_blob':ctx.store._paths(ref.artifact_id)[0].write_bytes(b'{}')
 assert execute(ctx,ExperimentState(run_id='independent-intake',artifacts_index={METHOD:ref})).status=='fail'

@pytest.mark.parametrize('change',['prior','hint','threshold','seed'])
def test_known_edges_independent_confidence_and_current_request(tmp_path,change):
 ctx=context(tmp_path);s=state();old=execute(ctx,s);a=read(ctx,old);current=old.state.model_copy(deep=True)
 if change=='prior':current.artifacts_index[PRIOR]=persist_literature_causal_prior(ctx.store,LiteratureCausalPrior(edges=[LiteratureEdgePrior(src='X',dst='Y',confidence=.8)]))
 elif change=='hint':current.params['llm_structural_hints']=[{'src':'X','dst':'Y','confidence':.9}]
 elif change=='threshold':current.params['reconciliation_min_edge_confidence']=.95
 else:current.params['random_seed']=987654
 b=read(ctx,execute(ctx,current));assert b.metadata['reconciliation_request_sha256']!=a.metadata['reconciliation_request_sha256']
 if change=='threshold':assert b.edges==[]
 else:
  assert [(e.src,e.dst) for e in b.edges]==[('X','Y')]
  expected={'prior':.98,'hint':.92,'seed':.9}[change]
  assert b.edges[0].combined_confidence==pytest.approx(expected,abs=1e-12)

@pytest.mark.parametrize('marks',[('circle','circle'),('circle','arrow'),('tail','tail'),('arrow','arrow')])
def test_partial_or_mixed_marks_cannot_be_lost_at_standalone_merge(marks):
 g=graph(graph_type='pag' if 'circle' in marks else 'admg' if marks==('arrow','arrow') else 'cpdag',marks=marks)
 with pytest.raises(ValueError,match='unresolved|mixed'):
  ReconcileCausalGraph.pure_step(GraphReconciliationData(data_graph=g),{})
 assert (g.edges[0].mark_src.value,g.edges[0].mark_dst.value)==marks

@pytest.mark.parametrize('lag',[1,2])
def test_known_temporal_default_is_preserved_but_static_cannot_admit_it(tmp_path,lag):
 g=graph(lag=lag);out=ReconcileCausalGraph.pure_step(GraphReconciliationData(data_graph=g),{})['reconciled_graph']
 assert [(e.src,e.dst,e.lag) for e in out.edges]==[('X','Y',lag)]
 persisted=context(tmp_path);ref=persist_causal_graph_model(persisted.store,out)
 assert load_causal_graph_model(FileSystemCAS(persisted.store.root),ref).edges==out.edges
 assert execute(persisted,state(g)).status=='fail'

@pytest.mark.parametrize('value',[None,1,'true',[],{}])
def test_static_profile_is_explicit_boolean(value):
 with pytest.raises(ValueError,match='boolean'):ReconcileCausalGraph.pure_step(GraphReconciliationData(data_graph=graph()),{'static_intake':value})

def test_reverse_orientation_has_original_coordinate_witness():
 g=graph(graph_type='pag',marks=('arrow','tail'));out=ReconcileCausalGraph.pure_step(GraphReconciliationData(data_graph=g),{})['reconciled_graph']
 assert [(e.src,e.dst,e.mark_src.value,e.mark_dst.value) for e in out.edges]==[('Y','X','tail','arrow')]
 assert out.edges[0].metadata['data_endpoint_origin']=={'src':'X','dst':'Y','mark_src':'arrow','mark_dst':'tail','lag':0}
 assert g.edges[0].src=='X' and g.edges[0].mark_src.value=='arrow'
