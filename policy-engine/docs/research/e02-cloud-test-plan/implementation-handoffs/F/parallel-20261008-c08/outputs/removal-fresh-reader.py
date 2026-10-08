import json,os,pathlib,subprocess,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal import _partial_graph_queries as adapter
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.ir.analytics.causal_graph import CausalEdge,CausalGraphModel,GraphType,persist_causal_graph_model
assert pathlib.Path(adapter.__file__).is_relative_to(pathlib.Path(sys.argv[1]))
graph=CausalGraphModel(graph_type=GraphType.CPDAG,nodes=['X','Y','Z'],edges=[CausalEdge(src='X',dst='Y',mark_dst='tail'),CausalEdge(src='Y',dst='Z',mark_dst='tail')])
store=FileSystemCAS(pathlib.Path(sys.argv[1])/'independent-removal-cas')
gref=persist_causal_graph_model(store,graph)
engine=CausalEngine(artifact_store=store)
r=engine.identify('X','Z',graph,dataset_ref='binary-chain-law')
audit=engine.audit(r,None,run_id='removed-full-family',graph=graph)
script='''
import json,os,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import load_proof_bundle
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.registry.refs import ProofBundleRef,CausalGraphModelRef
store=FileSystemCAS(sys.argv[1]);p=load_proof_bundle(store,ProofBundleRef.model_validate_json(sys.argv[2]));g=load_causal_graph_model(store,CausalGraphModelRef.model_validate_json(sys.argv[3]));b=p.metadata['partial_graph_query']
print(json.dumps({'pid':os.getpid(),'proof_status':p.proof_status,'profile':b['profile'],'coverage':b['coverage'],'orientation_assignments_checked':b['orientation_assignments_checked'],'admitted_completions':b['admitted_completions'],'disposition':b['disposition'],'authority_eligible':b['authority_eligible'],'original_graph_type':g.graph_type.value}),flush=True)
assert g.graph_type.value=='cpdag'
assert p.proof_status=='oracle_needed' and p.estimand_ast is None,'full independent family has .68/.5/.5; persisted sampled-common proof must remain conditional'
'''
child=subprocess.run([sys.executable,'-c',script,str(store.root),audit.proof_bundle_ref.model_dump_json(),gref.model_dump_json()],capture_output=True,text=True)
print(json.dumps({'producer_pid':os.getpid(),'child_stdout':child.stdout,'child_stderr':child.stderr,'child_returncode':child.returncode}),flush=True)
sys.exit(child.returncode)
