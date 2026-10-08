"""Bind original B218 supersession and the narrow source/quality review requirements."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/workspace/e02-F-economics-20261006')
OUT = Path(__file__).parent
F = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
GRAPH = '36b18cc142aff77a5825126b4f07bafec09a5180'
G = '6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79'
BASE = 'policy-engine/docs/research/e02-cloud-test-plan/'
P = BASE + 'implementation-handoffs/F/continuation-transfer-20261007/'

def get(ref, path):
    b = subprocess.check_output(['git', 'show', ref + ':' + path], cwd=ROOT)
    return b, {'git_ref': ref, 'path': path, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}

def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

per_b, per_ref = get(F, P + 'per-ID/B218.json')
per = json.loads(per_b)
historical = []
for ref in per['deciding_receipt_refs']:
    if 'json_pointer' not in ref:
        continue
    b, source = get(ref['git_ref'], ref['path'])
    assert len(b) == ref['bytes'] and hashlib.sha256(b).hexdigest() == ref['sha256']
    value = json.loads(b)
    for k in ref['json_pointer'].strip('/').split('/'):
        value = value[int(k)] if isinstance(value, list) else value[k]
    assert value['finding_id'] == 'B218' and value['outcome'] == 'limited'
    historical.append({'receipt': source, 'json_pointer': ref['json_pointer'], 'literal_row': value})
dump('B218-supersession-requirement.json', {
    'current_bound_original_decision': per_ref,
    'current_original_card_refs': per['original_card_refs'],
    'historical_limited_rows': historical,
    'required_current_supersession': {
        'recommendation': 'closed in original finite compact-temporal export/static-consumer criterion',
        'basis': 'Lag1/lag2/self-lag serialization and expanded finite sanity, static consumer typed '
                 'refusal, unchanged static DAG path; original criterion does not demand universal temporal ID.',
        'explicitly_supersedes': [h['receipt'] | {'json_pointer': h['json_pointer']} for h in historical],
        'preserve_historical_literals': True,
        'retained_limits': 'Temporal protected-readiness/full identification route remains UNRUN and separate '
                           'from the original bounded criterion; no new numerical replay.'
    }})

g_native_path = BASE + 'integration/reviews/2026-10-07-F35-decision/native-MGraph/'
native = {}
for name in ['receipt.json', 'deciding.stdout.txt']:
    b, ref = get(G, g_native_path + name)
    (OUT / ('G-native-MGraph-' + name)).write_bytes(b)
    native[name] = ref

paths = subprocess.check_output(['git', 'diff', '--name-only', F, GRAPH], cwd=ROOT).decode().splitlines()
assert len(paths) == 6
diff = subprocess.check_output(['git', 'diff', '--binary', F, GRAPH], cwd=ROOT)
(OUT / 'graph36-full.patch').write_bytes(diff)
source_refs = []
for p in paths:
    b, ref = get(GRAPH, p)
    ref['git_blob'] = subprocess.check_output(['git', 'rev-parse', GRAPH + ':' + p], cwd=ROOT).decode().strip()
    source_refs.append(ref)

previous = []
for name in ['root-quality-review/review.json', 'recovery-review-20261007/retry-review-delta.json',
             'recovery-review-20261007/source-review.json']:
    path = BASE + 'implementation-handoffs/F/continuation-closeout-20261007/companions/economics/' + name
    _, ref = get(F, path)
    previous.append(ref)

dump('source-and-quality-requirements.json', {
    'schema': 'e02.F.independent.narrow_source_criterion_review.v1',
    'reviewer_role': 'Independent read-only source/criterion/quality reviewer; no author, G or root mutations',
    'G_review': G, 'baseline_F': F, 'graph_candidate': GRAPH,
    'graph_candidate_tree': subprocess.check_output(['git', 'rev-parse', GRAPH + '^{tree}'], cwd=ROOT).decode().strip(),
    'graph36_source_review': 'GO_BOUNDED_SOURCE_ONLY',
    'graph36_changed_paths': source_refs,
    'graph36_full_diff': {'path': 'graph36-full.patch', 'bytes': len(diff), 'sha256': hashlib.sha256(diff).hexdigest()},
    'new_property': 'Declared static DAG/ADMG family admission is checked before confidence filtering, '
                    'merge/cycle rewriting and reconciled-graph persistence, not inferred from visible marks.',
    'same_class_denominator': [
        'ReconcileCausalGraph.pure_step current data graph',
        'ComposeSCMFragments.pure_step each fragment graph, including typed model_copy bypass',
        'Scientist _resolve_graph_ref selected cache and fragment source refs',
        'Scientist query-only composed-graph replay',
        'Scientist final reconciled graph validation before CAS persistence'],
    'preserved_positive_profiles': [
        'Ordinary declared DAG producer → Node → fresh CAS reader',
        'Declared ADMG directed/bidirected relations including parallel pair',
        'Reverse-stored known arrow in actual ADMG DTO',
        'Original fully-known reverse PAG projection remains unchanged in its separate owner',
        'MGraph original artifact and missingness extractor remain readable after reconciliation refusal'],
    'required_native_evidence_after_candidate': [
        'Scored actual build_mgraph before and after canonical admission, no new reconciled artifact',
        'CPDAG/PAG/MGraph fully-oriented and empty forms refuse before filtering, direct/method/CAS/cache',
        'Canonical producer and actual selected Node/CAS paths, not DTO-only reflection',
        'A retained-marker admission removal causes the real numeric/semantic discriminator to fail',
        'Declared DAG/ADMG positives and composition/temporal static-refusal contracts stay supported'],
    'native_execution_by_this_reviewer': 'NOT_RUN; code/claims only, independent author/other reviewer receipts separate',
    'G_native_pre_fix': native,
    'B204_followup': 'Repair only maintained benchmark pretrend fixture/expectation; leave insufficient-pre '
                    'not_testable, zero-pre rejection and method numerical law unchanged. Qualify fresh exact selector '
                    'and preserve historical2PASS1FAIL without inherited/P41 claim.',
    'B212_B213_followup': 'Focused actual changed test_dowhy_worker.py qualification in configured genuine3.12 '
                         'DoWhy backend profile. Do not turn excluded in-process3.14 markers into a backend witness; '
                         'no blanket backend repeat or shim.',
    'LA037_docs_followup': 'IR.kernel.slots is sole owner; primary Foundry facade and compiler compatibility '
                          'alias are explicit direct identical bindings, not two algorithm hops. Align current state '
                          'reference/autodoc and finite lifecycle classification without deleting supported paths.',
    'LA035_carry': 'Original equivalent GlobalState formula relocation remains closed. Future changed objective '
                   'ranking/optimizer intent needs an independent version/decision, not reopening this original ID.',
    'B214_broad_limit': {
        'F_outcome': 'limited', 'formal_G': 'not_issued',
        'trigger': 'Tracked canonical C identification/graph-family/query decision with A projection contract '
                   'and exact finite supported partial/conditional capability discriminator; genuine completions '
                   'with different answers remain conditional or refuse, no arbitrary extension.',
        'narrow_fix_not_broad_closure': True},
    'B56_limit': {
        'F_outcome': 'limited', 'check': 'UNRUN', 'formal_G': 'not_issued',
        'trigger': 'Actual shared Runtime/Scientist admission unit/cap on exact source/tree and runnable profile; '
                   'full simultaneous-job/model/fold/repeat/seed/input roster, peak active/wait/wall/RSS and '
                   'complete no-loss result/provenance/CAS comparison. Test-created pool is not canonical budget.',
        'no_new_TMLEScheduler': True},
    'status_separation': {
        'F_original_closed': 33, 'F_original_limited': 2, 'code_ready': 'source/profile qualified independently',
        'G_new_runtime_source_acceptance': 0, 'G_formal_findings_closed': 0,
        'historical_Lex_source_acceptance_preserved': '00a6eda114b903bc5abe86902cd8372426f739a1',
        'G_bounded_supported_criteria': 33},
    'global_quality_preserved': {'source519_scanner': 'ERROR/-9 twice; no fullJSON, no repeat',
                                'Ruff': 'FAIL103', 'public_surface': 'FAIL38',
                                'P41': 'not_established; overlap, no inherited label',
                                'old_b5_completed_scanner': 'FAIL/UNRESOLVED partial5954, not PASS',
                                'format19': 'PASS exact519', 'five_fragments': 'PASS exact519',
                                'new_graph_profile_full_source_quality': 'not inferred from old519 scoped checks'},
    'prior_reviews_by_ref_no_171MB_reparse': previous,
    'review_scope_limit': 'Proposed current ledger update requirements; final frozen ledger not yet received. '
                          'No production/identification/legal authority, institutional adoption or installed-assembled '
                          'readiness is inferred from source-only review.'
})
print(json.dumps({'graph_source': 'GO_BOUNDED_SOURCE_ONLY', 'source_paths': len(source_refs),
                  'B218_historical_limited_rows': len(historical), 'original35': '33closed2limited'}))
