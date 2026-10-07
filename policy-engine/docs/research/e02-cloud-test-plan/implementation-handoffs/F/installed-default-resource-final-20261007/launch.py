"""Execute unchanged current Graph plus actual installed curated-default callers."""
import hashlib,json,os,platform,sys
from pathlib import Path
sys.dont_write_bytecode=True
import pytest
config=json.loads(Path(sys.argv[1]).read_text());kind=sys.argv[2];base=Path(config['scratch']);site=Path(config['sites'][kind]).resolve();carrier=base/(kind+'-consumer')
assert sys.flags.isolated==1 and Path.cwd()==carrier and not (carrier/'src').exists()
assert not any(Path(p).is_relative_to(Path(config['source_root'])) for p in sys.path if p)
manifest=json.loads(Path(config['carrier_manifest']).read_text())
for ref in manifest['files']:
 raw=(carrier/ref['path'].removeprefix('policy-engine/')).read_bytes();assert len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
os.environ.pop('PYTHONPATH',None);os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['POLISYOS_DOWHY_WORKER_PYTHON']=config['worker_python'];os.environ['E02_PROFILE_EXPECTED_JSON']=str(base/'profile-expected.json');os.environ['E02_CATALOG_EXPECTED_JSON']=config['catalog_expected']
class Collection:
 def pytest_collection_finish(self,session):
  self.ids=[item.nodeid for item in session.items]
  assert len(self.ids)==config['expected_cases_per_profile'],len(self.ids)
collection=Collection()
argv=['-q','-s','-ra','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--basetemp='+str(base/(kind+'-pytest-tmp')),'--junitxml='+str(base/(kind+'-junit.xml')),*[str(carrier/p) for p in config['selectors']]]
status=pytest.main(argv,plugins=[collection])
origins={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.copy().items() if name.startswith(('polisyos','tools')) and getattr(module,'__file__',None)}
violations={name:path for name,path in origins.items() if not Path(path).is_relative_to(site)}
proof={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'python':platform.python_version(),'executable':sys.executable,'isolated':sys.flags.isolated,'cwd':str(Path.cwd()),'sys_path':sys.path,'pytest_argv':argv,'pytest_exit':int(status),'collected_ids':getattr(collection,'ids',[]),'product_origins':origins,'origin_violations':violations,'reader_scope':'actual four native Graph modules plus installed immutable resource/default callers, no TMLE/refit/worker inference/admission positives','authority':'No operational/statistical/value admission or competing-study budget witness.'}
(base/(kind+'-installed-proof.json')).write_text(json.dumps(proof,indent=2)+'\n');assert not violations,violations
print(json.dumps({'source_sha':config['source_sha'],'kind':kind,'pytest_exit':int(status),'cases':len(getattr(collection,'ids',[])),'owned_product_origins':len(origins),'origin_violations':len(violations)}));raise SystemExit(status)
