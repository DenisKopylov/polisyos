import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
import networkx,pytest
root=Path('/workspace/e02-F-installed-worker-20261006')
scratch=Path('/workspace/e02-F-20261006-receipts/installed-latest')
owned=Path('/workspace/e02-F-20261006-receipts/final-root/installed-latest-independent')
source='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
kind=sys.argv[1];manifest=json.loads((scratch/(kind+'-setup-manifest.json')).read_text());site=Path(manifest['site'])
assert sys.flags.isolated and not any(p.endswith('/src') for p in sys.path)
carrier=owned/(kind+'-cache-consumer')/'test_installed_worker_profile.py';carrier.parent.mkdir(exist_ok=True)
path='policy-engine/tests/unit/foundry/methods/catalog/causal/test_installed_worker_profile.py'
raw=subprocess.check_output(['git','show',source+':'+path],cwd=root);carrier.write_bytes(raw)
assert hashlib.sha256(raw).hexdigest()==manifest['carriers'][carrier.name]['sha256']
own=owned/'test_b220_independent.py'
assert own.read_bytes()==Path('/workspace/e02-F-20261006-receipts/final-root/b220-independent-review/test_b220_independent.py').read_bytes()
argv=['-o','addopts=','-q',str(carrier)+'::test_public_canonical_helpers_and_pure_report_factory_identity',str(own)]
print(json.dumps({'source_sha':source,'kind':kind,'python':platform.python_version(),'executable':sys.executable,'site':str(site),'isolated':sys.flags.isolated,'sys_path':sys.path,'networkx_version':networkx.__version__,'networkx_origin':networkx.__file__,'argv':argv,'test_carriers':{'worker':{'source_path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'independent':{'path':str(own),'bytes':own.stat().st_size,'sha256':hashlib.sha256(own.read_bytes()).hexdigest()}}},sort_keys=True))
code=pytest.main(argv)
origins={n:m.__file__ for n,m in sys.modules.copy().items() if n.startswith('polisyos') and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(site) for p in origins.values()),origins
print(json.dumps({'product_origins':origins,'product_origin_count':len(origins),'source_origin_violations':0},sort_keys=True))
raise SystemExit(code)
