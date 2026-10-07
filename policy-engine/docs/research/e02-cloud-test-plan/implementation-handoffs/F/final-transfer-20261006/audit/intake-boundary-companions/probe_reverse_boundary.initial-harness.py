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
print(json.dumps({'source_sha':'6321dc33476b0fad24d97ebb140c373608d30019','rows':rows,'classification':'Default canonical method recognizes known reverse direction; static Scientist node accepts only declaredDAG canonicalTAIL-ARROW input and intentionally refuses noncanonical reverse representation. No claim allknownresolved node inputs supported; missing generalnormalizedintake positive remains B214limited, protected broader B218limited.'},ensure_ascii=False,indent=2))
assert rows[0]['default_method_edges']==[('Y','X','tail','arrow')]
assert rows[0]['node_status']=='fail'
assert rows[1]['node_status']=='fail'
assert rows[2]['node_status']=='ok' and rows[2]['actual_fresh_edges']==[('Y','X','tail','arrow')]
