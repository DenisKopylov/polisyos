from fractions import Fraction as Q
import json
from polisyos.ir.analytics.causal_graph import CausalGraphModel,CausalEdge,GraphType,EdgeMark
from polisyos.ir.analytics.estimand import StochasticPolicy
from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm,conditional_intervention_id
from polisyos.foundry.methods.catalog.causal.admg_ops import m_separation,remove_outgoing_edges
pairs=[(Q(9,4),Q(-5,4)),(Q(-2),Q(3))]
covs=[((Q(1),b+g),(b+g,(b+g)**2+1)) for b,g in pairs]
assert covs[0]==covs[1]==((1,1),(1,2))
assert covs[0][0][0]*covs[0][1][1]-covs[0][0][1]**2==1
assert pairs[0][0]!=pairs[1][0]
bow=CausalGraphModel(graph_type=GraphType.ADMG,nodes=['X','Y'],edges=[CausalEdge(src='X',dst='Y'),CausalEdge(src='X',dst='Y',mark_src=EdgeMark.ARROW)])
results=[]
for f in ['SID','conditional-ID']:
 kw=dict(treatment=frozenset({'X'}),outcome=frozenset({'Y'}),graph=bow)
 result=sid_algorithm(**kw,policy=StochasticPolicy(policy_type='soft')) if f=='SID' else conditional_intervention_id(**kw,condition_vars=frozenset())
 assert result.status.value=='hedge_found', result.status
 assert result.hedge_certificate is not None and [s.rule_name for s in result.proof_steps]==['HEDGE']
 results.append({'consumer':f,'status':result.status.value,'proof':[s.rule_name for s in result.proof_steps]})
collider=CausalGraphModel(graph_type=GraphType.ADMG,nodes=['X','U','Y','D'],edges=[CausalEdge(src='X',dst='Y'),CausalEdge(src='X',dst='U',mark_src=EdgeMark.ARROW),CausalEdge(src='Y',dst='U',mark_src=EdgeMark.ARROW),CausalEdge(src='U',dst='D')])
no_effect=remove_outgoing_edges(collider,frozenset({'X'}))
truths=[]
for z,want in [(frozenset(),True),(frozenset({'U'}),False),(frozenset({'D'}),False)]:
 actual=m_separation(no_effect,frozenset({'X'}),frozenset({'Y'}),z)
 assert actual is want,(z,actual,want)
 truths.append({'condition':sorted(z),'separated':actual})
cpdag=CausalGraphModel(graph_type=GraphType.CPDAG,nodes=['Y','Z'],edges=[CausalEdge(src='Y',dst='Z',mark_dst=EdgeMark.TAIL)])
try:m_separation(cpdag,frozenset({'Y'}),frozenset({'Z'}),frozenset())
except ValueError as e:refusal=str(e)
else:raise AssertionError('Unresolved Y--Z profile must refuse before a positive separation')
print(json.dumps({'check':'PASS','distinct_bow_do_means':[str(b) for b,g in pairs],'same_observed_covariance':[[str(v) for v in row] for row in covs[0]],'actual_identification':results,'collider_conditioned_descendant_truths':truths,'CPDAG_refusal':refusal},sort_keys=True))
