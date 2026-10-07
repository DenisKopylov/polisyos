"""Execute unchanged native persisted consumer in the selected installed -I profile."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
sys.dont_write_bytecode = True
script, spec, proofs, site_arg, source_sha = sys.argv[1:]
site = Path(site_arg).resolve()
assert sys.flags.isolated == 1
assert Path(sys.prefix).resolve() == site.parents[2].resolve()
assert not (Path.cwd() / 'src').exists()
sys.argv = [script, '--reader', spec]
buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    runpy.run_path(script, run_name='__main__')
origins = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.copy().items()
           if name.startswith(('polisyos', 'tools')) and getattr(module, '__file__', None)}
violations = {name: path for name, path in origins.items() if not Path(path).is_relative_to(site)}
assert origins and not violations, violations
body = {'source_sha': source_sha, 'site': str(site), 'isolated': sys.flags.isolated,
        'product_origins': origins, 'origin_violations': violations}
raw = (json.dumps(body, sort_keys=True, indent=2)+'\n').encode()
hash_value = hashlib.sha256(raw).hexdigest()
path = Path(proofs) / (hash_value+'.json')
if path.exists():
    assert path.read_bytes() == raw
else:
    path.write_bytes(raw)
print(json.dumps({'installed_reader_observer': {'source_sha': source_sha, 'isolated': 1,
    'product_origins': len(origins), 'origin_violations': 0, 'proof': str(path),
    'proof_sha256': hash_value, 'proof_bytes': len(raw)}}))
# Native report/issue observation remains the last line for the original frozen assertion.
print(buffer.getvalue(), end='')
