"""Read-only independent finite ledger/protocol/transport adjudication."""
from collections import Counter
from copy import deepcopy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/e02-F-economics-20261006')
OUT = Path(__file__).parent / 'ledger3d'
OUT.mkdir(exist_ok=True)
BASE = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
LEDGER = '3d43eb459eec1f346571306647e5dbc68f32f076'
CARRIER = '248497d27aa7951492c9a6d12c3c3493f3c246ec'
SOURCE = '4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
P = 'policy-engine/docs/research/e02-cloud-test-plan/'
TR = P + 'implementation-handoffs/F/continuation-transfer-20261007/'
RECEIPT = P + 'implementation-handoffs/F/graph-profile-20261007.json'
MANIFEST = P + 'implementation-handoffs/F/graph-profile-20261007/artifact-transports.json'
COMMANDS = []

def sha(b):
    return hashlib.sha256(b).hexdigest()

def git(*args, check=True):
    p = subprocess.run(['git', *args], cwd=ROOT, capture_output=True)
    COMMANDS.append({'argv': ['git', *args], 'exit_code': p.returncode,
                     'stdout_bytes': len(p.stdout), 'stdout_sha256': sha(p.stdout),
                     'stderr_bytes': len(p.stderr), 'stderr_sha256': sha(p.stderr)})
    if check and p.returncode:
        raise ValueError(p.stderr.decode())
    return p

def read(ref, path):
    return git('show', ref + ':' + path).stdout

def dump(name, d):
    (OUT / name).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

def ref(ref, path):
    b = read(ref, path)
    return {'git_ref': ref, 'path': path, 'bytes': len(b), 'sha256': sha(b),
            'git_blob': git('rev-parse', ref + ':' + path).stdout.decode().strip()}

receipt_bytes = read(CARRIER, RECEIPT)
receipt = json.loads(receipt_bytes)
manifest_bytes = read(CARRIER, MANIFEST)
manifest = json.loads(manifest_bytes)
assert sha(manifest_bytes) == receipt['evidence_transport']['sha256']
assert len(manifest_bytes) == receipt['evidence_transport']['bytes']
assert len(manifest['files']) == manifest['file_count'] == 513
assert receipt['candidate']['sha'] == SOURCE
assert receipt['candidate']['tree'] == git('rev-parse', SOURCE + '^{tree}').stdout.decode().strip()
assert git('merge-base', '--is-ancestor', SOURCE, LEDGER, check=False).returncode == 0
assert git('merge-base', '--is-ancestor', CARRIER, LEDGER, check=False).returncode == 0
assert receipt['slice_base']['sha'] == BASE
assert git('rev-parse', LEDGER + '^{tree}').stdout.decode().strip() == '18a07f2d4de206cdd7c0b85532b2201d8ae279e8'

affected = {'B204', 'B212', 'B213', 'B214', 'B218', 'LA-037'}
idx = json.loads(read(LEDGER, TR + 'index.json'))
audit = json.loads(read(LEDGER, TR + 'full-audit.json'))
old_idx = json.loads(read(BASE, TR + 'index.json'))
ids = {r['finding_id'] for r in old_idx['rows']}
assert len(ids) == 35
tsv = read(BASE, P + 'execution-organization/finding-owners.tsv')
owners = {r['finding_id']: r for r in csv.DictReader(io.StringIO(tsv.decode()), delimiter='\t')
          if r['unit'] == 'F'}
