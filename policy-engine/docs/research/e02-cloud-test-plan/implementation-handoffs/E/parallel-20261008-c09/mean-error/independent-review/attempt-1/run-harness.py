from __future__ import annotations
import json
import os
from pathlib import Path
import resource
import subprocess
import time

here = Path(__file__).resolve().parent
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PYTHONPATH'] = '/dev/shm/e02-orch03-20261008/c09/policy-engine/src'
cmd = ['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python', str(here / 'probe.py')]
start = time.monotonic()
result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd='/dev/shm/e02-orch03-20261008/c09')
(here / 'probe.stdout.json').write_text(result.stdout)
(here / 'probe.stderr.txt').write_text(result.stderr)
record = {'command': cmd, 'cwd': '/dev/shm/e02-orch03-20261008/c09',
          'source_sha': '1b8c9e1c84d9f2e86d4b0900bf5aa54515487747',
          'source_tree': '7a4ee9e71c793827abef998540dcd12ab129c4ba',
          'env_selected': {'PYTHONDONTWRITEBYTECODE': env['PYTHONDONTWRITEBYTECODE'], 'PYTHONPATH': env['PYTHONPATH']},
          'returncode': result.returncode, 'elapsed_seconds': time.monotonic() - start,
          'child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
          'stdout_path': str(here / 'probe.stdout.json'), 'stderr_path': str(here / 'probe.stderr.txt')}
(here / 'harness.json').write_text(json.dumps(record, sort_keys=True, indent=2))
print(json.dumps(record, sort_keys=True, indent=2))
raise SystemExit(result.returncode)
