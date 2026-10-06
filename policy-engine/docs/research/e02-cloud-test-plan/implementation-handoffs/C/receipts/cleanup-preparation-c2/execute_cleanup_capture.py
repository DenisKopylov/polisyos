"""Capture one root-authorized Trash-only operation; never remove files."""
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

root = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos')
script = root / '.tmp/e02-C2/raw/cleanup/move_released_to_trash.py'
expected_sha = '5dfe312ea92a95956046291a9d8bd776aa8e610b6ad70e952c077d4cf0efa611'
selection, release, out, capture = map(Path, sys.argv[1:5])
if any(not p.is_absolute() for p in (selection, release, out, capture)):
    raise RuntimeError('Exact absolute inputs required')
if capture.exists():
    raise RuntimeError('Capture already exists')
source = script.read_bytes()
if hashlib.sha256(source).hexdigest() != expected_sha:
    raise RuntimeError('Frozen mover source drift')
inputs = {str(p): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in (script, selection, release)}
argv = [sys.executable, '-I', str(script), str(selection), str(release), str(out)]
started = datetime.now(timezone.utc).isoformat()
tick = time.monotonic()
run = subprocess.run(argv, cwd=root, capture_output=True)
finished = datetime.now(timezone.utc).isoformat()
record = {'schema': 'policyos.e02.C.cleanup.execution_capture.v1', 'argv': argv, 'cwd': str(root), 'started_utc': started, 'finished_utc': finished, 'wall_seconds': time.monotonic()-tick, 'inputs_pre': inputs, 'exit_code': run.returncode, 'stdout': run.stdout.decode('utf-8'), 'stderr': run.stderr.decode('utf-8'), 'script_bytes_identical_after': script.read_bytes() == source, 'production_data_read_or_modified': False}
with capture.open('x') as f:
    json.dump(record, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'exit_code':run.returncode,'capture':str(capture),'sha256':hashlib.sha256(capture.read_bytes()).hexdigest(),'stdout':record['stdout']}))
sys.exit(run.returncode)
