"""Independent source/card/owner reconciliation; scratch-only, no scientific reruns."""
from __future__ import annotations
import copy, csv, hashlib, io, json, pathlib, platform, subprocess, sys, time
from collections import Counter
REPO='/workspace/e02-F-cau-20261006'
CARRIER='072d45a56d1119fe3e7665cec2cbbdca015d2934'
PRODUCT='8236d9c368336a5ea20c1586f29aea7321db6536'
BASE='198076863e143dea9f89f02734b13d50dae3eed5'
G='9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7'
P='policy-engine/docs/research/e02-cloud-test-plan/'
PACK=P+'implementation-handoffs/F/continuation-transfer-20261006/'
OUT=pathlib.Path('/tmp/e02-F-continuation-20261007/cau')
CACHE={}
def git(*argv): return subprocess.check_output(['git',*argv],cwd=REPO)
def body(sha,path):
 key=(sha,path)
 if key not in CACHE: CACHE[key]=git('show',sha+':'+path)
 return CACHE[key]
def sha256(b): return hashlib.sha256(b).hexdigest()
def bref(sha,path):
 b=body(sha,path)
 return {'git_ref':sha,'path':path,'bytes':len(b),'sha256':sha256(b),'git_blob':git('rev-parse',sha+':'+path).decode().strip()}
def pointer(x,p):
 for part in p.strip('/').split('/'):
  part=part.replace('~1','/').replace('~0','~')
  x=x[int(part)] if isinstance(x,list) else x[part]
 return x
