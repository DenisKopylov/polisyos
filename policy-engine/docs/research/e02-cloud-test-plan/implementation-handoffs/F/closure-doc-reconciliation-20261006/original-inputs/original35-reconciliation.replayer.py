#!/usr/bin/env python3
"""Read immutable source/card/receipt objects; propose criterion rows, never edit ledger."""
from __future__ import annotations
import ast
import csv
import hashlib
import io
import json
import pathlib
import subprocess
from collections import Counter

REPO = '/workspace/e02-F-cau-20261006'
PREFIX = pathlib.Path('/tmp/e02-F-continuation-20261006/cau/original35-reconciliation')
BASE = '198076863e143dea9f89f02734b13d50dae3eed5'
TRANSFER = '421f1dd977b237307394c68820caab4156716eb2'
G = '363e7ae0cb2929a92d9667334fdc0ac3087daf5e'
F = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
INDEX = F + 'final-transfer-20261006/index.json'
AUDIT = F + 'final-transfer-20261006/audit/final35-complete-audit.json'
G_AUDIT = 'policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/F-pr65-continuation-audit-2026-10-06.md'
SOURCE = 'policy-engine/src/polisyos/'
CAUSAL = SOURCE + 'foundry/methods/catalog/causal/'
OLD_CAU = 'cebe94d8134a4652bbfc1ae4d74ec6403940ced5'
NEW_CAU = '0b522ed173730b4ec744253bb75b6ee260bfcebb'
RDD = 'fb022aa12599ee1617f83d154cd9a8027b2a58b8'
SCM = '6dcb792b6f8c2d2dcfc04a5e04ea33135a2ad181'
STATIC = '5182825c190aa403bee765e339a119bb53e805e0'
GRAPH_HEAD = 'eaf9d0e0ee2dae728351cbb3dfc333474c88931b'
POLY = '6f95f55ca7d9c5cd9489256a354a27da058b46b9'
ECO = '532ca1f5ff78dad58ac00d261aeabff3a99f9aa6'
ECO_NEW = '4128879c3cec37dcb2bd1e7f91a1da5e4f51d2d3'
FRY = '63425f734946979cfc990e9cb91b00163f051898'
FAMILY = '7f05b6259e0c78fac81a0baa4bff41e648a9d771'
FAMILY_HEAD = 'e00dd3799cf2cdd14baf4b26e175ba1e848c3a6a'
API = '729d137279b7d6334230045e420255762fe55f08'
FIT = '55d2e14755bda6af31c41acd4fe1dcb76f3814b1'
LEX = '00a6eda114b903bc5abe86902cd8372426f739a1'

def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=REPO, stderr=subprocess.PIPE)

def read(sha: str, path: str) -> bytes:
    return git('show', sha + ':' + path)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def identity(sha: str, path: str) -> dict:
    raw = read(sha, path)
    return {'source_sha': sha, 'path': path, 'git_blob': git('rev-parse', sha + ':' + path).decode().strip(),
            'bytes': len(raw), 'sha256': digest(raw)}

def receipt_ref(sha: str, name: str) -> dict:
    return identity(sha, F + name)

