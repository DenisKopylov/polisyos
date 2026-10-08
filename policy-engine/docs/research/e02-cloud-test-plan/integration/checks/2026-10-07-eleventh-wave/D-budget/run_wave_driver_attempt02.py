from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

repo = Path('/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos').resolve()
live_project = repo / 'policy-engine'
base = repo / 'policy-engine/_build/e02-g-continuation-20261006/R/incoming-20261007-1146/I/D-budget-local'
root = base / 'checkout/policy-engine'
results = base / 'results'
manifest_path = results / 'source-manifest-repaired.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
interpreter = live_project / '.venv/bin/python'
runner = results / 'candidate_pytest_runner.py'
origins_path = results / 'polisyos-origins-attempt-02.json'
junit_path = results / 'owner-budget-factory.attempt-02.junit.xml'
stdout_path = results / 'pytest.attempt-02.stdout.log'
stderr_path = results / 'pytest.attempt-02.stderr.log'
source_check_path = results / 'source-immutability-attempt-02.json'
receipt_path = results / 'receipt-attempt-02.json'

if not interpreter.exists() or not root.exists():
    raise SystemExit('preflight failure: interpreter or candidate root missing')

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def content(path: Path, mode: str) -> bytes:
    import stat
    st = path.lstat()
    if mode == '120000' and stat.S_ISLNK(st.st_mode):
        return os.readlink(path).encode()
    if stat.S_ISREG(st.st_mode):
        return path.read_bytes()
    raise RuntimeError(f'unexpected file type: {path}')

def verify_source(label: str) -> dict:
    mismatches=[]
    for row in manifest['files']:
        rel=row['path'].removeprefix('policy-engine/')
        path=root/rel
        if not os.path.lexists(path):
            mismatches.append({'path':row['path'],'problem':'missing'})
            continue
        actual=sha(content(path,row['mode']))
        if actual != row['sha256']:
            mismatches.append({'path':row['path'],'problem':'content hash mismatch','expected':row['sha256'],'actual':actual})
        import stat
        if row['mode'] != '120000':
            actual_mode=f'{stat.S_IMODE(path.stat().st_mode):06o}'
            expected_mode=f'{int(row["mode"],8)&0o777:06o}'
            if actual_mode != expected_mode:
                mismatches.append({'path':row['path'],'problem':'mode mismatch','expected':expected_mode,'actual':actual_mode})
    return {'label':label,'candidate_sha':manifest['candidate_sha'],'candidate_tree':manifest['candidate_tree'],'files_checked':len(manifest['files']),'status':'PASS' if not mismatches else 'FAIL','mismatches':mismatches}

def shell(command: list[str]) -> str:
    p=subprocess.run(command,cwd=repo,text=True,capture_output=True)
    return p.stdout.strip() if p.returncode==0 else f'ERROR({p.returncode}): {p.stderr.strip()}'

def resource_snapshot() -> dict:
    return {
        'disk_usage_bytes':dict(total=shutil.disk_usage(repo).total,used=shutil.disk_usage(repo).used,free=shutil.disk_usage(repo).free),
        'df_h':shell(['/bin/df','-h',str(repo)]),
        'memory_pressure':shell(['/usr/bin/memory_pressure']),
        'git_head':shell(['git','rev-parse','HEAD']),
        'git_branch':shell(['git','symbolic-ref','--short','HEAD']),
        'git_status':shell(['git','status','-sb']),
    }

before_source=verify_source('before')
if before_source['status']!='PASS':
    raise SystemExit('refusing to run: extracted source failed pre-run hash check')
pre=resource_snapshot()
expected_g_head='855cb26a7a2c9fea60356663cf81e7d01e20c738'
if pre['git_head'] != expected_g_head or pre['git_branch'] != 'codex/e02-integration':
    raise SystemExit(f'unexpected G attachment: {pre["git_branch"]} {pre["git_head"]}')

