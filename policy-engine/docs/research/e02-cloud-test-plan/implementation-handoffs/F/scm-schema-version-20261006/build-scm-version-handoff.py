"""Transfer exact bounded schema runtime/generation evidence, without ledger writes."""
import pathlib,json,hashlib,subprocess,shlex
root=pathlib.Path('/workspace/e02-F-graph-20261006');scratch=pathlib.Path('/tmp/e02-F-continuation-20261006/graph');unit=root/'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F';dest=unit/'scm-schema-version-20261006';dest.mkdir(exist_ok=True)
scientific='eaf9d0e0ee2dae728351cbb3dfc333474c88931b';base='5b748047b4d5dfbee1e31721a8cec3a4ead2ace1'
current=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
names=['scm-version-original-red','scm-version-original-corrected-red','scm-version-original-bound-red','scm-version-development','scm-version-development-2','scm-version-owner-generation','scm-version-frozen-native','scm-version-frozen-owner-check','scm-version-full-generator-check','scm-version-remove-default','scm-version-remove-legacy-read','scm-version-public-fragment','scm-version-frozen-ruff']
optional=['scm-version-public-fragment-corrected','scm-version-final-owner-check','scm-version-fragment-body-equivalence']
names += [n for n in optional if (scratch/(n+'.json')).is_file()]
files=[scratch/(n+'.'+s) for n in names for s in ['json','stdout.txt','stderr.txt']]
files += [scratch/n for n in ['execute_check.py','generate-scm-owner-packet.py','remove-scm-version-property.py','check-scm-public-and-fragment.py','check-scm-fragment-body-equivalence.py','scm-version-original-test.py','feedback-scm-schema-delta.json','probe-readonly-runtime.py','current-runtime-identity.json','current-runtime-identity.stdout.txt','current-runtime-identity.stderr.txt','build-scm-version-handoff.py','verify-scm-version-transfer.py']]
files += [scratch/'scm-version-generated/owner-packet.json',scratch/'scm-version-generated/snapshots/ir/_manifest.json',scratch/'scm-version-generated/snapshots/ir/structural_causal_model_spec.schema.json']
manifest=[]
for src in files:
 name='generated-selected-'+src.name if src.parent.name=='ir' else 'generated-'+src.name if src.parent.name=='scm-version-generated' else src.name
 dst=dest/name;body=src.read_bytes();dst.write_bytes(body);manifest.append({'path':str(dst.relative_to(root)),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'original_path':str(src),'encoding':'raw'})
def ref(name):return str((dest/name).relative_to(root))
checks=[]
for n in names:
 r=json.loads((scratch/(n+'.json')).read_text());check=r['check'];role='current_deciding_check'
 if n in ['scm-version-original-red','scm-version-original-corrected-red']:role='historical_harness_development_not_deciding'
 if n=='scm-version-original-bound-red':role='original_semantic_failure'
 if n in ['scm-version-development','scm-version-development-2','scm-version-owner-generation']:role='development_not_frozen_source_proof'
 if n.startswith('scm-version-remove-'):role='current_property_removal'
 if n=='scm-version-full-generator-check':role='complete_required_generator_gate_FAIL_noP41'
 checks.append({'command':r['command'],'target_sha':r['source_sha'],'environment':{'application_interpreter':r['command'][0],'cwd':r['cwd'],'PYTHONPATH':r['PYTHONPATH'],'application_profile':'readonly Python3.14.7 current probe; author wrapper preserves executable but does not independently capture patch version for every earlier run','selected_worker_profile':'genuine locked Python3.12.14/DoWhy0.14 only when the native selected-fit case invokes it','selected_worker_environment_variable':'POLISYOS_DOWHY_WORKER_PYTHON=/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python for native version test command'},'input_closure':'complete argv selector and exact schema/model/generated owner sources;64iid knownsynthetic rows for actual selected fit; legacy/manual CAS profiles explicit; no admittedrealdata','outcome':check,'exit_code':r['exit_code'],'wall_s':r['wall_s'],'rss_kib':r['rss_kib'],'output':ref(n+'.stdout.txt'),'stderr_output':ref(n+'.stderr.txt'),'execution_receipt':ref(n+'.json'),'expected_negative':n.startswith('scm-version-remove-'),'role':role})
