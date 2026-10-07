"""Build one source-bound candidate wheel; preserve every actual command output."""
from pathlib import Path
import hashlib, io, json, os, subprocess, sys, time, tomllib, zipfile

BASE=Path(__file__).resolve().parent/'installed-4ee'
BASE.mkdir(exist_ok=False)
ROOT=Path('/workspace/e02-F-closeout-20261006')
SHA='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
TREE='551d4e760dc1168f6ad8182c9b176f00e94a2281'
APP=ROOT/'policy-engine/.venv/bin/python'
DEPS=ROOT/'policy-engine/.venv/lib/python3.14/site-packages'
git=lambda *args:subprocess.check_output(['git','-C',str(ROOT),*args])
def ref(path):
 p=Path(path);raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def write(name,obj):
 p=BASE/name;assert not p.exists();p.write_text(json.dumps(obj,indent=2)+'\n');return ref(p)
entries={}
for item in git('ls-tree','-rz','--full-tree',SHA).split(b'\0'):
 if item:
  metadata,path=item.split(b'\t',1);mode,kind,oid=metadata.decode().split();entries[path.decode()]=oid
hatch=tomllib.loads(git('show',SHA+':policy-engine/hatch.toml').decode())
resources=hatch['build']['targets']['wheel']['force-include']
selected={p:oid for p,oid in entries.items() if p.startswith(('policy-engine/src/polisyos/','policy-engine/tools/'))}
for p in ('policy-engine/pyproject.toml','policy-engine/hatch.toml','policy-engine/uv.lock',*('policy-engine/'+p for p in resources)):selected[p]=entries[p]
queries=list(selected.values());result=subprocess.run(['git','-C',str(ROOT),'cat-file','--batch'],input=('\n'.join(queries)+'\n').encode(),capture_output=True,check=True)
stream=io.BytesIO(result.stdout);contents={}
for path,oid in selected.items():
 header=stream.readline().decode().split();assert header[:2]==[oid,'blob'];raw=stream.read(int(header[2]));assert stream.read(1)==b'\n';contents[path]=raw
assert not stream.read()
def guard():
 assert git('rev-parse','HEAD').decode().strip()==SHA
 assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
 assert not git('diff','--name-only','HEAD','--','policy-engine/src','policy-engine/tools','policy-engine/workers','policy-engine/pyproject.toml','policy-engine/hatch.toml','policy-engine/uv.lock','policy-engine/data/dataset_catalog')
 for path,raw in contents.items():assert (ROOT/path).read_bytes()==raw,path
guard()
environment=os.environ.copy();environment.pop('PYTHONPATH',None);environment.update({'UV_CACHE_DIR':str(BASE/'uv-cache'),'PYTHONDONTWRITEBYTECODE':'1'})
records=[]
def run(name,argv,cwd):
 guard();start=time.monotonic();r=subprocess.run(argv,cwd=cwd,env=environment,capture_output=True)
 record={'source_sha':SHA,'source_tree':TREE,'argv':[str(a) for a in argv],'cwd':str(cwd),'exit_code':r.returncode,'seconds':time.monotonic()-start,'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1','UV_CACHE_DIR':environment['UV_CACHE_DIR']}}
 for kind,raw in [('stdout',r.stdout),('stderr',r.stderr)]:p=BASE/(name+'.'+kind+'.txt');p.write_bytes(raw);record[kind]=ref(p)
 write(name+'.execution.json',record);records.append(record);guard();assert r.returncode==0,record
run('uv-version',['uv','--version'],BASE)
run('build-wheel',['uv','build','--python',str(APP),'--wheel','--out-dir',str(BASE/'dist')],ROOT/'policy-engine')
wheels=list((BASE/'dist').glob('*.whl'));assert len(wheels)==1
wheel=wheels[0];env=BASE/'wheel-env'
run('create-env',['uv','venv','--python',str(APP),str(env)],BASE)
python=env/'bin/python'
run('install-wheel',['uv','pip','install','--python',str(python),'--no-deps',str(wheel)],BASE)
site=env/'lib/python3.14/site-packages';assert site.is_dir() and DEPS.is_dir()
(site/'e02_readonly_dependencies.pth').write_text(str(DEPS)+'\n')
expected={};bindings=[]
for path,raw in contents.items():
 if path.startswith(('policy-engine/src/polisyos/','policy-engine/tools/')):
  target=path.removeprefix('policy-engine/src/').removeprefix('policy-engine/');expected[target]=raw;bindings.append({'source':path,'git_blob':entries[path],'destination':target,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':'tracked_product'})
for source,target in resources.items():
 raw=contents['policy-engine/'+source];assert target not in expected;expected[target]=raw;bindings.append({'source':'policy-engine/'+source,'git_blob':entries['policy-engine/'+source],'destination':target,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':'forced_resource'})
def installed_guard():
 with zipfile.ZipFile(wheel) as whl:
  actual={n for n in whl.namelist() if n.startswith(('polisyos/','tools/')) and not n.endswith('/')};assert actual==set(expected),(actual-set(expected),set(expected)-actual)
  for target,raw in expected.items():assert whl.read(target)==raw and (site/target).read_bytes()==raw,target
 actual_python={p.relative_to(site).as_posix() for folder in ('polisyos','tools') for p in (site/folder).rglob('*.py')};assert actual_python=={t for t in expected if t.endswith('.py')}
 return {'outcome':'PASS','product_and_resources':len(expected),'actual_python':len(actual_python),'wheel':ref(wheel),'site':str(site)}
write('pre-native-custody.json',{'source_sha':SHA,'source_tree':TREE,'bindings':bindings,**installed_guard()})
old=Path('/tmp/e02-F-continuation-20261007/foundry/installed-default-resource-forward/carrier-manifest.json');old_rows=json.loads(old.read_text())['files']
target='policy-engine/tests/unit/scientist/methods/causal/test_graph_intake_current_content.py'
paths={r['path'] for r in old_rows if r['path'].startswith('policy-engine/tests/_helpers/') or r['path'].endswith('/conftest.py') or r['path']==target}
carrier=BASE/'wheel-consumer';carrier.mkdir();carrier_rows=[]
for path in sorted(paths):
 raw=git('show',SHA+':'+path);out=carrier/path.removeprefix('policy-engine/');out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw);carrier_rows.append({'git_sha':SHA,'path':path,'git_blob':entries[path],**ref(out)})
write('carrier-manifest.json',{'source_sha':SHA,'source_tree':TREE,'files':carrier_rows})
config={'source_sha':SHA,'source_tree':TREE,'git_root':str(ROOT),'source_root':str(ROOT),'scratch':str(BASE),'site':str(site),'python':str(python),'wheel':str(wheel),'dependency_site':str(DEPS),'carrier':str(carrier),'carrier_manifest':str(BASE/'carrier-manifest.json'),'metrics_port':'9466','selectors':json.loads((BASE.parent/'narrow-installed-plan.json').read_text())['selectors']}
write('installed-config.json',config)
guard();print(json.dumps({'outcome':'PASS_SETUP_ONLY','config':str(BASE/'installed-config.json'),'wheel':ref(wheel),'bindings':len(bindings),'site':str(site),'resources':len(resources),'native':'UNRUN'}))
