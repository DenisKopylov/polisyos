"""Prepare reviewer proposals from immutable original cards, not PR captions."""
import collections
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess

REPO = '/workspace/e02-F-cau-20261006'
BASE = '198076863e143dea9f89f02734b13d50dae3eed5'
OLD_LEDGER = 'd8334672f44d24dd32113264f96ca3f7954dace4'
G = '855cb26a7a2c9fea60356663cf81e7d01e20c738'
OWN = '4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9'
P = 'policy-engine/docs/research/e02-cloud-test-plan/'
PACK = P+'implementation-handoffs/F/continuation-transfer-20261007/'
OWN_PACKET = P+'implementation-handoffs/F/original35-independent-criterion-review-20261007/original35-review.json.gz'
OUT = Path(__file__).resolve().parent

RATIONAL = {
 'B204':'Standard DiD requires estimable pre/post and compared regimes, recovers hand ATT3, and distinguishes invalid/not_testable/nonrejection/violation. Pretrend nonsignificance is not identification or real parallel-trends proof.',
 'B205':'Actual selected HC1 and unit-cluster CR0 covariance agree with independent Statsmodels, preserve ATT, row permutation and technical period duplication; unsupported covariance/cluster variable refuses. No universal small-cluster coverage claim.',
 'B206':'Both Standard DiD and RDD honor actual confidence level, preserve95 compatibility, widen at positive SE and refuse invalid levels. Separate cebe DiD/fb RBC source receipts remain; interval-level fix does not itself prove covariance/RBC.',
 'B207':'Unit-level shared Mammen draws act coherently on ATT cells; selected scalar target includes estimated-share ratio IF and fixed eligible horizons. One-cell variable-unit uncertainty and independent serial/multicohort DGP coverage are measured on exact historical sources; no real-data inference.',
 'B208':'Centered studentized null statistic and matching CI inversion use the same unit influence law, with exact discrete-tail/endpoint decision correction; retained source-bound null/power/coverage/removal results suffice for the finite original profile.',
 'B209':'Admissible not-yet controls require timing beyond t+anticipation and valid baselines; boundary/never-treated/a=0 controls and no silent cohort/horizon drop preserve requested aggregate scope. Additional diagnostic basis time_treatment binding remains separate from theta target.',
 'B210':'Real local-polynomial RBC executes curvature correction and appropriate variance on declared finiteHC0 profile; external locked rdrobust parity, heteroskedastic coverage and property-removal evidence are exact fb sources. No unsupported backend/selector or production law claim.',
 'B211':'Vector/weighted-QR local polynomial preserves point/SE/effective support across declared kernel/order without N-by-N weight matrix; insufficient support typed refusal. Performance property remains distinct from RBC calibration.',
 'B212':'Genuine selected3.12 DoWhy worker preserves useful point-only partial result without invented CI and preserves actual backend interval through report/CAS/freshreader. Baseline3.14 excludedbackend remains UNRUN, not a witness or new production-authority prerequisite.',
 'B213':'Requested estimand_type/contrast/target is bound to actual identify/estimate arguments and result; default ATE remains and unsupported types refuse. Actual dispatcher/backend/CAS binding is the finite criterion, not unprovided observational identification authority.',
 'B214':'Known reverse direction and marks are preserved; uncertainty/static-temporal routes are typed limited/refused and DAG/latent positive paths measured. Original additionally requires supported partial/conditional models or sound extension; universal refusal alone does not close this part.',
 'B215':'Partial factual linear-Gaussian abduction matches independent conditional mean/covariance including singular cases; fully observed invertible residual and shared posteriorU worlds preserved in native CAS consumers. General nonlinear posterior and real SCM validity stay outside declared profile.',
 'B216':'Correct staticADMG separation matches full200-by12 independent latent-DAG oracle plus symmetry/rename/descendant controls and actual do/sigma/ID/IDC family consumers. PAG/temporal unidentified semantics not silently promoted.',
 'B217':'Perfect surgery removes directed/bidirected incoming arrowhead influence while preserving outgoing effects and other latent causes; actual multiple-action/static latent-DAG controls discriminate from conditioning/fixing.',
 'B218':'Compact lag1/lag2 and lagged self-dependence retain time in validated roundtrip/export; zero-lag cycles refuse and static consumers refuse unresolved temporal conversion. Original allows exact static incompatibility; no new universal temporal-identification engine required.',
 'B219':'Declared mixed/parallel/lag relationship identity survives actual backend export/roundtrip and edge permutation. MultiDiGraph storage is not proof arbitrary directed algorithms interpret causal marks; actual supported backend window remains bounded.',
 'B220':'Deep immutable topology/nested metadata, warmed copy/update cache invalidation, detached prepared rows and oldweakref release are measured together; actual dump/ancestor/export agree. Internal stable cache contract is not recategorized as publicstable.',
 'B221':'Observed root law/source rows are fitted/persisted and actually consumed by GCM query with required joint dependence; no invented N(0,1) substituted for data. Missing/default root assumptions stay explicit scoped limitations.',
 'B222':'Existing additive polynomial helper payload without cross terms is executed consistently by typedmanualSCM→realMethodJob/CAS→query/twin/abduction; polynomial/LINEAR retained-fields discriminators pass. Original is conditional payload reachability, not new default nonlinear fitter or unrestricted posterior.',
 'B223':'Explicit target and baseline/query refs produce do2-do0=6 and same-arm0, observational/stochastic comparators; independent outcome draws versus sharedU ITE remain distinct. Optional IID-refit intervals are an additional boundary, not replacement criterion.',
 'B224':'Perfectdo bypasses replaced natural mechanism and active query plan omits irrelevant nodes while preserving needed factual/latent ancestors and shift semantics. Actual source/query cache binding and RNG rules are explicit; no claimed global speedup.',
 'B225':'Declared supported stochastic law preserves scale/support/tails/degenerate semantics with independent math.erfc/tail oracle and native consumers; unknown law refuses rather than silently atomic fallback. Clip policy and conditionaltruncnorm remain distinct.',
 'B54':'Immutable reusable fit core preserves source/split/seed identity; current diagnostic policy rebinds without refit and detached readers cannot poison hits. Real TMLE report/CAS consumers and neighbor causal-blocker preservation are bounded evidence, not statistical authority.',
 'B56':'Actual admitted shared study workload/resource composition is not measured. Historical custom4study/24fold and configured/default native15fold singles are useful siblings, while attempted pool failed before0fits. Need actual admitted workload/cap/wait/results/wall/RSS denominator.',
 'LA-001':'Equivalent randomization-plan relocation preserves seed0/nonzero, node IDs/order, repeat compilation and historical serialized plan/actual compiler-executor callers. No new temporalRNG law or digest change required.',
 'LA-002':'Four family IDs/params/assumptions and IC lookup/unknown behavior, actual registered runtime loading and existing IR certificates are preserved. Catalog declaration alone not IC proof; four new optional solver implementations are not original acceptance.',
 'LA-003':'Named baseline fiscal/labor profile preserves registry/spec/PatchMap masks/balance/employer/key, compiler/CAS/replay and gradients with declared minfloat compatibility. Separate ABM diagnosticFAIL and P41notestablished stay visible; no model law change hidden as relocation.',
 'LA-004':'Original compares two distinct PatchMap/GlobalState and plugin/EconomicState fiscal/labor models with state/unit/time/tax-base/RNG/budget mapping, matched law equality and deliberate divergence. Gini/welfare/signed C-PPO route is separate, not replacement acceptance.',
 'LA-007':'Only exact empty id_engine.py sibling is absent alreadyat198; real package/publicimports/find_spec/filename-loader/source inventory and installed distribution/native ID consumers retained. No new deletion or universal external-loader absence asserted.',
 'LA-016':'Independent dedicated metadata/helpers and maintained FQN/flag/slot request route replace deprecated default registry; declared historical adapter/old-slot replay preserves effective result/warnings. Two original bindings remain one ID; numerical estimators separately proven.',
 'LA-017':'All unchanged/added/removed/modified norm diffs, issuekeys/passconfiguration, report IDs/refs/persistence and actual CLI downstream readers measured; candidate topics not magnitudes. Dedupealone insufficient; equivalent relocation needs no production current-law corpus or Gclosure.',
 'LA-019':'Only two empty causal_engine.py/interference.py siblings are absent alreadyat198; actual packages/export/filename loader supportedwindow plus installed native consumers preserved. No global/external computed-loader zero claimed.',
 'LA-020':'Explicit public/historical-supported surface preserves import/star/FQN/pickle/monkeypatch/docs/distribution identity and incidental-import isolation. Actual finite manifest/window and unresolved computed/external clients explicit; reflectionabsence alone not ABI.',
 'LA-035':'Unchanged named GlobalState normalized-income/budget baseline preserves original formula/sign/scales/population/minbalance/breach/nonfinite, aliases/native guard/eager-JIT-grad/import/caller paths. Fraction32panels-by2=64 comparisons and83native are distinct from Gini. No new optimizer/welfare/norm packet prerequisite;9007 tracked literal census leaves constructed/external/untracked/production use unknown.',
 'LA-037':'Canonical IR slots/family builders and actual compiler/defaultregistry/PatchOp/state/CAS/docs/distribution preserve IDs/identity; one deliberate direct Foundry facade supports historical paths, not two hops/new layout algorithm.',
}

