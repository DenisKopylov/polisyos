import hashlib,json,pathlib,shlex,shutil,subprocess
repo=pathlib.Path('/workspace/e02-F-graph-20261006');scratch=pathlib.Path('/tmp/e02-F-continuation-20261007/graph');root='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F';stem='graph-intake-current-content-20261007';prefix=root+'/'+stem;dest=repo/prefix
receipt=json.loads((scratch/'handoff-draft.json').read_bytes());sha=receipt['candidate_sha'];assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==sha
reviewroot=pathlib.Path('/tmp/e02-F-continuation-20261007/api/graph-intake-review-647');oldroot=reviewroot.parent/'graph-intake-review';review=json.loads((reviewroot/'review.json').read_bytes());assert review['target_sha']==sha and not review['new_blockers'] and review['source_guard_unchanged']
material=[]
def add(source,relative,expected=None,role='full deciding/support material'):
 source=pathlib.Path(source);b=source.read_bytes();digest=hashlib.sha256(b).hexdigest()
 if expected is not None:assert len(b)==expected['bytes'] and digest==expected['sha256'],source
 target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
 material.append({'path':prefix+'/'+relative,'bytes':len(b),'sha256':digest,'original_execution_path':str(source),'role':role})
# Full moderate author outputs and source-bound replayers. Draft is intentionally not a decision.
for p in sorted(scratch.iterdir()):
 if p.is_file() and p.name not in {'handoff-draft.json','author-transfer-selection.json','receipt-custody-check.json'}:
  add(p,p.name,role='author exactsource or explicitly labelled development/support material')
for r in json.loads((scratch/'base072-cas-manifest.json').read_bytes())['files']:
 add(r['path'],'base072-cas/'+r['relative_path'],r,'immutable072 syntheticCASselectedblob/manifest/view/trace')
for origin,folder,key in [(oldroot,'independent-3e','items'),(reviewroot,'independent-647','required_files')]:
 selection=origin/('transfer-selection-with-warning.json' if folder=='independent-3e' else 'transfer-selection.json');data=json.loads(selection.read_bytes())
 for r in data[key]:add(r['path'],folder+'/'+pathlib.Path(r['path']).relative_to(origin).as_posix(),r,'historical3eBLOCK' if folder=='independent-3e' else 'independent647boundedGO')
 add(selection,folder+'/'+selection.name,role='complete independent transport selection')
 if folder=='independent-3e':add(origin/'transfer-selection.json',folder+'/transfer-selection.json',role='original15file historical selection unchanged')
def located(path):
 p=pathlib.Path(path)
 for origin,folder in [(reviewroot,'independent-647'),(oldroot,'independent-3e')]:
  if p.is_relative_to(origin):return prefix+'/'+folder+'/'+p.relative_to(origin).as_posix()
 if p.is_relative_to(scratch):return prefix+'/'+p.relative_to(scratch).as_posix()
 return str(path)
env=receipt['checks'][0]['environment']
for c in review['checks']:
 command=c['command'];receipt['checks'].append({'check_id':'independent647/'+c['id'],'command':shlex.join(command['argv']),'argv':command['argv'],'target_sha':sha,'target_tree_sha':review['tree'],'environment':env,'cwd':command['cwd'],'env':command['env'],'input_closure':c['result'],'outcome':c['outcome'],'exit':c['exit_code'],'output':located(c['output']),'result':c['result'],'source_unchanged':True})
