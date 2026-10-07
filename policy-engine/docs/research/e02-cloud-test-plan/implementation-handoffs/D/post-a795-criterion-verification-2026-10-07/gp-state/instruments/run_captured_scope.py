"""Capture a single existing frozen-scope process and POSIX resource use, without caps."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import resource
import subprocess
import sys
import time

command_file=Path(sys.argv[1]);name=sys.argv[2]
command=json.loads(command_file.read_text())[name]
base=command_file.parent
cg=Path('/sys/fs/cgroup')
def cgroup():return {p:(cg/p).read_text() for p in ('memory.current','memory.max','memory.events','memory.stat','pids.current','pids.max','cpu.max') if(cg/p).is_file()}
before={'timestamp':datetime.datetime.now(datetime.UTC).isoformat(),'cgroup_observation_shared_not_per_process':cgroup()}
env=os.environ.copy();env.update(command['env_overrides'])
start=time.monotonic()
with Path(command['stdout']).open('wb') as stdout,Path(command['stderr']).open('wb') as stderr:
    result=subprocess.run(command['argv'],cwd=command['cwd'],env=env,stdout=stdout,stderr=stderr)
r=resource.getrusage(resource.RUSAGE_CHILDREN)
after={'timestamp':datetime.datetime.now(datetime.UTC).isoformat(),'cgroup_observation_shared_not_per_process':cgroup()}
record={'scope':name,'command':command,'command_file_sha256':hashlib.sha256(command_file.read_bytes()).hexdigest(),'wrapper_file':str(Path(__file__).resolve()),'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'exitcode':result.returncode,'wall_s':time.monotonic()-start,'resource_method':'one subprocess; POSIX RUSAGE_CHILDREN Linux ru_maxrss KiB; shared cgroup only context, no per-child quota or OOM inference','rusage':{f:getattr(r,f) for f in ('ru_utime','ru_stime','ru_maxrss','ru_minflt','ru_majflt','ru_nswap','ru_inblock','ru_oublock','ru_nvcsw','ru_nivcsw')},'before':before,'after':after,'finalized_outer_streams':{key:{'path':command[key],'sha256':hashlib.sha256(Path(command[key]).read_bytes()).hexdigest(),'bytes':Path(command[key]).stat().st_size} for key in ('stdout','stderr')},'numerical_caps':'none introduced; environment is recorded by child and command; existing intrinsic ownerprofile observed'}
(base/(name+'.captured-result.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'scope':name,'exitcode':result.returncode,'wall_s':record['wall_s'],'maxrss_kib':r.ru_maxrss}));sys.exit(result.returncode)
