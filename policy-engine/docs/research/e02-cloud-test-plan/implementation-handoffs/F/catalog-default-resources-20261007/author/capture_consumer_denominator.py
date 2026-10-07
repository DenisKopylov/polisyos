import ast,hashlib,json,pathlib,subprocess
repo=pathlib.Path('/workspace/e02-F-graph-20261006');out=pathlib.Path(__file__).resolve().parent;sha='b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a';tree=subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=repo,text=True).strip()
names={'default_seed_alignments_path','load_seed_alignments','score_variable_pair','default_proxy_metric_alignments_path','load_proxy_metric_alignments','metric_proxy_alignments','resolve_proxy_penalty','_seed_alignments_path','_wvs_registry_path','_load_wvs_registry','_load_wvs_indicator_registry','_load_wvs_registry_indicators','default_metrics_map_path','resolved_metrics_map_path'}
resources={'seed_variable_alignments.yaml','proxy_metric_alignments.yaml','wvs_indicator_registry.yaml','metrics_map.yaml'}
paths=[x for x in subprocess.check_output(['git','ls-tree','-r','--name-only',sha,'policy-engine/src'],cwd=repo,text=True).splitlines() if x.endswith('.py')];stream=subprocess.run(['git','cat-file','--batch'],cwd=repo,input=(''.join(sha+':'+p+'\n' for p in paths)).encode(),capture_output=True,check=True).stdout;pos=0;refs=[];inputs=[]
for path in paths:
 end=stream.index(b'\n',pos);head=stream[pos:end].split();size=int(head[2]);raw=stream[end+1:end+1+size];assert stream[end+1+size:end+2+size]==b'\n';pos=end+2+size
 identity={'path':path,'git_blob':head[0].decode(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};inputs.append(identity);hits=[]
 for node in ast.walk(ast.parse(raw)):
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:hits.append({'line':node.lineno,'role':'definition','symbol':node.name})
  elif isinstance(node,ast.Name) and node.id in names:hits.append({'line':node.lineno,'role':type(node.ctx).__name__,'symbol':node.id})
  elif isinstance(node,ast.Attribute) and node.attr in names:hits.append({'line':node.lineno,'role':'attribute','symbol':node.attr})
  elif isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in names|resources:hits.append({'line':node.lineno,'role':'exact-string declaration/resource','symbol':node.value})
  elif isinstance(node,ast.ImportFrom):
   for alias in node.names:
    if alias.name in names:hits.append({'line':node.lineno,'role':'import','symbol':alias.name,'module':node.module,'alias':alias.asname})
 if hits:refs.append({**identity,'references':sorted(hits,key=lambda x:(x['line'],x['symbol'],x['role']))})
assert pos==len(stream)
curated=[]
for name in sorted(resources):
 path='policy-engine/data/dataset_catalog/'+name;raw=subprocess.check_output(['git','show',sha+':'+path],cwd=repo);curated.append({'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
actual=[x for x in subprocess.check_output(['git','ls-tree','-r','--name-only',sha,'policy-engine/data/dataset_catalog'],cwd=repo,text=True).splitlines() if x.endswith('.yaml')];assert set(actual)=={x['path'] for x in curated}
r={'check':'PASS','source_sha':sha,'source_tree':tree,'scope':'complete tracked source-Python AST lexical definitions, names, attributes, import names and exact source/string/resource declarations for existing curated defaultloader symbols; transitive arbitrary dynamic dispatch not inferred','python_files':len(inputs),'reference_files':len(refs),'resource_files':len(curated),'symbols':sorted(names),'resources':curated,'complete_input_manifest':inputs,'reference_manifest':refs,'missing_or_unresolved_boundaries':['Arbitrary dynamic import/monkeypatch/caller dispatch is not inferred; actual installed path/default consumers separately executed.','Raw WVS CSV/XLSX and mutable runtime data not part of four curated defaults.']};(out/'curated-resource-consumer-denominator.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'check':'PASS','source':sha,'python_files':len(inputs),'reference_files':len(refs),'resource_files':len(curated),'paths':[x['path'] for x in refs]},indent=2))
