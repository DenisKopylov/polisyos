"""Exact old/new harness execution with one native fixture job, not a common wave."""
from __future__ import annotations
import asyncio, hashlib, json, os, runpy, subprocess
from pathlib import Path

REPO=Path('/workspace/e02-E-continuation-20261006')
OUT=Path('/workspace/e02-E-pr38-r2-receipts/harness-native-parent-repair-5e3e37276')
BASE='5e3e3727685132f270a3a07b9f63dd962a88cd96'
PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/wave-controls/'
PY=REPO/'policy-engine/.venv/bin/python'
OLD=OUT/'old-exact';OLD.mkdir()
for name in ('plan_wave.py','run_check.py'):
    data=subprocess.check_output(['git','-C',str(REPO),'show',BASE+':'+PREFIX+name]);(OLD/name).write_bytes(data)
old=runpy.run_path(str(OLD/'plan_wave.py'),run_name='exact_old_fixture_harness')
new=runpy.run_path(str(OUT/'plan_wave.py'),run_name='new_fixture_harness')
selected=new['runtime_environment'](REPO)
for name in new['CAP_VARIABLES']:selected.pop(name,None)
os.environ.clear();os.environ.update(selected)
results=[]
for name,namespace in [('old-exact',old),('new-parent-admission',new),('removed-parent-property',new)]:
    output=OUT/'native-checks'/name;output.mkdir(parents=True,exist_ok=False)
    temp=output/'temporary/native-case'
    callback=output/'callback-count.json'
    os.environ['NATIVE_CALLBACK_RECEIPT']=str(callback);os.environ['NATIVE_EXPECTED_BASETEMP']=str(temp)
    importer={'name':'native-fixture-preflight','kind':'importer','argv':[str(PY),'-c','print("Native harness fixture preflight only; not results importer")'],'cwd':str(REPO/'policy-engine'),'output':str(output/'checks/native-fixture-preflight'),'junit':None,'environment':{'TMPDIR':str(output/'tmp-env/preflight')}}
    native={'name':'native-tmp-cas','kind':'numerical','argv':[str(PY),'-m','pytest','-q','-s','-c',str(REPO/'policy-engine/pytest.ini'),'-o','cache_dir='+str(output/'cache/pytest'),'--benchmark-storage='+(output/'cache/benchmark').as_uri(),'--junitxml',str(output/'checks/native-tmp-cas/pytest.xml'),'--basetemp',str(temp),str(OUT/'test_native_tmp_cas.py')],'cwd':str(REPO/'policy-engine'),'output':str(output/'checks/native-tmp-cas'),'junit':str(output/'checks/native-tmp-cas/pytest.xml'),'environment':{'TMPDIR':str(output/'tmp-env/native')}}
    plan={'repo':str(REPO),'output_root':str(output),'tracked_dirty':'','candidate_sha':BASE,'observed_head':BASE,'missing_required_paths':[],'required_upstream':{},'owner_packet_extra_inputs':[],'jobs':[importer,native],'interpreter':str(PY)}
    original=None
    if name=='removed-parent-property':
        original=namespace['execute'].__globals__['create_numeric_scratch_parents']
        namespace['execute'].__globals__['create_numeric_scratch_parents']=lambda *args:None
    try:code=asyncio.run(namespace['execute'](plan))
    finally:
        if original is not None:namespace['execute'].__globals__['create_numeric_scratch_parents']=original
    receipt=json.loads((output/'checks/native-tmp-cas/native-tmp-cas.json').read_text())
    row={'case':name,'scope':'bounded native harness fixture only, no full common wave/product family','source_base':BASE,'harness_exit_code':code,'check_outcome':receipt['outcome'],'pytest_exit_code':receipt['exit_code'],'case_counts':receipt['counts'],'native_callback_count':json.loads(callback.read_text())['native_callback_count'] if callback.exists() else 0,'source_immutable':receipt['source_immutable'],'basetemp_parent_exists_after':temp.parent.exists(),'stdout':receipt['stdout_path'],'stdout_sha256':receipt['stdout_sha256'],'stdout_bytes':receipt['stdout_bytes']}
    if name=='new-parent-admission':assert code==0 and receipt['counts']['passed']==1 and row['native_callback_count']==1
    else:assert code!=0 and receipt['counts']['errors']==1 and row['native_callback_count']==0
    results.append(row)
(OUT/'native-parent-results.json').write_text(json.dumps({'scope':'Actual pytest tmp_path and nativeCAS IO; no calibration/backend wave repeated','results':results,'all_deciding_outputs_preserved':True},indent=2)+'\n')
print(json.dumps({'results':results,'full_common_wave_run':False}))