def git(*args): return subprocess.check_output(['git',*args],cwd=REPO,stderr=subprocess.PIPE)
def sha(b): return hashlib.sha256(b).hexdigest()
def raw(ref,path): return git('show',ref+':'+path)
def bind(ref,path):
    b=raw(ref,path)
    return dict(git_ref=ref,path=path,bytes=len(b),sha256=sha(b),git_blob=git('rev-parse',ref+':'+path).decode().strip())

packet_raw=gzip.decompress(raw(OWN,OWN_PACKET));packet=json.loads(packet_raw)
assert len(packet_raw)==998227 and sha(packet_raw)=='67607c87d420030944247874fdc6ac6962f6201fc982f534257529b89fa820b6'
owners=list(csv.DictReader(io.StringIO(raw(BASE,P+'execution-organization/finding-owners.tsv').decode()),delimiter='\t'))
bundles=list(csv.DictReader(io.StringIO(raw(BASE,P+'execution-organization/bundle-owners.tsv').decode()),delimiter='\t'))
F_owners={r['finding_id']:r for r in owners if r['unit']=='F'}
F_bundles={r['bundle_id']:r for r in bundles if r['unit']=='F'}
assert len(owners)==282 and len(bundles)==127 and len(F_owners)==35 and len(F_bundles)==17 and set(RATIONAL)==set(F_owners)
coverage=json.loads(raw(G,P+'closure-decisions/coverage.json'))
assert coverage['denominator']['bundles']==127 and coverage['denominator']['findings']==282
index=json.loads(raw(OLD_LEDGER,PACK+'index.json'))
expected=[]
for source_row in packet['rows']:
    fid=source_row['finding_id'];owner=F_owners[fid]
    row=json.loads(raw(OLD_LEDGER,PACK+'per-ID/'+fid+'.json'))
    assert source_row['primary_owner_from_full_TSV']==owner==row['primary_owner_from_full_TSV']
    assert source_row['original_card_refs']==row['original_card_refs']
    assert source_row['original_text']==row['original_text']
    for original in row['original_card_refs']:
        b=raw(original['source_sha'],original['source_path']);lo,hi=original['lines'];block=b''.join(b.splitlines(keepends=True)[lo-1:hi])
        assert len(block)==original['bytes'] and sha(block)==original['sha256'] and block.decode()==row['original_text']
        assert original['criterion_id']==fid
    outcome='limited' if fid in {'B214','B56'} else 'closed'
    check='UNRUN' if fid=='B56' else 'PASS'
    assert row['F_finding_outcome']==outcome and row['check_result']==check
    assert git('rev-parse',row['scientific_implementation']['sha']+'^{tree}').decode().strip()==row['scientific_implementation']['tree']
    expected.append(dict(finding_id=fid,primary_bundle=owner['source_closure_owner'],original_binding_count=len(row['original_card_refs']),original_card_refs_pointer='/original_card_refs',original_norm_text_ref=bind(OLD_LEDGER,PACK+'per-ID/'+fid+'.json'),expected_original_check=check,proposed_F_original_recommendation=outcome,proposed_original_technical_lens=outcome,expected_rationale=RATIONAL[fid],missing_original_criterion=row['original_missing_input'],next_original_owner=row['original_next_owner'],scientific_implementation=row['scientific_implementation'],prior_deciding_receipts_pointer='/deciding_receipt_refs',existing_author_or_reviewer_conflict_pointer='/existing_author_or_reviewer_conflict',formal_G_closure='not_issued'))
