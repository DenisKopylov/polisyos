from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path('/workspace/e02-F-closeout-20261006')
E02 = Path('policy-engine/docs/research/e02-cloud-test-plan')
PACK = ROOT / E02 / 'implementation-handoffs/F/continuation-transfer-20261007'
OLD = 'e89d449acc6eedb1629c42c428689f7c578fce26'
NEW = '248497d27aa7951492c9a6d12c3c3493f3c246ec'
RP = E02 / 'implementation-handoffs/F/graph-profile-20261007.json'
raw = subprocess.check_output(['git', 'show', NEW + ':' + str(RP)], cwd=ROOT)
binding = {'git_ref': NEW, 'path': str(RP), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'git_blob': subprocess.check_output(['git', 'rev-parse', NEW + ':' + str(RP)], cwd=ROOT, text=True).strip()}
affected = {'B204', 'B212', 'B213', 'B214', 'B218', 'LA-037'}

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

records = []
for path in sorted((PACK / 'per-ID').glob('*.json')):
    obj = json.loads(path.read_text())
    if obj['finding_id'] in affected:
        obj['focused_continuation']['previous_custom_receipt'] = obj['focused_continuation']['receipt']
        obj['focused_continuation']['receipt'] = binding
        obj['focused_continuation']['canonical_handoff_fields_review'] = 'Forward receipt-only correction; no runtime/source/native outcome changes'
        obj['new_property_followups_not_automatically_original_reopen'].append({'lane': 'Canonical-graph-profile-receipt', **binding, 'code_candidate_sha': '4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d', 'code_candidate_tree': '551d4e760dc1168f6ad8182c9b176f00e94a2281', 'role': 'HANDOFF minimal schema/check/property canonical aliases; old source/output bytes and custom receipt remain historical'})
        dump(path, obj)
    d = path.read_bytes()
    records.append({'finding_id': obj['finding_id'], 'path': str(path.relative_to(ROOT)), 'bytes': len(d), 'sha256': hashlib.sha256(d).hexdigest()})

for name in ['index.json', 'full-audit.json']:
    path = PACK / name
    obj = json.loads(path.read_text())
    obj['focused_continuation']['previous_custom_receipt'] = obj['focused_continuation']['receipt']
    obj['focused_continuation']['receipt'] = binding
    obj['focused_continuation']['fresh_observed_G_checkpoint'] = json.loads(raw)['fresh_remote_checkpoint']
    obj['current_receipt_registry'].append({'lane': 'Canonical-graph-profile-receipt', **binding, 'role': 'Forward correction of HANDOFF minimum schema fields only; unchanged source/deciding bytes'})
    if name == 'index.json':
        for i, row in enumerate(obj['rows']):
            if row['finding_id'] in affected:
                per = json.loads((PACK / 'per-ID' / (row['finding_id'] + '.json')).read_text())
                obj['rows'][i] = {k: per[k] for k in row}
        obj['per_ID_complete_records'] = records
    else:
        obj['rows'] = records
    dump(path, obj)

path = PACK / 'G-source-integration-order.json'
obj = json.loads(path.read_text())
obj['focused_continuation']['previous_custom_receipt'] = obj['focused_continuation']['receipt']
obj['focused_continuation']['receipt'] = binding
obj['focused_continuation']['fresh_observed_G_checkpoint'] = json.loads(raw)['fresh_remote_checkpoint']
obj['entries'][-1]['previous_custom_receipt'] = obj['entries'][-1]['receipt']
obj['entries'][-1]['receipt'] = binding
dump(path, obj)
path = PACK / 'G-local-causal-reruns.json'
obj = json.loads(path.read_text()); obj['previous_custom_receipt'] = obj['focused_receipt']; obj['focused_receipt'] = binding; dump(path, obj)
for path in [PACK / 'REPORT.md', *(ROOT / E02 / 'closure-decisions' / name for name in ['F.md', 'method-decisions.md', 'runtime-profiles.md'])]:
    text = path.read_text(); assert OLD in text; path.write_text(text.replace(OLD, NEW))
print(json.dumps({'canonical_receipt': NEW, 'bytes': len(raw), 'six_current_refs_updated': True}))
