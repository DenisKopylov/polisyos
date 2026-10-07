"""Freeze independent pure-import-profile and output-determinism review."""
import hashlib,json,pathlib,subprocess
D=pathlib.Path(__file__).resolve().parent;R=pathlib.Path('/workspace/e02-F-api-20261006')
SHA='35b1808c63fa84dd0555ff9043e0aaffe9831e7b';TREE='0002a76b106d74a3bc5fb341b578c1093e6c193c';PREV='fd36b2f66d7226e001b4e96bf78f019841da6541'
def h(b):return hashlib.sha256(b).hexdigest()
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':h(b),'full':True}
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
names=['native95','effect-boundary','root-probe','namespace-gate','import-profile','import-profile-corrected','determinism'];records=[]
for n in names:
 r=json.loads((D/(n+'.json')).read_text());assert r['source_sha']==SHA and r['source_tree']==TREE and r['source_begin']==r['source_end']
 for s in r['source_begin']:
  b=git('show',SHA+':'+s['source_path']);assert len(b)==s['bytes'] and h(b)==s['sha256']
 for o in r['output_refs']:
  b=pathlib.Path(o['path']).read_bytes();assert len(b)==o['bytes'] and h(b)==o['sha256']
 records.append(r)
assert '1 failed, 94 passed, 1 warning' in (D/'native95.stdout.txt').read_text()
assert '9 passed' in (D/'effect-boundary.stdout.txt').read_text()
assert '2 failed, 5 passed' in (D/'import-profile-corrected.stdout.txt').read_text()
ns=json.loads((D/'namespace-gate.stdout.txt').read_text());assert ns['entrypoint_count']==38 and ns['unknown_count']==38 and len(ns['canonical_contract_violations'])==38
for row in ns['entrypoints']:
 assert row['export_count'] is None and row['known_export_count']==0 and not row['complete']
 for x in row['resolution']['inputs']:
  if x['operation']=='read_bytes' and x['status']=='read':
   b=git('show',SHA+':policy-engine/'+x['path']);assert len(b)==x['bytes'] and h(b)==x['sha256']
assert ns['explicit_successful_read_count']==109
proof=json.loads((D/'generation-portability-probe.json').read_text());assert not proof['byte_equal'] and len(proof['differing_entrypoints'])==11
for c in proof['checks']:
 for k in ['stdout','stderr']:
  o=c[k];b=pathlib.Path(o['path']).read_bytes();assert len(b)==o['bytes'] and h(b)==o['sha256']
source_delta=[]
for p in git('diff','--name-only',PREV,SHA).decode().splitlines():
 b=git('show',SHA+':'+p);source_delta.append({'source_sha':SHA,'source_path':p,'bytes':len(b),'sha256':h(b)})
