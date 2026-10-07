"""Bind both distribution archives to the complete frozen product denominator."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile
import zipfile

ROOT = Path('/workspace/e02-F-api-20261006')
SCRATCH = Path('/tmp/e02-F-continuation-20261006/api')
SOURCE = '5484db7a25014953bdab7cb2418df735f972ff93'
raw = subprocess.check_output(['git', 'ls-tree', '-rz', '--full-tree', SOURCE], cwd=ROOT)
entries = {}
for member in raw.split(b'\0'):
    if not member:
        continue
    metadata, path = member.split(b'\t', 1)
    mode, kind, oid = metadata.decode().split()
    name = path.decode()
    if name.startswith(('policy-engine/src/polisyos/', 'policy-engine/tools/')):
        assert kind == 'blob' and mode in ('100644', '100755'), (name, mode, kind)
        entries[name] = oid
resource_source = 'policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml'
resource_oid = subprocess.check_output(['git', 'rev-parse', SOURCE + ':' + resource_source], cwd=ROOT, text=True).strip()
queries = [*entries.values(), resource_oid]
batch = subprocess.run(['git', 'cat-file', '--batch'], input=('\n'.join(queries) + '\n').encode(), cwd=ROOT, stdout=subprocess.PIPE, check=True)
stream = io.BytesIO(batch.stdout)
contents = []
for expected in queries:
    header = stream.readline().decode().strip().split()
    assert len(header) == 3 and header[0] == expected and header[1] == 'blob', header
    content = stream.read(int(header[2]))
    assert stream.read(1) == b'\n'
    contents.append(content)
assert not stream.read()
wheel = SCRATCH / 'dist-5484/policy_engine-0.1.0-py3-none-any.whl'
sdist = SCRATCH / 'dist-5484/policy_engine-0.1.0.tar.gz'
rows = []
with zipfile.ZipFile(wheel) as whl, tarfile.open(sdist) as tar:
    prefix = next(iter(tar.getnames())).split('/')[0] + '/'
    cache = [name for name in whl.namelist() if '/_cache/' in '/' + name]
    cache += [name for name in tar.getnames() if '/_cache/' in '/' + name]
    assert not cache, cache
    for (path, oid), content in zip(entries.items(), contents, strict=False):
        wheel_path = path.removeprefix('policy-engine/src/').removeprefix('policy-engine/')
        sdist_path = prefix + path.removeprefix('policy-engine/')
        assert whl.read(wheel_path) == content, ('wheel', path)
        reader = tar.extractfile(sdist_path)
        assert reader is not None and reader.read() == content, ('sdist', path)
        rows.append({'path': path, 'git_blob': oid, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    resource_dest = 'polisyos/foundry/methods/catalog/_resources/method_catalog_dependency_digest_domains.toml'
    assert whl.read(resource_dest) == contents[-1]
    resource_reader = tar.extractfile(prefix + resource_source.removeprefix('policy-engine/'))
    assert resource_reader is not None and resource_reader.read() == contents[-1]
    product_names = [name for name in whl.namelist() if name.startswith(('polisyos/', 'tools/')) and not name.endswith('/')]
    assert set(product_names) == {p.removeprefix('policy-engine/src/').removeprefix('policy-engine/') for p in entries} | {resource_dest}
proof = {'source_sha': SOURCE, 'tracked_product_files': len(entries), 'archived_product_files_verified': len(rows),
         'wheel_product_entries': len(product_names), 'cache_members': cache, 'source_bindings': rows,
         'forced_resource': {'source': resource_source, 'git_blob': resource_oid, 'destination': resource_dest},
         'scope': 'Every tracked product file is byte-equal to exact frozen Git blob in both archives; wheel extra resource separately reconciled.',
         'artifacts': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size, 'source_sha': SOURCE} for p in (wheel, sdist)]}
(SCRATCH / 'artifact-bindings-current.json').write_text(json.dumps(proof, indent=2) + '\n')
with zipfile.ZipFile(wheel) as whl:
    for kind in ('wheel','sdist'):
        site=SCRATCH / (kind+'-env-retry-5484/lib/python3.14/site-packages')
        for name in product_names:
            assert (site/name).read_bytes()==whl.read(name),(kind,name)
        actual_python={p.relative_to(site).as_posix() for folder in ('polisyos','tools') for p in (site/folder).rglob('*.py')}
        expected_python={name for name in product_names if name.endswith('.py')}
        assert actual_python==expected_python,(kind,actual_python-expected_python,expected_python-actual_python)
proof['installations']=[str(SCRATCH / (kind+'-env-retry-5484/lib/python3.14/site-packages')) for kind in ('wheel','sdist')]
proof['all_installed_product_files_verified']=len(product_names)
(SCRATCH / 'artifact-bindings-current.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'source_sha': SOURCE, 'tracked_product_files': len(entries), 'all_archive_bindings': len(rows), 'wheel_product_entries': len(product_names), 'cache_members': cache}))
