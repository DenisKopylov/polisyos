"""Full candidate wheel/site/source and old immutable profile byte guard."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
base=Path(__file__).resolve().parent/'installed-4ee';config=json.loads((base/'installed-config.json').read_text());site=Path(config['site']);proof=json.loads((base/'pre-native-custody.json').read_text())
def digest(p):
 h=hashlib.sha256();n=0
 with Path(p).open('rb') as f:
  while raw:=f.read(1024*1024):h.update(raw);n+=len(raw)
 return {'bytes':n,'sha256':h.hexdigest()}
git=lambda *args:subprocess.check_output(['git','-C',config['git_root'],*args])
assert git('rev-parse','HEAD').decode().strip()==config['source_sha'] and git('rev-parse','HEAD^{tree}').decode().strip()==config['source_tree']
assert digest(config['wheel'])=={k:proof['wheel'][k] for k in ('bytes','sha256')}
with zipfile.ZipFile(config['wheel']) as whl:
 for row in proof['bindings']:
  expected={k:row[k] for k in ('bytes','sha256')};assert digest(Path(config['source_root'])/row['source'])==expected and digest(site/row['destination'])==expected,row
  raw=whl.read(row['destination']);assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
 python={p.relative_to(site).as_posix() for folder in ('polisyos','tools') for p in (site/folder).rglob('*.py')};assert python=={r['destination'] for r in proof['bindings'] if r['destination'].endswith('.py')}
carrier=json.loads(Path(config['carrier_manifest']).read_text());bridges=[]
for row in carrier['files']:
 actual=Path(row['path']);logical='policy-engine/'+actual.relative_to(Path(config['carrier'])).as_posix();raw=git('show',config['source_sha']+':'+logical);expected={k:row[k] for k in ('bytes','sha256')}
 assert digest(actual)==expected and len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
 assert git('rev-parse',config['source_sha']+':'+logical).decode().strip()==row['git_blob']
 bridges.append({'logical_path':logical,'stored_carrier_path':row['path'],'git_sha':config['source_sha'],'git_blob':row['git_blob'],**expected})
old=Path('/tmp/e02-F-continuation-20261007/foundry/installed-default-resource-forward');oldproof=json.loads((old/'archive-installed-source-bindings.json').read_text());plan=json.loads((base.parent/'narrow-installed-plan.json').read_text())
for row in plan['old_archives_existing_locator_bindings']:assert digest(row['path'])=={k:row[k] for k in ('bytes','sha256')}
for kind,oldsite in oldproof['sites'].items():
 for row in oldproof['source_bindings']:assert digest(Path(oldsite['path'])/row['destination'])=={k:row[k] for k in ('bytes','sha256')},(kind,row['destination'])
profile_paths=['policy-engine/hatch.toml','policy-engine/uv.lock','policy-engine/pyproject.toml',*(r['source'] for r in proof['bindings'] if r['role']=='forced_resource')]
unchanged=[]
for path in profile_paths:
 before=git('rev-parse',plan['old_source_sha']+':'+path).decode().strip();after=git('rev-parse',config['source_sha']+':'+path).decode().strip();assert before==after,path
 unchanged.append({'path':path,'old_source_sha':plan['old_source_sha'],'candidate_sha':config['source_sha'],'git_blob':after})
out={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'outcome':'PASS','candidate_wheel':proof['wheel'],'complete_candidate_source_wheel_site_files':len(proof['bindings']),'actual_python_files':len(python),'carrier_logical_to_absolute_binding_adapter':bridges,'unchanged_packaging_lock_resources':unchanged,'old519_archives':plan['old_archives_existing_locator_bindings'],'old519_sites':{'profiles':len(oldproof['sites']),'files_each':len(oldproof['source_bindings']),'all_declared_bytes_match_original':True},'limits':'Actual old/new immutable byte custody; no new old519 scientific run or new sdist qualification.'}
path=base/'post-native-custody.json';assert not path.exists();path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('source_sha','outcome','complete_candidate_source_wheel_site_files','actual_python_files','old519_sites')}))
