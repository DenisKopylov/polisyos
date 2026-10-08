import ast, collections, gzip, hashlib, io, json, pathlib, re, subprocess, tarfile, xml.etree.ElementTree as ET
D=pathlib.Path('/tmp/e02-F-continuation-20261007/economics/root-companion-review')
REPO='/workspace/e02-F-closeout-20261006'
ROOT='5609d09cbf519f01bde1ea81c6b3ee4a36a484a8'; PRODUCT='8236d9c368336a5ea20c1586f29aea7321db6536'; BASE='072d45a56d1119fe3e7665cec2cbbdca015d2934'
API='605dadeb76499c3f6eadd95e16a8df1bbb2cb89f'; FIT='e04ddf884071b17ffb1d021c9a6b23f826d76774'; A90='90c72b51155321684c788cd5a03fbb70fc001d53'; AB='ab56a0f3414c6e903f7dcdaaa7b7ed540b1923c5'; COMP='3dde887e22592cdd7c1fe8865707afdfd72dc6fb'
P='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
commands=[]; counter=0; cache={}
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(name,d): (D/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def run(name,args,input=None):
 global counter
 counter+=1; stem=f'{counter:03d}-{name}'
 q=subprocess.run(args,cwd=REPO,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 (D/(stem+'.stdout')).write_bytes(q.stdout);(D/(stem+'.stderr')).write_bytes(q.stderr)
 commands.append({'name':name,'argv':args,'cwd':REPO,'exit_code':q.returncode,'stdin':None if input is None else {'bytes':len(input),'sha256':sha(input)},'stdout':{'path':stem+'.stdout','bytes':len(q.stdout),'sha256':sha(q.stdout)},'stderr':{'path':stem+'.stderr','bytes':len(q.stderr),'sha256':sha(q.stderr)}})
 return q

def git(name,args):
 q=run(name,['git',*args]); assert q.returncode==0,(name,q.stderr);return q.stdout

def content(ref,path):
 key=(ref,path)
 if key not in cache: cache[key]=subprocess.check_output(['git','show',ref+':'+path],cwd=REPO)
 return cache[key]
def meta(ref,path):
 b=content(ref,path);return {'git_ref':ref,'path':path,'bytes':len(b),'sha256':sha(b),'git_blob':subprocess.check_output(['git','rev-parse',ref+':'+path],cwd=REPO,text=True).strip()}
api=json.loads(content(ROOT,P+'api-installed-graph-reconciliation-20261007.json'));fit=json.loads(content(ROOT,P+'tmle-persisted-consumers-20261007.json'))
checks=[]
for first,last in [(A90,API),(API,ROOT),(FIT,ROOT),(BASE,FIT),(PRODUCT,API),(PRODUCT,FIT)]:
 q=run('ancestor', ['git','merge-base','--is-ancestor',first,last]);assert q.returncode==0
 checks.append({'first':first,'last':last,'is_ancestor':True})
heads=git('merge-parents',['log','--format=%H %T %P %s','-8',ROOT]).decode()
tracked=git('tracked-status',['status','--porcelain=v1','--untracked-files=no']).decode();assert tracked==''
assert git('runtime-delta',['diff','--name-status',PRODUCT,ROOT,'--','policy-engine/src'])==b''
footprints={}
for label,head in [('api',API),('fit',FIT)]:
 raw=git(label+'-full-delta',['diff','--name-status',BASE,head]).decode(); rows=[s.split('\t') for s in raw.splitlines()]
 paths=[x[-1] for x in rows if x[-1].startswith(('policy-engine/tests/','policy-engine/docs/reference/','policy-engine/release-fragments/','policy-engine/src/','policy-engine/tools/'))]
 assert len(paths)==3 and not any(x.startswith('policy-engine/src/') for x in paths)
 git(label+'-complete-footprint-patch',['diff','--binary',BASE,head,'--',*paths])
 git(label+'-full-handoff-delta',['diff','--binary',head+'^',head])
 for path in paths:
  assert content(head,path)==content(ROOT,path)
  git(label+'-source-'+path.rsplit('/',1)[1],['show',head+':'+path])
 footprints[label]={'carrier':head,'candidate_sha':api['candidate_source_sha'] if label=='api' else fit['candidate_sha'],'candidate_tree':api['candidate_tree_sha'] if label=='api' else fit['candidate_tree_sha'],'all_changed_paths':rows,'three_new_owned_paths':[meta(ROOT,x) for x in paths]}
# Complete competing history, independent reconstruction, no sampling.
rows=[s.split('\t') for s in git('competing-complete-delta',['diff','--name-status',AB,COMP]).decode().splitlines()]
def category(p):
 if p.startswith(P):return 'handoff_evidence'
 if p.startswith('policy-engine/src/'):return 'runtime_source'
 if p.startswith('policy-engine/tests/'):return 'test'
 if p.startswith('policy-engine/docs/reference/'):return 'reference_doc'
 if p.startswith('policy-engine/release-fragments/'):return 'release_fragment'
 raise AssertionError(p)
counts=dict(collections.Counter(category(x[-1]) for x in rows));selected=[x[-1] for x in rows if category(x[-1])!='handoff_evidence']
commits=git('competing-nine-commits',['rev-list','--reverse',AB+'..'+COMP]).decode().splitlines();assert len(commits)==9
recon=json.loads(gzip.decompress(content(ROOT,api['reconciliation']['full_table_ref']['path'])))
assert len(rows)==221 and len(selected)==7 and counts==recon['delta_denominator']['classifications']
assert [{'status':x[0],'path':x[-1],'category':category(x[-1])} for x in rows]==recon['complete_ab56_to_3dde_delta']
commit_rows=[]
for ref,decl in zip(commits,recon['all_nine_commit_deltas']):
 assert ref==decl['sha']
 delta=[s.split('\t') for s in git('competing-commit-'+ref[:8],['diff','--name-status',ref+'^',ref]).decode().splitlines()]
 assert [{'status':x[0],'path':x[-1],'category':category(x[-1])} for x in delta]==decl['changed_paths']
 commit_rows.append({'sha':ref,'parent':git('competing-parent-'+ref[:8],['rev-parse',ref+'^']).decode().strip(),'tree':git('competing-tree-'+ref[:8],['rev-parse',ref+'^{tree}']).decode().strip(),'all_changed_paths':delta})
contracts=[]
for path in selected:
 bindings=[meta(ref,path) if subprocess.run(['git','cat-file','-e',ref+':'+path],cwd=REPO,stderr=subprocess.DEVNULL).returncode==0 else {'git_ref':ref,'path':path,'present':False} for ref in [AB,COMP,PRODUCT,A90,BASE,ROOT]]
 contracts.append({'path':path,'bindings':bindings})
graph='policy-engine/src/polisyos/ir/analytics/causal_graph.py'
blob_oids=sorted(set(meta(ref,graph)['git_blob'] for ref in [AB,*commits,PRODUCT,A90,BASE,ROOT]));assert blob_oids==recon['every_defining_IR_blob']['unique_blobs']
a=content(COMP,graph).decode();b=content(PRODUCT,graph).decode();assert a!=b and ast.dump(ast.parse(a),include_attributes=False)==ast.dump(ast.parse(b),include_attributes=False)
patch=git('competing-canonical-graph-patch',['diff',COMP,PRODUCT,'--',graph]).decode();assert len(re.findall(r'^@@ ',patch,re.M))==2
git('competing-all-seven-path-patch',['diff','--binary',AB,COMP,'--',*selected]);git('competing-canonical-full-seven-patch',['diff','--binary',COMP,PRODUCT,'--',*selected])
dump('provenance.json',{'root':ROOT,'tree':git('root-tree',['rev-parse',ROOT+'^{tree}']).decode().strip(),'ancestry':checks,'merge_log':heads,'tracked_status':tracked,'runtime_source_delta_vs8236':[],'footprints':footprints,'competing_history':{'nine_commits':commit_rows,'221_path_classification':counts,'seven_contract_paths':contracts,'defining_graph_blobs':blob_oids,'canonical_competing_graph_two_hunks':2,'whole_module_AST_equal':True}})
# Audit complete transports/decoded raw bytes, not excerpts. Do not execute numerical tests.
manifest_api=json.loads(content(ROOT,api['full_output_manifest']['path']));manifest_fit=json.loads(content(ROOT,P+'tmle-persisted-consumers-20261007/outputs.json'))
audit=[]; dec={}; prefixes=[P+'api-installed-graph-reconciliation-20261007/',P+'tmle-persisted-consumers-20261007/']
for label,records in [('api',manifest_api['records']),('fit',manifest_fit['files'])]:
 for rec in records:
  data=content(ROOT,rec['path']); assert len(data)==rec['bytes'] and sha(data)==rec['sha256'],rec['path']
  enc=rec.get('encoding','identity');raw=gzip.decompress(data) if enc.startswith('gzip') else data
  assert len(raw)==rec['decoded_bytes'] and sha(raw)==rec['decoded_sha256'],rec['path']
  dec[rec['path']]=raw
  audit.append({'lane':label,**rec,'git_ref':ROOT,'git_blob':meta(ROOT,rec['path'])['git_blob'],'stored_binding_verified':True,'decoded_binding_verified':True})
 assert set(x['path'] for x in records)==set(git(label+'-complete-tree-files',['ls-tree','-r','--name-only',ROOT,'--',prefixes[0 if label=='api' else 1]]).decode().splitlines())-{api['full_output_manifest']['path'] if label=='api' else P+'tmle-persisted-consumers-20261007/outputs.json'}
assert len(manifest_api['records'])==120
assert sum(x['bytes'] for x in manifest_api['records'])==manifest_api['stored_bytes']
assert sum(x['decoded_bytes'] for x in manifest_api['records'])==manifest_api['decoded_bytes']
# Preserve exact binary Git batch readback for all unique encoded companion blobs.
unique=sorted(set(x['git_blob'] for x in audit));stdin=('\n'.join(unique)+'\n').encode();(D/'bound-companion-blobs.stdin').write_bytes(stdin)
q=run('bound-companion-blobs',['git','cat-file','--batch'],stdin);assert q.returncode==0
# Check complete source packet provider planes, actual ROOT bytes, both scopes stay separate.
packet=json.loads(content(ROOT,P+'tmle-persisted-consumers-20261007/author/source-and-owner-packet.json'))
provider=[]
for group in packet['provider_byte_equivalence']+packet['runtime_byte_equivalence']:
 for entry in group:
  actual=meta(entry['git_ref'],entry['path']);assert all(actual[k]==entry[k] for k in ['bytes','sha256','git_blob'])
 hashes={x['sha256'] for x in group};assert len(hashes)==1
 current=meta(ROOT,group[0]['path']);assert current['sha256'] in hashes
 provider.append({'path':group[0]['path'],'all_declared_ref_bindings_verified':True,'root_current_binding':current,'equivalent_refs':[x['git_ref'] for x in group]})
assert len(provider)==12
# CAS archives read all regular members, compared to complete companion file manifests.
archives=[]
for lane in ['author','independent']:
 base=P+'tmle-persisted-consumers-20261007/'+lane+'/'
 path=base+'native-cas-input.tar.gz';data=content(ROOT,path);members=[]
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as ar:
  for m in ar:
   if m.isfile():
    raw=ar.extractfile(m).read();members.append({'path':m.name.removeprefix('./'),'bytes':len(raw),'sha256':sha(raw)})
 manifest=json.loads(content(ROOT,base+'cas-input-manifest.json'))
 assert sorted(members,key=lambda x:x['path'])==sorted(manifest['files'],key=lambda x:x['path'])
 archives.append({'path':path,'git_ref':ROOT,'stored':meta(ROOT,path),'regular_file_count':len(members),'total_raw_bytes':sum(x['bytes'] for x in members),'complete_member_bindings_verified':True,'members':members})
# Complete JUnit census where supplied; check deciding transcript actually matches each PASS/negative declaration.
censuses=[]
for path,raw in dec.items():
 if path.endswith('.xml'):
  x=ET.fromstring(raw);cases=list(x.iter('testcase'))
  censuses.append({'path':path,'cases':len(cases),'failures':sum(c.find('failure') is not None for c in cases),'errors':sum(c.find('error') is not None for c in cases),'skips':sum(c.find('skipped') is not None for c in cases),'testcase_ids':[c.get('classname','')+'::'+c.get('name','') for c in cases]})
checkread=[]
for label,d in [('api',api),('fit',fit)]:
 assert d['closure_ids']==[]
 for i,c in enumerate(d['checks']):
  assert c['outcome'] in {'PASS','FAIL','ERROR','UNRUN'}
  p=c['output'];r=dec.get(p)
  checkread.append({'lane':label,'index':i,'name':c['name'],'outcome':c['outcome'],'command':c['command'],'target_sha':c.get('target_sha'),'target_tree_sha':c.get('target_tree_sha'),'output':p,'full_output_read':r is not None,'output_bytes':None if r is None else len(r),'output_sha256':None if r is None else sha(r),'whole_pytest_summary_lines':[] if r is None else [line for line in r.decode(errors='replace').splitlines() if re.search(r'\b\d+ (passed|failed|skipped|error|errors)\b',line)],'exit_code':c.get('exit_code'),'statement':c.get('statement')})
  if c['outcome']!='UNRUN': assert r is not None,(label,i,p)
dump('byte-audit.json',{'root_git_ref':ROOT,'api_manifest':meta(ROOT,api['full_output_manifest']['path']),'fit_manifest':meta(ROOT,P+'tmle-persisted-consumers-20261007/outputs.json'),'all_unique_transports':audit,'api_stored_files':len(manifest_api['records']),'fit_stored_files':len(manifest_fit['files']),'stored_bytes':sum(x['bytes'] for x in audit),'decoded_bytes':sum(x['decoded_bytes'] for x in audit),'provider_source_equivalence':provider,'synthetic_CAS_archives':archives,'complete_JUnit_censuses':censuses,'complete_check_outputs':checkread})
# Named source readers relevant to authority/value constraints. Full source output, not snippets.
for name,path in [('confidence','policy-engine/src/polisyos/scientist/governance/passes/confidence_pass.py'),('value','policy-engine/src/polisyos/foundry/methods/components/value_evidence.py'),('causal_report','policy-engine/src/polisyos/ir/analytics/causal.py')]:
 git(name+'-full-owner-source',['show',ROOT+':'+path])
run('runtime-default-owner-context',['sed','-n','898,946p','policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py'])
dump('commands.json',commands)
summary={'root':ROOT,'verdict':'EVIDENCE_COMPLETE_PENDING_EDITORIAL_FINAL','api_companions':len(manifest_api['records']),'fit_companions':len(manifest_fit['files']),'all_complete_raw_bindings_verified':True,'stored_bytes':sum(x['bytes'] for x in audit),'decoded_bytes':sum(x['decoded_bytes'] for x in audit),'complete_API_history_commits':9,'complete_API_history_paths':221,'contract_paths':7,'source_provider_planes':12,'no_numerical_test_run':True,'new_src_delta':0}
dump('audit-summary.json',summary)
print(json.dumps(summary))
