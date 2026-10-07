from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest
from polisyos.fabric.data_plane.streaming import StreamingSourceSession

ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-c-net-ing-20261007/polisyos')
PRODUCT = ROOT / 'policy-engine'
RAW = ROOT / '.tmp/e02-C4/raw/stream-replay/focused-v3'
BASE = RAW / 'pytest-basetemp'
TEST_PATH = 'tests/unit/fabric/data_plane/test_net_ing_registry_cleanup.py::test_fresh_stream_does_not_replace_older_pending_cleanup_owner'
STREAMING_PATH = PRODUCT / 'src/polisyos/fabric/data_plane/streaming.py'
TEST_FILE = PRODUCT / 'tests/unit/fabric/data_plane/test_net_ing_registry_cleanup.py'
source_before = hashlib.sha256(STREAMING_PATH.read_bytes()).hexdigest()
test_before = hashlib.sha256(TEST_FILE.read_bytes()).hexdigest()

# Remove the semantic owner-transfer behavior in memory while leaving all
# production source and state markers untouched.
StreamingSourceSession._retain_cleanup_owner = lambda self, error: None
sys.modules['hypothesis'] = None
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
args = [
    '-p', 'pytest_asyncio.plugin',
    '-p', 'pytest_benchmark.plugin',
    '-o', f'cache_dir={RAW / "pytest-cache"}',
    '--basetemp', str(BASE),
    TEST_PATH,
]
stdout_path = RAW / 'pytest.stdout'
stderr_path = RAW / 'pytest.stderr'
started = time.monotonic()
with stdout_path.open('w', encoding='utf-8') as stdout_file, stderr_path.open(
    'w', encoding='utf-8'
) as stderr_file:
    with contextlib.redirect_stdout(stdout_file), contextlib.redirect_stderr(stderr_file):
        pytest_exit = int(pytest.main(args, plugins=[]))
elapsed = time.monotonic() - started
stdout = stdout_path.read_text(encoding='utf-8')
source_after = hashlib.sha256(STREAMING_PATH.read_bytes()).hexdigest()
test_after = hashlib.sha256(TEST_FILE.read_bytes()).hexdigest()
expected_assertion = 'AssertionError: registry must retain the old cleanup obligation'
probe_verdict = (
    'EXPECTED_PROPERTY_REMOVAL_RED'
    if pytest_exit == 1 and expected_assertion in stdout and '1 failed' in stdout
    else 'UNEXPECTED_REMOVAL_CONTROL_RESULT'
)
record = {
    'profile': 'observed-system-python-3.14; pytest 9.0.2; not frozen/offline venv',
    'argv': ['/opt/homebrew/opt/python@3.14/bin/python3.14', str(RAW / 'run_remove_property.py')],
    'pytest_args': args,
    'cwd': str(PRODUCT),
    'python_version': sys.version,
    'environment': {
        key: os.environ.get(key)
        for key in ('PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD')
    },
    'removed_property': 'StreamingSourceSession._retain_cleanup_owner replaced with in-memory no-op',
    'markers_or_source_files_changed': False,
    'streaming_source_sha256_before': source_before,
    'streaming_source_sha256_after': source_after,
    'test_file_sha256_before': test_before,
    'test_file_sha256_after': test_after,
    'pytest_exit_code': pytest_exit,
    'elapsed_seconds': round(elapsed, 3),
    'expected_failure_assertion': expected_assertion,
    'probe_verdict': probe_verdict,
    'stdout_path': str(stdout_path),
    'stderr_path': str(stderr_path),
    'stdout_sha256': hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
    'stderr_sha256': hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
    'basetemp': str(BASE),
}
(RAW / 'run.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({key: record[key] for key in ('pytest_exit_code', 'elapsed_seconds', 'probe_verdict', 'expected_failure_assertion', 'streaming_source_sha256_before', 'streaming_source_sha256_after', 'stdout_sha256', 'stderr_sha256')}, indent=2))
raise SystemExit(0 if probe_verdict == 'EXPECTED_PROPERTY_REMOVAL_RED' else 1)
