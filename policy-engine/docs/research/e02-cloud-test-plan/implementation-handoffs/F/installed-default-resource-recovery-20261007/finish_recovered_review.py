"""Freeze additive recovery evidence without modifying the historical29 review."""
from pathlib import Path
import collections,gzip,hashlib,json,re,shlex,subprocess,sys
OUT=Path(__file__).resolve().parent;ORIGINAL=OUT.with_name('installed-resource-final-519')
SOURCE='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82';TREE='750d28da94f372848fe6b2db5f88db95b94cb57d'
def load(name):return json.loads((OUT/name).read_text())
def ref(p):
    p=Path(p);body=p.read_bytes();return {'path':str(p),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'complete':True}
pre=load('preflight.json');old=json.loads((ORIGINAL/'transfer-selection.json').read_text())
for row in old['files']:
    assert ref(row['path'])['bytes']==row['bytes'] and ref(row['path'])['sha256']==row['sha256']
    if row.get('decoded_sha256'):
        decoded=gzip.decompress(Path(row['path']).read_bytes());assert len(decoded)==row['decoded_bytes'] and hashlib.sha256(decoded).hexdigest()==row['decoded_sha256']
assert ref(ORIGINAL/'review.json')['sha256']=='e315caff26b9efbf86bb1122b8e789f2eb8344521c3c1790c37b7ea149010937'
assert ref(ORIGINAL/'transfer-selection.json')['sha256']=='aaf0e955e75ec0a7c83c8cfc2a6cfd0cdc9d5a2afb8990dbb1ded154f020ebb7'
custody=load('custody-review.json');native=load('native-output-review.json');parent=load('fresh-bridge-proof.json');child=load('fresh-reader-proof.json');post=load('post-own-probe-guard.json')
assert custody['custody_verdict']=='PASS' and native['outcome']==parent['outcome']==child['outcome']==post['outcome']=='PASS'
assert len(pre['verified_files'])==29 and native['expected_negative_actual_FAIL_count']==6
assert child['reader_pid']!=parent['parent_pid'] and child['isolated']==parent['parent_isolated']==1
assert parent['selected_graph_ref']==child['selected_graph_ref']
for kind in ['wheel','sdist']:
    assert native['profiles'][kind]['outcomes']=={'PASS':91,'FAIL':0,'ERROR':0,'SKIP':0}
assert post['complete_active_site_checks']==6928 and post['active_archives']==3
for name in ['fresh-bridge','fresh-reader']:
    raw=(OUT/(name+'.stdout.txt')).read_text();assert not (OUT/(name+'.stderr.txt')).read_bytes()
    assert not re.search(r'\[(?:INFO|WARNING|ERROR)\] [^\n]*?: (?:nan_detected|inf_detected|unexpected_key|missing_key|empty_array|shape_mismatch|distribution_shift)',raw)
    assert 'Warning:' not in raw and 'Prometheus metrics exporter disabled' not in raw
cas=load('observed-cas-payloads.json');cas_by_digest={}
for row in cas['files']:
    body=Path(row['path']).read_bytes();assert len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256']
    cas_by_digest.setdefault((row['bytes'],row['sha256']),[]).append(row['path'])
cas_unique=[paths[0] for paths in cas_by_digest.values()]
publication=load('original-publication-readback.json')
checks=[]
def check(label,outcome,command,output,scope):
    command=shlex.join(command) if isinstance(command,list) else command
    checks.append({'id':label,'target_sha':SOURCE,'target_tree':TREE,'outcome':outcome,'command':command,'output':str(OUT/output) if output else 'No saved pre-outage execution output exists on recovered filesystem.','scope':scope})
