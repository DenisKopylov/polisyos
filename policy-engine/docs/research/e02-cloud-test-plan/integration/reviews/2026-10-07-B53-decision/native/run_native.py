from __future__ import annotations
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path('/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos')
OUT = ROOT / 'policy-engine/_build/e02-g-continuation-20261006/R/B-stop-53b-20261007/native'
CANDIDATE = OUT / 'candidate'
PRODUCT = CANDIDATE / 'policy-engine'
SRC = PRODUCT / 'src'
MANIFEST = OUT / 'source-manifest.json'
RESULTS = OUT / 'results'
RESULTS.mkdir(exist_ok=True)
ATTEMPT = RESULTS / 'attempt1'
if ATTEMPT.exists():
    raise SystemExit(f'refusing to overwrite existing attempt: {ATTEMPT}')
ATTEMPT.mkdir()
ORIGINS = ATTEMPT / 'module-origins.json'
JUNIT = ATTEMPT / 'pytest.junit.xml'
STDOUT = ATTEMPT / 'pytest.stdout.txt'
STDERR = ATTEMPT / 'pytest.stderr.txt'
CONTEXT = ATTEMPT / 'execution-context.json'
TIMEOUT_SECONDS = 120

SELECTORS = [
    'tests/unit/scientist/orchestration/engine/test_producer_scope_reconciliation.py',
    'tests/unit/scientist/orchestration/engine/test_producer_model_scope_oracle.py',
]


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()


def disk_snapshot(path: Path) -> dict[str, int]:
    st = os.statvfs(path)
    return {'available_bytes': st.f_bavail * st.f_frsize, 'total_bytes': st.f_blocks * st.f_frsize}


def source_inventory() -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text('utf-8'))
    expected = {row['path']: row for row in manifest['files']}
    mismatches = []
    for rel, row in expected.items():
        path = CANDIDATE / rel
        if row['mode'] == '120000':
            if not path.is_symlink():
                mismatches.append({'path': rel, 'reason': 'expected symlink missing'})
                continue
            data = os.fsencode(os.readlink(path))
        else:
            if path.is_symlink() or not path.is_file():
                mismatches.append({'path': rel, 'reason': 'expected regular file missing'})
                continue
            data = path.read_bytes()
            executable = bool(path.stat().st_mode & 0o111)
            if executable != (row['mode'] == '100755'):
                mismatches.append({'path': rel, 'reason': 'mode changed'})
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != row['git_blob'] or len(data) != row['bytes']:
            mismatches.append({'path': rel, 'reason': 'Git blob/size changed', 'actual_blob': blob, 'expected_blob': row['git_blob'], 'actual_bytes': len(data), 'expected_bytes': row['bytes']})
    extras = []
    for path in CANDIDATE.rglob('*'):
        if path.is_dir() and not path.is_symlink():
            continue
        rel = path.relative_to(CANDIDATE).as_posix()
        if rel not in expected:
            extras.append(rel)
    return {'expected_files': len(expected), 'mismatches': mismatches, 'extra_files': sorted(extras)}


def process_tree_snapshot(root_pid: int) -> dict[str, object]:
    try:
        out = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,rss=,pcpu=,command='], text=True, stderr=subprocess.DEVNULL)
    except Exception as exc:
        return {'error': repr(exc)}
    rows = []
    for line in out.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) < 4:
            continue
        try:
            rows.append({'pid': int(parts[0]), 'ppid': int(parts[1]), 'rss_kib': int(parts[2]), 'pcpu': float(parts[3]), 'command': parts[4] if len(parts) > 4 else ''})
        except ValueError:
            continue
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for row in rows:
            if row['ppid'] in descendants and row['pid'] not in descendants:
                descendants.add(row['pid'])
                changed = True
    selected = [row for row in rows if row['pid'] in descendants]
    return {'root_pid': root_pid, 'processes': selected, 'tree_rss_kib': sum(row['rss_kib'] for row in selected)}