error=json.loads((reviewroot/'finish-first-observer-error.json').read_bytes())
receipt['checks'].append({'check_id':'independent647/first-observer-metadata-error','command':shlex.join(error['argv']),'argv':error['argv'],'target_sha':sha,'environment':'Python3 scratch metadata observer; no scientific/source rerun','cwd':error['cwd'],'input_closure':error['scope'],'outcome':'ERROR','exit':error['exit_code'],'output':prefix+'/independent-647/finish-first-observer-error.stderr','meaning':'Literal observer matcher rejected legitimate typed-refusal diagnostics; corrected metadata only, all99 scientific checks retained exactoriginal outputs.'})
receipt['checks'].append({'check_id':'independent3e/deciding-content-BLOCK','command':'Independent corrected realCAS source discriminator archived in independent-3e/test_current_source_guards.py; exact original corrected CLI flags not captured in the old review','target_sha':receipt['implementation_commits'][0],'environment':env,'cwd':str(repo/'policy-engine'),'input_closure':'Genuine composed graph/source bundle, actual changed incompatible alignment report, canonical producer broken certificate while graph same; full raw corrected1FAIL2PASS preserved','outcome':'FAIL','output':prefix+'/independent-3e/adversarial-corrected.stdout','stderr':prefix+'/independent-3e/adversarial-corrected.stderr','replayer':prefix+'/independent-3e/test_current_source_guards.py','meaning':'Actual historical blocking counterexample, not setup-error or current647 FAIL. Current647 uses exact copied source and records fullliteral CLI.'})
receipt['independent_review']={'check':'PASS','outcome':'limited','scope':'Independent boundedGO exact647:79native+3original+17projection/cachePASS; exact18typedcertificatefield denominator15semanticfields+2operationalcaches+separatelyvalidatedpointer','reviewer':'F causal_api independent read-only','target_sha':sha,'full_review_ref':next(x for x in material if x['path']==prefix+'/independent-647/review.json'),'full_selection_ref':next(x for x in material if x['path']==prefix+'/independent-647/transfer-selection.json'),'historical3eBLOCK_ref':next(x for x in material if x['path']==prefix+'/independent-3e/review.json'),'historical3e_additive_warning_ref':next(x for x in material if x['path']==prefix+'/independent-3e/review-with-warning.json'),'observer_ERROR_preserved':True}
for r in receipt['per_id']:
 if r['finding_id']=='B218':
  r['outcome']='closed';r['original_storage_recommendation']='closed';r['criterion']='Original lag/self-lag representation/export and static-consumer safe-refusal law; currentcanonicalintake compactlag1/2 refusal measured, earlier exactsource losslessstorage evidence remains separate and unmodified'
  r['recommendation_basis']='Originalcard explicitly permits exact static incompatibility absent an established temporal transformation. Generic storage/static boundary is data-independent; no admitted realdata/Gauthority is required for this property. Prior root limited proposal is preserved historically, not overwritten.'
  r['limit']='Full temporal causal inference/protected readiness remains an unclaimed separate capability, not a reason to hold the original storage/static-refusal law. Existing graphprojection/export proofs remain on their own exactsource; no new temporal engine or ledger closure.'
receipt['capability_state_or_finding_state']='Bounded currentcontent/endpoint/static-intake property corrected. B214 original recommendation limited; B218 originalstorage/staticlaw closed recommendation, with fulltemporal/protected capability UNRUN separately. This companion issues noG/ledger acceptance.'
receipt['limitations_and_next_owner'][3]='F root/G own original/current adjudication and formal code/ledger acceptance. B214 arbitraryPAG capability limited; B218 originalstorage/staticlaw closed recommendation is separate from unclaimed fulltemporal/protected route.'
receipt['checks_denominator']={'canonical_records':len(receipt['checks']),'by_outcome':{v:sum(c['outcome']==v for c in receipt['checks']) for v in ['PASS','FAIL','ERROR','SKIP','UNRUN']},'scope':'checkrecords includehistorical3e/base072/removalFAIL/observerERROR androotUNRUN explicitly; not an aggregate current scientific PASS count','current_author_native_cases':79,'current_independent_native_cases':79,'current_independent_original_discriminators':3,'current_independent_projection_cases':17,'current_typed_certificate_fields':18,'material_files':len(material)}
receipt['evidence_transfer']={'status':'complete lossless storedbytes; no oversizedlogs or productiondata','full_output_manifest':{'path':prefix+'/outputs.json'},'files':len(material),'bytes':sum(x['bytes'] for x in material),'all_deciding_stdout_stderr_complete':True,'moderate_outputs_committed':True,'source_bound_replayer_rule':'Recorded commands require their actual immutable source checkout and supported environment. Use newunique output/CAS roots; historical072/3e evidence must not be rerun against647 and relabelled.'}
(dest/'outputs.json').write_text(json.dumps({'schema':'policyos.e02.full_output_manifest.v1','candidate_sha':sha,'files':material},ensure_ascii=False,indent=2)+'\n')
b=(dest/'outputs.json').read_bytes();receipt['evidence_transfer']['full_output_manifest'].update({'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
path=repo/(root+'/'+stem+'.json');path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'receipt':str(path),'checks':len(receipt['checks']),'material_files':len(material),'storedbytes':sum(x['bytes'] for x in material)},indent=2))
