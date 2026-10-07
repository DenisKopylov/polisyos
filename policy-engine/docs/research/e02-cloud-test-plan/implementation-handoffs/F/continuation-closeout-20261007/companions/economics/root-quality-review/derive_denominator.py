import collections,hashlib,json,pathlib,subprocess,tomllib
D=pathlib.Path('/tmp/e02-F-continuation-20261007/economics/root-quality-review'); R=pathlib.Path('/workspace/e02-F-closeout-20261006');Q=pathlib.Path('/tmp/e02-F-continuation-20261007/root-quality')
CUR='b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a';BASE='072d45a56d1119fe3e7665cec2cbbdca015d2934';PRODUCT='8236d9c368336a5ea20c1586f29aea7321db6536';commands=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,d):(D/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def cmd(n,a):
 q=subprocess.run(a,cwd=R,capture_output=True);(D/(n+'.stdout')).write_bytes(q.stdout);(D/(n+'.stderr')).write_bytes(q.stderr);commands.append(dict(name=n,argv=a,cwd=str(R),exit_code=q.returncode,stdout=dict(path=n+'.stdout',bytes=len(q.stdout),sha256=sha(q.stdout)),stderr=dict(path=n+'.stderr',bytes=len(q.stderr),sha256=sha(q.stderr))));assert q.returncode==0;return q.stdout
def git(n,a):return cmd(n,['git',*a])
def read_tree(ref):
 raw=git('full-path-list-'+ref[:8],['ls-tree','-rz','--name-only',ref]);names=[s.decode() for s in raw.split(b'\0') if s]
 paths=[s for s in names if s.startswith(('policy-engine/src/','policy-engine/tools/','policy-engine/tests/')) and s.endswith('.py')]
 # Exact same utf-8-sig/json sort serialization as canonical scanner; no AST traversal or scanner invocation.
 query_paths=paths+['policy-engine/pyproject.toml'];request=''.join(ref+':'+p+'\n' for p in query_paths).encode();process=subprocess.run(['git','cat-file','--batch'],cwd=R,input=request,capture_output=True);assert process.returncode==0
 offset=0;sources={};entries=[];manifest={}
 for p in query_paths:
  end=process.stdout.index(b'\n',offset);header=process.stdout[offset:end].split();offset=end+1;assert header[1]==b'blob';size=int(header[2]);b=process.stdout[offset:offset+size];offset+=size+1;entries.append(dict(path=p,git_blob=header[0].decode(),bytes=len(b),sha256=sha(b)))
  if p.endswith('pyproject.toml'):manifest=tomllib.loads(b.decode('utf-8-sig'))
  else:sources[p.removeprefix('policy-engine/')]=b.decode('utf-8-sig')
 assert offset==len(process.stdout)
 dump('source-byte-manifest-'+ref[:8]+'.json',entries)
 commands.append(dict(name='complete-read-tree-'+ref[:8],argv=['git','cat-file','--batch'],cwd=str(R),stdin_queries=ref+':{each complete Python path plus pyproject.toml}',stdin_bytes=len(request),stdin_sha256=sha(request),exit_code=0,stdout_bytes=len(process.stdout),stdout_sha256=sha(process.stdout),output_policy='Read complete source blobs in memory; original immutable Git bytes are not copied into reviewer evidence. Complete path/blob/size/SHA manifests and exact hash protocol retained.',stderr_bytes=len(process.stderr),stderr_sha256=sha(process.stderr)))
 return names,sources,entries,manifest
allcur,cur,curmeta,cp=read_tree(CUR);allbase,base,basemeta,bp=read_tree(BASE)
receipt=json.loads((Q/'invocation-full.json').read_bytes());expected=receipt['denominator'];curhash=sha(json.dumps(cur,sort_keys=True).encode());basehash=sha(json.dumps(base,sort_keys=True).encode());assert len(cur)==expected['current_files'] and len(base)==expected['base_files'] and curhash==expected['current_sha256'] and basehash==expected['base_sha256']
C=set(cur);B=set(base);same=sorted(p for p in C&B if cur[p]==base[p]);changed=sorted(p for p in C&B if cur[p]!=base[p]);added=sorted(C-B);deleted=sorted(B-C)
assert len(added)==5 and len(changed)==4 and not deleted
full_delta=git('full-072-to-b5-delta',['diff','--name-status',BASE,CUR]).decode();delta=[s.split('\t') for s in full_delta.splitlines()]
for label,paths in [('python','policy-engine/src'),('schema','policy-engine/schemas'),('manifest','policy-engine/pyproject.toml')]:git('delta-'+label,['diff','--binary',BASE,CUR,'--',paths])
bytype=collections.Counter((''.join(pathlib.PurePosixPath(p).suffixes) or '<none>') for x in delta for p in [x[-1]])
scoped_all=[p for p in allcur if p.startswith(('policy-engine/src/','policy-engine/tools/','policy-engine/tests/'))]
nonpy=[p for p in scoped_all if not p.endswith('.py')]
summary=dict(schema='policyos.e02.full_scanner_denominator_review.v1',source_sha=CUR,base_sha=BASE,canonical_scanner_source='policy-engine/src/polisyos/runtime/quality/production_invocation.py',exact_hash_serialization='sha256(json.dumps({relative product Python path:git blob decodedutf-8-sig},sort_keys=True).encode())',current=dict(files=len(cur),by_prefix=dict(collections.Counter(p.split('/')[0] for p in cur)),sha256=curhash),base=dict(files=len(base),by_prefix=dict(collections.Counter(p.split('/')[0] for p in base)),sha256=basehash),overlap=dict(shared_paths=len(C&B),identical_bytes=len(same),modified_existing=len(changed),added=len(added),deleted=len(deleted),modified_paths=changed,added_paths=added,full_common_path_denominator='complete base5949 current5954 overlap5949; not disjoint'),filetype_scope=dict(all_tracked_paths=len(allcur),all_scoped_src_tools_tests_paths=len(scoped_all),python_included=len(cur),nonpython_excluded=len(nonpy),nonpython_suffix_counts=dict(collections.Counter(''.join(pathlib.PurePosixPath(p).suffixes) or '<none>' for p in nonpy))),full_actual_delta=dict(paths=len(delta),filetype_counts=dict(bytype),scanner_included_changed_paths=[x for x in delta if x[-1].removeprefix('policy-engine/') in set(changed+added)]),entry_manifest=dict(current_scripts=cp.get('project',{}).get('scripts',{}),base_scripts=bp.get('project',{}).get('scripts',{}),scripts_equal=cp.get('project',{}).get('scripts',{})==bp.get('project',{}).get('scripts',{}),manifest_hash_excluded_from_sources_dictionary_but_read_for_entry_roots=True),global_result=dict(exit_code=3,status='UNRESOLVED',coverage=receipt['coverage'],mechanisms=len(receipt['mechanisms']),status_counts=dict(collections.Counter(x['status'] for x in receipt['mechanisms'].values())),regressions=receipt['regressions'],new_unresolved=receipt['new_unresolved_by_construction'],new_function_records={p:receipt['mechanisms'][p] for p in receipt['new_unresolved_by_construction']},unresolved_receivers=len(receipt['unresolved_receiver_calls']),root_count=receipt['root_count'],runtime_invocation_established=False,unmeasured=receipt['unmeasured']),P41='not_established; exact new scanner result has changed source overlap and is partial; historical8236 red cannot be relabeled inherited/discharged by selective9pathformat/native proof.')
dump('denominator.json',summary);dump('complete-overlap-paths.json',dict(shared_paths=sorted(C&B),identical_paths=same,modified_paths=changed,added=added,deleted=deleted,excluded_scoped_non_python=nonpy));dump('full-delta-paths.json',delta)
# Bind and preserve complete moderate current outputs. Large fullscanner receipt stays original, hashed and parsed completely.
inputs=[]
for p in sorted(Q.iterdir()):
 if p.is_file():
  raw=p.read_bytes();inputs.append(dict(path=str(p),bytes=len(raw),sha256=sha(raw),fully_read=True,transport='original-local lossless full receipt; no duplicate171MB' if p.name=='invocation-full.json' else 'copied exact moderate output'))
  if p.name!='invocation-full.json':(D/('current-'+p.name)).write_bytes(raw)
dump('full-input-bindings.json',inputs)
# Capture exact immutable native Graph647 source chain receipt from owner Gitref rather than wrong rootcode-only carrier.
G='/workspace/e02-F-graph-20261006';graph_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=G,text=True).strip()
path='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-intake-current-content-20261007.json'
raw=git('graph-owner-receipt',['show',graph_head+':'+path]);graph=json.loads(raw);dump('graph-native-chain-separate.json',dict(owner_receipt_ref=graph_head,receipt_path=path,receipt_bytes=len(raw),receipt_sha256=sha(raw),candidate_sha=graph.get('candidate_sha',graph.get('candidate_source_sha')),candidate_tree=graph.get('candidate_tree_sha'),checks=graph['checks'],independent_review=graph.get('independent_review'),scope='Existing genuine native source-bound producer→persist→current CAS/Scientist chain; not a repeat here, not a rewrite of staticglobalUNRESOLVED. No identification/EMPserved authority inferred.'))
for name,path in [('EMP-card','policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/EMP-01.md'),('A-coverage','policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json'),('A-decisions','policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/A.md'),('EMP-native-test','policy-engine/tests/unit/remediation/test_emp_01.py'),('scanner-full-source','policy-engine/src/polisyos/runtime/quality/production_invocation.py')]:git(name,['show',CUR+':'+path])
# Full consumer function from exact immutable Git blob; body is standalone sufficient exact footprint.
owner=git('generation-cycle-full-source',['show',CUR+':policy-engine/src/polisyos/runtime/quality/generation_cycle.py']).decode();lines=owner.splitlines(keepends=True);(D/'generation-selection-function.txt').write_text(''.join(lines[10575:10669]));assert 'def _build_candidate_selection_diagram' in ''.join(lines[10575:10669])
dump('commands.json',commands);print(json.dumps({'current':summary['current'],'base':summary['base'],'overlap':{k:v for k,v in summary['overlap'].items() if not isinstance(v,list)},'full_delta_count':len(delta),'graph_owner_head':graph_head}))
