"""One frozen delta wave on existing native method/IR/value consumers."""
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

ROOT = Path('/workspace/e02-F-tmle-20261006')
SCRATCH = Path(__file__).resolve().parent
SHA = '2577a3fa7f11fdaf596d30b364d6ad527d4430b6'
PUBLISHED = '8e4f98569959570df1916c4a92271e9a60084c19'
FILES = [
    'tests/unit/foundry/methods/catalog/causal/test_did.py',
    'tests/unit/foundry/methods/catalog/causal/test_rdd.py',
    'tests/unit/foundry/methods/catalog/causal/test_synthetic_control.py',
    'tests/unit/foundry/methods/catalog/causal/test_structural_time_series.py',
    'tests/unit/ir/test_uncertainty.py',
    'tests/unit/ir/analytics/test_estimand_normalization.py',
    'tests/unit/ir/mirror_contracts/test_causal.py',
    'tests/unit/foundry/methods/test_value_evidence.py',
]


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def digest(raw: bytes) -> dict:
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def binding(path: str) -> dict:
    raw = git('show', f'{SHA}:{path}')
    assert (ROOT / path).read_bytes() == raw
    return {'path': path, 'git_ref': SHA, 'git_blob': git('rev-parse', f'{SHA}:{path}').decode().strip(), **digest(raw)}


def main() -> None:
    assert git('rev-parse', 'HEAD').decode().strip() == PUBLISHED
    assert git('status', '--porcelain=v1') == b''
    assert git('diff', '--name-only', SHA, PUBLISHED, '--', 'policy-engine/src', 'policy-engine/tests') == b''
    source = [binding('policy-engine/' + path) for path in FILES]
    for path in git('diff', '--name-only', SHA + '^', SHA).decode().splitlines():
        source.append(binding(path))
    carrier = SCRATCH / 'test_causal_identification_consumer.py'
    argv = [sys.executable, '-m', 'pytest', '-o', 'addopts=', '-q',
            '-o', f'cache_dir={SCRATCH}/final-neighbor-cache', '--basetemp', str(SCRATCH / 'final-neighbor-tmp'),
            *FILES, str(carrier)]
    env = dict(os.environ, PYTHONPATH='src:.')
    start = time.monotonic()
    timeout = False
    try:
        completed = subprocess.run(argv, cwd=ROOT / 'policy-engine', env=env, capture_output=True, timeout=900)
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, exit_code, timeout = exc.stdout or b'', exc.stderr or b'', None, True
    wall = time.monotonic() - start
    out = {}
    for label, raw in [('stdout', stdout), ('stderr', stderr)]:
        path = SCRATCH / f'final-neighbor.{label}.txt'
        assert not path.exists()
        path.write_bytes(raw)
        out[label] = {'path': str(path), **digest(raw)}
    text = stdout.decode(errors='replace')
    matches = list(re.finditer(r'(?:\d+ (?:passed|failed|skipped|warnings?|errors?)[, ]*)+in [\d.]+s', text))
    summary = matches[-1].group(0) if matches else None
    counts = {key: 0 for key in ('passed', 'failed', 'skipped', 'warnings', 'errors')}
    if summary:
        for count, key in re.findall(r'(\d+) (passed|failed|skipped|warnings?|errors?)', summary):
            counts[{'warning': 'warnings', 'error': 'errors'}.get(key, key)] = int(count)
    outcome = 'ERROR' if timeout or not summary or counts['errors'] else 'FAIL' if exit_code else 'SKIP' if counts['skipped'] else 'PASS'
    record = {
        'source_sha': SHA, 'source_tree': git('rev-parse', SHA + '^{tree}').decode().strip(),
        'launch_head': PUBLISHED, 'launch_head_source_tests_byte_identical_to_source': True,
        'argv': argv, 'cwd': str(ROOT / 'policy-engine'), 'environment_overrides': {'PYTHONPATH': 'src:.'},
        'python': {'executable': sys.executable, 'version': sys.version, 'platform': platform.platform()},
        'versions': {p: importlib.metadata.version(p) for p in ('pytest', 'numpy', 'scipy', 'pydantic', 'statsmodels')},
        'timeout_seconds': 900, 'timeout': timeout, 'exit_code': exit_code, 'wall_seconds': wall,
        'child_max_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'child_rss_scope': 'Wrapper child-process high-water mark, including small pre-test Git readback children; Linux KiB.',
        'no_artificial_cpu_process_thread_quota_introduced': True,
        'outcome': outcome, 'counts': counts, 'pytest_summary': summary, 'outputs': out,
        'input_closure': source, 'scratch_test': {'path': str(carrier), **digest(carrier.read_bytes())},
        'scope': 'Focused existing native DID/RDD/synthetic-control/structural-time-series, uncertainty/estimand/value-evidence consumers and unique adversarial CAS reader carrier; no full integration or real-data admission claim.',
        'static_mirror_test_scope': 'IR mirror-contract file is a structural companion, not identification or numerical evidence.',
    }
    path = SCRATCH / 'final-neighbor.json'
    assert not path.exists()
    path.write_text(json.dumps(record, indent=2) + '\n')
    assert git('status', '--porcelain=v1') == b''
    print(json.dumps({'receipt': str(path), 'outcome': outcome, 'exit_code': exit_code, 'wall_seconds': wall, 'counts': counts}))


if __name__ == '__main__':
    main()
