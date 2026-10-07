"""Freeze the independent e576 BLOCK review without editing an author lane."""
import hashlib,json,pathlib,shlex,subprocess
root=pathlib.Path('/workspace/e02-F-api-20261006')
out=pathlib.Path('/tmp/e02-F-continuation-20261006/graph/api-review')
sha='e5764d9511417c68d599cf8ecabb1a8137d9fc4c'
tree='85299d465d34317fb040b4f272e30f99f7d1d67a'
base='449d32909928caf39382f4ff02ac74b0adf277eb'
prior='2458891c9714404982110ee4c513a8d0142b34c3'
def bound(path):
 body=path.read_bytes();return {'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
names=['native71','root-probe-current','effect-boundary','descriptor-hook','namespace-gate']
checks=[]
for name in names:
 r=json.loads((out/(name+'.json')).read_text())
 assert r['source_sha']==sha and r['source_tree']==tree
 assert r['source_begin']==r['source_end']
 for x in r['output_refs']:
  assert bound(pathlib.Path(x['path']))==x
 check={'name':name,'command':shlex.join(r['command']),'target_sha':sha,
        'environment':r['environment'],'input_closure':'Exact read-only frozen9-path source and the complete argv selector; wholly authored closed runtime fixtures for adversarial effects only.',
        'outcome':r['check'],'exit_code':r['exit_code'],'wall_seconds':r['wall_seconds'],'rss_kib':r['rss_kib'],
        'output':r['output_refs'][0]['path'],'output_refs':r['output_refs'],'execution_receipt':bound(out/(name+'.json'))}
 if name=='native71':check['counts']={'PASS':71,'FAIL':0,'SKIP':0,'ERROR':0,'warnings':1}
 if name=='effect-boundary':check['counts']={'PASS':1,'FAIL':2,'SKIP':0,'ERROR':0,'warnings':0}
 if name=='descriptor-hook':check['counts']={'FAIL':1,'SKIP':0,'ERROR':0,'deselected':3,'warnings':0}
 if name=='namespace-gate':check['classification']='Correctly preserved actual6 incomplete-export violations; this FAIL is distinct from the three false-complete falsifiers.'
 checks.append(check)
source_refs=json.loads((out/'native71.json').read_text())['source_begin']
for x in source_refs:
 body=subprocess.check_output(['git','show',sha+':'+x['source_path']],cwd=root)
 assert len(body)==x['bytes'] and hashlib.sha256(body).hexdigest()==x['sha256']
delta_paths=subprocess.check_output(['git','diff','--name-only',prior,sha],cwd=root,text=True).splitlines()
full_paths=subprocess.check_output(['git','diff','--name-only',base,sha],cwd=root,text=True).splitlines()
assert len(delta_paths)==4 and len(full_paths)==9
finding={'severity':'medium','confidence':'high','bucket':'SAME P40 export-effect class one level deeper, not a new scientific/ABI class',
         'source_path':'policy-engine/tools/devx/architecture/guardrails.py','locations':['audit_consumers: call threshold uses selected binding.end_lineno','audit_consumers: only classes with bases/keywords/decorators refuse','_value: builtin identity inferred from direct AST symbol bindings'],
         'requirement':'A bounded declared-export resolver must return typed unknown rather than complete when unproved import-time effects change the selected export interpretation.',
         'cases':['prebinding globals()[sorted] rebind changes the invoked builtin','unknown call inside a multiline selected mapping initializer occurs before binding.end_lineno','plain class construction invokes a pre-created descriptor __set_name__ hook'],
         'actual_consequence':'Actual canonical inventory/renderJSON emits complete=True and StaticName/export_count1, while controlled real fixture __all__ differs. Actual _check_public_surface_contracts returns no incomplete violation.',
         'minimum_direction':'One conservative whole import-time effect admission boundary, including all class construction, with typed unknown for unsupported effects. No per-callback/global-name/descriptor ladder, provider whitelist or arbitrary-Python execution by the static reader.',
         'proof_refs':[bound(out/'effect-boundary.stdout.txt'),bound(out/'descriptor-hook.stdout.txt')],
         'not_claimed':'No demonstrated current production recommendation, data-dependent causal claim, external caller census completeness, or optional backend failure.'}
originals=[pathlib.Path('/tmp/e02-F-continuation-20261006/root-api-symbol-consumer-probe.py'),pathlib.Path('/tmp/e02-F-continuation-20261006/root-api-symbol-consumer-probe.json')]
files=[p for p in out.iterdir() if p.is_file() and p.name not in {'review.json','transfer-selection.json','finish_review.py'}]+originals+[out/'finish_review.py']
refs=[bound(path) for path in sorted(files)]
report={'schema':'policyos.e02.independent-review.v1','reviewer':'F/graph_scm independent of API author',
        'source_sha':sha,'source_tree':tree,'slice_base_sha':base,'delta_predecessor_sha':prior,
        'scope':'Full base449→e5769-path migration/guardrails footprint and prior245→e5764-path typed unknown representation delta; finite source-bound namespace grammar and real canonical consumer.',
        'specification_verdict':'BLOCK bounded export-effect property: three actual false-complete controls',
        'engineering_quality_verdict':'BLOCK same generic source-effect admission boundary; positive finite resolver/typed representation mechanisms otherwise have bounded native evidence',
        'closure_ids':[],'related_finding_ids':['LA-020','LA-007','LA-019'],
        'findings':[finding],'checks':checks,'source_refs':source_refs,'delta_paths':delta_paths,'full_paths':full_paths,
        'requirement_matrix':[
         {'requirement':'Named/imported map keys and literal sequence declarations resolve without source execution; owner dependency actualreadhashes propagate','result':'PASS bounded','evidence':'native71 actual analytics278 and changed dependency/no-facade-change, unreadable/outside selector controls'},
         {'requirement':'Parser-only deliberate refusal is represented as unknown total; known0 never means empty runtime namespace','result':'PASS bounded','evidence':'native71 +complete namespace-gate38 rows,6 actual incomplete gate violations'},
         {'requirement':'Unexpected ValueError/TypeError/Syntax/OSError remain ERROR rather than parser unknown','result':'PASS bounded','evidence':'actual native unexpected exception injection and missing/unreadable source cases'},
         {'requirement':'Original root190 call/alias/all mutation and builtin shadow cases refuse','result':'PASS bounded','evidence':'retarget COPY:4UNRESOLVED,1correct supportedliteral; original190 outputs preserved'},
         {'requirement':'Unknown import-time effects cannot produce wrong complete selected namespace','result':'FAIL','evidence':'2builtin timing falsecomplete +1implicitdescriptor falsecomplete; supportedliteral positive1PASS'},
         {'requirement':'Compatibility migration keeps actual supported facade owner identities and explicit old-filename boundary','result':'static delta PASS; current independent installed review UNRUN','evidence':'Nine fullchangedpaths exclude runtime facade providers; docs/fixtures/census retain no actualruntime-client assertion. Earlier author548 wheel/sdist observations not relabelled to e576.'},
        ],
        'complete_denominator':{'supported_entrypoints':38,'unknown_total_rows':6,'actual_incomplete_gate_violations':6,'explicit_successful_source_reads':40,'actual_analytics_current_runtime_exports':278,'actual_world_current_runtime_exports':59,'world_known_literal_prefix':41,'interpretation':'Representation completeness is separate from semantic total completeness. Full canonical namespace gate is FAIL, no full architecture PASS claimed.'},
        'property_vs_proxy':'Direct AST binding absence and declaration.end_lineno are proxies for effect-free builtin/namespace interpretation. Controlled unknown effects retain literal maps and __all__ markers but actual namespaces differ while completeness remains true.',
        'predicate_basis':'recomputed','P41_inherited':'not_established and not claimed',
        'limits':['Wholly authored fixtures execute only under reviewer control; product parser never executes source modules or does runtime import resolution.',
                  'Function bodies/runtime dataflow/external plugin configuration are outside a finite static grammar; unknown effects still must not admit a concrete complete quantity.',
                  'No new scientific wave, wheel/sdist rebuild, full architecture/schema generation, production-data claim or authority ratification.',
                  'The six actual incomplete entrypoints are retained FAIL, not auto-closed or suppressed. Full generated snapshot awaits root composition.',
                  'Native71 has one cache_dir instrumentation warning retained; no skip/error promoted to PASS.'],
        'source_guard':'All five actual runs bound clean attached e576 HEAD/tree and9 sourcefile hashes before/end. Author source hold released only after all runs completed; later report reads immutable Git blobs, not mutable forward source.',
        'allowed_actions':{'product_source_writes':False,'git_mutations':False,'env_mutations':False,'children':False},
        'content_refs':refs,'source_hold_released':True}
target=out/'review.json';target.write_text(json.dumps(report,indent=2)+'\n')
selection={'schema':'policyos.e02.transfer-selection.v1','source_sha':sha,'files':[bound(target),*refs],
           'source_refs':source_refs,'scope':'All unique full deciding outputs, original historical root190 probe and replayers; no tracked source bodies, generated fullinventory duplicate or testCAS copied.',
           'total_unique_bytes':sum(x['bytes'] for x in [bound(target),*refs])}
(out/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':bound(target),'selection':bound(out/'transfer-selection.json'),'files':len(selection['files']),'total_unique_bytes':selection['total_unique_bytes'],'verdict':'BLOCK','science_tests_not_repeated':True},indent=2))
