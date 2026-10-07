"""Independent current-source discriminators; candidate data, no authority seals."""
import json,logging
import pytest
from polisyos.core.artifacts import PutOptions,SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ComposeSCMFragments
from polisyos.foundry.methods.catalog.causal.protocols import FragmentCompositionData
from polisyos.ir.analytics.alignment_certification import AlignmentOverallStatus,load_alignment_report,persist_alignment_report
from polisyos.ir.analytics.causal_graph import CausalEdge,CausalGraphModel,GraphType,load_causal_graph_model,persist_causal_graph_model
from polisyos.ir.analytics.cross_graph import SCMFragment,load_scm_fragment,persist_scm_fragment,load_interface_mapping,load_composition_certificate
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_ALIGNMENT_REPORT_REF,ARTIFACT_COMPOSITION_CERTIFICATE_REF,ARTIFACT_INTERFACE_MAPPING_REF,ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

def case(tmp):
 store=FileSystemCAS(tmp/'cas'); registry=build_default_registry_bundle(store).bundle_ref
 ctx=ExecutionContext(store=store,run=RunContext.start(store=store,registry_bundle=registry,run_id='independent-current-source'),logger=logging.getLogger('independent-current-source'))
 refs=[]
 for name,nodes,edge,role in [('a',['X','E'],('X','E'),'out'),('b',['E','Y'],('E','Y'),'in')]:
  gr=persist_causal_graph_model(store,CausalGraphModel(graph_type=GraphType.DAG,nodes=nodes,edges=[CausalEdge(src=edge[0],dst=edge[1])]))
  frag=SCMFragment(fragment_id=name,graph_ref=str(gr.artifact_id),semantic_namespace='synthetic.example',interface_variables=['E'],exposed_outputs=['E'] if role=='out' else [],exposed_inputs=['E'] if role=='in' else [],variable_definitions={'E':'Employment rate'},variable_units={'E':'percent'})
  refs.append(persist_scm_fragment(store,frag))
 initial=ReconcileCausalGraphNode().execute(ctx,ExperimentState(run_id='independent-current-source',params={'scm_fragment_refs':[str(r.artifact_id) for r in refs]}))
 assert initial.status=='ok' and ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in initial.state.artifacts_index
 state=initial.state.model_copy(deep=True);state.params.pop('scm_fragment_refs')
 state.params['query_preservation_queries']=[{'query_type':'interventional','x':['E'],'y':['Y'],'z':[]}]
 return ctx,state,refs

def test_real_query_only_replay_positive(tmp_path):
 ctx,state,refs=case(tmp_path); outcome=ReconcileCausalGraphNode().execute(ctx,state)
 assert outcome.status=='ok',outcome.error
 assert outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]==state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]

def test_current_incompatible_alignment_is_not_preserved_by_graph_only_comparison(tmp_path):
 ctx,state,refs=case(tmp_path);report=load_alignment_report(ctx.store,state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF])
 report=report.model_copy(update={'overall_status':AlignmentOverallStatus.INCOMPATIBLE,'incompatible_pairs':[('a:E','b:E')]})
 state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF]=persist_alignment_report(ctx.store,report)
 old=load_composition_certificate(ctx.store,state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]);mapping=load_interface_mapping(ctx.store,state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF])
 fragments=[load_scm_fragment(ctx.store,r) for r in refs]; graphs={f.fragment_id:load_causal_graph_model(ctx.store,persist_causal_graph_model(ctx.store,CausalGraphModel.model_validate(ctx.store.get_json(f.graph_ref)))) for f in []}
 # Resolve actual persisted source graphs; comparison uses the canonical producer.
 from polisyos.ir.registry.refs import CausalGraphModelRef
 graphs={f.fragment_id:load_causal_graph_model(ctx.store,CausalGraphModelRef.model_validate({'artifact_id':f.graph_ref})) for f in fragments}
 reproduced=ComposeSCMFragments.pure_step(FragmentCompositionData(fragments=fragments,fragment_graphs=graphs,alignment_report=report,interface_mapping=mapping,source_fragment_refs=dict(old.source_fragment_refs),source_fragment_graph_refs=dict(old.source_fragment_graph_refs)),{})
 assert reproduced['composition_certificate'].status=='broken'
 assert reproduced['composed_graph']==load_causal_graph_model(ctx.store,state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF])
 outcome=ReconcileCausalGraphNode().execute(ctx,state)
 print(json.dumps({'actual_node_status':outcome.status,'canonical_current_certificate_status':reproduced['composition_certificate'].status,'actual_reused_certificate_status':load_composition_certificate(ctx.store,outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]).status if outcome.status=='ok' else None}))
 assert outcome.status=='fail', 'current canonical certificate is broken despite unchanged graph geometry'

def test_supplied_fragment_ref_checks_actual_manifest_kind(tmp_path):
 ctx,state,refs=case(tmp_path);body=load_scm_fragment(ctx.store,refs[0]).model_dump(mode='json')
 bad=ctx.store.put_json(body,PutOptions(kind='tests.wrong_fragment_kind',media_type='application/json',schema=SchemaInfo(name='ir.scm_fragment',version='1.0')),canon_spec=CanonSpec(forbid_floats=False))
 state.params.pop('query_preservation_queries');state.params['scm_fragment_refs']=[str(bad.artifact_id),str(refs[1].artifact_id)]
 outcome=ReconcileCausalGraphNode().execute(ctx,state)
 print(json.dumps({'actual_kind':ctx.store.get_manifest(bad).kind,'node_status':outcome.status,'artifacts':len(outcome.artifacts)}))
 assert outcome.status=='fail','valid-shaped fragment body is not actual typed source-manifest admission'
