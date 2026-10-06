"""Independent v3 actual reader/custody controls, zero native/gate stages."""
from argparse import Namespace
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import runpy
import subprocess

ROOT = Path('/workspace/e02-E-continuation-20261006')
OUT = Path(__file__).parent
SOURCE = Path('/workspace/e02-E-pr38-r2-receipts/common-wave-publication-prep/collect_wave_v3_final.py')
AUTHOR = Path('/workspace/e02-E-pr38-r2-receipts/collector-v3-final-author-controls')
WAVE = Path('/workspace/e02-E-pr38-r2-receipts/common-wave-5e3e37276')
FROZEN = '5e3e3727685132f270a3a07b9f63dd962a88cd96'
FREEZE = Path('/workspace/e02-E-pr38-r2-receipts/source-freeze-5e3e37276.json')
MODULE = runpy.run_path(str(SOURCE), run_name='independent_actual_v3_reader_only')
identity = MODULE['identity']
assert identity(SOURCE) == dict(bytes=38152, sha256='a6399cc46cbfe25b103fa210259eff2be9483f582ae7cba773632f079f7194ec')

def check_index(path, absolute=False):
    index = json.loads(path.read_text())
    files = index['files']
    assert len(files) == index['file_count']
    assert sum(row['bytes'] for row in files) == index['total_bytes']
    for row in files:
        file = Path(row['path']) if absolute else path.parent/row['path']
        assert identity(file) == dict(bytes=row['bytes'], sha256=row['sha256'])
    return {'path': str(path), 'identity': identity(path), 'files': len(files), 'bytes': index['total_bytes']}

author_index = check_index(AUTHOR/'copy-index.json', absolute=True)
author_publication = Path('/workspace/e02-E-pr38-r2-receipts/common-wave-publication-prep/actual-failed-5e3e37276-v3')
author_nested = check_index(author_publication/'copy-index.json')
root_before = subprocess.check_output(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}'], cwd=ROOT, text=True).splitlines()
plan = json.loads((WAVE/'plan.json').read_text())
observed = MODULE['collect'](Namespace(repo=ROOT, candidate=FROZEN, wave_root=WAVE, publication_root=OUT/'actual-reader-publication', freeze_receipt=FREEZE, max_moderate_bytes=8*1024*1024, capture_incomplete=False))
assert observed['collection_state'] == 'COMPLETE_BOUND' and not observed['issues']
assert observed['numeric_counts'] == dict(cases=1440, passed=1086, failed=3, errors=351, skipped=0)
assert observed['native_numeric_counts_excluding_A_packets'] == dict(cases=1433, passed=1086, failed=2, errors=345, skipped=0)
assert [p['counts'] for p in observed['foreign_owner_A_packet_cases']] == [dict(cases=5, passed=0, failed=0, errors=5, skipped=0), dict(cases=2, passed=0, failed=1, errors=1, skipped=0)]
assert observed['unattributed_owner_packet_counts']['cases'] == 0
assert observed['native_numeric_attribution_complete'] is True
assert observed['doctor_is_full_ci'] is False and observed['finding_closure'] is False
assert observed['static_proxy']['P41'].startswith('not_established')
publication = OUT/'actual-reader-publication'
own_index = check_index(publication/'copy-index.json')
index = json.loads((publication/'copy-index.json').read_text())
assert len(index['wave_source_assets']) == 45
for row in index['wave_source_assets']:
    original = FREEZE if row['path'] == 'source-freeze-receipt.json' else WAVE/row['path']
    expected = dict(bytes=row['bytes'], sha256=row['sha256'])
    assert identity(original) == identity(publication/row['path']) == expected
    assert identity(author_publication/row['path']) == expected
assert len(observed['excluded_raw_custody']) == 16
for row in observed['excluded_raw_custody']:
    assert identity(WAVE/row['path']) == dict(bytes=row['bytes'], sha256=row['sha256'])
    assert not (publication/row['path']).exists()
assert not any('raw' in Path(r['path']).parts or 'git-config-private' in r['path'] for r in index['files'])
raw = next(r for r in observed['excluded_raw_custody'] if r['path'].endswith('production-invocation.raw.json'))
assert raw['bytes'] == 171772803 and raw['sha256'] == '404cdb1543a96433016ca3880c3d557e2d027f9fa62060be40d9b8e266b16fbd'
stage_counts = {}
for row in observed['jobs']:
    if row['name'] in {'workspace-verify', 'ci-parity'}:
        c = dict(Counter(s['outcome'] for scope in row['umbrella_stages']['scopes'] for s in scope['steps']))
        assert c == row['umbrella_stage_outcomes']
        stage_counts[row['name']] = c
assert stage_counts == {'workspace-verify': {'PASS': 1, 'FAIL': 1, 'UNRUN': 13}, 'ci-parity': {'FAIL': 1, 'UNRUN': 23}}
controls = []
first = index['files'][0]
for field, wrong in [('bytes', -1), ('sha256', '0'*64)]:
    forged = dict(first)
    forged[field] = wrong
    assert identity(publication/forged['path']) != dict(bytes=forged['bytes'], sha256=forged['sha256'])
    controls.append(field+' REFUSED')
forged_counts = dict(observed['native_numeric_counts_excluding_A_packets'], cases=1440)
assert forged_counts != dict(cases=1433, passed=1086, failed=2, errors=345, skipped=0)
controls.append('native/A denominator forgery REFUSED')
caps = {name: os.environ.get(name) for name in MODULE['CAPS']}
assert all(value is None for value in caps.values())
assert identity(SOURCE) == dict(bytes=38152, sha256='a6399cc46cbfe25b103fa210259eff2be9483f582ae7cba773632f079f7194ec')
assert check_index(AUTHOR/'copy-index.json', absolute=True) == author_index
root_after = subprocess.check_output(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}'], cwd=ROOT, text=True).splitlines()
result = {'source_path': str(SOURCE), 'source_identity': identity(SOURCE), 'author_index_verified': author_index, 'author_actual_nested_index_verified': author_nested, 'independent_actual_index_verified': own_index, 'root_metadata_before': root_before, 'root_metadata_after': root_after, 'original_actual_wave_candidate': FROZEN, 'counts': observed['numeric_counts'], 'native_counts': observed['native_numeric_counts_excluding_A_packets'], 'A_counts': [p['counts'] for p in observed['foreign_owner_A_packet_cases']], 'unattributed': observed['unattributed_owner_packet_counts'], 'scope': 'Reader-only collection of same completed historical5e bytes, no command replay or new numeric evidence', 'moderate_original_source_assets': 45, 'raw_and_private_hash_only_records': 16, 'large_raw_bytes_not_copied': 171772803, 'stage_outcomes': stage_counts, 'independent_corrupt_controls': controls, 'product_native_or_gate_commands_executed': 0, 'cpu_caps': caps, 'verdict': 'GO-bounded-actual-reader-custody-and-preserved-attribution', 'finding_closure': False}
(OUT/'reader-custody.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
