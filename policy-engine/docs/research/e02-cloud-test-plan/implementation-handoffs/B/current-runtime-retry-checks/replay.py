"""Replay one exact runtime input against Git source or one guard removal."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = '141e1f47f375ef6805ede2a427f7555ae9690cf3'
CANDIDATE = 'f04e3b80e910ad3cbbbf8262ed58bec69e3d57e8'
SOURCE = 'policy-engine/src/polisyos/scientist/orchestration/engine/retry.py'
TEST = 'policy-engine/tests/unit/scientist/orchestration/engine/test_retry.py'
SELECTOR = 'canonical_retry_boundary or whole_invocation_deadline or unconfigured_sync_bridge or event_loop_block or queued_async_thread or real_process_preserves_control or expired_retry_budget or unbounded_thread_cancellation or completed_provider_error'
PYTHON = '/workspace/polisyos/policy-engine/.venv/bin/python'
parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=['base', 'candidate', 'error-publication-removal'], required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[7]
product = root / 'policy-engine'
out = args.output_dir.resolve()
out.mkdir(parents=True, exist_ok=True)
identity = dict(mode=args.mode, base_sha=BASE, candidate_sha=CANDIDATE, python=PYTHON, cwd=str(product), input_sha256={})
for path in [SOURCE, TEST, 'policy-engine/tests/unit/scientist/orchestration/engine/_retry_setup_probe.py', 'policy-engine/src/polisyos/common/async_tools.py', 'policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py']:
    raw = subprocess.check_output(['git', 'show', CANDIDATE + ':' + path], cwd=root)
    if (root/path).read_bytes() != raw:
        raise SystemExit('immutable input changed: ' + path)
    identity['input_sha256'][path] = hashlib.sha256(raw).hexdigest()
env = os.environ.copy()
env['POLISYOS_METRICS_PORT'] = '0'
prefix = []
selector = SELECTOR
if args.mode != 'candidate':
    overlay = out/'overlay'
    overlay.mkdir(exist_ok=True)
    target = BASE if args.mode == 'base' else CANDIDATE
    raw = subprocess.check_output(['git', 'show', target+':'+SOURCE], cwd=root)
    identity['overlay_basis_sha'] = target
    identity['overlay_basis_source_sha256'] = hashlib.sha256(raw).hexdigest()
    if args.mode == 'error-publication-removal':
        guard = '''            try:
                _remaining_deadline(
                    deadline, execution_state="completed_error_publication_rejected"
                )
            except NodeTimeoutError:
                _merge_spend(state, failed_spend)
                raise
'''
        source = raw.decode()
        if source.count(guard) != 2:
            raise SystemExit('expected both canonical sync/async error guards')
        raw = source.replace(guard, '').encode()
        selector = 'completed_provider_error'
        identity['removed_property'] = 'Both owner error-publication deadline checks; all other canonical source bytes unchanged'
    compile(raw, str(overlay/'pinned_retry.py'), 'exec')
    (overlay/'pinned_retry.py').write_bytes(raw)
    identity['executed_overlay_source_sha256'] = hashlib.sha256(raw).hexdigest()
    (overlay/'sitecustomize.py').write_text('''import importlib.abc, importlib.util, sys
from pathlib import Path
class PinnedRetry(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'polisyos.scientist.orchestration.engine.retry':
            return importlib.util.spec_from_file_location(fullname, Path(__file__).with_name('pinned_retry.py'))
sys.meta_path.insert(0, PinnedRetry())
''')
    prefix.append(str(overlay))
env['PYTHONPATH'] = ':'.join(prefix + [str(product/'src'), str(product)])
command = [PYTHON, '-m', 'pytest', '-o', 'addopts=', '-q', TEST.removeprefix('policy-engine/'), '-k', selector, '--junitxml='+str(out/'native.xml')]
completed = subprocess.run(command, cwd=product, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
(out/'native.txt').write_text(completed.stdout)
identity.update(command=command, PYTHONPATH=env['PYTHONPATH'], POLISYOS_METRICS_PORT=env['POLISYOS_METRICS_PORT'], exit_code=completed.returncode, stdout_sha256=hashlib.sha256(completed.stdout.encode()).hexdigest())
(out/'receipt.json').write_text(json.dumps(identity,indent=2)+'\n')
print(json.dumps(identity,indent=2))
print(completed.stdout,end='')
sys.exit(completed.returncode)
