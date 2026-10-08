"""Record bounded exact-source independent wave and preserved setup attempts."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import time

b = Path('/dev/shm/e02-F-profile-consistency-adversary')
source = b / 'candidate852cc'
script = b / 'probe.py'
interpreter = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
receipt = b / 'execution852cc.json'
prior = json.loads(receipt.read_text())
runs = prior['runs']
(b / 'tmp').mkdir(exist_ok=False)
for label, port, extra, expected in [
    ('repaired-attempt2', '19755', [], 0),
    ('retained-marker-mutant-attempt1', '19756', ['--remove-known-profile-guard'], 1),
]:
    argv = [interpreter, str(script), '--source', str(source), '--out', str(b / label), '--expect', 'repaired', *extra]
    started = time.time()
    with (b / f'{label}.stdout').open('wb') as stdout, (b / f'{label}.stderr').open('wb') as stderr:
        result = subprocess.run(argv, cwd=source, env={**os.environ, 'POLISYOS_METRICS_PORT': port, 'TMPDIR': str(b / 'tmp')}, stdout=stdout, stderr=stderr)
    run = {
        'label': label, 'argv': argv, 'cwd': str(source), 'metrics_port': port, 'TMPDIR': str(b / 'tmp'),
        'returncode': result.returncode, 'expected_returncode': expected,
        'wall_seconds': time.time() - started,
        'children_max_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'source_sha': '852cc3707bfc7dee132ec07a9ed5adcb5911fdf2',
        'source_tree': '52fb13e9e12d80e4b1af5580f61d15310535e5e8',
        'harness_sha256': hashlib.sha256(script.read_bytes()).hexdigest(), 'outputs': {},
    }
    for suffix in ('stdout', 'stderr'):
        p = b / f'{label}.{suffix}'; data = p.read_bytes()
        run['outputs'][suffix] = {'path': str(p), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    report_path = b / label / 'report.json'
    if report_path.exists():
        report = json.loads(report_path.read_text())
        run.update({key: report[key] for key in ('origin_count', 'origin_errors', 'positive', 'original_mgraph_readable')})
        run['reported_outcome'] = report['outcome']
        run['failed_expectations'] = len(report['failed_expectations'])
    else:
        run['reported_outcome'] = 'ERROR/incomplete; report missing'
    runs.append(run)
    receipt.write_text(json.dumps({
        'runs': runs,
        'serialized_resource': str(source / 'policy-engine/src/_build/benchmark-results/foundry/selection_history/executions.jsonl'),
        'quota': 'none; sequential only shared runtime history',
        'result': 'incomplete' if label != 'retained-marker-mutant-attempt1' else 'complete',
    }, indent=2, sort_keys=True) + '\n')
    print(label, 'returncode', result.returncode, 'expected', expected, 'wall', round(run['wall_seconds'], 3), 'outcome', run['reported_outcome'], flush=True)
    if result.returncode != expected:
        raise AssertionError(run)
