from pathlib import Path
import hashlib,json,os,resource,subprocess,sys,time
name=sys.argv[1]
root=Path('/dev/shm/e02-orch03-20261008/c09')
product=root/'policy-engine'
python='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
out=Path('/dev/shm/e02-orch03-20261008/c09-scratch')
selectors={
'affected':[
 'tests/unit/scientist/methods/backtesting/test_evaluator_interval_admission.py',
 'tests/unit/scientist/methods/backtesting/test_backtesting.py',
 'tests/unit/remediation/test_bkt_02.py',
 'tests/unit/remediation/test_bkt_03.py'],
'ets':[
 'tests/unit/remediation/test_frc_02_owner.py::test_real_ets_owner_persists_content_bound_predictive_evidence',
 'tests/unit/remediation/test_frc_02_owner.py::test_same_ets_shape_uses_held_out_observations_for_suitability']}
cmd=[python,'-m','pytest','-q',*selectors[name],f'--basetemp={out/name}',f'--junitxml={out/(name+".junit.xml")}', '-o',f'cache_dir={out/(name+"-cache")}']
identity=subprocess.run(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=root,capture_output=True,text=True,check=True).stdout.splitlines()
start=time.monotonic()
with (out/(name+'.stdout.txt')).open('wb') as stdout, (out/(name+'.stderr.txt')).open('wb') as stderr:
 try:
  result=subprocess.run(cmd,cwd=product,stdout=stdout,stderr=stderr,timeout=240)
  returncode=result.returncode
  interrupted=None
 except subprocess.TimeoutExpired:
  returncode=None
  interrupted='harness_timeout_240_seconds'
elapsed=time.monotonic()-start
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
metadata={'source_sha':identity[0],'source_tree':identity[1],'command':cmd,'cwd':str(product),'returncode':returncode,'interrupted':interrupted,'wall_seconds':elapsed,'max_rss_kib':usage.ru_maxrss,'outputs':{}}
for suffix in ['stdout.txt','stderr.txt','junit.xml']:
 p=out/(name+'.'+suffix)
 if p.exists(): metadata['outputs'][suffix]={'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(out/(name+'.execution.json')).write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
print((out/(name+'.stdout.txt')).read_text()[-7000:])
