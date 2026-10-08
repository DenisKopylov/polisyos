from pathlib import Path
import argparse,ast,csv,hashlib,io,json,re,subprocess
import gzip
parser=argparse.ArgumentParser();parser.add_argument('--repo',default='/workspace/polisyos');parser.add_argument('--scratch',default='/workspace/e02-F-20261006-receipts/final-root');args=parser.parse_args();root=Path(args.scratch);repo=args.repo;n=json.loads((root/'selector-audit-navigation.json').read_text());base=n['base']
def read(ref,path):
 p=subprocess.run(['git','show',ref+':'+path],cwd=repo,capture_output=True);return p.stdout if p.returncode==0 else None
def bound(ref,path):
 raw=read(ref,path)
 if raw is None:return {'source_sha':ref,'path':path,'present':False}
 return {'source_sha':ref,'path':path,'present':True,'git_blob':subprocess.check_output(['git','rev-parse',ref+':'+path],cwd=repo,text=True).strip(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
def scratch_bound(path):
 raw=Path(path).read_bytes();return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
ownpath='policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv';owners=list(csv.DictReader(io.StringIO(read(base,ownpath).decode()),delimiter='\t'));fowners=[x for x in owners if x['unit']=='F'];assert len(fowners)==35
cards=[]
for r in n['bundles']:
 text=read(base,r['card']['path']).decode()
 for m in re.finditer(r'<!-- SOURCE_BEGIN (B|LA):([^ ]+) -->\n(.*?)<!-- SOURCE_END \1:\2 -->',text,re.S):
  cards.append({'bundle':r['bundle'],'id':m[2],'body':m[3],'sha256':hashlib.sha256(m[3].encode()).hexdigest(),'bytes':len(m[3].encode()),'card_ref':r['card']})
assert len(cards)==36 and len({c['id'] for c in cards})==35
(root/'selector-original-source-cards.json').write_text(json.dumps({'base':base,'denominator':36,'blocks':cards},ensure_ascii=False,indent=2)+'\n')
files={};checks={};rows=[]
def file_id(ref,path):
 key=ref+':'+path
 if key not in files:
  b=bound(ref,path);raw=read(ref,path);functions=[]
  if raw and path.endswith('.py'):
   src=raw.decode();t=ast.parse(src)
   for f in ast.walk(t):
    if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith('test_'):
     functions.append({'name':f.name,'line':f.lineno,'end_line':f.end_lineno,'sha256':hashlib.sha256(ast.get_source_segment(src,f).encode()).hexdigest(),'docstring':ast.get_docstring(f)})
  files[key]={'binding':b,'test_functions':functions}
 return key
receipts={}
def load_receipt(head,path):
 key=head+':'+path
 if key not in receipts:
  receipts[key]=json.loads(read(head,path))
 return receipts[key]
def owner_criteria(h,ids):
 value=h.get('per_id',h.get('per_id_matrix',h.get('per_finding',h.get('criterion_decisions',h.get('finding_outcomes',h.get('finding_decisions',{}))))))
 if isinstance(value,dict):return {i:(value.get(i) if i in value else ({'state':h.get('finding_outcome'),'finding_closure':h.get('finding_closure'),'decisions':h.get('decisions'),'unavailable_inputs':h.get('unavailable_inputs'),'local_rerun':h.get('local_rerun')} if h.get('finding_outcome') else None)) for i in ids}
 if isinstance(value,list):return {i:next((x for x in value if x.get('id',x.get('finding_id'))==i),None) for i in ids}
 return {i:({'state':h.get('finding_outcome'),'finding_closure':h.get('finding_closure'),'decisions':h.get('decisions'),'unavailable_inputs':h.get('unavailable_inputs'),'local_rerun':h.get('local_rerun')} if h.get('finding_outcome') else None) for i in ids}
for r in n['bundles']:
 head=r['owner_receipt_head'];hp=r['owner_receipt']['path'];h=load_receipt(head,hp);actual=[]
 for a in r['actual_tested_selectors']:
  receipt=a['check_receipt']['path'];key=head+':'+receipt+'#checks['+str(a['check_index'])+']'
  if key not in checks:
   c=load_receipt(head,receipt)['checks'][a['check_index']]
   outputs={}
   for field in ['output','stderr','receipt','execution_receipt','environment_receipt','deciding_output']:
    val=c.get(field)
    if isinstance(val,str) and val.startswith('policy-engine/') and '\n' not in val:outputs[field]=bound(head,val)
   checks[key]={'receipt':bound(head,receipt),'check_index':a['check_index'],'recorded_check':c,'committed_outputs':outputs,'audit_role':'recorded actual check, not reexecuted by this selector audit; SKIP/ERROR/FAIL are not PASS'}
  actual.append({'selector':a['selector'],'path':a['path'],'check_ref':key,'outcome':a['outcome'],'candidate_test_file_ref':file_id(r['candidate_implementation'],a['path']),'tested_test_file_ref':file_id(a['resolved_tested_tree'],a['path']),'same_test_file_bytes':a['candidate_test_bytes_match_tested'],'target_basis':a['target_input_basis']})
 # Keep numerical child/fresh-reader checks even when the launcher contains no pytest selector.
 for i,c in enumerate(h['checks']):
  key=head+':'+hp+'#checks['+str(i)+']'
  if key not in checks:
   outputs={}
   for field in ['output','stderr','receipt','execution_receipt','environment_receipt','deciding_output']:
    val=c.get(field)
    if isinstance(val,str) and val.startswith('policy-engine/') and '\n' not in val:outputs[field]=bound(head,val)
   checks[key]={'receipt':bound(head,hp),'check_index':i,'recorded_check':c,'committed_outputs':outputs,'audit_role':'supplemental actual check; not a proposed-selector execution proof unless its command selects that file'}
 declared=[]
 for p in r['declared_test_paths']:
  matches=[a for a in actual if a['path']==p['declared_selector']]
  positive=[a for a in matches if a['outcome']=='PASS' and a['same_test_file_bytes']]
  status='PASS' if p['candidate']['present'] and positive else 'UNRUN'
  declared.append({'selector':p['declared_selector'],'base_file_ref':file_id(base,p['declared_selector']),'candidate_file_ref':file_id(r['candidate_implementation'],p['declared_selector']),'present_in_candidate':p['candidate']['present'],'declared_path_execution_outcome':status,'actual_matching_checks':matches,'explanation':'Exact file selected by recorded PASS check; test file bytes bind to candidate. This is not full finding or runtime-composition closure.' if status=='PASS' else ('Proposed new file absent at both source trees; never claimed executed. See exact bounded property equivalents.' if not p['candidate']['present'] else 'File exists but its recorded selected whole commands are SKIP/FAIL, so file-level PASS is unestablished. See separate selected-profile scientific witness.')})
 criteria=owner_criteria(h,r['finding_ids'])
 perid=[]
 for id in r['finding_ids']:
  original=next(c for c in cards if c['bundle']==r['bundle'] and c['id']==id)
  perid.append({'id':id,'canonical_owner':next(o['source_closure_owner'] for o in fowners if o['finding_id']==id),'original_card_body_sha256':original['sha256'],'original_card_body_bytes':original['bytes'],'original_card_ref':original['card_ref'],'owner_criterion_decision':criteria[id],'scientific_and_input_limit':'Use the original complete card and owner finite criterion decision. Selector presence/PASS does not admit real-data estimand, source authority, external caller lifecycle or protected production inputs.'})
 rows.append({'bundle':r['bundle'],'finding_ids':r['finding_ids'],'candidate_implementation':r['candidate_implementation'],'candidate_tree':r['candidate_tree'],'scientific_implementation':h.get('scientific_implementation_sha',h.get('implementation_sha')),'receipt_head':head,'receipt_binding':r['owner_receipt'],'declared_selectors':declared,'manifest_tests':r['manifest_tests'],'manifest_source_test_refs':r['manifest_source_test_refs'],'actual_native_selectors':actual,'per_id':perid,'bounded_equivalents':[]})
def equivalents(bundle,ids,path,names,property,limit):
 r=next(r for r in rows if r['bundle']==bundle);pool=[a for a in r['actual_native_selectors'] if a['path']==path and a['outcome']=='PASS' and a['same_test_file_bytes']];assert pool,(bundle,path)
 assert names,(bundle,path,'empty exact function list');f=files[file_id(r['candidate_implementation'],path)];known={x['name'] for x in f['test_functions']};assert set(names)<=known,(path,names,known)
 r['bounded_equivalents'].append({'finding_ids':ids,'candidate_selector':path.removeprefix('policy-engine/'),'exact_test_functions':names,'test_file_ref':file_id(r['candidate_implementation'],path),'actual_pass_check_refs':sorted({a['check_ref'] for a in pool}),'property':property,'outcome':'PASS','limit':limit,'scope':'Equivalent finite acceptance property, not execution of the missing proposed filename nor an assertion that the complete finding has closed.'})
equivalents('GRF-01',['B216','B217'],'policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_latent_oracle.py',['test_b216_complete_three_node_domain_matches_latent_dag_oracle','test_b217_perfect_do_matches_latent_dag_for_all_action_sets','test_graph_oracle_distinguishes_fork_from_collider_at_rule_consumer'],'200 fully specified three-node ADMGs: all2400 ordered m-separation queries and19200 post-surgery queries equal independent latent-DAG ancestral moralization; real Rule1 distinguishes fork/collider and Rule3 removes a pure confounded action. Separate actual collider and incident-bidirected-cut removals each exit1/FAIL with declarations retained.','No general PAG/ID/temporal completeness. LA-007/LA-019 full legacy retirement/plugin/dynamic-filename paths are UNRUN in this defining graph suite; exact source selectors do not close them.')
equivalents('GRF-02',['B219'],'policy-engine/tests/unit/ir/test_causal_graph_networkx_roundtrip.py',['test_native_networkx_mixed_export_after_cas_all_input_permutations','test_native_networkx_export_loss_is_detected_with_markers_preserved','test_warm_graph_copy_export_and_topology_agree'],'Genuine NetworkX3.6.1 MultiDiGraph exports all directed/bidirected/lag1/lag2/duplicate complete payloads after CAS→new reader for120 permutations (60unique). DiGraph replacement retains graph declarations but fails full edge-multiset oracle. Warm copy/export agrees with cold topology.','NetworkX supported exporter only; no Rustworkx/Kuzu execution witness.')
equivalents('GRF-02',['B220'],'policy-engine/tests/unit/ir/test_causal_graph_networkx_roundtrip.py',['test_warm_graph_copy_export_and_topology_agree'],'Actual warm ancestors/Kuzu projection/NetworkX export; mutation of edge vector refuses; copied empty edge set agrees with fresh cold model dumps/ancestors/derived edge rows/export.','This exact tracked native selector proves edge-vector immutability and warm/cold copy cache coherence. Full nested metadata mutation and weakref cleanup need their independently source-bound controls; they are not asserted by this five-file56PASS selector. No arbitrary backend cache safety claim.')
equivalents('FRY-01',['LA-001'],'policy-engine/tests/unit/foundry/compile/test_randomization.py',['test_randomization_owner_preserves_treasury_plan_bytes_and_seed_laws','test_randomization_salts_match_historical_hash_oracle_and_round_trip','test_v1_plan_bytes_remain_readable'],'Seed0/nonzero(-3 included) salts match independent SHA256 historical formula; canonical/legacy bytes equal; node-storage permutation/repeat compilation builder and literal v1 plan remain byte-compatible.','Selected synthetic program basis; no speed or economic validity inference.')
equivalents('FRY-01',['LA-001'],'policy-engine/tests/unit/foundry/compile/test_treasury_execution.py',['test_compiled_seed_and_persisted_salts_drive_actual_native_kernel','test_unmarked_historical_plan_keeps_sequential_default_and_override','test_profile_rejects_cas_bound_same_shape_wrong_property_before_kernel','test_actual_rng_bridge_removal_is_detected_while_profile_and_cas_remain','test_public_execute_cas_snapshot_consumer_uses_bound_profile','test_versioned_legacy_mechanism_node_and_graph_storage_permutation','test_native_skipped_prior_draw_cannot_move_versioned_node_stream','test_actual_registered_dispatcher_consumes_versioned_node_seed'],'Real compiler→Treasury+ExecPlan CAS inputs→native JAX adaptive-agent kernel→StateDelta→GlobalState/public fresh snapshot reader equals independent salt/fold-in RNG oracle. Null/zero/nonzero/large seeds and overrides, legacy sequential plans, malformed same-shape source-bound plans and salt-word/bridge removal are distinguished.','Versioned Treasury profile/adaptive-agent consumer, not a four-family certificate-to-state witness.')
equivalents('FRY-01',['LA-002'],'policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_families.py',['test_catalog_family_owner_preserves_ids_assumptions_and_unknown_id_behavior','test_ic_service_binds_family_lookup_to_catalog_owner','test_registered_family_requires_native_certificate_for_actual_policy'],'All four catalog IDs exact parameters/assumptions and unknown-ID refusal; IC service binds canonical lookup. Actual bayes_tax_pl positive and negative schedule yields real IR-owned certificate via CAS and fresh reader with same catalog membership.','Runtime admission refuses all four catalog IDs; no owner-ratified family→state operation mapping supplied. Live activation required by F-M12 remains UNRUN; catalog/certificate PASS is not state execution.')
equivalents('FRY-01',['LA-037'],'policy-engine/tests/unit/foundry/contracts/test_layout.py',['test_both_layout_addresses_preserve_all_ir_object_identities','test_foundry_layout_facade_binds_ir_owner_without_compiler_hop','test_native_layout_and_family_builders_distinguish_inventory_from_state_paths','test_slot_family_manifest_includes_cell_families'],'Both exact historical addresses preserve all five IR object identities; poisoning intermediate builder leaves direct outer owner binding; native builders distinguish state_path/inventory/grouping/global fallback and default cell families. Native compile files are separately selected in same76PASS command.','API729 independent installed wheel/sdist companion proves unchanged layout/certificate bytes and neutral consumer paths; full hosted docs build and any four-family state activation remain UNRUN. API install excludes new Treasury implementation.')
equivalents('FRY-01',['LA-037'],'policy-engine/tests/unit/foundry/compile/test_compile_artifact_contracts.py',['test_native_compile_artifacts_survive_scientist_consumer_and_cas_reopen'],'Actual native compile artifacts persist, reopen through CAS and survive the true Scientist compiler consumer; complete input bindings and layout artifacts remain source-bound.','Exact03bb native76 selector includes this consumer; full docs/build admission and four-family activation remain UNRUN.')
equivalents('CAU-04',['B212','B213'],'policy-engine/workers/dowhy-014/tests/test_worker.py',[x['name'] for x in files[file_id(next(r for r in rows if r['bundle']=='CAU-04')['candidate_implementation'],'policy-engine/workers/dowhy-014/tests/test_worker.py')]['test_functions'] if any(v in x['name'] for v in ['point_only','interval','estimate','target','contrast'])],'Selected genuine Python3.12.14/DoWhy0.14 backend scientific tests retain real identified estimand/method/contrast/target and typed optional interval profile; own full25PASS worker output and exact numerical MethodJob/CAS/fresh application3.14 reader are separate bound checks. Original B212 is point-only/no manufactured interval; B213 is identified-estimand/contrast/target binding.','App baseline Python3.14 optional in-process backend file SKIP/FAIL remains distinct. Real production input/admission UNRUN; synthetic coverage property is not real-data coverage. This audit does not promote a test selection to default-backend PASS.')
equivalents('CAU-04',['B212','B213'],'policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py',['test_public_complete_report_builder_abi_and_real_producer_invocation'],'Exact public static factory invokes genuine producer, retains class/function pickle FQN, produces the complete worker typed report through normalized public parameters; source-owned numerical replayer/CAS and installed ab56 companion bind actual canonical projection separately.','The recorded complete parent command contains5skips and a pydoc harness failure; only corrected66 single producer selector is PASS. No whole-file PASS is inferred.')
for r in rows:
 # Exact recorded commands/env, not newly invented test names. Replaying these on G integration SHA requires that source/test byte differences are reviewed and a fresh result.
 refs=sorted({a['check_ref'] for a in r['actual_native_selectors'] if a['outcome']=='PASS' and a['same_test_file_bytes'] and (any(a['path']==d['selector'] for d in r['declared_selectors']) or any(a['path']==e['candidate_selector'] or a['path'].removeprefix('policy-engine/')==e['candidate_selector'] for e in r['bounded_equivalents']))})
 r['G_exact_recorded_rerun_check_refs']=refs
 r['G_admission_rule']='Resolve existing selected files against G candidate first, compare bound bytes/providers to owner immutable implementation, then rerun using admitted application/actual selected backend profiles. Receipt cwd and interpreter are historical concrete cloud executions; do not treat their availability on G as guaranteed. No missing proposed filenames passed, no marker absence passed, and no production positive inputs inferred.'
 if r['bundle'] in ['GRF-01','FRY-01']:
  r['remaining_acceptance_axes_outcome']='UNRUN'
  r['remaining_axes']=['LA-007/LA-019 arbitrary plugin/dynamic-filename/sibling retirement full lifecycle not established by native graph primitives'] if r['bundle']=='GRF-01' else ['LA-002 four-family certificate-to-state operation mapping','LA-037 full documentation/build acceptance and shared family activation']
 if r['bundle']=='GRF-02':
  next(x for x in r['per_id'] if x['id']=='B220')['audit_remaining_axes']={'outcome':'UNRUN','finding_verification_state':'limited_pending_missing_discriminating_controls','required_property':['deep nested metadata mutation refusal/isolated returned projection','actual old adjacency cache-entry weakref cleanup'],'reason':'Exact five-file graph56 source bodies contain no executed discriminating nested-write or weakref cleanup control. Owner independently confirmed missing fresh proof; legacy baseline greens are not substituted. Warm edge-vector refusal/copy/cache agreement is the only native B220 equivalent bound above.'}
 # Attach full recording of native parent/red/skip checks to avoid hiding negative outcomes.
 r['all_owner_check_refs']=[k for k in checks if k.startswith(r['receipt_head']+':'+r['receipt_binding']['path']+'#')]
# Append final exact B220 mechanism delta while preserving earlier missing-axis/FAIL evidence.
b220=root/'b220-independent-review'
if (b220/'review.json').exists():
 review=json.loads((b220/'review.json').read_text());final=review['implementation_sha'];runtime=review['runtime_and_test_sha'];ftree=review['implementation_tree']
 fresh=json.loads((root/'b220-author-evidence/native.json').read_text())
 newpaths=['policy-engine/tests/unit/ir/test_causal_graph_cache_rows.py','policy-engine/tests/unit/foundry/methods/catalog/causal/test_performance_primitives.py']
 for row in rows:
  if not row['bundle'].startswith(('GRF','SCM')):continue
  row['latest_owner_composed_implementation_sha']=final;row['latest_owner_composed_tree']=ftree
  row['prior_scientific_primary_receipt_scope']='The original primary method receipt binds6d; latest213 B220 is an append-only same-owner narrow cache/reader component. Prior scientific check results are preserved with exact original source, not promoted to final production or installed outcomes.'
  for decl in row['declared_selectors']:
   decl['latest_owner_file_ref']=file_id(final,decl['selector']);decl['latest_owner_present']=files[decl['latest_owner_file_ref']]['binding']['present']
  if row['bundle']=='GRF-02':
   row['final_b220_delta']={'candidate_implementation':final,'candidate_tree':ftree,'runtime_and_test_sha':runtime,'provider_ref':file_id(final,'policy-engine/src/polisyos/ir/analytics/causal_graph.py'),'native_test_file_refs':[file_id(final,p) for p in newpaths],'native_author_execution':fresh,'native_independent_execution':review['native'],'independent_review':scratch_bound(b220/'review.json'),'historical_6d_missing_axes':next(x for x in row['per_id'] if x['id']=='B220')['audit_remaining_axes'],'historical_row_mutation_defect':review['prior_defect'],'decision':'GO','outcome':'PASS','criterion_scope':'Original generic immutable topology/cache/copy/dump/export/cleanup property. All exactnew11 row cases and existing4 selectors (8cases including5nested) execute at fresh source; independent own4 controls +those19 are23PASS. True freshCAS+completeCSV/plainparameter ABI.','limits':['Live Kuzu database/Rustworkx not executed; no real-data identification or production admission.','Source213 differs from e2c only canonical fragment TOML; code and tests unchanged.','Prior absence/FAIL remains historical, not erased or labelled inherited.'],'G_exact_selectors':['tests/unit/ir/test_causal_graph_cache_rows.py','tests/unit/foundry/methods/catalog/causal/test_performance_primitives.py::test_cached_adjacency_reuse','tests/unit/foundry/methods/catalog/causal/test_performance_primitives.py::test_cached_adjacency_eviction','tests/unit/foundry/methods/catalog/causal/test_performance_primitives.py::test_published_graph_rejects_nested_topology_mutation','tests/unit/foundry/methods/catalog/causal/test_performance_primitives.py::test_warmed_derived_rows_are_not_reused_after_copy_update']}
   x=next(x for x in row['per_id'] if x['id']=='B220');x['final_audit_criterion_decision']={'check':'PASS','outcome':'closed_generic_criterion_recommendation','source_sha':final,'deciding_scope':'Fresh actual cache-row/dict/JSON/nativeCSV/CAS/copy/weakref controls; no subject causal effect or production authority claim','historical_gap_retained':True}
result={'schema':'policyos.e02.F.selector-equivalence-audit.v1','audit_mode':'readonly Git/source/receipt selector and property audit; no new source/test edits; no new methodological test run','audited_base':base,'G97_candidate_audited':False,'coverage':n['coverage'],'canonical_manifest':n['manifest'],'finding_owners':bound(base,ownpath),'finding_owner_rows':fowners,'denominator':{**n['denominator'],'declared_manifest_selectors':17,'present_candidate_selectors':14,'missing_proposed_candidate_selectors':3,'declared_path_recorded_PASS':13,'declared_path_recorded_UNRUN':4},'coverage_selector_generation':{**json.loads((root/'coverage-selector-generator.json').read_text()),'output_bindings':{p:scratch_bound(root/p) for p in ['coverage-selector-generator.stdout.txt','coverage-selector-generator.stderr.txt','coverage-selector-generator.json']}},'original_source_card_blocks':n['source_card_blocks'],'original_source_cards_full':scratch_bound(root/'selector-original-source-cards.json'),'bundles':rows,'test_files':files,'native_checks':checks,'limits':['This audit binds exact original card/manifest selectors to immutable owner implementations and recorded check results. It does not rerun G integrated production candidate97.','A recorded PASS on a whole file does not certify every original criterion or production authority. Per-ID owner criterion decisions and remaining axes are kept explicitly.','Test-file equality is a test denominator proof, not proof that all runtime dependencies are unchanged. Final G must rebind/replay the exact integrated candidate and preserve typed limits.','CAU-04 default optional in-process profile SKIP/FAIL is preserved; actual admitted worker3.12 and installed composed ab56 are finite separate backend witnesses.','Three paths were proposals in original cards, not found existing selectors. Equivalent finite property tests never claim those filenames ran.','No architecture/invocation FAIL is attributed inherited without exact paired P41 replay.'], 'source_equivalence_companion':scratch_bound(root/'graph-selector-source-equivalence.json')}
# Durable append-only new mechanism primary and genuine latest installed review.
publication_head='bf335dd687c313fda9001fa3bb1365df6bc5ae1f'
publication_path='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-cache-immutability-20261006.json'
publication=json.loads(read(publication_head,publication_path))
assert publication['candidate_sha']=='2137961b0d3a2b39b85c5a57bf774777d2a4204e' and publication['closure_ids']==['B220']
new_checks=[]
for i,c in enumerate(publication['checks']):
 refs={}
 for field in ['output','execution_ref','stdout_ref','stderr_ref','stdin_replayer_ref']:
  value=c.get(field);path=value if isinstance(value,str) else value.get('path') if isinstance(value,dict) else None
  if path and path.startswith('policy-engine/'):refs[field]=bound(publication_head,path)
 new_checks.append({'check_index':i,'recorded_check':c,'committed_outputs':refs,'audit_role':'Exact published append-only primary execution; prior native/control source retained, not rerun by selector audit.'})
result['latest_component_publications']={'B220_cache_immutability':{'receipt_head':publication_head,'receipt':bound(publication_head,publication_path),'candidate_sha':publication['candidate_sha'],'implementation_commits':publication['implementation_commits'],'closure_ids':publication['closure_ids'],'recorded_checks':new_checks,'scope':'Fresh original generic cache/topology/copy/reader/cleanup criterion; original6d defect/gap remains historical. LiveKuzu/realdata UNRUN.'}}
for row in rows:
 if row['bundle']=='GRF-02':row['final_b220_delta']['published_primary_receipt']=bound(publication_head,publication_path)
latest=root/'installed-latest-independent'
if (latest/'review.json').exists():
 installed=json.loads((latest/'review.json').read_text())
 assert installed['implementation_sha']=='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6' and installed['own_native_total']==36
 result['latest_component_publications']['installed_latest_dependency_companion']={'candidate_sha':installed['implementation_sha'],'candidate_tree':installed['implementation_tree'],'review':scratch_bound(latest/'review.json'),'full_transfer':scratch_bound(latest/'transfer-selection.json'),'decision':'GO','outcome':'PASS','own_native36_pass':True,'limits':installed['limits'],'scope':'Separate actual wheel/sdist current-source ABI/cache companion: complete3146Python2917resource byteproof,13+5 cases each. Not execution of missing proposed selectors or production source authority.'}
 installed_head='3dde887e22592cdd7c1fe8865707afdfd72dc6fb'
 installed_path='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-latest-dependencies-20261006.json'
 installed_publication=json.loads(read(installed_head,installed_path))
 assert installed_publication['implementation_sha']==installed['implementation_sha'] and installed_publication['candidate_tree_sha']==installed['implementation_tree'] and installed_publication['closure_ids']==[]
 assert all(isinstance(c['output'],str) and c['outcome'] in {'PASS','FAIL','SKIP','ERROR','UNRUN'} for c in installed_publication['checks'])
 transport_proof=[];own_transferred=0
 for record in installed_publication['transport_records']:
  raw=read(installed_head,record['path']);assert raw is not None and len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['sha256']
  decoded=gzip.decompress(raw) if record['encoding']=='gzip' else raw
  assert len(decoded)==record['raw_original_bytes'] and hashlib.sha256(decoded).hexdigest()==record['raw_original_sha256']
  if record['encoding']=='gzip':assert len(decoded)==record['decompressed_bytes'] and hashlib.sha256(decoded).hexdigest()==record['decompressed_sha256']
  if record['raw_original_path'].startswith(str(latest)+'/'):
   assert decoded==Path(record['raw_original_path']).read_bytes();own_transferred+=1
  transport_proof.append({'binding':bound(installed_head,record['path']),'encoding':record['encoding'],'decoded_bytes':len(decoded),'decoded_sha256':hashlib.sha256(decoded).hexdigest(),'outcome':'PASS'})
 assert len(transport_proof)==112 and own_transferred==25
 result['latest_component_publications']['installed_latest_dependency_companion'].update({'receipt_head':installed_head,'published_receipt':bound(installed_head,installed_path),'published_independent_review':bound(installed_head,installed_publication['independent_review']['installed_fit_go']['path']),'complete_transport_byte_checks':transport_proof,'complete_transport_files':112,'own_selected24_plus_selection_exact_raw_readback':25,'checks_output_type_and_outcome_enum':'PASS','closure_ids':[],'related_finding_ids':installed_publication['related_finding_ids'],'per_id':installed_publication['per_id'],'final_publication_rule':'All112 complete stored bytes and gzip decoded bytes re-read from immutable published Git; reviewer25 raw companions equal original frozen bytes. No chats required. Scientific code5cd and installed source tree unchanged.'})

(root/'selector-equivalence-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':scratch_bound(root/'selector-equivalence-audit.json'),'bundles':len(rows),'test_file_bindings':len(files),'recorded_checks':len(checks),'equivalent_properties':sum(len(r['bounded_equivalents']) for r in rows),'denominator':result['denominator']},indent=2))
