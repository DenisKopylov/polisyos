"""Capture complete source-bound independent native/value-removal evidence."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/workspace/e02-F-closeout-20261006')
SCRATCH = Path('/tmp/e02-F-continuation-20261006/foundry/value-consumer')
PYTHON = ROOT / 'policy-engine/.venv/bin/python'
PATHS = [
    'policy-engine/src/polisyos/ir/analytics/causal.py',
    'policy-engine/src/polisyos/ir/analytics/uncertainty.py',
    'policy-engine/src/polisyos/ir/analytics/causal_graph.py',
    'policy-engine/src/polisyos/foundry/methods/components/value_evidence.py',
    'policy-engine/src/polisyos/foundry/methods/components/consensus.py',
    'policy-engine/src/polisyos/foundry/methods/backends/dispatch.py',
    'policy-engine/src/polisyos/foundry/methods/backends/protocol.py',
    'policy-engine/src/polisyos/foundry/methods/lifecycle/output_monitor.py',
    'policy-engine/src/polisyos/foundry/methods/catalog/causal/rdd.py',
    'policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py',
    'policy-engine/src/polisyos/foundry/methods/catalog/econometrics/timeseries.py',
    'policy-engine/src/polisyos/foundry/methods/catalog/econometrics/protocols.py',
    'policy-engine/src/polisyos/foundry/methods/selection/history.py',
    'policy-engine/tests/unit/foundry/methods/test_value_evidence.py',
]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def bound(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    expected, mode = sys.argv[1:3]
    suffix = sys.argv[3] if len(sys.argv) == 4 else ''
    assert suffix in {'', '-corrected'}
    sha = git('rev-parse', 'HEAD').decode().strip()
    tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
    assert sha == expected, (sha, expected)
    refs = []
    for path in PATHS:
        original = git('show', f'{sha}:{path}')
        assert (ROOT / path).read_bytes() == original
        refs.append({'path':path, 'git_sha':sha, 'bytes':len(original), 'sha256':hashlib.sha256(original).hexdigest()})
    env = os.environ.copy()
    env.update(PYTHONPATH=str(ROOT / 'policy-engine/src')+':'+str(ROOT / 'policy-engine'), PYTHONDONTWRITEBYTECODE='1')
    test = '/tmp/e02-F-continuation-20261006/foundry/test_value_consumer_identification.py'
    if mode == 'native':
        command = [str(PYTHON), '-m', 'pytest', test, 'tests/unit/foundry/methods/test_value_evidence.py',
                   '-o', 'addopts=', '-p', 'no:cacheprovider', '-q', '-s', '--tb=short',
                   '--basetemp', str(SCRATCH / ('native'+suffix+'-tmp'))]
        expected_exit = 0
    else:
        assert mode in {'report_cap', 'value_guard'}
        command = [str(PYTHON), str(SCRATCH / 'replay_value_consumer.py'), mode, str(SCRATCH / (mode+suffix+'-tmp'))]
        expected_exit = 1
    start = time.monotonic()
    result = subprocess.run(command, cwd=ROOT / 'policy-engine', env=env, capture_output=True)
    elapsed = time.monotonic()-start
    out, err = SCRATCH / (mode+suffix+'.stdout.txt'), SCRATCH / (mode+suffix+'.stderr.txt')
    out.write_bytes(result.stdout)
    err.write_bytes(result.stderr)
    unchanged = all((ROOT / path).read_bytes() == git('show', f'{sha}:{path}') for path in PATHS)
    receipt = {
        'name': 'actual_value_consumer_'+mode, 'command':' '.join(command), 'target_sha':sha, 'target_tree':tree,
        'environment':{'interpreter':str(PYTHON), 'PYTHONPATH':env['PYTHONPATH'], 'PYTHONDONTWRITEBYTECODE':'1',
                       'runtime_history':'supported SelectionHistoryStore in-memory injection; no shared history writes', 'cloud_quota_introduced':False},
        'input_closure':'Actual dispatcher sharp CCT HC0 fixed RD400-row SUCCESS+CI, typed report/graph/proof CAS and fresh readers; actual dispatcher statsmodelsARIMA(0,0,0)96-row native result→CAS→freshmodel→existing value projector; complete existing test_value_evidence.py for native run. Removal cases execute real path with memory-only code mutation and retained method/class/function identity and markers.',
        'outcome':'PASS' if result.returncode==0 else ('FAIL' if result.returncode==1 else 'ERROR'),
        'exit_code':result.returncode, 'expected_exit':expected_exit, 'expected_rejection_met':result.returncode==expected_exit,
        'wall_seconds':elapsed, 'output':str(out), 'output_refs':[bound(out), bound(err)],
        'source_refs':refs, 'head_after':git('rev-parse', 'HEAD').decode().strip(), 'direct_source_inputs_unchanged_after':unchanged,
        'source_binding_limits':'Explicit fourteen defining/consumer paths, not a complete global imported input denominator or P41 classification.',
    }
    (SCRATCH / (mode+suffix+'.json')).write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'receipt':bound(SCRATCH / (mode+suffix+'.json')), 'exit':result.returncode, 'wall_seconds':elapsed,
                      'output_refs':receipt['output_refs'], 'head_after':receipt['head_after'], 'source_inputs_unchanged':unchanged}, indent=2))
    print(result.stdout.decode())
    print(result.stderr.decode())
    assert result.returncode == expected_exit and unchanged


if __name__ == '__main__':
    main()