def node_refs(sha: str, path: str, needles: list[str] = ()) -> dict:
    """Source identity/locator check only, not a runtime semantic verdict."""
    raw = read(sha, path)
    text = raw.decode()
    out = identity(sha, path)
    out['source_locator_check'] = 'PASS'
    if path.endswith('.py'):
        nodes = [n for n in ast.walk(ast.parse(text)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        selected = [n for n in nodes if not needles or any(v in n.name for v in needles)]
        out['symbol_locators'] = [{'name': n.name, 'line': n.lineno, 'end_line': n.end_lineno,
                                  'slice_sha256': digest(''.join(text.splitlines(keepends=True)[n.lineno-1:n.end_lineno]).encode())}
                                 for n in selected]
        if needles and not selected:
            raise AssertionError((sha, path, needles))
    return out

# Each row is a technical recommendation under the ORIGINAL criterion; no G ledger mutation.
# Fields: original scope, actual consumer, proposed outcome, deciding discriminator, original-scope remainder,
# separate unavailable production/authority, correction to421.
RULES = {
 'B204': ('Standard estimability and honest pretrend disposition, hand ATT3', 'StandardDifferenceInDifferences.pure_step → canonical report; root diagnostic reader is a separate bound consumer', 'closed', 'Zero-pre guard removal FAIL; native ATT3, not_testable/nonrejection/violation, retained time_treatment-only diagnostic attack', 'None for this original finite design predicate.', 'Untreated real parallel trends and causal identification are not established by pretrend nonsignificance.', 'Replace «Идентифицированный DiD» with estimable contrast plus diagnostic states; no identification claim.'),
 'B205': ('Actual HC1 and unit-cluster CR0 execution', 'StandardDifferenceInDifferences.pure_step → actual OLS scores/unit groups → report', 'closed', 'Independent Statsmodels HC1/CR0, duplicated periods and unit identity; HC1-for-CR0 removal FAIL', 'None in declared large-unit covariance algebra.', 'Small-cluster nominal coverage and real-design admission remain outside property.', 'Preserve actual covariance procedure, not reported cov_type label.'),
 'B206': ('Requested confidence level actually changes BOTH DiD and RDD bounds', 'StandardDifferenceInDifferences and RegressionDiscontinuity → native report/CAS readers', 'closed', '80/95/99 quantiles, point preservation/invalid levels; hardcoded95 removal FAIL; RBC current source supplement', 'None in requested-level interval construction.', 'This does not prove B205 covariance or B210 RBC coverage.', 'Retain dual sourcecebe and sourcefb; do not assign all evidence to one DiD receipt.'),
 'B207': ('Fixed selected-participation estimand with estimated-share ratio IF and one iid unit multiplier', 'StaggeredDifferenceInDifferences → genuine MethodJob/CAS → fresh report reader', 'closed', 'Independent share derivative and shared-unit law; single-cell variance, serial multi-cohort MC160 retained, share-IF removal FAIL', 'Original selected iid-unit scientific discriminator is established; final composition source must stay distinct.', 'Full production EvalSafety/admitted units/real graph and parallel trends remain UNRUN separately.', 'Separate source_criterion closed from old aggregate limited for whole production admission; do not label θW as θsel.'),
 'B208': ('Centered studentized null test with the SAME closed finite-B CI inversion', 'StaggeredDifferenceInDifferences → result null/CI → actual native consumer', 'closed', 'MC160 exact oldsource null6/160 and coverage154/160; endpoint integer-tail24 controls and uncentered removal FAIL', 'None in selected pointwise iid-unit finite-B law.', 'No small-G/simultaneous/real-data coverage claim.', 'Retain exact endpoint correction provenance; unchanged heavy wave is not a new run.'),
 'B209': ('Anticipation-safe controls and full fixed eligible-horizon target; no silent drops', 'StaggeredDifferenceInDifferences → whole requested cohort admission → CAS refusal/readback', 'closed', 'g=t+a excluded, never-treated/a0 positive; missing baseline/support refuses full requested target; changed E changes binding', 'None in declared synthetic eligibility predicate.', 'Chosen anticipation window is not empirical proof of a real window.', 'Do not require real-data authority to measure fixed synthetic timing/control law.'),
 'B210': ('Sharp fixed-profile CCT robust bias correction and variance', 'RegressionDiscontinuity → MethodJob/CAS → canonical dematerializer/fresh reader', 'closed', 'Actual rdrobust2.1.0 dev parity36 + two2000-replicate coverage groups; repaired full removal4036 rejects', 'None for selected finite sharp HC0 profile.', 'No fuzzy/cluster/selector/real-design identification; no parallel shim.', 'Preserve real external oracle install identity and corrected removal denominator; old removal no-MC harness gap remains historical.'),
 'B211': ('RDD weighted O(np) structures preserve supported numerical kernels/order/SE', 'RegressionDiscontinuity weighted design → report/dispatcher', 'closed', 'Native permutation/kernel/order/reference and no dense diag control', 'None in selected supported linear-algebra property.', 'No whole-estimator measured speedup or new statistical law inferred.', 'Use original performance/numerical criterion, not broad backend claim.'),
 'B212': ('Real backend point-only uncertainty has NO invented CI; real CI stays compatible', 'DoWhyIdentifyEstimate → actual Python3.12 worker estimate → parent report/CAS → fresh3.14 reader', 'closed', 'Actual estimate getCI None remains noneligible point-only; malformed numeric shapes refuse; genuine backend property removal', 'Finite original backend/shape criterion measured; latest root/installed receipt composition must remain exact.', 'Production source/identification authority and optional unselected3.14 backend are UNRUN.', 'Point-only criterion is distinct from B213 target/estimand binding and from G production acceptance.'),
 'B213': ('Request estimand type/contrast/target and actual backend identification/estimation binding', 'DoWhyIdentifyEstimate → genuine identify_effect/estimate_effect → canonical report factory', 'closed', 'Actual supported ATE/backdoor adjustment, independent OLS; unsupported requests refuse; source/CAS payload binding negatives', 'Selected ATE finite profile only, not universal backend method capability.', 'Admitted real-world graph/source validity and authority positive remain UNRUN.', 'Do not equate labels/reflection/proceed flag with actual requested estimand.'),
 'B214': ('Known reversed arrow normalization and explicit unresolved endpoint/cycle refusal', 'ReconcileCausalGraph intake/CAS + static ADMG/GCM consumers', 'limited', 'Source reverse-arrow positive and circle/PAG/lag typed refusal; static518 now rejects all6 unsupported endpoint pairs', 'Need exact latest graph-intake source/receipt for valid TAIL–TAIL request through actual node, not only ADMG primitive.', 'General PAG identification and protected authority are not claimed.', 'Keep actual unresolved-endpoint intake escape separate from already-proven reverse arrow and finite ADMG property.'),
 'B215': ('Actual conditional Gaussian noise posterior and complete-fact residual inverse', 'GCMQuery/TwinNetworkQuery → typed conditional result → genuine CAS/fresh reader', 'closed', 'Independent affine Gaussian mean/cov/singular evidence; Y2 gives Uy mean1/var.5; fullX1Y2→Y0=1', 'None for declared affine Gaussian profile.', 'Nonlinear/unknown-law partial posterior is typed limited; no real-data identification.', 'Posterior predictive/credible spans are not estimator sampling CI.'),
 'B216': ('Endpoint-aware m-separation AND actual do/sigma/IDC consumer paths', 'CachedAdjacency/m_separation → real do/sigma/ID/IDC/IDC*/AMN/CTF entries', 'closed', '200ADMG×12 independent latent moralization plus static518 real fork/collider/descendant, do/sigma, two actual IDC ID calls and IDC*', 'Finite supported fully specified static ADMG only; malformed fixture failures retained.', 'No completeness for arbitrary PAG/temporal identification.', 'Widen old Rule1-only label to the actual518 full entry/consumer denominator; not just importability.'),
 'B217': ('Perfect do removes latent incoming ends and preserves outgoing effects', 'ADMG perfect surgery → real Rule3/do consumer', 'closed', '200graphs×8actions×12 explicit latent-DAG surgery; bidirected-cut removal FAIL; known reverse normalization', 'None within finite supported static ADMG.', 'Conditioning/fixing and universal ID completeness are separate laws.', 'Carry old surgeryoracle plus new518 input-profile admission exactsources.'),
 'B218': ('Lag/self-lag survives representation/export; static inference refuses absent unrolling', 'CausalGraphModel → actual NetworkX/CAS roundtrip → static GCM/ADMG/intake', 'limited', 'Actual lag1/lag2/self-lag export; static refusal and expanded finite graph sanity', 'Need exact newest intake consumer endpoint+lag packet; do not invent a temporal method or call serialization identification.', 'Unprovided temporal identification/real readiness are separate unknown capabilities.', 'Use temporal-preservation/static-refusal criterion; not automatic requirement for a new dynamic estimator.'),
 'B219': ('Actual mixed parallel edge export preserves complete keyed multiset/order', 'CausalGraphModel.to_networkx → NetworkX3.6.1 MultiDiGraph → CAS/fresh reader', 'closed', 'Fullpayload120 permutations/60unique; DiGraph substitution retains markers but edge multiset FAIL', 'None for actual native NetworkX export profile.', 'Live Kuzu/Rustworkx transports not run, not implied.', 'Missing backend historical reason superseded by actual native NetworkX witness only.'),
 'B220': ('Deep immutable topology, detached rows, warmed-copy freshness and weakref cleanup', 'CausalGraphModel model_copy/dump/ancestors/export/rows → real native cache readers', 'closed', 'Native75+independent23; nested-freeze/row-alias/weakref removals each actualFAIL;518 retained19cache cases', 'None for original local cache divergence property.', 'Live Kuzu/readiness/real causal authority remain UNRUN outside local property.', 'Correct fragment to actual internal provider; absent public inventory does not make CausalGraphModel public_stable.'),
 'B221': ('Observed root/joint-row law survives fit/model/runtime; unknown law stays limited', 'Actual GCMFit worker/source rows → source-bound SCM → GCMQuery fresh reader', 'closed', 'Truefit n400 selected backend + rootlaw/dependentrow oracle and coherent fake fit/source permutations', 'Supported declared empirical/affine profile.', 'No automatic nonlinear fitter or real-data identification.', 'Separate historical analytic profile from actual selected backend fit receipt.'),
 'B222': ('Conditional fitted additive polynomial payload executes its declared law throughout query/twin', 'Existing _fit_additive_noise_poly → typed manualSCM1.0 → MethodJob/CAS → fresh query/twin process', 'closed', 'Exact6f helper101x² produces do2=4; LINEAR samefields7; factual1/1.25 counter4.25 ITE3; independent cubic8/8.25/3.25; evaluator removal2FAIL1LINEARPASS', 'Finite no-cross-term additive payload; partial nonlinear posterior remains typed limited.', 'No new default nonlinear Hybrid/DoWhy fitter, general posterior or real authority.', 'Replace broad nonlinear fitter implication with original conditional helper/payload criterion; no extra commissioning prerequisite.'),
 'B223': ('Explicit target/comparator and same-U causal contrast; law/inference kinds remain separate', 'GCMQuery/TwinNetworkQuery → result DTO/CAS → real RunCausalQueriesNode', 'closed', 'do2−do0=6,samearm0; actual changed-arm coherent job/CAS refuses; predictive vs optional iid-refit typed intervals', 'Finite declared static profiles and explicit comparators.', 'No gating identification based on simulated draw-count narrowing.', 'Keep comparator identity and original request binding, not aliases/markers alone.'),
 'B224': ('Perfect do bypasses replaced natural mechanism and prunes irrelevant work safely', 'GCMQuery surgical planning/sampler → CAS result reader', 'closed', 'Broken oldmechanism bypass do2→7;shift still requiresnatural; full/pruned/reordered common-row draws and unexecuted20roots', 'Static declared law/planning only.', 'Temporal mismatch refuses; no unsupported law authority.', 'Preserve factual ancestors/shared-noise requirements despite pruning.'),
 'B225': ('Declared stochastic-law parsing/support and numerically stable conditional tails', 'GCMQuery stochastic intervention sampler → outcome DTO/CAS', 'closed', 'Five5000draw CDF/DKW controls use independent math.erfc Normal CDF/SF and analyticUniform; unknownlaw fallback7 refuses', 'Supported Normal/Uniform/TruncNormal/explicit atomic laws.', 'No unknown policy law admission or policy authority.', 'Correct old independentSciPyCDF label: original581 test already computes independent math.erfc, positive-tail SF difference.'),
 'B54': ('Fit-cache identity separates nuisance fit from current diagnostics and immutable readers', 'fit_crossfit_nuisance_bundle → controlled issued fit core → fit_tmle_ate/TMLEEstimator', 'closed', 'All32contractfields/currentfitcalls; changeddata/seed/splits invalidates; reader/cache/precomputed identity removals FAIL', 'Finite original native cache/reader property.', 'Untrusted externally supplied prediction provenance is not accepted; production causal authority separate.', 'Do not impose a new persistence contract on original B54 cache predicate.'),
 'B56': ('All folds/repeats/seeds/results survive common admitted-work resource accounting', 'Real LocalWorkerPool studies → actual fold fits → result CAS/fresh reader', 'limited', 'Native cap1/2 fourstudies24folds, serial/parallel-request equality, barrier/wait/admission; nested executor removal FAIL', 'Latest owner broker/study admission receipt needed for any cross-process/whole resource-bound closure.', 'No cloud verification quota; production admission positive and native thread quota not inferred.', 'Measured local admitted worker profile is distinct from declared metadata or all-process budget.'),
 'LA-001': ('Treasury relocation preserves seed/IDs/salts/plans and actual RNG behavior', 'compile.api.compile → compile_trinity → TreasuryPlan → execute.api.execute → execute_program_graph → adaptive_agent', 'closed', 'Seed0/nonzero, recompilation/permutation, unmarked historical plans, realnativekey/dispatcher; salt removal retainsmarkers and FAIL', 'Versioned v1 intentionally has same node draw at steps0/1; unchanged temporal law.', 'No newly commissioned fresh innovation law or real economic validity.', 'Do not move time-law followup into original relocation acceptance.'),
 'LA-002': ('Canonical family catalog, real IC service/certificates, reexports and supported runtime loading', 'Catalog → real ICVerificationRequest → IR certificate CAS/fresh reader; actual native runtime descriptor', 'closed', 'All4 concretepositive certificates + wrong-payment negative; family-owner/catalog-as-IC removals FAIL; actual native income_tax', 'Scoped original migration complete at7f05/3e181.', 'Four new optional family execution mappings and real-world IC are outside criterion.', 'Remove invented family-certificate→new state-kernel requirement; use e00 family-layout receipt.'),
 'LA-003': ('Named fiscal/labor baseline relocation with PatchMap/mask/key/spec/compiler/replay ABI', 'Registry-created native fiscal/labor → apply_patch_map → complete GlobalState; actual runtime adapters', 'limited', '532 fullfiscal/labor patches,key,active/target/accounting; existing compiler/replay/JIT; current412 new actual Composite/native tests require owner outcome receipt', 'Latest root reports actual broad fiscal precision FAIL: exact full deciding source/receipt and root re-adjudication pending. Old finite532 controls do not close this broader actual consumer property.', 'No equivalence to richer plugin or admitted production calibration.', 'Keep measured narrow relocation controls separate from current whole LA003 limited and actual precision red; do not merge distinct laws.'),
 'LA-004': ('Two DISTINCT economic profiles: matched regimes, deliberate divergence, accounting, seeds and observables', 'Native fiscal/labor PatchMap/GlobalState and EconomicsPlugin→CompositeExecutor/EconomicState', 'closed', '532matchedtax/subsidy + distinctunits/means-test/laborseed; latest412 realComposite tax/labor states and zero-employment match/diverge', 'Need exact owner per-original-card outcome/receipt, currently primary532 remains held for unrelated norm.', 'No fullmodel calibration/replacement/migration or externaleconomicnorm implied.', 'Remove Gini pairwise and missing welfare norm from LA004 deciding criterion; Gini separate unassigned technical property.'),
 'LA-007': ('Exact EMPTY id_engine.py sibling absent; preserved package/algorithms and finite loader/install consumers', 'Actual id_engine package/find_spec/imports/native identify → installed wheel/sdist → CAS fresh evidence', 'limited', 'Base198 exact sibling absence; API729 real nonempty package/ID algorithm and installed13compat each; direct facade bindings', 'Need exact latest owner finite filename/loader/sourceinventory/docs/install per-original-card packet; do not require all hypothetical external users.', 'External computed unknown inputs recorded separately; no new deletion performed here.', 'Already absent base198; do not claim new file removal or delete same-name package.'),
 'LA-016': ('Dedicated DiD metadata/callers/flags/slots and default-registry retirement with historical replay', 'Maintained G2 request candidate → dedicated standardFQN → actual registry/dispatcher/CAS; declared historical direct adapter', 'closed', '0b/f88 complete maintained source/config6507/6509+outside4694 census, actualroute9PASS; restoreoldFQN1FAIL; original wrappers/metadata poison', 'Bounded supported maintained window, historical direct-import replay kept explicit.', 'Unenumerated external dynamic/frozen inputs require owner packet, not universal criterion.', 'OneID/two identical source bindings. Replace old umbrella dispatcher consumer and missing maintained caller claim with0b exact route.'),
 'LA-017': ('Norm diff/issues/pass config/report refs/topic hypotheses survive actual supported consumers', 'NormImpactAnalyzer actual LegalPass→CAS→fresh NormDiff/Impact reader→CLI markdown', 'limited', '00a24native checks, duplicateplan dedupe3FAIL controls, actualsyntheticLegalPass→persistedreport', 'Original full supported caller/config migration/corpus compatibility still needs exact owner packet; dedupe alone is partial.', 'Current-law authority/source corpus is local and UNRUN; topics are not causal quantified effects.', 'Do not treat current-law admission as prerequisite to a synthetic transport migration; keep genuine remaining migration limits.'),
 'LA-019': ('Exact EMPTY causal_engine.py/interference.py siblings absent; preserve packages and known loaders', 'Preserved causal_engine/interference packages/native algorithms → installed supported imports/ABI', 'limited', 'Base198 twoexactfilenames absent; API installed canonical package/directalgorithm/patch witnesses', 'Need exact owner finite source/filename/loader/docs/package per-card reconciliation.', 'Unprovided external computed consumers remain unknown, not blanket package deletion authority.', 'Already absent base198; preserve nonempty same-name packages, no LA020 prerequisite invented.'),
 'LA-020': ('Explicit supported public facade manifest, canonical identities/FQNs/patch consumers/docs/install', 'Canonical facade→real native algorithms/FQN/pickle/pydoc→wheel/sdist neutral-cwd consumers', 'limited', '729 direct/star/privatewindow, fouractualpatchtargets, incidental/staleexports refusal; clone/bridge removals1/4FAIL', 'Original supported docs/client window needs latest API criterion reconciliation;182computed candidates must be classified as inputs rather than assumeall supported.', 'Unprovided arbitrary external clients/hosted surfaces UNRUN separately.', 'Supported finite ABI acceptance is not absence of reflection alone and not proof of everypossible computed importer.'),
 'LA-035': ('Named GlobalState normalized-income/budget baseline relocation preserves ORIGINAL formula and guards; current requested optimizer/intent basis remains separate', 'economics.baselines.normalized_income_budget_loss → two legacy aliases → nativeGlobalState/real guardrail/JIT/grad; actual maintained optimizer caller not supplied', 'held', '532positive/zero/negative/mixed/populations/scales/breach/NaNInf/JITgrad/importer; >=1nonnegative score−1 preserved;412 appended actualwholeconsumer tests pendingreceipt', 'Technical historical baseline/replay/aliases profile is measured, but latest user continuation requires actual optimizer and semantic intent packet. Missing unit/population/time/sign intent and named optimizer keep whole LA035 held per economics owner.', 'No actual production optimizer, normative unit/population/time/sign intent owner packet, policy objective or full external retirement established.', 'Keep technical historical-baseline closed/profile whole held; do not replace formula or infer original whole closure from aliases/JIT/grad.'),
 'LA-037': ('Native IR slot owner, direct compiler/docs caller and supported wrapper/install compatibility', 'IR.kernel.slots → TrinityCompiler/default registry → PatchOp/state/CAS; scoped realMkDocs Python handler; installed owners', 'closed', '7f05native40 + actualcompile1 + layoutCAS3, layout removalFAIL; realstatepage buildPASS; exactownerbytes installed5cd13wheel/13sdist', 'Original finite supported migration covered; retained compatibility lifecycle separate.', 'Fullstrictdocs/architecture/production admission not implied by scoped page; optionalfamilyexecution notcriterion.', 'Use real IR/native/compiler/docs/install receipt e00, not aliasidentityalone or full wrapper retirement prerequisite.'),
}

# Latest user continuation asks for real admitted/source-bound consumer capability as well as
# the original generic numerical discriminator. Those are separate states, never blanket real-data
# prerequisites retroactively added to a known-DGP technical property.
CONTINUATION_OUTCOMES = {fid:'limited' for fid in ['B207','B208','B209','B212','B213','LA-004']}
CONTINUATION_OUTCOMES['LA-035']='held'

SOURCES = {
 'CAU-01': [(NEW_CAU, CAUSAL+'did.py', ['_run_standard_did','_parallel_trend_diagnostic','_ols_hc1','StandardDifference','_diagnostic_contract'])],
 'CAU-02': [(NEW_CAU, CAUSAL+'did.py', ['_run_staggered_did','_staggered','StaggeredDifference','_diagnostic_contract'])],
 'CAU-03': [(RDD, CAUSAL+'rdd.py', ['RegressionDiscontinuity','rdd','weighted'])],
 'CAU-04': [('423165322e508a293ffd23918c039c99fb37e7a7', CAUSAL+'dowhy_identify_estimate.py', ['DoWhy','pure_step']), ('423165322e508a293ffd23918c039c99fb37e7a7','policy-engine/workers/dowhy-014/worker.py',['linear_ate','execute'])],
 'CAU-05': [(NEW_CAU, CAUSAL+'did.py', ['DifferenceInDifferences']), (NEW_CAU,SOURCE+'runtime/quality/proving_ground/causal_forecast_search.py',['_default_g2_runtime_method_candidate'])],
 'GRF-01': [(STATIC, CAUSAL+'admg_ops.py',['CachedAdjacency','m_separation','surgery']), (STATIC,CAUSAL+'do_calculus.py',['rule']), (STATIC,CAUSAL+'sigma_calculus.py',['rule']), (STATIC,CAUSAL+'id_engine/core.py',['idc','ID'])],
 'GRF-02': [('2137961b0d3a2b39b85c5a57bf774777d2a4204e',SOURCE+'ir/analytics/causal_graph.py',['CausalGraphModel','networkx','model_copy','cache'])],
 'GRF-03': [('6321dc33476b0fad24d97ebb140c373608d30019',CAUSAL+'graph_reconciliation.py',['Reconcile','pure_step']), (STATIC,CAUSAL+'admg_ops.py',['CachedAdjacency'])],
 'SCM-01': [(SCM,CAUSAL+'gcm_fit.py',['GCMFit','pure_step','poly']), (POLY,CAUSAL+'gcm_query.py',['polynomial','mechanism'])],
 'SCM-02': [(SCM,CAUSAL+'gcm_query.py',['posterior','GCMQuery','contrast']), (SCM,CAUSAL+'twin_network_query.py',['TwinNetwork','pure_step'])],
 'SCM-03': [(SCM,CAUSAL+'gcm_query.py',['stochastic','sample','GCMQuery'])],
 'FIT-01': [(FIT,CAUSAL+'tmle_core.py',['fit_crossfit','fit_tmle','materialize'])],
 'FRY-01': [(FRY,SOURCE+'foundry/compile/randomization.py',['Treasury','build']), (FAMILY,SOURCE+'foundry/methods/catalog/mechanism/families.py',['family']), (FAMILY,SOURCE+'ir/kernel/slots.py',['build_slot'])],
 'FRY-03': [(ECO,SOURCE+'foundry/methods/catalog/mechanism/runtime.py',['IncomeTax','LaborMarket','TaxSubsidy']), (ECO,SOURCE+'foundry/execute/_internal/patching/__init__.py',['apply_patch_map'])],
 'ECO-01': [(ECO,SOURCE+'foundry/plugins/economics/mechanisms.py',['Taxation','Transfer','LaborMarket']), (ECO,SOURCE+'foundry/plugins/economics/baselines.py',['normalized_income_budget_loss'])],
 'LEX-01': [(LEX,SOURCE+'lex/legal_evaluation/impact_diff.py',['NormImpact','analyze'])],
 'API-01': [(API,CAUSAL+'causal_engine/__init__.py',[])],
}

def main() -> None:
    started_head = git('rev-parse','HEAD').decode().strip()
    inputs = {k: identity(sha,p) for k,sha,p in [('frozen421_index',TRANSFER,INDEX),('frozen421_fullaudit',TRANSFER,AUDIT),('fresh_G363_audit',G,G_AUDIT)]}
    idx=json.loads(read(TRANSFER,INDEX)); audit=json.loads(read(TRANSFER,AUDIT))
    old={r['finding_id']:r for r in idx['finding_rows']}; audit_rows={r['finding_id']:r for r in audit['rows']}
    assert set(old)==set(RULES) and len(old)==35
    tsvpath='policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv'
    owner_rows=list(csv.DictReader(io.StringIO(read(BASE,tsvpath).decode()),delimiter='\t'))
    owners={r['finding_id']:r for r in owner_rows if r['unit']=='F'}
    assert set(owners)==set(RULES)
    source_checks={}; source_failures=[]
    for bundle,refs in SOURCES.items():
        source_checks[bundle]=[]
        for sha,path,needles in refs:
            try: source_checks[bundle].append(node_refs(sha,path,needles))
            except (subprocess.CalledProcessError,AssertionError,SyntaxError) as e:
                source_failures.append({'bundle':bundle,'sha':sha,'path':path,'error':str(e)})
    registry=[]
    for x in audit['receipt_registry']:
        actual=identity(x['head'],x['receipt_path']); assert actual['bytes']==x['receipt_bytes'] and actual['sha256']==x['receipt_sha256']
        assert git('rev-parse',x['implementation_sha']+'^{tree}').decode().strip()==x['candidate_tree_sha']
        registry.append({**actual,'implementation_sha':x['implementation_sha'],'implementation_tree':x['candidate_tree_sha'],'lane':x['lane'],'role':x['role'],'binding_check':'PASS'})
    supplements={
        'current_cau': receipt_ref('f88c98a190c336ef414361a236276ed7ea6d3d62','did-diagnostic-basis-20261006.json'),
        'current_family_layout': receipt_ref(FAMILY_HEAD,'family-layout-consumers-20261006.json'),
        'current_static_admg': receipt_ref(GRAPH_HEAD,'static-admg-profile-20261006.json'),
        'current_polynomial': receipt_ref(GRAPH_HEAD,'polynomial-helper-cas-20261006.json'),
    }
    installed_equivalence_path=F+'family-layout-consumers-20261006/layout-installed-equivalence.json'
    installed_equivalence=json.loads(read(FAMILY_HEAD,installed_equivalence_path))
    installed_binding_checks=[]
    for item in installed_equivalence['source_equivalence']:
        measured=[]
        for sha,expected in item['sources'].items():
            actual=identity(sha,item['path'])
            assert all(actual[k]==expected[k] for k in ['git_blob','bytes','sha256'])
            measured.append(actual)
        assert measured[0]['sha256']==measured[1]['sha256']
        installed_binding_checks.append({'property':'exact unchanged installed layout owner bytes','check':'PASS','refs':measured})
    installed_receipt=installed_equivalence['original_installed_receipt']
    for c in installed_equivalence['reconciled_existing_checks']:
        actual=identity(installed_receipt['git_sha'],c['output'])
        assert actual['bytes']==c['output_bytes'] and actual['sha256']==c['output_sha256']
        installed_binding_checks.append({'property':'complete historical installed output custody; not a fresh run','check':'PASS','ref':actual,'observed_run_source':c['target_sha'],'original_outcome':c['outcome']})
    rows=[];binding_count=0
    for fid in old:
        row=old[fid]; scope,consumer,outcome,oracle,remainder,external,correction=RULES[fid]
        blocks=[];refs=[]
        for ref in row['original_source_criterion_refs']:
            raw=read(ref['source_sha'],ref['source_path']); start,end=ref['lines']; part=b''.join(raw.splitlines(keepends=True)[start-1:end])
            assert len(part)==ref['bytes'] and digest(part)==ref['sha256']
            assert part.decode().splitlines()[0]==ref['title']
            assert git('rev-parse',ref['source_sha']+':'+ref['source_path']).decode().strip()==ref['document_git_blob']
            assert ref['criterion_id']==fid
            blocks.append(part);refs.append({**ref,'byte_binding_check':'PASS'});binding_count+=1
        supplied=pathlib.Path('/tmp/e02-F-continuation-20261006/original-cards',fid+'.md').read_bytes()
        assert supplied==b'\n'.join(blocks),(fid,'scratch card != source-bound exact blocks')
        a=audit_rows[fid];primary_index=row['receipt_registry_index']; entry=audit['receipt_registry'][primary_index]
        # Original selectors/deciding refs stay source-bound via fullaudit; don't copy original-card text/whole source.
        # Full deciding records already exist in tracked immutable audit; retain reconstruction locators,
        # never duplicate its complete check/source footprint for every row.
        deciding={'source_sha':TRANSFER,'path':AUDIT,'json_pointer':f'/rows/{list(old).index(fid)}/deciding_check_refs',
                  'count':len(a['deciding_check_refs']),
                  'check_ids':list(dict.fromkeys(c.get('check_id') for c in a['deciding_check_refs']))}
        extra=[]
        if fid in ['B204','B207','B208','B209','LA-016']:extra.append('current_cau')
        if fid in ['LA-001','LA-002','LA-037']:extra.append('current_family_layout')
        if fid in ['B216','B217','B220']:extra.append('current_static_admg')
        if fid=='B222':extra.append('current_polynomial')
        secondary_receipts=[]
        if fid=='B206':
            secondary_receipts=[i for i,x in enumerate(registry) if x['path']==F+'rdd-sharp-rbc-20261006.json']
            assert len(secondary_receipts)==1
        if fid in ['LA-007','LA-019','LA-037']:
            secondary_receipts=[i for i,x in enumerate(registry) if x['path'] in [F+'api-20261006.json',F+'installed-latest-dependencies-20261006.json']]
            assert len(secondary_receipts)==2
        secondary=[]
        if fid=='B206': secondary.append(node_refs(RDD,CAUSAL+'rdd.py',['RegressionDiscontinuity','rdd']))
        if fid in ['LA-003','LA-004','LA-035']:
            secondary.append(node_refs(ECO_NEW,'policy-engine/tests/unit/foundry/plugins/test_economic_profile_consumers.py',['registered','matched','historical']))
        rows.append({'finding_id':fid,'original_titles':list(dict.fromkeys(x['title'] for x in refs)),
                     'original_card_bindings':refs,'scratch_card':{'path':f'/tmp/e02-F-continuation-20261006/original-cards/{fid}.md','bytes':len(supplied),'sha256':digest(supplied),'check':'PASS'},
                     'owner_tsv':owners[fid], 'bundle':row['primary_bundle'],
                     'source_scope':scope,'actual_consumer':consumer,'finite_check':row['check'],
                     'old421_outcome':row['outcome'],'technical_original_criterion_recommendation':outcome,
                     'current_continuation_outcome_recommendation':CONTINUATION_OUTCOMES.get(fid,outcome),
                     'technical_historical_baseline_profile_outcome':'closed' if fid=='LA-035' else None,
                     'recommendation_is_G_accepted':False,
                     'oracle_and_negative':oracle,'original_criterion_remainder':remainder,'separate_unavailable_inputs_or_authority':external,
                     'correction_to421':correction,'primary_receipt':{'head':entry['head'],'path':entry['receipt_path'],'sha256':entry['receipt_sha256'],'bytes':entry['receipt_bytes'],
                        'scientific_source_sha':entry['scientific_implementation_sha'],'candidate_tree_sha':entry['candidate_tree_sha']},
                     'deciding_check_refs_at421':deciding,'complete_original_owner_decision_ref':{'source_sha':TRANSFER,'path':AUDIT,'json_pointer':f'/rows/{list(old).index(fid)}/author_per_id_original'},
                     'source_locator_check_bundle':row['primary_bundle'], 'secondary_source_locator_checks':secondary, 'supplement_keys':extra,
                     'secondary_frozen_receipt_registry_indices':secondary_receipts,
                     'readiness_for_canonical_owner_decision': 'pending exact owner reconciliation receipt' if fid in ['LA-003','LA-004','LA-035','LA-007','LA-019','LA-020','B56','B214','B218','LA-017'] else 'finite original criterion evidence identified; owner/G ledger decision remains separate'})
    assert binding_count==36 and len(set(r['finding_id'] for r in rows))==35 and len(set(r['bundle'] for r in rows))==17
    # Additional actual test source locators establish named consumers, not new runtime passes.
    test_refs=[(ECO,'policy-engine/tests/unit/foundry/plugins/test_economic_profiles.py',['equal','labor','historical']),
               (ECO_NEW,'policy-engine/tests/unit/foundry/plugins/test_economic_profile_consumers.py',['registered','matched','historical']),
               (FAMILY,'policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py',['test_']),
               (API,'policy-engine/tests/unit/foundry/methods/catalog/causal/test_installed_facade_contract.py',['installed','public','patch']),
               (STATIC,'policy-engine/tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py',['test_']),
               (POLY,'policy-engine/tests/unit/foundry/methods/catalog/causal/test_polynomial_helper_cas_consumers.py',['test_']),
               (SCM,'policy-engine/tests/unit/foundry/methods/catalog/causal/test_scm_result_semantics.py',['cdf','law'])]
    test_checks=[node_refs(*x) for x in test_refs]
    sf=read(SCM,test_refs[-1][1]).decode(); assert 'math.erfc' in sf and 'sf(lo) - sf(value)' in sf
    # Direct exact sibling absence proof at the admitted immutable base; nonempty packages are retained.
    retired=[]
    for name in ['id_engine','causal_engine','interference']:
        path=CAUSAL+name+'.py';present=subprocess.run(['git','cat-file','-e',BASE+':'+path],cwd=REPO,capture_output=True).returncode==0
        assert not present
        package=identity(BASE,CAUSAL+name+'/__init__.py')
        assert package['bytes']>0
        retired.append({'exact_file':path,'source_sha':BASE,'exact_file_exists':False,'retained_nonempty_package':package,'check':'PASS','new_deletion_claim':False})
    ended_head=git('rev-parse','HEAD').decode().strip();assert started_head==ended_head
    result={'schema':'F-original35-independent-reconciliation/1','role':'read-only technical criterion proposals for root canonical ledger; no formal closure/G writes',
            'source_refs':inputs,'own_git_head_begin_end':{'begin':started_head,'end':ended_head,'check':'PASS'},
            'denominator':{'finding_ids':35,'source_bindings':36,'bundles':17,'duplicate_LA016_counted_once':True,'frozen421_receipt_components':15},
            'scope_limits':['No scientific/native reruns in this criterion-only task. Existing exact source/check receipts retained, not relabeled to421 or current combined runtime.',
                            'Source locator/AST/hash checks establish provenance and actual consumer names, not scientific correctness by naming/reflection.',
                            'Technical criterion closure recommendations are not G acceptance or production/authority approval.',
                            'Optional Python3.14 marker exclusions are not backend PASS; actual3.12 subprocess/backend receipts are distinct.',
                            'Historical175c provenance-only blob unavailable/HTTP404 remains UNRUN; none of these recommendations depends on it.'],
            'frozen_receipt_bindings':registry,'supplement_receipt_bindings':supplements,'source_locator_checks_by_bundle':source_checks,'actual_test_source_locators':test_checks,
            'fresh_independent_unchanged_installed_source_and_output_bindings':installed_binding_checks,
            'exact_base_retired_sibling_checks':retired,'source_locator_failures':source_failures,
            'own_prior_independent_checks_not_rerun':[
               {'scope':'0b producer/maintainedLA016 request route','source_sha':NEW_CAU,'receipt':supplements['current_cau'],'new_run':False},
               {'scope':'root actual current typed input views and complete diagnostics consumer','source_sha':'3afb3ea5f26ad429ac45be78bd2cbd180fcc5a77','scratch_review':'/tmp/e02-F-continuation-20261006/cau/root-causal-consumer-independent-review.json','new_run':False,'bound':'actual23PASS + diagnostic7expectedFAIL + selectedview1expectedFAIL; no authority positive'},
               {'scope':'B222 genuinehelper→CAS→query/twin + independentcubic/manualprofilefalsifier','source_sha':POLY,'scratch_review':'/tmp/e02-F-continuation-20261006/cau/b222-independent-review.json','new_run':False,'bound':'8nativePASS, polynomialremoval2FAIL1LINEARPASS; fullfactualonly nonlinearabduction'}],
            'rows':rows,'technical_original_criterion_proposal_counts':dict(Counter(r['technical_original_criterion_recommendation'] for r in rows)),
            'current_continuation_proposal_counts':dict(Counter(r['current_continuation_outcome_recommendation'] for r in rows)),
            'decision':'PASS_BOUNDED' if not source_failures else 'ERROR_SOURCE_LOCATOR','formal_ledger_acceptance':'UNRUN'}
    PREFIX.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# Independent original35 reconciliation proposals','',f'Frozen421 `{TRANSFER}`; exact G audit `{G}`. 35 IDs, 36 source bindings, 17 bundles. No source or ledger edits; no scientific reruns.','',
           '| ID | Source criterion | Technical / current continuation proposals | Correction / remaining input |','|---|---|---|---|']
    for r in rows:
        lines.append('| '+r['finding_id']+' | '+r['source_scope'].replace('|','/')+' | '+r['technical_original_criterion_recommendation']+' / '+r['current_continuation_outcome_recommendation']+' (not G accepted) | '+r['correction_to421'].replace('|','/')+' '+r['original_criterion_remainder'].replace('|','/')+' |')
    lines.extend(['','Every exact original title/block hash/byte count and duplicate binding is in the JSON. Source/receipt/document-head identities remain separate. Ten rows name a pending owner reconciliation packet; missing inputs are not converted to formal closure.'])
    PREFIX.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'decision':result['decision'],'denominator':result['denominator'],'source_locator_failures':source_failures,'technical_proposals':result['technical_original_criterion_proposal_counts'],'continuation_proposals':result['current_continuation_proposal_counts'],'output':str(PREFIX.with_suffix('.json'))},ensure_ascii=False))

if __name__=='__main__': main()
