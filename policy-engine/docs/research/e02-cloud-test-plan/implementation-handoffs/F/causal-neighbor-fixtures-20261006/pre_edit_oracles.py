"""Read-only intent discriminator; actual maintained consumers and independent oracles."""
import json
from itertools import combinations
from fractions import Fraction as F
from polisyos.ir.analytics.causal_graph import CausalGraphModel,CausalEdge,EdgeMark,GraphType
from polisyos.ir.analytics.estimand import StochasticPolicy,DistributionRef,DistributionDomain,EstimandAST,ProductNode,SumNode
from polisyos.foundry.methods.catalog.causal.admg_ops import m_separation,remove_outgoing_edges
from polisyos.foundry.methods.catalog.causal.id_engine import sid_algorithm,conditional_intervention_id,IdentificationStatus
from polisyos.foundry.methods.catalog.causal.amn import build_amn,amn_d_separation
from polisyos.foundry.methods.catalog.causal.do_calculus import rewrite_estimand
from polisyos.foundry.methods.catalog.causal.estimand_compiler import compile_estimand

def graph(nodes,directed=(),bidirected=(),metadata=None):
 return CausalGraphModel(graph_type=GraphType.ADMG,nodes=list(nodes),edges=[CausalEdge(src=a,dst=b) for a,b in directed]+[CausalEdge(src=a,dst=b,mark_src=EdgeMark.ARROW) for a,b in bidirected],metadata=metadata or {})
def oracle(edges,x,y,z):
 parents={}
 for a,b in edges:parents.setdefault(b,set()).add(a)
 anc={x,y,*z};pending=list(anc)
 while pending:
  for p in parents.get(pending.pop(),()):
   if p not in anc:anc.add(p);pending.append(p)
 moral={n:set() for n in anc}
 for n in anc:
  family=parents.get(n,set())&anc
  for p in family:moral[p].add(n);moral[n].add(p)
  for a,b in combinations(family,2):moral[a].add(b);moral[b].add(a)
 seen=set(z);pending=[x]
 while pending:
  n=pending.pop()
  if n in seen:continue
  if n==y:return False
  seen.add(n);pending.extend(moral[n]-seen)
 return True
bow=graph(['X','Y'],[('X','Y')],[('X','Y')]);collider=graph(['X','Y','U'],[('X','Y')],[('U','X'),('U','Y')]);records=[]
for name,g,latent,expected in [('bow',bow,[('L','X'),('L','Y')],False),('old_observed_U_collider',collider,[('L1','X'),('L1','U'),('L2','Y'),('L2','U')],True)]:
 for z in [frozenset(),frozenset({'U'})] if 'U' in g.nodes else [frozenset()]:
  ref=oracle(latent,'X','Y',z);actual=m_separation(remove_outgoing_edges(g,frozenset({'X'})),frozenset({'X'}),frozenset({'Y'}),z);assert actual==ref
  if not z:assert actual==expected
  records.append({'graph':name,'condition':sorted(z),'latent_dag_separated':ref,'native_separated':actual})
 for consumer,r in [('sid',sid_algorithm(treatment=frozenset({'X'}),outcome=frozenset({'Y'}),graph=g,policy=StochasticPolicy(policy_type='soft'))),('conditional',conditional_intervention_id(treatment=frozenset({'X'}),outcome=frozenset({'Y'}),condition_vars=frozenset(),graph=g))]:
  assert (r.status==IdentificationStatus.HEDGE_FOUND)==(name=='bow');records.append({'graph':name,'consumer':consumer,'status':r.status.value,'proof_rules':[p.rule_name for p in r.proof_steps]})
# X=U, Y=beta*X+(1-beta)*U+E: same nondegenerate observed N(0, [[1,1],[1,2]]), distinct do means.
assert [F(1,2)+(1-F(1,2)),F(3,2)+(1-F(3,2))]==[1,1]
records.append({'independent_nonidentification_oracle':{'observed_covariance':[[1,1],[1,2]],'observed_determinant':1,'two_nonzero_structural_beta_gamma_pairs':[['1/2','1/2'],['3/2','-1/2']],'do_X_1_Y_mean':['1/2','3/2']}})
chain=graph(['U_shared','X','Y'],[('U_shared','X'),('X','Y')],metadata={'shared_exogenous':['U_shared']});amn,meta=build_amn(chain,{'w0':{'X':0.},'w1':{'X':1.}})
latent=[('U_shared','X__w0'),('X__w0','Y__w0'),('U_shared','X__w1'),('X__w1','Y__w1'),('B','X__w0'),('B','X__w1')]
for z,expected in [(frozenset(),False),(frozenset({'X__w1'}),True)]:
 ref=oracle(latent,'X__w0','Y__w1',z);actual=amn_d_separation(amn,meta,frozenset({'X__w0'}),frozenset({'Y__w1'}),z);assert ref==actual==expected;records.append({'AMN_chain_condition':sorted(z),'oracle':ref,'native':actual})
assert not amn_d_separation(amn,meta,frozenset({'X__w0'}),frozenset({'X__w1'}),frozenset({'X__w1'}))
# U,B,E0,E1,E2 independent unit Gaussian: X0=U+B+E0, X1=U+B+E1, Y1=X1+E2.
assert F(2)-F(2)*F(3)/F(3)==0
records.append({'independent_AMN_covariance':{'Cov(X0,Y1)':2,'Cov(X0,X1)':2,'Var(X1)':3,'Cov(X1,Y1)':3,'conditional_covariance':0,'scope':'derived AMN graph, not numerical intervention validation'}})
source=graph(['T','Y','Z'],[('T','Y')]);leaf=DistributionRef(domain=DistributionDomain.SOURCE,variables=('Y',),conditioning=('T','Z'));cov=DistributionRef(domain=DistributionDomain.SOURCE,variables=('Z',));ast=EstimandAST(query_str='P(Y|do(T))',outcome='Y',treatment='T',root=SumNode(summation_vars=('Z',),operand=ProductNode(factors=(leaf,cov))),all_variables=('Y','T','Z'),identification_method='backdoor')
rewritten,steps=rewrite_estimand(ast,source); assert rewritten.root.operand.factors[0].conditioning==('T',);assert len(steps)==1 and steps[0].rule_name=='RULE1' and steps[0].variables_affected==('Z',)
_,compiled=compile_estimand(ast,run_id='oracle',n_obs=200,causal_graph=source);assert compiled.proof_steps==tuple(steps);assert source.model_dump()['edges'][0]['src']=='T';records.append({'compiler_actual_rule_walk':{'rewrite_rules':[p.rule_name for p in steps],'variables':[p.variables_affected for p in steps],'compiled_rules':[p.rule_name for p in compiled.proof_steps],'executor_nodes':[n.method_fqn for n in compiled.nodes]}})
print(json.dumps({'check':'PASS','controls':records},indent=2))
