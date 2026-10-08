"""Append focused evidence to six rows; preserve the other29 byte-for-byte."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path('/workspace/e02-F-closeout-20261006')
E02 = Path('policy-engine/docs/research/e02-cloud-test-plan')
BASE = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
SOURCE = '4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
TREE = '551d4e760dc1168f6ad8182c9b176f00e94a2281'
RECEIPT = 'e89d449acc6eedb1629c42c428689f7c578fce26'
RP = E02 / 'implementation-handoffs/F/graph-profile-20261007.json'
LEDGER = ROOT / E02 / 'implementation-handoffs/F/continuation-transfer-20261007'
affected = ['B204', 'B212', 'B213', 'B214', 'B218', 'LA-037']

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def git_binding(ref, path):
    raw = subprocess.check_output(['git', 'show', ref + ':' + str(path)], cwd=ROOT)
    return {'git_ref': ref, 'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'git_blob': subprocess.check_output(['git', 'rev-parse', ref + ':' + str(path)], cwd=ROOT, text=True).strip()}

binding = git_binding(RECEIPT, RP)
handoff = json.loads((ROOT / RP).read_text())
source = {'sha': SOURCE, 'tree': TREE, 'base_sha': BASE, 'not_a_transfer_of_old_numerical_waves': True}
supersession = {
    'role': 'Explicit append-only supersession of the original B218 recommendation only',
    'from': {'F_recommendation': 'limited', 'refs': [dict(git_binding('bf335dd687c313fda9001fa3bb1365df6bc5ae1f', E02 / 'implementation-handoffs/F/scm-source-bound-20261006.json'), json_pointer='/per_id/4'), dict(git_binding('2044260c39dc4988b37d5a1568b65a1cdb1e3d31', E02 / 'implementation-handoffs/F/graph-intake-native-20261006.json'), json_pointer='/per_finding/1'), git_binding('072d45a56d1119fe3e7665cec2cbbdca015d2934', E02 / 'implementation-handoffs/F/continuation-transfer-20261006/per-ID/B218.json')]},
    'to': {'F_original_bounded_recommendation': 'closed', 'check': 'PASS', 'already_recorded_at': git_binding(BASE, E02 / 'implementation-handoffs/F/continuation-transfer-20261007/per-ID/B218.json')},
    'criterion': 'Actual lag1/lag2/positive-self-lag representation, NetworkX/CAS export and roundtrip, exact static refusal without temporal conversion',
    'new_affected_check': '4ee graph62PASS includes original GRF03 representation/reverse controls and actual static intake refusals',
    'separate_capability': {'protected_temporal_readiness': 'UNRUN', 'outcome': 'limited', 'serialization_is_identification': False},
    'historical_literals_preserved': True, 'G_formal_closure': 'not_issued',
}
descriptions = {
    'B204': {'implementation': 'e1c4bb28c9d5ff936ae1c047619c56cf12ba5347', 'check': 'PASS', 'consumer': 'Unchanged StandardDifferenceInDifferences → report → actual clean_rollout benchmark checker', 'result': 'Two preperiods: passedFalse/statisticNone/pNone/statusnot_testable/reasoninsufficient_pre_periods/identification_authorityFalse; original ATT2 DGP unchanged. Full affected benchmark3/3PASS.', 'oracle_negative': 'Independent four-means ATT1.9972170388636759 matches native1.997217038863679;10 retained-report diagnostic tamper controls refuse; unchanged25c checker FAIL retained.', 'limitation': 'Non-testability/nonrejection is not untreated parallel-trends authority. Base-red attribution remains P41not_established.'},
    'B212': {'implementation': 'unchanged423 worker; changed test body qualified on4ee', 'check': 'PASS', 'consumer': 'Actual configured Python3.12/DoWhy0.14 estimator → Python3.14 report/CAS → fresh3.14 reader', 'result': 'Three exact-source selected tests PASS. Point-only negative executes genuine CausalModel estimate then controlled interval/SE accessors returnNone; point survives, CI absent, non-gating.', 'oracle_negative': 'Actual backend fit, full request/result/CI/fresh-reader guards; controlled accessor-unavailability is a real-backend post-fit negative, not mock fitting or naturally missing-CI positive.', 'limitation': 'Optional in-process3.14 DoWhy/EconML and genuine identification/Runtime admission remainUNRUN.'},
    'B213': {'implementation': 'unchanged423 worker; changed test body qualified on4ee', 'check': 'PASS', 'consumer': 'Actual selected identify_effect/estimate_effect defaults → canonical typed factory → parent CAS → fresh3.14 reader', 'result': 'Focused3PASS genuine configured3.12/DoWhy0.14; selected ATE/control0/treatment1/targetate binding and fresh-reader assertions executed on exact4ee.', 'oracle_negative': 'Real selected fit/public builder ABI and persisted interval/non-gating reader checks; previous broader independent OLS/estimand negatives retain their own unchanged source bindings.', 'limitation': 'No new general mediation profile, actual real-source scientific identification or wholeNode admission proof.'},
    'B214': {'implementation': '36b18cc142aff77a5825126b4f07bafec09a5180', 'check': 'PASS', 'consumer': 'Scored real build_mgraph → registered job → direct/supplied/selected-CAS ReconcileCausalGraphNode; same-shape ADMG → CAS → different-PID reader', 'result': 'Declared DAG/ADMG family admission now precedes confidence/rewrites/persistence. MGraph/PAG/CPDAG refuse without publishing reconciled graph; original MGraph remains readable; ADMG/DAG/reverse positives preserved.', 'oracle_negative': 'Actual missingness extractor and graph-family identity; independent guard removal2behavioralFAIL/5positivePASS, installed removal1FAIL;62native+16installedPASS and real fresh-child readback.', 'limitation': 'Reconciliation-only family invariant. Broad sound partial/conditional extension and authority projection remainlimited; A/C/F tracked family/output contract and query whose effects differ across admissible completions are the trigger. No new general ID engine.'},
    'B218': {'implementation': '36b graph companion; original SCM6d/STATIC518 unchanged', 'check': 'PASS', 'consumer': 'Existing compact lag/self-lag graph export/NetworkX/CAS roundtrip plus actual static reconciliation refusal', 'result': 'Append explicit historical limited→current bounded-original closed supersession. New4ee static lag refusal validated; historical original lag persistence proof preserved.', 'oracle_negative': 'Actual lag1/lag2/positive-self-lag and static refusal; known reverse control preserved in affected62PASS; original graph source scope unchanged.', 'limitation': 'Protected temporal readiness separateUNRUN/limited; serialization does not prove identification.'},
    'LA-037': {'implementation': '6beacc8b42dacabff214901919203323f07d1fef', 'check': 'PASS', 'consumer': 'IR.kernel.slots → direct compiler/Foundry facade and same-object legacy alias → actual Trinity/native layout consumers and scoped MkDocs page', 'result': 'Three finaldocs agree on IRowner, one direct facade, same-object compatibility alias, both preserved addresses and explicit finite tracked lifecycle; no two-hop algorithm.', 'oracle_negative': 'Native6PASS/scopedMkDocs5anchors; independent object/import/document review; all3148Python product blobs identical25c/519; no new layout law.', 'limitation': 'Known maintained internal window only; no universal external-caller census or automatic removal of either supported address.'},
}
per_records = []
for path in sorted((LEDGER / 'per-ID').glob('*.json')):
    obj = json.loads(path.read_text())
    fid = obj['finding_id']
    original = subprocess.check_output(['git', 'show', BASE + ':' + str(path.relative_to(ROOT))], cwd=ROOT)
    if fid in affected:
        obj['focused_continuation'] = {'source': source, 'receipt': binding, **descriptions[fid], 'code_ready': True, 'G_new_code_acceptance': 'not_issued', 'G_formal_finding_closure': 'not_issued', 'no_original_criterion_rebinding': True}
        obj['new_property_followups_not_automatically_original_reopen'].append({'lane': 'Graph-profile-and-focused-companions', **binding, 'code_candidate_sha': SOURCE, 'code_candidate_tree': TREE, 'role': 'New property/consumer and companion proof, not new finding ID or G acceptance'})
        obj['next_concrete_result'] = {'B214': 'A/C/F tracked graph-family/identified-conditional-partial output and authority-projection contract with completion-distinguishing query; G affected freeze only after exact owner slices accepted', 'B218': 'G review exact reconciliation boundary; protected temporal readiness requires its separately appointed consumer/input contract', 'LA-037': 'G review finite IR facade lifecycle docs; preserve both import addresses under existing compatibility window'}.get(fid, 'G review exact focused4ee source and affected consumer receipts; composed replay after integration freeze')
        if fid == 'B218':
            obj['status_supersession'] = supersession
        dump(path, obj)
    else:
        assert path.read_bytes() == original, fid
    data = path.read_bytes()
    per_records.append({'finding_id': fid, 'path': str(path.relative_to(ROOT)), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

focused = {'source': source, 'receipt': binding, 'G_dependency_sha': '6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79', 'affected_IDs': affected, 'unchanged_per_ID_bytes': 29, 'actual_checks': {'graph': '62PASS', 'natural_experiment': '3PASS', 'real_configured_worker': '3PASS', 'new_source_wheel': '16PASS +differentPIDreaderPASS', 'property_removal': '2expectednativeFAIL/5positivePASS +1expectedinstalledFAIL'}, 'new_sdist': 'UNRUN', 'G_new_runtime_source_accepted': 0, 'formal_G_closures': 0, 'prior_Lex_accepted_source_preserved': '00a6eda114b903bc5abe86902cd8372426f739a1', 'scope': 'Historical519 whole91/91 consumers retained at their own source; current4ee is focused delta, not rerun/relabelled whole suite'}
for name in ['index.json', 'full-audit.json']:
    path = LEDGER / name
    obj = json.loads(path.read_text())
    obj['focused_continuation'] = focused
    obj['assembled_consumer_status'] += ' New4ee focused graph/native/worker/wheel delta passed; new rebuilt-sdistUNRUN. Historical519 whole-wave readiness is not promoted to a new whole-head package qualification.'
    obj['current_receipt_registry'].append({'lane': 'Graph-profile-and-focused-companions', **binding, 'code_candidate_sha': SOURCE, 'code_candidate_tree': TREE, 'role': 'Exact focused continuation, independent source/installed reviews and lossless complete outputs'})
    obj['B218_status_supersession'] = supersession
    if name == 'index.json':
        for i, row in enumerate(obj['rows']):
            if row['finding_id'] in affected:
                updated = json.loads((LEDGER / 'per-ID' / (row['finding_id'] + '.json')).read_text())
                obj['rows'][i] = {k: updated[k] for k in row}
                obj['rows'][i]['focused_continuation'] = updated['focused_continuation']
                if row['finding_id'] == 'B218': obj['rows'][i]['status_supersession'] = supersession
        obj['per_ID_complete_records'] = per_records
    else:
        obj['rows'] = per_records
    dump(path, obj)

path = LEDGER / 'G-source-integration-order.json'
obj = json.loads(path.read_text())
obj['historical_measured_source519'] = {'sha': obj['source_product_freeze'], 'tree': obj['source_product_tree'], 'existing_entries_unchanged': True}
obj['source_product_freeze'] = SOURCE
obj['source_product_tree'] = TREE
obj['focused_continuation'] = focused
obj['B218_status_supersession'] = supersession
obj['entries'].append({'lane': 'F-root-focused-graph-profile', 'topic': 'codex/e02-F-closeout-20261006', 'published_head_or_product_source': SOURCE, 'tree': TREE, 'true_slice_dependency_base': BASE, 'implementation_commits': [r['sha'] for r in handoff['implementation_commits']], 'complete_diff_footprint_paths': [r['path'] for r in handoff['full_source_footprint']['paths']], 'receipt': binding, 'upstream_history': 'Preserve36b/e1/6be and ordinarymerge parents; cumulative historical carriers are not owner patches', 'checks': focused['actual_checks'], 'remaining': 'New rebuilt-sdistUNRUN; G integratedfreeze after acceptance; B214/B56 ownertriggers separate'})
dump(path, obj)
path = LEDGER / 'G-local-causal-reruns.json'
obj = json.loads(path.read_text())
obj['historical_source519'] = {'sha': obj['source_sha'], 'tree': obj['source_tree']}
obj['source_sha'] = SOURCE
obj['source_tree'] = TREE
obj['focused_receipt'] = binding
for packet in obj['packets']:
    if packet['packet_id'] == 'original-B214-capability':
        packet['owner'] = 'A/C/F canonical graph-family and requested consumer/output contract owners; G only integration/local execution'
        packet['needed'] = ['Tracked graph-family/identified-versus-conditional/partial output and authority-projection contract', 'Query whose effect differs across admissible completions, bounded profile and independent oracle; no arbitrary DAG completion']
        packet['current_result'] += ' New4ee rejects unsupported semantic graph families before cutoff/rewrite/persistence, preserves original MGraph and same-shapeADMG positive; broad contract stilllimited.'
    if packet['packet_id'] == 'original-B56-shared-study':
        packet['needed'].append('Canonical Runtime/Scientist shared admission/cap and full workload/input roster; serial folds retained, no second scheduler/CPU money alias')
        packet['current_result'] += ' This narrow continuation does not commission workload/cap or alter folds. G measures local read-only active/wait/wall/RSS/all-results only after canonical packet.'
dump(path, obj)

report = LEDGER / 'REPORT.md'
text = report.read_text().replace('Exact new product source: `519e', 'Historical measured product source: `519e', 1)
intro = f'Focused continuation after25c: exact product `{SOURCE}` / tree `{TREE}`; separate committed [handoff](../graph-profile-20261007.json) at `{RECEIPT}`. Six rows append evidence (B204/B212/B213/B214/B218/LA-037); other29 per-ID files are byte-identical25c. Original35/36 bindings and all component scientific sources remain unchanged. G checkpoint6e supports33 bounded recommendations; **0 new runtime acceptance /0 formal closures**, with prior Lex00a6 acceptance preserved.\n\nNew affected proof:62native graph PASS,3benchmark PASS,3real Python3.12/DoWhy0.14 worker PASS,16new-wheel PASS and a different-PID CAS reader. Guard removal detects2native/1installed expected behavioral FAIL;5native positive controls remainPASS. New rebuilt-sdist UNRUN. Scored synthetic DATAconfidence0.9 is cutoff fixture only. Previous91/91 wheel/sdist evidence stays bound to519e; no whole-head replay or scientific wave repeated.\n\n'
text = text.replace('Historical measured product source:', intro + 'Historical measured product source:', 1)
captions = {
    'B204': ' Focused4ee companion: honest two-preperiod not_testable;3benchmarkPASS;four-meansATToracle and10retained-report falsifiers. Base-red P41not_established.',
    'B212': ' Focused4ee genuine configuredworker3PASS; controlled post-fit missing-CI accessor negative preserves point/noCI/non-gating; not naturally point-only positive.',
    'B213': ' Focused4ee selected estimand/contrast/defaults and fresh3.14reader test body actually executed3PASS on genuine3.12/DoWhy0.14.',
    'B214': ' Focused36b/4ee canonical graph-family guard refuses scored MGraph/direct/supplied/cache before cutoff; originalMGraph reads, same-formADMG/fresh-child positive. BroadA/C/F contract stayslimited.',
    'B218': ' Explicit supersession: earlier bf335/204426/ROOT072 limited→25c bounded-original closed/PASS for lag/export/staticrefusal. Protectedtemporal readiness remains separateUNRUN/limited.',
    'LA-037': ' Focused6be docs align IRdirectfacade/same-objectalias and finite lifecycle;bothpaths preserved. Native6PASS/scopedMkDocs/independentreview;zeroalgorithm delta.',
}
lines = text.splitlines()
for i, line in enumerate(lines):
    for fid, caption in captions.items():
        if line.startswith('| [' + fid + ']'):
            lines[i] = line[:-2] + caption + ' |'
report.write_text('\n'.join(lines) + '\n')

# Three F-owned prose companions; no other-unit decision section changes.
fpath = ROOT / E02 / 'closure-decisions/F.md'
text = fpath.read_text()
note = f'\n## Focused continuation после25c\n\nSource `{SOURCE}` / tree `{TREE}`, [отдельный handoff](../implementation-handoffs/F/graph-profile-20261007.json) carrier `{RECEIPT}`. Canonical reconciliation проверяет declared DAG/ADMG graph family до cutoff/rewrites/CAS; scored builder MGraph, CPDAG/PAG, lag/unresolved inputs typed-refuse, исходный MGraph остаётся читаемым. Direct/supplied/selected-cache используют один boundary; shared ADMG inference helper не менялся. Actual62graphPASS и16new-wheelPASS плюс different-PIDreader; property-removal2native/1installedFAIL при сохранённых markers и5positivePASS. Это bounded P40 class repair, не general identification support.\n\nB204 companion e1 сохраняет DGP/ATT и честный not_testable при двух preperiods; affected benchmark3/3PASS и независимый ATT/falsifiers. B212/B213 changed test body реально прошёл3selectedchecks на Python3.12/DoWhy0.14 с3.14parent/freshreader; point-only negative контролируемо убирает CI/SE после genuine fit. Optional3.14 markers остаютсяUNRUN, scientific/Runtime authority не выдаётся. LA-037 final3docs6be согласуют IRowner/directfacade/same-objectalias и finite lifecycle; оба import-addresses сохраняются, native6PASS/scopedMkDocs и independentreview не доказывают external zero.\n\n**B218 explicit supersession.** Earlier `bf335dd687c313fda9001fa3bb1365df6bc5ae1f:scm-source-bound-20261006.json#/per_id/4`, `2044260c39dc4988b37d5a1568b65a1cdb1e3d31:graph-intake-native-20261006.json#/per_finding/1` и ROOT072 limited сохраняются исторически; для original lag1/lag2/self-lag persistence/export/static-refusal они superseded текущей bounded F closed/checkPASS at25c. Protected temporal readiness остаётся отдельноUNRUN/limited; serialization не identification. Это не G formal closure.\n\nВсе35/36 bindings сохранены; только6per-ID append, остальные29byte-identical. B214 broad A/C/F family/conditional/partial output contract и completion-distinguishing query остаётся trigger; B56 canonical Runtime/Scientist shared admission/cap +full workload roster нужен для G local measurement, folds/scheduler не меняются. G6e поддерживает33 bounded recommendations, новая source acceptance/formal closures не выданы; prior Lex00a6 accepted source сохраняется. Historical scanner2×ERROR−9/Ruff103FAIL/publicsurface38FAIL/P41not_established не исчезают. New graph4fileRuff/5fileformatPASS; benchmarkRuff2T201FAIL, P41not_established. New rebuilt-sdistUNRUN, prior51991/91 qualification не переименована в4ee whole-headPASS.\n'
fpath.write_text(text + note)
mpath = ROOT / E02 / 'closure-decisions/method-decisions.md'
text = mpath.read_text()
for next_anchor, note in [
    ('<a id="f-m4"></a>', '**Focused after25c / B204.** Companione1 changes only clean_rollout checker:2preperiods require passedFalse/statistic/pNone/not_testable/insufficient_pre_periods/identification_authorityFalse; ATT2/seed11 unchanged. Exact4ee affected benchmark3PASS; independent four-meansATT and10retained-report falsifiers passed. Base-red is retained, P41not_established.\n\n'),
    ('<a id="f-m8"></a>', '**Focused after25c / B212/B213.** Exact4ee changed `test_dowhy_worker.py` selected3tests actuallyPASS on configured Python3.12.14/DoWhy0.14 with3.14.7parent, realselected defaults/estimand/contrast/CAS/freshreader. Point-only negative executes genuine estimate then test-controlled CI/SE accessors returnNone; no mockfit or naturally-point-only claim. Optionalinprocess3.14/wholeNode/identification admissionUNRUN.\n\n'),
    ('<a id="f-m10"></a>', '**Focused after25c / B214/B218.** Canonical reconciliation36b admits only declared DAG/ADMG beforeconfidence/rewrite/persistence, includingdirect/supplied/selectedcache anddefensiveCompose; ordinaryFragmentCompositionData already guards unsupportedtype. ActualscoredMGraph extractor discriminator/refusal/noCASpublication, retainedoriginal andsame-formADMGfreshchild positive;62native/16wheelPASS and2native/1installedguard-removalFAIL. SharedADMGhelper/otherIDconsumers unchanged. Broad B214 A/C/F completion semantics/output contract remainslimited. **B218 supersession:** historicalbf335#/per_id/4,204426#/per_finding/1 andROOT072limited are explicitly superseded only for original lag1/lag2/self-lag export/staticrefusal by25c boundedclosed/PASS. Protectedtemporal readinessUNRUN/limited, serialization≠identification, noGclosure.\n\n'),
    ('<a id="f-m13"></a>', '**Focused after25c / LA-037.** Docs6be final3pages agree on nativeIRowner, directFoundryfacade, same-objectlegacyalias andfinite tracked lifecycle;bothimportaddresses retained. Native6PASS/scopedMkDocs5anchors/independentreview, no product/layout algorithmdelta. Unknownexternalcensus is not a prerequisite for bounded original no-two-hop migration.\n\n'),
]:
    assert next_anchor in text
    text = text.replace(next_anchor, note + next_anchor, 1)
text += f'\nF focused-after25c deciding outputs: `graph-profile-20261007.json@{RECEIPT}`, exact source `{SOURCE}` / tree `{TREE}`. New wheel16/worker3/benchmark3/graph62 are separate finite denominators; no new sdist or global scanner/authority PASS. Historicalquality/P41 and B214/B56 triggers remain as documented in F ledger.\n'
mpath.write_text(text)
rpath = ROOT / E02 / 'closure-decisions/runtime-profiles.md'
rpath.write_text(rpath.read_text() + f'\n## F focused after25c runtime delta\n\nExact source `{SOURCE}`, tree `{TREE}`; [committed source-bound receipt](../implementation-handoffs/F/graph-profile-20261007.json) at `{RECEIPT}`. Native3.14.7 graph62PASS, natural-experiment3PASS and selected genuineworker3PASS; worker3.12.14/DoWhy0.14/NumPy2.4.6/SciPy1.15.3/statsmodels0.15.0 was actually configured/run. Controlled post-estimate CI/SE absence verifies point-only handling; optionalinprocess3.14 DoWhy/EconML remainsUNRUN. No actual institutional/scientific authority implied.\n\nNew source-wheel16PASS plus registeredMethodJob/Node/selectedCAS/different-PID-IreaderPASS; all3464source/wheel/site files and11resource bytes/origins guarded. Native semanticguard removal2FAIL/5positivePASS andinstalled1FAIL are expected controls. Newrebuilt-sdistUNRUN; historical51991wheel/91sdist checks stay at519. Reconciliation only admits declared DAG/ADMG beforeconfidence; MGraph/PAG/CPDAG/compactlag/unresolvedmarks typed-refuse, partialgraphs outside this staticboundary retain their original semantics. Shared inferencehelper unchanged.\n\nB218 original lag/export/static-refusal earlierlimited is explicitly superseded by boundedclosed/PASS (bf335/204426/ROOT072→25c); protectedtemporal readiness remains separateUNRUN/limited. LA-037 docs6be: nativeIRowner/directfacade/sameobjectalias with bothaddresses retained; no algorithm delta. B214 A/C/F contract trigger andB56 canonical sharedadmission/workload packet/localmeasurement remainlimited. Preserve scannerERROR−9twice, Ruff103FAIL, publicsurface38FAIL/P41not_established; newbenchmarkRuff2T201FAIL is not proveninherited. NoCPU/process/worker/threadquota or new scheduler introduced.\n')

# Exact denominator and unchanged-byte assertion; no estimator execution.
idx = json.loads((LEDGER / 'index.json').read_text())
assert len(idx['rows']) == len({r['finding_id'] for r in idx['rows']}) == 35
assert len({r['primary_bundle'] for r in idx['rows']}) == 17
unchanged = []
for r in idx['rows']:
    p = LEDGER / 'per-ID' / (r['finding_id'] + '.json')
    if r['finding_id'] not in affected:
        assert p.read_bytes() == subprocess.check_output(['git', 'show', BASE + ':' + str(p.relative_to(ROOT))], cwd=ROOT)
        unchanged.append(r['finding_id'])
assert len(unchanged) == 29
print(json.dumps({'ledger': 'updated', 'IDs': 35, 'bundles': 17, 'affected': affected, 'unchanged_bytes': 29, 'receipt': RECEIPT}))
