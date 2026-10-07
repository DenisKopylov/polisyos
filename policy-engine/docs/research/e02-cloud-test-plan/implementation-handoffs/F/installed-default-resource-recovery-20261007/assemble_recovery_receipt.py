"""Transport the exact independent recovery addendum without rerunning science."""
import gzip,hashlib,json,subprocess
from pathlib import Path
own=Path('/workspace/e02-F-fry-20261006')
peer=Path('/tmp/e02-F-continuation-20261007/api/installed-resource-recovered-observer-519')
name='installed-default-resource-recovery-20261007'
prefix=Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F')/name
old='de197363d4ba8a86b0e8c2fa0ff31c2858643d1c'
source='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82';tree='750d28da94f372848fe6b2db5f88db95b94cb57d'
def git(*args):return subprocess.check_output(['git','-C',str(own),*args])
assert git('symbolic-ref','--short','HEAD').decode().strip()=='codex/e02-F-fry-20261006'
assert git('rev-parse','HEAD').decode().strip()==old
assert not git('status','--porcelain')
selection=peer/'transfer-selection.json';sel=json.loads(selection.read_bytes())
assert sel['outcome']=='PASS' and sel['source_sha']==source and sel['source_tree']==tree
assert hashlib.sha256(selection.read_bytes()).hexdigest()=='3d2c675e413daf32484fecd1e13cd33387d6ec08c1080993d1c5fd0b3cd6cd67'
review=json.loads((peer/'review.json').read_bytes());assert review['decision']=='GO'
assert hashlib.sha256((peer/'review.json').read_bytes()).hexdigest()=='ff8f74c56c2142d6a2a9c534d21fa2cc7ef122b9e8f76e3440aa1db728bd113a'
old_manifest=json.loads(git('show',old+':policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-default-resource-final-20261007/outputs.json'))
reuse={}
for row in old_manifest['files']:
 reuse[(row['decoded_sha256'],row['decoded_bytes'])]={k:row[k] for k in ['committed_path','stored_bytes','stored_sha256','encoding']}
for val in reuse.values():val['git_ref']=old
selected=[selection,Path(__file__).resolve()]
for row in sel['files']:
 path=Path(row['path']);raw=path.read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'];selected.append(path)
assert len(sel['files'])==39
refs=[];new=[]
for path in sorted(set(selected)):
 raw=path.read_bytes();logical=gzip.decompress(raw) if path.suffix=='.gz' else raw;key=(hashlib.sha256(logical).hexdigest(),len(logical))
 if key in reuse:storage=reuse[key]
 else:
  relative=prefix/(path.relative_to(peer).as_posix() if path.is_relative_to(peer) else path.name)
  if len(raw)>65536 or path.suffix in ('.txt','.blob'):
   stored=gzip.compress(raw,mtime=0);relative=Path(str(relative)+'.gz');encoding='gzip'
  else:stored=raw;encoding='identity'
  target=own/relative;assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(stored)
  storage={'committed_path':str(relative),'stored_bytes':len(stored),'stored_sha256':hashlib.sha256(stored).hexdigest(),'encoding':encoding};reuse[key]=storage;new.append(str(relative))
 refs.append({'original_path':str(path),'original_stored_bytes':len(raw),'original_stored_sha256':hashlib.sha256(raw).hexdigest(),'decoded_bytes':len(logical),'decoded_sha256':key[0],**storage})
# The three view manifests are observed exact-byte aliases of the selected canonical manifests.
for digest,paths in sel['inspection_transport_aliases'].items():
 for original in paths:
  raw=Path(original).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
  if any(row['original_path']==original for row in refs):continue
  canonical=next(row for row in refs if row['decoded_sha256']==digest)
  refs.append({**canonical,'original_path':original,'observed_exact_byte_alias':True})
outputs=prefix/'outputs.json';(own/outputs).write_text(json.dumps({'schema':'policyos.e02.complete_output_transport.v1','tested_source_sha':source,'tested_source_tree':tree,'files':refs,'selected_peer_files':39,'peer_view_aliases':3,'previous_Git_body_references_are_immutable':old,'policy':'All39 full peer artifacts plus3 observed view aliases preserved; exact previous-body hashes reuse published Git bytes instead of duplicated bodies. Six synthetic CAS payload/manifests are unique deciding inputs; full unsafe-whitespace outputs use losslessgzip. No copied tracked product source.'},indent=2)+'\n');new.append(str(outputs))
def out(path):
 row=next((r for r in refs if r['original_path']==path),None)
 return row['committed_path']+('@'+row['git_ref'] if 'git_ref' in row else '') if row else path
