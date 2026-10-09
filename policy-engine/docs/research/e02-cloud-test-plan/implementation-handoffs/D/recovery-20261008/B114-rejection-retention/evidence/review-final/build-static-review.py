from pathlib import Path
import subprocess,json,hashlib,ast,datetime,collections
lane=Path('/workspace/ORCH04-C11');out=Path('/workspace/ORCH04-evidence/review-c11/03698439')
source='03698439abfb1cb59f763397a182d8e0e393d40d';old='c1bffbd531b9b2c4339f073416c95d42d90ee317';receipt='4810a9c4eb4e2a3dc4bdaa946483fe93e86e8067';base='0321633c0e6d9a87bccfbbe889a4998934c52dd3'
def git(*args):return subprocess.check_output(['git',*args],cwd=lane)
def blob(ref,path):
 try:return git('show',f'{ref}:{path}')
 except subprocess.CalledProcessError:return None
def item(data):return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} if data is not None else None
def describe(ref):
 row=git('show','--no-patch','--format=%H%n%T%n%P',ref).decode().splitlines();return {'commit':row[0],'tree':row[1],'parents':row[2].split()}
def paths(a,b):return git('diff','--name-only',f'{a}..{b}').decode().splitlines()
author_path=Path('/workspace/ORCH04-evidence/c11/b114/source-freeze-final.json');author=json.loads(author_path.read_bytes())
assert author['source']==source and author['tree']==describe(source)['tree']
actual_status=git('status','--porcelain').decode()
assert not git('diff','--name-only','--','policy-engine/src','policy-engine/tests','policy-engine/release-fragments','policy-engine/pdm.lock','policy-engine/pyproject.toml')
delta=paths(receipt,source);assert delta==author['delta_paths'] and len(delta)==4
full=paths(base,source);assert len(full)==271 and set(full)=={r['path'] for r in author['whole_footprint']}
verified=[]
for row in author['whole_footprint']:
 data=blob(source,row['path']);ident=item(data);oid=git('rev-parse',f'{source}:{row["path"]}').decode().strip()
 assert ident=={'sha256':row['sha256'],'bytes':row['bytes']} and oid==row['blob']
 verified.append({**row,'verified_git_blob':True})
prepost=[]
for path in delta:
 before=blob(receipt,path);after=blob(source,path)
 for label,data in [('preimages',before),('postimages',after)]:
  if data is not None:
   dest=out/label/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 prepost.append({'path':path,'before':item(before),'after':item(after),'before_blob':git('rev-parse',f'{receipt}:{path}').decode().strip() if before is not None else None,'after_blob':git('rev-parse',f'{source}:{path}').decode().strip()})
owner='policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py'
def methods(ref):
 tree=ast.parse(blob(ref,owner));cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BayesianOptimizer');return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
a,b=methods(old),methods(source);method_delta=[k for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]
math_names=['_fit_gp','_prepare_training_data','_is_append_update','_model_train_x_matches_fitted','_fit_full_gp','_model_train_x','_effective_training_corpus','_select_training_subset','_warm_compatibility','_has_compatible_params','_evaluation_identity','_select_acquisition','_optimize_acquisition']
assert all(a[n]==b[n] for n in math_names)
math_equal=[{'method':n,'ast_sha256':hashlib.sha256(a[n].encode()).hexdigest(),'equal':True} for n in math_names]
old_run=json.loads(Path('/workspace/ORCH04-evidence/native-tester/C11-bdc94a82-native-wave/execution.json').read_text());test_paths=[s for s in old_run['argv'] if s.startswith('tests/') and s.endswith('.py')]
unchangedtests=[]
for path in test_paths:
 rel='policy-engine/'+path;prior=blob(old,rel);current=blob(source,rel);assert prior==current;unchangedtests.append({'path':rel,**item(current),'equal_c1_to_036':True})
