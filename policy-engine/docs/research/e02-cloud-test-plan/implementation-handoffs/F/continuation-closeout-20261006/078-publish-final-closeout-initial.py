import json,hashlib,gzip,subprocess,sys,shutil
from pathlib import Path
root=Path('/workspace/e02-F-closeout-20261006'); base=Path('/tmp/e02-F-continuation-20261006'); prefix=Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F'); target=prefix/'continuation-closeout-20261006'; dest=root/target
packet='f17b9a52784d9484ef65563dc6695240629bdfc6'; source='8236d9c368336a5ea20c1586f29aea7321db6536'; tree='724a77c88d4e6699ffead58a5e3e3990fb88640a'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==packet
assert not dest.exists(); dest.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def gitref(head,path):
 b=subprocess.check_output(['git','show',head+':'+str(path)],cwd=root);return {'head':head,'git_ref':head,'path':str(path),'bytes':len(b),'sha256':sha(b)}
selpath=Path(sys.argv[1]); selection=json.loads(selpath.read_text()); items=selection.get('items',selection.get('files'));assert isinstance(items,list)
reviewpath=Path(sys.argv[2]); review=json.loads(reviewpath.read_text())
assert review['check']=='PASS' and review['decision']=='GO_BOUNDED_METADATA_CUSTODY' and review['packet_sha']==packet and review['scientific_source_sha']==source and review['scientific_source_tree']==tree
# Both literal independent signed review and complete registry transport are preserved.
inputs={str(Path(e['path'])):e for e in items}
for path in [selpath,reviewpath,base/'correct-current-captions.py',base/'current-caption-correction.json',base/'publish-final-closeout.py',base/'root-final-admission'/'doctor.json',base/'root-final-admission'/'doctor.stderr']:
 b=path.read_bytes(); inputs.setdefault(str(path),{'path':str(path),'bytes':len(b),'sha256':sha(b)})
for path in sorted((base/'root-closeout-publication').iterdir()):
 if path.is_file():
  b=path.read_bytes();inputs.setdefault(str(path),{'path':str(path),'bytes':len(b),'sha256':sha(b)})
records=[]
for no,(name,e) in enumerate(sorted(inputs.items())):
 path=Path(name); b=path.read_bytes();assert len(b)==e['bytes'] and sha(b)==e['sha256'],name
 encoded=e.get('encoding','raw');decoded=gzip.decompress(b) if encoded=='gzip' else b
 if e.get('decoded_sha256'):assert sha(decoded)==e['decoded_sha256'] and len(decoded)==e['decoded_bytes']
 name=f'{no:03d}-'+path.name
 if encoded=='raw' and len(b)>131072:
  out=gzip.compress(b,compresslevel=9,mtime=0);name+='.gz';encoded='gzip'
 else:out=b
 p=dest/name;p.write_bytes(out)
 records.append({'path':str(target/name),'bytes':len(out),'sha256':sha(out),'encoding':encoded,'decoded_bytes':len(decoded),'decoded_sha256':sha(decoded),'original_execution_path':str(path),'role':'Full deciding reviewer/publication/admission output or exact replayer; no scientific verdict inferred from custody.'})
