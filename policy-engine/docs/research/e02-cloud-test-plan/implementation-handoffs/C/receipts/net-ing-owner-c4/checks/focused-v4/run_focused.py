from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import os
import sys
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-c-net-ing-20261007/polisyos')
PRODUCT = ROOT / 'policy-engine'
RAW = ROOT / '.tmp/e02-C4/raw/stream-replay/focused-v4'
BASE = RAW / 'pytest-basetemp'
TARGETS = [
    'tests/unit/fabric/data_plane/test_net_ing_current_frontier.py',
    'tests/unit/fabric/data_plane/test_stream_cleanup_recovery.py',
    'tests/unit/fabric/data_plane/test_stream_pool_cleanup_oracle.py::test_process_file_stream_cleanup_ownership[process-disconnect-failure]',
    'tests/unit/fabric/data_plane/test_net_ing_registry_cleanup.py',
]
ARGS = [
    '-p', 'pytest_asyncio.plugin',
    '-p', 'pytest_benchmark.plugin',
    '-o', f'cache_dir={RAW / "pytest-cache"}',
    '--basetemp', str(BASE),
    *TARGETS,
]
SOURCE_PATHS = [
    'src/polisyos/fabric/data_plane/streaming.py',
    'src/polisyos/fabric/connectors/registry_core_parts.py',
    'src/polisyos/fabric/connectors/_registry_lifecycle.py',
    'src/polisyos/fabric/connectors/pool.py',
    'src/polisyos/fabric/connectors/sources/event_stream.py',
    'src/polisyos/fabric/data_plane/cursor_store.py',
    'tests/unit/fabric/data_plane/test_net_ing_current_frontier.py',
    'tests/unit/fabric/data_plane/test_stream_cleanup_recovery.py',
    'tests/unit/fabric/data_plane/test_stream_pool_cleanup_oracle.py',
    'tests/unit/fabric/data_plane/test_net_ing_registry_cleanup.py',
 ]

PRE_HEAD = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
PRE_TREE = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
PRE_HASHES = {
    path: hashlib.sha256((PRODUCT / path).read_bytes()).hexdigest()
    for path in SOURCE_PATHS
}

# The repository root conftest normally provisions a persistent Hypothesis
# database in the checkout. These targeted tests do not use Hypothesis, so make
# it unavailable before conftest collection to keep all test state under RAW.
sys.modules['hypothesis'] = None
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
started = time.monotonic()
stdout_path = RAW / 'pytest.stdout'
stderr_path = RAW / 'pytest.stderr'
with stdout_path.open('w', encoding='utf-8') as stdout_file, stderr_path.open(
    'w', encoding='utf-8'
) as stderr_file:
    with contextlib.redirect_stdout(stdout_file), contextlib.redirect_stderr(stderr_file):
        exit_code = int(pytest.main(ARGS, plugins=[]))
elapsed = time.monotonic() - started
modules = {}
for name in (
    'polisyos.fabric.data_plane.streaming',
    'polisyos.fabric.connectors.registry',
    'polisyos.fabric.connectors.pool',
    'polisyos.fabric.connectors.sources.event_stream',
    'polisyos.core.artifacts.store',
    'polisyos.fabric.data_plane.cursor_store',
):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    modules[name] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def git(command: list[str]) -> str:
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()

POST_HASHES = {
    path: hashlib.sha256((PRODUCT / path).read_bytes()).hexdigest()
    for path in SOURCE_PATHS
}
POST_HEAD = git(['git', 'rev-parse', 'HEAD'])
POST_TREE = git(['git', 'rev-parse', 'HEAD^{tree}'])

record = {
    'profile': 'observed-system-python-3.14; pytest 9.0.2; not frozen/offline venv',
    'argv': ['/opt/homebrew/opt/python@3.14/bin/python3.14', str(RAW / 'run_focused.py')],
    'pytest_args': ARGS,
    'cwd': str(PRODUCT),
    'interpreter': str(Path(sys.executable).resolve()),
    'python_version': sys.version,
    'environment': {
        key: os.environ.get(key)
        for key in ('PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD')
    },
    'sys_path_after_pytest': sys.path,
    'imported_runtime_modules': modules,
    'pre_run_head': PRE_HEAD,
    'pre_run_tree': PRE_TREE,
    'post_run_head': POST_HEAD,
    'post_run_tree': POST_TREE,
    'pre_run_hashes': PRE_HASHES,
    'post_run_hashes': POST_HASHES,
    'pre_post_hashes_identical': PRE_HASHES == POST_HASHES,
    'pre_post_git_identical': PRE_HEAD == POST_HEAD and PRE_TREE == POST_TREE,
    'source_and_test_hashes': {
        path: hashlib.sha256((PRODUCT / path).read_bytes()).hexdigest()
        for path in SOURCE_PATHS
    },
    'git_head': git(['git', 'rev-parse', 'HEAD']),
    'git_tree': git(['git', 'rev-parse', 'HEAD^{tree}']),
    'git_status': git(['git', 'status', '-sb']),
    'pytest_exit_code': exit_code,
    'elapsed_seconds': round(elapsed, 3),
    'stdout_path': str(stdout_path),
    'stderr_path': str(stderr_path),
    'stdout_sha256': hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
    'stderr_sha256': hashlib.sha256(stderr_path.read_bytes()).hexdigest(),
    'basetemp': str(BASE),
    'hypothesis_disabled_for_this_run': True,
    'plugins': ['pytest_asyncio.plugin', 'pytest_benchmark.plugin'],
}
(RAW / 'run.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({key: record[key] for key in ('pytest_exit_code', 'elapsed_seconds', 'stdout_path', 'stderr_path', 'stdout_sha256', 'stderr_sha256', 'git_head', 'git_tree')}, indent=2))
raise SystemExit(exit_code)