assert set(owners) == ids == {r['finding_id'] for r in idx['rows']}
index_binding = {r['finding_id']: r for r in idx['per_ID_complete_records']}
audit_binding = {r['finding_id']: r for r in audit['rows']}
index_rows = {r['finding_id']: r for r in idx['rows']}
rows, perids, old_perids = [], {}, {}
bindings, unique_blocks = [], set()
for ident in sorted(ids):
    p = TR + 'per-ID/' + ident + '.json'
    b, old = read(LEDGER, p), read(BASE, p)
    new, historical = json.loads(b), json.loads(old)
    perids[ident], old_perids[ident] = new, historical
    assert new['primary_owner_from_full_TSV'] == owners[ident]
    assert new['original_card_refs'] == historical['original_card_refs']
    assert new['original_text'] == historical['original_text']
    assert all(new[k] == historical[k] for k in ['scientific_implementation', 'code_sha', 'code_tree',
             'check_result', 'F_finding_outcome', 'F_technical_recommendation', 'G_finding_acceptance',
             'G_code_acceptance', 'deciding_per_ID_carrier_ref', 'historical_ROOT072'])
    assert all(new[k] == v for k, v in index_rows[ident].items())
    for declared in [index_binding[ident], audit_binding[ident]]:
        assert declared['path'] == p and declared['bytes'] == len(b) and declared['sha256'] == sha(b)
    if ident not in affected:
        assert b == old
    else:
        assert b != old
        focus = new['focused_continuation']
        assert focus['source']['sha'] == SOURCE
        assert focus['source']['tree'] == receipt['candidate']['tree']
        assert focus['check'] == 'PASS' and focus['G_new_code_acceptance'] == 'not_issued'
        assert focus['G_formal_finding_closure'] == 'not_issued'
        z = focus['receipt']
        actual = read(z['git_ref'], z['path'])
        assert actual == receipt_bytes and len(actual) == z['bytes'] and sha(actual) == z['sha256']
    for card in new['original_card_refs']:
        source = read(card['source_sha'], card['source_path'])
        a, z = card['lines']
        block = b''.join(source.splitlines(keepends=True)[a - 1:z])
        assert len(block) == card['bytes'] and sha(block) == card['sha256']
        bindings.append(card)
        unique_blocks.add((card['source_sha'], card['source_path'], tuple(card['lines']), card['sha256']))
    rows.append({'finding_id': ident, 'changed': b != old, 'old_bytes': len(old), 'old_sha256': sha(old),
                 'bytes': len(b), 'sha256': sha(b), 'F_outcome': new['F_finding_outcome'],
                 'check_result': new['check_result'], 'G_code_acceptance': new['G_code_acceptance'],
                 'G_finding_acceptance': new['G_finding_acceptance']})
assert len(bindings) == 36 and len(unique_blocks) == 35
assert Counter(r['F_outcome'] for r in rows) == {'closed': 33, 'limited': 2}
assert Counter(r['check_result'] for r in rows) == {'PASS': 34, 'UNRUN': 1}
assert perids['LA-017']['G_code_acceptance']['source_sha'] == '00a6eda114b903bc5abe86902cd8372426f739a1'
assert perids['LA-017']['G_code_acceptance']['status'] == 'accepted_source'
assert perids['LA-035'] == old_perids['LA-035']
assert perids['B56'] == old_perids['B56']
assert receipt['affected_IDs'] == ['B204', 'B212', 'B213', 'B214', 'B218', 'LA-037']
assert receipt['unchanged_ID_count'] == 29

sup = perids['B218']['status_supersession']
old_sup_rows = []
for z in sup['from']['refs']:
    b = read(z['git_ref'], z['path'])
    assert len(b) == z['bytes'] and sha(b) == z['sha256']
    v = json.loads(b)
    if 'json_pointer' in z:
        for k in z['json_pointer'].strip('/').split('/'):
            v = v[int(k)] if isinstance(v, list) else v[k]
        assert v['finding_id'] == 'B218' and v['outcome'] == 'limited'
    else:
        if 'complete_original_bound_row' in v:
            v = v['complete_original_bound_row']
        assert v['finding_id'] == 'B218'
        assert v.get('F_finding_outcome', v.get('outcome')) == 'limited'
    old_sup_rows.append({'ref': z, 'actual_historical_row': v})
assert len(old_sup_rows) == 3
assert sup['separate_capability'] == {'protected_temporal_readiness': 'UNRUN', 'outcome': 'limited',
                                    'serialization_is_identification': False}
z = sup['to']['already_recorded_at']
b = read(z['git_ref'], z['path'])
assert len(b) == z['bytes'] and sha(b) == z['sha256']
assert json.loads(b)['F_finding_outcome'] == 'closed'

