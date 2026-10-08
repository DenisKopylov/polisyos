import dataclasses, hashlib, json, pathlib, sys, tomllib
root=pathlib.Path('/dev/shm/e02-orch03-20261008/c08')
sys.path[:0]=[str(root/'policy-engine/src'),str(root/'policy-engine')]
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal_graph import CausalEdge,CausalGraphModel,GraphType
from polisyos.foundry.methods.catalog.causal import _partial_graph_queries
from polisyos.foundry.methods.catalog.causal._id_contracts import IdentificationStatus
assert pathlib.Path(_partial_graph_queries.__file__).is_relative_to(root)
pe=root/'policy-engine'
fragment_path=pe/'release-fragments/unreleased/2026-10-08-c08-partial-graph-query.toml'
fragment=tomllib.loads(fragment_path.read_text());fragment['__path__']=str(fragment_path.relative_to(pe))
policy=tomllib.loads((pe/'architecture/gates/compatibility_release.toml').read_text())
errors,findings=_validate_fragments(pe,policy,[fragment],breaking_classes=())
basepolicy=tomllib.loads((pe/'ops/release/release-fragment-policy.toml').read_text())['release_fragments']
assert all(key in fragment and fragment[key] for key in basepolicy['required_fields'])
assert fragment['type'] in basepolicy['allowed_types']
paths=[*fragment['evidence'],*fragment['migration_docs'],*fragment['runbook_docs']]
assert all((pe/path).is_file() for path in paths)
assert not errors,errors
rows=[]
for profile,edges,expected in [
(GraphType.DAG,[CausalEdge(src='X',dst='Y')],IdentificationStatus.IDENTIFIED),
(GraphType.ADMG,[CausalEdge(src='X',dst='Y')],IdentificationStatus.IDENTIFIED),
(GraphType.ADMG,[CausalEdge(src='X',dst='Y'),CausalEdge(src='X',dst='Y',mark_src='arrow')],IdentificationStatus.HEDGE_FOUND),
]:
 graph=CausalGraphModel(graph_type=profile,nodes=['X','Y'],edges=edges)
 result=CausalEngine().identify('X','Y',graph,dataset_ref='declared-observed-law')
 if expected is IdentificationStatus.HEDGE_FOUND:
  assert type(result).__name__ == 'NegativeCertificate'
  assert result.blocking_type == 'hedge_structure'
  state='typed_negative_certificate:hedge_structure'
 else:
  assert result.status is expected,(profile,result.status)
  assert 'partial_graph_query' not in result.metadata
  state=result.status.value
 rows.append({'graph_type':profile.value,'edge_marks':[(e.mark_src.value,e.mark_dst.value) for e in edges],'status':state,'existing_branch_preserved':True})
print(json.dumps({'source':'2dd8339c210caf973586f7ddec69b6b0a48f1df7','tree':'72c482aa7d731f1adfaf703dcd6708fcccff40cd','import':str(_partial_graph_queries.__file__),'release_fragment':fragment,'release_policy_errors':[dataclasses.asdict(x) for x in errors],'release_policy_findings':[dataclasses.asdict(x) for x in findings],'referenced_paths':paths,'existing_static_profiles':rows,'status':'PASS','scope':'one new internal additive fragment and three affected engine branch controls; not global release gate or installed composition'},indent=2))
