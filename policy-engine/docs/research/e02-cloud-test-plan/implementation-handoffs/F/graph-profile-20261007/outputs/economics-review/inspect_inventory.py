"""Read-only exact original-card/current35 custody and proposed delta locators."""
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

ROOT = Path('/workspace/e02-F-economics-20261006')
OUT = Path(__file__).parent
F = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
G = '6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79'
BASE = 'policy-engine/docs/research/e02-cloud-test-plan/'
TRANSFER = BASE + 'implementation-handoffs/F/continuation-transfer-20261007/'
GP = BASE + 'integration/reviews/2026-10-07-F35-decision/'
COMMANDS = []

def git(*args):
    p = subprocess.run(['git', *args], cwd=ROOT, capture_output=True)
    COMMANDS.append({'argv': ['git', *args], 'exit_code': p.returncode,
                     'stdout_bytes': len(p.stdout), 'stdout_sha256': sha(p.stdout),
                     'stderr': p.stderr.decode()})
    if p.returncode:
        raise RuntimeError(p.stderr.decode())
    return p.stdout

def sha(b):
    return hashlib.sha256(b).hexdigest()

def binding(ref, path):
    b = git('show', f'{ref}:{path}')
    return b, {'git_ref': ref, 'path': path, 'bytes': len(b), 'sha256': sha(b),
               'git_blob': git('rev-parse', f'{ref}:{path}').decode().strip()}

def dump(name, d):
    (OUT / name).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

papers = {}
for name in ['README.md', 'all-35.md', 'B214.md', 'B56.md', 'final-semantic-review.md',
             'estimators.md', 'GCM.md', 'migrations.md', 'decisions.json']:
    b, ref = binding(G, GP + name)
    (OUT / ('G-' + name)).write_bytes(b)
    papers[name] = ref
decision = json.loads((OUT / 'G-decisions.json').read_bytes())
idx_bytes, idx_ref = binding(F, TRANSFER + 'index.json')
audit_bytes, audit_ref = binding(F, TRANSFER + 'full-audit.json')
index, audit = json.loads(idx_bytes), json.loads(audit_bytes)
tsv_bytes, tsv_ref = binding(F, BASE + 'execution-organization/finding-owners.tsv')
owners = list(csv.DictReader(io.StringIO(tsv_bytes.decode()), delimiter='\t'))
f_owners = {r['finding_id']: r for r in owners if r['unit'] == 'F'}
g_rows = {r['finding_id']: r for r in decision['rows']}
idx_rows = {r['finding_id']: r for r in index['rows']}
audit_rows = {r['finding_id']: r for r in audit['rows']}
assert len(f_owners) == len(g_rows) == len(idx_rows) == len(audit_rows) == 35
assert set(f_owners) == set(g_rows) == set(idx_rows) == set(audit_rows)

affected = {'B204', 'B212', 'B213', 'B214', 'B218', 'LA-037'}
records = []
card_rows = []
blocks = {}
per_bindings = {r['finding_id']: r for r in index['per_ID_complete_records']}
all_original_bindings = []
locators = []
for i, row in enumerate(index['rows']):
    ident = row['finding_id']
    payload, ref = binding(F, TRANSFER + 'per-ID/' + ident + '.json')
    per = json.loads(payload)
    assert per['primary_owner_from_full_TSV'] == f_owners[ident]
    assert per['original_card_refs'] == row['original_card_refs'] == g_rows[ident]['original_card_refs']
    assert per['F_finding_outcome'] == g_rows[ident]['F_recommendation']
    assert per['check_result'] == g_rows[ident]['F_check']
    assert all(per[k] == v for k, v in row.items())
    declared = per_bindings[ident]
    assert all(declared[k] == ref[k] for k in ['path', 'bytes', 'sha256'])
    assert per['G_finding_acceptance']['formal_G_closed'] is False
    if ident == 'LA-017':
        assert per['G_code_acceptance']['status'] == 'accepted_source'
        assert per['G_code_acceptance']['source_sha'] == '00a6eda114b903bc5abe86902cd8372426f739a1'
    else:
        assert per['G_code_acceptance']['status'] == 'not_inferred'
    code = per['code_sha']
    assert per['code_tree'] == git('rev-parse', code + '^{tree}').decode().strip()
    for n, card in enumerate(per['original_card_refs']):
        b, source_ref = binding(card['source_sha'], card['source_path'])
        lo, hi = card['lines']
        block = b''.join(b.splitlines(keepends=True)[lo - 1:hi])
        assert len(block) == card['bytes'] and sha(block) == card['sha256']
        assert source_ref['git_blob'] == card['document_git_blob']
        assert card['source_sha'] == '198076863e143dea9f89f02734b13d50dae3eed5'
        key = (card['source_sha'], card['source_path'], tuple(card['lines']), card['sha256'])
        blocks.setdefault(key, []).append(ident)
        card_rows.append({'finding_id': ident, 'binding_index': n, **card, 'actual_check': 'PASS'})
        all_original_bindings.append(card)
        if ident in affected | {'B56', 'LA-035'}:
            (OUT / ('original-' + ident + f'-{n}.md')).write_bytes(block)
    record = {'finding_id': ident, 'owner': f_owners[ident], 'per_ID_byte_binding': ref,
              'code_sha': code, 'code_tree': per['code_tree'],
              'check_result': per['check_result'], 'F_finding_outcome': per['F_finding_outcome'],
              'F_technical_recommendation': per['F_technical_recommendation'],
              'G_code_acceptance': per['G_code_acceptance'], 'G_finding_acceptance': per['G_finding_acceptance'],
              'original_card_refs': per['original_card_refs'],
              'criterion': per['primary_acceptance_scope'], 'G_review': g_rows[ident],
              'affected_current_metadata': ident in affected,
              'B56_optional_trigger_caption': ident == 'B56'}
    records.append(record)
    if ident in affected | {'B56'}:
        locators.append({'finding_id': ident, 'per_ID_path': ref['path'],
                         'index_row_pointer': f'/rows/{i}',
                         'audit_row_pointer': f"/rows/{list(audit_rows).index(ident)}",
                         'index_byte_binding_pointer': f"/per_ID_complete_records/{list(per_bindings).index(ident)}",
                         'per_ID_mutable_recommendation_fields': [
                             '/F_rationale', '/oracle_and_negative', '/next_concrete_result',
                             '/separate_unavailable_inputs_or_authority',
                             '/original_missing_input', '/original_next_owner',
                             '/new_property_followups_not_automatically_original_reopen'],
                         'immutable_original_fields': ['/original_card_refs', '/original_text',
                                                       '/historical_ROOT072', '/deciding_per_ID_carrier_ref'],
                         'source_checks': 'Append measured candidate/consumer refs only; never retarget unchanged scientific checks.'})

