"""Independent C08 finite-family and exact-law immutable-candidate review."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from collections import Counter
from fractions import Fraction
from itertools import combinations, product

from completion_oracle import completion_family, truncated_binary_probability, chain_joint
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal import _partial_graph_queries as candidate
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal._id_contracts import IdentificationStatus
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType, persist_causal_graph_model, load_causal_graph_model
from polisyos.ir.analytics.estimand import DistributionRef, EstimandAST, SumNode, ProductNode

SOURCE=Path('/dev/shm/e02-orch03-20261008/c08')
SHA='2dd8339c210caf973586f7ddec69b6b0a48f1df7'
TREE='72c482aa7d731f1adfaf703dcd6708fcccff40cd'
BASE='f00dd7661a8d3329fb1fa1b049decb0d1d2f277b'
SCRATCH=Path('/dev/shm/e02-orch03-20261008/oracle-graph')

def git(*args):
    return subprocess.check_output(['git',*args],cwd=SOURCE,text=True).strip()

assert git('rev-parse','HEAD')==SHA
assert git('rev-parse','HEAD^{tree}')==TREE
assert Path(candidate.__file__).resolve()==SOURCE/'policy-engine/src/polisyos/foundry/methods/catalog/causal/_partial_graph_queries.py'
footprint=git('diff','--name-only',BASE,SHA).splitlines()
assert len(footprint)==8
for path in footprint:
    assert git('hash-object',path)==git('rev-parse',f'{SHA}:{path}')


def graph_from_states(nodes, pairs, states):
    edges=[]
    for (a,b), state in zip(pairs,states):
        if state==1:
            edges.append(CausalEdge(src=a,dst=b,mark_dst='tail'))
        elif state==2:
            edges.append(CausalEdge(src=a,dst=b))
        elif state==3:
            edges.append(CausalEdge(src=a,dst=b,mark_src='arrow',mark_dst='tail'))
    return CausalGraphModel(graph_type=GraphType.CPDAG,nodes=list(nodes),edges=edges)


def ast_probability(node, assignment, joint, nodes):
    if isinstance(node,DistributionRef):
        numerator=denominator=Fraction(0)
        assert not node.intervention_set and node.domain.value=='source'
        for values, mass in joint.items():
            row=dict(zip(nodes,values))
            if all(row[n]==assignment[n] for n in node.conditioning):
                denominator+=mass
                if all(row[n]==assignment[n] for n in node.variables):
                    numerator+=mass
        assert denominator>0
        return numerator/denominator
    if isinstance(node,SumNode):
        return sum((ast_probability(node.operand,{**assignment,**dict(zip(node.summation_vars,values))},joint,nodes)
                    for values in product((0,1),repeat=len(node.summation_vars))),Fraction(0))
    if isinstance(node,ProductNode):
        value=Fraction(1)
        for factor in node.factors:
            value*=ast_probability(factor,assignment,joint,nodes)
        return value
    raise AssertionError(type(node))


def check_query(name,nodes,edges,joint,tx,oy,expected_status):
    graph=CausalGraphModel(graph_type=GraphType.CPDAG,nodes=list(nodes),edges=edges)
    original=graph.model_dump(mode='json')
    result=CausalEngine().identify(tx,oy,graph,dataset_ref='oracle-positive-binary-law')
    assert result.status is expected_status
    basis=result.metadata['partial_graph_query']
    assert basis['coverage']=='exhaustive_for_declared_profile'
    assert basis['authority_eligible'] is False
    assert basis['query']=={'treatment':[tx],'outcome':[oy]}
    assert graph.model_dump(mode='json')==original
    answers=[]
    for completion in basis['completions']:
        arcs=tuple(tuple(arc) for arc in completion['arcs'])
        ast=EstimandAST.model_validate(completion['estimand'])
        assert ast.treatment==tx and ast.outcome==oy
        assert ast.query_str==f'P({oy}|do({tx}))'
        actual=ast_probability(ast.root,{tx:1,oy:1},joint,nodes)
        expected=truncated_binary_probability(joint,nodes,arcs,{tx:1},{oy:1})
        assert actual==expected,(name,arcs,actual,expected)
        answers.append({'arcs':arcs,'actual':str(actual),'independent':str(expected)})
    if result.estimand_ast is not None:
        common=ast_probability(result.estimand_ast.root,{tx:1,oy:1},joint,nodes)
        assert result.estimand_ast.treatment==tx and result.estimand_ast.outcome==oy
        assert all(Fraction(row['independent'])==common for row in answers)
    else:
        common=None
    return graph,result,{'name':name,'status':result.status.value,'admitted_completions':len(answers),
                         'all_completion_answers':answers,'common_answer':str(common) if common is not None else None,
                         'original_graph_preserved':True,'authority_eligible':False}


start=time.monotonic()
profiles=[]
for size in range(1,5):
    nodes=tuple('ABCD'[:size]);pairs=tuple(combinations(nodes,2))
    hist=Counter();empty=0;count=0
    for states in product(range(4),repeat=len(pairs)):
        expected=completion_family(nodes,list(zip(pairs,states)))
        graph=graph_from_states(nodes,pairs,states)
        count+=1
        if not expected:
            try:
                candidate._consistent_extensions(graph)
            except ValueError as exc:
                assert 'no acyclic extension' in str(exc)
                empty+=1
            else:
                raise AssertionError(('admitted impossible profile',nodes,states))
        else:
            extensions,assignments=candidate._consistent_extensions(graph)
            actual=tuple(sorted(tuple(sorted((e.src,e.dst) for e in g.edges)) for g in extensions))
            assert actual==expected,(nodes,states,actual,expected)
            assert assignments==2**states.count(1)
        hist[len(expected)]+=1
    profiles.append({'nodes':size,'profiles':count,'family_size_histogram':dict(sorted(hist.items())),
                     'empty_family_refusals':empty})
assert sum(row['profiles'] for row in profiles)==4165

q=[]
xy=tuple('XY')
xyjoint={bits:Fraction(1,2)*(Fraction(4,5) if bits[0]==bits[1] else Fraction(1,5))
         for bits in product((0,1),repeat=2)}
undirected=lambda a,b:CausalEdge(src=a,dst=b,mark_dst='tail')
pair_graph,pair_result,row=check_query('different_pair',xy,[undirected('X','Y')],xyjoint,'X','Y',IdentificationStatus.PAG_AMBIGUOUS);q.append(row)
xyz=tuple('XYZ')
_,_,row=check_query('sampled_agreement_chain_falsifier',xyz,[undirected('X','Y'),undirected('Y','Z')],chain_joint(xyz),'X','Z',IdentificationStatus.PAG_AMBIGUOUS);q.append(row)
noeffectjoint={bits:Fraction(1,2)*(Fraction(7,10) if bits[1] else Fraction(3,10))
               *(Fraction(4,5) if bits[1]==bits[2] else Fraction(1,5)) for bits in product((0,1),repeat=3)}
same_graph,same_result,row=check_query('no_effect_family_unequal_marginals',xyz,[undirected('Y','Z')],noeffectjoint,'X','Y',IdentificationStatus.IDENTIFIED);q.append(row)
_,_,row=check_query('fixed_reverse_nonzero_effect',xy,[CausalEdge(src='Y',dst='X',mark_src='arrow',mark_dst='tail')],xyjoint,'X','Y',IdentificationStatus.IDENTIFIED);q.append(row)

negatives=[]
unsupported=[
 ('oversized_nodes',CausalGraphModel(graph_type='cpdag',nodes=['X','Y','A','B','C'],edges=[undirected('X','Y')])),
 ('positive_lag',CausalGraphModel(graph_type='cpdag',nodes=['X','Y'],edges=[CausalEdge(src='X',dst='Y',lag=1)])),
 ('bidirected',CausalGraphModel(graph_type='cpdag',nodes=['X','Y'],edges=[CausalEdge(src='X',dst='Y',mark_src='arrow')])),
 ('MGraph_typed_contradiction',CausalGraphModel(graph_type='cpdag',nodes=['X','Y'],edges=[undirected('X','Y')],metadata={'mgraph':None})),
 ('parallel',CausalGraphModel(graph_type='cpdag',nodes=['X','Y'],edges=[CausalEdge(src='X',dst='Y'),CausalEdge(src='Y',dst='X')])),
 ('known_directed_cycle',CausalGraphModel(graph_type='cpdag',nodes=['X','Y','Z'],edges=[CausalEdge(src='X',dst='Y'),CausalEdge(src='Y',dst='Z'),CausalEdge(src='Z',dst='X')])),
]
# A model_copy can preserve a schema-valid graph object while bypassing validation;
# the runtime endpoint profile still must refuse the illegal mark before query execution.
unsupported.append(('circle_model_copy',pair_graph.model_copy(update={'edges':[pair_graph.edges[0].model_copy(update={'mark_src':importlib.import_module('polisyos.ir.analytics.causal_graph').EdgeMark.CIRCLE})]})))
for name,graph in unsupported:
    r=CausalEngine().identify('X','Y',graph)
    b=r.metadata['partial_graph_query']
    assert r.status is IdentificationStatus.PAG_AMBIGUOUS and r.estimand_ast is None
    assert b['coverage']=='not_established' and b['disposition']=='unsupported' and b['authority_eligible'] is False
    negatives.append({'case':name,'status':r.status.value,'limitation':b['limitation']})
for tx,oy,kwargs,name in [
 ('X','Z',{},'foreign_outcome'),('X','X',{},'same_treatment_outcome'),
 (frozenset(), 'Y',{},'empty_treatment'),
 ('X','Y',{'conditions':frozenset({'Z'})},'conditional_query'),
 ('X','Y',{'oracle':'expert'},'oracle_request'),
 ('X','Y',{'s_nodes':[object()]},'transport_request'),
]:
    r=CausalEngine().identify(tx,oy,pair_graph,**kwargs)
    assert r.metadata['partial_graph_query']['coverage']=='not_established' and r.estimand_ast is None
    negatives.append({'case':name,'status':r.status.value,'limitation':r.metadata['partial_graph_query']['limitation']})

cas=SCRATCH/'review-cas';store=FileSystemCAS(cas)
persisted=[]
for name,graph,result in [('conditional',pair_graph,pair_result),('common',same_graph,same_result)]:
    graph_ref=persist_causal_graph_model(store,graph)
    audit=CausalEngine(artifact_store=store).audit(result,None,run_id='independent-'+name,graph=graph)
    proof=load_proof_bundle(FileSystemCAS(cas),audit.proof_bundle_ref)
    assert proof.metadata['partial_graph_query']==result.metadata['partial_graph_query']
    assert load_causal_graph_model(FileSystemCAS(cas),graph_ref)==graph
    persisted.append({'case':name,'graph_ref':graph_ref.model_dump(mode='json'),'proof_ref':audit.proof_bundle_ref.model_dump(mode='json'),
                      'status':proof.proof_status,'basis':proof.metadata['partial_graph_query']['disposition']})
child_script='''
import json,os,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.registry.refs import ProofBundleRef,CausalGraphModelRef
store=FileSystemCAS(sys.argv[1]);rows=json.loads(sys.argv[2]);seen=[]
for row in rows:
 p=load_proof_bundle(store,ProofBundleRef.model_validate(row['proof_ref']))
 g=load_causal_graph_model(store,CausalGraphModelRef.model_validate(row['graph_ref']))
 b=p.metadata['partial_graph_query']
 assert g.graph_type.value=='cpdag' and b['authority_eligible'] is False
 assert b['disposition']==row['basis'] and p.proof_status==row['status'] and b['limitation']
 seen.append({'case':row['case'],'profile':g.graph_type.value,'status':p.proof_status,'completions':b['admitted_completions'],'authority_eligible':False})
print(json.dumps({'pid':os.getpid(),'rows':seen}))
'''
child=subprocess.run([sys.executable,'-c',child_script,str(cas),json.dumps(persisted)],capture_output=True,text=True,check=True)
child_data=json.loads(child.stdout.splitlines()[-1]);assert child_data['pid']!=os.getpid()
assert git('rev-parse','HEAD')==SHA and git('status','--porcelain')==''
print(json.dumps({'schema':'e02.c08.independent_candidate_review.v1','reviewer':'/root/oracle_graph','author':'/root/c08',
                  'candidate_sha':SHA,'candidate_tree':TREE,'slice_base':BASE,'footprint':footprint,
                  'structural_oracle':{'source':'completion_oracle.py','denominator':4165,'families':profiles},
                  'exact_law_queries':q,'unsupported_controls':negatives,
                  'consumer':{'path':'CausalEngine.identify→audit→proofCAS→fresh typedreader→distinct child',
                              'producer_pid':os.getpid(),'child':child_data,'stderr':child.stderr},
                  'existing_ID_shortcut':'not used by CPDAG branch; old limitation unchanged',
                  'removal_proposal':{'property':'complete family not sample','retain':['profile name','coverage field','orientation_assignments_checked','authority_eligible=False'],
                                      'remove':'return only chain reverse/fork two completions from runtime _consistent_extensions while originalorientationcount4 remains',
                                      'expected':'same no-effect answers falselyemitIDENTIFIED; independentfullfamily3/conditionalassertionsFAIL'},
                  'wall_s':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'status':'GO','scope':'declared bounded mathematical profile and candidate-grade proof persistence only',
                  'limitations':['not universal CPDAG/PAG identification completeness','no graph/source/assumption scientific authority','B56 actual canonical shared workload unavailable; C01/L01 packet required','broad Ruff357F821 and P41not_established carried separately; not run here']},indent=2))