check('immutable-original29-recovery-readback','PASS',shlex.join([sys.executable,str(OUT/'finish_recovered_review.py')]),'preflight.json','Original29 byte-identical; primary published separately at de197, no retrospective fresh-child claim.')
check('recovered-complete-archive-source-site-custody','PASS',load('review_custody.command.json')['argv'],'review_custody.stdout.txt','Read every18301Git/snapshot payload, all12981actualsdist/rebuild members,3archives,3464files/site,3147Python/site,36carriers; no builder/site mutation.')
check('recovered-complete-native91-and-six-controls-read','PASS',load('review_native_outputs.command.json')['argv'],'review_native_outputs.stdout.txt','Read existing complete XML/raw/commands/origins:91PASS each,0FAIL/ERROR/SKIP;6actualexpectedFAIL property controls. No suite replay.')
check('unknown-pre-outage-extra-result','UNRUN','Pre-outage tool result unavailable; saved directory inspected on recovery',None,'Completion not_established: directory absent. No assertion prior process never started; no fabricated PASS/FAIL from transport outage.')
check('one-real-wheel-job-node-selected-CAS-fresh-child','PASS',load('fresh-bridge.command.json')['argv'],'fresh-bridge.stdout.txt','Actual registered causal.prior.reconcile_causal_graph@1.0.0 MethodJob/run_job -> actualNode persistedselectedGraph -> separatePID ownwheel-I reader. LiteralX->Y/fullmodel/manifest producerlineage/detached-row property; ONEprofile, no79/TMLE/buildrepeat.')
check('fresh-child-reader-own-neutral-I-command','PASS',load('fresh-reader.command.json')['argv'],'fresh-reader.stdout.txt','DifferentPID fromproducer;83actualproductmodule origins ownsite0escapes; no parent-memory substitute. Source fixture copied from exact519Gitcarrier, no product sourcepath.')
check('complete-post-additive-site-archive-custody','PASS',load('post-recovered-fresh-bridge.command.json')['argv'],'post-recovered-fresh-bridge.stdout.txt','All6928actualsite product/resources plus3currentarchives unchanged afteradditive. Copied replayer historical caption retained; actual current invocation scope recorded separately.')
check('production-identifier-Runtime-authority','UNRUN','No real admitted authority input/verifier issued for this synthetic graph fixture',None,'Synthetic candidate only: no causalidentification/statistical/value/productionauthority closure, no fakeissuer oradmissionseal.')
checks[-1]['output']='UNRUN: no admitted Runtime authority input/verifier issued for this synthetic candidate.'
result={'schema':'e02-independent-installed-recovery-addendum/v1','role':'F-API independent installed evidence reviewer','decision':'GO','decision_scope':'Recovered immutable519 bytes and ONE actual wheel registeredMethodJob/Node persistedGraph fresh-I reader; original29 and b5NO-GO preserved.','source_sha':SOURCE,'source_tree':TREE,'closure_ids':[],'predicate_basis':'independently_reconciled','original_frozen_review':ref(ORIGINAL/'review.json'),'original_frozen_selection':ref(ORIGINAL/'transfer-selection.json'),'original_published_receipt':publication,'preflight':ref(OUT/'preflight.json'),'custody':ref(OUT/'custody-review.json'),'saved_native_output_review':ref(OUT/'native-output-review.json'),'fresh_parent':ref(OUT/'fresh-bridge-proof.json'),'fresh_child':ref(OUT/'fresh-reader-proof.json'),'observed_synthetic_CAS_records':ref(OUT/'observed-cas-payloads.json'),'post_additive':ref(OUT/'post-own-probe-guard.json'),'checks':checks,'current_native_run_counts':{'new_registered_method_jobs':1,'new_Node_executions':1,'new_fresh_I_children':1,'wheel_only':True,'expensive_suites_repeated':0,'parent_owned_module_origins':len(parent['product_origins']),'child_owned_module_origins':len(child['product_origins']),'origin_escapes':0,'stderr_bytes':0,'unexpected_warning_memberships':0},'historical_case_scope':{'author_wheel':{'PASS':91,'FAIL':0,'ERROR':0,'SKIP':0},'author_sdist':{'PASS':91,'FAIL':0,'ERROR':0,'SKIP':0},'six_expected_negative_controls':'6 actualFAIL, notunexpectedproductfailures','old_b5':'Each130PASS32FAIL retains c227 evidence; no relabeling.','old_8236':'199each/90LGBM are different source/profile, not replayed here.'},'limits':['Original29 freshGraph() means sameprocess reopenedCAS. New wheel-only fresh child is separate current additive proof, not retrospective original91 subprocess assertion.','38static public entrypointUNKNOWN/null totals andcanonicalFAIL remain; no parser/global scientific closure.','No transfer to freshG855 orlater ordinary-merge product candidate; changed IR/worker/consumer equality requires separate review.','No DoWhy/EconML backend execution inferred from this actualnumpy Graph producer or app3.14 imports.','No raw productiondata,authorityissuer,challenge/verifier positive,sharedB56studies or valueobjective authority supplied.','No cleanup/deletion/source/site/resource mutation; full registry/setup syntheticCAS stayslocal andreplayer reconstructs it. Three unique actualsyntheticartifact roles retained as fullbyte records.'],'complete_CAS_byte_aliases':{key[1]:paths for key,paths in cas_by_digest.items() if len(paths)>1},'no_original_review_mutation':True}
(OUT/'review.json').write_text(json.dumps(result,indent=2)+'\n')
selected=[p for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='transfer-selection.json']+[Path(p) for p in cas_unique]
records=[ref(p) for p in selected];assert len({r['path'] for r in records})==len(records)
selection={'outcome':'PASS','scope':'Additive independent recovery/fullsavedcustody+ONEwheel fresh-I graphreader; historical original29 unchanged.','primary_review':str(OUT/'review.json'),'source_sha':SOURCE,'source_tree':TREE,'files':records,'complete_file_count':len(records),'stored_bytes':sum(r['bytes'] for r in records),'decoded_bytes':sum(r['bytes'] for r in records),'inspection_transport_aliases':result['complete_CAS_byte_aliases'],'deletion_performed_by_reviewer':False}
(OUT/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'decision':'GO','review':ref(OUT/'review.json'),'selection':ref(OUT/'transfer-selection.json'),'complete_files':len(records),'bytes':selection['stored_bytes'],'fresh_bridge_seconds':load('fresh-bridge.command.json')['seconds'],'fresh_child_seconds':load('fresh-reader.command.json')['seconds']},indent=2))
