"""Source-guarded complete output capture for independent monitor mechanisms."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/workspace/e02-F-fry-20261006')
ENGINE = ROOT / 'policy-engine'
SCRATCH = Path(__file__).parent
PYTHON = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
EXPECTED = '3c152d3640f1aa9d46f4e3020cda364e25f6ef84'

def capture(name, cmd):
    before = subprocess.check_output(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}'], cwd=ROOT, text=True).splitlines()
    assert before[0] == EXPECTED, before
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ENGINE) + ':' + str(ENGINE / 'src'))
    start = time.monotonic()
    result = subprocess.run(cmd, cwd=ENGINE, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    wall = time.monotonic() - start
    after = subprocess.check_output(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}'], cwd=ROOT, text=True).splitlines()
    assert before == after, (before, after)
    refs = {}
    for kind, payload in [('stdout', result.stdout), ('stderr', result.stderr)]:
        path = SCRATCH / (name + '.' + kind + '.txt')
        path.write_bytes(payload)
        refs[kind] = {'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest(), 'size_bytes': len(payload)}
    record = {'source_sha': before[0], 'source_tree': before[1], 'after_sha_tree': after,
              'command': cmd, 'cwd': str(ENGINE), 'environment': {'python': PYTHON,
              'PYTHONPATH': env['PYTHONPATH'], 'PYTHONDONTWRITEBYTECODE': '1',
              'otel': 'Explicit realSDK activation and real in-memory counter; no external collector claimed.'},
              'exit_code': result.returncode, 'wall_seconds': wall, 'refs': refs}
    (SCRATCH / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    print(result.stdout.decode()[-2000:])
    print(result.stderr.decode())

mode = sys.argv[1]
if mode in ('no_consumption', 'no_sidecars', 'broad_identity_skip'):
    capture('removal-' + mode, [PYTHON, str(SCRATCH / 'removal_replay.py'), mode])
elif mode == 'ruff':
    capture('ruff', [PYTHON, '-m', 'ruff', 'check', 'src/polisyos/foundry/methods/backends/dispatch.py',
        'src/polisyos/foundry/methods/lifecycle/output_monitor.py',
        'tests/unit/foundry/methods/backends/test_output_anomaly_count.py'])
elif mode == 'format':
    capture('format', [PYTHON, '-m', 'ruff', 'format', '--check',
        'src/polisyos/foundry/methods/backends/dispatch.py',
        'src/polisyos/foundry/methods/lifecycle/output_monitor.py',
        'tests/unit/foundry/methods/backends/test_output_anomaly_count.py'])
elif mode == 'fragment':
    capture('fragment', [PYTHON, str(SCRATCH / 'fragment_check.py')])
elif mode == 'diff':
    capture('diff', ['git', 'diff', '--check', '7185572917f7a3db5e93385a176cb611b35aff42', EXPECTED])
else:
    raise ValueError(mode)
