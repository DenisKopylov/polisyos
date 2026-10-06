"""Reconcile every C historical status/label to the pinned coverage owner."""
import json
import re
import subprocess
from pathlib import Path

BASE = '198076863e143dea9f89f02734b13d50dae3eed5'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/'
coverage = json.loads(subprocess.check_output(['git', 'show', BASE + ':' + PREFIX + 'coverage.json']))
expected = {x['id']: x for x in coverage['findings'] if x['unit'] == 'C'}

def check(text):
    rows = {}
    for line in text.splitlines():
        if '<a id="finding-' not in line:
            continue
        cells = line.split('|')
        fid = re.search(r'`(B\d+|LA-\d+)`', cells[1]).group(1)
        status = re.search(r'`([^`]+)`', cells[2]).group(1)
        labels = re.findall(r'`([^`]+)`', cells[2])
        rows[fid] = {'status': status, 'capability_label': labels[1] if len(labels) > 1 else None}
    assert set(rows) == set(expected) and len(rows) == 54
    mismatches = []
    for fid, actual in rows.items():
        wanted = {'status': expected[fid]['ledger_status_historical'],
                  'capability_label': expected[fid]['capability_label']}
        if actual != wanted:
            mismatches.append({'id': fid, 'actual': actual, 'expected': wanted})
    return {'complete_C_rows': len(rows), 'mismatches': mismatches}

before = check(subprocess.check_output(['git', 'show', BASE + ':' + PREFIX + 'C.md']).decode())
after = check(Path(PREFIX + 'C.md').read_text())
assert [x['id'] for x in before['mismatches']] == ['B139']
assert not after['mismatches']
print(json.dumps({'basis': PREFIX + 'coverage.json@' + BASE,
                  'before': before, 'after': after,
                  'property': 'every C historical status/label agrees with the coverage owner; no finding status changed'}, indent=2))
