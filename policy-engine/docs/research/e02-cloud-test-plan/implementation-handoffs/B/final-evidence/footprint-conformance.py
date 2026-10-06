"""Read-only blob/mode reconciliation for every final changed tracked path."""
import hashlib
import json
import subprocess
from pathlib import Path

REPO = '/workspace/e02-B-acceptance'
INPUT = Path('/tmp/e02-B-final-footprint-census.json')
OUTPUT = Path('/tmp/e02-B-final-footprint-conformance.json')
d = json.loads(INPUT.read_text())

def tree(ref):
    output = subprocess.check_output(['git', '-C', REPO, 'ls-tree', '-r', '-z', ref])
    result = {}
    for record in output.split(b'\0'):
        if record:
            metadata, path = record.split(b'\t', 1)
            mode, kind, blob = metadata.decode().split()
            result[path.decode()] = {'mode': mode, 'kind': kind, 'blob': blob}
    return result

owners = {name: tree(row['head']) for name, row in d['family_results'].items()}
unique = []
shared = []
for row in d['changed_paths']:
    names = row['family_delta_membership']
    actual = row['candidate_blob']
    if len(names) == 1:
        expected = owners[names[0]].get(row['path'])
        unique.append({'path': row['path'], 'family': names[0], 'category': row['category'], 'equal_blob_kind_mode': actual == expected})
    else:
        shared.append({'path': row['path'], 'category': row['category'], 'candidate_blob': actual, 'family_blobs': {name: owners[name].get(row['path']) for name in names}})
failed = [row for row in unique if not row['equal_blob_kind_mode']]
assert len(unique) + len(shared) == d['denominator']['complete_changed_tracked_paths']
result = {
    'schema': 'policyos.e02.final_footprint_conformance.v1',
    'predicate_basis': 'recomputed',
    'command': 'python3 /tmp/e02-B-final-footprint-conformance.py',
    'cwd': '/workspace',
    'input_closure': {'candidate_sha': d['input_closure']['candidate_sha'], 'candidate_tree': d['input_closure']['candidate_tree'], 'census_path': str(INPUT), 'census_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest(), 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    'denominator': {'changed_tracked_paths': len(unique) + len(shared), 'uniquely_owned_paths': len(unique), 'shared_documentation_paths': len(shared), 'unique_paths_equal_owner_head': len(unique) - len(failed)},
    'mismatches': failed,
    'shared_paths': shared,
    'verdict': 'PASS' if not failed and all(row['category'] == 'documentation' for row in shared) else 'FAIL',
    'limitations': ['Shared engine README is intentionally combined from EXE and RUN; content review belongs to root. No product execution or runtime assertion.'],
}
OUTPUT.write_text(json.dumps(result, separators=(',', ':')) + '\n')
print(json.dumps({'verdict': result['verdict'], 'denominator': result['denominator'], 'mismatches': failed, 'output': str(OUTPUT), 'sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}, separators=(',', ':')))
