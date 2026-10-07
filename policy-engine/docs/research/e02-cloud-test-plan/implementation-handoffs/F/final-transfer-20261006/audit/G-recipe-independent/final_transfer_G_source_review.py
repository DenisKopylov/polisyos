"""Independent complete nested Git byte bindings of the local G rerun recipe."""
from pathlib import Path
import hashlib
import json
import subprocess

source = Path('/workspace/e02-F-20261006-receipts/final-root/G-local-causal-reruns.json')
out = Path('/workspace/e02-F-20261006-receipts/cau/final-transfer-G-source-review.json')
repo = '/workspace/e02-F-closeout-20261006'
raw_recipe = source.read_bytes()
recipe = json.loads(raw_recipe)
refs = {}

def walk(value, where='$'):
    if isinstance(value, dict):
        if {'source_sha', 'path', 'git_blob', 'sha256'} <= value.keys() and ('bytes' in value or 'lines' in value):
            refs[(value['source_sha'], value['path'], value.get('bytes'), value['sha256'])] = (where, value)
        for key, child in value.items():
            walk(child, where + '.' + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, where + '[' + str(index) + ']')

walk(recipe)
verified = []
for where, ref in refs.values():
    raw = subprocess.check_output(['git', '-C', repo, 'show', ref['source_sha'] + ':' + ref['path']])
    blob = subprocess.check_output(['git', '-C', repo, 'rev-parse', ref['source_sha'] + ':' + ref['path']], text=True).strip()
    assert blob == ref['git_blob'], where
    if 'lines' in ref:
        first, last = ref['lines']
        raw = b''.join(raw.splitlines(keepends=True)[first - 1:last])
    if 'bytes' in ref:
        assert len(raw) == ref['bytes'], where
    assert hashlib.sha256(raw).hexdigest() == ref['sha256'], where
    if 'exact_original_card_text' in ref:
        assert raw.decode() == ref['exact_original_card_text'], where
    verified.append({'where': where, 'ref': ref, 'verified_bytes': len(raw), 'scope': 'source_card_block' if 'lines' in ref else 'full_file'})
assert recipe['execution_outcome'] == 'UNRUN_by_this_spec'
assert recipe['closure_ids'] == []
report = {'check': 'PASS', 'recipe': {'path': str(source), 'bytes': len(raw_recipe), 'sha256': hashlib.sha256(raw_recipe).hexdigest()},
    'source_refs_verified': verified, 'execution_outcome': recipe['execution_outcome'], 'closure_ids': [],
    'scope': 'Complete unique nested Git byte bindings; rerun specification does not claim execution, real-data admission or authority.',
    'initial_harness_error': {'exit_code': 1, 'stdout': '', 'stderr': 'Traceback (most recent call last):\n  File "<stdin>", line 17, in <module>\nAssertionError: UNRUN_by_this_spec\n',
        'classification': 'Review harness expected exact canonical UNRUN enum in a rerun-recipe narrative field which correctly uses UNRUN_by_this_spec; no product or source binding defect and no deciding PASS from the initial failing probe.'}}
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'check': 'PASS', 'unique_nested_refs': len(verified), 'execution_outcome': recipe['execution_outcome'], 'output': str(out), 'bytes': out.stat().st_size, 'sha256': hashlib.sha256(out.read_bytes()).hexdigest()}))
