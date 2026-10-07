"""One real installed MethodJob/Node selected-CAS graph read in a fresh -I child."""
from pathlib import Path
import hashlib,json,os,runpy,subprocess,sys,time

OUT=Path(__file__).resolve().parent
PACKET=Path('/tmp/e02-F-continuation-20261007/foundry/installed-default-resource-forward')
CONFIG=json.loads((PACKET/'installed-config.json').read_text())
SOURCE='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82'
TREE='750d28da94f372848fe6b2db5f88db95b94cb57d'
SITE=Path(CONFIG['sites']['wheel']).resolve()
assert CONFIG['source_sha']==SOURCE and CONFIG['source_tree']==TREE
assert sys.flags.isolated==1
assert 'PYTHONPATH' not in os.environ

def ref(path):
    path=Path(path);body=path.read_bytes()
    return {'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

def origins():
    result={}
    for name,module in tuple(sys.modules.items()):
        if name=='polisyos' or name.startswith('polisyos.') or name=='tools' or name.startswith('tools.'):
            filename=getattr(module,'__file__',None)
            if filename:
                resolved=Path(filename).resolve();assert resolved.is_relative_to(SITE),(name,str(resolved))
                result[name]=str(resolved)
            for location in getattr(module,'__path__',[]):
                assert Path(location).resolve().is_relative_to(SITE),(name,location)
    return result

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_graph import load_causal_graph_model

if len(sys.argv)>1 and sys.argv[1]=='--reader':
    payload=json.loads((OUT/'reader-input.json').read_text())
    assert payload['source_sha']==SOURCE and payload['source_tree']==TREE
    store=FileSystemCAS(Path(payload['cas_root']))
    selected=ArtifactRef.model_validate(payload['selected_graph_ref'])
    method=ArtifactRef.model_validate(payload['method_result_ref'])
    model=load_causal_graph_model(store,selected)
    relations={(e.src,e.dst,e.mark_src.value,e.mark_dst.value,e.lag) for e in model.edges}
    assert relations=={('X','Y','tail','arrow',None)},relations
    assert model.model_dump(mode='json')==payload['expected_model']
    assert list(model.to_networkx().edges())==[('X','Y')]
    manifest=store.get_manifest(selected)
    assert manifest.kind=='ir.causal_graph_model'
    assert any(row.role=='data_graph' and row.artifact_id==method.artifact_id for row in manifest.inputs)
    detached=model.kuzu_edge_rows;assert detached[0]['src']=='X' and detached[0]['dst']=='Y'
    detached[0]['dst']='untrusted-reader-mutation'
    assert model.kuzu_edge_rows[0]['dst']=='Y' and model.edges[0].dst=='Y'
    proof={'source_sha':SOURCE,'source_tree':TREE,'outcome':'PASS','reader_pid':os.getpid(),'parent_pid':payload['parent_pid'],'isolated':sys.flags.isolated,'executable':sys.executable,'cwd':os.getcwd(),'PYTHONPATH':'absent','selected_graph_ref':selected.model_dump(mode='json'),'method_result_ref':method.model_dump(mode='json'),'manifest':manifest.model_dump(mode='json'),'literal_relation_oracle':[['X','Y','tail','arrow',None]],'complete_model_matches_parent_persisted_result':True,'detached_row_mutation_does_not_rewrite_model':True,'product_origins':origins(),'authority_scope':'Synthetic candidate graph only; no Runtime/EvalSafety or causal identification authority positive.'}
    assert proof['reader_pid']!=proof['parent_pid']
    (OUT/'fresh-reader-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'outcome':'PASS','reader_pid':proof['reader_pid'],'parent_pid':proof['parent_pid'],'isolated':1,'owned_origins':len(proof['product_origins']),'selected_ref':selected.model_dump(mode='json')}))
else:
    assert Path.cwd().resolve()==(PACKET/'wheel-consumer').resolve()
    relative='tests/unit/scientist/methods/causal/test_graph_intake_current_content.py'
    fixture=PACKET/'wheel-consumer'/relative
    carrier=json.loads((PACKET/'carrier-manifest.json').read_text())
    row=next(r for r in carrier['files'] if r['path']=='policy-engine/'+relative)
    assert ref(fixture)['bytes']==row['bytes'] and ref(fixture)['sha256']==row['sha256']
    assert row['git_sha']==SOURCE
    helpers=runpy.run_path(str(fixture))
    context=helpers['context'].__wrapped__(OUT/'synthetic-context')
    source_graph=helpers['graph']({'src':'X','dst':'Y'})
    job,source=helpers['produce'](context,source_graph)
    assert not job.issues and job.method_result_ref is not None,job.issues
    state=helpers['state_for'](job)
    node=helpers['ReconcileCausalGraphNode']()
    outcome=node.execute(context,state)
    assert outcome.status=='ok',outcome.error
    selected,model=helpers['fresh'](context,outcome)
    assert helpers['relations'](model)=={('X','Y','tail','arrow',None)}
    manifest=context.store.get_manifest(selected)
    assert any(row.role=='data_graph' and row.artifact_id==job.method_result_ref.artifact_id for row in manifest.inputs)
    payload={'source_sha':SOURCE,'source_tree':TREE,'cas_root':str(context.store.root),'parent_pid':os.getpid(),'source_input_ref':source.model_dump(mode='json'),'method_result_ref':job.method_result_ref.model_dump(mode='json'),'selected_graph_ref':selected.model_dump(mode='json'),'expected_model':model.model_dump(mode='json')}
    (OUT/'reader-input.json').write_text(json.dumps(payload,indent=2)+'\n')
    child_cwd=OUT/'neutral-reader-cwd';child_cwd.mkdir(exist_ok=True)
    argv=[sys.executable,'-I',str(Path(__file__).resolve()),'--reader'];env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';start=time.monotonic()
    child=subprocess.run(argv,cwd=child_cwd,env=env,capture_output=True)
    record={'argv':argv,'cwd':str(child_cwd),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':child.returncode,'seconds':time.monotonic()-start}
    for name,body in [('stdout',child.stdout),('stderr',child.stderr)]:
        path=OUT/('fresh-reader.'+name+'.txt');path.write_bytes(body);record[name]=ref(path)
    (OUT/'fresh-reader.command.json').write_text(json.dumps(record,indent=2)+'\n')
    assert child.returncode==0,child.stderr.decode(errors='replace')
    reader=json.loads((OUT/'fresh-reader-proof.json').read_text())
    assert reader['outcome']=='PASS' and reader['isolated']==1 and reader['reader_pid']!=os.getpid()
    proof={'source_sha':SOURCE,'source_tree':TREE,'outcome':'PASS','profile':'wheel','parent_pid':os.getpid(),'parent_isolated':sys.flags.isolated,'registered_method_fqn':helpers['ReconcileCausalGraph'].signature.fqn,'producer':'actual maintained fixture produce() -> MethodJob/run_job','consumer':'actual ReconcileCausalGraphNode -> persisted selected ref -> independent child -I load_causal_graph_model','source_input_ref':source.model_dump(mode='json'),'method_result_ref':job.method_result_ref.model_dump(mode='json'),'selected_graph_ref':selected.model_dump(mode='json'),'selected_manifest':manifest.model_dump(mode='json'),'fixture':row,'product_origins':origins(),'child_execution':record,'child_proof':ref(OUT/'fresh-reader-proof.json'),'scope':'ONE wheel-profile known static synthetic X->Y candidate; not sdist or79suite replay, not production/Runtime-authority-positive.'}
    (OUT/'fresh-bridge-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'outcome':'PASS','source_sha':SOURCE,'registered_method_fqn':proof['registered_method_fqn'],'parent_isolated':1,'child_isolated':1,'owned_parent_origins':len(proof['product_origins']),'owned_child_origins':len(reader['product_origins']),'child_seconds':record['seconds']}))
