"""Select independent immutable owner inputs BEFORE reading the final index.

No outcome adoption, scientific runs, tracked writes, or final-index reads.
The prior canonical inventory is this reviewer's own earlier full owner census.
ECO upstream receipt declarations are source inputs, not the index under review.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess

REPO = Path('/workspace/e02-F-closeout-20261006')
OUT = Path(__file__).resolve().parent
BASE = '198076863e143dea9f89f02734b13d50dae3eed5'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
OLD_CENSUS = Path('/workspace/e02-F-20261006-receipts/protocol-audit/canonical-receipt-inventory.json')
UPSTREAM = Path('/tmp/e02-F-continuation-20261006/economics/docs-reconciliation/current35-doc-ledger-draft.json')
SIX = Path('/tmp/e02-F-continuation-20261006/root-ledger-draft/current-extra-specifications-six.json')
MANIFEST = Path('/tmp/e02-F-continuation-20261006/cau/original35-reconciliation.json')
EXTRA = [
    ('root_tmle', '39133d4d8b9a680942ffeb983385cbee1b1b493a', 'tmle-selected-consumer-20261006.json'),
    ('tmle_common', '3ae04e86cc6d22a10d28abb163c1078a0bea6ba4', 'tmle-common-report-20261006.json'),
    ('tmle_schema', '27f172d56b59c3157275e90e50b1d00cc5219a91', 'tmle-report-schema-20261006.json'),
    ('f_docs', 'e84acb04fbe1fbebdfa5a54f87ff0fc72640a4ef', 'closure-doc-reconciliation-20261006.json'),
    ('root_worker', '8d7bf448874206429d87705454565d71a367cb32', 'worker-value-consumers-continuation-20261006.json'),
    ('root_style', '613a55a5946bdeff2dc849f2488fb88c81b01360', 'source-quality-freeze-20261006.json'),
]

def sha(body):
    return hashlib.sha256(body).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, stderr=subprocess.PIPE)

def file_ref(path):
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': sha(body)}

def normalize(ident):
    return ident.upper().replace('LA-', 'LA')

def prepare(extra_specs=None):
    OUT.mkdir(parents=True, exist_ok=True)
    tsv_path = 'policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv'
    tsv = git('show', BASE + ':' + tsv_path)
    owners = [row for row in csv.DictReader(io.StringIO(tsv.decode()), delimiter='\t') if row['unit'] == 'F']
    assert len(owners) == len({normalize(r['finding_id']) for r in owners}) == 35
    assert len({r['source_closure_owner'] for r in owners}) == 17
    manifest = json.loads(MANIFEST.read_bytes())
    rows = manifest['rows']
    assert {normalize(r['finding_id']) for r in rows} == {normalize(r['finding_id']) for r in owners}
    card_count = 0
    source_cache = {}
    for row in rows:
        owner = next(r for r in owners if normalize(r['finding_id']) == normalize(row['finding_id']))
        assert row['bundle'] == owner['source_closure_owner']
        for card in row['original_card_bindings']:
            key = card['source_sha'], card['source_path']
            if key not in source_cache:
                source_cache[key] = git('show', key[0] + ':' + key[1])
            start, end = card['lines']
            block = b''.join(source_cache[key].splitlines(keepends=True)[start-1:end])
            assert len(block) == card['bytes'] and sha(block) == card['sha256']
            assert block.decode().splitlines()[0] == card['title']
            card_count += 1
    assert card_count == 36

    seeds = []
    census = json.loads(OLD_CENSUS.read_bytes())
    assert census['canonical_unique_path_count'] == 15
    for path, records in census['introduced_canonical_receipt_paths'].items():
        assert len(records) == 1
        record = records[0]
        seeds.append({'head': record['sha'], 'path': path, 'bytes': record['bytes'],
                      'sha256': record['sha256'], 'origin': 'prior independent canonical owner census',
                      'role': record['role']})
    upstream = json.loads(UPSTREAM.read_bytes())['current_receipt_registry']
    assert len(upstream) == 10
    for record in upstream:
        seeds.append({'head': record['git_ref'], 'path': record['path'],
                      'bytes': record['bytes'], 'sha256': record['sha256'],
                      'origin': 'upstream owner packet:' + record['key'], 'role': 'owner_current_input'})
    for record in json.loads(SIX.read_bytes()):
        seeds.append({**record, 'origin': 'published followup:' + record['lane'], 'role': 'owner_current_input'})
    for lane, head, name in EXTRA:
        seeds.append({'lane': lane, 'head': head, 'path': PREFIX + name,
                      'origin': 'actual separately published:' + lane, 'role': 'owner_current_input'})
    if extra_specs is not None:
        for record in json.loads(extra_specs.read_bytes()):
            assert set(record).issuperset({'head', 'path'})
            assert record['path'].startswith(PREFIX)
            seeds.append({**record, 'origin': 'new final owner packet:' + record.get('lane', 'unnamed'),
                          'role': 'owner_current_input'})
    selected = {}
    for seed in seeds:
        key = seed['head'], seed['path']
        body = git('show', key[0] + ':' + key[1])
        if 'bytes' in seed:
            assert seed['bytes'] == len(body), key
        if 'sha256' in seed:
            assert seed['sha256'] == sha(body), key
        receipt = json.loads(body)
        assert receipt.get('schema') == 'policyos.e02.implementation_handoff.v1', key
        assert receipt.get('unit') == 'F', key
        commits = receipt['implementation_commits']
        assert isinstance(commits, list) and all(len(c) == 40 for c in commits), key
        if not commits:
            assert receipt.get('closure_ids') == receipt.get('related_finding_ids') == receipt.get('changed_paths') == [], key
            assert receipt.get('slice') == 'continuation-inputs-and-storage-20261006', key
            seed['role'] = 'ancillary_input_custody_no_scientific_closure'
        implementation = receipt.get('candidate_source_sha', receipt.get('implementation_sha', commits[-1] if commits else None))
        assert isinstance(implementation, str) and len(implementation) == 40, key
        tree = git('rev-parse', implementation + '^{tree}').decode().strip()
        assert tree == receipt.get('candidate_tree_sha', receipt.get('candidate_tree')), key
        if key not in selected:
            selected[key] = {'head': key[0], 'path': key[1], 'bytes': len(body),
                             'sha256': sha(body), 'implementation_sha': implementation,
                             'candidate_tree_sha': tree, 'selected_origins': [], 'role': seed['role']}
        selected[key]['selected_origins'].append(seed['origin'])
    records = list(selected.values())
    destination = OUT / ('required-registry-final.json' if extra_specs else 'required-registry-prepared.json')
    destination.write_text(json.dumps(records, indent=2) + '\n')
    note = {'schema': 'F-independent-required-owner-footprint/1', 'check': 'PASS',
            'selected_before_final_index_read': True, 'final_index_reads': 0,
            'original_denominator': {'findings': 35, 'bundles': 17, 'card_bindings': card_count},
            'components': len(records), 'seed_observations': len(seeds),
            'receipt_input_roles_not_per_ID_closure': True,
            'required_registry': file_ref(destination),
            'selection_inputs': [file_ref(p) for p in [OLD_CENSUS, UPSTREAM, SIX, MANIFEST]] +
                                ([file_ref(extra_specs)] if extra_specs else []),
            'original_owner_TSV': {'source_sha': BASE, 'source_path': tsv_path,
                                   'bytes': len(tsv), 'sha256': sha(tsv)},
            'author_heads_readonly_observation_not_ancestry_runtime_proof': True,
            'pending_unreceived_components': [] if extra_specs else ['final common-source API inventory receipt',
                                                                    'final both-sites common-source installed wave receipt'],
            'final_packet_validation': 'UNRUN',
            'limitations': ['Footprint/carrier/tree/card preparation is not original-finding closure or formal G acceptance.',
                            'Full metadata/transport/guard/narrative review runs only after ROOT publishes frozen packet.',
                            'All future owner receipts must be explicitly selected before reading final index.']}
    (OUT / ('footprint-final.json' if extra_specs else 'footprint-prepared.json')).write_text(json.dumps(note, indent=2) + '\n')
    print(json.dumps(note, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--extra-specs', type=Path)
    args = p.parse_args()
    prepare(args.extra_specs)
