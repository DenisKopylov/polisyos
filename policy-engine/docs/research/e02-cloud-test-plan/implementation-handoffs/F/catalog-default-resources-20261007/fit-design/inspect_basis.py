from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tomllib
import zipfile
import yaml

ROOT=Path('/workspace/e02-F-closeout-20261006')
SCRATCH=Path(__file__).resolve().parent
BASE=Path('/tmp/e02-F-continuation-20261007/foundry/installed-continuation-final')
GRAPH=Path('/tmp/e02-F-continuation-20261007/graph/packaged-default-diagnosis')
SHA='b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a'
TREE='055871c409ce72e6a29619b235698aa45a6844d4'
NAMES=('seed_variable_alignments.yaml','proxy_metric_alignments.yaml','wvs_indicator_registry.yaml','metrics_map.yaml')
def gitbytes(path):return subprocess.check_output(['git','-C',str(ROOT),'show',f'{SHA}:{path}'])
def binding(path):
 data=gitbytes(path)
 return {'git_ref':SHA,'path':path,'git_blob':subprocess.check_output(['git','-C',str(ROOT),'rev-parse',f'{SHA}:{path}'],text=True).strip(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'working_file_matches_pinned_blob':(ROOT/path).read_bytes()==data}
resources=[]
for name in NAMES:
 path=f'policy-engine/data/dataset_catalog/{name}'
 data=gitbytes(path);parsed=yaml.safe_load(data)
 row=binding(path)
 row.update(yaml_root_type=type(parsed).__name__,parsed_body_sha256=hashlib.sha256(json.dumps(parsed,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest())
 if name.startswith('seed'): row.update(alignment_count=len(parsed['alignments']),method_counts={kind:sum(item['method']==kind for item in parsed['alignments']) for kind in sorted({item['method'] for item in parsed['alignments']})},meaning='Curated variable alignment evidence; no statistical identification admission.')
 elif name.startswith('proxy'): row.update(metric_count=len(parsed['mappings']),mapping_count=sum(len(v) for v in parsed['mappings'].values()),meaning='Existing country/year proxy penalty overrides; no new rounding/welfare/penalty norm.')
 elif name.startswith('wvs'): row.update(indicator_count=len(parsed['indicators']),wave7_count=sum(7 in item.get('waves',[]) for item in parsed['indicators'].values()),version=parsed['version'],meaning='Existing curated/codebook-derived indicator definitions; raw CSV/XLSX remains external.')
 else:row.update(metric_count=len(parsed),meaning='Existing metric-to-provider indicator dictionary; no second catalog.')
 resources.append(row)
paths=['policy-engine/hatch.toml','policy-engine/pyproject.toml','policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py','policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/proxy_penalties.py','policy-engine/src/polisyos/data_forge/domains/catalog/batch/config.py','policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/loaders.py','policy-engine/src/polisyos/data_forge/domains/catalog/batch/harvester.py','policy-engine/src/polisyos/fabric/connectors/sources/wvs.py','policy-engine/src/polisyos/data_forge/read_api/catalog.py','policy-engine/src/polisyos/data_forge/read_api/__init__.py','policy-engine/src/polisyos/data_forge/read_api/surfaces.py','policy-engine/src/polisyos/data_forge/errors.py','policy-engine/src/polisyos/ir/analytics/alignment_certification.py','policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py','policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/derivation_catalog_selection.py','policy-engine/tests/repo_quality/tools/test_hatch_packaging.py','policy-engine/architecture/public_surface/contract.toml','policy-engine/tools/devx/architecture/guardrails.py']
source_bindings=[binding(path) for path in paths]
config=json.loads((BASE/'installed-config.json').read_bytes());assert config['source_sha']==SHA and config['source_tree']==TREE
archives=[]
for path in [BASE/'dist-source/policy_engine-0.1.0-py3-none-any.whl',BASE/'dist-source/policy_engine-0.1.0.tar.gz',BASE/'dist-rebuilt/policy_engine-0.1.0-py3-none-any.whl']:
 if path.suffix=='.whl':
  with zipfile.ZipFile(path) as archive:members=archive.namelist();files=[item.filename for item in archive.infolist() if not item.is_dir()]
 else:
  with tarfile.open(path) as archive:items=archive.getmembers();members=[m.name for m in items];files=[m.name for m in items if m.isfile()]
 matches={name:[p for p in files if Path(p).name==name] for name in NAMES}
 assert not any(matches.values()),matches
 archives.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),'complete_member_count':len(members),'complete_file_count':len(files),'resource_basename_matches':matches,'scope':'Complete member walk for four exact existing resource basenames, not all DataForge asset completeness.'})
