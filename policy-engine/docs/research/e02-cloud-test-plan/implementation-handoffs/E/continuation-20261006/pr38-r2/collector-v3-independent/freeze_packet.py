"""Freeze moderate independent review records; never index private/raw fixtures."""
from pathlib import Path
import hashlib
import json
import platform
import sys

OUT = Path(__file__).parent
SOURCE = Path('/workspace/e02-E-pr38-r2-receipts/common-wave-publication-prep/collect_wave_v3_final.py')
identity = lambda p: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
controls = json.loads((OUT/'controls.json').read_text())
custody = json.loads((OUT/'reader-custody.json').read_text())
freeze = json.loads((OUT/'freeze-role-probe.json').read_text())
assert controls['control_count'] == 14
assert all(row['synthetic_payload_copied'] and row['state'] == 'CONTROL_COMPLETE_BOUND' for row in freeze['controls'])
review = {
    'schema': 'policyos.e02.independent-collector-review.v3',
    'source': {'path': str(SOURCE), **identity(SOURCE)},
    'historical_v2_base': '1e1b5028274814b7c4318671588202480390a6bc',
    'reviewer': 'doe_r2, independent of FRC collector author',
    'reusable_collector_verdict': 'HOLD-explicit-external-freeze-parent-raw-private-role-escape',
    'affected_v2_escapes': 'Corrected:14 independent positives/refusals/property-removal controls passed.',
    'new_confirmed_remaining_class_escape': freeze,
    'actual_historical5e_custody_verdict': custody['verdict'],
    'actual5e_counts': custody['counts'],
    'scope': 'Scratch metadata reader/protocol only; no numeric/product/global gate commands. Same completed historical5e evidence, no new backend results.',
    'input_custody': {'author_index': custody['author_index_verified'], 'author_actual_nested': custody['author_actual_nested_index_verified'], 'independent_actual_nested': custody['independent_actual_index_verified'], 'moderate_original_source_assets':45, 'private_and_raw_hash_only':16},
    'configured_Ruff_and_format': 'PASS-frozen-collector-source-only; independent probes are full-input evidence, not a global lint PASS claim',
    'commands': [
        ['python', str(OUT/'collector_controls.py')],
        ['python', str(OUT/'reader_custody.py')],
        ['python', str(OUT/'freeze_role_probe.py')],
        ['ruff', 'check', '--config', '/workspace/e02-E-continuation-20261006/policy-engine/ruff.toml', str(SOURCE)],
        ['ruff', 'format', '--check', '--config', '/workspace/e02-E-continuation-20261006/policy-engine/ruff.toml', str(SOURCE)],
    ],
    'environment': {'python':sys.executable, 'version':sys.version, 'platform':platform.platform(), 'UV_NO_SYNC':'1', 'PYTHONDONTWRITEBYTECODE':'1', 'cpu_caps':custody['cpu_caps']},
    'property_basis': 'Independent actual case counts + source/name/job identities; declared planned stdout and common public payload role before copying. Integrity/hash never promotes raw/private payload.',
    'next_owner': 'FRC canonical collector author: retain raw/private parent role in explicit freeze admission; root publishes append-only after independent affected-delta GO.',
    'finding_closure':False,
    'limitations': [
        'Historic COMPLETE_BOUND is custody, not successful wave or finding closure.',
        'Full framed source mechanism review delegated to independent CAL; metadata consistency and immutable bytes alone do not prove its full property.',
        'Post-command backend observer is not child JAX configuration evidence; P41 inherited-red remains not_established.',
        'Real raw171772803B and15actualprivate config inputs hashed only, never printed/copied.',
        'Synthetic raw/private marker probes contain no actual private material; original source and author fixtures were not changed.',
        'No deletion/Trash. Exact repeatable candidates are synthetic-controls/, synthetic-freeze-role/, and actual-reader-publication/ after deciding receipts and inactive-user check; preserve unique evidence/source/docs.',
    ],
}
(OUT/'review.json').write_text(json.dumps(review, indent=2)+'\n')
files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in {'copy-index.json'})
files.append(OUT/'actual-reader-publication'/'copy-index.json')
rows = [{'path':str(p), **identity(p), 'complete_nested_index':p.parent.name=='actual-reader-publication'} for p in files]
index = {'scope':'Frozen moderate independent v3 review; reusable HOLD and historical custody GO separated', 'primary':str(OUT/'review.json'), 'files':rows, 'file_count':len(rows), 'total_bytes':sum(r['bytes'] for r in rows), 'index_self_excluded':True, 'fixtures_private_raw_not_indexed':True}
(OUT/'copy-index.json').write_text(json.dumps(index, indent=2)+'\n')
for row in rows:
    assert identity(Path(row['path'])) == {key:row[key] for key in ['bytes','sha256']}
print(json.dumps({'files':len(rows),'bytes':index['total_bytes'],'index_identity':identity(OUT/'copy-index.json'),'review_identity':identity(OUT/'review.json')}))
