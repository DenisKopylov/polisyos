from __future__ import annotations
import hashlib,json,os,shutil,subprocess,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
root=Path('/dev/shm/e02-orch03-20261008/c07')
scratch=Path('/dev/shm/e02-orch03-20261008/c07-checks')
relative=Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/parallel-20261008-c07')
out=root/relative
(out/'outputs').mkdir(exist_ok=True)
source='741af2a08a8dc5fa36340bf700c092c7fb51f651';tree='bfae04d141187c30e4f6bc14dbbbae00f6ee116c';base='f00dd7661a8d3329fb1fa1b049decb0d1d2f277b'
def git(*args): return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True).stdout
assert git('rev-parse','HEAD').decode().strip()==source
files=[]
for p in sorted(scratch.iterdir()):
    if p.is_file() and (p.suffix in {'.stdout','.stderr','.json','.xml','.patch','.py'}):
        shutil.copyfile(p,out/'outputs'/p.name)
        files.append({'path':str(relative/'outputs'/p.name),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'origin':str(p)})
review=Path('/dev/shm/e02-orch03-20261008/oracle-ir')
for name in ['review804.json','review804-environment.json','review741.json','review741-AST-py314.json','unit-oracle.json','b31-independent-proposal.md','check804.py','check804.out','check804.err']:
    p=review/name
    if p.exists():
        shutil.copyfile(p,out/'outputs'/('independent-'+name))
        files.append({'path':str(relative/'outputs'/('independent-'+name)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'origin':str(p),'author':'independent oracle_ir'})
(out/'evidence-index.json').write_text(json.dumps({'schema':'policyos.e02.output_custody.v1','execution_role':'C07','outputs':files,'empty_outputs':'Zero-byte stdout/stderr preserved, not omitted; all moderate deciding bytes committed. Scratch CAS/profile evidence retained locally, full source-qualified manifest pair committed.'},indent=2)+'\n')
checks=[]
counts={}
for label,outcome,scope in [
    ('final-affected','PASS','Source804 full four affected test files; 62 PASS, 0 unexpected failure/error/skip. Includes actual CAS plus fresh child and 44 existing envelope/core/value-evidence cases across three files; no scientific producer/ValuePort positive.'),
    ('retained-marker','FAIL','Source804 scratch remove runtime complete subject/unit and full role-set predicates, retaining models/enum/markers/diagnostics. Exactly9 intended DID NOT RAISE failures +1 fresh-child positive PASS. These expected controls are separate from unexpected failures.'),
    ('final-ruff','PASS','Source804 six changed Python files.'),
    ('final-format','FAIL','Source804 full six-file formatter; four red owner files. Own3 blank lines corrected later; preserved original red.'),
    ('final-companions','PASS','Source804 five root/analytics same-object facade exports, two schema1.0 exact-read/unknown-version refusals, release fragment render:8 probes.'),
    ('final-ref-boundary','ERROR','Harness attempt1 seeded prior native payload then changed lineage on same bytes; normalized IR return selected old default. Intended selected changed-source case not exercised. Assertion missing_source did not refuse; this is not a default-reader counterexample or PASS.'),
    ('final-ref-boundary2','ERROR','Harness attempt2 wrong attribute access on UncertaintyEnvelopeRef, which lacks manifest_profile_sha256. Setup AttributeError, not a product FAIL/PASS.'),
    ('final-ref-boundary3','PASS','Source804 corrected fresh-default cases: missing source/model refs, actual foreign source, resolved AST/outcome contradiction;4 PASS. Separate diagnostic shows prior actual producer selector loss. No current-producer or selected-view composition admission.'),
    ('final-manifest-pair','PASS','Diagnostic execution only: original Core put_json observer, both actual returned refs, full reopened default/selected manifests and bytes hash. Explicit selected C07 intake refuses. Underlying C06 selector-preservation property FAIL is separately recorded below.'),
    ('delta-defining','PASS','Exact source741 after independent delta-only review:18 defining/import/CAS/fresh-child/negative cases;0 FAIL/ERROR/SKIP. No relabelled source804 whole-suite PASS.'),
    ('delta-ruff','PASS','Exact source741 six changed Python files.'),
    ('delta-format','FAIL','Exact source741 remaining full-file format red in uncertainty.py and refs.py;4 other files formatted. No inheritedP41 attribution; new-owned whitespace fixed.'),
]:
    metadata=json.loads((scratch/(label+'.json')).read_text())
    item={'label':label,'command':metadata['command'],'target_sha':metadata['source_sha'],'target_tree':metadata['source_tree'],'environment':'Python3.14.7 locked root .venv; explicit lane PYTHONPATH; isolated scratch','input_closure':scope,'outcome':outcome,'exit_code':metadata['returncode'],'resources':{'wall_seconds':metadata['wall_seconds'],'maxrss_children_kib':metadata['maxrss_children_kib']},'output_refs':[str(relative/'outputs'/(label+ext)) for ext in ['.json','.stdout','.stderr']]}
    junit=scratch/(label+'.junit.xml')
    if junit.exists():
        t=ET.parse(junit).find('.//testsuite'); item['counts']={k:int(t.get(k)) for k in ['tests','failures','errors','skipped']};item['nodeids_ref']=str(relative/'outputs'/junit.name);counts[label]=item['counts']
    if label=='retained-marker': item['expected_outcome']='FAIL';item['unexpected_failures']=0;item['failure_reason']='DID NOT RAISE ValueError, all9; positive fresh child PASS'
    checks.append(item)
assert counts['final-affected']=={'tests':62,'failures':0,'errors':0,'skipped':0}
assert counts['delta-defining']=={'tests':18,'failures':0,'errors':0,'skipped':0}
assert counts['retained-marker']=={'tests':10,'failures':9,'errors':0,'skipped':0}
packet={
 'schema':'policyos.e02.dependency_packet.v1','execution_role':'C07','source_unit':'E','original_finding_owner':'A','finding_id':'B31','bundle_id':'EMP-01',
 'owner':'C06 canonical Core/IR artifact adapter; C07 canonical IR refs partner; G composes and generated family',
 'source_sha':'804a6aba31125372b0b57a10041c6d6aad375ad5','source_tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','semantic_carry_to_source':source,
 'status':'confirmed selector-preservation defect outside default-reader profile; not established current-producer identity/view composition',
 'exact_paths':['policy-engine/src/polisyos/ir/artifacts/io.py','policy-engine/src/polisyos/ir/artifacts/contracts.py','policy-engine/src/polisyos/ir/registry/refs.py'],
 'writer_leases':'C06 adapter/io companion and C07 typed refs only by explicit coordinated lease; no parallel shim or Core store replacement',
 'actual_witness':json.loads((scratch/'final-manifest-pair.stdout').read_text()),
 'trigger':'Core automatically returns a nondefault manifest_profile_sha256 for same native bytes plus different producer lineage, even when caller never explicitly selects a view. Current IR put_json_artifact normalizer/typed refs discard it. C10 must not adopt that as current producer evidence until preserved end to end.',
 'minimum_result':['Preserve actual Core-returned selected manifest identity through IR writer/ref/InputRef and fresh selected manifest resolution before normalization. Default historical refs preserve replay.','Actual samebytes/differentlineage output must reload the new requested subject/source; missing/fake/foreign/stale selector negatives refuse before content or job admission.','Give C07/C10 exact source SHA/tree/changed contract/complete produced refs+manifest+bytes and affected defining consumer output; then reconcile approved shared ref companions.'],
 'current_C07_bound':'Default-view artifact read/content/lineage only. Explicit incoming selected refs refuse before selector stripping; default relation production_value_eligible remains false. It cannot recover a selector already discarded by upstream writer.',
 'authority_limit':'Restoring selector is mechanical identity, not scientific identification or Runtime admission. Actual C10 ValuePort still needs its chosen existing verifier-backed supplier purpose/context/fresh challenge.',
 'deciding_output':str(relative/'outputs/final-manifest-pair.stdout'),'failed_harness_attempts':[str(relative/'outputs/final-ref-boundary.stderr'),str(relative/'outputs/final-ref-boundary2.stderr')]
}
(out/'C06-selected-view-producer-loss.json').write_text(json.dumps(packet,indent=2)+'\n')
card=git('show','198076863e143dea9f89f02734b13d50dae3eed5:policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md')
criterion=b''.join(card.splitlines(keepends=True)[592:606]);binding=hashlib.sha256(criterion).hexdigest();assert binding=='9311ba1b0fb2e6a3f180546c6118406c5781dbbfb57e27b28075b95a92fe371f'
paths=git('diff','--name-only',base,source).decode().splitlines()
footprint=[{'path':p,'candidate_blob':git('rev-parse',source+':'+p).decode().strip()} for p in paths]
admission=json.loads(git('show','de7b08ebbac72232c98d96ea74c3c0410864a7ba:policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/ORCH03/parallel-20261008-admission/manifest.json'))
admission['outputs']=[x for x in admission['outputs'] if x['requested']['branch']=='codex/e02-E-c07-20261008']
receipt={
 'schema':'policyos.e02.implementation_handoff.v1','unit':'E','execution_role':'C07','canonical_writer':'ORCH03 direct C07; no children','original_finding_owner':'A','slice':'persisted-value-subject-relation','created_at':datetime.now(timezone.utc).isoformat(),
 'closure_ids':['B31'],'bundle_ids':['EMP-01'],'closure_ids_meaning':'Original criterion covered by partial supplier slice; no finding closure asserted.',
 'slice_base_sha':base,'slice_base_tree':'d9a4e73a0e85fa11f865bf643c1b63fbe66c2767',
 'dependency_packet_commit':'7147ef63886dd95fb20cdb8ebb939d93663ca10d','implementation_commits':['804a6aba31125372b0b57a10041c6d6aad375ad5',source],
 'candidate_source_sha':source,'candidate_tree_sha':tree,'candidate_parent_sha':'804a6aba31125372b0b57a10041c6d6aad375ad5','branch':'codex/e02-E-c07-20261008','pull_request':None,
 'changed_paths':paths,'whole_source_test_companion_footprint':footprint,'baseline_cells':[],
 'write_lease':'Root admitted sole C07 writer: uncertainty.py, refs.py; actual root/api/schema registration companions; named new test_value_subject_relation.py; mechanism README, unique release, own E documents. No Core/value_evidence/A consumer/generated/lock/source schema snapshots rewritten.',
 'original_criterion':{'path':'policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md','source_sha':'198076863e143dea9f89f02734b13d50dae3eed5','lines':[593,606],'bytes':len(criterion),'byte_binding_sha256':binding,'full_original_text':criterion.decode()},
 'source_inputs':{'G_checkpoint':base,'G_tree':'d9a4e73a0e85fa11f865bf643c1b63fbe66c2767','A_readonly_sha':'8bfea70b2e2090ad5c541b103b7521efc01b30eb','A_tree':'fef42aadf2bf58ed5cc97ec827be99245a154253','E_selected_supplier_sha':'8d8e7b319e7eb6b57bc4ab3c4db5ca3070393f8c','E_tree':'192e584c646ee6df303b8793e7b92aa741dcaebb','selection':'C07 additive relation based on G1.1. Initial source pin is not whole carrier acceptance; no cumulative E merge or borrowed E PASS.'},
 'property':{'statement':'Two persisted default-view producer artifacts with exact resolved complete typed subject/estimand/unit/time/contrast/source/model lineage may be joined mechanically while preserving distinct identification/native channels; mismatch refuses and fresh reader recomputes manifests/bytes/full role roster. No authority minted.',
  'runtime_path':['Synthetic typed contract producer (not admitted scientific method): ValueOuterSet point4 and UncertaintyEnvelope asymmetric[1,10]','Canonical FileSystemCAS: typed subject plus full lineage manifest for each artifact','Existing IR uncertainty.resolve/persist_value_subject_relation','Fresh FileSystemCAS plus load_value_subject_relation re-resolves actual dependencies and native owner loader','Separate ValueOuterSet.from_persisted_payload / load_uncertainty_envelope in fresh child; root/analytics same-object facade'],
  'surface':['polisyos.ir.ValueArtifactSubject/ValueSubjectRelation and typed refs','polisyos.ir.analytics canonical same-object exports','Schema registry1.0 with exact-read/unknown-version refusal'],
  'oracle':'Fraction ratio↔percent exact scaling; independent oracle_ir seven probes. Subject coordinate excludes method FQN; native interval/point/functionals untouched.',
  'proxy_divergence':'Matching metadata says same estimand but resolved subject/population/time/contrast/unit/refs mismatch refuses; complete persisted relation/markers survive factor forgery but fresh recomputation rejects. An old default ref after producer selector loss reads old declared subject, so it cannot prove current producer quantity.',
  'negative_controls':['8 complete quantity/unit mismatch cases','Missing/extra/duplicate producer roster','Actual source/model missing refs and foreign source/outcome contradiction','Fake relation ref and retained-marker factor forgery','Actual native bytes corruption','Actual samebytes/different Core selected manifest profile refused if selector preserved','Runtime predicates removed in scratch while markers remain:9 intended failures plus1 fresh-child positive']},
 'authority':{'purpose':'Mechanical CAS content/manifest/lineage consistency only','authority_scope':'resolved_content_join_only','production_value_eligible':False,'verifier_provenance':'cas_bytes_manifest_lineage_recomputed.v1','scientific_identification':'not_established','Runtime_EvalSafety':'existing execution safety verifier purpose is distinct; no issuer/challenge fabricated by C07','actual_C10_fresh_ValuePort':'UNRUN'},
 'predicate_basis':'recomputed','predicates':{'default_bytes_manifest_lineage':'recomputed','complete_subject_unit_equality':'recomputed','actual_current_producer_identity':'not_established','scientific_admission':'not_established','actual_A_ValuePort':'not_established'},
 'checks':checks,
 'additional_measured_property':{'C06_producer_selector_preservation':'FAIL confirmed by actual selected Core return versus selector-free IR ref','diagnostic_exit_code':0,'output_ref':str(relative/'outputs/final-manifest-pair.stdout'),'scope':'Existing canonical IR adapter gap outside C07 default reader profile. This is not hidden as a passing producer or resolved authority.'},
 'development_attempts':[
  {'source':'uncommitted development before804a','outputs':['author.stdout','author-child-error.stderr'],'result':'1FAIL/14PASS: model subclass equality on fresh reader; normalized nested ref fixes persisted identity, native property not assumed passed.'},
  {'source':'uncommitted development before804a','outputs':['author2.stdout'],'result':'15PASS author characterization after identity correction.'},
  {'source':'uncommitted development before804a','outputs':['author3.stdout'],'result':'2FAIL/16PASS: added selected-view harness import/schema attribute error; actual Core integrity refusal had different expected regex. Corrected test harness, preserving Core refusal.'},
  {'source':'uncommitted development before804a','outputs':['author4.stdout'],'result':'18PASS prefreeze author characterization; final deciding source804/741 results separate.'},
  {'outputs':['author-lint.stdout','author-lint2.stdout','root-export-sort.stdout','format-before.stdout','test-format.stdout','test-format2.stdout'],'result':'All lint/format attempts retained. Five automatic lint fixes; root __all__ sort error corrected before freeze. Later exact formatter diff isolated owned3 blank lines; source741 fixes onlythose.'},
  {'result':'Initial Gcomposition metadata helper failed on nonexistent G posterior_summary.py; corrected nullblob representation. No product check or commit from failed metadata preparation.'}
 ],
 'delta_only_carry':{'source804':'62-test/9-removal output remains bound to804a/treebb1. No whole741 PASS inferred.','source741_delta':'Only3 blank-line changes, independent Python3.14 AST equality, source74118 defining/import checks fresh. Tests/native law/relations/negative executable AST unchanged.','uncomposed_E_Profile2':'Original selected B201/B202 weighted-median compatibility + named weighted mean/inverse-CDF equal-tail/jointlaw/raw-type/nonlinear/multi-envelope invariants retain E inputs. Text3way0conflicts != composed runtime PASS; no E supplier claims on current G-based blobs.'},
 'review':[{'path':str(relative/'outputs/independent-review804.json'),'sha256':'614acff56e96159d5298373189356d4e7d7ee21745d9db8558468ac7d7e6c717','target_sha':'804a6aba31125372b0b57a10041c6d6aad375ad5','verdict':'GO bounded nongating default-view relation; no B31 closure/G acceptance/ValuePort authority'}, {'path':str(relative/'outputs/independent-review741.json'),'sha256':'0cc55e166b0da2cd7ece126a720b7a65cf2e97f3831ff58138e733ee03038ad3','target_sha':source,'verdict':'GO delta-only whitespace and explicit measured C06 limitation; source804 evidence not relabelled'}],
 'capability_state_or_finding_state':'Bounded default-view IR reader mechanism code-ready with PASS; full B31 original criterion remains limited pending actual canonical C10 producer/readback/scientific basis. Producer currentness/view-composition not established.',
 'status':{'technical_supplier_property':'PASS in declared default-reader profile','code_ready':'bounded mechanical leaf ready for G review; known whole-file format red disclosed','finding_recommendation':'limited, not original B31 closure','G_source_acceptance':'not_issued','G_formal_finding_closure':'not_issued'},
 'limitations_and_next_owner':[
  {'owner':'C10 actual generation/ValuePort producer consumer','state':'UNRUN','input':str(relative/'C10-subject-join-input.json'),'next':'Persist actual supported identification/native outputs plus exact subject/complete lineage, validate supported identification kind and actual payloadlaw/coordinates/contrast/unit, resolve existing genuine supplier scientific purpose independently from Runtime execution safety, reopen both channels+relation in actual fresh ValuePort. Never turn generic relation read into identification proof.'},
  {'owner':'C06 adapter in coordination with C07 refs','state':'confirmed selector loss; selected/current producer composition UNRUN','input':str(relative/'C06-selected-view-producer-loss.json'),'next':'Preserve automatically returned nondefault manifest selector before C10 adoption; then affected selected-view/currentness checks only.'},
  {'owner':'G composition/generated family','state':'UNRUN','input':str(relative/'G-composition-companions.json'),'next':'Select original E supplier source history, reconcile owned uncertainty/registry facade companions, recompute schema/public inventory/reference family and corrupt-field drift on selected freeze. C07 supplies complete blobs, no generated hand-edits.'},
  {'owner':'C09/C08 actual conditional feature-law producer; G selected intake/BERL adapter','state':'no new IR companion commissioned','next':'Specific supplier contract: observed_feature_law, exact observed-feature order/units, source+model content/manifest/bytes, population/cohort/time/epoch/support/conditioning profile. Existing finite weighted strata or supported Gaussian projection selected by actual owner; parameter posterior/GCM noise posterior is not observed-feature law.'},
  {'owner':'Current source quality owner/C07 only owned delta','state':'FAIL full-file format; P41 not_established','next':'Remaining uncertainty.py/refs.py formatter red disclosed; no zero-overlap denominator/inherited claim. All own3 spacing defects corrected, lintPASS. Broad scanner/global inventory/optional backends not run by this narrow slice.'},
  {'owner':'G/C13 selected integrated freeze','state':'UNRUN','next':'Portable broad composed replay after selected source freeze/allreviews. No production uploaded or general scientific/model/current-law authority claimed.'}
 ],
 'patterns':{'P29':'Actual canonical CAS/manifests/current typed bytes plus fresh child, not markers alone.','P36':'B31 remains A/EMP01; E is relation supplier. Full original2949byte criterion, not shortlabel.','P37':'Mechanical predicates recomputed; current producer/scientific/A ValuePort unestablished.','P38':'Matching markers survive quantity and factor mismatch; removing actual predicate makes9 negatives fail.','P40':'Complete subject and full producer role-set choke point, bounded default-view reader. Second selector/currentness escape is disclosed class-wide C06 dependency with finite falsifier samebytes+changedlineage, not per-method ladder.','P41':'not_established; no inherited-red attribution or reused full-suite positive on changed source.'},
 'baseline_results':{'importer_command':'python3 policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py --check','importer_output':'{"ok":true,"files":["cells.tsv","properties.tsv","events.jsonl","gates.json","routes.tsv","verification.json"]}','grade':'index_transfer/navigation_only, raw archives0; baseline not candidate PASS','targeted_queries':['B31','B201','B202'],'ownership':'full finding-owners.tsv/card/coverage binding; B31 A/EMP01, B201/B202 E/UQS01'},
 'output_custody':{'index':str(relative/'evidence-index.json'),'complete_moderate_outputs':'All source804 and source741 commands/returncodes/nodeids/stdout/stderr/resources, removal patch/harness, independent reviews and failed harness attempts committed separately from source.','preservation':'Source/docs/deciding outputs and scratch CAS/current activeenv retained; no cleanup or permanent deletion.'},
 'admission':{'carrier_sha':'de7b08ebbac72232c98d96ea74c3c0410864a7ba','carrier_tree':'fe76cc863f551b834b29aa78b659f688d52b1fad','manifest_path':'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/ORCH03/parallel-20261008-admission/manifest.json','full_pair':admission['outputs'],'branch':'codex/e02-E-c07-20261008','path':str(root)},
 'transport':{'source_pushed_and_remote_readback':source,'source_tree':tree,'output_refs':[str(relative/'outputs/source-push.stderr'),str(relative/'outputs/source-remote-readback.stdout')],'handoff_is_separate_commit':True,'handoff_remote_readback':'To be read after receipt commit; this JSON does not name its own future SHA.'}
}
(out/'implementation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'candidate':source,'candidate_tree':tree,'path':str(relative/'implementation.json'),'bytes':(out/'implementation.json').stat().st_size,'outputs':len(files),'source_paths':len(paths),'receipt_sha256':hashlib.sha256((out/'implementation.json').read_bytes()).hexdigest()}))
