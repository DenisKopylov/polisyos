"""Actual neutral installed graph cases; no source path or editable fallback."""
from pathlib import Path
import hashlib,json,os,platform,sys
sys.dont_write_bytecode=True
import pytest
config=json.loads(Path(sys.argv[1]).read_text());base=Path(config['scratch']);site=Path(config['site']).resolve();carrier=Path(config['carrier']).resolve();mode=sys.argv[2]
assert sys.flags.isolated==1 and Path.cwd()==carrier and not (carrier/'src').exists()
assert not any(Path(p).is_relative_to(Path(config['source_root'])) and Path(p).resolve()!=Path(config['dependency_site']).resolve() for p in sys.path if p)
manifest=json.loads(Path(config['carrier_manifest']).read_text())
for row in manifest['files']:
 raw=(carrier/row['path'].removeprefix('policy-engine/')).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
assert 'PYTHONPATH' not in os.environ
os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['POLISYOS_METRICS_PORT']=config['metrics_port']
class Collection:
 def pytest_collection_finish(self,session):self.ids=[item.nodeid for item in session.items]
collection=Collection()
argv=['-q','-s','-ra','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--basetemp='+str(base/(mode+'-pytest-tmp')),*[str(carrier/p) for p in config['selectors']]]
if mode=='collect':argv.insert(0,'--collect-only')
else:argv.append('--junitxml='+str(base/(mode+'-junit.xml')))
status=pytest.main(argv,plugins=[collection])
origins={}
for name,module in tuple(sys.modules.items()):
 if name=='polisyos' or name.startswith('polisyos.') or name=='tools' or name.startswith('tools.'):
  filename=getattr(module,'__file__',None)
  if filename:origins[name]=str(Path(filename).resolve());assert Path(filename).resolve().is_relative_to(site),(name,filename)
  for location in getattr(module,'__path__',[]):assert Path(location).resolve().is_relative_to(site),(name,location)
proof={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'mode':mode,'python':platform.python_version(),'executable':sys.executable,'isolated':sys.flags.isolated,'cwd':str(Path.cwd()),'sys_path':sys.path,'pytest_argv':argv,'pytest_exit':int(status),'collected_ids':getattr(collection,'ids',[]),'product_origins':origins,'origin_violations':[],'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1','POLISYOS_METRICS_PORT':os.environ['POLISYOS_METRICS_PORT']},'reader_scope':'Maintained selected graph consumers include same-process reopenedCAS; differentPID proof separately recorded.','limits':'No new sdist, Runtime/EvalSafety/causal identification/value admission or competing-study budget witness.'}
if mode!='collect':assert proof['collected_ids']==json.loads((base/'collect-proof.json').read_text())['collected_ids']
path=base/(mode+'-proof.json');assert not path.exists();path.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'source_sha':config['source_sha'],'mode':mode,'pytest_exit':int(status),'cases':len(proof['collected_ids']),'owned_product_origins':len(origins),'origin_violations':0}));raise SystemExit(status)
