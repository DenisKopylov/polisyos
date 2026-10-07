"""Freeze the exact passive-dunder delta; do not change earlier review records."""
import hashlib,json,pathlib,subprocess
D=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/workspace/e02-F-api-20261006')
A=pathlib.Path('/tmp/e02-F-continuation-20261006/api')
SHA='a7a96a53894defa6311a0f8d9428bac26e583673'
TREE='360ff1fef25146df16512da35078dc8e95f5c6d8'
PREV='0c6c7efaab3eba502b44bf6471e7a3c675608f2a'
def h(b):return hashlib.sha256(b).hexdigest()
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':h(b),'full':True}
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def check_ref(r):
 b=pathlib.Path(r['path']).read_bytes();assert len(b)==r['bytes'] and h(b)==r['sha256']
names=['native7','independent-controls','independent-controls-corrected','namespace-gate']
records=[]
for n in names:
 row=json.loads((D/(n+'.json')).read_text());assert row['source_sha']==SHA and row['source_tree']==TREE and row['source_begin']==row['source_end']
 assert len(row['source_begin'])==9
 for x in row['source_begin']:
  b=git('show',SHA+':'+x['source_path']);assert len(b)==x['bytes'] and h(b)==x['sha256']
 for x in row['output_refs']:check_ref(x)
 records.append(row)
assert records[0]['exit_code']==records[2]['exit_code']==0
assert records[1]['exit_code']==records[3]['exit_code']==1
assert '7 passed, 1 warning' in (D/'native7.stdout.txt').read_text()
assert '1 failed, 5 passed' in (D/'independent-controls.stdout.txt').read_text()
assert '6 passed' in (D/'independent-controls-corrected.stdout.txt').read_text()
ns=json.loads((D/'namespace-gate.stdout.txt').read_text())
assert ns['entrypoint_count']==ns['unknown_count']==38 and len(ns['canonical_contract_violations'])==38 and ns['explicit_successful_read_count']==103
read_refs=[]
for row in ns['entrypoints']:
 assert row['export_count'] is None and row['known_export_count']==0 and not row['complete']
 for x in row['resolution']['inputs']:
  if x['operation']=='read_bytes' and x['status']=='read':
   b=git('show',SHA+':policy-engine/'+x['path']);assert len(b)==x['bytes'] and h(b)==x['sha256'];read_refs.append(x)
policy=ns['policy_ref'];b=git('show',SHA+':policy-engine/'+policy['source_path']);assert len(b)==policy['bytes'] and h(b)==policy['sha256']
delta=[]
for path in git('diff','--name-only',PREV,SHA).decode().splitlines():
 b=git('show',SHA+':'+path);delta.append({'source_sha':SHA,'source_path':path,'bytes':len(b),'sha256':h(b)})
assert len(delta)==3
decoder=json.JSONDecoder();text=(D/'independent-controls-corrected.stdout.txt').read_text();i=0;controls=[]
while i<len(text):
 j=text.find('{',i)
 if j<0:break
 try:r,e=decoder.raw_decode(text[j:])
 except json.JSONDecodeError:i=j+1;continue
 i=j+e
 if isinstance(r,dict) and 'case' in r:controls.append(r)
assert len(controls)==6
for c in controls:
 if c['case']=='declarative_all_positive':
  assert c['actual_CPython']['returncode']==0 and c['static']['export_count']==1 and not c['canonical_violations']
 else:
  assert c['static']['export_count'] is None and c['static']['known_export_count']==0 and not c['static']['export_resolution']['complete'] and c['canonical_violations']