assert len(card_rows) == 36 and len(blocks) == 35
assert [v for v in blocks.values() if len(v) > 1] == [['LA-016', 'LA-016']]
closed = sum(r['F_finding_outcome'] == 'closed' for r in records)
limited = sum(r['F_finding_outcome'] == 'limited' for r in records)
assert (closed, limited) == (33, 2)
assert {r['finding_id'] for r in records if r['F_finding_outcome'] == 'limited'} == {'B214', 'B56'}
bundles = set()
for r in f_owners.values():
    bundles.update(r['source_bundle_ids'].split(','))
assert len(bundles) == 17
unchanged29 = [r['per_ID_byte_binding'] | {'finding_id': r['finding_id']} for r in records
               if r['finding_id'] not in affected]
unchanged28 = [r for r in unchanged29 if r['finding_id'] != 'B56']
assert len(unchanged29) == 29 and len(unchanged28) == 28
dump('original35-binding-audit.json', {'result': 'PASS', 'refs': [idx_ref, audit_ref, tsv_ref],
     'G_papers': papers, 'IDs': 35, 'bundles': sorted(bundles), 'original_bindings': 36,
     'unique_original_blocks': 35, 'duplicate_binding': 'LA-016 same original card, one ID',
     'original_card_bindings': card_rows, 'all35': records,
     'statuses': {'F_closed': 33, 'F_limited': 2, 'G_formal_closed': 0, 'G_new_source_accepted': 0,
                  'historical_Lex_accepted_source': '00a6eda114b903bc5abe86902cd8372426f739a1'},
     'carry_profile_6_changes_29': unchanged29, 'carry_profile_7_changes_28': unchanged28,
     'canonical_original_bindings_sha256': sha(json.dumps(all_original_bindings, sort_keys=True,
                                              ensure_ascii=False).encode())})
dump('dependent-binding-locators.json', {'baseline_ref': F, 'rows': locators,
     'global_keys': {'index_and_full_audit': ['/product_source', '/G_checkpoint',
        '/summary', '/current_receipt_registry', '/formal_G_acceptance', '/assembled_consumer_ready',
        '/assembled_consumer_scope', '/global_quality', '/P41'],
        'index_only': ['/per_ID_complete_records'],
        'full_audit_only': ['/fresh_independent_reconciliation', '/pattern_review']},
     'preserve_all_original_bindings': True,
     'old_history_and_raw_review_snapshots_not_rewrite': True})
dump('read-commands.json', COMMANDS)
print(json.dumps({'result': 'PASS', 'IDs': 35, 'bundles': 17, 'bindings': 36, 'unique_blocks': 35,
                  'carry29': len(unchanged29), 'carry28': len(unchanged28), 'F_closed': closed,
                  'F_limited': limited, 'G_formal': 0, 'G_new_source': 0, 'commands': len(COMMANDS)}))
