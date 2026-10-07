"""Read-only immutable resource contract, canonical ABI and renderer input closure."""
import ast,hashlib,inspect,json,pathlib,pickle,pydoc,subprocess,tempfile,tomllib
from unittest.mock import patch
from tools.devx.architecture import guardrails as g
from polisyos.data_forge import read_api
from polisyos.data_forge.read_api import catalog
from polisyos.data_forge.domains.catalog import _resources
from polisyos.data_forge.domains.catalog.batch import harvester
from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties,variable_alignment
from polisyos.fabric.connectors.sources import wvs
ROOT=pathlib.Path('/workspace/e02-F-graph-20261006');PRODUCT=ROOT/'policy-engine';OUT=pathlib.Path(__file__).resolve().parent;SHA='08983d96395fdde81ffa9e88d0150fd12c13fe2e';TREE='cc4c47d1c12fd3174b546d9622a0878d3b88361d';BASE='370cac5c342bbc5b206331f93776505e0cffe3a6';G='a0ac10fc11975c345312034d0e568b4cfc330d76'
def h(b):return hashlib.sha256(b).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def freeze():
 assert git('rev-parse','HEAD').decode().strip()==SHA
 assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
 assert not git('status','--porcelain','--untracked-files=no')
 paths=git('diff','--name-only',BASE,SHA).decode().splitlines();assert len(paths)==14
 refs=[]
 for p in paths:
  b=git('show',SHA+':'+p);assert b==(ROOT/p).read_bytes();refs.append({'path':p,'bytes':len(b),'sha256':h(b),'blob':git('rev-parse',SHA+':'+p).decode().strip()})
 return refs
before=freeze();(OUT/'full-diff.patch').write_bytes(git('diff',BASE,SHA));owners=['src/polisyos/data_forge/domains/catalog/batch/config.py','src/polisyos/data_forge/domains/catalog/batch/core_sources/loaders.py','src/polisyos/data_forge/domains/catalog/batch/harvester.py','src/polisyos/data_forge/domains/catalog/knowledge/proxy_penalties.py','src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py','src/polisyos/fabric/connectors/sources/wvs.py','src/polisyos/data_forge/read_api/catalog.py','hatch.toml'];parity=[]
for relative in owners:
 p='policy-engine/'+relative;gb=git('show',G+':'+p);bb=git('show',BASE+':'+p);cb=git('show',SHA+':'+p)
 parity.append({'path':p,'G_sha256':h(gb),'base_sha256':h(bb),'candidate_sha256':h(cb),'G_equals_slice_base':gb==bb,'candidate_delta':cb!=gb})
 assert gb==bb,p
originals=[]
for name in sorted(_resources.__annotations__.get('CatalogDefaultResource',[]) if False else ['seed_variable_alignments.yaml','proxy_metric_alignments.yaml','wvs_indicator_registry.yaml','metrics_map.yaml']):
 p='policy-engine/data/dataset_catalog/'+name;b=git('show',SHA+':'+p);assert b==git('show',G+':'+p)==git('show',BASE+':'+p)
 originals.append({'path':p,'bytes':len(b),'sha256':h(b),'all_three_refs_equal':True})
config=tomllib.loads((PRODUCT/'hatch.toml').read_text());force=config['build']['targets']['wheel']['force-include'];old=tomllib.loads(git('show',BASE+':policy-engine/hatch.toml').decode());oldforce=old['build']['targets']['wheel']['force-include'];assert {k:force[k] for k in oldforce}==oldforce and len(force)==11 and len(force)-len(oldforce)==4
for item in originals:
 p=item['path'].removeprefix('policy-engine/');assert force[p]=='polisyos/data_forge/domains/catalog/_resources/'+pathlib.Path(p).name;assert p in config['build']['targets']['sdist']['include']
# Existing root names are unchanged. This does not establish nested ABI by itself.
def literal_exports(sha,path):
 tree=ast.parse(git('show',sha+':'+path));assign=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_EXPORTS' for t in n.targets));return set(ast.literal_eval(assign.value))
