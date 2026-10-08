from __future__ import annotations
import json, os, resource, subprocess, sys, time
from pathlib import Path
scratch = Path('/dev/shm/e02-orch03-20261008/c07-checks')
label, *command = sys.argv[1:]
env = dict(os.environ)
env['PYTHONPATH'] = '/dev/shm/e02-orch03-20261008/c07/policy-engine/src:/dev/shm/e02-orch03-20261008/c07/policy-engine'
start = time.time()
clock = time.perf_counter()
with (scratch / (label + '.stdout')).open('wb') as out, (scratch / (label + '.stderr')).open('wb') as err:
    result = subprocess.run(command, cwd='/dev/shm/e02-orch03-20261008/c07', env=env, stdout=out, stderr=err, check=False)
record = {
    'label':label,'command':command,'cwd':'/dev/shm/e02-orch03-20261008/c07',
    'source_sha':'741af2a08a8dc5fa36340bf700c092c7fb51f651',
    'source_tree':'bfae04d141187c30e4f6bc14dbbbae00f6ee116c',
    'started_unix':start, 'wall_seconds':time.perf_counter()-clock,
    'maxrss_children_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    'returncode':result.returncode,'PYTHONPATH':env['PYTHONPATH'],
}
(scratch / (label + '.json')).write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')
print(json.dumps(record, sort_keys=True))
sys.exit(result.returncode)
