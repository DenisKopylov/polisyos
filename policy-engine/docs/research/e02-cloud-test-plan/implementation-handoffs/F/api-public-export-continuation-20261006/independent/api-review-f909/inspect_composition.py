"""Read-only canonical representation and packaging projection review."""
import argparse,contextlib,copy,dataclasses,hashlib,importlib,io,json,pathlib,subprocess,tomllib
from unittest.mock import patch
from tools.devx.architecture import guardrails as g
from polisyos.ir import analytics
from polisyos.ir import api as ir_api
from polisyos import ir
from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
from polisyos.ir.analytics.causal import EstimationStatus
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as worker_bridge

ROOT=g.REPO_ROOT.parent
OUT=pathlib.Path(__file__).resolve().parent
SHA='f9095536592150362747b063c0f4cf3aac899bb0'
TREE='c856bac7be6970c52161f4534aabb31524ddd9d8'
BASE='34808bdae09b4a8dbd35bda989c4dc787dcb4e86'
INSTALL='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
ROOT_SOURCE='7185572917f7a3db5e93385a176cb611b35aff42'
def h(b):return hashlib.sha256(b).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def source_ref(path,sha=SHA):
 b=git('show',sha+':'+path)
 return {'source_sha':sha,'source_path':path,'bytes':len(b),'sha256':h(b)}
def freeze():
 assert git('rev-parse','HEAD').decode().strip()==SHA
 assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
 assert not git('status','--porcelain')
 return [source_ref(p) for p in git('diff','--name-only',BASE,SHA).decode().splitlines()]
before=freeze();assert len(before)==6
policies=g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST)
families=g._parse_public_generated_artifact_families(g.DEFAULT_PUBLIC_MANIFEST)
inventory=g.build_public_surface_inventory(policies)
encoded=g.render_public_surface_json(inventory,generated_artifact_families=families)
markdown=g.render_public_surface_markdown(inventory)
assert encoded.encode()==g.DEFAULT_PUBLIC_JSON.read_bytes()
assert markdown.encode()==g.DEFAULT_PUBLIC_MD.read_bytes()
rows=[row for package in inventory for row in package.entrypoints]
assert len(rows)==38 and all(row.export_count is None and row.known_export_count==0 and not row.exports and not row.export_resolution['complete'] for row in rows)
violations=g._check_public_surface_contracts(inventory)
assert len(violations)==38 and all(item.detail=='incomplete_exports' for item in violations)
read_refs=[]
for row in rows:
 for item in row.export_resolution['inputs']:
  if item['operation']=='read_bytes' and item['status']=='read':
   body=git('show',SHA+':policy-engine/'+item['path'])
   assert len(body)==item['bytes'] and h(body)==item['sha256']
   assert body==(g.REPO_ROOT/item['path']).read_bytes()
   read_refs.append(item)
analytics_row=next(row for row in rows if row.module=='polisyos.ir.analytics')
world_row=next(row for row in rows if row.module=='polisyos.fabric.world')
assert len(analytics.__all__)==280
assert analytics_row.export_resolution['declared_export_candidates']==sorted(ir_api.ANALYTICS_FACADE_EXPORTS)==sorted(analytics.__all__)
assert len(world_row.export_resolution['declared_export_candidates'])==41
bindings=[]
for name in ['CausalEstimatorInterval','CausalResultKind']:
 leaf=importlib.import_module('polisyos.ir.analytics.causal_queries')
 assert getattr(ir,name) is getattr(analytics,name) is getattr(ir_api,name) is getattr(leaf,name)
 bindings.append({'name':name,'provider':getattr(leaf,name).__module__,'identity':'same canonical object','scope':'native binding only; static candidates unproved'})
for name in ['SCMTrainingRows','SCMFitProvenance']:
 leaf=importlib.import_module('polisyos.ir.analytics.structural_causal_model')
 assert getattr(ir,name) is getattr(leaf,name)
 bindings.append({'name':name,'provider':getattr(leaf,name).__module__,'identity':'same canonical root IR object','scope':'root IR binding only; no extra analytics/API promotion assumed'})
assert StructuralCausalModelSpec.model_fields['schema_version'].default=='1.1'
assert EstimationStatus.DIAGNOSTIC_ONLY.value=='diagnostic_only'
assert 'InternalTwinNetwork' not in ir.__all__ and 'InternalTwinNetwork' not in analytics.__all__
assert all('InternalTwinNetwork' not in row.export_resolution.get('declared_export_candidates',[]) for row in rows if row.module in ['polisyos.ir','polisyos.ir.api','polisyos.ir.analytics'])

hatch=tomllib.loads((g.REPO_ROOT/'hatch.toml').read_text())
origin=tomllib.loads(git('show',INSTALL+':policy-engine/hatch.toml').decode())
expected={'architecture/production_quality/method_catalog_dependency_digest_domains.toml':'polisyos/foundry/methods/catalog/_resources/method_catalog_dependency_digest_domains.toml'}
names=['worker.py','protocol.py','pyproject.toml','uv.lock','.python-version','README.md']
expected.update({f'workers/dowhy-014/{name}':f'polisyos/foundry/methods/catalog/causal/_dowhy_profile/{name}' for name in names})
assert hatch['build']['targets']['wheel']['force-include']==origin['build']['targets']['wheel']['force-include']==expected
assets=[]
for name in names:
 path='policy-engine/workers/dowhy-014/'+name
 body=git('show',SHA+':'+path)
 assert body==git('show',INSTALL+':'+path)==git('show',ROOT_SOURCE+':'+path)==(ROOT/path).read_bytes()
 assert f'workers/dowhy-014/{name}' in hatch['build']['targets']['sdist']['include']
 assets.append(source_ref(path))