# This is the reviewer's interpretation of the FULL original blocks, not copied ROOT decisions.
SCOPE={
'B204':'Estimable standard pre/post contrast; zero-pre refusal, hand ATT3, numeric/control validation, not_testable/nonrejection/violation dispositions without identification authority.',
'B205':'Declared HC1 or unit-cluster CR0 covariance, independent Statsmodels algebra, row permutation, technical duplicates, unsupported-cluster refusal; small-G coverage is separate.',
'B206':'Requested confidence level for BOTH standard DiD and RDD: old95 compatibility, higher-level widening at positive SE, invalid-level refusal.',
'B207':'Unit-level resampling/ratio IF for the declared selected cohort-horizon estimand: nondegenerate one-cell variation, constant-model control, serial/multicohort calibration, unit/repeat identities.',
'B208':'Explicit centered H0 studentized null law; null calibration, real-effect power and same-test CI inversion including finite-B boundary decisions.',
'B209':'Controls outside the full anticipation exposure window and required baselines; g=t+a exclusion, never-treated/a=0 controls, fixed eligible horizons/no silent target drops.',
'B210':'Actual sharp-RDD bias correction and corrected variance in finite fixed h/b HC0 profile: curvature/jump/heteroskedastic cases, independent reference parity and coverage; usable uncorrected option retained.',
'B211':'Diagonal-free weighted polynomial design/score covariance with point/SE/ESS/kernel/order/refusal equivalence; no whole-estimator speedup claim.',
'B212':'Actual backend point without interval remains point-only/partial; real backend interval retained; unavailable optional backend is typed unrun, not manufactured CI.',
'B213':'Bind requested estimand_type/contrast/target to actual identify_effect/estimate_effect; supported default ATE unchanged, unsupported capability typed, no forced identification.',
'B214':'Known reverse arrow normalization plus preserved endpoint uncertainty; sound DAG extension/declared conditional completion or typed partial/refusal, no arbitrary PAG-to-DAG identification.',
'B215':'Partial factual affine-Gaussian posterior mean/covariance/singular support, full factual residual inversion, same posterior U across twin worlds; nonlinear unknown posterior remains limited.',
'B216':'Fully specified static ADMG separation against independent latent-DAG oracle, symmetry/rename/descendant conditioning and actual do/sigma/ID/IDC family callers.',
'B217':'Perfect-do cuts incoming directed AND incident bidirected edges while preserving outgoing/other latent effects; independent latent-DAG/multiple-action controls.',
'B218':'Lag1/lag2 and positive self-lag survive compact temporal representation/export/roundtrip; known static DAG unchanged, exact static incompatibility until temporal conversion; no universal temporal-ID requirement.',
'B219':'Actual native MultiDiGraph export retains every parallel edge identity/mark/lag/evidence/payload under order changes; no live Kuzu inference.',
'B220':'Deep immutable topology/nested data and detached prepared rows; warmed model_copy/update agrees with dump/ancestors/export, old-cache weakref release preserved.',
'B221':'Observed necessary root laws and dependent joint rows survive actual fit/source/CAS/query; unresolved roots distinguished from explicit exploratory natural-law assumptions.',
'B222':'Existing additive polynomial helper payload (no cross terms) consumed consistently by actual query/twin/abduction; LINEAR params-kept discriminator; no new default nonlinear fitter.',
'B223':'Explicit attribution target and comparator: do2−do0=6, same-arm0, observational and stochastic comparators, both query refs; independent draws versus shared-U ITE kept distinct.',
'B224':'Perfect surgery precedes natural evaluation; active-ancestor/factual/shared-noise pruning preserves logical RNG and full-trace option, shift still needs natural mechanism.',
'B225':'Supported stochastic Normal/Uniform/TruncNormal/atomic laws with stable tails/scales/support/degenerate cases and independent math.erfc oracle; unknown law refuses.',
'B54':'Issued nuisance core/input identity immutable; policy-only refresh reuses nuisance, actual data/seed/splits/fitter changes refit; explicit keys are not complete identity.',
'B56':'Actual shared study/fold workload obeys admitted common cap, waits without losing results and preserves fold/repeat/numeric/provenance with wall/RSS/active/wait measurements.',
'LA-001':'Equivalent randomization-plan relocation: seed0/nonzero, node permutation/repeat compilation and historical reader; compiler/executor inputs retain schema/content/digest.',
'LA-002':'Preserve four catalog family IDs/params/assumptions and IC-service lookup/unknown ID, actual registered runtime loading and existing IR certificates; family declarations are not new solver claims.',
'LA-003':'Equivalent baseline fiscal/labor relocation/spec registration, PatchMap/masks/budget/employer/key, compiler/replay and existing gradients; deliberate precision profile not new law.',
'LA-004':'Two distinct native/plugin economic models: state/unit/time/tax-base/RNG/budget mapping, matched regime equivalence and deliberately different regime non-equivalence, accounting and observable outputs.',
'LA-007':'Absent empty id_engine.py sibling while package/API remains: actual imports/find_spec, loader/sourceinventory bounded census, installed wheel/sdist and native ID tests.',
'LA-016':'Dedicated DiD metadata independent of deprecated umbrella, maintained FQN/flag/slots dedicated requests, retired default registry plus declared historical replay/warnings equivalence.',
'LA-017':'Actual unchanged/added/removed/modified norm diff, issue keys/pass config, persisted report IDs/refs and real downstream rendering; candidate tags never measured KPI. Equivalent relocation separate from current-law authority.',
'LA-019':'Only empty causal_engine.py/interference.py siblings absent; real packages/import/find_spec/public/loader/sourceinventory supported window, wheel/sdist/native package tests preserved.',
'LA-020':'Explicit actual export manifest preserving supported direct/star/private/FQN/pickle/pydoc/monkeypatch identities; incidental internal imports cannot expand API; no blanket underscore retirement.',
'LA-035':'Equivalent named GlobalState normalized-income/budget baseline relocation preserving ORIGINAL formula/sign/scale/size/min_balance/breach/NaNInf, native State/guardrail/JIT-grad promised paths, caller census and import side effects. New optimizer/welfare ratification is separate.',
'LA-037':'Actual IR slot/family builders, compiler/default registry/output, one intentional direct facade, identity/caller/docs/distribution support; no two-hop algorithm or new layout law.'}
# Named producer/artifact/bridge/consumer reviewed against the corresponding source and source-bound receipts.
CHAINS={
'CAU-01':['StandardDifferenceInDifferences.pure_step','CausalEffectReport + uncertainty_envelope','canonical method-output dematerializer/MethodJob CAS','fresh report reader and root diagnostic projection'],
'CAU-02':['StaggeredDifferenceInDifferences.pure_step','selected theta_sel/share IF/bootstrap law + CausalEffectReport','real MethodJob/CAS and canonical report projections','fresh native report reader; actual current diagnostic/target checks'],
'CAU-03':['RegressionDiscontinuity.pure_step','sharp RBC CausalEffectReport + uncertainty_envelope','MethodJob/CAS + canonical declared-slot dematerializer','fresh report reader'],
'CAU-04':['DoWhyIdentifyEstimate.pure_step / actual selected Python3.12 DoWhy0.14 worker','typed estimate/report, actual identified estimand','worker protocol → parent canonical report → CAS','fresh Python3.14 report reader'],
'CAU-05':['maintained G2 dedicated MethodCandidate + independent DiD metadata','native dedicated request and historical legacy inputs','actual MethodRegistry/dispatcher + declared old-route adapter','MethodJob/CAS/canonical output consumer'],
'GRF-01':['CausalGraphModel + canonical static ADMG operators','immutable explicit marks/lag/source graph snapshot','CachedAdjacency / graph surgery / do-sigma-ID-IDC callers','actual finite separation/identification callers'],
'GRF-02':['CausalGraphModel immutable topology/model_copy/export','detached row preparations and complete parallel edge records','native NetworkX3.6.1 / schema1.0 CAS','fresh graph reader, ancestors/export/cache readers'],
'GRF-03':['existing ReconcileCausalGraph owner and CausalGraphModel','current-request graph artifact with marks/lag/source lineage','typed graph ref/CAS verifier → static consumer boundary','actual reconciliation fresh reader/static GCM/ADMG consumers'],
'SCM-01':['actual source-bound GCM fit worker; existing _fit_additive_noise_poly for B222','fitted empirical/joint rows or typed manual polynomial SCM1.0','real MethodJob/CAS typed model ref','fresh-process GCMQuery/TwinNetworkQuery'],
'SCM-02':['GCMQuery/TwinNetworkQuery','typed conditional/contrast result + both query refs','canonical generated two-slot ABI / real CAS custody','fresh RunCausalQueriesNode canonical peer/result projection'],
'SCM-03':['GCMQuery intervention planner/sampler','typed stochastic outcome/query result','method output/CAS/ref reconciliation','fresh reader and declared static-law consumers'],
'FIT-01':['fit_crossfit_nuisance_bundle / TMLEEstimator','issued immutable nuisance core + actual result/report/envelope','native fitter/public factory → real MethodJob/CAS','fresh result/report reader; actual study common-budget route distinct'],
'FRY-01':['compile randomization/IR slot builders/catalog family owner','TreasuryPlan/SlotLayout/IR certificate refs','compile.api.compile → compile_trinity / ICVerificationRequest → CAS','execute.api.execute → execute_program_graph → adaptive_agent / fresh IR reader'],
'FRY-03':['registry-created baseline fiscal/labor methods','PatchMap + PRNG key and GlobalState','ParamDecimal/spec compiler/CAS/ExecutorGraph/apply_patch_map','actual balances/current metrics/fresh state reader'],
'ECO-01':['native baseline and separately EconomicsPlugin models; named economics.baselines loss','PatchMap/GlobalState versus EconomicState; native scalar normalized-income loss','apply_patch_map versus CompositeExecutor; canonical aliases/guardrail/JIT-grad','real finite model comparators and supported loss callers; Gini is separate'],
'API-01':['explicit causal_engine/interference facade owners','same identity public and supported historical export objects','declared exports/FQN/monkeypatch/pickle/loader/docs/install bindings','actual native algorithms/dispatcher/CAS/fresh isolated wheel+sdist readers'],
'LEX-01':['NormImpactAnalyzer actual LegalPass/NormDiff','lex.norm_diff + lex.norm_impact_report schema1.0','canonical analyzer → FileSystemCAS → CLI norm-impact rendering','fresh NormImpactReport/NormDiff reader and render_impact_markdown']}
SCOPE_SURFACE={}
for fid in SCOPE:
 if fid in ['B204','B205','B206','B207','B208','B209','B210','B211']:SCOPE_SURFACE[fid]='Declared Standard/Staggered DiD or RDD method parameters and typed CausalEffectReport/envelope consumer ABI'
 elif fid in ['B212','B213']:SCOPE_SURFACE[fid]='DoWhyIdentifyEstimate declared estimand parameters, selected worker protocol and typed report/CAS reader ABI'
 elif fid in ['B214','B218']:SCOPE_SURFACE[fid]='CausalGraphModel schema1.0 endpoint/lag representation; existing graph reconciliation, projection and static method consumer boundary'
 elif fid in ['B216','B217']:SCOPE_SURFACE[fid]='Canonical internal static ADMG separation/surgery operators and actual do/sigma/ID/IDC method callers'
 elif fid in ['B219','B220']:SCOPE_SURFACE[fid]='CausalGraphModel typed graph and internal immutable cache/export provider; actual NetworkX/CSV/CAS reader values'
 elif fid in ['B215','B221','B222','B223','B224','B225']:SCOPE_SURFACE[fid]='Declared SCM model/query/result DTOs, GCM/Twin method outputs and generated canonical CAS/fresh-reader consumer seam'
 elif fid in ['B54','B56']:SCOPE_SURFACE[fid]='TMLE issued nuisance/core and public result/report/envelope factory; shared actual Runtime study/fold resource consumer distinct'
 elif fid in ['LA-007','LA-019','LA-020']:SCOPE_SURFACE[fid]='Maintained causal_engine/interference/id_engine package direct/star/private historical exports, FQN/pickle/monkeypatch/loader and installed distribution ABI'
 elif fid=='LA-016':SCOPE_SURFACE[fid]='Dedicated DiD class metadata/FQN/flags/input slots, maintained MethodCandidate/registry and declared historical adapter window'
 elif fid=='LA-017':SCOPE_SURFACE[fid]='Lex canonical normpack.diff/legal_evaluation.impact_diff plus simulator compatibility aliases, persisted report/ref schema and actual CLI candidate-topic rendering'
 elif fid=='LA-035':SCOPE_SURFACE[fid]='Named internal economics.baselines GlobalState scalar profile with two existing callable aliases and public numeric guard; no new welfare surface'
 elif fid=='LA-004':SCOPE_SURFACE[fid]='Two explicitly different native PatchMap/GlobalState and registered plugin EconomicState model contracts'
 elif fid=='LA-003':SCOPE_SURFACE[fid]='Maintained mechanism registry/spec/FQN→baseline execute mechanisms→PatchMap/PRNG key/compiler/replay contracts'
 elif fid=='LA-001':SCOPE_SURFACE[fid]='Compiler randomization-plan builder/TreasuryPlan historical schema and actual execution RNG consumers'
 elif fid=='LA-002':SCOPE_SURFACE[fid]='Four family catalog descriptors, IC-service lookup/runtime method registration and canonical IR certificate calls'
 elif fid=='LA-037':SCOPE_SURFACE[fid]='Canonical IR slot-layout/family builders and supported direct Foundry facade, Trinity compiler/default registry/docs/install consumers'