assert sum(r['original_binding_count'] for r in expected)==36
review=dict(schema='e02.F.original35-recovery-expected-criteria.v1',status='reviewer_proposal_waiting_ROOT_immutable_final_ledger',not_ROOT_or_G_decision=True,source=dict(original_base=BASE,own_packet=bind(OWN,OWN_PACKET),own_packet_decoded_bytes=len(packet_raw),own_packet_decoded_sha256=sha(packet_raw),prior_reviewed_ledger=OLD_LEDGER,fresh_G_checkpoint=dict(sha=G,tree=git('rev-parse',G+'^{tree}').decode().strip()),coverage=bind(G,P+'closure-decisions/coverage.json')),denominator=dict(IDs=35,bundles=17,original_bindings=36,full_source_TSVs=dict(finding_rows=282,bundle_rows=127)),independent_proposed_counts=dict(original_check=dict(collections.Counter(r['expected_original_check'] for r in expected)),F_original_recommendation=dict(collections.Counter(r['proposed_F_original_recommendation'] for r in expected)),original_technical_lens=dict(collections.Counter(r['proposed_original_technical_lens'] for r in expected)),formal_G_closures=0),rows=expected,dependent_caption_constraints=['HistoricalROOT072 current25/9/1 technical30/4/1 checks33/2 remain at their source, not relabeled519. New original35/36 recomputed from rows, not PR prose.','Both new F original recommendation and technical-original lens33closed/2limited; checks34PASS/1UNRUN. B218 temporal roundtrip/staticincompatibility and LA017 actualnormdiff/pass/readers satisfy original bounded criteria, not expanded authority conditions.','LA035 unchanged relocation requires no optimizer/normpacket;9007 literal tracked source/config inputs do not prove constructed/external/untracked callers or productionuse. Score/ranking/sign/scale ornew welfare change would require versioned accountable owner.','LA004 distinctmodelsnotGini; Gini prior244exact532/e157 arithmeticpositive fragment through8236 isnotwholeblob/wave reuse; fa53 signedsyntheticC-PPO refusal separate;64Fractioncomparisons are LA035.','B214 originalsupportedpartial/conditional route remains limited; B56 actualadmittedsharedpool workload remains limitedUNRUN. Missinginstitutional/value/law/realdata followups not inserted as unrequested originalcriterion prerequisites.','Fouraxes: original check; F recommendation; original technical lens; G formalacceptance/codeacceptance. Currentassembledinstalled readiness and genuine authority are separate explicit fields, not rolled into34 originalPASS.','Failedb5 each130PASS32FAIL preserved; recovered519 exactwave may be claimed only from published fullbytes/source/archives/sites/environment/controls, not old8236 or PR summary.','Scanner-9 isERROR/incomplete until actualretry; currentglobalqualityred/P41notestablished andhistorical175c4nondecidingcustodyUNRUN retained.','Baseline3.14 DoWhy/EconML markers excluded: UNRUN/absent notpositive witness. Selectedreal3.12 worker receipts stay own exactbackend/sourcepin.'],negative_guard_plan=['droporiginalbinding','wrongoriginalhash','wrongTSVowner','duplicateoromittedID','retargetscientificsource/tree toreceiptcarrier','claimGclosedfromFrecommendation','turn9007literalcensus intoexternalzero','reintroduceLA035optimizerprerequisite','retag07225/9/1as519','roll34originalPASSintoassembledwholePASS'],method_execution='No unchanged estimator/native/1659-material rerun. Full original text was read and all36 actual card block bytes compared to their Git source; only finite row/tree/card/owner metadata computed.',replayer=dict(path=__file__,bytes=Path(__file__).stat().st_size,sha256=sha(Path(__file__).read_bytes())))
path=OUT/'expected-original35-compact.json';path.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(check='PASS',output=dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path.read_bytes())),denominator=review['denominator'],proposed_counts=review['independent_proposed_counts']),indent=2))
