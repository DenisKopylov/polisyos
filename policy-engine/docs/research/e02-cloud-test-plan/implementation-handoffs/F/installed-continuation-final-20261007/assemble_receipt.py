"""Publish complete deciding bytes once; cite tracked science/carriers instead of copying them."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
base=Path(__file__).resolve().parent
own=Path('/workspace/e02-F-fry-20261006')
slice_name='installed-continuation-final-20261007'
prefix=Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F')/slice_name
config=json.loads((base/'installed-config.json').read_text())
assert subprocess.check_output(['git','-C',str(own),'symbolic-ref','--short','HEAD']).decode().strip()=='codex/e02-F-fry-20261006'
assert subprocess.check_output(['git','-C',str(own),'rev-parse','HEAD']).decode().strip()=='0552bd338dad23b2eabb0d22a1c7c4eb4bcd61d6'
assert not subprocess.check_output(['git','-C',str(own),'status','--porcelain','--untracked-files=no'])
selected=[]
# All original/deciding commands, including pre-native harness failures, remain available.
for name in ('prepare.py','setup.py','bind.py','environment.py','launch.py','installed_tmle_reader.py','capture_native.py','capture_native_v2.py','postguard.py','census.py','census_v2.py','assemble_receipt.py','source-export-proof.json','setup-config.json','carrier-manifest.json','profile-expected.json','installed-config.json','setup-command-records.json','archive-installed-source-bindings.json','environment-checks.json','orchestration-inputs.json','initial-capture-harness-error.json','native-wave-v2.json','post-native-custody.json','native-census.json','native-census-v2.json','auxiliary-diagnostic-classification.json','failure-attribution-correction.json'):
 selected.append(base/name)
for pattern in ('prepare.*.json','prepare.*.txt','git-archive.stderr.txt','setup.*.json','setup.*.txt','binder.*.json','binder.*.txt','*-environment.*.json','native-wave*.stdout.json','native-wave*.stderr.txt','*-native*.json','*-native*.stdout.txt','*-native*.stderr.txt','*-resources-v2.json','*-junit.xml','*-installed-proof.json','postguard.*.json','postguard.*.txt','census*.stdout.json','census*.stderr.txt','graph-diagnostic*.stdout.txt','graph-diagnostic*.stderr.txt'):
 selected.extend(base.glob(pattern))
for record in json.loads((base/'setup-command-records.json').read_text()):
 for stream in ('stdout','stderr'):
  if stream in record:selected.append(Path(record[stream]['path']))
selected.extend((base/'wheel-reader-origin-proofs').glob('*.json'))
selected.extend((base/'sdist-reader-origin-proofs').glob('*.json'))
selected.append(base/'wheel-consumer/diagnose_graph.py')
review_selection=base/'independent-api-transfer-selection.json'
assert review_selection.is_file(),'API independent review/complete input selection not yet ready'
peer=json.loads(review_selection.read_text());selected.append(review_selection)
import os
peer_root=Path(os.path.commonpath([str(Path(row['path']).parent) for row in peer['files']]))
for row in peer['files']:selected.append(Path(row['path']))
selected=sorted(set(selected))
refs=[];seen={};created=[]
destination_root=own/prefix
assert not destination_root.exists()
destination_root.mkdir(parents=True)
for path in selected:
 assert path.is_file(),path
 raw=path.read_bytes();logical=gzip.decompress(raw) if path.suffix=='.gz' else raw;decoded_sha=hashlib.sha256(logical).hexdigest()
 key=(decoded_sha,len(logical))
 if key in seen:
  storage=seen[key]
 else:
  name=path.relative_to(base).as_posix() if path.is_relative_to(base) else 'independent/'+path.relative_to(peer_root).as_posix()
  if path.suffix=='.gz':
   stored=raw;relative=prefix/name;encoding='gzip'
  elif len(raw)>65536:
   stored=gzip.compress(raw,mtime=0);relative=prefix/(name+'.gz');encoding='gzip'
  elif path.suffix in ('.txt','.xml','.diff') or '.stdout.' in path.name or '.stderr.' in path.name:
   stored=(json.dumps({'schema':'policyos.e02.lossless_utf8_text.v1','decoded_bytes':len(raw),'decoded_sha256':decoded_sha,'text':raw.decode('utf-8')},ensure_ascii=False,indent=2)+'\n').encode();relative=prefix/(name if path.suffix=='.diff' else name+'.text.json');encoding='lossless_utf8_json'
  else:
   stored=raw;relative=prefix/name;encoding='identity'
  target=own/relative;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();target.write_bytes(stored)
  storage={'committed_path':relative.as_posix(),'stored_bytes':len(stored),'stored_sha256':hashlib.sha256(stored).hexdigest(),'encoding':encoding};seen[key]=storage;created.append(relative.as_posix())
 refs.append({'original_path':str(path),'decoded_bytes':len(logical),'decoded_sha256':decoded_sha,'original_stored_bytes':len(raw),'original_stored_sha256':hashlib.sha256(raw).hexdigest(),**storage})
outputs={'schema':'policyos.e02.complete_output_transport.v1','tested_source_sha':config['source_sha'],'tested_source_tree':config['source_tree'],'files':refs,'unique_stored_files':len(created),'source_body_policy':'Tracked product/test/source bodies are cited as path@b5 and Git blob in carrier/source manifests; not copied into this receipt. Full unique deciding logs/observer inputs and expected errors are transported.'}
manifest_path=prefix/'outputs.json';(own/manifest_path).write_text(json.dumps(outputs,indent=2)+'\n');created.append(manifest_path.as_posix())
def committed(original):
 return next(row['committed_path'] for row in refs if row['original_path']==str(base/original))
census=json.loads((base/'native-census-v2.json').read_text())
env='Fresh separate Python3.14.7 installed wheel/rebuilt-sdist sites, -I neutralcwd, literal readonly dependency .pth only; locked external DoWhy3.12.14 version/resources observed but no new backend execution claimed; no quotas.'
closure='Exact b5 Gitarchive17843files/550021601B;8 selected Git-bound modules/41 fixtures;3452product+7forcedresource declaredfiles; synthetic actualTMLE600binary2fold1repeat once/profile, genuine Graph/CAS and signed economics producer-route fixtures.'
checks=[]
for name,outcome,output in [('Exact Git source export/complete originalblob reconciliation','PASS','source-export-proof.json'),('Actual sourcewheel+sdist+rebuiltwheel build/two isolated installs','PASS','setup-command-records.json'),('Every declared archive/site product/resource byte','PASS','archive-installed-source-bindings.json'),('Initial capture before native process launch missing /usr/bin/time','ERROR','initial-capture-harness-error.json'),('Complete two parallel162 affected native suites','FAIL','native-wave-v2.json'),('Post-native source/archive/site/carrier custody','PASS','post-native-custody.json'),('Complete literal warnings and actual53 fresh isolated consumer lineage','PASS','native-census-v2.json')]:
 checks.append({'command':{'source-export-proof.json':'python3 '+str(base/'prepare.py'),'setup-command-records.json':'python3 '+str(base/'setup.py')+' '+str(base/'setup-config.json'),'archive-installed-source-bindings.json':'python3 '+str(base/'bind.py')+' '+str(base/'installed-config.json'),'initial-capture-harness-error.json':'python3 '+str(base/'capture_native.py'),'native-wave-v2.json':'python3 '+str(base/'capture_native_v2.py'),'post-native-custody.json':'python3 '+str(base/'postguard.py'),'native-census-v2.json':'python3 '+str(base/'census_v2.py')}[output],'target_sha':config['source_sha'],'environment':env,'input_closure':closure,'outcome':outcome,'output':committed(output)})
checks.append({'command':'../wheel-env/bin/python -I diagnose_graph.py ../installed-config.json; cwd=wheel-consumer; one real unchanged selector', 'target_sha':config['source_sha'],'environment':env,'input_closure':closure,'outcome':'FAIL','output':committed('auxiliary-diagnostic-classification.json')})
checks.append({'command':'Independent API complete archive/site/input review; exact commands/full outputs in peer packet','target_sha':config['source_sha'],'environment':env,'input_closure':closure,'outcome':peer['outcome'],'output':next(row['committed_path'] for row in refs if row['original_path']==peer['primary_review'])})
receipt={'schema':'policyos.e02.implementation_handoff.v1','unit':'F','slice':slice_name,'closure_ids':[],'bundle_ids':['GRF-03','GRF-01','GRF-02','API-01','FIT-01','ECO-01'],'related_finding_ids':['B214','B218','B220','LA-007','LA-019','LA-020','B54','B56','LA035','LA004'],'slice_base_sha':'0552bd338dad23b2eabb0d22a1c7c4eb4bcd61d6','implementation_commits':[],'candidate_tree_sha':config['source_tree'],'branch':'codex/e02-F-fry-20261006','pull_request':'https://github.com/DenisKopylov/polisyos/pull/60','changed_paths':[],'mandatory_companions':created,'evidence_only':True,'tested_source_sha':config['source_sha'],'tested_source_tree_sha':config['source_tree'],'root_source_dependency_branch':'codex/e02-F-closeout-20261006','root_source_dependency_pull_request':'https://github.com/DenisKopylov/polisyos/pull/65','source_binding':'External immutable ROOT productb5, not this receipt-only branchHEAD/tree. Own implementation footprint empty. No product/source/environment/sharedasset mutations. ROOT/G code/ledger acceptance separate.','baseline_cells':[],'baseline_navigation_reference':'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/foundry-consumer-input-review-20261007.json@0552bd338dad23b2eabb0d22a1c7c4eb4bcd61d6','checks':checks,'complete_outputs_manifest':manifest_path.as_posix(),'property':{'statement':'Measure actual affected installed consumers with complete default-resource closure, preserving successful bounded numerical candidates and refusing false operational/statistical/value authority. Actual default-resource closure FAILs at b5; declared package-byte closure PASS does not close that property.','runtime_path':['exactGit source','sourcewheel and sdist→rebuiltwheel','two independent installedPython-I profiles','registered actual Graph/TMLE/economics producer','typed MethodJob/IR manifests and physicalCAS','fresh installed reader','actual Scientist/Confidence/value consumer'],'proxy_divergence':'3459declaredpackagedfile hash checks and static marker/type presence pass, while32realGraphcomposition/default callers cannot load the existing seedalignment file. SUCCESS+CI nativeTMLE is an actual candidate, not authority/valuepositive.','negative_controls':['Current Graph missing/corrupt/schema/cache/source/certificate and temporal inputs retained in full38+41 tests. All32Graph FAILs preserved:26directXMLmissingseed,6commoncauseby source-pathinference only.','52retained nativeSUCCESS/CI forged envelope/source/SimulationResult variations+1original share actualsamepersistedTMLE lineage, keep causal blocker and unresolved value contract refusal.','Actual Cbridge→labor→tax signed-wealth Gini/metricPPO typed refusal; plain metric-disabled PPO positive.','Read-only postguard all source/site/archive/carrier bytes remain exact; no resource injected.']},'predicate_basis':'independently_reconciled','capability_state_or_finding_state':'limited; complete b5 installed consumer candidate NO-GO/FAIL32each (26directmissingseed/6sourceinferred) while independent package custody and130boundedcases/profile pass. No finding IDs closed by this evidence companion.','failure_attribution_correction':committed('failure-attribution-correction.json'),'native_profile_outcomes':{kind:{'PASS':130,'FAIL':32,'ERROR':0,'SKIP':0,'total':162} for kind in ('wheel','sdist')},'warning_scope':census['warnings_scope'],'warning_precision_companion':next(row['committed_path'] for row in refs if row['original_path'].endswith('/b5-independent-review-companion.json')),'local_oversized_archives':[{**row,'receiver_bytes':'not_committed; exact rawarchive acceptance requires explicit raw transfer or fresh build from frozen b5 with committed replayer; no summary-only rawbytes custody claim for G'} for row in json.loads((base/'archive-installed-source-bindings.json').read_text())['archives'].values()],'limitations_and_next_owner':['ROOT/Graph/DataForge/API: existing default seed_variable_alignments.yaml real installed dependency absent;26XMLdirectfailuremessages,6oldernodeassertions source-inferred commoncause only; preserve b5failedcheckpoint, forward canonical packaging/loader repair only after owner/source review.','Do not rerun162 or unchangedTMLE53 after resource-only fix; next newfreeze needs only affected Graph/resource installed callers and full new product/archive/siteguards.','No P41 inherited-red attribution; original8236 full162 command was not replayed before this external candidate. Default-loader source being unchanged alone is not baseline proof.','Current literalwarnings retained:16pytest=1unitmark+15Equinox deprecations;36load_simulation_result warning episodes (SimulationResult classliteral12)+36Prometheus bootstrap failures each;9464is source-default label notliteralraw port evidence;2expectedJAXnegative-Gini callbacks each. Prometheus exporterpositiveUNRUN.','Earlier historical15=14runtime+1instrumentation→0 and90optionalLightGBM are exact prior8236profile proof only, not fresh current162counts. No warning suppression introduced.','Genuine operational Runtime seal/current fullcontext+challenge+verifier, statisticalidentification admission, nativevaluecontractpositive andB56admittedcompeting-studybudget remain institutionally missing/UNRUN. No new gate/issuer/authority facade.','No global architecture/schema/invocation closure, codeacceptance/main/Gintegration claim. ROOT current35ledger remains solewriter.']}
primary=prefix.with_suffix('.json');(own/primary).write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'primary':primary.as_posix(),'bytes':(own/primary).stat().st_size,'sha256':hashlib.sha256((own/primary).read_bytes()).hexdigest(),'unique_companions':len(created),'complete_original_inputs_outputs':len(refs),'scientific_status':'FAIL/limited; noclosure','stored_bytes':sum(row['stored_bytes'] for row in seen.values())}))
