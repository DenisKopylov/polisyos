"""Measure unchanged committed consumer driver against the frozen B union."""
import datetime
import hashlib
import importlib.metadata
import json
import os
import pathlib
import platform
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path('/workspace/e02-B-acceptance')
CWD = ROOT / 'policy-engine'
PYTHON = '/workspace/polisyos/policy-engine/.venv/bin/python'
DRIVER_ROOT = pathlib.Path('/workspace/e02-B-coordination')
DRIVER_REL = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/downstream/stream-unpublished-owner-probe.py'
DRIVER = DRIVER_ROOT / DRIVER_REL
FROZEN = 'a3daffbe867ddfe9eede5e5990687283b552952a'
TREE = '78f41aecb81d2e27ed89346328c90be1b4da6041'
DRIVER_SHA256 = '892d997187bfc79d5d9c2c6c269f3c5bab878ae938b535f799ff2a65d28d9a31'
OUT = pathlib.Path(__file__).resolve().parent
PREFIX = 'stream-unpublished-final-a3daffbe'

def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

def utc():
    return datetime.datetime.now(datetime.UTC).isoformat()

def artifact(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def source():
    return {'sha': git(ROOT, 'rev-parse', 'HEAD'), 'tree': git(ROOT, 'rev-parse', 'HEAD^{tree}'), 'branch': git(ROOT, 'branch', '--show-current'), 'status_porcelain': git(ROOT, 'status', '--porcelain')}

def measured(argv, log, env):
    start = utc()
    monotonic = time.monotonic()
    with log.open('wb') as stream:
        process = subprocess.Popen(argv, cwd=CWD, env=env, stdout=stream, stderr=subprocess.STDOUT)
        pid, status, usage = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
    return {'argv': argv, 'cwd': str(CWD), 'start_utc': start, 'end_utc': utc(), 'exit_code': process.returncode, 'wall_seconds': time.monotonic() - monotonic, 'pid': pid, 'resource_method': 'direct os.wait4 child rusage; Linux max RSS in KiB', 'resources': {'max_rss_kib': usage.ru_maxrss, 'user_seconds': usage.ru_utime, 'system_seconds': usage.ru_stime, 'minor_page_faults': usage.ru_minflt, 'major_page_faults': usage.ru_majflt, 'voluntary_context_switches': usage.ru_nvcsw, 'involuntary_context_switches': usage.ru_nivcsw}, 'full_stdout_stderr': artifact(log)}

def driver_oracle(log):
    content = log.read_text()
    decoder = json.JSONDecoder()
    objects = []
    for index, char in enumerate(content):
        if char != '{':
            continue
        try:
            value, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and 'property_actual_registry_cleanup_completes' in value:
            objects.append(value)
    if len(objects) != 1:
        return {'unresolved_oracle': f'expected one printed driver result, found {len(objects)}'}
    return objects[0]

before = source()
if before['sha'] != FROZEN or before['tree'] != TREE or before['status_porcelain']:
    raise SystemExit(f'UNRUN frozen source admission mismatch: {before!r}')
driver_before = artifact(DRIVER)
if driver_before['sha256'] != DRIVER_SHA256:
    raise SystemExit(f'UNRUN driver hash mismatch: {driver_before!r}')
driver_head = git(DRIVER_ROOT, 'rev-parse', 'HEAD')
committed = subprocess.check_output(['git', '-C', str(DRIVER_ROOT), 'show', f'{driver_head}:{DRIVER_REL}'])
if hashlib.sha256(committed).hexdigest() != DRIVER_SHA256:
    raise SystemExit('UNRUN driver is not the requested committed bytes')

modules = [
    'polisyos.fabric.connectors.base',
    'polisyos.fabric.connectors.pool',
    'polisyos.fabric.connectors.registry',
    'polisyos.fabric.connectors.registry_core_parts',
    'polisyos.fabric.connectors._registry_lifecycle',
    'polisyos.fabric.connectors.sources.event_stream',
    'polisyos.fabric.data_plane.streaming',
]
paths = [f'policy-engine/src/{name.replace(".", "/")}.py' for name in modules]
source_inputs = []
for rel in paths:
    path = ROOT / rel
    entry = artifact(path)
    entry['repository_path'] = rel
    entry['git_blob'] = git(ROOT, 'rev-parse', f'{FROZEN}:{rel}')
    if hashlib.sha256(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{FROZEN}:{rel}'])).hexdigest() != entry['sha256']:
        raise SystemExit(f'UNRUN source blob mismatch: {rel}')
    source_inputs.append(entry)

env = os.environ.copy()
env.update({'PYTHONPATH': str(CWD / 'src') + ':' + str(CWD / 'product'), 'PYTHONDONTWRITEBYTECODE': '1', 'POLISYOS_METRICS_PORT': '0'})
packet = {'schema': 'policyos.e02.B_final_upstream_consumer_replay.v1', 'wrapper': artifact(pathlib.Path(__file__).resolve()), 'source_before': before, 'driver': driver_before, 'driver_committed_head': driver_head, 'driver_git_blob': git(DRIVER_ROOT, 'rev-parse', f'{driver_head}:{DRIVER_REL}'), 'source_inputs': source_inputs, 'selected_environment': {key: env.get(key) for key in ('PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'POLISYOS_METRICS_PORT')}, 'fixtures': {'connector_url': 'https://stream.invalid', 'dataset_id': 'unpublished-health', 'max_connections': 1, 'pool_acquire_timeout_seconds': 0.03, 'pool_connection_timeout_seconds': 0.5, 'outer_driver_wait_for_seconds': 0.5, 'network_input': 'typed adversarial connector fixture; no remote network operation', 'consumer': 'actual StreamingSourceSession.create, ConnectionPool and ConnectorRegistry.shutdown_async', 'negative': 'persistent physical disconnect OSError until registry retry observation, then explicit cleanup rescue', 'control': 'same unchanged driver with --disconnect-ok', 'isolation': 'each driver is a fresh separate OS process, singleton registry and actual pool instance; metrics port 0; temporary directory outside checkout'}, 'checks': [], 'limits': ['Bounded upstream consumer cleanup transfer test, not full served stream.', 'No C streaming source edits, no production dataset or broad pytest execution.', 'The actual current exits/oracles stand alone; no previous d0 outcome inherited.', 'No hard wall-time guarantee for uncooperative physical cleanup/drain and no all-external-cancellation-suppression claim.', 'Root B frozen union replay, distinct from G integration.']}

env_code = 'import hashlib,importlib,importlib.metadata,json,platform,sys; names=' + repr(modules) + '; result={"python_executable":sys.executable,"python_version":sys.version,"platform":platform.platform(),"packages":{name:importlib.metadata.version(name) for name in ["pydantic","duckdb","numpy"]},"modules":[]};\nfor name in names:\n m=importlib.import_module(name); p=m.__file__; result["modules"].append({"name":name,"origin":p,"sha256":hashlib.sha256(open(p,"rb").read()).hexdigest()})\nprint(json.dumps(result,indent=2))'
with tempfile.TemporaryDirectory(prefix='e02-B-stream-final-', dir=OUT) as temporary:
    env['TMPDIR'] = temporary
    packet['selected_environment']['TMPDIR'] = temporary
    native_log = OUT / f'{PREFIX}.environment.txt'
    native = measured([PYTHON, '-c', env_code], native_log, env)
    packet['native_environment_probe'] = native
    if native['exit_code'] != 0:
        packet['actual_status'] = 'UNRUN native environment probe failed before consumer replay'
    else:
        for label, extra in [('negative', []), ('control', ['--disconnect-ok'])]:
            log = OUT / f'{PREFIX}.{label}.txt'
            check = measured([PYTHON, str(DRIVER), *extra], log, env)
            check['label'] = label
            check['actual_printed_oracle'] = driver_oracle(log)
            check['actual_outcome'] = 'PASS' if check['exit_code'] == 0 else 'FAIL'
            packet['checks'].append(check)
        packet['actual_status'] = 'COMPLETED two actual consumer driver executions'

packet['source_after'] = source()
packet['source_unchanged'] = packet['source_after'] == before
packet['source_input_hashes_unchanged'] = all(artifact(pathlib.Path(entry['path']))['sha256'] == entry['sha256'] for entry in source_inputs)
packet['driver_after'] = artifact(DRIVER)
packet['driver_unchanged'] = packet['driver_after'] == driver_before
packet['complete_replay_admitted'] = packet['source_unchanged'] and packet['source_input_hashes_unchanged'] and packet['driver_unchanged'] and len(packet['checks']) == 2
packet['ended_utc'] = utc()
path = OUT / f'{PREFIX}.json'
path.write_text(json.dumps(packet, indent=2) + '\n')
print(json.dumps({'packet': artifact(path), 'source_unchanged': packet['source_unchanged'], 'complete_replay_admitted': packet['complete_replay_admitted'], 'checks': [{key: value for key, value in check.items() if key in ('label', 'exit_code', 'actual_outcome', 'wall_seconds', 'resources', 'actual_printed_oracle')} for check in packet['checks']]}, indent=2))
raise SystemExit(0 if packet['complete_replay_admitted'] else 2)
