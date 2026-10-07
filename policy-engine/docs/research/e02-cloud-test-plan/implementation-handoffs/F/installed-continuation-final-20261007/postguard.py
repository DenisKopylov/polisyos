"""Reconcile actual complete installed bytes and immutable inputs after the native wave."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
base=Path(__file__).resolve().parent
config=json.loads((base/'installed-config.json').read_text())
binding=json.loads((base/'archive-installed-source-bindings.json').read_text())
started=time.monotonic();count=0
for kind,site in config['sites'].items():
 site=Path(site)
 for row in binding['source_bindings']:
  raw=(site/row['destination']).read_bytes()
  assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],(kind,row['destination'])
  count+=1
 actual={p.relative_to(site).as_posix() for parent in ('polisyos','tools') for p in (site/parent).rglob('*.py')}
 expected={row['destination'] for row in binding['source_bindings'] if row['destination'].endswith('.py')}
 assert actual==expected,(kind,'extra/missing product Python files')
 assert (site/'e02_readonly_dependencies.pth').read_text()==config['dependency_site']+'\n'
for kind,row in binding['archives'].items():
 p=Path(row['path']);assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],kind
carriers=json.loads(Path(config['carrier_manifest']).read_text())
for kind in ('wheel','sdist'):
 carrier=base/(kind+'-consumer')
 assert not (carrier/'src').exists()
 for row in carriers['files']:
  raw=(carrier/row['path'].removeprefix('policy-engine/')).read_bytes()
  assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],(kind,row['path'])
assert subprocess.check_output(['git','-C',config['git_root'],'rev-parse',config['source_sha']+'^{tree}']).decode().strip()==config['source_tree']
source_proof=json.loads(Path(config['source_export_proof']).read_text());aggregate=hashlib.sha256();total=0;source_count=0
for item in subprocess.check_output(['git','-C',config['git_root'],'ls-tree','-rz','--full-tree',config['source_sha']]).split(b'\0'):
 if not item:continue
 _,name=item.split(b'\t',1);name=name.decode();raw=(Path(config['source_root'])/name).read_bytes()
 aggregate.update((name+'\0'+hashlib.sha256(raw).hexdigest()+'\0'+str(len(raw))+'\n').encode());total+=len(raw);source_count+=1
assert aggregate.hexdigest()==source_proof['ordered_path_hash_size_aggregate'] and total==source_proof['complete_bytes_verified']
proof={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'outcome':'PASS','complete_site_product_resource_file_checks':count,'complete_archives_rechecked':len(binding['archives']),'complete_Git_source_files_rechecked':source_count,'complete_Git_source_bytes_rechecked':total,'complete_carrier_files_each_profile':len(carriers['files']),'source_aggregate':aggregate.hexdigest(),'literal_dependency_pth_only':True,'product_Python_extra_missing':[],'source_fallback':False,'wall_seconds':time.monotonic()-started,'scope':'Custody only; scientific/numerical/native outcomes retain own PASS/FAIL/ERROR statuses.'}
(base/'post-native-custody.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
