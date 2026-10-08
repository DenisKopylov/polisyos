import ast, dataclasses, hashlib, importlib, inspect, json, pathlib, subprocess, sys
from tools.devx.architecture import guardrails as g
from tools.quality.validation.check_docs_gate import build_gate_plan, _facade_readmes
from tools.quality.diagnostics import gen_schema as s
from polisyos import foundry
from polisyos.foundry.methods import api
from polisyos.ir.analytics.causal_queries import CausalQueryResult
from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
root=pathlib.Path('/workspace/e02-F-graph-20261006'); product=root/'policy-engine'
out=pathlib.Path('/workspace/e02-F-20261006-receipts/graph/scm-final6d')
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert source=='6dcb792b6f8c2d2dcfc04a5e04ea33135a2ad181'
base='198076863e143dea9f89f02734b13d50dae3eed5'
changed=subprocess.check_output(['git','diff','--name-only',base,source,'--','policy-engine'],cwd=root,text=True).splitlines()
paths=[p.removeprefix('policy-engine/') for p in changed]
def save(name,data):
 data={'source_sha':source,'python':sys.version,'executable':sys.executable,'source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip(),**data}
 (out/name).write_text(json.dumps(data,indent=2)+'\n'); print(name,data.get('check'))
def ident(path):
 b=path.read_bytes();return {'path':str(path.relative_to(root)) if path.is_relative_to(root) else str(path),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
policies=g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST)
allowed={}
for p in policies:
 r=g._root_for_module(p.module)
 if r:allowed.setdefault(r,set()).update(p.supported_entrypoints)
files=[product/p for p in paths if p.startswith('src/') and p.endswith('.py')]
edges={};entries=[]
for f in files:
 module,is_package=g._module_name_for_path(f);source_root=g._root_for_module(module)
 tree=ast.parse(f.read_text()); targets=[]
 for n in ast.walk(tree):
  names=[a.name for a in n.names] if isinstance(n,ast.Import) else [g._resolve_import_module(module,is_package,n)] if isinstance(n,ast.ImportFrom) else []
  for target in names:
   if target:
    targets.append({'line':n.lineno,'target':target})
    if source_root:g._maybe_add_deep_import(edges=edges,allowed_entrypoints=allowed,source_module=module,source_root=source_root,source_file=f,target_module=target)
 entries.append({'file':ident(f),'module':module,'all_ast_import_targets':targets,'import_denominator':len(targets)})
violations=g._check_deep_import_creep(baseline_path=g.DEFAULT_DEEP_IMPORT_BASELINE,current_edges=list(edges.values()))
assert not violations,violations
unchanged=[]
for f in [g.DEFAULT_PUBLIC_MANIFEST,g.DEFAULT_DEEP_IMPORT_BASELINE]:
 old=subprocess.check_output(['git','show',base+':'+str(f.relative_to(root))],cwd=root)
 assert old==f.read_bytes();unchanged.append(ident(f))
save('owned-import-denominator.json',{'check':'PASS','canonical_classifier':'tools.devx.architecture.guardrails._maybe_add_deep_import/_check_deep_import_creep','scope':'all AST imports in every actual changed product src Python file, including fresh carried helper; not whole repository gate','file_denominator':len(files),'import_denominator':sum(e['import_denominator'] for e in entries),'source_records':entries,'all_classified_edges':[dataclasses.asdict(e) for e in edges.values()],'new_violations':[],'unchanged_policy_and_baseline':unchanged,'P41_inherited':'not_established'})
plans={}
controls={'actual':paths,'remove_scientist_doc':[p for p in paths if p!='docs/reference/scientist/structural-causal-queries.md'],'remove_foundry_doc':[p for p in paths if p!='docs/reference/foundry/structural-causal-models.md'],'remove_ir_readme':[p for p in paths if p!='src/polisyos/ir/README.md'],'remove_foundry_readme':[p for p in paths if p!='src/polisyos/foundry/README.md']}
controls['remove_all_matching_facade_readmes']=[p for p in paths if p not in _facade_readmes(paths)]
for name,pp in controls.items():
 plan=build_gate_plan(pp);plans[name]={'findings':[dataclasses.asdict(f) for f in plan.findings],'commands':[dataclasses.asdict(c) for c in plan.commands]}
assert not plans['actual']['findings']
for name,rule in [('remove_scientist_doc','scientist_docs'),('remove_foundry_doc','foundry_docs'),('remove_all_matching_facade_readmes','readme_freshness')]:
 assert rule in [f['rule_id'] for f in plans[name]['findings']],(name,plans[name])
save('docs-plan.json',{'check':'PASS','base_sha':base,'changed_path_denominator':len(paths),'actual_changed_paths':paths,'matching_facade_readmes':_facade_readmes(paths),'readme_predicate':'canonical gate requires any matching README; individual IR/Foundry removals remain satisfied by the other actual README, complete matching-denominator removal fails','plans':plans,'scope':'path-aware companion predicate only; native full gate retains separate FAIL/UNRUN results'})
manifest=json.loads((product/'schemas/snapshots/ir/_manifest.json').read_text());records=[]
for key,cls in [('causal_query_result',CausalQueryResult),('structural_causal_model_spec',StructuralCausalModelSpec)]:
 schema=s._generate_model_schema(cls); snapshot=product/f'schemas/snapshots/ir/{key}.schema.json'
 assert s._json_dump(schema,'pretty').encode()==snapshot.read_bytes()
 entry=manifest['models'][key]
 assert entry['sha256_full']==s._schema_hash(schema) and entry['sha256_semantic']==s._schema_hash(s._strip_metadata(schema))
 records.append({'abi_key':key,'snapshot':ident(snapshot),'manifest_entry':entry,'check':'PASS'})
assert manifest['content_hash']==s._schema_hash(manifest['models'])
save('own-generated-schemas.json',{'check':'PASS','canonical_generator':'tools.quality.diagnostics.gen_schema._generate_model_schema/_json_dump/_schema_hash/_strip_metadata','records':records,'manifest_internal_content_hash':'PASS','full_generator_check':'FAIL exact1e output retained; feedback_solve_result+wholemanifest are not attributed inherited; no schema owner/baseline waiver'})
inv=g.build_public_surface_inventory(policies)
assert g.render_public_surface_json(inv,generated_artifact_families=g._parse_public_generated_artifact_families(g.DEFAULT_PUBLIC_MANIFEST)).encode()==g.DEFAULT_PUBLIC_JSON.read_bytes()
assert g.render_public_surface_markdown(inv).encode()==g.DEFAULT_PUBLIC_MD.read_bytes()
save('public-generated-companions.json',{'check':'PASS','canonical_generator':'tools.devx.architecture.guardrails.build_public_surface_inventory/render_public_surface_json/render_public_surface_markdown','outputs':[ident(g.DEFAULT_PUBLIC_JSON),ident(g.DEFAULT_PUBLIC_MD)],'owner_record_delta':'0b modifies only polisyos.ir four types and polisyos.foundry four canonical helper aliases; other package records preserved'})
aliases={'causal_worker_execution_context':('polisyos.foundry.methods.catalog.causal._dowhy_worker','worker_execution_context'),'validate_source_bound_causal_worker_response':('polisyos.foundry.methods.catalog.causal._dowhy_worker','validate_persisted_worker_response'),'validate_source_bound_gcm_spec':('polisyos.foundry.methods.catalog.causal.gcm_fit','validate_persisted_gcm_spec'),'validate_source_bound_causal_estimator_interval':('polisyos.foundry.methods.catalog.causal.gcm_query','validate_persisted_estimator_interval')}
names=set(aliases)|{v[1] for v in aliases.values()}; tracked=subprocess.check_output(['git','ls-files','*.py'],cwd=product,text=True).splitlines();tracked=[p for p in tracked if p.split('/')[0] in ('src','tests','tools','workers','examples')];hits=[]
for p in tracked:
 for number,line in enumerate((product/p).read_text().splitlines(),1):
  found=sorted(n for n in names if n in line)
  if found:hits.append({'path':p,'line':number,'names':found,'text':line})
providers=[]
for alias,(module,name) in aliases.items():
 fn=getattr(importlib.import_module(module),name);assert fn is getattr(foundry,alias) is getattr(api,alias)
 providers.append({'alias':alias,'provider_fqn':fn.__module__+'.'+fn.__qualname__,'signature':str(inspect.signature(fn)),'callable_code_source':ident(pathlib.Path(inspect.getfile(fn))),'canonical_provider_source':ident(pathlib.Path(inspect.getfile(inspect.unwrap(fn)))),'root_and_method_identity':True})
save('public-consumer-census.json',{'check':'PASS','tracked_python_denominator':len(tracked),'searched_roots':['src','tests','tools','workers','examples'],'literal_name_hits':hits,'providers':providers,'consumer_override':'process-local marker-kept job wrapper exercises actual canonical registered producer before mutating full peer; original source/backend artifact retained','boundary':'finite repository literal-name/FQN/provider census; dynamic external filename/pickle/loader absence not established, separate installed-package acceptance remains with API/C/G'})
worker_assets=['workers/dowhy-014/worker.py','workers/dowhy-014/protocol.py','workers/dowhy-014/uv.lock','workers/dowhy-014/pyproject.toml','workers/dowhy-014/.python-version','workers/dowhy-014/tests/test_worker.py']
assets=[]
for p in worker_assets:
 current=(product/p).read_bytes();original=subprocess.check_output(['git','show','e5895da2ebbb5f6108e398d78258b973dbdc7b68:policy-engine/'+p],cwd=root);assert current==original;assets.append(ident(product/p))
save('worker-math-profile-equivalence.json',{'check':'PASS','worker_author_profile':'e5895da2ebbb5f6108e398d78258b973dbdc7b68','unchanged_complete_assets':assets,'helper_author_commit':'f6e80c4cb812f2e561791df9d323ebfbe40f7dd9','helper':ident(product/'src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py'),'scope':'complete actual worker/protocol/lock/math/test profile identity; parent report projection dependency is separately checked, README docs changed without numeric authority'})
