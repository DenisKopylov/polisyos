"""Capture full metadata replayer streams and execution identity; no product test."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--repo', required=True)
ap.add_argument('--target', required=True)
ap.add_argument('--stem', required=True)
ap.add_argument('command', nargs=argparse.REMAINDER)
a = ap.parse_args()
command = a.command[1:] if a.command[:1] == ['--'] else a.command
start = time.time()
run = subprocess.run(command, capture_output=True)
prefix = Path(a.stem)
def artifact(path):
    value = path.read_bytes()
    return dict(path=str(path.absolute()),bytes=len(value),sha256=hashlib.sha256(value).hexdigest())
refs = {}
for channel,value in [('stdout',run.stdout),('stderr',run.stderr)]:
    path = prefix.with_suffix('.'+channel)
    path.write_bytes(value)
    refs[channel] = artifact(path)
execution = dict(command=command,cwd=str(Path.cwd()),exit=run.returncode,elapsed_s=time.time()-start,environment=dict(python=platform.python_version(),executable=sys.executable,purpose='stdlib immutable Git metadata verification only'),target=dict(sha=a.target,tree=subprocess.check_output(['git','rev-parse',a.target+'^{tree}'],cwd=a.repo).decode().strip()),capture_replayer=artifact(Path(__file__)),scope_guard='All deciding reads immutable target Gitshow; no repo writes',**refs)
prefix.with_suffix('.execution.json').write_text(json.dumps(execution,indent=2)+'\n')
sys.stdout.buffer.write(run.stdout)
sys.stderr.buffer.write(run.stderr)
raise SystemExit(run.returncode)