def junit_summary(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
    totals = {'tests': 0, 'failures': 0, 'errors': 0, 'skips': 0, 'time_seconds': 0.0}
    failing = []
    for suite in suites:
        totals['tests'] += int(suite.attrib.get('tests', 0))
        totals['failures'] += int(suite.attrib.get('failures', 0))
        totals['errors'] += int(suite.attrib.get('errors', 0))
        totals['skips'] += int(suite.attrib.get('skipped', 0))
        try:
            totals['time_seconds'] += float(suite.attrib.get('time', 0.0))
        except ValueError:
            pass
    for case in root.iter('testcase'):
        failure = case.find('failure')
        error = case.find('error')
        skipped = case.find('skipped')
        if failure is not None or error is not None:
            nodeid = f"{case.attrib.get('classname', '')}::{case.attrib.get('name', '')}"
            item = {'nodeid': nodeid, 'kind': 'failure' if failure is not None else 'error'}
            element = failure if failure is not None else error
            if element is not None:
                item['message'] = element.attrib.get('message', '')
                item['text'] = element.text or ''
            failing.append(item)
    return {**totals, 'failing_nodeids': failing}


def file_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


packages = {}
for package in ['pytest', 'pytest-asyncio', 'pytest-benchmark', 'pydantic', 'loguru', 'hypothesis', 'anyio', 'opentelemetry-api', 'opentelemetry-sdk']:
    try:
        packages[package] = metadata.version(package)
    except metadata.PackageNotFoundError:
        packages[package] = None

source_before = source_inventory()
if source_before['mismatches']:
    raise SystemExit(f'candidate source failed pre-run identity check: {source_before["mismatches"][:10]}')

original_env = dict(os.environ)
env = dict(os.environ)
removed_env = {}
for key in ['GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'PYTHONHOME', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PYTEST_CURRENT_TEST']:
    if key in env:
        removed_env[key] = env.pop(key)
old_pythonpath = env.get('PYTHONPATH')
env.update({
    'PYTHONPATH': os.pathsep.join([str(OUT / 'guard'), str(SRC), str(PRODUCT / 'tests')]),
    'E02_CANDIDATE_ROOT': str(CANDIDATE),
    'E02_CANDIDATE_SRC': str(SRC),
    'E02_SOURCE_MANIFEST': str(MANIFEST),
    'E02_ORIGIN_OUTPUT': str(ORIGINS),
    'PYTHONDONTWRITEBYTECODE': '1',
    'POLISYOS_METRICS_PORT': '0',
    'GIT_CEILING_DIRECTORIES': str(CANDIDATE),
})
argv = [
    sys.executable, '-m', 'pytest',
    '-c', str(PRODUCT / 'pytest.ini'),
    '-o', 'addopts=',
    '--import-mode=importlib', '--strict-markers', '-q',
    '-p', 'no:cacheprovider',
    '-p', 'e02_native_origin_guard',
    '--basetemp', str(ATTEMPT / 'pytest-tmp'),
    '--junitxml', str(JUNIT),
    *SELECTORS,
]

context = {
    'schema': 'e02.g.b-stop-native-execution.v1',
    'candidate_sha': '0bf788ac2e57533b08be9172d64c19705a3af30d',
    'candidate_tree': '2e069f18e02175dd0d6f7acd6573a4c0b071c766',
    'source_manifest_sha256': file_sha(MANIFEST),
    'source_manifest_path': str(MANIFEST),
    'source_before': source_before,
    'selectors': SELECTORS,
    'pytest_argv': argv,
    'cwd': str(PRODUCT),
    'environment': {
        'python_executable': sys.executable,
        'python_realpath': str(Path(sys.executable).resolve()),
        'python_version': sys.version.replace('\n', ' '),
        'platform': platform.platform(),
        'installed_packages': packages,
        'PYTHONPATH': env['PYTHONPATH'],
        'original_PYTHONPATH': old_pythonpath,
        'removed_environment_keys': removed_env,
        'set_values': {key: env[key] for key in ['PYTHONDONTWRITEBYTECODE', 'POLISYOS_METRICS_PORT', 'GIT_CEILING_DIRECTORIES']},
    },
    'G_state_before': {
        'branch': git('symbolic-ref', '--short', 'HEAD'),
        'head': git('rev-parse', 'HEAD'),
        'tree': git('rev-parse', 'HEAD^{tree}'),
        'status_porcelain': git('status', '--porcelain=v1', '-uall'),
    },
    'disk_before': disk_snapshot(OUT),
    'timeout_seconds': TIMEOUT_SECONDS,
    'status': 'RUNNING',
}
CONTEXT.write_text(json.dumps(context, indent=2, sort_keys=True) + '\n', 'utf-8')

start = time.monotonic()
proc = subprocess.Popen(argv, cwd=PRODUCT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
peak_tree_rss = {'rss_kib': 0, 'snapshot': None}
timed_out = False
while proc.poll() is None:
    snapshot = process_tree_snapshot(proc.pid)
    rss = int(snapshot.get('tree_rss_kib', 0))
    if rss > peak_tree_rss['rss_kib']:
        peak_tree_rss = {'rss_kib': rss, 'snapshot': snapshot}
    if time.monotonic() - start >= TIMEOUT_SECONDS:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            time.sleep(2)
        except ProcessLookupError:
            pass
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        break
    time.sleep(0.2)
stdout_bytes, stderr_bytes = proc.communicate()
wall = time.monotonic() - start
STDOUT.write_bytes(stdout_bytes)
STDERR.write_bytes(stderr_bytes)
source_after = source_inventory()
origin_payload = None
if ORIGINS.is_file():
    origin_payload = json.loads(ORIGINS.read_text('utf-8'))
context.update({
    'status': 'TIMEOUT' if timed_out else ('PASS' if proc.returncode == 0 else 'FAIL_OR_ERROR'),
    'exit_code': proc.returncode,
    'timed_out': timed_out,
    'wall_seconds': wall,
    'peak_process_tree_rss_kib': peak_tree_rss['rss_kib'],
    'peak_process_tree_snapshot': peak_tree_rss['snapshot'],
    'source_after': source_after,
    'module_origin_audit': {
        'path': str(ORIGINS) if origin_payload is not None else None,
        'module_count': origin_payload.get('module_count') if origin_payload else None,
        'violations': origin_payload.get('violations') if origin_payload else ['origin audit output missing'],
    },
    'junit_summary': junit_summary(JUNIT),
    'output_files': {
        'stdout_path': str(STDOUT), 'stdout_sha256': file_sha(STDOUT), 'stdout_bytes': len(stdout_bytes),
        'stderr_path': str(STDERR), 'stderr_sha256': file_sha(STDERR), 'stderr_bytes': len(stderr_bytes),
        'junit_path': str(JUNIT) if JUNIT.is_file() else None, 'junit_sha256': file_sha(JUNIT),
    },
    'disk_after': disk_snapshot(OUT),
    'G_state_after': {
        'branch': git('symbolic-ref', '--short', 'HEAD'),
        'head': git('rev-parse', 'HEAD'),
        'tree': git('rev-parse', 'HEAD^{tree}'),
        'status_porcelain': git('status', '--porcelain=v1', '-uall'),
    },
})
CONTEXT.write_text(json.dumps(context, indent=2, sort_keys=True) + '\n', 'utf-8')
print(json.dumps({
    'status': context['status'],
    'exit_code': proc.returncode,
    'wall_seconds': round(wall, 3),
    'peak_process_tree_rss_kib': peak_tree_rss['rss_kib'],
    'junit_summary': context['junit_summary'],
    'module_origin_count': context['module_origin_audit']['module_count'],
    'module_origin_violations': context['module_origin_audit']['violations'],
    'source_before_mismatches': source_before['mismatches'],
    'source_after_mismatches': source_after['mismatches'],
    'context': str(CONTEXT),
}, indent=2))
