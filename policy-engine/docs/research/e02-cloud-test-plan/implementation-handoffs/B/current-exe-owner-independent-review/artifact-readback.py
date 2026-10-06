import hashlib
import json
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.orchestration.engine.checkpoint import resolve_latest_checkpoint

root = Path('/workspace/e02-B-current-runtime/_build/e02-current-runtime')
controls = json.loads((root / 'exe-owner-controls-v2/receipt.json').read_text())
base = json.loads((root / 'exe-ff6d-cancel/receipt.json').read_text())
fixed = json.loads((root / 'exe-1bd1-cancel/receipt.json').read_text())
rows = []
for case, directory, packet in [('base_suppressed', 'exe-ff6d-cancel', base), ('fixed_suppressed', 'exe-1bd1-cancel', fixed),
                              ('cooperative', 'exe-owner-controls-v2/cooperative_cancel', controls['controls'][0]),
                              ('no_cancel', 'exe-owner-controls-v2/no_cancel', controls['controls'][1])]:
    store = FileSystemCAS(root / directory / 'cas')
    run_dir = store.root / 'runs/R_deadline'
    persisted = []
    for name in ('trace.jsonl', 'checkpoint_head.json', 'checkpoint_history.json'):
        path = run_dir / name
        if path.exists():
            raw = path.read_bytes()
            persisted.append({'role': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'raw_utf8': raw.decode()})
    selected = []
    def capture(ref, role):
        ref = ArtifactRef.model_validate(ref)
        verified = store.verify(ref)
        assert verified.ok, (role, verified)
        raw = store.get_bytes(ref)
        assert hashlib.sha256(raw).hexdigest() == str(ref.artifact_id).removeprefix('sha256:')
        selected.append({'role': role, 'ref': ref.model_dump(mode='json'), 'verify_ok': verified.ok,
                         'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'raw_utf8': raw.decode()})
    for ref in packet.get('run_outputs_after_cancel', packet.get('run_outputs', [])):
        capture(ref, 'run_output')
    run_ref = packet.get('termination', {}).get('run_ref')
    if run_ref:
        capture(run_ref, 'run_manifest')
    checkpoint = resolve_latest_checkpoint(store, 'R_deadline')
    if checkpoint:
        head, dto = checkpoint
        capture(head.checkpoint_ref, 'checkpoint')
        for ref in dto.metadata.cache_entry_refs:
            capture(ref, 'checkpoint_cache_entry')
        assert dto.state['params'] == {'seed': 7, 'result': 14}
    rows.append({'case': case, 'persisted_files': persisted, 'selected_verified_artifacts': selected,
                 'checkpoint_present': checkpoint is not None})
packet = {'reader': 'real FileSystemCAS.verify/get_bytes and resolve_latest_checkpoint', 'rows': rows, 'pass': True}
(root / 'exe-owner-artifact-readback.json').write_text(json.dumps(packet, indent=2) + '\n')
print(json.dumps(packet, indent=2))