write(dest/'transport.json',{'schema':'policyos.e02.complete-output-transport.v1','files':records,'stored_files':len(records),'stored_bytes':sum(r['bytes'] for r in records),'decoded_bytes':sum(r['decoded_bytes'] for r in records),'full_bytes_preserved':True,'historical_failed_attempts_preserved':True})
registry={r['original_execution_path']:r for r in records}; localref=lambda p:registry[str(p)]
packpath=prefix/'continuation-transfer-20261006'; idx=json.loads(subprocess.check_output(['git','show',packet+':'+str(packpath/'index.json')],cwd=root)); order=json.loads(subprocess.check_output(['git','show',packet+':'+str(packpath/'source-order.json')],cwd=root))
assert idx['finding_count']==35 and idx['bundle_count']==17 and idx['original_card_bindings']==36 and len(idx['receipt_registry'])==37 and len(idx['topics'])==12
refs=(base/'root-closeout-publication'/'refs.stdout').read_text().splitlines();assert refs[0]==packet
transport=json.loads((root/packpath/'artifact-transports.json').read_text())
cleanup=[r for r in transport['files'] if r.get('original_execution_path','').endswith('/cleanup-input-custody/cleanup-candidates.json')];assert len(cleanup)==1
closed=[r['finding_id'] for r in idx['finding_rows'] if r['outcome']=='closed']
rows=[{k:r[k] for k in ['finding_id','primary_bundle','primary_tsv_owner','original_source_criterion_refs','criterion_short_ru','actual_consumer','source_scope','oracle_and_negative','check','outcome','technical_original_criterion_recommendation','technical_check','implementation_sha','candidate_tree_sha','ROOT_adjudication_ref','complete_audit_row_ref','current_per_ID_receipt','original_criterion_remainder','separate_unavailable_inputs_or_authority','next_owner']} for r in idx['finding_rows']]
receipt={
 'schema':'policyos.e02.implementation_handoff.v1','unit':'F','slice':'continuation-closeout-20261006','branch':'codex/e02-F-closeout-20261006','worktree_root':str(root),'pull_request':'https://github.com/DenisKopylov/polisyos/pull/65',
 'slice_base_sha':'421f1dd977b237307394c68820caab4156716eb2','slice_base_tree_sha':'0508db0976255da2d970168d1300ec6dbafcb1b2','common_base_sha':'198076863e143dea9f89f02734b13d50dae3eed5','candidate_source_sha':source,'candidate_tree_sha':tree,'implementation_commits':[],'component_role':'Separate committed final source/evidence handoff; product code source and immutable packet are external exact commits, not this document carrier.',
 'frozen_packet_sha':packet,'frozen_packet_tree':subprocess.check_output(['git','rev-parse',packet+'^{tree}'],cwd=root,text=True).strip(),'superseded_current_caption_packet_sha':'d645cea93fe5bde8419b5ecbe6b612209891e16d','historical_inputs_are_not_rewritten':True,
 'closure_ids':closed,'closure_ids_role':'F bounded recommendations only; no G formal acceptance','formal_G_acceptance':False,'code_ready_vs_G_accepted':'Implemented shared properties and supported finite migrations are source code-ready with independent behavioral evidence. G separately reviews/applies and replays its exact composed candidate; scientific/institutional owners supply missing authority/law/budget inputs.',
 'counts':idx['summary'],'full_inventory':{'IDs':35,'bundles':17,'original_card_bindings':36,'LA_016_duplicate_binding_one_ID':True,'components':37,'topics':12},'per_id':rows,
 'full_original_criterion_ledger_ref':gitref(packet,packpath/'full-audit.json'),'full_35_row_report_ref':gitref(packet,packpath/'REPORT.md'),'index_ref':gitref(packet,packpath/'index.json'),'complete_output_transports_ref':gitref(packet,packpath/'artifact-transports.json'),'complete_source_history_dependency_and_full_diff_bindings_ref':gitref(packet,packpath/'source-order.json'),'component_registry':idx['receipt_registry'],'topic_refs':idx['topics'],
 'independent_final_validation':{'check':'PASS','reviewer':'/root/graph_scm','writer':'/root','exact_packet_sha':packet,'signed_review_ref':localref(reviewpath),'complete_selection_ref':localref(selpath),'scope':'Full immutable metadata/Git bytes/decoded bytes/original35 cards/36bindings/37components/12topics/canonical per-ID and independent semantic custody validation, actual adversarial denominator/hash/tree controls. Does not invent production authority or convert global gates to PASS.','prior_d645_review':'Actual byte validator PASS; current semantic caption HOLD, all initial errors/controls/outputs preserved. Four current captions corrected forward before final independent GO.'},
 'independent_semantic_original35_review_ref':idx['signed_independent_semantic_review_ref'],
 'checks':[
 {'check':'PASS','name':'installed source wheel','source_sha':source,'result':'199PASS/5explicitdeselected/0FAIL/ERROR/SKIP; real3.14 consumer and real pinned3.12/DoWhy0.14 worker'},
 {'check':'PASS','name':'independent rebuilt-sdist','source_sha':source,'result':'199PASS/5explicitdeselected/0FAIL/ERROR/SKIP;3459site files and archive bytes guarded'},
 {'check':'FAIL','name':'eight installed retained-marker property removals','expected':True,'result':'All8 actual fail withoutERROR/SKIP; original source/site byteguards restored unchanged'},
 {'check':'PASS','name':'runtime-warning membership replay','result':'Historical14 affected memberships→0;90unsuppressedLightGBMwarnings per site retained; raw full streams and historical classifications remain bound'},
 {'check':'PASS','name':'Ruff changed Python source','result':'92paths'},
 {'check':'FAIL','name':'full format','result':'3outsideFpaths retained; canonical A/G owners'},
 {'check':'FAIL','name':'full schema check','result':'FeedbackSolveResult and _manifest two Core/IR paths;5optional properties, canonical owner packet'},
 {'check':'FAIL','name':'full production invocation static','result':'26regressions/78newunresolved;coveragepartial;complete source/base denominator retained;P41not_established'},
 {'check':'FAIL','name':'conservative canonical export census','result':'38UNKNOWN/incomplete;computed/external unknowns not established supported clients'},
 {'check':'FAIL','name':'separate actual ABM diagnostic','result':'Canonical A semantic packet; finite fiscal/labor migration does not erase this FAIL'},
 {'check':'UNRUN','name':'actual whole Runtime/PDC semantic authority positive','result':'Missing current verifier/context/revision/appointment/full refs/distinct semantic identity/fresh challenge; no F self-issued seal'},
 {'check':'UNRUN','name':'B56 actual common admitted workload/budget','result':'Attempted commonpoolFAIL execution_context_missing before0fits; configured6/default15fold MethodJob bounded bridge is separate'},
 {'check':'UNRUN','name':'LA035 actual optimizer/intent','result':'Held; historical normalized income≥1 constant−1 replay remains measured baseline'},
 {'check':'UNRUN','name':'Lex current local-law/applicability','result':'Gaccepted00a6 genericdedupe remains distinct; localNormPack/source/jurisdiction/effective/custody owner packet required'},
 {'check':'UNRUN','name':'four historical175c nondeciding Git objects and historicalRDD textual lint raw','result':'No35deciding verdict depends on them; historicalcustodyunavailable preserved'},
 ],
 'source_bound_numerical_profiles':'Each component registry retains its own immutable source/tree/output. DiD selectedtheta/shareIF/160panel waves, nativeRBC vsrealdevrdrobust4036cases, GCM/Gaussian/surgery/stochastic/math.erfc and TMLEregulariid cache/EIF proofs are preserved, not rerun/relabelled as real-data authority. Python3.14 excludedDoWhy/EconML markers and optionalUNRUN/SKIP are not positive backend witnesses.',
 'minimal_missing_owner_packets_ref':gitref(packet,packpath/'minimal-owner-packets.json'),'unknown_production_refs_command':None,'production_data_uploaded':False,'scientific_or_institutional_authority_owner_is_not_G':True,
 'fresh_remote_checkpoint':{'main_sha':refs[2],'main_tree':refs[3],'G_sha':refs[4],'G_tree':refs[5],'anchor_ancestor':'PASS','no_auto_G_integration':True,'full_execution_outputs':'All root-closeout-publication files in complete transport'},
 'workspace_admission':{'check':'PASS','mode':'resume','exact_branch':'codex/e02-F-closeout-20261006','exact_absolute_path':str(root),'full_json':localref(base/'root-final-admission'/'doctor.json'),'scope':'Same existing own lane; no checkout creation, no prune/reset/rebase/switch.'},
 'patterns':{'P01_P02_P05_P09':'Real selectedMethodJob/CAS/freshreader and exact source/job/diagnostic identities','P10_P14_P27_P29_P32_P35_P36_P37_P38':'Independent oracles, full installed consumer ABI/origins/schema/version, full byte-bound receipts and property-removal controls, originalcard reconciliation, explicit unsupported laws/profiles','P40':'Class-wide normalized slots/rawsidecars, complete typedCASviews/optionals/lineage, accumulated Confidence returns, shared staticADMGadmission; unsupported semantic/law/temporal profiles have explicit finite residual/falsifier','P41':'not_established; no full disjoint zero-overlap inherited-red proof'},
 'cleanup':{'native_trash_available':False,'exact_full_candidate_list_ref':dict(cleanup[0],head=packet,git_ref=packet),'candidate_count':63,'candidate_admission':'CONDITIONAL; inactive-user/retirement/release checks NOT_PERFORMED, publication alone does not authorize moving an active candidate','permanent_deletion':False,'trash_emptied':False,'scratch_moved_to_trash':False,'preserve':'All source/docs/uniqueinputs/deciding outputs/Git object store and active worker/application/cuDNN environments; final8236sites evidence and historicald5nativeUNRUN separately preserved.'},
 'full_output_transport':str(target/'transport.json'),'final_doc_only_delta_does_not_require_new_science_wave':True,'G_next':'Preserve exact upstream commits and append-only history; review whole own source/dependencies/companions without cumulative160pathpatch. Fetch topicrefs, perform owner-supplied local readonly admission/authority/data residuals and affected composed consumer/packaging replay at one integrated freeze. No main publication authorization.',
 'publication_protocol':'This receipt is committed after source and frozen packet. Resolve the actual receipt carrier from Git; push/readremote and postpublication stored/decoded readback are completed by ROOT outside its own self-reference. PR remains open draft unmerged; no otherchat messages.'
}
write(root/prefix/'continuation-closeout-20261006.json',receipt)
print(json.dumps({'files':len(records),'stored_bytes':sum(r['bytes'] for r in records),'decoded_bytes':sum(r['decoded_bytes'] for r in records),'receipt_bytes':(root/prefix/'continuation-closeout-20261006.json').stat().st_size,'finding_count':len(rows)}))
