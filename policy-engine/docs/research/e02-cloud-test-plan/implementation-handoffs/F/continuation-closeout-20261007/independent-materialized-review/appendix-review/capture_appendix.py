"""Capture one read-only narrow appendix check without altering root files."""
import hashlib
import json
import pathlib
import subprocess
import sys
import time

p = pathlib.Path(__file__).resolve().parent
script = p / 'verify_appendix.py'
argv = [sys.executable, str(script)]
started = time.monotonic()
run = subprocess.run(argv, cwd=p, capture_output=True)
record = {'argv': argv, 'cwd': str(p), 'Python': sys.version.split()[0],
          'scope': 'Precommit appendix bytes only; stdlib/read-only Git; no main transport decode or science.',
          'script_bytes': script.stat().st_size, 'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
          'exit_code': run.returncode, 'wall_seconds': time.monotonic() - started}
for name, raw in [('stdout', run.stdout), ('stderr', run.stderr)]:
    f = p / (name + ('.json' if name == 'stdout' else '.txt'))
    f.write_bytes(raw)
    record[name] = {'path': str(f), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
(p / 'execution.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
sys.exit(run.returncode)
