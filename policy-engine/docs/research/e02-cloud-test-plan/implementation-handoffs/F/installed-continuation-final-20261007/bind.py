"""Bind complete frozen Git product/resource bytes to source/rebuilt archives and sites."""
from pathlib import Path
import hashlib,io,json,subprocess,sys,tarfile,tomllib,zipfile
config=json.loads(Path(sys.argv[1]).read_text());root=Path(config['source_root']);scratch=Path(config['scratch']);sha=config['source_sha']
git=lambda *args: subprocess.check_output(['git','-C',config['git_root'],*args])
assert git('rev-parse',sha+'^{tree}').decode().strip()==config['source_tree']
entries={}
for item in git('ls-tree','-rz','--full-tree',sha).split(b'\0'):
 if not item:continue
 meta,path=item.split(b'\t',1);mode,kind,oid=meta.decode().split();name=path.decode()
 if name.startswith(('policy-engine/src/polisyos/','policy-engine/tools/')):
  assert kind=='blob' and mode in ('100644','100755'),(name,kind,mode)
  entries[name]=oid
hatch=tomllib.loads(git('show',sha+':policy-engine/hatch.toml').decode())
resources=hatch['build']['targets']['wheel']['force-include'];assert len(resources)==7,resources
queries=[*entries.values(),*(git('rev-parse',sha+':policy-engine/'+source).decode().strip() for source in resources)]
result=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(queries)+'\n').encode(),cwd=config['git_root'],stdout=subprocess.PIPE,check=True);stream=io.BytesIO(result.stdout);contents=[]
for oid in queries:
 h=stream.readline().decode().strip().split();assert h[0]==oid and h[1]=='blob';d=stream.read(int(h[2]));assert stream.read(1)==b'\n';contents.append(d)
assert not stream.read()
expected={};bindings=[]
for (source,oid),data in zip(entries.items(),contents,strict=False):
 target=source.removeprefix('policy-engine/src/').removeprefix('policy-engine/');assert target not in expected;expected[target]=data;bindings.append({'source':source,'git_blob':oid,'destination':target,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'role':'tracked_product'})
for index,(source,target) in enumerate(resources.items(),start=len(entries)):
 assert target not in expected;data=contents[index];expected[target]=data;bindings.append({'source':'policy-engine/'+source,'git_blob':queries[index],'destination':target,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'role':'forced_resource'})
archives={};sdist=Path(config['archives']['sdist'])
with tarfile.open(sdist) as tar:
 prefix=tar.getnames()[0].split('/')[0]+'/'
 for row in bindings:
  reader=tar.extractfile(prefix+row['source'].removeprefix('policy-engine/'));assert reader is not None and reader.read()==expected[row['destination']],('sdist',row['source'])
 assert not [name for name in tar.getnames() if '/_cache/' in '/'+name]
for kind in ('wheel','rebuilt_wheel'):
 archive=Path(config['archives'][kind])
 with zipfile.ZipFile(archive) as whl:
  names={name for name in whl.namelist() if name.startswith(('polisyos/','tools/')) and not name.endswith('/')};assert names==set(expected),(kind,names-set(expected),set(expected)-names)
  for target,data in expected.items():assert whl.read(target)==data,(kind,target)
  assert not [name for name in whl.namelist() if '/_cache/' in '/'+name]
for name,path in config['archives'].items():
 p=Path(path);archives[name]={'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
sites={}
for kind,path in config['sites'].items():
 site=Path(path)
 for target,data in expected.items():assert (site/target).read_bytes()==data,(kind,target)
 actual_python={p.relative_to(site).as_posix() for folder in ('polisyos','tools') for p in (site/folder).rglob('*.py')};expected_python={target for target in expected if target.endswith('.py')};assert actual_python==expected_python,(kind,actual_python-expected_python,expected_python-actual_python)
 sites[kind]={'path':str(site),'verified_product_files':len(expected),'complete_actual_python_files':len(actual_python),'extra_missing_python':[]}
proof={'source_sha':sha,'source_tree':config['source_tree'],'tracked_product_files':len(entries),'forced_resources':len(resources),'complete_product_resource_files':len(expected),'source_bindings':bindings,'archives':archives,'sites':sites,'outcome':'PASS','scope':'Every declared product/resource file and every actual installed product Python file checked; no scientific/admission claim.'}
p=scratch/'archive-installed-source-bindings.json';p.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:proof[k] for k in ('source_sha','tracked_product_files','forced_resources','complete_product_resource_files','outcome')}))