REASONS={
'B207':'Published selected iid-unit ratio-IF/Mammen/native/MC and actual CAS reader meet original finite property. Missing whole Runtime institutional admission is a separate residual, not a condition of this original criterion.',
'B208':'Published centered studentized H0 and exact finite-B inversion/endpoint consumer controls meet original criterion; small-G/simultaneous/real-world coverage remains unclaimed.',
'B209':'Published g>t+a and baseline eligibility, never-treated/a0 and whole requested set refusal controls meet original criterion. Empirical length of anticipation is not established or required by the synthetic property.',
'B212':'Actual selected3.12 DoWhy0.14 worker preserves point-only versus genuine interval and persisted reader. Excluded3.14 optional backend is UNRUN and does not negate or stand in for that selected witness.',
'B213':'Actual estimand_type/contrast/target binding and typed unsupported routes are the original mechanism. Real observational validity/authority remains separate.',
'B214':'Reverse normalization and typed preserved/refused unresolved marks are measured. Original also discusses sound extension/declared conditional partial model, not blanket complete identification. Keep limited until the original owner supplies the precise supported partial/conditional route or explicit finite refusal capability criterion; protected authority is not the reason.',
'B218':'Published actual lag1/lag2/self-lag export/CAS/NX roundtrip and exact static refusal meet the original temporal consumer-boundary property. Universal temporal estimator/protected readiness is not original acceptance.',
'B223':'Original attribution contrast is primary: explicit target/baseline/query refs, same arm0 and do2−do0=6 plus observational/stochastic comparators. Interval/refit type semantics are an additional boundary, not the replacement criterion.',
'B56':'The original actual common-budget property has no admitted workload measurement. Four-study custom fixture and single configured MethodJob are bounded siblings; attempted LocalWorkerPool failed before0fits. Keep original limited/UNRUN, no fake admission.',
'LA-017':'Exact supported native norm-diff/issue/pass/report/topic downstream properties are measured by original+canonical relocation tests and24native/fresh-reader receipts. Neither arbitrary corpus/global retirement nor current-law authority is in original acceptance; if an actually supported caller is missing it must be named rather than replacing the criterion.',
'LA-035':'COMMON supersedes the added optimizer/intent hold. Existing published original formula/aliases/native/JIT-grad/guards/import/caller measurements support equivalent relocation. Fresh independent ECO193 review28+55native,32Fraction panels/64eagerJIT/2analyticgrad and preserved-identity normalization/PPO refusal removals plus9007-input source/config census PASS support original closed; no new welfare choice.',
'LA-004':'Original compares TWO distinct economic models/ABIs and forbids silently substituting richer plugin. Gini scalar correctness and C/PPO signed-population consumer are separate properties, not this original criterion.',
'LA-002':'Actual catalog lookup/registered runtime loading/certificate calls are required; implementing all optional family kernels or real-world IC is not.',
'LA-007':'Sibling was already absent at198; retained packaging/API tests prove current maintained property, not a new deletion in this slice.',
'LA-019':'Two empty siblings were already absent at198; no new deletion or universal dynamic client absence is claimed.',
'B222':'Actual helper payload→typed manualSCM→MethodJob/CAS→fresh query/twin polynomial witnesses satisfy the conditional original helper path, not a new default Hybrid/DoWhy nonlinear fitter.',
'B225':'Independent math.erfc/CDF oracle and actual extreme-tail sampler controls apply; product self-comparison is not the numerical oracle.',
'B220':'Canonical cache provider fragment is internal stable; an older public-surface label must not recategorize this internal contract.'}