root_facade='policy-engine/src/polisyos/data_forge/read_api/__init__.py';assert git('show',SHA+':'+root_facade)==git('show',BASE+':'+root_facade)
facade_path='policy-engine/src/polisyos/data_forge/read_api/catalog.py'
# The facade map contains source variables, so inspect its actual loaded mapping for native window.
base_tree=ast.parse(git('show',BASE+':'+facade_path));base_map=next(n.value for n in base_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_EXPORTS' for t in n.targets));base_keys={ast.literal_eval(k) for k in base_map.keys};assert set(catalog._EXPORTS)-base_keys=={'catalog_default_resource_path'} and not base_keys-set(catalog._EXPORTS)
fn=catalog.catalog_default_resource_path;assert fn is _resources.catalog_default_resource_path;assert fn.__module__=='polisyos.data_forge.domains.catalog._resources';assert pickle.loads(pickle.dumps(fn)) is fn
signature=str(inspect.signature(fn));assert list(inspect.signature(fn).parameters)==['name'];assert inspect.signature(fn).return_annotation is pathlib.Path
assert 'durable filesystem path' in pydoc.render_doc(fn)
assert 'catalog_default_resource_path' in catalog.__all__ and 'catalog_default_resource_path' not in read_api.__all__
functions=[fn,variable_alignment.default_seed_alignments_path,proxy_penalties.default_proxy_metric_alignments_path,loaders._seed_alignments_path,loaders._wvs_registry_path,harvester._wvs_registry_path]
abi=[]
for f in functions:
 assert pickle.loads(pickle.dumps(f)) is f
 result=f('seed_variable_alignments.yaml') if f is fn else f();assert isinstance(result,pathlib.Path);assert pickle.loads(pickle.dumps(result))==result and result.exists()
 abi.append({'FQN':f.__module__+'.'+f.__qualname__,'signature':str(inspect.signature(f)),'pickle_identity':True,'result_type':type(result).__name__,'path':str(result),'bytes_sha256':h(result.read_bytes())})
# Existing overridable default helpers execute their real consumer path.
with tempfile.TemporaryDirectory(dir=OUT,prefix='abi-') as td:
 td=pathlib.Path(td);seed=td/'seed.yaml';seed.write_text('alignments: []\n')
 with patch.object(variable_alignment,'default_seed_alignments_path',return_value=seed) as call:
  score=variable_alignment.score_variable_pair(left_name='RL.EST',right_name='GE.EST');assert call.call_count==1 and score.seed_support_score==0.0
 custom=td/'proxy.yaml';custom.write_text('mappings: {custom_metric: [{canonical_var: custom_var, confidence: 0.8, proxy_penalty: 0.37}]}\n');proxy_penalties.load_proxy_metric_alignments.cache_clear()
 try:
  with patch.object(proxy_penalties,'default_proxy_metric_alignments_path',return_value=custom) as call:
   penalty=proxy_penalties.resolve_proxy_penalty(metric_name='custom_metric',canonical_var='custom_var',base_penalty=0.99);assert call.call_count==1 and penalty==0.37
 finally:proxy_penalties.load_proxy_metric_alignments.cache_clear()
 # Fabric import binding remains explicitly replaceable and reads the offered actual YAML.
 registry=td/'wvs.yaml';registry.write_text('indicators: {custom: {title: custom_title, waves: [7]}}\n');wvs._load_wvs_registry_indicators.cache_clear()
 try:
  with patch.object(wvs,'catalog_default_resource_path',return_value=registry) as call:
   assert wvs._load_wvs_registry_indicators()=={'custom':'custom_title'} and call.call_count==1
 finally:wvs._load_wvs_registry_indicators.cache_clear()
assert catalog.catalog_default_resource_path is fn
policies=g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST);families=g._parse_public_generated_artifact_families(g.DEFAULT_PUBLIC_MANIFEST);inventory=g.build_public_surface_inventory(policies);encoded=g.render_public_surface_json(inventory,generated_artifact_families=families);markdown=g.render_public_surface_markdown(inventory);rows=[r for p in inventory for r in p.entrypoints];violations=g._check_public_surface_contracts(inventory);assert len(rows)==38 and all(r.export_count is None and r.known_export_count==0 and not r.export_resolution['complete'] for r in rows);assert len(violations)==38 and all(v.detail=='incomplete_exports' for v in violations)
read_refs=[];operations=[]
for row in rows:
 for item in row.export_resolution['inputs']:
  operations.append(item)
  if item['operation']=='read_bytes' and item['status']=='read':
   b=git('show',SHA+':policy-engine/'+item['path']);assert len(b)==item['bytes'] and h(b)==item['sha256'];assert b==(PRODUCT/item['path']).read_bytes();read_refs.append(item)
