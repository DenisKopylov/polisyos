from pathlib import Path
import concurrent.futures, datetime, hashlib, json, os, subprocess, time
ROOT=Path('/workspace/ORCH04-evidence/c13'); ROOT.mkdir(exist_ok=True)
PROJECT=Path('/workspace/ORCH04-C13/policy-engine')
SHA='0321633c0e6d9a87bccfbbe889a4998934c52dd3'
ENV=os.environ.copy(); ENV.update({'PATH':'/workspace/.polisyos-environment/bin:/workspace/.polisyos-environment/uv/bin:/workspace/.polisyos-environment/node-v22.23.3-linux-x64/bin:'+ENV['PATH'],'UV_CACHE_DIR':'/workspace/.polisyos-environment/cache/uv','COREPACK_HOME':'/workspace/.polisyos-environment/cache/corepack','npm_config_store_dir':'/workspace/.polisyos-environment/cache/pnpm','NODE_USE_ENV_PROXY':'1','TMPDIR':'/workspace/ORCH04-environments/tmp','E02_TEST_DOWHY_WORKER_PYTHON':'/workspace/ORCH04-environments/worker/bin/python','POLISYOS_DOWHY_WORKER_PYTHON':'/workspace/ORCH04-environments/worker/bin/python','PYTHONDONTWRITEBYTECODE':'1'})
APP='/workspace/ORCH04-environments/app/bin/python'; WORKER='/workspace/ORCH04-environments/worker/bin/python'
manifest={}
for path in ['pyproject.toml','uv.lock','hatch.toml','pnpm-lock.yaml','tests/conftest.py','tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py','tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py','tests/unit/foundry/methods/catalog/causal/test_installed_worker_profile.py']:
    b=(PROJECT/path).read_bytes(); manifest[path]={'git_blob':subprocess.check_output(['git','hash-object','--stdin'],input=b).decode().strip(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
for path in sorted((PROJECT/'workers/dowhy-014').glob('*.py')):
    b=path.read_bytes(); manifest[str(path.relative_to(PROJECT))]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
for path in ['workers/dowhy-014/uv.lock','workers/dowhy-014/pyproject.toml']:
    b=(PROJECT/path).read_bytes();manifest[path]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT).decode().strip()==SHA
assert not subprocess.check_output(['git','status','--porcelain'],cwd=PROJECT)
TREE=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=PROJECT).decode().strip()
(ROOT/'source-manifest.json').write_text(json.dumps({'source':SHA,'tree':TREE,'inputs':manifest,'scope':'Independent scoped conformance; not broad portable replay.'},indent=2)+'\n')
def pytest_args(label):
    return ['-o','addopts=','--import-mode=importlib','--basetemp='+str(ROOT/(label+'-basetemp')),'--junitxml='+str(ROOT/(label+'-junit.xml')),'-q','-s']
JOBS={
'gcm-query':([APP,'-m','pytest',*pytest_args('gcm-query'),'tests/unit/foundry/methods/catalog/causal/test_gcm_backend_contract.py::test_actual_query_consumer_binds_complete_cas_projection_and_original_request'],str(PROJECT)),
'dowhy-native':([APP,'-m','pytest',*pytest_args('dowhy-native'),'tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py'],str(PROJECT)),
'worker-backend':([WORKER,'-m','pytest',*pytest_args('worker-backend'),'tests'],str(PROJECT/'workers/dowhy-014')),
'node-client':(['corepack','pnpm','--filter','@polisyos/runtime-api-client','test'],str(PROJECT)),
'dashboard-contracts':(['corepack','pnpm','--filter','@polisyos/runtime-dashboard','run','test:contracts'],str(PROJECT)),
'dashboard-build':(['corepack','pnpm','--filter','@polisyos/runtime-dashboard','run','build'],str(PROJECT)),
'packaging-contract':([APP,'-m','pytest',*pytest_args('packaging-contract'),'tests/repo_quality/tools/test_hatch_packaging.py'],str(PROJECT)),
}
def snap():
    fs=os.statvfs('/workspace'); return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'memory_current':Path('/sys/fs/cgroup/memory.current').read_text().strip(),'memory_events':Path('/sys/fs/cgroup/memory.events').read_text(),'workspace_available_bytes':fs.f_bavail*fs.f_frsize}
def run(label,job):
    argv,cwd=job;env=ENV.copy()
    if label=='packaging-contract': env['PYTHONPATH']='/workspace/ORCH04-environments/packaging-tools'
    start=datetime.datetime.now(datetime.timezone.utc).isoformat(); t=time.monotonic()
    with (ROOT/(label+'.log')).open('wb') as out:
        actual=argv; proc=subprocess.Popen(actual,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT)
        r={'source':SHA,'tree':TREE,'argv':argv,'actual_wrapper_argv':actual,'cwd':cwd,'pid':proc.pid,'started_utc':start,'resource_before':snap(),'output':str(ROOT/(label+'.log')),'environment_selections':{k:env.get(k) for k in ['TMPDIR','E02_TEST_DOWHY_WORKER_PYTHON','POLISYOS_DOWHY_WORKER_PYTHON','PYTHONPATH','NODE_USE_ENV_PROXY','COREPACK_HOME']}}
        (ROOT/(label+'-running.json')).write_text(json.dumps(r,indent=2)+'\n')
        child_pid, wait_status, usage = os.wait4(proc.pid, 0)
        rc=os.waitstatus_to_exitcode(wait_status)
        proc.returncode=rc
    r.update({'exit_code':rc,'wait4_pid':child_pid,'max_rss_kib':usage.ru_maxrss,'user_cpu_seconds':usage.ru_utime,'system_cpu_seconds':usage.ru_stime,'wall_seconds':time.monotonic()-t,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'resource_after':snap(),'source_status_after':subprocess.check_output(['git','status','--porcelain'],cwd=PROJECT).decode(),'output_sha256':hashlib.sha256((ROOT/(label+'.log')).read_bytes()).hexdigest()})
    (ROOT/(label+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'label':label,'exit_code':rc,'wall_seconds':r['wall_seconds']}),flush=True)
    return r
samples=[snap()]
with concurrent.futures.ThreadPoolExecutor(max_workers=len(JOBS)) as pool:
    futures={pool.submit(run,k,v):k for k,v in JOBS.items()}
    while not all(f.done() for f in futures):
        samples.append(snap());(ROOT/'resource-samples.json').write_text(json.dumps(samples,indent=2)+'\n');time.sleep(2)
    results={futures[f]:f.result() for f in futures}
(ROOT/'scoped-checks.json').write_text(json.dumps({'source':SHA,'tree':TREE,'results':results,'qualification':'Raw runner outcomes. Consumer/property and proxy/removal interpretation requires full deciding output.'},indent=2)+'\n')
