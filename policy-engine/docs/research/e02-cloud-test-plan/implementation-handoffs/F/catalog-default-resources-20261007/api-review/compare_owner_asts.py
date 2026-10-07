import ast,hashlib,json,pathlib,subprocess
ROOT=pathlib.Path('/workspace/e02-F-graph-20261006');OUT=pathlib.Path(__file__).resolve().parent;SHA='08983d96395fdde81ffa9e88d0150fd12c13fe2e';G='a0ac10fc11975c345312034d0e568b4cfc330d76';inspection=json.loads((OUT/'inspection.json').read_text());rows=[]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def functions(tree,prefix=''):
 result={}
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
   name=prefix+node.name
   if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):result[name]=ast.dump(node,include_attributes=False)
   result.update(functions(node,name+'.'))
 return result
for entry in inspection['G_boundary_parity']:
 p=entry['path']
 if not p.endswith('.py'):continue
 old=ast.parse(git('show',G+':'+p));new=ast.parse(git('show',SHA+':'+p));a=functions(old);b=functions(new);assert set(a)==set(b),p
 changed=[n for n in a if a[n]!=b[n]];rows.append({'path':p,'function_denominator':len(a),'changed_function_ASTs':changed,'equal_remaining_function_ASTs':len(a)-len(changed)})
expected={'config.py':['DatasetBatchConfig.default_metrics_map_path'],'loaders.py':['_seed_alignments_path','_wvs_registry_path'],'harvester.py':['_wvs_registry_path'],'proxy_penalties.py':['default_proxy_metric_alignments_path'],'variable_alignment.py':['default_seed_alignments_path'],'wvs.py':['_load_wvs_registry_indicators'],'catalog.py':[]}
for row in rows:assert row['changed_function_ASTs']==expected[pathlib.Path(row['path']).name],row
result={'source_sha':SHA,'G_sha':G,'scope':'Full function AST census in actual six default owners and nested facade, excluding source-position/formatting; class/property and assignments separately inspected full diff. Curated YAML bytes unchanged. This is narrow behavioral-scope proof, not global P41 disjointness.','rows':rows,'changed_function_count':sum(len(x['changed_function_ASTs']) for x in rows),'function_denominator':sum(x['function_denominator'] for x in rows)};(OUT/'owner-ast-delta.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
