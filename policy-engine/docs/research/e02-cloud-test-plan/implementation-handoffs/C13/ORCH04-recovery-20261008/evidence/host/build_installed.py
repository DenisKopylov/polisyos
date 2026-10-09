from pathlib import Path
import datetime, hashlib, json, os, shutil, subprocess, tarfile, time, zipfile
ROOT=Path('/workspace/ORCH04-evidence/c13/installed');ROOT.mkdir(parents=True,exist_ok=True)
PROJECT=Path('/workspace/ORCH04-C13/policy-engine'); SHA='0321633c0e6d9a87bccfbbe889a4998934c52dd3'
BASE=Path('/workspace/ORCH04-environments'); CARRIERS=BASE/'installed-check-carriers';CARRIERS.mkdir(exist_ok=True)
ENV=os.environ.copy();ENV.update({'PATH':'/workspace/.polisyos-environment/bin:/workspace/.polisyos-environment/uv/bin:/workspace/.polisyos-environment/node-v22.23.3-linux-x64/bin:'+ENV['PATH'],'UV_CACHE_DIR':'/workspace/.polisyos-environment/cache/uv','TMPDIR':str(BASE/'tmp'),'PYTHONDONTWRITEBYTECODE':'1'})
PYTHON='/workspace/.polisyos-environment/python/cpython-3.14.2-linux-x86_64-gnu/bin/python3.14'
TOOLLOCK='/workspace/ORCH04-evidence/host/packaging-tooling.lock'
APP_SITE=BASE/'app/lib/python3.14/site-packages'
commands=[]
def run(label,argv,cwd=PROJECT,extra=None):
    env=ENV.copy()
    if extra: env.update(extra)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat();begin=time.monotonic()
    with (ROOT/(label+'.log')).open('wb') as out:
        p=subprocess.Popen(argv,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT)
        record={'label':label,'argv':argv,'cwd':str(cwd),'pid':p.pid,'started_utc':started,'source':SHA,'extra_env':extra or {},'output':str(ROOT/(label+'.log'))}
        (ROOT/(label+'-running.json')).write_text(json.dumps(record,indent=2)+'\n')
        child,status,usage=os.wait4(p.pid,0);p.returncode=os.waitstatus_to_exitcode(status)
    record.update({'exit_code':p.returncode,'wall_seconds':time.monotonic()-begin,'max_rss_kib':usage.ru_maxrss,'user_cpu_seconds':usage.ru_utime,'system_cpu_seconds':usage.ru_stime,'output_sha256':hashlib.sha256((ROOT/(label+'.log')).read_bytes()).hexdigest()})
    (ROOT/(label+'.json')).write_text(json.dumps(record,indent=2)+'\n');commands.append(record)
    print(json.dumps({'label':label,'exit_code':p.returncode,'wall_seconds':record['wall_seconds']}),flush=True)
    if p.returncode: raise RuntimeError(f'{label}: exit{p.returncode}; full deciding output {record["output"]}')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT).decode().strip()==SHA
