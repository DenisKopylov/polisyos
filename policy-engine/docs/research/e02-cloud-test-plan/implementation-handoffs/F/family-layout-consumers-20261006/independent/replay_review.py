"""Source-bound independent FRY review; writes only new scratch observations."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time

ROOT = Path('/workspace/e02-F-fry-20261006')
SCRATCH = Path(__file__).resolve().parent
SHA = '7f05b6259e0c78fac81a0baa4bff41e648a9d771'
FILES = [
    'tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py',
    'tests/unit/foundry/methods/catalog/mechanism/test_families.py',
    'tests/unit/foundry/mechanisms/test_mechanism_design.py',
    'tests/unit/foundry/contracts/test_layout.py',
    'tests/unit/foundry/compile/test_trinity_compiler.py',
]


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def digest(raw: bytes) -> dict:
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def main() -> None:
    mode = sys.argv[1]
    assert mode in ('native40', 'compiled1', 'negative3')
    assert git('rev-parse', 'HEAD').decode().strip() == SHA
    assert git('status', '--porcelain=v1') == b''
    selections = {
        'native40': FILES,
        'compiled1': ['tests/unit/foundry/compile/test_compile_artifact_contracts.py::test_native_compile_artifacts_survive_scientist_consumer_and_cas_reopen'],
        'negative3': ['tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py::test_native_registered_income_tax_patches_consume_layout_and_fresh_state'],
    }[mode]
    argv = [sys.executable, '-m', 'pytest', *selections, '-o', 'addopts=', '-q', '-ra',
            '-o', f'cache_dir={SCRATCH}/{mode}-cache', '--basetemp', str(SCRATCH / (mode + '-tmp'))]
    overrides = {'PYTHONPATH': 'src:tools'}
    if mode == 'negative3':
        argv += ['-p', 'layout_readback_removal']
        overrides['PYTHONPATH'] = str(SCRATCH) + ':src:tools'
    env = dict(os.environ, **overrides)
    start = time.monotonic()
    completed = subprocess.run(argv, cwd=ROOT / 'policy-engine', env=env, capture_output=True, timeout=900)
    wall = time.monotonic() - start
    outputs = {}
    for label, raw in [('stdout', completed.stdout), ('stderr', completed.stderr)]:
        path = SCRATCH / f'{mode}.{label}.txt'
        assert not path.exists()
        path.write_bytes(raw)
        outputs[label] = {'path': str(path), **digest(raw)}
    text = completed.stdout.decode(errors='replace')
    matches = list(re.finditer(r'(?:\d+ (?:passed|failed|skipped|warnings?|errors?)[, ]*)+in [\d.]+s', text))
    summary = matches[-1].group(0) if matches else None
    counts = {k: 0 for k in ('passed', 'failed', 'skipped', 'warnings', 'errors')}
    if summary:
        for number, key in re.findall(r'(\d+) (passed|failed|skipped|warnings?|errors?)', summary):
            counts[{'warning': 'warnings', 'error': 'errors'}.get(key, key)] = int(number)
    providers = list(dict.fromkeys(['policy-engine/' + path for path in FILES] + [
        'policy-engine/tests/unit/foundry/compile/test_compile_artifact_contracts.py',
        'policy-engine/docs/reference/foundry/state.md',
        'policy-engine/src/polisyos/foundry/methods/catalog/mechanism/families.py',
        'policy-engine/src/polisyos/foundry/mechanisms/design.py',
        'policy-engine/src/polisyos/ir/analytics/mechanism_design.py',
        'policy-engine/src/polisyos/scientist/validation/verification/ic/service.py',
        'policy-engine/src/polisyos/ir/kernel/slots.py',
        'policy-engine/src/polisyos/foundry/methods/layout.py',
        'policy-engine/src/polisyos/foundry/methods/compiler/layout.py',
        'policy-engine/src/polisyos/foundry/methods/catalog/mechanism/runtime.py',
        'policy-engine/src/polisyos/foundry/compile/trinity_compiler.py',
    ]))
    closure = []
    for path in providers:
        raw = git('show', f'{SHA}:{path}')
        assert (ROOT / path).read_bytes() == raw
        closure.append({'path': path, 'git_ref': SHA, 'git_blob': git('rev-parse', f'{SHA}:{path}').decode().strip(), **digest(raw)})
    assert git('rev-parse', 'HEAD').decode().strip() == SHA
    assert git('status', '--porcelain=v1') == b''
    record = {
        'reviewer': 'F/fit_tmle, independent of foundry author', 'source_sha': SHA,
        'source_tree': git('rev-parse', SHA + '^{tree}').decode().strip(),
        'command': argv, 'target_sha': SHA, 'environment': {'python': sys.version, 'interpreter': sys.executable,
            'platform': platform.platform(), 'cwd': str(ROOT / 'policy-engine'), 'overrides': overrides,
            'packages': {p: importlib.metadata.version(p) for p in ('pytest', 'jax', 'jaxlib', 'numpy', 'pydantic')},
            'quota_introduced': False},
        'input_closure': closure, 'outcome': 'ERROR' if not summary or counts['errors'] else 'FAIL' if completed.returncode else 'SKIP' if counts['skipped'] else 'PASS',
        'output': outputs['stdout']['path'], 'output_ref': outputs['stdout'], 'stderr_ref': outputs['stderr'],
        'exit_code': completed.returncode, 'wall_seconds': wall, 'child_max_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'counts': counts, 'pytest_summary': summary, 'mode': mode,
        'expected_outcome': 'FAIL' if mode == 'negative3' else 'PASS',
        'source_worktree_after': 'clean/attached/exact unchanged7f',
        'scope': 'Original LA002 family/certificate/runtime loading and LA037 layout/callers/compiler output bounded migration contract; no admitted real-data/global IC/unknown external retirement claim.',
    }
    if mode == 'negative3':
        record['replayer_plugin'] = {'path': str(SCRATCH / 'layout_readback_removal.py'), **digest((SCRATCH / 'layout_readback_removal.py').read_bytes())}
        record['actual_mutation'] = json.loads(text.splitlines()[0])
    path = SCRATCH / (mode + '.json')
    assert not path.exists()
    path.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'receipt': str(path), 'outcome': record['outcome'], 'exit_code': completed.returncode, 'counts': counts, 'wall_seconds': wall}))


if __name__ == '__main__':
    main()
