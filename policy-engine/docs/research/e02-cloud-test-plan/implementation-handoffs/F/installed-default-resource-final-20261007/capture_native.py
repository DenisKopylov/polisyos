"""Capture two resource-affected profiles with exclusive actual exporter port windows."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
scratch=Path(__file__).resolve().parent
config=json.loads((scratch/'installed-config.json').read_text())
manifest=json.loads((scratch/'archive-installed-source-bindings.json').read_text())
assert manifest['outcome']=='PASS' and manifest['source_sha']==config['source_sha']
env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1'
keys=['PYTHONPATH','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','XLA_FLAGS','XLA_PYTHON_CLIENT_PREALLOCATE','JAX_PLATFORM_NAME','JAX_PLATFORMS','POLISYOS_DOWHY_WORKER_PYTHON','METRICS_PORT']
def run(kind):
    argv=[config['installed_pythons'][kind],'-I',str(scratch/'launch.py'),str(scratch/'installed-config.json'),kind]
    cwd=scratch/(kind+'-consumer');started=time.monotonic()
    timepath=scratch/(kind+'-resources-v2.json')
    measured=argv
    record={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'kind':kind,'argv':argv,'measured_argv':measured,'cwd':str(cwd),'environment':{key:env.get(key,'absent') for key in keys},'new_quota':False,'parallel_profiles':False,'serialization_reason':config['serialization_reason'],'status':'RUNNING'}
    recordpath=scratch/(kind+'-native-v2.json');recordpath.write_text(json.dumps(record,indent=2)+'\n')
    with (scratch/(kind+'-native-v2.stdout.txt')).open('wb') as out,(scratch/(kind+'-native-v2.stderr.txt')).open('wb') as err:
        process=subprocess.Popen(measured,cwd=cwd,env=env,stdout=out,stderr=err)
        record['pid']=process.pid;recordpath.write_text(json.dumps(record,indent=2)+'\n')
        _, waited, usage = os.wait4(process.pid, 0)
        code=os.waitstatus_to_exitcode(waited);process.returncode=code
        timepath.write_text(json.dumps({'wait4_pid':process.pid,'user_seconds':usage.ru_utime,'system_seconds':usage.ru_stime,'maxrss_KiB':usage.ru_maxrss,'minor_faults':usage.ru_minflt,'major_faults':usage.ru_majflt,'voluntary_context_switches':usage.ru_nvcsw,'involuntary_context_switches':usage.ru_nivcsw},indent=2)+'\n')
    record.update(exit_code=code,wall_seconds=time.monotonic()-started,status='PASS' if code==0 else 'FAIL')
    for stream in ('stdout','stderr'):
        path=scratch/(kind+'-native-v2.'+stream+'.txt');raw=path.read_bytes();record[stream]={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    record['resources']={'path':str(timepath),'bytes':timepath.stat().st_size,'sha256':hashlib.sha256(timepath.read_bytes()).hexdigest()}
    recordpath.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({key:record[key] for key in ('kind','exit_code','wall_seconds','status')}),flush=True)
    return record
records=[run(kind) for kind in ('wheel','sdist')]
# Serialization guards the existing shared exporter port, not computation.
(scratch/'native-wave-v2.json').write_text(json.dumps({'source_sha':config['source_sha'],'profiles':records,'outcome':'PASS' if all(r['exit_code']==0 for r in records) else 'FAIL','scope':'Maintained Graph79 + actual installed curated-default probe12/profile; actual collected IDs/counts retained; no numerical quota or global/admission closure'},indent=2)+'\n')
