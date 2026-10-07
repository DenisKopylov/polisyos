"""Reconcile complete immutable Git deltas without executing competing source."""
import ast,collections,hashlib,json,pathlib,subprocess
root=pathlib.Path('/workspace/e02-F-api-20261006');out=pathlib.Path('/tmp/e02-F-continuation-20261007/api')
G=lambda *a:subprocess.check_output(['git',*a],cwd=root)
refs={k:G('rev-parse',v+'^{commit}').decode().strip() for k,v in {'reviewed':'ab56a0f3414c6e903f7dcdaaa7b7ed540b1923c5','competing':'3dde887e22592cdd7c1fe8865707afdfd72dc6fb','canonical':'8236d9c368336a5ea20c1586f29aea7321db6536','api_carrier':'90c72b51155321684c788cd5a03fbb70fc001d53','root_evidence':'072d45a56d1119fe3e7665cec2cbbdca015d2934'}.items()}
commits=G('rev-list','--reverse',refs['reviewed']+'..'+refs['competing']).decode().splitlines();assert len(commits)==9
cache={}
def data(sha,path):
 key=(sha,path)
 if key not in cache:
  p=subprocess.run(['git','show',sha+':'+path],cwd=root,capture_output=True);cache[key]=None if p.returncode else p.stdout
 return cache[key]
def blob(sha,path):
 d=data(sha,path)
 if d is None:return {'present':False}
 r={'present':True,'oid':G('rev-parse',sha+':'+path).decode().strip(),'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}
 if path.endswith('.py'):r['ast_sha256']=hashlib.sha256(ast.dump(ast.parse(d),include_attributes=False).encode()).hexdigest()
 return r
def category(p):
 return 'runtime_source' if p.startswith('policy-engine/src/') else 'test' if p.startswith('policy-engine/tests/') else 'release_fragment' if p.startswith('policy-engine/release-fragments/') else 'reference_doc' if p.startswith('policy-engine/docs/reference/') else 'handoff_evidence' if '/implementation-handoffs/' in p else 'tool' if p.startswith('policy-engine/tools/') else 'other_tracked'
def diff_paths(a,b):
 lines=G('diff','--no-renames','--name-status',a,b).decode().splitlines();return [{'status':r.split('\t')[0],'path':r.split('\t')[1],'category':category(r.split('\t')[1])} for r in lines]
full=diff_paths(refs['reviewed'],refs['competing']);product=[r['path'] for r in full if r['category'] in ('runtime_source','test','release_fragment','reference_doc','tool')];assert len(product)==7
rows=[]
for p in product:
 row={'path':p,'category':category(p),'bindings':{k:blob(v,p) for k,v in refs.items()}}
 pairs={}
 for a,b in [('reviewed','competing'),('competing','canonical'),('canonical','api_carrier'),('canonical','root_evidence')]:
  left,right=row['bindings'][a],row['bindings'][b];pairs[a+'__'+b]={'byte_equal':left==right,'same_presence':left['present']==right['present'],'ast_equal':left.get('ast_sha256')==right.get('ast_sha256') if left.get('ast_sha256') and right.get('ast_sha256') else None}
 row['comparisons']=pairs;rows.append(row)
commitrows=[]
ir='policy-engine/src/polisyos/ir/analytics/causal_graph.py'
for sha in commits:
 parent=G('rev-parse',sha+'^').decode().strip();paths=diff_paths(parent,sha);commitrows.append({'sha':sha,'parent':parent,'tree':G('rev-parse',sha+'^{tree}').decode().strip(),'subject':G('show','-s','--format=%s',sha).decode().strip(),'changed_paths':paths,'classification_counts':dict(collections.Counter(p['category'] for p in paths)),'defining_IR_blob':blob(sha,ir)})
patches=[]
for label,a,b in [('reviewed-to-competing','reviewed','competing'),('competing-to-canonical','competing','canonical')]:
 raw=G('diff','--no-renames',refs[a],refs[b],'--',*product);p=out/(label+'.patch');p.write_bytes(raw);patches.append({'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'left':refs[a],'right':refs[b],'selected_paths':product})
result={'schema':'policyos.e02.installed_source_reconciliation.v1','executing_party':'F/causal_api independent read-only reconciler','refs':{k:{'sha':v,'tree':G('rev-parse',v+'^{tree}').decode().strip()} for k,v in refs.items()},'complete_ab56_to_3dde_delta':full,'delta_denominator':{'all_changed_tracked_paths':len(full),'classifications':dict(collections.Counter(p['category'] for p in full)),'source_test_reference_doc_fragment_tool_paths':len(product),'post_review_commits':len(commits)},'all_nine_commit_deltas':commitrows,'every_defining_IR_blob':{'path':ir,'unique_blobs':sorted({r['defining_IR_blob']['oid'] for r in commitrows}|{blob(refs['reviewed'],ir)['oid'],blob(refs['canonical'],ir)['oid']}),'bound_every_commit':True},'contract_blob_delta_table':rows,'full_product_patches':patches,'decision':'Keep canonical8236 contract. Competing3dde remains unmerged; its causal_graph.py differs only in two formatting hunks and normalized whole-module AST is identical. This does not transfer any whole-head PASS.','affected_consumers':['CausalGraphModel detached node/edge rows→actual CSV/to_kuzu parameter consumer','warm model_copy(update)→ancestors/export/currentdump→CAS→fresh typedreader','gcm_fit.validate_persisted_gcm_spec and gcm_query.validate_persisted_estimator_interval→maintained Core ArtifactRef facade','DoWhy/sharedworker projection release metadata only, no worker math/protocol delta'],'new_installed_wave':'UNRUN; only affected consumers join finalfuture freeze. Existing199source8236 tests remain exactly source/profile-specific.','patterns':['P14','P27','P29','P35','P36','P37','P38','P40','P41'],'source_guard':{'own_head':G('rev-parse','HEAD').decode().strip(),'branch':G('symbolic-ref','HEAD').decode().strip(),'tracked_status':G('status','--porcelain','--untracked-files=no').decode()}}
p=out/'source-reconciliation.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'output':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'denominator':result['delta_denominator'],'IR_blobs':result['every_defining_IR_blob'],'contract_rows':[{'path':r['path'],'competing_vs_canonical':r['comparisons']['competing__canonical']} for r in rows]}))
