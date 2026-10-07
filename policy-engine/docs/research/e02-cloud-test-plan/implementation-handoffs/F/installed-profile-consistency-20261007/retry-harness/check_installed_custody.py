"""Complete frozen source/wheel/site/copy-custody guard; no historical suite rerun."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
base=Path(__file__).resolve().parent/'candidate-wheel';config=json.loads((base/'installed-config.json').read_text());site=Path(config['site']);proof=json.loads((base/'pre-native-custody.json').read_text())
def digest(p):
 h=hashlib.sha256();n=0
 with Path(p).open('rb') as f:
  while raw:=f.read(1024*1024):h.update(raw);n+=len(raw)
 return {'bytes':n,'sha256':h.hexdigest()}
git=lambda *args:subprocess.check_output(['git','-C',config['git_root'],*args])
assert git('rev-parse','HEAD').decode().strip()==config['source_sha'] and git('rev-parse','HEAD^{tree}').decode().strip()==config['source_tree']
assert digest(config['wheel'])=={k:proof['wheel'][k] for k in ('bytes','sha256')}
with zipfile.ZipFile(config['wheel']) as whl:
 actual={n for n in whl.namelist() if n.startswith(('polisyos/','tools/')) and not n.endswith('/')}
 assert actual=={r['destination'] for r in proof['bindings']}
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
packaging_paths=['policy-engine/hatch.toml','policy-engine/uv.lock','policy-engine/pyproject.toml',*(r['source'] for r in proof['bindings'] if r['role']=='forced_resource')]
unchanged=[]
for path in packaging_paths:
 before=git('rev-parse','4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d:'+path).decode().strip();after=git('rev-parse',config['source_sha']+':'+path).decode().strip();assert before==after,path
 unchanged.append({'path':path,'previous_source_sha':'4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d','candidate_sha':config['source_sha'],'git_blob':after})
out={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'outcome':'PASS','candidate_wheel':proof['wheel'],'complete_candidate_source_wheel_site_files':len(proof['bindings']),'actual_python_files':len(python),'carrier_files_checked':len(bridges),'unchanged_packaging_lock_resources':unchanged,'limits':'One new source-wheel byte-custody qualification; no old4ee16/old51991 rerun or new rebuilt-sdist.'}
path=base/(sys.argv[1] if len(sys.argv)>1 else 'post-native-custody.json');assert not path.exists();path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
