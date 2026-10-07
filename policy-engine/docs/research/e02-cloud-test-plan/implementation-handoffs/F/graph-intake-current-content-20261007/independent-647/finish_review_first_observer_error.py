from pathlib import Path
import hashlib,json,subprocess
out=Path('/tmp/e02-F-continuation-20261007/api/graph-intake-review-647');old=out.with_name('graph-intake-review');root=Path('/workspace/e02-F-graph-20261006')
sha='647f5d35362c2a5d7ad32283b804a5b03ea56e83';tree='6b699cac11fb1fe5b317ed0ccfc76940e5958906'
def record(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(name):return json.loads((out/name).read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()==sha
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root).decode().strip()==tree
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root)
assert record(old/'review.json')['sha256']=='707a6575b8f70a6b5fda8b5b9f26134425138af90bd0cbfde2f4c274903214ec'
assert record(old/'review-with-warning.json')['sha256']=='fb57b54593513c0d5f2233a723867255e544b651da334bd64420a40fbc6ef2a8'
for name in ['native','original-controls','complete-projection','profile']:
 m=read(name+'.json');assert m['target_sha']==sha and m['tree']==tree and m['exit_code']==0
profile=json.loads((out/'profile.stdout').read_text())
assert all(v.startswith(str(root/'policy-engine/src/')) for v in profile['origins'].values())
for name,count in [('native',79),('original-controls',3),('complete-projection',17)]:
 s=(out/(name+'.stdout')).read_text();assert f'{count} passed' in s and 'failed' not in s
files=['run_native.py','native.json','native.stdout','native.stderr','capture_controls.py','test_current_source_guards.py','original-controls.json','original-controls.stdout','original-controls.stderr','test_complete_projection.py','complete-projection.json','complete-projection.stdout','complete-projection.stderr','bind_review.py','source-bindings.json','full-delta.diff','profile.json','profile.stdout','profile.stderr','finish_review.py']
report={
 'schema':'policyos.e02.independent_graph_intake_review.v1',
 'reviewer':'F causal_api, independent read-only',
 'target_sha':sha,'tree':tree,'base_sha':'3e6b47e88e0f25474df8cffa213a5e09e7b7affa',
 'source_bindings':read('source-bindings.json'),
 'verdict':'GO bounded current-content graph intake and query-only composition replay',
 'specification_verdict':'GO for exercised current static profile, selected CAS resolution and complete producer certificate reconciliation',
 'engineering_verdict':'GO; canonical producer reused, full typed certificate projection rather than field-specific repairs, operational caches recomputed',
 'new_blockers':[],
 'P40_bucket':'Prior 3e same current-input/content-reconciliation class corrected at complete canonical certificate projection; no new class found in current bounded review',
 'checks':[
  {'id':'selected-native','outcome':'PASS','exit_code':0,'command':read('native.json'),'result':'79PASS, zero skip/error, one PytestConfigWarning unknown cache_dir; complete raw warning retained','output':str(out/'native.stdout')},
  {'id':'original-deciding-discriminators','outcome':'PASS','exit_code':0,'command':read('original-controls.json'),'result':'3PASS; actual query-only positive, unchanged graph/current incompatible alignment typed refusal, unique wrong-kind fragment actual CAS refusal','output':str(out/'original-controls.stdout')},
  {'id':'complete-field-and-operational-cache-controls','outcome':'PASS','exit_code':0,'command':read('complete-projection.json'),'result':'17PASS: exact18-field model denominator, all15 nonoperational field changes refused, orphan and altered operational cache removed with whole fresh certificate equal','output':str(out/'complete-projection.stdout')},
  {'id':'fresh-profile-and-origins','outcome':'PASS','exit_code':0,'command':read('profile.json'),'result':'Actual Python3.14.7 and six product module origins bind candidate source. App DoWhy/EconML absent; this native graph witness is not backend success','output':str(out/'profile.stdout')},
 ],
 'profile':profile,
 'source_guard_unchanged':True,
 'requirements':[
  {'requirement':'Current source contents govern reused output','evidence':'Original incompatible-alignment discriminator now refuses even when producer graph geometry is unchanged; full79 includes changed MethodJob producer direction/current parameters'},
  {'requirement':'Entire producer contract is reconciled','evidence':'Full model serialization excluding only two query caches and separately resolved failure-card pointer; all15 other model fields covered by valid persisted mutations. Owner79 includes full actual failure-card body refusal and selected-view refusal'},
  {'requirement':'Operational cache cannot self-authorize preservation','evidence':'Known record statuses altered plus extra orphan keys inserted into actual persisted certificate; replay rederives whole certificate exactly and removes extra keys'},
  {'requirement':'Actual selected CAS view/body governs loading','evidence':'Current shared resolver checks actual manifest kind/schema/body-version, passes complete selectedref to byte loader; original unique wrong-kind-only blob discriminator and owner selected manifest profile negative refuse'},
 ],
 'historical_block_evidence':{
  'immutable_review':record(old/'review.json'),
  'additive_warning_metadata':record(old/'review-with-warning.json'),
  'full_transfer_selection':record(old/'transfer-selection-with-warning.json'),
  'result':'Prior3e independent69PASS+1configwarning coexists with deciding1FAIL2PASS; first guessed-query/ambiguous-manifest setup nondeciding and preserved. No relabeling'},
 'closure_ids':[],
 'limitations':[
  'Read-only source candidate checks only: future built/installed composed candidate remains UNRUN until root freeze and single affected archive wave',
  'Known synthetic candidate graph/CAS data is not admitted real-data causal evidence or Runtime authority',
  'No DoWhy/EconML positive backend witness; both absent in current app profile',
  'Native current static directed/bidirected scope is bounded; uncertainty endpoints, compact temporal lag and unsupported graphs refuse, no orientation/lag repair',
  'No whole competing3dde head PASS, no rerun/relabeling of historical8236 installed199 proofs, no finding/G closure inference'],
 'full_outputs':[record(out/name) for name in files],
}
(out/'review.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
selection={'schema':'policyos.e02.transfer_selection.v1','target_sha':sha,'tree':tree,'required_files':[record(out/name) for name in ['review.json',*files]],'historical_selection':record(old/'transfer-selection-with-warning.json'),'all_deciding_stdout_stderr_complete':True,'source_unchanged':True,'no_cas_fixture_directory_needed_for_deciding_outputs':'Commands/replayers and complete deciding output bytes are selected; disposable synthetic CAS contents only generated by replay and contain no owner-authority input'}
(out/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':record(out/'review.json'),'selection':record(out/'transfer-selection.json'),'selected_files':len(selection['required_files']),'full_bytes':sum(x['bytes'] for x in selection['required_files'])},indent=2))
