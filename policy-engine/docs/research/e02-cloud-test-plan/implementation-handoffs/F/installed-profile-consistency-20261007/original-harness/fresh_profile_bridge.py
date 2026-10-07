"""ONE installed registered producer/Node -> selected CAS -> fresh -I ADMG reader."""
from pathlib import Path
import hashlib,json,os,runpy,subprocess,sys,time
OUT=Path(__file__).resolve().parent/'candidate-wheel'/'fresh-profile'
OUT.mkdir(exist_ok=True)
CONFIG=json.loads((OUT.parent/'installed-config.json').read_text());SITE=Path(CONFIG['site']).resolve()
assert sys.flags.isolated==1 and 'PYTHONPATH' not in os.environ
assert os.environ['POLISYOS_METRICS_PORT']=='9476'
SHA=CONFIG['source_sha'];TREE=CONFIG['source_tree']
EXPECTED={('Y','X','tail','arrow',None),('X','Y','arrow','arrow',None)}
def ref(path):
 p=Path(path);raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def origins():
 result={}
 for name,module in tuple(sys.modules.items()):
  if name=='polisyos' or name.startswith('polisyos.') or name=='tools' or name.startswith('tools.'):
   filename=getattr(module,'__file__',None)
   if filename:p=Path(filename).resolve();assert p.is_relative_to(SITE),(name,p);result[name]=str(p)
   for location in getattr(module,'__path__',[]):assert Path(location).resolve().is_relative_to(SITE),(name,location)
 return result
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.analytics.mgraph import extract_mgraph_metadata
if len(sys.argv)>1 and sys.argv[1]=='--reader':
 payload=json.loads((OUT/'reader-input.json').read_text());assert payload['source_sha']==SHA and payload['source_tree']==TREE
 store=FileSystemCAS(Path(payload['cas_root']));selected=ArtifactRef.model_validate(payload['selected_graph_ref']);method=ArtifactRef.model_validate(payload['method_result_ref'])
 model=load_causal_graph_model(store,selected)
 original=load_causal_graph_model(store,ArtifactRef.model_validate(payload['original_mgraph_ref']))
 assert original.graph_type.value=='mgraph' and extract_mgraph_metadata(original).model_dump(mode='json')==payload['original_mgraph_metadata']
 assert original.model_dump(mode='json')==payload['original_mgraph_model']
 assert payload['retagged_rejection']['job_issues'] and payload['retagged_rejection']['method_result_ref'] is None
 assert payload['retagged_rejection']['node_status']=='fail' and not payload['retagged_rejection']['node_artifacts']
 assert payload['retagged_rejection']['has_reconciled_ref'] is False
 actual={(e.src,e.dst,e.mark_src.value,e.mark_dst.value,e.lag) for e in model.edges}
 assert actual==EXPECTED,actual
 assert model.graph_type.value=='admg' and model.model_dump(mode='json')==payload['expected_model']
 manifest=store.get_manifest(selected);assert manifest.kind=='ir.causal_graph_model'
 assert any(row.role=='data_graph' and row.artifact_id==method.artifact_id for row in manifest.inputs)
 rows=model.kuzu_edge_rows;assert len(rows)==2
 rows[0]['dst']='untrusted-reader-mutation';assert model.kuzu_edge_rows[0]['dst']!='untrusted-reader-mutation'
 proof={'source_sha':SHA,'source_tree':TREE,'outcome':'PASS','reader_pid':os.getpid(),'parent_pid':payload['parent_pid'],'isolated':sys.flags.isolated,'executable':sys.executable,'cwd':os.getcwd(),'environment':{'PYTHONPATH':'absent','POLISYOS_METRICS_PORT':os.environ['POLISYOS_METRICS_PORT']},'selected_graph_ref':selected.model_dump(mode='json'),'method_result_ref':method.model_dump(mode='json'),'manifest':manifest.model_dump(mode='json'),'literal_relation_oracle':[list(row) for row in sorted(EXPECTED)],'complete_typed_model_matches_parent':True,'detached_row_mutation_does_not_rewrite_model':True,'product_origins':origins(),'authority_scope':'Synthetic static ADMG only; no admission/causal identification positive.'}
 assert proof['reader_pid']!=proof['parent_pid']
 (OUT/'fresh-reader-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'outcome':'PASS','reader_pid':proof['reader_pid'],'parent_pid':proof['parent_pid'],'isolated':1,'owned_origins':len(proof['product_origins'])}))
else:
 assert Path.cwd()==Path(CONFIG['carrier'])
 relative='policy-engine/tests/unit/scientist/methods/causal/test_graph_intake_current_content.py';fixture=Path(CONFIG['carrier'])/relative.removeprefix('policy-engine/')
 row=next(r for r in json.loads(Path(CONFIG['carrier_manifest']).read_text())['files'] if r['path']==str(fixture))
 assert ref(fixture)['bytes']==row['bytes'] and ref(fixture)['sha256']==row['sha256'] and row['git_sha']==SHA
 helpers=runpy.run_path(str(fixture));context=helpers['context'].__wrapped__(OUT/'synthetic-context')
 original_mgraph=helpers['scored_mgraph']()
 original_ref=helpers['persist_causal_graph_model'](context.store,original_mgraph)
 retag=original_mgraph.model_dump(mode='json');retag['graph_type']='admg';retagged=helpers['CausalGraphModel'].model_validate(retag)
 rejected_job,_=helpers['produce'](context,retagged)
 rejected_node=helpers['ReconcileCausalGraphNode']().execute(context,helpers['ExperimentState'](run_id='graph-content',params={'data_causal_graph':retagged.model_dump(mode='json')}))
 assert rejected_job.issues and rejected_job.method_result_ref is None,rejected_job
 assert rejected_node.status=='fail' and not rejected_node.artifacts,rejected_node
 key=helpers['ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF'];assert key not in rejected_node.state.artifacts_index
 refusal={'job_issues':[i.model_dump(mode='json') for i in rejected_job.issues],'method_result_ref':None,'node_status':rejected_node.status,'node_artifacts':[a.model_dump(mode='json') for a in rejected_node.artifacts],'has_reconciled_ref':key in rejected_node.state.artifacts_index,'node_error':rejected_node.error.model_dump(mode='json')}
 source=helpers['graph']({'src':'Y','dst':'X'},{'src':'X','dst':'Y','mark_src':'arrow','mark_dst':'arrow'},graph_type='admg')
 job,input_ref=helpers['produce'](context,source);assert not job.issues and job.method_result_ref is not None,job.issues
 outcome=helpers['ReconcileCausalGraphNode']().execute(context,helpers['state_for'](job));selected,model=helpers['fresh'](context,outcome)
 assert helpers['relations'](model)==EXPECTED and model.graph_type.value=='admg'
 payload={'source_sha':SHA,'source_tree':TREE,'cas_root':str(context.store.root),'parent_pid':os.getpid(),'source_input_ref':input_ref.model_dump(mode='json'),'method_result_ref':job.method_result_ref.model_dump(mode='json'),'selected_graph_ref':selected.model_dump(mode='json'),'expected_model':model.model_dump(mode='json'),'original_mgraph_ref':original_ref.model_dump(mode='json'),'original_mgraph_model':original_mgraph.model_dump(mode='json'),'original_mgraph_metadata':extract_mgraph_metadata(original_mgraph).model_dump(mode='json'),'retagged_rejection':refusal}
 (OUT/'reader-input.json').write_text(json.dumps(payload,indent=2)+'\n');child_cwd=OUT/'neutral-reader-cwd';child_cwd.mkdir()
 argv=[sys.executable,'-I',str(Path(__file__).resolve()),'--reader'];env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';start=time.monotonic();child=subprocess.run(argv,cwd=child_cwd,env=env,capture_output=True)
 record={'argv':argv,'cwd':str(child_cwd),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1','POLISYOS_METRICS_PORT':env['POLISYOS_METRICS_PORT']},'exit_code':child.returncode,'seconds':time.monotonic()-start}
 for name,raw in [('stdout',child.stdout),('stderr',child.stderr)]:p=OUT/('fresh-reader.'+name+'.txt');p.write_bytes(raw);record[name]=ref(p)
 (OUT/'fresh-reader.command.json').write_text(json.dumps(record,indent=2)+'\n');assert child.returncode==0,child.stderr.decode(errors='replace')
 reader=json.loads((OUT/'fresh-reader-proof.json').read_text());assert reader['isolated']==1 and reader['reader_pid']!=os.getpid()
 proof={'source_sha':SHA,'source_tree':TREE,'outcome':'PASS','profile':'wheel','parent_pid':os.getpid(),'parent_isolated':sys.flags.isolated,'registered_method_fqn':helpers['ReconcileCausalGraph'].signature.fqn,'producer':'Actual maintained produce()->MethodJob/run_job','consumer':'Actual ReconcileCausalGraphNode->persisted selected ref->differentPID child-I load_causal_graph_model','source_input_ref':input_ref.model_dump(mode='json'),'method_result_ref':job.method_result_ref.model_dump(mode='json'),'selected_graph_ref':selected.model_dump(mode='json'),'original_mgraph_ref':original_ref.model_dump(mode='json'),'retagged_rejection':refusal,'selected_manifest':context.store.get_manifest(selected).model_dump(mode='json'),'fixture':row,'product_origins':origins(),'child_execution':record,'child_proof':ref(OUT/'fresh-reader-proof.json'),'scope':'Retagged genuineMGraph realproducer+Node refuse withoutpublication; originalMGraph separatechild extractor positive; ONE native static ADMG with reversed directed and bidirected edges; no new sdist/wholeRuntime authority/budget positive.'}
 (OUT/'fresh-bridge-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'outcome':'PASS','source_sha':SHA,'parent_isolated':1,'child_isolated':1,'owned_parent_origins':len(proof['product_origins']),'owned_child_origins':len(reader['product_origins']),'child_seconds':record['seconds']}))