assert len(source_delta)==4
report={
 'reviewer':'graph_scm','role':'independent_read_only_finite_profile_review','check':'FAIL','decision':'BLOCK','outcome':'open','candidate_sha':SHA,'candidate_tree':TREE,'slice_base_sha':'449d32909928caf39382f4ff02ac74b0adf277eb','delta_predecessor_sha':PREV,
 'scope':'The selected finite pure-declaration/import-owner profile, actual canonical gate and generated output determinism; not a general Python interpreter, runtime installed ABI closure or scientific/authority acceptance.',
 'source_bindings':records[0]['source_begin'],'delta_source_refs':source_delta,'begin_end_full_bindings':'PASS',
 'findings':[
  {'id':'API-STATIC-LOCAL-IMPORT-PROTOCOL','priority':'P2','confidence':'high','bucket':'SAME P40 unresolved implicit import-time effect class one level deeper','check':'FAIL','outcome':'open',
   'property':'A local source is admitted as pure only when its actual import-time profile cannot invoke excluded callback bodies and silently change the selected namespace.',
   'actual_path':'Real File-reader→_StaticExportResolver local ImportFrom/passive-owner admission→render_public_surface_json→canonical _check_public_surface_contracts; independent fresh CPython-I controlled file import supplies different actual namespace.',
   'smallest_divergent_case':'Owner defines PASSIVE=1 and __getattr__. from .owner import PASSIVE still invokes owner.__getattr__(__path__) in genuine CPython import. Callback body rebinds builtins.sorted before top-level sorted(M). Reader excludes body and grants complete=True, export_count1, exportsStaticName, canonicalviolations[]; actualnative exportsRuntimeShadow.',
   'sibling':'Missing from-owner builtin len is incorrectly accepted as actual owner binding by _passive_binding builtin fallback; absent-name callback executes and also changes actual namespace.',
   'actual_results':{'negative_cases_failed':2,'supported_no_hook_same_import_positive_passed':1,'function_header_default_unknown_controls_passed':4,'native_namespace':['RuntimeShadow'],'static_namespace':['StaticName'],'static_complete':True,'canonical_violations':[]},
   'replayer_ref':ref(D/'test_import_profile_corrected.py'),'execution_ref':ref(D/'import-profile-corrected.json'),'full_deciding_output_ref':ref(D/'import-profile-corrected.stdout.txt'),
   'next_owner':'causal_api; generic import-owner purity boundary must cover implicit import protocol and distinguish builtins in expression/header context from an actual named owner import. Do not infer purity from existing imported name alone.'},
  {'id':'API-GENERATED-OUTPUT-DETERMINISM','priority':'P2','confidence':'high','bucket':'NEW generated-output determinism/portable locator class','check':'FAIL','outcome':'open',
   'property':'Same immutable Git source/profile must produce identical public-surface JSON bytes independent of Python hash seed or workspace path.',
   'actual_results':{'fresh_process_hash_seeds':['1','2'],'full_JSON_byte_equal':False,'differing_entrypoints':11,'source_fixed':SHA,'absolute_source_locators_present':True},
   'cause':'Second audit phase iterates a set of source paths, making first refusal reason/order vary; typed messages include absolute worktree paths. Independent native95 gets94PASS1reasonFAIL while author95PASS is also source-specific observed output.',
   'replayer_ref':ref(D/'generation_portability_probe.py'),'proof_ref':ref(D/'generation-portability-probe.json'),'execution_ref':ref(D/'determinism.json'),'next_owner':'causal_api sorted generic source queue and stable repo-relative bounded locators; no exception/check weakening.'}
 ],
 'checks':[
  {'name':'Original e576 three controls and fd36 baredecorator plus same literal +unexpected errors','check':'PASS','outcome':'limited','passed':9,'output':str(D/'effect-boundary.stdout.txt'),'scope':'Allfour original effects now typedUNKNOWN before actual canonical gate; OSError/SyntaxError/unexpectedValueError/TypeError same exceptions propagate.'},
  {'name':'Same frozen native95 selector','check':'FAIL','outcome':'open','passed':94,'failed':1,'skip':0,'error':0,'warnings':1,'output':str(D/'native95.stdout.txt'),'scope':'UNKNOWN reason expectedRaise vsactualpassivebinding demonstrates unstable source audit order; not a numerical/scientific failure.'},
  {'name':'Actual pure-header/default profile and localimport native falsifier','check':'FAIL','outcome':'open','passed':5,'failed':2,'skip':0,'error':0,'output':str(D/'import-profile-corrected.stdout.txt')},
  {'name':'Original root mutator/alias/builtin-shadow cases and literal positive','check':'PASS','outcome':'limited','output':str(D/'root-probe.stdout.txt')},
  {'name':'Complete canonical supported-entrypoint representation/full109explicitread bytes','check':'PASS','outcome':'limited','entrypoints':38,'source_successful_reads':109,'output':str(D/'namespace-gate.stdout.txt')},
  {'name':'Actual canonical selected public-surface predicate','check':'FAIL','outcome':'limited','incomplete_rows':38,'output':str(D/'namespace-gate.stdout.txt'),'scope':'Declared conservative grammar can honestly refuse all38rows; deliberatefutureexternalUNKNOWN accepted, no falsezero or complete claim. This expected gate red differs from the localimport false-complete escape.'},
  {'name':'Declared candidates retain source meanings apart from native ABI','check':'PASS','outcome':'limited','analytics_candidates':278,'actual_analytics_native':278,'world_candidates':41,'actual_world_native':59,'static_known':0,'static_total':None,'complete':False,'output':str(D/'namespace-gate.stdout.txt')},
  {'name':'Fresh process hashseed differential whole JSON bytes','check':'FAIL','outcome':'open','differing_entrypoints':11,'output':str(D/'generation-portability-probe.json')},
  {'name':'Original reviewer local fixture lacks regular root and selects installed package','check':'ERROR','outcome':'limited','raw_pytest_failed':3,'header_control_passed':4,'output':str(D/'import-profile.stdout.txt'),'scope':'Harness constructor/source setup error, not candidate defect. Exact original script/raw retained; corrected root and native-I child remove installed shadow.'}
 ],
 'executions':records,'hash_seed_full_JSON_outputs':[x[k] for x in proof['checks'] for k in ['stdout','stderr']],
 'historical_fd36_block':{'review_ref':ref(D.with_name('api-review-fd36')/'review.json'),'transfer_selection_ref':ref(D.with_name('api-review-fd36')/'transfer-selection.json'),'role':'historical_non_deciding; original baredecorator now separatelyreplayed at35PASS'},
 'related_finding_ids':['LA-020','LA-007','LA-019'],'closure_ids':[],
 'limits':['No old scientific/wheel ABI wave relabelled on newsource.','HumanDecisionRecord/DDM native identities tested in actualexisting95 source independently fromUNKNOWNnamespaceformat, not complete metadata proof.','Generated inventory snapshot/fullarchitecture notgreen or updated byreviewer.','All candidate source reads and process-local numeric-free tests complete; no productwrites/environmentmutation.','No new general arbitraryPython escapecommission; decisivecounterexample is inside newdeclaredlocalImportFrom ownerprofile.','No G acceptance or authority/real-data assumption established.'],
 'author_hold_release':'All pinned35 source reads/tests complete. Author may forward root-authorized generic corrections; preserve exact prior95 author/94+1 reviewer observations and actual2FAIL nativeimport outputs.'
}
(D/'review.json').write_text(json.dumps(report,indent=2)+'\n')
files=[D/'review.json',D/'finish_review.py',D/'run_check.py',D/'root-probe-current.py',D/'root-probe-results.json',D/'test_implicit_function_effect.py',D/'test_import_profile.py',D/'test_import_profile_corrected.py',D/'measure_namespace_gate.py',D/'generation_portability_probe.py',D/'generation-portability-probe.json']
for n in names:
 files += [D/(n+'.json'),D/(n+'.stdout.txt'),D/(n+'.stderr.txt')]
for c in proof['checks']:
 for k in ['stdout','stderr']:files.append(pathlib.Path(c[k]['path']))
assert len(files)==len(set(files));selection={'source_sha':SHA,'source_tree':TREE,'check':'FAIL','decision':'BLOCK','unique_full_files':len(files),'items':[ref(p) for p in files]};selection['full_bytes']=sum(x['bytes'] for x in selection['items']);(D/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':ref(D/'review.json'),'selection':ref(D/'transfer-selection.json'),'files':len(files),'bytes':selection['full_bytes']}))
