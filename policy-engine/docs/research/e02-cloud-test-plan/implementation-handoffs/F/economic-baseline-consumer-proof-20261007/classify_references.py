from pathlib import Path
import subprocess,json,re,hashlib,collections
root=Path('/workspace/e02-F-economics-20261006');scratch=Path('/tmp/e02-F-continuation-20261007/economics');base=json.loads((scratch/'dependent-reference-locators.json').read_text());sha='c0084cd530c1dbe01eedfb9b5c24f055954a97be';rows=[]
for row in base['locators']:
 if row['role']!='root_current_caption_candidate':continue
 p=row['path'];b=subprocess.check_output(['git','show',sha+':'+p],cwd=root);lines=b.decode().splitlines();matches=[{'line':i,'text':s} for i,s in enumerate(lines,1) if re.search(r'LA-?0(?:04|35)',s)]
 if p.endswith(('/closure-decisions/F.md','/closure-decisions/method-decisions.md','/closure-decisions/runtime-profiles.md')):
  role='mandatory_current_ROOT_operating_view';action='ROOT forward-correct LA035 held-optimizer/norm prerequisite to original equivalent-relocation technicalclosed, preserving dated history; LA004 remains distinctmodelsclosed. Link new recommendation/receipt and separate Gacceptance.'
 elif p.endswith('/reference/foundry/economic-baseline-profile.md'):
  role='owned_current_profile_corrected';action='Already corrected explicitly in doc-onlyc008, independentlyreviewed; originaltechnicalclosed, dated072heldliteral, newobjective/version onlyfuturefollowup. No further mutation needed.'
 elif p.endswith('/closure-decisions/coverage.json'):
  role='immutable_G97_planned_criterion_baseline';action='Preserve runtime_source97 and criterion_specific_acceptance_not_executed baseline/36binding identity. Add/link currentseparateclosure record only if ROOT needsnavigation; do not overwrite historical scope/state as present acceptance.'
 elif p.endswith('/bundle-catalog.md'):
  role='historical_research697_test_navigation';action='Headerpins69780761 and explicitly establishes noexecution/semanticadequacy. Preserve reported narrowmapping/gaps; optionally add currentrecord link, never rewrite selectedtestscope into fresh83 or closure.'
 elif '/execution-organization/' in p:
  role='immutable_allocation_source_owner_mapping';action='Preserve TSV source_statuspartial and ECO01allocation/originalIDs. Currenttechnicaloutcome belongsnewROOTledger, not allocation rewrite.'
 elif '/PolicyOS_E02_Combined_Agent_Package/' in p:
  role='immutable_original_requirement_or_queue_mapping';action='Preserve cards/queue/crosswalk/bundlemanifest/template and fullsourcebinding. These assign owner/originalcriteria, not currenttechnicaloutcomes. No correction/newGiniID needed.'
 elif '/PolicyOS_E02R2/' in p:
  role='historical_E02R2_dated_source_decision_snapshot';action='Retain original2026-10-02/earlier residual/principaldecision/sourceprobe bytes. Oldoptimizerretirement premise is not controlling originalLA035 underCOMMON9a; newROOTcurrentrecord supersedes it for unchangedrelocation. If futureR2maintainer consumescurrentstate, provide explicit source-qualified currentlink via owner, not F blanketrewrite.'
 elif '/2026-09-30-post-e02/' in p:
  role='other_program_derived_historical_source_view';action='Preserve reported source/date/selector provenance; source-disposition/decisionrow may be consumed by laterprogramowner. Provide neworiginalcriterion/source-qualified currentlink to thatowner if reused; not authorized F current35 rewrite.'
 elif '/execution-prompts/continuation-2026-10-06/' in p:
  role='historical_executed_instruction_checkpoint';action='Preserve executedOct6prompt literally. COMMON9aOct7 controls newtask and supersedes optimizer/norm prerequisite; futureprompt maylinknewdecision but doesnot retrospectivelyalter instructions.'
 elif p.endswith('/closure-decisions/execution-sequence.md'):
  role='current_ROOT_routing_view_already_criterion_coherent';action='ExactECOIDs/lanes and distinctprofiles are correct; no obsoleteLA035hold stated onmatchinglines. No mandatory prose correction; optionalnewrecordnavigation only.'
 elif '/integration/' in p:
  role='immutable_dated_G_acceptance_or_audit';action='Preserve exactOct5/6source/candidate/acceptedhead/reviewer/outcome snapshot. Earlier held caption is historical; freshROOTrecommendation/Gfutureadoption is a separate record. No retrospectivecurrentclosure rewrite.'
 else:raise AssertionError(p)
 rows.append({'git_ref':sha,'path':p,'git_blob':subprocess.check_output(['git','rev-parse',sha+':'+p],cwd=root,text=True).strip(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'source_role':role,'current_action':action,'matches':matches})
assert len(rows)==31
out={'schema':'policyos.e02.caption_reference_role_review.v1','unit':'F','source_sha':sha,'source_tree':'9bbaa69dc195dd38adb04c9d52fc4cd700824bc7','denominator':31,'rows':rows,'role_counts':dict(collections.Counter(r['source_role'] for r in rows)),'additional_mandatory_current_not_in_baseline31':['ROOT newcurrent35ledger/index/REPORT/per-ID/full-audit (new20261007carrier); cite original LA004distinctmodelsclosed and LA035equivalentrelocationclosed with separateGacceptance. Old frozen handoff/index bodies remain immutablehistorical.'],'current_adjudication_ref':'original-criterion-adjudication.json','no_edits_to_other_owners':True}
(scratch/'current-caption-role-classification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'bytes':(scratch/'current-caption-role-classification.json').stat().st_size,'roles':out['role_counts']}))