# One immutable Git batch contains the complete modest transport denominator.
proc = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT,
        input=b''.join((CARRIER + ':' + f['path'] + '\n').encode() for f in manifest['files']), capture_output=True)
assert proc.returncode == 0
cursor = 0
blobs = {}
transport_rows = []
for entry in manifest['files']:
    end = proc.stdout.index(b'\n', cursor)
    header = proc.stdout[cursor:end].decode().split()
    assert header[1] == 'blob'
    size = int(header[2]); start = end + 1
    stored = proc.stdout[start:start + size]; cursor = start + size + 1
    assert proc.stdout[cursor - 1:cursor] == b'\n'
    decoded = gzip.decompress(stored) if entry['encoding'] == 'gzip' else stored
    assert entry['encoding'] in {'gzip', 'identity'}
    assert len(stored) == entry['stored_bytes'] and sha(stored) == entry['stored_sha256']
    assert len(decoded) == entry['decoded_bytes'] and sha(decoded) == entry['decoded_sha256']
    # The actual canonical row, rather than only a summary, is kept for reuse.
    blobs[entry['path']] = (stored, decoded)
    transport_rows.append({**entry, 'actual_git_blob': header[0], 'stored_check': 'PASS', 'decoded_check': 'PASS'})
assert cursor == len(proc.stdout)
assert sum(r['stored_bytes'] for r in transport_rows) == manifest['stored_bytes'] == 2539936
assert sum(r['decoded_bytes'] for r in transport_rows) == manifest['decoded_bytes'] == 5633677

def check_transport(entry):
    stored, decoded = blobs[entry['path']]
    assert len(stored) == entry['stored_bytes'] and sha(stored) == entry['stored_sha256']
    assert len(decoded) == entry['decoded_bytes'] and sha(decoded) == entry['decoded_sha256']

def validate_state(state):
    assert len(state) == 35
    assert state['B214']['F_finding_outcome'] == state['B56']['F_finding_outcome'] == 'limited'
    assert state['B56']['check_result'] == 'UNRUN'
    assert state['LA-017']['G_code_acceptance']['status'] == 'accepted_source'
    assert state['LA-017']['G_code_acceptance']['source_sha'] == '00a6eda114b903bc5abe86902cd8372426f739a1'
    assert all(not v['G_finding_acceptance']['formal_G_closed'] for v in state.values())
    for ident, v in state.items():
        assert v['original_card_refs'] == old_perids[ident]['original_card_refs']

controls = []
def rejects(name, mutate, check):
    try:
        check(mutate())
    except (AssertionError, ValueError, KeyError):
        controls.append({'name': name, 'result': 'REJECTED', 'kind': 'finite metadata corruption; no estimator run'})
    else:
        raise AssertionError('Accepted metadata corruption: ' + name)

bad = deepcopy(manifest['files'][0]); bad['stored_sha256'] = '0' * 64
rejects('wrong stored SHA with actual untouched Git bytes', lambda: bad, check_transport)
bad = deepcopy(next(f for f in manifest['files'] if f['encoding'] == 'gzip')); bad['decoded_sha256'] = '0' * 64
rejects('wrong decoded SHA with valid stored gzip', lambda: bad, check_transport)
bad_state = deepcopy(perids); bad_state['LA-016']['original_card_refs'].pop()
rejects('drop duplicate LA016 coverage binding without dropping ID', lambda: bad_state, validate_state)
bad_state = deepcopy(perids); bad_state['B214']['F_finding_outcome'] = 'closed'
rejects('promote broad B214 from narrow property', lambda: bad_state, validate_state)
bad_state = deepcopy(perids); bad_state['B56']['check_result'] = 'PASS'
rejects('promote deferred shared-admission B56', lambda: bad_state, validate_state)
bad_state = deepcopy(perids); bad_state['LA-017']['G_code_acceptance']['status'] = 'not_inferred'
rejects('erase historical Lex accepted source while declaring0new', lambda: bad_state, validate_state)
bad_state = deepcopy(perids); bad_state['B218']['G_finding_acceptance']['formal_G_closed'] = True
rejects('promote F B218 supersession to G formal closure', lambda: bad_state, validate_state)

