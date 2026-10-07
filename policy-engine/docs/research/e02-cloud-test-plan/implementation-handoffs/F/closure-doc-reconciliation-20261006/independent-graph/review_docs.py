"""Independent immutable doc/card/receipt reconciliation; no scientific execution."""
import collections,csv,hashlib,io,json,pathlib,re,subprocess,sys
R=pathlib.Path('/workspace/e02-F-economics-20261006');D=pathlib.Path(__file__).resolve().parent
SHA='99f196be45dec7acabdc05f0cb3af5430ec94c9e';TREE='18711c5732863a4e50672112c7f3c5ba4a1b229b';BASE='d9c48853c5ab9ad7473df204bf3a7a1995a32057';ROOT='53afa776'
P='policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/'
H='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/'
E=pathlib.Path('/tmp/e02-F-continuation-20261006/economics/docs-reconciliation')
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def h(b):return hashlib.sha256(b).hexdigest()
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':h(b),'full':True}
def source(sha,path):
 b=git('show',sha+':'+path);return {'source_sha':sha,'source_path':path,'bytes':len(b),'sha256':h(b)}
assert git('rev-parse','HEAD').decode().strip()==SHA and git('rev-parse','HEAD^{tree}').decode().strip()==TREE
working_status_begin=git('status','--porcelain').decode();assert not git('diff','--name-only');paths=git('diff','--name-only',BASE,SHA).decode().splitlines();assert set(paths)=={P+x for x in ['F.md','method-decisions.md','runtime-profiles.md']}
cur={x:git('show',SHA+':'+P+x).decode() for x in ['F.md','method-decisions.md','runtime-profiles.md']}
old={x:git('show',BASE+':'+P+x).decode() for x in cur}
for x in cur:
 assert (R/(P+x)).read_bytes()==cur[x].encode()
 assert git('show',ROOT+':'+P+x)==old[x].encode()
mc=cur['method-decisions.md'];mo=old['method-decisions.md'];rc=cur['runtime-profiles.md'];ro=old['runtime-profiles.md']
assert mc[mc.index('<a id="methods-c"></a>'):mc.index('<a id="methods-f"></a>')]==mo[mo.index('<a id="methods-c"></a>'):mo.index('<a id="methods-f"></a>')]
assert rc[rc.index('## C —'):rc.index('<a id="f-current-runtime"></a>')].rstrip()==ro[ro.index('## C —'):ro.index('## F —')].rstrip()
for n in range(1,17):assert mc.count(f'<a id="f-m{n}"></a>')==1
for u in ['C','D','E']:
 assert next(x for x in rc.splitlines() if x.startswith('| '+u+' |'))==next(x for x in ro.splitlines() if x.startswith('| '+u+' |'))
org='policy-engine/docs/research/e02-cloud-test-plan/execution-organization/'
owners=list(csv.DictReader(io.StringIO(git('show','198076863e143dea9f89f02734b13d50dae3eed5:'+org+'finding-owners.tsv').decode()),delimiter='\t'))
fids={x['finding_id'] for x in owners if x['unit']=='F'};assert len(fids)==35
rows=[]
for line in cur['F.md'].splitlines():
 m=re.match(r'\| (B\d+|LA-\d+) \| (.*?) \| (.*?) \|$',line)
 if m: rows.append({'finding_id':m[1],'criterion_and_recommendation':m[2],'source_and_limit':m[3]})
assert len(rows)==35 and {r['finding_id'] for r in rows}==fids
outcomes=collections.Counter(re.search(r'; (closed|limited|held)$',r['criterion_and_recommendation'])[1] for r in rows);assert dict(outcomes)=={'closed':21,'limited':13,'held':1}
c=json.loads(git('show',SHA+':'+P+'coverage.json'));f=[x for x in c['findings'] if x['unit']=='F'];assert {x['id'] for x in f}==fids
cards=[];distinct=set()
for item in f:
 for x in item['criterion_refs']:
  path=c['criterion_documents'][x['document']]['path'];b=git('show','198076863e143dea9f89f02734b13d50dae3eed5:'+path)
  block=b''.join(b.splitlines(keepends=True)[x['lines'][0]-1:x['lines'][1]])
  assert h(block)==x['sha256'];distinct.add((path,*x['lines']))
  cards.append({'finding_id':item['id'],'source_sha':'198076863e143dea9f89f02734b13d50dae3eed5','source_path':path,'lines':x['lines'],'bytes':len(block),'sha256':h(block),'title':block.decode().splitlines()[0]})