directory=worker_bridge._worker_directory()
assert directory==g.REPO_ROOT/'workers/dowhy-014'
assert all((directory/name).read_bytes()==git('show',SHA+':policy-engine/workers/dowhy-014/'+name) for name in names)
fixture='policy-engine/tests/unit/foundry/methods/catalog/causal/test_installed_worker_profile.py'
body=git('show',SHA+':'+fixture)
assert len(body)==11758 and body==git('show',INSTALL+':'+fixture)
assert git('diff','--name-only','a8c40ac9dca0d680dd82187e2538cbba9a34eb08',SHA).decode().splitlines()==['policy-engine/architecture/public_surface/inventory.json','policy-engine/docs/reference/public-surface.md']

# Run the actual canonical representation consumer, with unrelated broad graph,
# README/exception and workflow/family measurements explicitly omitted in memory.
# Positive means no JSON/Markdown drift; its overall exit remains FAIL for all38
# incomplete rows. No baseline exception or checker source is modified.
corrupt=json.loads(encoded)
for package in corrupt['packages']:
 for row in package['entrypoints']:
  if row['module']=='polisyos.ir.analytics':
   row['export_count']=0;row['known_export_count']=0;row['export_resolution']['complete']=True
corrupt_json=json.dumps(corrupt,indent=2,ensure_ascii=True)+'\n'
assert corrupt_json!=encoded
assert 'unknown (no names proven)' in markdown
corrupt_markdown=markdown.replace('unknown (no names proven)','0',1)
real_read=pathlib.Path.read_text
omitted=['collect_deep_import_edges','_parse_generated_artifacts','_check_readmes','_validate_guardrail_exceptions','_check_deep_import_creep','_check_generated_artifact_manifest','_check_workflow_toolchain_guardrails','_parse_guardrail_exceptions']
checker_results=[]
for name,json_value,md_value in [('fresh',encoded,markdown),('corrupt_total_complete_field',corrupt_json,markdown),('corrupt_unknown_markdown',encoded,corrupt_markdown)]:
 def read_text(path,*args,**kwargs):
  if path==g.DEFAULT_PUBLIC_JSON:return json_value
  if path==g.DEFAULT_PUBLIC_MD:return md_value
  if path==g.DEFAULT_GENERATED_MD:return g.render_generated_artifacts_markdown([])
  if path==g.DEFAULT_DEEP_IMPORT_BASELINE:return g.render_deep_import_baseline_json([])
  return real_read(path,*args,**kwargs)
 args=argparse.Namespace(public_manifest=g.DEFAULT_PUBLIC_MANIFEST,public_json=g.DEFAULT_PUBLIC_JSON,public_md=g.DEFAULT_PUBLIC_MD,generated_manifest=g.DEFAULT_GENERATED_MANIFEST,generated_md=g.DEFAULT_GENERATED_MD,deep_import_baseline=g.DEFAULT_DEEP_IMPORT_BASELINE,exceptions=g.DEFAULT_EXCEPTIONS,exceptions_registry=g.DEFAULT_EXCEPTION_REGISTRY,max_expiry_days=90,skip_generated_checks=True,all_generated_checks=False)
 buffer=io.StringIO()
 with contextlib.ExitStack() as stack:
  for method in omitted:stack.enter_context(patch.object(g,method,return_value=[]))
  stack.enter_context(patch.object(pathlib.Path,'read_text',read_text))
  with contextlib.redirect_stdout(buffer):code=g.run_check(args)
 output=buffer.getvalue();file=OUT/(name+'.canonical-check.stdout.txt');file.write_text(output)
 assert code==1 and output.count('export total is unresolved:')==38
 json_drift='Public surface inventory JSON drift detected' in output
 md_drift='Public surface reference doc drift detected' in output
 assert json_drift==(name=='corrupt_total_complete_field')
 assert md_drift==(name=='corrupt_unknown_markdown')
 checker_results.append({'case':name,'actual_run_check_exit':code,'json_drift':json_drift,'markdown_drift':md_drift,'incomplete_rows':38,'full_output':{'path':str(file),'bytes':len(file.read_bytes()),'sha256':h(file.read_bytes())}})
after=freeze();assert before==after
result={'source_sha':SHA,'source_tree':TREE,'check':'PASS','outcome':'limited','exact_renderer_refs':[source_ref('policy-engine/architecture/public_surface/inventory.json'),source_ref('policy-engine/docs/reference/public-surface.md')], 'native_static_representation':{'entrypoints':38,'unknown':38,'incomplete_canonical_violations':38,'analytics_declared_candidates':280,'world_declared_candidates':41,'proven_known':0,'total':None,'complete':False},'all_explicit_read_refs':read_refs,'bindings':bindings,'SCM_default':'1.1','TMLE_status':'diagnostic_only','InternalTwinNetwork_root_promotion':False,'asset_refs':assets,'hatch_mapping':expected,'mapping_origin_sha':INSTALL,'assets_also_equal_root_source_sha':ROOT_SOURCE,'fixture_ref':source_ref(fixture),'worker_profile_resolver_origin':{'module':worker_bridge.__file__,'directory':str(directory),'scope':'actual six source asset resolution, not installed or scientific execution'}, 'canonical_consumer_controls':checker_results,'omitted_measurements':omitted+['required generated family freshness','installed wheel/sdist','numerical/backend/scientific/G acceptance'], 'source_begin':before,'source_end':after,'scope':'Read-only exact packaging projection/representation review; positive freshness excludes the existing38incomplete canonicalFAIL. Three native canonical consumer runs retainFAIL1. Memory corruption inputs only, no source writes or broad architecture GREEN.'}
(OUT/'inspection.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
