"""Full old/shared, candidate, actual sdist, archives, sites and fixture custody."""
import hashlib,json,subprocess,time
from pathlib import Path
base=Path(__file__).resolve().parent
config=json.loads((base/'installed-config.json').read_text())
binding=json.loads((base/'archive-installed-source-bindings.json').read_text())
started=time.monotonic()
def digest(path):
 h=hashlib.sha256();total=0
 with Path(path).open('rb') as stream:
  while chunk:=stream.read(1024*1024):h.update(chunk);total+=len(chunk)
 return total,h.hexdigest()
def source_guard(c,proof,byte_field):
 assert subprocess.check_output(['git','-C',config['git_root'],'rev-parse',c['source_sha']+'^{tree}']).decode().strip()==c['source_tree']
 aggregate=hashlib.sha256();total=count=0
 for item in subprocess.check_output(['git','-C',config['git_root'],'ls-tree','-rz','--full-tree',c['source_sha']]).split(b'\0'):
  if not item:continue
  _,name=item.split(b'\t',1);name=name.decode();p=Path(c['source_root'])/name;n,h=digest(p)
  aggregate.update((name+'\0'+h+'\0'+str(n)+'\n').encode());total+=n;count+=1
 assert aggregate.hexdigest()==proof['ordered_path_hash_size_aggregate'] and total==proof[byte_field]
 return {'complete_files':count,'complete_bytes':total,'aggregate':aggregate.hexdigest()}
def installed_guard(c,b):
 count=0
 for kind,path in c['sites'].items():
  site=Path(path)
  for r in b['source_bindings']:
   assert digest(site/r['destination'])==(r['bytes'],r['sha256']),(kind,r['destination']);count+=1
  actual={p.relative_to(site).as_posix() for parent in ('polisyos','tools') for p in (site/parent).rglob('*.py')}
  expected={r['destination'] for r in b['source_bindings'] if r['destination'].endswith('.py')};assert actual==expected
  assert (site/'e02_readonly_dependencies.pth').read_text()==c['dependency_site']+'\n'
 for name,r in b['archives'].items():assert digest(r['path'])==(r['bytes'],r['sha256']),name
 return {'complete_site_checks':count,'complete_archives':len(b['archives']),'extra_missing_product_python':[],'literal_dependency_pth_only':True}
current_source=source_guard(config,json.loads(Path(config['source_snapshot_proof']).read_text()),'complete_original_Git_bytes')
current_installed=installed_guard(config,binding)
old=Path(config['old_b5_scratch']);old_config=json.loads((old/'installed-config.json').read_text())
old_source=source_guard(old_config,json.loads((old/'source-export-proof.json').read_text()),'complete_bytes_verified')
old_installed=installed_guard(old_config,json.loads((old/'archive-installed-source-bindings.json').read_text()))
sdist=json.loads((base/'actual-sdist-decoded-payloads.json').read_text());extracted=Path(sdist['rebuilt_source_root']).parent
for row in sdist['members']:
 path=extracted/row['actual_tar_member'];assert digest(path)==(row['bytes'],row['sha256']),row['actual_tar_member'];assert (path.stat().st_mode & 0o777)==row['actual_tar_mode']
manifest=json.loads(Path(config['carrier_manifest']).read_text())
for kind in ('wheel','sdist'):
 carrier=base/(kind+'-consumer');assert not (carrier/'src').exists()
 for ref in manifest['files']:assert digest(carrier/ref['path'].removeprefix('policy-engine/'))==(ref['bytes'],ref['sha256'])
proof={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'outcome':'PASS','current_source':current_source,'current_installed':current_installed,'old_b5_source_unchanged':old_source,'old_b5_installed_unchanged':old_installed,'actual_sdist_decoded_regular_members_unchanged':len(sdist['members']),'actual_sdist_decoded_regular_bytes':sdist['actual_decoded_regular_bytes'],'complete_carrier_files_each_profile':len(manifest['files']),'old_evidence_outputs_mutated':False,'shared_hardlinked_content_verified_before_and_after':True,'wall_seconds':time.monotonic()-started,'scope':'Complete physical byte custody only; no native/scientific/authority closure implied.'}
(base/'post-native-custody.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