assert len(cards)==36 and len(distinct)==35
bundles=[x for x in c['bundles'] if x['unit']=='F'];assert len(bundles)==17
for x in bundles:assert cur['F.md'].count('<a id="bundle-'+x['id'].lower()+'"></a>')==1
registry=json.loads((E/'source-receipts.json').read_text());assert len(registry)==10;receipts={};receipt_bindings=[]
for x in registry:
 b=git('show',x['git_ref']+':'+x['path']);assert len(b)==x['bytes'] and h(b)==x['sha256'];o=json.loads(b);receipts[x['key']]=(x,o)
 assert o['implementation_commits']==x['implementation_commits'] and o['candidate_tree_sha']==x['candidate_tree_sha']
 assert git('rev-parse',x['implementation_commits'][-1]+'^{tree}').decode().strip()==x['candidate_tree_sha']
 assert x['sha256'] in cur['F.md'] and str(x['bytes']) in cur['F.md']
 assert all(k in z for z in o['checks'] for k in ['command','target_sha','environment','input_closure','outcome','output'])
 receipt_bindings.append({**x,'checks':len(o['checks']),'full_json_read_and_hash_check':'PASS'})
assert sum(x['checks'] for x in receipt_bindings)==148
# Every explicit path@Git-carrier citation in F is actually read, not inferred from a prefix.
citations=[]
for name,head in re.findall(r'F/([A-Za-z0-9_-]+\.json)@([0-9a-f]{40})',cur['F.md']):
 b=git('show',head+':'+H+'F/'+name);o=json.loads(b)
 citations.append({'artifact_git_ref':head,'path':H+'F/'+name,'bytes':len(b),'sha256':h(b),'candidate_tree_sha':o.get('candidate_tree_sha'),'checks':len(o.get('checks',[]))})
