from pathlib import Path
import os,subprocess,json,time,hashlib,sys,xml.etree.ElementTree as ET
root=Path('/workspace/e02-F-economics-20261006');product=root/'policy-engine';dest=Path('/tmp/e02-F-continuation-20261007/economics');py='/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python';sha='193b3582a72c640c1d06a131f93502654a77a36a';tree='81c2e3e636bec4c5d81b8f918bb61cca6a49309b'
kind=sys.argv[1]
def git(*a):return subprocess.check_output(['git',*a],cwd=root,text=True).strip()
def guard():assert git('rev-parse','HEAD')==sha and git('rev-parse','HEAD^{tree}')==tree and not git('status','--porcelain','--untracked-files=no')
selectors=['tests/unit/foundry/plugins/test_historical_income_baseline.py','tests/unit/foundry/agent_sim/test_signed_gini_producer_route.py','tests/unit/foundry/plugins/test_economic_profiles.py','tests/unit/foundry/plugins/test_economic_profile_consumers.py','tests/unit/foundry/analysis/test_loss_numeric.py','tests/unit/remediation/test_eco_01.py']
new=selectors[:2]
if kind=='native':argv=[py,'-m','pytest','-p','no:cacheprovider','-p','origin_plugin',*selectors,'-v','--tb=short','--junitxml='+str(dest/(kind+'.xml'))]
elif kind in ['ruff','format']:argv=[str(Path(py).with_name('ruff')),'check' if kind=='ruff' else 'format',*(['--check'] if kind=='format' else []),*new]
elif kind.startswith('removal-'):argv=[py,str(dest/'removal.py'),kind.removeprefix('removal-')]
else:raise ValueError(kind)
env=os.environ.copy();env.update({'PYTHONPATH':str(product/'src')+':'+str(product/'tools')+':'+str(product)+':'+str(dest),'PYTHONDONTWRITEBYTECODE':'1','ECO_ORIGIN_OUTPUT':str(dest/(kind+'-origins.json'))})
guard();start=time.monotonic()
with (dest/(kind+'.stdout.txt')).open('wb') as out,(dest/(kind+'.stderr.txt')).open('wb') as err:r=subprocess.run(argv,cwd=product,env=env,stdout=out,stderr=err)
guard();receipt={'command':argv,'cwd':str(product),'source_sha':sha,'source_tree':tree,'runtime_source_sha':'8236d9c368336a5ea20c1586f29aea7321db6536','published_C_G_source_sha':'9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7','exit_code':r.returncode,'wall_seconds':time.monotonic()-start,'check':'PASS' if r.returncode==0 else 'ERROR' if r.returncode<0 else 'FAIL','environment':{'interpreter':py,'PYTHONPATH':env['PYTHONPATH'],'PYTHONDONTWRITEBYTECODE':'1'},'outputs':[]}
for p in [dest/(kind+'.stdout.txt'),dest/(kind+'.stderr.txt'),dest/(kind+'.xml'),dest/(kind+'-origins.json')]:
 if p.is_file():b=p.read_bytes();receipt['outputs'].append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
if kind=='native':
 receipt['inputs']=[{'path':x,'bytes':len((product/x).read_bytes()),'sha256':hashlib.sha256((product/x).read_bytes()).hexdigest()} for x in selectors]
 suites=ET.parse(dest/(kind+'.xml')).getroot();receipt['test_counts']={k:sum(int(s.get(k,0)) for s in suites.findall('testsuite')) for k in ['tests','failures','errors','skipped']}
(dest/(kind+'.receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:receipt[k] for k in ['check','exit_code','wall_seconds']}));print(receipt.get('test_counts',{}))