assert not subprocess.check_output(['git','status','--porcelain'],cwd=PROJECT)
run('wheel-build',['uv','build','--wheel','--out-dir',str(ROOT/'source-wheel'),'--build-constraint',TOOLLOCK])
run('sdist-build',['uv','build','--sdist','--out-dir',str(ROOT/'sdist'),'--build-constraint',TOOLLOCK])
sdist=next((ROOT/'sdist').glob('*.tar.gz')); extract=BASE/'rebuilt-sdist-source';extract.mkdir(exist_ok=True)
with tarfile.open(sdist) as archive: archive.extractall(extract,filter='data')
(rebuilt_root,)=extract.iterdir()
run('rebuilt-sdist-wheel',['uv','build','--wheel','--out-dir',str(ROOT/'rebuilt-wheel'),'--build-constraint',TOOLLOCK],cwd=rebuilt_root)
asset_names=['worker.py','protocol.py','pyproject.toml','uv.lock','.python-version','README.md']
expected={'assets':{name:{'sha256':hashlib.sha256((PROJECT/'workers/dowhy-014'/name).read_bytes()).hexdigest(),'bytes':(PROJECT/'workers/dowhy-014'/name).stat().st_size} for name in asset_names}}
(ROOT/'profile-expected.json').write_text(json.dumps(expected,indent=2)+'\n')
carrier_manifest={}
for name in ['test_installed_worker_profile.py','test_dowhy_worker.py','test_gcm_backend_contract.py']:
    source=PROJECT/'tests/unit/foundry/methods/catalog/causal'/name; destination=CARRIERS/name;shutil.copyfile(source,destination)
    data=destination.read_bytes(); assert data==source.read_bytes()
    carrier_manifest[name]={'original_path':str(source),'runtime_carrier':str(destination),'sha256':hashlib.sha256(data).hexdigest(),'git_blob':subprocess.check_output(['git','hash-object','--stdin'],input=data).decode().strip(),'bytes':len(data)}
(ROOT/'carrier-manifest.json').write_text(json.dumps({'source':SHA,'files':carrier_manifest,'qualification':'Exact unmodified runtime test carriers, separate from receipts; avoid checkout parent conftest/source imports.'},indent=2)+'\n')
wheel_manifests={};profile_runs={}
for kind,folder in [('wheel','source-wheel'),('rebuilt-sdist','rebuilt-wheel')]:
    wheel=next((ROOT/folder).glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        content={name:hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist() if not name.endswith('/RECORD')}
        for name,row in expected['assets'].items():
            assert content['polisyos/foundry/methods/catalog/causal/_dowhy_profile/'+name]==row['sha256']
        resource_names=['seed_variable_alignments.yaml','proxy_metric_alignments.yaml','wvs_indicator_registry.yaml','metrics_map.yaml']
        for name in resource_names:
            source=PROJECT/'data/dataset_catalog'/name
            assert content['polisyos/data_forge/domains/catalog/_resources/'+name]==hashlib.sha256(source.read_bytes()).hexdigest()
    wheel_manifests[kind]={'path':str(wheel),'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'bytes':wheel.stat().st_size,'members_except_record':content,'four_curated_resources':resource_names,'worker_assets':expected}
    env_path=BASE/('installed-'+kind)
    run(kind+'-venv',['uv','venv','--python',PYTHON,str(env_path)])
    site=env_path/'lib/python3.14/site-packages'
    # Reuse literal locked third-party dependency files; .pth files in APP_SITE are not traversed.
    # Own installed package precedes this path. All product origins are checked inside the harness.
    (site/'orch04_locked_thirdparty_dependencies.pth').write_text(str(APP_SITE)+'\n')
    interpreter=str(env_path/'bin/python')
    run(kind+'-install',['uv','pip','install','--python',interpreter,'--no-deps',str(wheel)])
    run(kind+'-consumer',[interpreter,'-I',str(ROOT/'launch_installed.py'),str(ROOT),kind,str(CARRIERS)],cwd=CARRIERS,extra={'E02_DOWHY_FIXTURE_PATH':str(CARRIERS/'test_dowhy_worker.py'),'E02_GCM_FIXTURE_PATH':str(CARRIERS/'test_gcm_backend_contract.py'),'E02_PROFILE_EXPECTED_JSON':str(ROOT/'profile-expected.json'),'E02_TEST_DOWHY_WORKER_PYTHON':str(BASE/'worker/bin/python')})
assert wheel_manifests['wheel']['members_except_record']==wheel_manifests['rebuilt-sdist']['members_except_record']
(ROOT/'artifacts.json').write_text(json.dumps({'source':SHA,'sdist':{'path':str(sdist),'sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'bytes':sdist.stat().st_size},'wheels':wheel_manifests,'wheel_and_rebuilt_sdist_wheel_complete_member_identity':True,'commands':commands},indent=2)+'\n')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=PROJECT)