sites=[]
for kind in ['wheel','sdist']:
 site=Path(config['sites'][kind]);matches={name:[str(p) for p in site.rglob(name)] for name in NAMES};assert not any(matches.values()),matches
 graphs=json.loads((GRAPH/f'{kind}-defaults.stdout.json').read_bytes())
 own=json.loads((SCRATCH/f'{kind}-additional.stdout.txt').read_bytes())
 combined={**graphs['modules'],**own['modules']};module_bindings=[]
 for name,item in sorted(combined.items()):
  path='policy-engine/src/'+name.replace('.','/')+'.py';data=gitbytes(path)
  assert item['bytes']==len(data) and item['sha256']==hashlib.sha256(data).hexdigest(),name
  module_bindings.append({'module':name,'git_path':path,**item,'source_matches':True})
 sites.append({'kind':kind,'site':str(site),'resource_basename_matches':matches,'complete_named_module_count':len(module_bindings),'modules':module_bindings,'graph_observations':graphs['results'],'own_observations':own['results'],'graph_origin_violations':graphs['origin_violations'],'own_origin_violations':own['origin_violations'],'origin_count_own':own['product_origin_count']})
hatch=tomllib.loads(gitbytes('policy-engine/hatch.toml').decode());force=hatch['build']['targets']['wheel']['force-include'];sdist=hatch['build']['targets']['sdist']['include']
test_tree=ast.parse(gitbytes('policy-engine/tests/repo_quality/tools/test_hatch_packaging.py').decode());legacy=next(ast.literal_eval(n.value) for n in test_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LEGACY' for t in n.targets));legacy_includes=tomllib.loads(legacy)['tool']['hatch']['build']['targets']['sdist']['include']
def selected(path,prefixes):return any(path==p or path.startswith(p+'/') for p in prefixes)
projection={'existing_force_include_count':len(force),'current_sdist_preserves_projection_sources':{p:selected(p,sdist) for p in force},'migration_fixture_preserves_current_projection_sources':{p:selected(p,legacy_includes+['hatch.toml']) for p in force},'resources_selected_in_sdist':{f'data/dataset_catalog/{n}':selected(f'data/dataset_catalog/{n}',sdist) for n in NAMES},'migration_oracle':'Original LEGACY static include fixture and complete old/new archive equality; not a current required-resource oracle. No test was run or changed by this audit.'}
assert len(force)==7
result={'source_sha':SHA,'source_tree':TREE,'resources':resources,'source_bindings':source_bindings,'archives':archives,'sites':sites,'hatch_projection_basis':projection,'science_scope':'No numerical suites repeated. No production input/admitted execution/identification positive claimed. Actual default missing/degraded observations preserved; explicit original-path positives only compatibility controls.'}
(SCRATCH/'basis-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'source_sha':SHA,'resources':[{k:v for k,v in row.items() if k not in {'git_blob','parsed_body_sha256'}} for row in resources],'archives':[{'path':r['path'],'member_count':r['complete_member_count'],'file_count':r['complete_file_count'],'matches':r['resource_basename_matches']} for r in archives],'named_source_bindings':len(source_bindings),'site_modules_per_kind':[len(s['modules']) for s in sites],'hatch_projection':projection},indent=2))
