"""Freeze independent fd36 review; reads immutable Git/source/output bytes only."""
import hashlib,json,pathlib,subprocess
D=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/workspace/e02-F-api-20261006')
SHA='fd36b2f66d7226e001b4e96bf78f019841da6541'; TREE='c441031428cc5039f84eef188936a6a904c21f71'
BASE='449d32909928caf39382f4ff02ac74b0adf277eb'; PREV='e5764d9511417c68d599cf8ecabb1a8137d9fc4c'
def h(b):return hashlib.sha256(b).hexdigest()
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':h(b),'full':True}
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
names=['native76','root-probe','effect-boundary','namespace-gate','decorator-and-errors'];records=[]
for name in names:
 p=D/(name+'.json');r=json.loads(p.read_text());assert r['source_sha']==SHA and r['source_tree']==TREE
 assert r['source_begin']==r['source_end']
 for s in r['source_begin']:
  b=git('show',SHA+':'+s['source_path']);assert len(b)==s['bytes'] and h(b)==s['sha256']
 for o in r['output_refs']:
  b=pathlib.Path(o['path']).read_bytes();assert len(b)==o['bytes'] and h(b)==o['sha256']
 records.append(r)
assert len(records[0]['source_begin'])==9
assert '76 passed, 1 warning' in (D/'native76.stdout.txt').read_text()
assert '4 passed' in (D/'effect-boundary.stdout.txt').read_text()
assert '1 failed, 4 passed, 4 deselected' in (D/'decorator-and-errors.stdout.txt').read_text()
ns=json.loads((D/'namespace-gate.stdout.txt').read_text());assert ns['entrypoint_count']==38 and ns['unknown_count']==15
assert ns['explicit_successful_read_count']==40 and len(ns['canonical_contract_violations'])==15
for row in ns['entrypoints']:
 for x in row['resolution']['inputs']:
  if x['operation']=='read_bytes' and x['status']=='read':
   b=git('show',SHA+':policy-engine/'+x['path']);assert len(b)==x['bytes'] and h(b)==x['sha256']
unknown=[r for r in ns['entrypoints'] if r['export_count'] is None]
assert all(r['known_export_count']==0 and not r['complete'] for r in unknown)
analytics=next(r for r in ns['entrypoints'] if r['module']=='polisyos.ir.analytics');world=next(r for r in ns['entrypoints'] if r['module']=='polisyos.fabric.world')
assert len(analytics['resolution']['declared_export_candidates'])==278 and len(world['resolution']['declared_export_candidates'])==41
paths=git('diff','--name-only',PREV,SHA).decode().splitlines();assert len(paths)==3
patch=git('diff',PREV,SHA);(D/'e576-to-fd36.diff.txt').write_bytes(patch)
source_refs=[]
for p in paths:
 b=git('show',SHA+':'+p);source_refs.append({'source_sha':SHA,'source_tree':TREE,'source_path':p,'bytes':len(b),'sha256':h(b)})
