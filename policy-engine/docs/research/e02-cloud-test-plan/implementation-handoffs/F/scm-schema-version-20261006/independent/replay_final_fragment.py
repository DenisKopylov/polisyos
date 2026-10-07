"""Read-only final SCM release-fragment audit; preserve science source identity."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import tomllib

ROOT = Path('/workspace/e02-F-graph-20261006')
SCRATCH = Path('/tmp/e02-F-continuation-20261006/foundry/schema-review')
SCIENCE = 'eaf9d0e0ee2dae728351cbb3dfc333474c88931b'
FINAL = 'e94a40e78416b7392edf96f1f24c7846a808c8d0'
FINAL_TREE = '8fcab970c187cb6f15f4b3a7cb368b9f929db2fd'
FRAGMENT = 'policy-engine/release-fragments/unreleased/2026-10-06-scm-schema-catalog-version.toml'
PYTHON = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def ref(data, path, sha):
    return {'path': path, 'git_sha': sha, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def file_ref(path):
    item = ref(path.read_bytes(), str(path), FINAL)
    del item['git_sha']
    return item


def main():
    assert git('rev-parse', 'HEAD').decode().strip() == FINAL
    assert git('rev-parse', 'HEAD^{tree}').decode().strip() == FINAL_TREE
    assert not git('status', '--porcelain')
    paths = json.loads((SCRATCH / 'audit.stdout.txt').read_text().split('\n', 1)[1])['changed_paths']
    changed = git('diff', '--name-only', SCIENCE, FINAL).decode().splitlines()
    assert changed == [FRAGMENT]
    science_refs, final_refs = [], []
    for path in paths:
        old = git('show', f'{SCIENCE}:{path}')
        new = git('show', f'{FINAL}:{path}')
        assert (ROOT / path).read_bytes() == new
        if path != FRAGMENT:
            assert old == new
        science_refs.append(ref(old, path, SCIENCE))
        final_refs.append(ref(new, path, FINAL))
    old_fragment = tomllib.loads(git('show', f'{SCIENCE}:{FRAGMENT}').decode())
    new_fragment = tomllib.loads(git('show', f'{FINAL}:{FRAGMENT}').decode())
    assert len(old_fragment['compatibility_change']) == len(new_fragment['compatibility_change']) == 1
    assert old_fragment['compatibility_change'][0]['impact'] == 'migration'
    assert new_fragment['compatibility_change'][0]['impact'] == 'breaking'
    old_fragment['compatibility_change'][0]['impact'] = 'breaking'
    assert old_fragment == new_fragment
    diff = git('diff', '--numstat', SCIENCE, FINAL).decode().splitlines()
    assert diff == [f'1\t1\t{FRAGMENT}']
    command = [PYTHON, '/tmp/e02-F-continuation-20261006/graph/check-scm-public-and-fragment.py']
    env = os.environ.copy()
    env.update(PYTHONPATH=str(ROOT / 'policy-engine/src') + ':' + str(ROOT / 'policy-engine'), PYTHONDONTWRITEBYTECODE='1')
    start = time.monotonic()
    result = subprocess.run(command, cwd=ROOT / 'policy-engine', env=env, capture_output=True)
    wall = time.monotonic() - start
    out = SCRATCH / 'fragment-final.stdout.txt'
    err = SCRATCH / 'fragment-final.stderr.txt'
    out.write_bytes(result.stdout)
    err.write_bytes(result.stderr)
    assert result.returncode == 0
    assert git('rev-parse', 'HEAD').decode().strip() == FINAL and not git('status', '--porcelain')
    receipt = {
        'name': 'independent_final_fragment_and_source_identity',
        'command': ' '.join(command), 'target_sha': FINAL, 'target_tree': FINAL_TREE,
        'science_source_sha': SCIENCE,
        'environment': {'interpreter': PYTHON, 'PYTHONPATH': env['PYTHONPATH'], 'PYTHONDONTWRITEBYTECODE': '1', 'cloud_quota_introduced': False},
        'input_closure': 'Exact source-bound ten approved paths; nine bytes unchanged from eaf; sole parsed TOML impact migration→breaking and one-line delta. Actual public class identity/pickle/manual current1.1 CAS consumer and actual structured persisted-artifact-format compatibility rule.',
        'outcome': 'PASS', 'exit_code': result.returncode, 'wall_seconds': wall,
        'output': str(out), 'output_refs': [file_ref(out), file_ref(err)],
        'source_refs': final_refs, 'science_source_refs': science_refs,
        'metadata_delta': {'changed_paths': changed, 'line_counts': diff, 'other_nine_source_paths_byte_identical': True, 'parsed_toml_only_impact_changed': True},
        'scientific_reexecution': False,
        'limits': 'Original eaf fragment FAIL remains historical; no numerical repeat or full generator/production/G acceptance claim.'
    }
    (SCRATCH / 'fragment-final.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
