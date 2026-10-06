from __future__ import annotations
import hashlib, importlib.util, json, os, resource, subprocess, sys
from pathlib import Path
ROOT = Path('/workspace/e02-B-current-execution-state')
SHA = '3f4455f11600f6a5c94e3a5dfbcd519d46ac6c6f'
SOURCE = 'policy-engine/src/polisyos/scientist/orchestration/engine/retry.py'
OUT = ROOT / '_build/current-execution-state/run-review-3f'
source = subprocess.check_output(['git','show',SHA + ':' + SOURCE], cwd=ROOT)
path = OUT / 'retry_pinned.py'
path.write_bytes(source)
spec = importlib.util.spec_from_file_location('run_review_pinned_retry', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
from polisyos.scientist.orchestration.engine.state import ExperimentState
class Node:
    def execute(self, _ctx, state):
        raise AssertionError('physical node must not start on setup failure')
def fds():
    result=[]
    for fd in range(64):
        try: os.fstat(fd)
        except OSError: continue
        result.append(fd)
    return result
before=fds()
old=resource.getrlimit(resource.RLIMIT_NOFILE)
limit=max(before)+3
resource.setrlimit(resource.RLIMIT_NOFILE,(limit,old[1]))
retained=[]
try:
    module._execute_with_timeout_process(Node(), None, ExperimentState(), timeout_s=.1)
except BaseException as exc:
    retained.append(exc)
    failure={'type':type(exc).__name__, 'message':str(exc)}
finally:
    resource.setrlimit(resource.RLIMIT_NOFILE,old)
after=fds()
observed={'source_sha':SHA, 'source_path':SOURCE, 'source_sha256':hashlib.sha256(source).hexdigest(),
          'python':sys.executable, 'environment':{'PYTHONPATH':os.environ.get('PYTHONPATH'),'POLISYOS_METRICS_PORT':os.environ.get('POLISYOS_METRICS_PORT')},
          'fd_before':before, 'RLIMIT_NOFILE_soft_fault':limit, 'exception':failure,
          'fd_after_while_exception_retained':after, 'new_fds':list(set(after)-set(before))}
print(json.dumps(observed,indent=2))
(OUT/'setup-probe.json').write_text(json.dumps(observed,indent=2)+'\n')
