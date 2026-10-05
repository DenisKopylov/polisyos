import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
parser.add_argument('--target', required=True)
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command
assert command
output = Path(args.output).resolve()
assert not output.exists(), 'fresh output prefix required'
output.parent.mkdir(parents=True, exist_ok=True)
def git(*argv):
    return subprocess.check_output(['git', *argv], text=True).strip()
before = {'sha': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'), 'branch': git('symbolic-ref', 'HEAD'), 'status': git('status', '--porcelain')}
assert before['sha'] == args.target and not before['status']
origins = {}
for name in ['polisyos.fabric.connectors.pool', 'pytest', 'numpy', 'orjson', 'pydantic', 'jax', 'duckdb']:
    origin = importlib.util.find_spec(name).origin
    origins[name] = {'path': origin}
    if origin and Path(origin).is_file():
        origins[name]['sha256'] = hashlib.sha256(Path(origin).read_bytes()).hexdigest()
started = datetime.now(timezone.utc).isoformat()
clock = time.monotonic()
log = output.with_suffix('.log')
with log.open('wb') as stream:
    child = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
elapsed = time.monotonic() - clock
after = {'sha': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'), 'branch': git('symbolic-ref', 'HEAD'), 'status': git('status', '--porcelain')}
result = {'schema': 'policyos.e02.check.v1', 'command': command, 'cwd': os.getcwd(), 'target_sha': args.target, 'source_before': before, 'source_after': after, 'source_unchanged': before == after, 'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(), 'wall_s': elapsed, 'maxrss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss, 'resource_measurement': 'Linux resource.getrusage(RUSAGE_CHILDREN) cumulative child peak; no process/thread quota imposed', 'exit_code': child.returncode, 'environment': {'PYTHONPATH': os.getenv('PYTHONPATH'), 'POLISYOS_METRICS_PORT': os.getenv('POLISYOS_METRICS_PORT'), 'python_executable': sys.executable, 'python': sys.version, 'platform': platform.platform(), 'versions': {name: importlib.metadata.version(name) for name in ['pytest', 'numpy', 'orjson', 'pydantic', 'jax', 'duckdb']}, 'module_origins': origins}, 'input_closure': 'Frozen tree-selected source/tests/conftest/config and existing shared installed venv; complete command and wrapper retained, own unique tmp/cache/JUnit path. Synthetic events and actual pool path; no live TCP/DB/data except existing whole-file fixtures. Optional backend/data absence stays declared.', 'log': {'path': str(log), 'bytes': log.stat().st_size, 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()}, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({'exit_code': child.returncode, 'wall_s': elapsed, 'maxrss_kib': result['maxrss_kib'], 'source_unchanged': before == after, 'log': str(log)}))
sys.exit(child.returncode)
