"""Verify the approved fragment-only append preserves the scientific source."""
import ast
import hashlib
import json
import pathlib
import subprocess
import tomllib

root = pathlib.Path('/workspace/e02-F-graph-20261006')
scientific = 'eaf9d0e0ee2dae728351cbb3dfc333474c88931b'
base = '5b748047b4d5dfbee1e31721a8cec3a4ead2ace1'
fragment = 'policy-engine/release-fragments/unreleased/2026-10-06-scm-schema-catalog-version.toml'
current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
paths = subprocess.check_output(['git', 'diff', '--name-only', base, scientific], cwd=root, text=True).splitlines()
delta = subprocess.check_output(['git', 'diff', '--name-only', scientific, current], cwd=root, text=True).splitlines()
assert delta == [fragment], delta
refs = []
for path in paths:
    before = subprocess.check_output(['git', 'show', scientific + ':' + path], cwd=root)
    after = subprocess.check_output(['git', 'show', current + ':' + path], cwd=root)
    assert (root / path).read_bytes() == after, path
    if path == fragment:
        old = tomllib.loads(before.decode())
        new = tomllib.loads(after.decode())
        assert old['compatibility_change'][0]['impact'] == 'migration'
        assert new['compatibility_change'][0]['impact'] == 'breaking'
        old['compatibility_change'][0]['impact'] = 'breaking'
        assert old == new
    else:
        assert before == after, path
        if path.endswith('.py'):
            assert ast.dump(ast.parse(before)) == ast.dump(ast.parse(after))
    refs.append({'source_path': path, 'scientific_sha': scientific,
                 'current_sha': current, 'bytes': len(after),
                 'sha256': hashlib.sha256(after).hexdigest(),
                 'scientific_bytes_unchanged': path != fragment})
assert len(paths) == 10
print(json.dumps({'check': 'PASS', 'scientific_runtime_sha': scientific,
                  'metadata_sha': current, 'delta_paths': delta,
                  'unchanged_source_paths': 9,
                  'fragment_only_semantic_delta': 'compatibility_change[0].impact migration -> breaking',
                  'source_refs': refs}, indent=2))
