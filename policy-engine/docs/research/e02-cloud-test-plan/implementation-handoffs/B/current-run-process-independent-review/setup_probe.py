from __future__ import annotations
import argparse, asyncio, hashlib, importlib.util, json, os, resource, subprocess, sys, traceback
from pathlib import Path
ROOT = Path('/workspace/e02-B-current-execution-state')
SHA = '3f4455f11600f6a5c94e3a5dfbcd519d46ac6c6f'
SOURCE = 'policy-engine/src/polisyos/scientist/orchestration/engine/retry.py'
OUT = ROOT / '_build/current-execution-state/run-review-3f'
parser=argparse.ArgumentParser()
parser.add_argument('--mode', choices=('sync','async'), default='sync')
args=parser.parse_args()
source = subprocess.check_output(['git','show',SHA + ':' + SOURCE], cwd=ROOT)
path = OUT / 'retry_pinned.py'
path.write_bytes(source)
spec = importlib.util.spec_from_file_location('run_review_pinned_retry', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
from polisyos.scientist.orchestration.engine.state import ExperimentState
entered=OUT / ('entered-' + args.mode + '.txt')
entered.unlink(missing_ok=True)
class Node:
    def execute(self, _ctx, state):
        entered.write_text('physical node body entered')
        raise AssertionError('physical node must not start on setup failure')
def fds():
    result=[]
    for fd in range(64):
        try: os.fstat(fd)
        except OSError: continue
        result.append(fd)
    return result
state=ExperimentState(run_id="R_review_setup")
loop=asyncio.new_event_loop() if args.mode == "async" else None
before=fds()
old=resource.getrlimit(resource.RLIMIT_NOFILE)
limit=max(before)+3
resource.setrlimit(resource.RLIMIT_NOFILE,(limit,old[1]))
retained=[]
try:
    if args.mode == "sync":
        module._execute_with_timeout_process(Node(), None, state, timeout_s=.1)
    else:
        loop.run_until_complete(module._execute_with_timeout_process_async(Node(), None, state, timeout_s=.1, authority=module._AttemptAuthority()))
except BaseException as exc:
    retained.append(exc)
    failure={'type':type(exc).__name__, 'message':str(exc)}
    traceback.print_exception(exc)
finally:
    resource.setrlimit(resource.RLIMIT_NOFILE,old)
after=fds()
observed={'source_sha':SHA, 'source_path':SOURCE, 'source_sha256':hashlib.sha256(source).hexdigest(),
          'python':sys.executable, 'environment':{'PYTHONPATH':os.environ.get('PYTHONPATH'),'POLISYOS_METRICS_PORT':os.environ.get('POLISYOS_METRICS_PORT')},
          'mode':args.mode, 'body_entered':entered.exists(), 'fd_before':before, 'RLIMIT_NOFILE_soft_fault':limit, 'exception':failure,
          'fd_after_while_exception_retained':after, 'new_fds':list(set(after)-set(before)),
          'new_fd_targets':{str(fd):os.readlink('/proc/self/fd/'+str(fd)) for fd in set(after)-set(before)}}
print(json.dumps(observed,indent=2))
(OUT/('setup-probe-' + args.mode + '.json')).write_text(json.dumps(observed,indent=2)+'\n')

if loop is not None: loop.close()