command=[str(interpreter),str(runner),'--junitxml='+str(junit_path),'-o','addopts=','-q','-p','no:cacheprovider','tests/unit/scientist/methods/search/test_service_owner_budget_factory.py']
env=os.environ.copy()
env.update({
 'D_BUDGET_CANDIDATE_ROOT':str(root),
 'D_BUDGET_LIVE_PROJECT':str(live_project),
 'D_BUDGET_SOURCE_MANIFEST':str(manifest_path),
 'D_BUDGET_ORIGINS_PATH':str(origins_path),
 'PYTHONPATH':os.pathsep.join([str(root/'src'),str(root/'tests/unit/scientist/methods/search')]),
 'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
 'PYTHONNOUSERSITE':'1',
 'PYTHONDONTWRITEBYTECODE':'1',
 'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','JAX_NUM_THREADS':'1',
})
env_for_receipt={key:env[key] for key in ['PYTHONPATH','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONNOUSERSITE','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','JAX_NUM_THREADS']}
start=time.monotonic()
proc=subprocess.Popen(command,cwd=root,env=env,stdout=open(stdout_path,'wb'),stderr=open(stderr_path,'wb'))
peak_rss_kib=0
samples=0
timeout_seconds=180
terminated_for_timeout=False
while proc.poll() is None:
    try:
        output=subprocess.check_output(['/bin/ps','-o','rss=','-p',str(proc.pid)],text=True,stderr=subprocess.DEVNULL).strip()
        if output:
            peak_rss_kib=max(peak_rss_kib,int(output.split()[0])); samples+=1
    except (subprocess.CalledProcessError,ValueError):
        pass
    if time.monotonic()-start>=timeout_seconds:
        terminated_for_timeout=True
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait()
        break
    time.sleep(.25)
return_code=proc.wait()
wall=time.monotonic()-start
# Close parent-held descriptors before reading logs.
try: proc.stdout.close()
except Exception: pass
try: proc.stderr.close()
except Exception: pass

stdout=stdout_path.read_bytes() if stdout_path.exists() else b''
stderr=stderr_path.read_bytes() if stderr_path.exists() else b''
after_source=verify_source('after')
post=resource_snapshot()
junit_summary={'exists':junit_path.exists()}
if junit_path.exists():
    try:
        tree=ET.parse(junit_path).getroot()
        suites=[tree] if tree.tag=='testsuite' else tree.findall('.//testsuite')
        junit_summary.update({key:sum(int(suite.attrib.get(key,'0')) for suite in suites) for key in ['tests','failures','errors','skipped']})
        junit_summary['time_seconds']=sum(float(suite.attrib.get('time','0')) for suite in suites)
    except Exception as exc:
        junit_summary['parse_error']=f'{type(exc).__name__}: {exc}'

receipt={
 'schema':'policyos.e02.local-test-receipt.v1',
 'candidate_sha':manifest['candidate_sha'],'candidate_tree':manifest['candidate_tree'],
 'g_checkout_head_before':pre['git_head'],'g_checkout_head_after':post['git_head'],
 'g_branch_before':pre['git_branch'],'g_branch_after':post['git_branch'],
 'command':command,'cwd':str(root),'environment':env_for_receipt,
 'interpreter':str(interpreter),'python_version':shell([str(interpreter),'--version']),
 'timeout_seconds':timeout_seconds,'terminated_for_timeout':terminated_for_timeout,
 'process_exit_code':return_code,'wall_seconds':round(wall,3),
 'peak_rss_kib_sampled':peak_rss_kib,'rss_samples':samples,
 'source_before':before_source,'source_after':after_source,
 'junit':junit_summary,
 'stdout':{'path':str(stdout_path),'bytes':len(stdout),'sha256':sha(stdout)},
 'stderr':{'path':str(stderr_path),'bytes':len(stderr),'sha256':sha(stderr)},
 'junit_path':str(junit_path),'origins_path':str(origins_path),
 'resources_before':pre,'resources_after':post,
 'test_outcome':None,
}
origin_report=json.loads(origins_path.read_text(encoding='utf-8')) if origins_path.exists() else None
if terminated_for_timeout or return_code in (2,3,4,5,98) or not junit_path.exists():
    receipt['test_outcome']='ERROR'
elif junit_summary.get('errors',0)>0 or junit_summary.get('tests')!=10 or after_source['status']!='PASS' or not origin_report or origin_report.get('origin_problems'):
    receipt['test_outcome']='ERROR'
elif junit_summary.get('failures',0)>0 or return_code==1:
    receipt['test_outcome']='FAIL'
elif return_code==0 and junit_summary.get('tests')==10 and junit_summary.get('skipped')==0:
    receipt['test_outcome']='PASS'
else:
    receipt['test_outcome']='ERROR'
receipt['origin_summary']={key:origin_report.get(key) for key in ['polisyos_modules_loaded','polisyos_origins_matched','origin_problems']} if origin_report else None
receipt_path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
source_check_path.write_text(json.dumps({'before':before_source,'after':after_source},indent=2)+'\n',encoding='utf-8')

print(json.dumps({key:receipt[key] for key in ['candidate_sha','candidate_tree','command','process_exit_code','test_outcome','wall_seconds','peak_rss_kib_sampled','junit','source_before','source_after','stdout','stderr','resources_before','resources_after']},indent=2))
