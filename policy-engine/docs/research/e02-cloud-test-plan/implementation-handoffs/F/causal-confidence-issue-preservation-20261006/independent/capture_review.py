"""Read-only immutable Confidence native/independent evidence capture."""
from pathlib import Path
import hashlib
import json
import os
import resource
import subprocess
import sys
import time

ROOT = Path('/workspace/e02-F-tmle-20261006')
ENGINE = ROOT / 'policy-engine'
SCRATCH = Path(__file__).parent
PYTHON = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
EXPECTED = 'df5057dd3816885fc5bfacd9a9f1ee772df9ac51'
mode = sys.argv[1]
if mode == 'native':
    cmd = [PYTHON, '-m', 'pytest',
        'tests/unit/scientist/governance/test_confidence_issue_accumulation.py',
        'tests/unit/scientist/governance/test_causal_confidence_candidate.py',
        'tests/unit/scientist/governance/test_confidence_pass.py',
        '-o', 'addopts=', '-o', 'cache_dir='+str(SCRATCH / 'native-cache'), '-q', '-ra',
        '--basetemp='+str(SCRATCH / 'native-tmp')]
elif mode == 'mixed-corrected':
    cmd = [PYTHON, '-m', 'pytest', str(SCRATCH / 'test_mixed_refs.py'),
        '-o', 'addopts=', '-o', 'cache_dir='+str(SCRATCH / 'mixed-corrected-cache'), '-q', '-s',
        '--tb=short', '--basetemp='+str(SCRATCH / 'mixed-corrected-tmp')]
elif mode == 'removal':
    cmd = [PYTHON, str(SCRATCH / 'remove_retention.py')]
else:
    raise ValueError(mode)
before = subprocess.check_output(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}'], cwd=ROOT, text=True).splitlines()
assert before[0] == EXPECTED, before
env = os.environ.copy()
env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ENGINE)+':'+str(ENGINE/'src')+':'+str(ENGINE/'tools'), TMPDIR='/tmp')
start = time.monotonic()
r = subprocess.run(cmd, cwd=ENGINE, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
wall = time.monotonic()-start
after = subprocess.check_output(['git', 'rev-parse', 'HEAD', 'HEAD^{tree}'], cwd=ROOT, text=True).splitlines()
assert after == before, (before, after)
refs = {}
for key, b in [('stdout', r.stdout), ('stderr', r.stderr)]:
    f = SCRATCH / (mode+'.'+key+'.txt'); f.write_bytes(b)
    refs[key] = {'path': str(f), 'sha256': hashlib.sha256(b).hexdigest(), 'size_bytes': len(b)}
record = {'source_sha': before[0], 'source_tree': before[1], 'after_sha_tree': after,
    'command': cmd, 'cwd': str(ENGINE), 'exit_code': r.returncode, 'wall_seconds': wall,
    'child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    'environment': {'python': PYTHON, 'PYTHONPATH': env['PYTHONPATH'],
        'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': '/tmp', 'shared_venv_read_only': True,
        'resource_caps_added': False}, 'outputs': refs}
(SCRATCH/(mode+'.json')).write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record));print(r.stdout.decode()[-6000:]);print(r.stderr.decode())
