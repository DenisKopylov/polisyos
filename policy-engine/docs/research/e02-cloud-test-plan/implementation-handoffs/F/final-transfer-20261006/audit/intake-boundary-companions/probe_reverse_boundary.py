"""Actual known reverse direction at default vs canonical static node profile."""
import sys,json,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('independent_controls',Path(__file__).with_name('test_independent_intake.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ctx=m.context(Path(__file__).with_name('reverse-boundary-cas'));rows=[]
for kind in ['dag','pag']:
 row={'input_graph_type':kind,'input_marks':['arrow','tail'],'source_coordinates':['X','Y']}
 try:
  g=m.graph(graph_type=kind,marks=('arrow','tail'));row['IR_model_admission']='accepted'
  result=m.ReconcileCausalGraph.pure_step(m.GraphReconciliationData(data_graph=g),{})['reconciled_graph'];row['default_method_edges']=[(e.src,e.dst,e.mark_src.value,e.mark_dst.value) for e in result.edges]
  outcome=m.execute(ctx,m.state(g));row.update(node_status=outcome.status,node_error=None if outcome.error is None else outcome.error.model_dump(mode='json'))
 except Exception as e:row.update(IR_or_method_error=type(e).__name__+': '+str(e))
 rows.append(row)
canonical=m.execute(ctx,m.state(m.graph(reverse=True)));out=m.read(ctx,canonical);rows.append({'equivalent_canonical_forward_coordinate_graph':['Y','X'],'node_status':canonical.status,'actual_fresh_edges':[(e.src,e.dst,e.mark_src.value,e.mark_dst.value) for e in out.edges]})

known=m.graph(graph_type='pag',marks=('arrow','tail'));request=m.GraphReconciliationData(data_graph=known)
m.MethodRegistry.get_instance().register(m.ReconcileCausalGraph,override=True)
source=ctx.store.put_json(request.model_dump(mode='json'),m.PutOptions(kind='tests.synthetic.known_reverse_graph',media_type='application/json',schema=m.SchemaInfo(name='tests.GraphInput',version='1.0')),canon_spec=m.CanonSpec(forbid_floats=False))
job=m.run_job(m.JobSpec(job_kind='method',method_fqn=m.ReconcileCausalGraph.signature.fqn,input_refs={'graph_reconciliation_data':source},seed=37),cas_root=ctx.store.root,method_state=request)
assert not job.issues and job.method_result_ref is not None,job.issues
from_producer=m.execute(ctx,m.ExperimentState(run_id='independent-intake',artifacts_index={m.METHOD:job.method_result_ref}));fresh=m.read(ctx,from_producer)
rows.append({'registered_default_method_source_graph_type':'pag','registered_default_method_source_marks':['arrow','tail'],'producer_fqn':m.ReconcileCausalGraph.signature.fqn,'source_ref':source.model_dump(mode='json'),'method_result_ref':job.method_result_ref.model_dump(mode='json'),'node_status':from_producer.status,'fresh_edges':[(e.src,e.dst,e.mark_src.value,e.mark_dst.value) for e in fresh.edges],'original_endpoint_origin':fresh.edges[0].metadata['data_endpoint_origin'],'declared_scope':'Actual default producer normalizes known direction before canonical-DAG static Node; direct PAG input remains refused.'})
assert rows[3]['node_status']=='ok' and rows[3]['fresh_edges']==[('Y','X','tail','arrow')]

print(json.dumps({'source_sha':'6321dc33476b0fad24d97ebb140c373608d30019','rows':rows,'classification':'Default canonical method recognizes known reverse direction; static Scientist node accepts only declaredDAG canonicalTAIL-ARROW input and intentionally refuses noncanonical reverse representation. No claim allknownresolved node inputs supported; missing generalnormalizedintake positive remains B214limited, protected broader B218limited.'},ensure_ascii=False,indent=2))
assert 'DAG requires oriented edges' in rows[0]['IR_or_method_error']
assert rows[1]['default_method_edges']==[('Y','X','tail','arrow')]
assert rows[1]['node_status']=='fail'
assert rows[2]['node_status']=='ok' and rows[2]['actual_fresh_edges']==[('Y','X','tail','arrow')]