check_outputs = []
for n, check in enumerate(receipt['checks']):
    for key in ['output_ref', 'execution', 'fresh_reader']:
        if not isinstance(check.get(key), dict):
            continue
        b = check[key]; assert b['path'] in blobs
        stored, decoded = blobs[b['path']]
        assert b['stored_bytes'] == len(stored) and b['stored_sha256'] == sha(stored)
        assert b['decoded_bytes'] == len(decoded) and b['decoded_sha256'] == sha(decoded)
        row = {'check': n, 'name': check['name'], 'field': key, 'binding': b}
        if b['path'].endswith('.xml'):
            tree = ET.fromstring(decoded)
            cases = list(tree.iter('testcase'))
            failures = sum(bool(list(c.iter('failure'))) for c in cases)
            errors = sum(bool(list(c.iter('error'))) for c in cases)
            skips = sum(bool(list(c.iter('skipped'))) for c in cases)
            row['actual_cases'] = len(cases); row['actual_passed'] = len(cases) - failures - errors - skips
            row['actual_failures'] = failures; row['actual_errors'] = errors; row['actual_skipped'] = skips
            if 'passed' in check: assert row['actual_passed'] == check['passed']
            if 'behavioral_failures' in check: assert failures == check['behavioral_failures']
        check_outputs.append(row)

# Preserve the complete actual diagnostic streams; classify exact raw paths.
quality = []
for name, args in [
    ('authored14-diff-check', ('diff', '--check', LEDGER + '^', LEDGER)),
    ('source10-diff-check', ('diff', '--check', BASE, SOURCE)),
    ('allraw-ledger-diff-check', ('diff', '--check', BASE, LEDGER)),
]:
    p = git(*args, check=False)
    (OUT / (name + '.stdout.txt')).write_bytes(p.stdout)
    (OUT / (name + '.stderr.txt')).write_bytes(p.stderr)
    lines = p.stdout.decode().splitlines()
    locations = [line for line in lines if re.match(r'^.+:\d+: (?:trailing whitespace|new blank line at EOF)', line)]
    paths = sorted({line.rsplit(':', 2)[0] for line in locations})
    quality.append({'name': name, 'argv': ['git', *args], 'exit_code': p.returncode,
                    'diagnostic_location_count': len(locations), 'paths': paths,
                    'output_sha256': sha(p.stdout), 'output_bytes': len(p.stdout),
                    'raw_flagged_paths_present_in_transport': all(path in blobs for path in paths)})
assert quality[0]['exit_code'] == quality[1]['exit_code'] == 0
assert quality[2]['exit_code'] != 0
assert quality[2]['raw_flagged_paths_present_in_transport']

mandatory = ['schema', 'unit', 'slice', 'closure_ids', 'bundle_ids', 'slice_base_sha',
             'implementation_commits', 'candidate_tree_sha', 'branch', 'pull_request', 'changed_paths',
             'baseline_cells', 'checks', 'property', 'predicate_basis', 'capability_state_or_finding_state',
             'limitations_and_next_owner']
check_mandatory = ['command', 'target_sha', 'environment', 'input_closure', 'outcome', 'output']
property_mandatory = ['statement', 'runtime_path', 'proxy_divergence', 'negative_controls']
protocol = {'required_by': P + 'execution-prompts/HANDOFF.md:38',
            'schema': receipt['schema'], 'canonical_schema_match': receipt['schema'] == 'policyos.e02.implementation_handoff.v1',
            'missing_minimum_fields': [k for k in mandatory if k not in receipt],
            'checks': [{'index': n, 'missing': [k for k in check_mandatory if k not in check],
                        'output_is_string': isinstance(check.get('output'), str)}
                       for n, check in enumerate(receipt['checks'])],
            'property_missing': [k for k in property_mandatory if k not in receipt['property']],
            'verdict': 'PENDING'}