old_json=g.DEFAULT_PUBLIC_JSON.read_bytes();old_md=g.DEFAULT_PUBLIC_MD.read_bytes();jchanged=encoded.encode()!=old_json;mchanged=markdown.encode()!=old_md
if jchanged:(OUT/'rendered-current-inventory.json').write_text(encoded)
if mchanged:(OUT/'rendered-current-public-surface.md').write_text(markdown)
changed_paths={r['path'].removeprefix('policy-engine/') for r in before};intersections=sorted({r['path'] for r in read_refs}&changed_paths)
package=next(p for p in policies if p.module=='polisyos.data_forge');assert package.classification=='public_experimental';assert 'polisyos.data_forge.read_api.catalog' not in package.supported_entrypoints
current_declared={r.module:len(r.export_resolution.get('declared_export_candidates',[])) for r in rows}
after=freeze();assert before==after
result={'source_sha':SHA,'source_tree':TREE,'slice_base_sha':BASE,'G_comparison_sha':G,'bounded_runtime_verdict':'PASS','whole_installed_consumer':'UNRUN newcandidate; historicalb5NO-GO unchanged','source_begin':before,'source_end':after,'G_boundary_parity':parity,'original_YAML_refs':originals,'Hatch':{'old_mappings_preserved':7,'new_curated_mappings':4,'total':11,'original_sdist_includes':4},'ABI':{'native_functions':abi,'new_nested_alias_canonical_identity':True,'root_alias_absent_preserved':True,'new_alias_signature':signature,'new_alias_pickle_FQN_is_private_owner':fn.__module__+'.'+fn.__qualname__,'pydoc_durable_Path':True,'actual_override_controls':{'seed_real_score_seed_support':0.0,'proxy_real_penalty':0.37,'Fabric_real_custom_indicator':{'custom':'custom_title'}},'classification':package.classification,'nested_catalog_is_listed_entrypoint':False,'documentation_residual':'Fragment/internal description omits supported nested public_experimental Path alias; root authorized doc-only correction.'},'generator':{'entrypoints':len(rows),'UNKNOWN':38,'canonical_incomplete_violations':38,'json_drift':jchanged,'markdown_drift':mchanged,'json_bytes':len(encoded.encode()),'json_sha256':h(encoded.encode()),'markdown_bytes':len(markdown.encode()),'markdown_sha256':h(markdown.encode()),'explicit_read_refs':read_refs,'operation_denominator':len(operations),'read_denominator':len(read_refs),'changed_path_read_intersection':intersections,'declared_candidate_counts':current_declared,'nested_alias_outside_manifest_entrypoint_denominator':True,'scope':'Exact native maintained renderer input closure; no static UNKNOWN completeness or whole source census promotion; generated canonical files not written.'}}
(OUT/'inspection.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['source_sha','bounded_runtime_verdict','Hatch','ABI']},indent=2));print(json.dumps({k:result['generator'][k] for k in ['entrypoints','UNKNOWN','canonical_incomplete_violations','json_drift','markdown_drift','operation_denominator','read_denominator','changed_path_read_intersection']},indent=2))