changed=subprocess.check_output(['git','diff','--name-only',base,current],cwd=root,text=True).splitlines()
bindings=[]
for path in changed:
 body=subprocess.check_output(['git','show',current+':'+path],cwd=root);assert (root/path).read_bytes()==body,path;bindings.append({'source_path':path,'source_sha':current,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
record={'schema':'policyos.e02.implementation_handoff.v1','unit':'F','slice':'scm-schema-version-20261006','role':'compatibility_companion','closure_ids':[],'related_finding_ids':['B221','B222','B223','B224','B225'],'bundle_ids':['SCM-01','SCM-02','SCM-03'],'slice_base_sha':base,'implementation_commits':[scientific]+([current] if current!=scientific else []),'candidate_tree_sha':tree,'scientific_runtime_sha':scientific,'branch':'codex/e02-F-graph-20261006','pull_request':None,'changed_paths':changed,'source_bindings':bindings,'checks':checks,'property':{'statement':'Current SCM producer/default/catalog/snapshot/CAS manifest agree on1.1; historical1.0 missing/explicit payloadversions remain1.0 and cannot inherit selectedworker authority.','original_divergence':'At literal6f source actualsource-bound DoWhyGCM producer returns1.1 whilecatalog/snapshot/default claim1.0; unversionedgcm constructor can bypass currentprovenance validation. Five semanticFAIL plus2legacyPASS before source repair.','mechanism':['default StructuralCausalModelSpec.schema_version1.1','existinggcm1.1 trainingrows/provenance validator now applies to defaultconstructor','actualCAS manifest validation + explicitlegacy1.0 injection before typedmodel construction','SCM1.1declaredBACKWARD/read1.0;1.0ruleNONE withcanonical same-version handling, noforwardclaim','canonicalgenerator singleSCMsnapshot/entry merge;98otherIRentries andmanifestheader preserved;complete2generatedreference documents equalcommittedsources'],'native_counts':{'PASS':15,'FAIL':0,'SKIP':0,'ERROR':0,'warnings':14},'removal_counts':{'default_removed_FAIL_expected':2,'legacy_injection_removed_FAIL_expected':1,'legacy_explicit_version_control_PASS':1},'genuine_fit':'Actual configured3.12/DoWhy0.14 run_worker gcm_fit on64rows, fittedcoefficient agreesindependent leastsquares;new1.1model CASfreshreader validatesoriginalactualsource andworkerresponse. No NumPyfallback/import-only witness.','public_abi':'Existing rootIR/analytics canonicalclass identity+classpickle+publicconstructor→actualCAS roundtrip measured; no newexport or wholeinventory/regeneration claim.','authority_purpose':'schema/custody compatibility and knownsyntheticfit only; no global uncertainty ratification or realdata causal authority'},'per_id':{i:{'check':'PASS','outcome':'limited','criterion':'SCMschema/custody compatibility layer only; corresponding original scientific criterion is decided in its primary property receipt','checks':['scm-version-frozen-native','scm-version-frozen-owner-check'],'limits':['No originalfinding closure override by this companion; no admittedrealdata or protectedproductionreadiness witness']} for i in ['B221','B222','B223','B224','B225']},'predicate_basis':'recomputed','capability_state_or_finding_state':'limited_companion_schema_property_PASS','compatibility':{'schema_version_default':'1.1','readable_legacy_versions':['1.0'],'historical_missing_version_manifest':'retained1.0','current_selected_gcm_requires_actual_rows_and_provenance':True,'legacy_manual_new_backend_claim':False,'public_export_names_changed':False,'global_uncertainty_schema_changed':False},'evidence_transfer':{'complete_companions':manifest,'companion_count':len(manifest),'all_moderate_deciding_bytes_committed':True,'canonical_fullreference_outputs':'Complete generatedreference bytes equal the alreadycommitted source_bindings docs/reference/ir/schema-catalog.md and docs/reference/schemas.md; no duplicate fullreference body needed.'},'limitations_and_next_owner':[{'owner':'G/generatedartifact owner','check':'FAIL','state':'limited','detail':'Fullcanonical gen_schema--check completesFAIL forfeedback_solve_result snapshot andIRmanifest. Exactcanonical comparison identifies5nested artifactref manifest_profile_sha256 additions, noSCMdefault dependency. Noothergeneratedwrite;P41not_established.'},{'owner':'F/root/G','check':'UNRUN','state':'limited','detail':'Independent schema reviewer queued; append actual fullreview before final publication.'},{'owner':'G/localdata owner','check':'UNRUN','state':'limited','detail':'Productioninputs/evaluationauthority arelocal and outside this finiteknownDGP schema packet.'}]}
for check in checks:
 check['argv']=check['command']
 check['command']=shlex.join(check['argv'])
 check['id']=pathlib.Path(check['execution_receipt']).name.removesuffix('.json')
record['baseline_cells']=[]
record['baseline_relation']='A new producer/catalog/default compatibility residual identified at literal6f95f55; older SCM baseline cells remain explicitly bounded in the source-bound primary receipt, not promoted to proof of this schema packet.'
record['property']['runtime_path']=['actual typed SCMFitData source CAS','configured genuine DoWhy0.14 gcm_fit subprocess','source-bound StructuralCausalModelSpec producer1.1','canonical default/catalog/snapshot and schema negotiation','CAS envelope with matching wire version','fresh load_structural_causal_model_spec reader','existing rootIR/analytics canonical class facade and polynomial/twin legacy consumers']
record['property']['proxy_divergence']='Before repair, the selected worker really produced1.1 while reflection catalog/default/snapshot said1.0; a matching fit_method=gcm marker on an unversioned constructor escaped current provenance validation. After repair that marker alone refuses, and removing the current default or legacy reader injection fails even while names and validators remain.'
record['property']['negative_controls']=['remove current default while retaining current registry/validators:2FAIL','remove legacy missing-version injection while retaining full prior loader body:1FAIL and explicit1.0control1PASS','independent actual canonical snapshot default, manifest version and digest corruption:3expectedFAIL','independent actual public CAS reader wrong/future wire versions and currentgcm marker without provenance:typed refusal']
record['compatibility']['constructor_migration_impact']='breaking'
record['compatibility']['scientific_source_and_metadata_append_distinct']={'scientific_source_sha':scientific,'metadata_source_sha':current,'nine_other_paths_byte_and_python_ast_equal':True}
record['runtime_identity_ref']=ref('current-runtime-identity.stdout.txt')
record['original_failure_harness_binding']={'runtime_source_sha':'6f95f55ca7d9c5cd9489256a354a27da058b46b9','new_test_not_in_that_git_tree':True,'copied_exact_harness':ref('scm-version-original-test.py'),'target_test_path':'policy-engine/tests/unit/ir/test_structural_causal_model_versions.py','harness_sha256':hashlib.sha256((scratch/'scm-version-original-test.py').read_bytes()).hexdigest(),'harness_equal_current_frozen_source':(scratch/'scm-version-original-test.py').read_bytes()==(root/'policy-engine/tests/unit/ir/test_structural_causal_model_versions.py').read_bytes(),'P41_inherited':'not_established','scope':'Concrete pre-repair runtime discriminator with a new fully transferred test input, not an inherited-red attribution.'}
dependency_paths=['policy-engine/workers/dowhy-014/'+name for name in ['worker.py','protocol.py','pyproject.toml','uv.lock','.python-version','README.md']]
dependency_paths += ['policy-engine/src/polisyos/foundry/methods/catalog/causal/'+name for name in ['_dowhy_worker.py','gcm_fit.py','gcm_query.py','twin_network_query.py']]
dependency_paths += ['policy-engine/tools/quality/diagnostics/'+name for name in ['gen_schema.py','generate_ir_reference_catalog.py']]
record['dependency_bindings']=[]
for path in dependency_paths:
 body=subprocess.check_output(['git','show',scientific+':'+path],cwd=root)
 assert body==subprocess.check_output(['git','show',current+':'+path],cwd=root),path
 record['dependency_bindings'].append({'source_path':path,'source_sha':scientific,'current_source_sha':current,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'unchanged_through_metadata_append':True})
review_dir=pathlib.Path('/tmp/e02-F-continuation-20261006/foundry/schema-review')
selection_path=review_dir/'transfer-selection.json'
assert selection_path.is_file(),'Full independent reviewer transfer selection required before publication'
selection=json.loads(selection_path.read_text())
review_files=[*selection['files'],{'path':str(selection_path),'bytes':selection_path.stat().st_size,'sha256':hashlib.sha256(selection_path.read_bytes()).hexdigest()}]
transport={}
for item in review_files:
 src=pathlib.Path(item['path']);body=src.read_bytes()
 assert len(body)==item['bytes'] and hashlib.sha256(body).hexdigest()==item['sha256'],src
 dst=dest/'independent'/src.name;dst.parent.mkdir(exist_ok=True);dst.write_bytes(body)
 copied={'path':str(dst.relative_to(root)),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'original_path':str(src),'encoding':'raw'}
 assert copied['path'] not in [x['path'] for x in manifest]
 manifest.append(copied);transport[str(src)]=copied['path']
review=json.loads((review_dir/'review.json').read_text())
assert review['source_sha']==current and review['science_source_sha']==scientific
independent_checks=[*review['checks'],review['initial_reviewer_harness_error']]
for original in independent_checks:
 check=dict(original)
 check['id']='independent/'+original['name']
 check['output']=transport[original['output']]
 check['role']='historical_independent_harness_ERROR_not_deciding' if original['outcome']=='ERROR' else 'independent_property_removal' if original['outcome']=='FAIL' else 'independent_current_deciding_check'
 check['expected_negative']=original.get('expected_rejection_met',False) and original['outcome']=='FAIL'
 check['original_output_refs']={'role':'original_scratch_metadata_not_current_git_locator','refs':original.get('output_refs',[])}
 check['output_refs']=[{'path':transport[x['path']],'bytes':x['bytes'],'sha256':x['sha256']} for x in original.get('output_refs',[])]
 checks.append(check)
record['independent_review']={'review':transport[str(review_dir/'review.json')],'selection':transport[str(selection_path)],'source_sha':review['source_sha'],'scientific_source_sha':review['science_source_sha'],'metadata_sha':review['source_sha'],'specification_verdict':review['specification_verdict'],'engineering_quality_verdict':review['engineering_quality_verdict'],'full_original_bytes_copied':True,'transport_mapping':transport}
record['evidence_transfer']['companion_count']=len(manifest)
record['limitations_and_next_owner']=[x for x in record['limitations_and_next_owner'] if 'Independent schema reviewer queued' not in x['detail']]
record['independent_check_scope']='24 native PASS (15author selectors repeated +9 independent reader cases),3canonical corruptionFAIL as expected; scoped source/version metadata acceptance, no global gate or originalfinding closure override.'
p=unit/'scm-schema-version-20261006.json';p.write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'receipt':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'checks':len(checks),'companions':len(manifest),'runtime_sha':scientific,'current':current}))