protocol['verdict'] = 'GO_CANONICAL_PROTOCOL' if (protocol['canonical_schema_match'] and not protocol['missing_minimum_fields'] and not protocol['property_missing'] and all(not c['missing'] and c['output_is_string'] for c in protocol['checks'])) else 'BLOCK_CANONICAL_PROTOCOL'
assert protocol['verdict'] == 'GO_CANONICAL_PROTOCOL'

ledger_paths = git('diff', '--name-only', LEDGER + '^', LEDGER).stdout.decode().splitlines()
assert len(ledger_paths) == 14
full_diff = git('diff', '--binary', LEDGER + '^', LEDGER).stdout
(OUT / 'full14-ledger.patch').write_bytes(full_diff)
source_diff = git('diff', '--binary', BASE, SOURCE).stdout
(OUT / 'full10-source.patch').write_bytes(source_diff)
dump('complete-transport-audit.json', {'manifest_ref': ref(CARRIER, MANIFEST),
     'files': transport_rows, 'file_count': len(transport_rows), 'stored_bytes': manifest['stored_bytes'],
     'decoded_bytes': manifest['decoded_bytes'], 'check_output_bindings': check_outputs})
dump('current35-actual-binding-audit.json', {'result': 'PASS', 'source': LEDGER, 'source_tree':
     '18a07f2d4de206cdd7c0b85532b2201d8ae279e8', 'affected6': sorted(affected),
     'unchanged29_whole_bytes': True, 'IDs': 35, 'original_bindings': 36, 'distinct_blocks': 35,
     'bundles': 17, 'rows': rows, 'counts': {'closed': 33, 'limited': 2, 'PASS': 34, 'UNRUN': 1},
     'B218_actual_superseded_limited_rows': old_sup_rows,
     'B218_supersession': sup, 'finite_metadata_controls': controls})
dump('canonical-protocol-audit.json', protocol)
dump('quality-actual-classification.json', quality)
dump('commands.json', COMMANDS)
dump('review.json', {'schema': 'e02.F.independent_frozen_ledger_review.v1',
     'source': LEDGER, 'source_tree': '18a07f2d4de206cdd7c0b85532b2201d8ae279e8',
     'base': BASE, 'product_source': SOURCE, 'receipt': ref(CARRIER, RECEIPT),
     'verdict': 'GO_BOUNDED_CANONICAL_LEDGER_AND_TRANSPORT',
     'counts_and_unchanged_bindings': 'PASS35IDs/36bindings/35unique/17bundles/6appended29wholebytecarry',
     'statuses': '33closed2limited/34PASS1UNRUN;0NEW_Gruntime_source/0formal;priorLex00a6accepted preserved',
     'global_quality': 'Old519 scannerERROR-9twice, RuffFAIL103/surfaceFAIL38/P41not_established retained; '
                       'new fullscannerUNRUN, benchmarkRuff2T201FAIL; old51991+91 not new4ee qualification',
     'transport': 'PASS513complete actual Git stored and decoded bytes; all deciding outputs present',
     'B218': 'PASS explicit3historical supersession refs, actual limited values preserved; temporalUNRUN separate',
     'B212': 'Actual controlled post-fit missingCI/SE negative correctly qualified; not naturalpoint-only witness',
     'LA035': 'Entire perID unchanged and original equivalent relocation closed; no optimizer prerequisite',
     'no_independent_product_source_review_claim': True, 'no_numerical_runs': True,
     'protocol_verification': protocol, 'metadata_corruption_controls': controls,
     'outputs': ['current35-actual-binding-audit.json', 'complete-transport-audit.json',
                 'canonical-protocol-audit.json', 'quality-actual-classification.json', 'full14-ledger.patch'],
     'historical_requirement_review': '../review.json'})
print(json.dumps({'ledger_verdict': 'GO_BOUNDED', 'protocol': protocol['verdict'], 'IDs': 35, 'bindings': 36,
                  'unchanged': 29, 'transport_files': 513, 'metadata_controls_rejected': len(controls),
                  'quality': quality, 'protocol_detail': protocol}, ensure_ascii=False, indent=2))