author=json.loads((A/'passive-protocol-final-frozen.json').read_text());assert author['target_sha']==SHA and author['tree_sha']==TREE and author['exit_code']==0
for k in ['stdout','stderr']:check_ref(author[k])
assert '108 passed, 1 warning' in (A/'passive-protocol-final-frozen.stdout').read_text()
prior=D.with_name('api-review-0c6');old=json.loads((prior/'review.json').read_text());assert old['candidate_sha']==PREV and old['decision']=='GO_bounded_static_profile'
historical_probe=[ref(A/('passive-protocol-binding-probe'+suffix)) for suffix in ['.py','.stdout','.stderr']]
report={
 'reviewer':'graph_scm','role':'independent_read_only_narrow_passive_protocol_delta','check':'PASS','decision':'GO_bounded_passive_dunder_profile','outcome':'limited','candidate_sha':SHA,'candidate_tree':TREE,'delta_predecessor_sha':PREV,'slice_base_sha':'449d32909928caf39382f4ff02ac74b0adf277eb',
 'scope':'Exact three-path delta declaring that passive imported modules and package initializers have no explicit dunder binding except declarative __all__. Same finite pure grammar, no new runtime interpreter or scientific algorithm.',
 'source_bindings':records[0]['source_begin'],'delta_source_refs':delta,'source_begin_end_check':'PASS','canonical_policy_ref':policy,'explicit_source_read_refs':read_refs,
 'findings':[],
 'checks':[
  {'name':'Fresh exact two native functions/new seven cases','check':'PASS','outcome':'limited','passed':7,'failed':0,'skip':0,'error':0,'warnings':1,'output':str(D/'native7.stdout.txt')},
  {'name':'Independent Assign/AnnAssign/import-alias and initializer actual import consumers','check':'PASS','outcome':'limited','passed':6,'failed':0,'skip':0,'error':0,'output':str(D/'independent-controls-corrected.stdout.txt'),'scope':'Three module cases actually raise child TypeError; static rejects all three before canonical gate. Owner and parent initializer bindings are conservatively UNKNOWN even when this concrete import succeeds. Declarative __all__ in passive owner/parent remains supported complete1/nativeStaticName.'},
  {'name':'Initial package-protocol native oracle assumption','check':'ERROR','outcome':'limited','raw_pytest_failed':1,'raw_pytest_passed':5,'output':str(D/'independent-controls.stdout.txt'),'scope':'Reviewer expected package owner.__getattr__=[] to be invoked for existing PASSIVE. Actual package has __path__ and import succeeds. Static UNKNOWN was already correct. Original unchanged script and full raw FAIL retained; distinct corrected script changes only expected child success for that case.'},
  {'name':'Actual canonical 38-entrypoint public predicate','check':'FAIL','outcome':'limited','incomplete_rows':38,'unknown_rows':38,'exit_code':1,'output':str(D/'namespace-gate.stdout.txt'),'scope':'Expected conservative incompleteness retained; zero namespace not inferred, no full architecture/generated inventory PASS.'},
  {'name':'All explicit recorded source reads and canonical selector bind Git bytes','check':'PASS','outcome':'limited','successful_source_reads':103,'entrypoints':38,'output':str(D/'namespace-gate.stdout.txt')},
  {'name':'Author full final selector observation','check':'PASS','outcome':'limited','role':'author_execution_independently_inspected_not_reexecuted','passed':108,'failed':0,'skip':0,'error':0,'warnings':1,'output':str(A/'passive-protocol-final-frozen.stdout')},
 ],
 'controlled_native_static_records':controls,'executions':records,'author_full_selector':{'execution':author,'execution_ref':ref(A/'passive-protocol-final-frozen.json'),'spec_ref':ref(A/'passive-protocol-final-frozen-spec.json')},
 'prior_go_preserved':{'role':'historical_non_deciding_for_current_profile','review_ref':ref(prior/'review.json'),'selection_ref':ref(prior/'transfer-selection.json'),'original_decision':'GO_bounded_static_profile','limitation':'Later actual literal-dunder counterexample refutes an additional passive-protocol assumption beyond those previously measured controls. Old report bytes and scientific/install/source identity observations are unchanged, not a current closure basis.'},
 'original_dunder_failure':{'role':'author_historical_actual_falsifier','source_sha':PREV,'check':'FAIL','outcome':'open_at_historical_source','full_refs':historical_probe,'scope':'Original probe prints source and actual CPython child TypeError versus staticcomplete1/canonicalnone. Probe predates dedicated execution metadata; use as observed author evidence, not fabricated independent source begin/end receipt. Current independent exact-source controls separately reproduce actual TypeError and typed refusal.'},
 'related_finding_ids':['LA-020','LA-007','LA-019'],'closure_ids':[],
 'limits':['Only the exact generic passive binding profile is admitted; no universal Python interpreter.', 'All dependency/ancestor functions/classes and explicit dunder bindings except declarative __all__ remain outside profile; unexpected OSError/Syntax/unexpectedValueError error policy unchanged by this delta.', 'Canonical all38UNKNOWN/incompleteFAIL retained, candidates analytics278/world41 remain unproved and actual nativeworld59 is separate.', 'Earlier source0c6 hashseed/relocation measurements remain exact historical evidence; no current-source rerun or byte equivalence invented after selector-text change.', 'No wheel/sdist/scientific/real-data/backend/authority or G acceptance closure; full architecture and inventory snapshot remain UNRUN by reviewer.', 'Source trees bound before/after every native execution; reader source hold released after all reads/tests complete, report uses immutable Git blobs thereafter. No product or environment mutation.'],
 'author_hold_release':'Pinned a7 source reads and controlled native runs complete. Author may proceed with root-authorized packaging/root merge/generated inventory work. This GO preserves canonical38incompleteFAIL.',
}
(D/'review.json').write_text(json.dumps(report,indent=2)+'\n')
files=[D/'review.json',D/'finish_review.py',D/'run_check.py',D/'measure_namespace_gate.py',D/'test_passive_protocol_profile.py',D/'test_passive_protocol_profile_corrected.py']
for name in names:files.extend([D/(name+'.json'),D/(name+'.stdout.txt'),D/(name+'.stderr.txt')])
files.extend([A/('passive-protocol-final-frozen'+suffix) for suffix in ['.json','-spec.json','.stdout','.stderr']])
files.extend([pathlib.Path(x['path']) for x in historical_probe])
assert len(files)==len(set(files))
selection={'source_sha':SHA,'source_tree':TREE,'check':'PASS','decision':'GO_bounded_passive_dunder_profile','unique_full_files':len(files),'items':[ref(p) for p in files],'separately_preserved_historical_selection':ref(prior/'transfer-selection.json')}
selection['full_bytes']=sum(x['bytes'] for x in selection['items'])
(D/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':ref(D/'review.json'),'selection':ref(D/'transfer-selection.json'),'full_files':len(files),'full_bytes':selection['full_bytes']}))
