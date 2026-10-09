from pathlib import Path
import hashlib, importlib.metadata, json, os, platform, sys
import pytest
root=Path(sys.argv[1]);kind=sys.argv[2];carriers=Path(sys.argv[3]);site=Path(sys.prefix)/'lib/python3.14/site-packages'
assert sys.flags.isolated and Path.cwd()==carriers
assert not any('/src' in p for p in sys.path),sys.path
manifest=json.loads((root/'carrier-manifest.json').read_text())
for name,row in manifest['files'].items():
    assert hashlib.sha256((carriers/name).read_bytes()).hexdigest()==row['sha256']
class Collected:
    def pytest_collection_finish(self,session):self.ids=[item.nodeid for item in session.items]
collected=Collected()
argv=['-q','-s','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--basetemp='+str(root/(kind+'-basetemp')),'--junitxml='+str(root/(kind+'-junit.xml')),str(carriers/'test_installed_worker_profile.py')]
status=pytest.main(argv,plugins=[collected])
origins={name:str(Path(m.__file__).resolve()) for name,m in sys.modules.copy().items() if name.startswith(('polisyos','tools')) and getattr(m,'__file__',None)}
violations={name:path for name,path in origins.items() if not Path(path).is_relative_to(site)}
proof={'kind':kind,'source':manifest['source'],'python':platform.python_version(),'executable':sys.executable,'sys_prefix':sys.prefix,'isolated':sys.flags.isolated,'sys_path':sys.path,'cwd':str(Path.cwd()),'pytest_argv':argv,'pytest_exit':int(status),'collected_ids':getattr(collected,'ids',[]),'product_origins':origins,'origin_violations':violations,'dependency_reuse':'Literal locked app site directory; dependency .pth files not traversed; no checkout/src import. Fresh artifact interpreter and actual installed wheel.','authority':'Known synthetic computation only; no real causal/public/production authority.'}
(root/(kind+'-origin-proof.json')).write_text(json.dumps(proof,indent=2)+'\n')
assert not violations,violations
assert len(getattr(collected,'ids',[]))==3,getattr(collected,'ids',[])
print(json.dumps({'kind':kind,'collected_tests':len(collected.ids),'product_origins':len(origins),'origin_violations':len(violations),'pytest_exit':int(status)}))
raise SystemExit(status)