assert len(citations)==16
cache_path=H+'F/graph-cache-immutability-20261006.json';cache_head='bf335dd687c313fda9001fa3bb1365df6bc5ae1f'
cache_body=git('show',cache_head+':'+cache_path);cache=json.loads(cache_body)
citations.append({'artifact_git_ref':cache_head,'path':cache_path,'bytes':len(cache_body),'sha256':h(cache_body),'candidate_tree_sha':cache.get('candidate_tree_sha'),'checks':len(cache.get('checks',[])),'locator_basis':'Doc explicitly says this receipt on the same carrier as preceding source-bound SCM citation.'})
x,did=receipts['cau_science'];didraw=git('show',x['git_ref']+':'+did['checks'][3]['output']);j=json.loads(didraw);text=j['text'];raw=text.encode();assert len(raw)==j['decoded_bytes'] and h(raw)==j['decoded_sha256']
assert all(s in text for s in ["'known_DGP_repetitions': 160","'null_rejected': 6","'null_covered': 154","'alternative_rejected': 160","'alternative_covered': 154"])
x,rdd=receipts['rdd'];rddout=json.loads(git('show',x['git_ref']+':'+rdd['checks'][1]['output']));rem=json.loads(git('show',x['git_ref']+':'+rdd['checks'][2]['output']))
assert rddout['case_count']==4036 and rddout['differential_failure_count']==0 and [a['covered'] for a in rddout['coverage']]==[1879,1877]
assert all(a['replicates']==2000 for a in rddout['coverage']) and rddout['maximum_abs_differences']['ci']==3.658229275060876e-11
assert rem['case_count']==4036 and rem['differential_failure_count']==12108 and [a['covered'] for a in rem['coverage']]==[1687,1676]
rddsrc=git('show','fb022aa12599ee1617f83d154cd9a8027b2a58b8:policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py');assert h(rddsrc)==rddout['product_source_sha256'];assert b'import rdrobust' not in rddsrc and b'from rdrobust' not in rddsrc
sampler=git('show','6dcb792b6f8c2d2dcfc04a5e04ea33135a2ad181:policy-engine/tests/unit/foundry/methods/catalog/causal/test_scm_result_semantics.py').decode();assert '0.5 * math.erfc' in sampler and 'sf(lo) - sf(value)' in sampler
original=pathlib.Path('/tmp/e02-F-continuation-20261006/cau/original35-reconciliation.json');assert len(original.read_bytes())==235804 and h(original.read_bytes())=='95f728b758fde25591b0124bc0a2cd8b6c0acd86a61deb6d13bc07e99c4ba2a7'
draft=json.loads((E/'current35-doc-ledger-draft.json').read_text());assert draft['technical_proposal_counts']=={'closed':26,'limited':8,'held':1} and draft['current_continuation_proposal_counts']==dict(outcomes)
assert draft['scientific_reruns'] is False and all(r['authority_or_G_acceptance']=='UNRUN' for r in draft['rows'])
summary={'check':'PASS','scope':'Independent docs-only semantic/card/receipt reconciliation, not scientific rerun or G acceptance','candidate_sha':SHA,'candidate_tree':TREE,'slice_base_sha':BASE,'changed_paths':paths,'source_refs':[source(SHA,p) for p in paths],'base_three_blobs_identical_root53afa776':True,'nonF_C_D_E_section_bytes_unchanged':True,'F_method_anchors':16,'F_bundle_anchors':17,'original_finding_IDs':35,'original_bindings':36,'unique_original_card_blocks':35,'document_current_continuation_recommendation_counts':dict(outcomes),'technical_proposal_counts':draft['technical_proposal_counts'],'current_receipt_registry':receipt_bindings,'current_registry_check_denominator':148,'explicit_F_receipt_citation_bindings':citations,'original_card_bindings':cards,'actual_DID_wave':{'scientific_source':did['checks'][3]['target_sha'],'original_counts':{'datasets_each_arm':160,'null_coverage':154,'alternative_coverage':154,'null_rejections':6,'alternative_rejections':160},'source0b_diagnostics_not_wave_relabel':True},'actual_RDD_wave':{'product_source':'fb022aa12599ee1617f83d154cd9a8027b2a58b8','product_module_sha256':h(rddsrc),'scientific_original_target':rdd['checks'][1]['target_sha'],'actual_external_differential_cases':4036,'coverage_each_arm':2000,'covered':[1879,1877],'removal_numeric_failures':12108,'removal_covered':[1687,1676],'GPL_development_oracle_not_product_prerequisite':True},'B225_independence':'math.erfc and SF differences vs SciPy sampler; actual immutable test inspected','LA004_original_property':'DISTINCT economic models with equal-regime and deliberate-inequivalence/accounting/seed/observable controls; current Gini remains separately scoped, not substitution for LA004 or LA035 intent.','G_acceptance':'UNRUN','scientific_reruns':False,'source_begin_end_stable':True,'working_status_begin':working_status_begin,'working_status_end':git('status','--porcelain').decode(),'untracked_receipt_companions_outside_frozen_product_scope':True}
assert git('rev-parse','HEAD').decode().strip()==SHA and git('rev-parse','HEAD^{tree}').decode().strip()==TREE and not git('diff','--name-only')
(D/'deciding-output.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'check':'PASS','source':SHA,'full_deciding_output':ref(D/'deciding-output.json'),'source_paths':3,'registry_receipts':10,'registry_checks':148,'IDs':35,'unique_source_cards':35,'anchors':16,'recommendations':dict(outcomes)}))