def verify_rows(rows,owners):
 issues=[];ids=[x['finding_id'] for x in rows]
 if len(ids)!=35 or len(set(ids))!=35 or set(ids)!=set(owners): issues.append('original-ID-denominator')
 if sum(len(x['original_source_criterion_refs']) for x in rows)!=36: issues.append('36-bindings')
 if set(x['primary_bundle'] for x in rows)!=set(o['source_closure_owner'] for o in owners.values()): issues.append('17-bundles')
 for r in rows:
  fid=r['finding_id'];o=owners.get(fid)
  if not o or r['primary_tsv_owner']!=o or r['primary_bundle']!=o['source_closure_owner']:issues.append(fid+':owner')
  refs=r['original_source_criterion_refs']; unique=set()
  for c in refs:
   raw=body(c['source_sha'],c['source_path']);lines=raw.splitlines(keepends=True);lo,hi=c['lines'];b=b''.join(lines[lo-1:hi]);unique.add(c['sha256'])
   if c['criterion_id']!=fid or len(b)!=c['bytes'] or sha256(b)!=c['sha256'] or b.decode()!=c['complete_original_block'] or git('rev-parse',c['source_sha']+':'+c['source_path']).decode().strip()!=c['document_git_blob']:issues.append(fid+':original-bytes')
   if not b.decode().startswith(c['title']+'\n') or not c['title'].startswith('## '+fid+'. '): issues.append(fid+':heading')
  if len(unique)!=1 or (len(refs)!=2 if fid=='LA-016' else len(refs)!=1): issues.append(fid+':unique-card-binding')
  if git('rev-parse',r['implementation_sha']+'^{tree}').decode().strip()!=r['candidate_tree_sha']:issues.append(fid+':source-tree')
  for rr in r['ROOT_deciding_refs']:
   b=body(rr['git_ref'],rr['path'])
   if len(b)!=rr['bytes'] or sha256(b)!=rr['sha256'] or git('rev-parse',rr['git_ref']+':'+rr['path']).decode().strip()!=rr['git_blob']:issues.append(fid+':receipt-byte')
   if rr.get('json_pointer') and pointer(json.loads(b),rr['json_pointer'])!=rr['complete_deciding_entry']: issues.append(fid+':pointer-entry')
 return issues

