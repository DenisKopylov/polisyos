from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

base = Path(__file__).resolve().parent
root = Path('/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos')
candidate_root = base / 'candidate' / 'policy-engine'
result_dir = base / 'results' / 'attempt2'
result_dir.mkdir(parents=True, exist_ok=True)
python = root / 'policy-engine/.venv/bin/python'
env = {
    **os.environ,
    'PYTHONPATH': str(candidate_root / 'src'),
    'PYTHONNOUSERSITE': '1',
    'PYTHONDONTWRITEBYTECODE': '1',
    'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
    'C_CANON_GROOT': str(root),
}
argv = [str(python), '-B', str(base / 'probe_runner.py')]
stdout_path = result_dir / 'stdout.txt'
stderr_path = result_dir / 'stderr.txt'
receipt_path = result_dir / 'supervisor-receipt.json'
preflight_path = base / 'preflight-attempt2.json'
preflight_sha = hashlib.sha256(preflight_path.read_bytes()).hexdigest()
disk_before = shutil.disk_usage(root).free
start_wall = time.monotonic()
started = dt.datetime.now(dt.timezone.utc).isoformat()
timed_out = False
try:
    proc = subprocess.run(argv, cwd=candidate_root, env=env, capture_output=True, timeout=180)
    exit_code = proc.returncode
    out = proc.stdout
    err = proc.stderr
except subprocess.TimeoutExpired as exc:
    timed_out = True
    exit_code = None
    out = exc.stdout or b''
    err = exc.stderr or b''
wall = time.monotonic() - start_wall
ended = dt.datetime.now(dt.timezone.utc).isoformat()
stdout_path.write_bytes(out)
stderr_path.write_bytes(err)
disk_after = shutil.disk_usage(root).free
receipt = {
    'candidate_sha': '55b45d9a5c95c3b773fc3b4d8679786b3993eb1e',
    'candidate_tree': '70ed14e004063536ff3a12d30d14d9bdd79a4916',
    'argv': argv,
    'cwd': str(candidate_root),
    'timeout_seconds': 180,
    'timed_out': timed_out,
    'environment': {k: env[k] for k in ('PYTHONPATH', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'C_CANON_GROOT')},
    'python_version': subprocess.check_output([str(python), '--version'], text=True).strip(),
    'started_utc': started,
    'ended_utc': ended,
    'wall_seconds': wall,
    'disk_free_bytes_before': disk_before,
    'disk_free_bytes_after': disk_after,
    'source_preflight_sha256': preflight_sha,
    'exit_code': exit_code,
    'stdout_path': str(stdout_path),
    'stderr_path': str(stderr_path),
    'stdout_bytes': len(out),
    'stderr_bytes': len(err),
    'stdout_sha256': hashlib.sha256(out).hexdigest(),
    'stderr_sha256': hashlib.sha256(err).hexdigest(),
    'child_maxrss_platform_units': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    'pytest_junit_path': str(result_dir / 'pytest.junit.xml'),
    'runner_result_path': str(result_dir / 'runner-result.json'),
    'module_origins_path': str(result_dir / 'module-origins.json'),
}
receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