# No Bayesian method entrypoint is referenced by the selected funnel/Phase5 fixtures.
import re
pattern=re.compile(r'BayesianOptimizer|BayesianConfig|\.warm_start\(|\.suggest\(|\.suggest_batch\(|\.set_state\(|\.get_state\(')
fixture_refs=[{'path':r['path'],'refs':pattern.findall(blob(source,r['path']).decode())} for r in unchangedtests]
assert all(not r['refs'] for r in fixture_refs)
source_changed=paths(old,source);nonreceipt_changed=[p for p in source_changed if '/implementation-handoffs/D/recovery-20261008/evidence/' not in p and not p.endswith('/implementation-handoffs/D/recovery-20261008/HANDOFF.json') and not p.endswith('/implementation-handoffs/D/recovery-20261008/README.md')]
manifest={'schema':'ORCH04.independent-c11-B114-source-review-manifest.v1','reviewer':'/root/review_c11','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':describe(source),'canonical_base':describe(base),'prior_implementation':describe(old),'published_parent_receipt':describe(receipt),'intermediate_rejection':describe('53a7cb99e4636e3cdfa903e22743e0a9b19a62a7'),'admission':{'remote':git('remote','get-url','origin').decode().strip(),'branch':git('branch','--show-current').decode().strip(),'path':str(lane),'actual_status':actual_status,'frozen_source_test_lock_equal_to_commit':True,'head':git('rev-parse','HEAD').decode().strip()},'delta':prepost,'full_footprint_count':len(full),'full_footprint':verified,'author_freeze':{'path':str(author_path),**item(author_path.read_bytes()),'271_rows_verified':True},'inherited_receipt_bytes':'No earlier receipt evidence/HANDOFF changed in four-path append; historical c1 receipts retain old source pins.','changed_methods_vs_c1':method_delta,'unchanged_method_bodies':math_equal,'unchanged_selected_test_inputs':unchangedtests,'selected_fixture_Bayesian_entrypoint_references':fixture_refs,'callclosure_qualification':'Prior selected126 funnel/Phase5 coverage =53fresh c1 +73qualifiedbdc, still source/input-qualified at same unchanged actual selected fixtures/own runtime paths. They reference no changed Bayesian method entrypoint. This is not a new126fresh run, not a universal dynamic import census, and does not transfer GP/state/numerical results across changed Bayesian module.','GP_qualification':'Whole Bayesian module/get_state/set_state/suggest bytes changed. Prior34whole-input GP equality applies bdc→c1 only; unchanged listed numerical/admission method bodies alone do not create final source numerical PASS. Fresh affected state/restore/no_refit/nativewarm scope required; priorboundedindependentNumPy oracle retains old pins unless independently refreshed.'}
(out/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
result={'schema':'ORCH04.independent-c11-B114-static-review.v1','reviewer':'/root/review_c11','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'verdict':'SCOPED_SOURCE_GO_AFFECTED_TEST_PENDING','source':describe(source),'manifest':'source-manifest.json','manifest_sha256':hashlib.sha256((out/'source-manifest.json').read_bytes()).hexdigest(),'complete_delta_paths':delta,'remaining_source_blockers':[],'findings':{'C11-review-3':'FIXED: full actual rejected Evaluation snapshots and existing refusal reasons retained per occurrence in ordinary version1 strategy artifact/state channel, repeat and caller-mutation isolation; oldcheckpoint completefalse without fabricatedhistory.','C11-review-4':'FIXED: actual adaptive planning receives same complete admitted/deduped corpus as training intake, ordinary/reversed presentation consistent; originalfixedbatchqEI retained.','C11-review-4-cold-batch':'FIXED: coldsingle uses effectivecorpus count; coldbatch offsets samecount. Currentiteration/refitcountersemantics unchanged.'},'restore_boundary':'Version/list/reason/candidateID shape guards and full normal produced-snapshot preservation; arbitrary caller-provided ledger evaluation mappings are not fully Evaluation-schema validated or authenticated. Restored complete flag is carried supplied-state metadata, not provenance/scientificauthority. Audit records never enter training.','P40':'Canonical widening of same effective-corpus planning intake class across adaptive/coldsingle/coldbatch; rejectedrecord explanation retention is separately fixed originalB114 branch. No exception waiver or adjacentsourcewriter.','required_affected_deciding_scope':['rejectionstateartifact1(all5reasons,repeatedreject,deepcopy,normalroundtrip,legacyincomplete)','authoredsingleadaptiveandfixedbatchqEI4(original+reversed)','actualsupportedSobolcoldsinglebatch2','existingrealnativewarmtraining1','lightweightstatewithoutdeps1','actualrestoredappend1','actualnorefit1','independentexactoriginalfixtureadaptive/cold/rejection probes and meaningful property removals'],'pending':'Independentaffectednative11andprobes/removals/affectedGPcontinuationclosure; review GO is not testerPASS/Gcodeacceptance/formalclosure/productionclaim.','prior_native_coverage':'126 qualified previous scoped cases53c1fresh+73bdcqualified, none freshly rerun here; exact fixture/ownruntimecallclosure unchanged. No GPmodule-wide priorinputequalitytransfer.','held_inputs':'B131/B137/B157/B161/B164 separately unchanged; B108fiscallaw,LA036conditionalproductionlaw,exactadditionalE/Fsupplierpacket unchanged; full joinedWarmStartBridge/BayesianCandidateGenerator/SearchLoopRunner/CAS supplierAPI/HNSWboundary remains separate from originalB114minimalrepair.'}
(out/'static-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'source':source,'tree':describe(source)['tree'],'full_footprint_count':len(full),'delta_count':len(delta),'changed_methods':method_delta,'manifest_sha256':result['manifest_sha256'],'static_result_sha256':hashlib.sha256((out/'static-result.json').read_bytes()).hexdigest(),'selected_test_inputs_equal':len(unchangedtests)}))
