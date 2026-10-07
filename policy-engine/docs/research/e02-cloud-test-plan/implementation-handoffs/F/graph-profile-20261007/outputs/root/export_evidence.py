"""Lossless finite evidence export; never copies a source tree or environment."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess

ROOT = Path('/workspace/e02-F-closeout-20261006')
SCRATCH = Path('/tmp/e02-F-graph-profile-20261007')
REL = Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-profile-20261007')
DEST = ROOT / REL
SELECTIONS = [
    'api-review/combined4ee/transfer-selection.json',
    'api-review/installed4ee/transfer-selection.json',
    'graph-review-prep/transfer-selection.json',
    'worker/focused-real-worker-transfer-selection.json',
    'worker/assembly-output-selection.json',
    'economics-review/transfer-selection.json',
    'cau/publication-recovery-transfer-selection.json',
]
selected = {}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def add(path, role, asserted=None):
    path = path.resolve()
    assert path.is_relative_to(SCRATCH), path
    data = path.read_bytes()
    if asserted is not None:
        assert len(data) == asserted['bytes'], path
        assert sha(data) == asserted['sha256'], path
    if path in selected:
        selected[path]['roles'].add(role)
    else:
        selected[path] = {'data': data, 'roles': {role}}

for rel in SELECTIONS:
    p = SCRATCH / rel
    selection = json.loads(p.read_text())
    add(p, 'immutable_complete_selection')
    for item in selection.get('files', selection.get('items', [])):
        path = Path(item['path'])
        if not path.is_absolute():
            path = p.parent / path
        add(path, rel, item)

for p in (SCRATCH / 'root').iterdir():
    if p.is_file():
        add(p, 'root_setup_or_full_deciding_output')
for p in (SCRATCH / 'root/final-wave').iterdir():
    if p.is_file():
        add(p, 'root_frozen_affected_wave')
for rel in ['cau/root-dependent-caption-proposal.json']:
    add(SCRATCH / rel, 'independent_binding_proposal')

DEST.mkdir(parents=True, exist_ok=True)
records = []
for path, item in sorted(selected.items(), key=lambda kv: str(kv[0])):
    data = item['data']
    rel = path.relative_to(SCRATCH)
    stored_rel = REL / 'outputs' / rel
    encoding = 'identity'
    stored = data
    if len(data) > 80000 and not str(path).endswith('.gz'):
        stored = gzip.compress(data, compresslevel=9, mtime=0)
        stored_rel = Path(str(stored_rel) + '.gz')
        encoding = 'gzip'
    target = ROOT / stored_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(stored)
    assert sha(target.read_bytes()) == sha(stored)
    assert (gzip.decompress(stored) if encoding == 'gzip' else stored) == data
    records.append({
        'original_path': str(path), 'path': str(stored_rel),
        'encoding': encoding, 'stored_bytes': len(stored), 'stored_sha256': sha(stored),
        'decoded_bytes': len(data), 'decoded_sha256': sha(data),
        'roles': sorted(item['roles']),
    })

manifest = {
    'schema': 'e02.F.lossless_artifact_transports.v1', 'unit': 'F',
    'source_sha': '4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d',
    'source_tree': '551d4e760dc1168f6ad8182c9b176f00e94a2281',
    'law': 'Finite immutable selections plus root full outputs; complete bytes, optional lossless gzip, no recursive source/environment copy. Historical references remain immutable Git refs.',
    'file_count': len(records), 'stored_bytes': sum(r['stored_bytes'] for r in records),
    'decoded_bytes': sum(r['decoded_bytes'] for r in records), 'files': records,
    'no_production_data': True, 'cleanup_action': 'none',
}
(DEST / 'artifact-transports.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'files': len(records), 'stored_bytes': manifest['stored_bytes'], 'decoded_bytes': manifest['decoded_bytes']}))
