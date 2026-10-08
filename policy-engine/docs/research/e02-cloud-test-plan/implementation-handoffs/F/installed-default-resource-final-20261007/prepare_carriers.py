"""Materialize exact final Git fixtures and one separately bound installed probe."""
import hashlib,json,subprocess,tomllib
from pathlib import Path
base=Path(__file__).resolve().parent
config=json.loads((base/'prepared-config.json').read_text());source=Path(config['source_root']);sha=config['source_sha']
git=lambda *args:subprocess.check_output(['git','-C',config['git_root'],*args])
fixtures=set(config['selectors'][:-1])
for selected in config['selectors'][:-1]:
 for folder in Path(selected).parents:
  if str(folder)=='.':continue
  for name in ('conftest.py','__init__.py'):
   candidate=str(folder/name)
   if (source/'policy-engine'/candidate).is_file():fixtures.add(candidate)
for p in (source/'policy-engine/tests/_helpers').rglob('*.py'):fixtures.add(str(p.relative_to(source/'policy-engine')))
if (source/'policy-engine/tests/quarantine.toml').is_file():fixtures.add('tests/quarantine.toml')
rows=[]
for path in sorted(fixtures):
 raw=(source/'policy-engine'/path).read_bytes();assert raw==git('show',sha+':policy-engine/'+path)
 for kind in ('wheel','sdist'):
  target=base/(kind+'-consumer')/path;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();target.write_bytes(raw)
 rows.append({'git_sha':sha,'path':'policy-engine/'+path,'blob':git('rev-parse',sha+':policy-engine/'+path).decode().strip(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':'selected_test' if path in config['selectors'] else 'actual_ancestor_or_helper_fixture'})
probe=base/'test_installed_catalog_defaults.py';raw=probe.read_bytes()
for kind in ('wheel','sdist'):
 target=base/(kind+'-consumer')/probe.name;assert not target.exists();target.write_bytes(raw)
rows.append({'path':probe.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':'unique_installed_default_consumer_input','original_path':str(probe),'Git_source':'scratch reviewer input, not falsely labeled as sourceGit'})
manifest={'source_sha':sha,'source_tree':config['source_tree'],'selectors':config['selectors'],'expected_cases_per_profile':config['expected_cases_per_profile'],'expected_case_basis':config['expected_case_basis'],'files':rows,'source_fallback':'neutral sibling src absent; exact fixture bodies only; actual product must resolve own installed site'}
(base/'carrier-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');config['carrier_manifest']=str(base/'carrier-manifest.json')
hatch=tomllib.loads((source/'policy-engine/hatch.toml').read_text());resources=hatch['build']['targets']['wheel']['force-include']
expected={'source_sha':sha,'source_tree':config['source_tree'],'resources':{}}
for src,destination in resources.items():
 if src.startswith('data/dataset_catalog/'):
  data=(source/'policy-engine'/src).read_bytes();expected['resources'][Path(src).name]={'source_path':'policy-engine/'+src,'git_blob':git('rev-parse',sha+':policy-engine/'+src).decode().strip(),'destination':destination,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
assert len(expected['resources'])==4
(base/'catalog-expected.json').write_text(json.dumps(expected,indent=2)+'\n');config['catalog_expected']=str(base/'catalog-expected.json')
assets={Path(target).name:{'bytes':(source/'policy-engine'/path).stat().st_size,'sha256':hashlib.sha256((source/'policy-engine'/path).read_bytes()).hexdigest()} for path,target in resources.items() if '/_dowhy_profile/' in target}
(base/'profile-expected.json').write_text(json.dumps({'source_sha':sha,'assets':assets,'forced_resource_count':len(resources),'worker_assets':len(assets)},indent=2)+'\n')
(base/'prepared-config.json').write_text(json.dumps(config,indent=2)+'\n');print(json.dumps({'source_sha':sha,'carrier_files':len(rows),'expected_native_cases':config['expected_cases_per_profile'],'forced_resources':len(resources),'curated_resources':4,'worker_resources':len(assets),'native_status':'UNRUN'}))
