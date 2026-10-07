import ast, pathlib, json, hashlib, subprocess
root=pathlib.Path('/workspace/e02-F-graph-20261006'); source=root/'policy-engine/src'; base=source/'polisyos/foundry/methods/catalog/causal'
providers=['admg_ops.py','do_calculus.py','sigma_calculus.py','id_engine/core.py','id_engine/transport.py','id_engine/counterfactual.py','amn.py','ctf_calculus.py']
raw={'extract_undirected_edges','is_adjacent','has_directed_path','topological_order','has_directed_cycle'}
records=[];qualified={}
for p in providers:
 f=base/p;data=f.read_bytes();module='.'.join(f.relative_to(source).with_suffix('').parts);tree=ast.parse(data);exported=None
 for n in tree.body:
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__all__' for t in n.targets):
   try:exported=ast.literal_eval(n.value)
   except Exception:pass
 for n in tree.body:
  if not isinstance(n,ast.FunctionDef):continue
  args=[a.arg for a in n.args.posonlyargs+n.args.args+n.args.kwonlyargs]
  if not ({'graph','amn','selection_diagram'}&set(args)):continue
  public=not n.name.startswith('_') or (exported and n.name in exported)
  boundary=public or n.name in {'_build_counterfactual_graph','_pag_id_algorithm'}
  if not boundary:continue
  calls=sorted(set(ast.unparse(c.func) for c in ast.walk(n) if isinstance(c,ast.Call)))
  first=n.body[1] if isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Constant) and isinstance(n.body[0].value.value,str) else n.body[0]
  direct=any('_validate_static_admg'==c for c in calls)
  classification='raw_endpoint_or_orientation_inspection' if n.name in raw else 'static_causal_entry_or_builder'
  r={'path':str(f.relative_to(root)),'module':module,'function':n.name,'line':n.lineno,'args':args,'public':bool(public),'classification':classification,'direct_shared_guard':direct,'first_statement':ast.unparse(first),'calls':calls,'provider_sha256':hashlib.sha256(data).hexdigest()}
  records.append(r);qualified[module+'.'+n.name]=r
callers=[]; parsed=0
# Complete source denominator, no sampling; imported aliases and explicit FQN
# calls are resolved conservatively. Reflection/dynamic call targets remain a
# stated static-analysis limitation, with native entries tested independently.
for f in sorted(source.rglob('*.py')):
 tree=ast.parse(f.read_bytes());parsed+=1;aliases={}
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):
   for a in n.names:aliases[a.asname or a.name]=a.name
  elif isinstance(n,ast.ImportFrom) and n.module and n.level==0:
   for a in n.names:aliases[a.asname or a.name]=n.module+'.'+a.name
 for n in ast.walk(tree):
  if not isinstance(n,ast.Call):continue
  text=ast.unparse(n.func);head,sep,tail=text.partition('.');resolved=aliases.get(head,head)+(sep+tail if sep else '')
  if resolved in qualified:callers.append({'path':str(f.relative_to(root)),'line':n.lineno,'call':text,'resolved':resolved})
record={'schema':'policyos.e02.static_admg_profile_census.v1','source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'working_tree_note':'Development footprint; final frozen receipt must bind provider hashes exactly','provider_paths':providers,'entries':records,'entry_count':len(records),'classification_counts':{c:sum(r['classification']==c for r in records) for c in sorted(set(r['classification'] for r in records))},'resolved_static_callers':callers,'resolved_static_caller_count':len(callers),'complete_source_parse_denominator':parsed,'limitations':['Relative/reflection/dynamic dispatch calls not resolved by static census; public method facades examined separately','Census proves finite source/input denominator and routing, not universal algorithm correctness']}
out=pathlib.Path('/tmp/e02-F-continuation-20261006/graph/static-profile-denominator.json');out.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ('entries','resolved_static_callers')}));print([(r['function'],r['direct_shared_guard']) for r in records if r['classification']=='static_causal_entry_or_builder' and not r['direct_shared_guard']])