old=D.with_name('api-review')
report={
 'reviewer':'graph_scm','role':'independent_read_only_static_profile_review','check':'FAIL','decision':'BLOCK','outcome':'open',
 'candidate_sha':SHA,'candidate_tree':TREE,'slice_base_sha':BASE,'delta_predecessor_sha':PREV,
 'scope':'Finite static export resolver and canonical consumer metadata only; no universal Python interpreter, runtime facade ABI closure, wheel/sdist rerun, generated/public full architecture green, scientific authority or ledger closure.',
 'source_bindings':records[0]['source_begin'],'delta_source_refs':source_refs,'delta_diff_ref':ref(D/'e576-to-fd36.diff.txt'),
 'source_begin_end_binding_check':'PASS','source_read_denominators':{'base_to_candidate_changed_paths':9,'delta_paths':3,'canonical_supported_entrypoints':38,'explicit_successful_file_reads':40,'actual_incomplete_canonical_gate_rows':15,'read_receipt_unobserved_boundaries':'Python imports/Git/subprocess/external service reads are explicitly outside the collector; not claimed complete.'},
 'findings':[{'id':'API-STATIC-EFFECT-FUNCTION-DECORATOR','priority':'P2','confidence':'high','class':'P40 same unresolved import-time effect class','check':'FAIL','criterion':'Unknown import-time executable effects must refuse a complete selected export namespace before canonical public-surface admission.',
  'trigger':'A bare local function decorator executes before the selected literal map and rebinds the module-level sorted name from inside the invoked decorator body.',
  'actual_controlled_namespace':['RuntimeShadow'],'actual_product_inventory':{'exports':['StaticName'],'export_count':1,'known_export_count':1,'complete':True,'canonical_violations':[]},
  'cause':'_module_level_nodes visits decorator expressions but the whole-effect audit only refuses ast.Call and ast.ClassDef; a bare decorator implicitly calls the function without an ast.Call node. Function body is excluded, so its executed global rebind is not detected.',
  'source_path':'policy-engine/tools/devx/architecture/guardrails.py','locations':{'module_level_nodes':529,'audit_consumers':772},
  'negative_deciding_output_ref':ref(D/'decorator-and-errors.stdout.txt'),'execution_ref':ref(D/'decorator-and-errors.json'),'replayer_ref':ref(D/'test_implicit_function_effect.py'),
  'next_owner':'causal_api; generic finite import-time effect grammar/admission, not descriptor/decorator/provider-specific whitelist or runtime execution.'}],
 'checks':[
  {'name':'Original three independent e576 escape properties + same consumer literal positive','check':'PASS','outcome':'limited','cases':4,'negative_cases':['implicit_descriptor_hook','prebinding_builtin_rebind','multiline_selected_mapping_value_call'],'output':str(D/'effect-boundary.stdout.txt')},
  {'name':'Frozen native source selector','check':'PASS','outcome':'limited','passed':76,'skip':0,'error':0,'warnings':1,'warning_kind':'known cache_dir configuration option while cacheprovider disabled','output':str(D/'native76.stdout.txt')},
  {'name':'Root original190 unknown mutator/alias/list consumers and literal discriminator','check':'PASS','outcome':'limited','four_refusals_one_literal':True,'output':str(D/'root-probe.stdout.txt')},
  {'name':'Whole canonical supported-entrypoint representation and source bytes','check':'PASS','outcome':'limited','entrypoints':38,'read_refs':40,'output':str(D/'namespace-gate.stdout.txt')},
  {'name':'Actual current whole selected canonical contract predicate','check':'FAIL','outcome':'limited','incomplete_count':15,'output':str(D/'namespace-gate.stdout.txt'),'limit':'Deliberate finite grammar rejects unresolved declarations. This expected gate red is distinct from the false-complete decorator counterexample.'},
  {'name':'Declared candidates and true runtime namespaces stay distinct from proof/count','check':'PASS','outcome':'limited','analytics_declared':278,'analytics_actual_native':278,'world_declared':41,'world_actual_native':59,'known_static_count':0,'static_total':None,'complete':False,'output':str(D/'namespace-gate.stdout.txt')},
  {'name':'Unanticipated read/parser errors are not transformed to typed UNKNOWN','check':'PASS','outcome':'limited','error_classes':['OSError','SyntaxError','ValueError','TypeError'],'actual_same_exception_propagated':True,'output':str(D/'decorator-and-errors.stdout.txt')},
  {'name':'Implicit function decorator same-class falsifier','check':'FAIL','outcome':'open','failed':1,'output':str(D/'decorator-and-errors.stdout.txt')}
 ],
 'executions':records,
 'historical_previous_block':{'status':'historical_non_deciding_for_fd36','review_ref':ref(old/'review.json'),'transfer_selection_ref':ref(old/'transfer-selection.json'),'scope':'Original e576 BLOCK/full raw evidence remains immutable; its three exact escape controls are separately replayed at fd36, not relabelled.'},
 'related_finding_ids':['LA-020','LA-007','LA-019'],'closure_ids':[],
 'limits':['Unknown static counts are not empty runtime namespaces.','No generated inventory snapshot updated or full architecture PASS inferred.','Earlier installed facade profile remains separate source-specific proof; no wheel/sdist receipt is promoted to fd36.','No full retirement/FQN/dynamic consumer census closure.','No DoWhy/EconML marker omission treated as backend PASS.','No real-data estimand/authority inference.'],
 'author_source_hold_release':'All candidate source reads and native/independent executions completed. No product edits or environment mutations by reviewer; author may continue after root-authorized generic effect correction.'
}
(D/'review.json').write_text(json.dumps(report,indent=2)+'\n')
files=[D/'review.json',D/'finish_review.py',D/'run_check.py',D/'root-probe-current.py',D/'root-probe-results.json',D/'test_effect_boundary_extended.py',D/'test_implicit_function_effect.py',D/'measure_namespace_gate.py',D/'e576-to-fd36.diff.txt']
for n in names:
 files += [D/(n+'.json'),D/(n+'.stdout.txt'),D/(n+'.stderr.txt')]
selection={'source_sha':SHA,'source_tree':TREE,'check':'FAIL','decision':'BLOCK','unique_full_files':len(files),'items':[ref(p) for p in files],'historical_selection_ref':ref(old/'transfer-selection.json')}
selection['full_bytes']=sum(x['bytes'] for x in selection['items'])
(D/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':ref(D/'review.json'),'selection':ref(D/'transfer-selection.json'),'files':len(files),'bytes':selection['full_bytes']}))