def register_check(x,registry):
 key=x['receipt']['git_ref']+':'+x['receipt']['path']+'#'+x['pointer']
 registry[key]={k:v for k,v in x.items() if k in ['receipt','pointer','raw_outcome','target_sha','expected_negative','input_closure','counts']}
 # Complete stdout/decoding/body remain in the exact byte-verified receipt,
 # reached by this JSON pointer; no duplicate source-derived output copy.
 return key

def local_review_ref(path):
 b=path.read_bytes();return {'path':str(path),'bytes':len(b),'sha256':sha256(b),'material_role':'complete independent frozen-source review; source-bearing receipts published by original authors separately'}

def main():
 t=time.monotonic();a=json.loads(body(CARRIER,PACK+'full-audit.json'));index=json.loads(body(CARRIER,PACK+'index.json'))
 ownerraw=body(BASE,P+'execution-organization/finding-owners.tsv');allowners=list(csv.DictReader(io.StringIO(ownerraw.decode()),delimiter='\t'));owners={x['finding_id']:x for x in allowners if x['unit']=='F'}
 bundlesraw=body(BASE,P+'execution-organization/bundle-owners.tsv');allbundles=list(csv.DictReader(io.StringIO(bundlesraw.decode()),delimiter='\t'));bundles=[x for x in allbundles if x['unit']=='F']
 rows=a['rows'];assert len(allowners)==282 and len(allbundles)==127 and len(bundles)==17
 issues=verify_rows(rows,owners)
 negatives=[]
 for label,mutate in [('missing-ID',lambda v:v.pop()),('wrong-owner',lambda v:v[0]['primary_tsv_owner'].update(source_closure_owner='CAU-03')),('wrong-card-title',lambda v:v[0]['original_source_criterion_refs'][0].update(title='## B204. wrong title')),('stale-receipt-hash',lambda v:v[0]['ROOT_deciding_refs'][0].update(sha256='0'*64)),('wrong-code-tree',lambda v:v[0].update(candidate_tree_sha='0'*40)),('LA016-extra-ID',lambda v:v.append(copy.deepcopy(next(x for x in v if x['finding_id']=='LA-016'))))]:
  changed=copy.deepcopy(rows);mutate(changed);bad=verify_rows(changed,owners);negatives.append({'control':label,'validator_outcome':'FAIL' if bad else 'PASS','issues':bad,'harness_check':'PASS' if bad else 'FAIL'})
 result=[];refset={};check_registry={}
 for r in rows:
  fid=r['finding_id'];original=r['original_source_criterion_refs'][0];proposed='limited' if fid in ['B214','B56'] else 'closed'
  sourcecheck='UNRUN' if fid=='B56' else 'PASS'
  deciding=[];receipt_checks=[]
  for rr in r['ROOT_deciding_refs']:
   x={k:v for k,v in rr.items() if k!='complete_deciding_entry'};deciding.append(x);refset[(x['git_ref'],x['path'])]=x
   obj=json.loads(body(x['git_ref'],x['path']))
   for n,c in enumerate(obj.get('checks',[])):
    receipt_checks.append({'receipt':{'git_ref':x['git_ref'],'path':x['path']},'pointer':'/checks/'+str(n),'raw_outcome':c.get('outcome',c.get('check','UNRUN')),'target_sha':c.get('target_sha'),'expected_negative':c.get('expected_negative',c.get('expected_outcome')=='FAIL'),'input_closure':c.get('input_closure'),'output':c.get('output'),'output_ref':c.get('output_ref'),'stdout_ref':c.get('stdout_ref'),'stderr_ref':c.get('stderr_ref'),'counts':c.get('counts')})
  # All full row records are read; a per-ID carrier may additionally bind its complete source-derived row.
  perid=bref(CARRIER,PACK+'per-ID/'+fid+'.json');json.loads(body(CARRIER,perid['path']))
  refs=[{k:v for k,v in c.items() if k!='complete_original_block'} for c in r['original_source_criterion_refs']]
  result.append({'finding_id':fid,'primary_owner_from_full_TSV':owners[fid],'bundle_owner_from_full_TSV':next(x for x in bundles if x['bundle_id']==r['primary_bundle']),'original_card_refs':refs,'original_text':original['complete_original_block'],'primary_acceptance_scope':SCOPE[fid],'source_chain':dict(zip(['producer','artifact','bridge','consumer'],(['StandardDifferenceInDifferences AND RegressionDiscontinuity.pure_step','both actual requested-level CausalEffectReports/envelopes','their real MethodJobs/CAS and canonical declared-slot dematerialization','both native/fresh report readers'] if fid=='B206' else ['Registry-created native fiscal/labor AND EconomicsPlugin.get_mechanisms','PatchMap/GlobalState versus separate EconomicState with observable budget/employer/RNG state','apply_patch_map/native registry/compiler versus CompositeExecutor','actual matched-law and deliberately-divergent-regime accounting/seed/output consumers'] if fid=='LA-004' else ['economics.baselines.normalized_income_budget_loss','native GlobalState scalar normalized-income/budget loss','exact methods.loss and methods._internal.loss aliases + real public finite_loss_or_inf','native caller tests/eager/JIT/grad/fresh-import witness'] if fid=='LA-035' else CHAINS[r['primary_bundle']]))),'actual_recorded_consumer':('named economics.baselines.normalized_income_budget_loss → exact public/internal policy_loss_fn aliases → native GlobalState/real finite_loss_or_inf → eager/JIT/grad and supported native caller tests; actual C/G9a ActorCritic→labor/tax producer reaches F canonical current metrics/PPO Gini refusal as a separate property' if fid=='LA-035' else r['actual_consumer']),'surface':SCOPE_SURFACE[fid],'deciding_receipt_refs':deciding,'deciding_per_ID_carrier_ref':perid,'scientific_implementation':{'sha':r['implementation_sha'],'tree':r['candidate_tree_sha'],'not_receipt_carrier':True},'recorded_independent_oracle_and_negative':('Fresh193 native28+55;32independent Fraction panels64eager/JIT and2analytic gradients PASS; exact same public/internal callable with normalization removed FAIL, actual canonical Gini admission body removed2real bridge/PPO assertionFAIL. Full9007-file source/config/FQN literal byte census and10matchingfiles independently verified; old historical formula/native guard/aliases retained. No optimizer/welfare prerequisite.' if fid=='LA-035' else 'Explicit target/baseline/query-ref attribution controls: do2−do0=6, samearm0, observational and stochastic comparator; sharedU ITE distinct from independent outcome draws. OptionalIID-refit CI is a separate interval type boundary, not the original attribution property.' if fid=='B223' else r['oracle_and_negative']),'complete_raw_receipt_checks_refs':[register_check(x,check_registry) for x in list({json.dumps(x,sort_keys=True):x for x in receipt_checks}.values())],'historical_ROOT072':{k:r.get(k) for k in ['check','outcome','technical_original_criterion_recommendation','current_continuation_outcome_recommendation','original_criterion_remainder','actual_consumer','oracle_and_negative','separate_unavailable_inputs_or_authority']},'independent_original_criterion_recommendation':{'check':sourcecheck,'outcome':proposed,'basis':REASONS.get(fid,'Verified original block/TSV/source-tree/receipt bytes and pointers support the recorded bounded native discriminator; extra universal production authority is not substituted for this finite property.'),'scientific_rerun':fid=='LA-035','review_scope':'independent criterion/evidence reconciliation; not an independently rerun estimator measurement','missing_actual_original_criterion':('Actual admitted common-budget study/fold measurement remains UNRUN.' if fid=='B56' else 'Supported sound extension/declared conditional partial-model route and exact finite capability discrimination need owner clarification; no protected-authority prerequisite.' if fid=='B214' else None),'new_owner_review_pending':False,'not_formal_G_closure':True},'separate_unavailable_inputs_or_authority':('Uncommissioned new optimizer/welfare convention and actual production economic authority remain separate; not conditions of equivalent original relocation. Unknown dynamic external callers are not proven absent; supported literal/native callers are verified.' if fid=='LA-035' else r['separate_unavailable_inputs_or_authority']),'existing_author_or_reviewer_conflict':'Reviewer previously authored CAU and graph-intake provider; current independent role is ROOT original-criterion reconciliation. Prior scientific validation uses source-bound independent economics/graph/API receipts, not self-claimed fresh independent math.' if r['primary_bundle'].startswith('CAU') or fid in ['B214','B218'] else None})
 counts=Counter(x['independent_original_criterion_recommendation']['outcome'] for x in result);checks=Counter(x['independent_original_criterion_recommendation']['check'] for x in result)
 common=bref(G,P+'execution-prompts/continuation-2026-10-07/COMMON.md')
 packet={'schema':'F-original35-independent-criterion-review/2026-10-07','role':'Noncanonical source-bound owner recommendation; ROOT sole ledger writer, G sole formal closure publisher','reviewer':'/root/cau','environment':{'python':platform.python_version(),'executable':sys.executable,'purpose':'stdlib Git-byte/card/owner/pointer review, not product backend'},'source':{'common':common,'ROOT072_audit':bref(CARRIER,PACK+'full-audit.json'),'ROOT072_index':bref(CARRIER,PACK+'index.json'),'ROOT072_report':bref(CARRIER,PACK+'REPORT.md'),'product_sha':PRODUCT,'product_tree':git('rev-parse',PRODUCT+'^{tree}').decode().strip(),'owner_TSV':bref(BASE,P+'execution-organization/finding-owners.tsv'),'bundle_TSV':bref(BASE,P+'execution-organization/bundle-owners.tsv'),'own_admitted_head':git('rev-parse','HEAD').decode().strip()},'denominator':{'all_TSV_findings':len(allowners),'all_TSV_bundles':len(allbundles),'F_IDs':len(rows),'F_bundles':len(bundles),'original_bindings':36,'unique_original_blocks':35,'LA016_ID_count':1,'LA016_bindings':2},'mechanical_evidence_check':'PASS' if not issues else 'FAIL','mechanical_issues':issues,'meaningful_metadata_negative_controls':negatives,'original_recommendation_counts':dict(counts),'original_check_counts':dict(checks),'recommendation_is_not_G_accepted':True,'historical_F_counts_not_G_closure':index['summary'],'deciding_unique_receipts':len(refset),'raw_receipt_check_registry':list(check_registry.values()),'raw_errors_failures_skips_unrun_preserved_by_full_check_refs':True,'optional_backend_limit':'Baseline Python3.14 excludes DoWhy/EconML markers. Absence is UNRUN, never positive backend witness; distinct selected real3.12 DoWhy0.14 receipts remain their exact finite evidence.','custody':{k:index.get(k) for k in ['current_deciding_reference_check','all_reference_custody_check','historical_non_deciding_reference_check','historical_non_deciding_custody','non_deciding_textual_assertions_without_raw_output','zero_finding_deciding_dependence_on_missing_historical175c_and_lint_raw']},'P41':'not_established; exact base replay alone is not complete disjoint input denominator proof','new_DiD160_or_RDD4000_coverage_wave':False,'fresh_finite_owner_verification':{'ECO193':'28+55native,32Fraction/64eagerJIT/2analyticgrad and2actualPPO admission negatives','API6f39':'two real isolated-wheel graph consumers plus2row-isolation property-removal negatives'},'fresh_independent_review_refs':{'economics193':local_review_ref(OUT/'economics-review/independent-review.json'),'API6f39':local_review_ref(OUT/'api-review/independent-review.json')},'rows':result,'wall_s':time.monotonic()-t}
 f=OUT/'original35-independent-review-final.json';f.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'check':packet['mechanical_evidence_check'],'issues':issues,'denominator':packet['denominator'],'original_recommendation_counts':dict(counts),'original_check_counts':dict(checks),'negative_controls':negatives,'packet':{'path':str(f),'bytes':f.stat().st_size,'sha256':sha256(f.read_bytes())},'wall_s':packet['wall_s']}))
 return 1 if issues or any(n['harness_check']!='PASS' for n in negatives) else 0
if __name__=='__main__':raise SystemExit(main())
