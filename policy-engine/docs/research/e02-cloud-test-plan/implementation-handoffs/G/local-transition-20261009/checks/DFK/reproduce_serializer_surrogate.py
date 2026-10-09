from __future__ import annotations
import hashlib, json, os, subprocess
from pathlib import Path
repo = Path(os.environ['E02_G_ROOT']).resolve()
candidate = Path(os.environ['E02_CANDIDATE_ROOT']).resolve()
receipt = Path(os.environ['E02_RECEIPT_DIR']).resolve()
script = """import sys; import tools.quality.validation.schema_fqn_census as m; m.collect_census=lambda root: ({'selection': {'selected_paths': ['bad_\\udcff.json']}}, 0); raise SystemExit(m.main(['--repo-root', '.']))"""
cmd = [str(repo / 'policy-engine/.venv/bin/python'), '-c', script]
env = dict(os.environ)
env['PYTHONPATH'] = os.pathsep.join([str(candidate / 'policy-engine'), str(candidate / 'policy-engine/src')])
proc = subprocess.run(cmd, cwd=candidate / 'policy-engine', env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(receipt / 'serializer-surrogate.stdout.bin').write_bytes(proc.stdout)
(receipt / 'serializer-surrogate.stderr.bin').write_bytes(proc.stderr)
try:
    parsed = json.loads(proc.stdout)
    parse = {'json_parse': 'PASS', 'path_value': parsed['selection']['selected_paths'][0]}
except Exception as exc:
    parse = {'json_parse': 'FAIL', 'error_type': type(exc).__name__, 'error': str(exc)}
out = {'argv': cmd, 'candidate': str(candidate), 'exit_code': proc.returncode, 'stdout_size': len(proc.stdout), 'stdout_hex': proc.stdout.hex(), 'stdout_sha256': hashlib.sha256(proc.stdout).hexdigest(), 'stderr_hex': proc.stderr.hex(), **parse}
(receipt / 'serializer-surrogate-falsifier.json').write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
print(json.dumps(out, indent=2, sort_keys=True))