env='Actual own installed wheel Python3.14.7 parent/child -I; PYTHONPATH absent, literal readonly dependency-site .pth, no product source/editable fallback. Registered NumPy graph backend; no new DoWhy/EconML inference. Serialized existing real9464 port only, no numerical quota.'
closure='Frozen external519/tree750d, existing independently guarded wheel/archive/site/source carrier. Exact tracked Graph fixture and known synthetic X->Y inputs; one registeredMethodJob, one realNode and one separate-PID child. Complete six unique CAS bytes/manifests and three byte-alias views retained.'
checks=[{**{k:row[k] for k in ['command','target_sha','outcome']},'environment':env,'input_closure':closure,'output':out(row['output']),'scope':row['scope']} for row in review['checks']]
primary=prefix.with_suffix('.json')
receipt={'schema':'policyos.e02.implementation_handoff.v1','unit':'F','slice':name,'closure_ids':[],'related_finding_ids':['B214','B218','B220'],'bundle_ids':['GRF-01','GRF-02','GRF-03'],'slice_base_sha':old,'implementation_commits':[],'changed_paths':[],'candidate_tree_sha':tree,'tested_source_sha':source,'tested_source_tree_sha':tree,'branch':'codex/e02-F-fry-20261006','pull_request':'https://github.com/DenisKopylov/polisyos/pull/60','evidence_only':True,'baseline_cells':[],'checks':checks,'property':{'statement':'An actual installed registeredGraph MethodJob and actualNode selected persistedref must be readable from physicalCAS in a different neutral -I process, preserving known relations, complete model and producer lineage.','runtime_path':['registered causal.prior.reconcile_causal_graph@1.0.0 MethodJob/run_job','actual ReconcileCausalGraphNode','physicalCAS selectedGraph artifact plus manifest','different-PID installedwheel Python-I load_causal_graph_model','literal X->Y/fullmodel/manifest lineage and detached-row consumer checks'],'proxy_divergence':'Original91-per-profile proof reopened CAS in the same process. This separate new wheel-only probe actually creates a child with distinctPID and verifies ownsite origins; originalde197 reader scope remains unchanged.','negative_controls':['Actual child mutates the detached edge-row view to an untrusted destination; subsequent canonical model rows/edges retain originalY.','The existing external519 Graph79 adversarial controls and six actual installed-resource refusal controls remain exact source-bound in originalde197; none were rerun or relabeled by this addendum.']},'predicate_basis':'independently_reconciled','capability_state_or_finding_state':'limited','bounded_check_outcome':'PASS','complete_independent_review':out(str(peer/'review.json')),'original_published_receipt':review['original_published_receipt'],'original_29_immutable':True,'current_native_run_counts':review['current_native_run_counts'],'authority_purpose':'Synthetic Graph consumer transport property only; no Runtime appointment/challenge/verifier, statisticalidentification or value authority.','unknown_pre_outage_attempt':{'outcome':'UNRUN','predicate_basis':'not_established','reason':'Recovered filesystem has no saved script/output for the earlier uncertain attempt. No assertion it never started; new authorized narrow probe is a separate observation.'},'external_source_dependency':{'branch':'codex/e02-F-closeout-20261006','pull_request':'https://github.com/DenisKopylov/polisyos/pull/65','assembled_commit':source,'assembled_tree':tree},'limitations_and_next_owner':review['limits']+['Fresh-child positive is wheel-only. Rebuilt-sdist retains original91 same-process CAS proof; no new child/I or53TMLE/79/full91/numerical wave there.','The scientific source is external519, not this evidence-only commit tree. G independently fetches/adjudicates; closure_ids remain empty. No source/lock/schema/environment cleanup or authority subsystem was changed.'],'mandatory_companions':new,'complete_outputs_manifest':str(outputs),'transport_policy':'Complete moderate output/deciding syntheticCAS bytes preserved once; exact previous publishedbody references prevent duplicate copied tracked source/derived views. Rawgenerated archives remain local as declared in originalde197.'}
(own/primary).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'primary':str(primary),'bytes':(own/primary).stat().st_size,'sha256':hashlib.sha256((own/primary).read_bytes()).hexdigest(),'mandatory_companions':len(new),'all_original_record_refs':len(refs),'new_unique_bodies':len(new)-1,'existing_Git_body_refs':sum('git_ref' in r for r in refs),'science_rerun_by_publisher':False}))
