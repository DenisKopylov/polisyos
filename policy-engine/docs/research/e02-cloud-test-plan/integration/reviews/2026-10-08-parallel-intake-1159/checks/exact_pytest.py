import hashlib
import json
import subprocess
import sys
from pathlib import Path

root, checkout, sha, out, selectors_file = map(Path, sys.argv[1:])
sha = str(sha)
sys.path.insert(0, str(checkout / 'policy-engine/src'))
import pytest

selectors = json.loads(selectors_file.read_text())
rc = pytest.main(['-q', '-ra', '-o', 'addopts=', '-p', 'no:cacheprovider',
                 *selectors, '--basetemp=' + str(out / 'pytest-temp'),
                 '--junitxml=' + str(out / 'junit.xml')])
origins = []
bad = []
tree = subprocess.check_output(['git', 'ls-tree', '-r', sha, 'policy-engine/src'], cwd=root)
blobs = {}
for row in tree.splitlines():
    meta, path = row.split(b'\t', 1)
    blobs[path.decode()] = meta.split()[2].decode()
for name, module in sorted(sys.modules.items()):
    if name != 'polisyos' and not name.startswith('polisyos.'):
        continue
    file = getattr(module, '__file__', None)
    if not file:
        continue
    path = Path(file).resolve()
    try:
        relative = path.relative_to(checkout).as_posix()
    except ValueError:
        bad.append({'module': name, 'path': str(path), 'reason': 'outside_exact_source'})
        continue
    content = path.read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    row = {'module': name, 'path': relative, 'blob': actual, 'candidate_blob': blobs.get(relative)}
    origins.append(row)
    if actual != row['candidate_blob']:
        bad.append(row)
result = {'source_sha': sha, 'pytest_returncode': int(rc),
          'loaded_file_backed_polisyos_module_denominator': len(origins),
          'source_mismatch_count': len(bad)}
(out / 'origins.json').write_text(json.dumps({'summary': result, 'origins': origins,
                                            'mismatches': bad}, indent=2) + '\n')
print(json.dumps(result))
raise SystemExit(int(rc) if not bad else 9)
