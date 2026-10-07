"""Capture immutable native consumer and retained-marker negative executions."""
from pathlib import Path
import hashlib
import json
import os
import resource
import subprocess
import sys
import time

ROOT = Path('/workspace/e02-F-economics-20261006')
OUT = Path('/tmp/e02-F-continuation-20261006/fit-fiscal-review')
PYTHON = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
SHA = sys.argv[1]
BASE = sys.argv[2]
paths = ['policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py',
         'policy-engine/src/polisyos/foundry/mechanisms/fiscal.py',
         'policy-engine/src/polisyos/foundry/_registry.py',
         'policy-engine/src/polisyos/foundry/compile/api.py',
         'policy-engine/src/polisyos/foundry/execute/api.py',
         'policy-engine/src/polisyos/foundry/execute/executor.py',
         'policy-engine/src/polisyos/foundry/contracts/state.py',
         'policy-engine/src/polisyos/ir/kernel/slots.py',
         'policy-engine/tests/unit/foundry/execute/mechanisms/test_fiscal_precision.py',
         'policy-engine/tests/unit/foundry/mechanisms/test_fiscal.py',
         'policy-engine/docs/reference/foundry/fiscal-calculation-dtype.md',
         'policy-engine/release-fragments/unreleased/2026-10-06-economic-fiscal-calculation-dtype.toml']
(OUT / 'source-paths.json').write_text(json.dumps(paths, indent=2) + '\n')
env = os.environ.copy()
env.update({'PYTHONPATH': str(ROOT / 'policy-engine/src') + ':' + str(ROOT / 'policy-engine') + ':' + str(ROOT / 'policy-engine/tools'),
            'PYTHONDONTWRITEBYTECODE': '1', 'FISCAL_REVIEW_SHA': SHA,
            'FISCAL_REVIEW_BASE_SHA': BASE, 'FISCAL_REVIEW_PATHS': str(OUT / 'source-paths.json')})

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

assert git('rev-parse', 'HEAD').decode().strip() == SHA
assert not git('diff', '--name-only')
assert not git('diff', '--cached', '--name-only')
bindings = []
for path in paths:
    raw = (ROOT / path).read_bytes()
    assert raw == git('show', SHA + ':' + path)
    bindings.append({'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                     'git_blob': git('rev-parse', SHA + ':' + path).decode().strip()})
(OUT / 'source-bindings.json').write_text(json.dumps({'source_sha': SHA,
    'tree': git('rev-parse', 'HEAD^{tree}').decode().strip(), 'base': BASE, 'paths': bindings}, indent=2) + '\n')

runs = []
for name, argv in [
    ('native', [PYTHON, '-m', 'pytest', str(OUT / 'test_fiscal_independent.py'),
        'tests/unit/foundry/execute/mechanisms/test_fiscal_precision.py',
        'tests/unit/foundry/mechanisms/test_fiscal.py', '-o', 'addopts=', '-p', 'no:cacheprovider',
        '-q', '-s', '--tb=short', '--basetemp=' + str(OUT / 'native-tmp')]),
    ('removal', [PYTHON, str(OUT / 'remove_early_precision.py')]),
]:
    assert git('rev-parse', 'HEAD').decode().strip() == SHA
    for row in bindings:
        assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['sha256']
    start = time.monotonic()
    process = subprocess.run(argv, cwd=ROOT / 'policy-engine', env=env, capture_output=True)
    stdout, stderr = OUT / (name + '.stdout.txt'), OUT / (name + '.stderr.txt')
    stdout.write_bytes(process.stdout)
    stderr.write_bytes(process.stderr)
    record = {'name': name, 'source_sha': SHA, 'source_tree': git('rev-parse', 'HEAD^{tree}').decode().strip(),
        'baseline_sha': BASE, 'argv': argv, 'cwd': str(ROOT / 'policy-engine'),
        'environment': {k: env[k] for k in ('PYTHONPATH', 'PYTHONDONTWRITEBYTECODE',
            'FISCAL_REVIEW_SHA', 'FISCAL_REVIEW_BASE_SHA', 'FISCAL_REVIEW_PATHS')},
        'inherited_environment': True, 'artificial_cloud_quota': False,
        'exit_code': process.returncode, 'wall_seconds': time.monotonic() - start,
        'peak_child_rss_kib_cumulative': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'stdout': {'path': str(stdout), 'bytes': len(process.stdout), 'sha256': hashlib.sha256(process.stdout).hexdigest()},
        'stderr': {'path': str(stderr), 'bytes': len(process.stderr), 'sha256': hashlib.sha256(process.stderr).hexdigest()},
        'source_status_after': git('status', '--porcelain').decode()}
    assert git('rev-parse', 'HEAD').decode().strip() == SHA
    for row in bindings:
        assert hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['sha256']
    (OUT / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    runs.append(record)
    print(json.dumps({'name': name, 'exit_code': process.returncode, 'wall_seconds': record['wall_seconds'],
        'stdout_bytes': len(process.stdout), 'stderr_bytes': len(process.stderr)}), flush=True)
(OUT / 'runs.json').write_text(json.dumps(runs, indent=2) + '\n')
