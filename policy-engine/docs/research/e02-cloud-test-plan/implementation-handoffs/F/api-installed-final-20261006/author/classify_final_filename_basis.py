"""Read-only literal filename/config basis, separate from executed loader consumers."""
from __future__ import annotations
import ast,collections,hashlib,json,pathlib,subprocess
root=pathlib.Path('/workspace/e02-F-api-20261006');scratch=pathlib.Path('/tmp/e02-F-continuation-20261006/api');sha='8236d9c368336a5ea20c1586f29aea7321db6536'
census=json.loads((scratch/'census-8236-full.json').read_bytes());assert census['source_sha']==sha
argv=['git','grep','--no-textconv','-I','-n','-i','-E',r'(causal_engine[.]py|interference[.]py|id_engine[.]py|spec_from_file_location|SourceFileLoader|runpy|package_data|package-data)',sha,'--']
proc=subprocess.run(argv,cwd=root,capture_output=True);assert proc.returncode in (0,1);(scratch/'filename-8236-gitgrep.stdout').write_bytes(proc.stdout);(scratch/'filename-8236-gitgrep.stderr').write_bytes(proc.stderr)
def role(p):
 return 'runtime_source' if '/src/' in p else 'test_source' if '/tests/' in p else 'tool_source' if '/tools/' in p else 'historical_research_source' if '/docs/research/' in p else 'documentation' if '/docs/' in p else 'configuration_or_other_tracked_source'
rows=[]
for line in proc.stdout.decode('utf-8').splitlines():
 prefix,text=line.split(':',1);path,line_number,text=text.split(':',2);assert prefix==sha
 rows.append({'path':path,'line':int(line_number),'source_role':role(path),'text':text,'classification':'literal_retired_filename_mention' if any(t in text.lower() for t in ('causal_engine.py','interference.py','id_engine.py')) else 'loader_or_package_configuration_lexical_candidate','executed_client_established':False})
loader_rows=[];python_candidates=sorted({r['path'] for r in rows if r['path'].endswith('.py')})
for path in python_candidates:
 data=subprocess.check_output(['git','show',sha+':'+path],cwd=root);tree=ast.parse(data,filename=path)
 aliases={}
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):
   for a in n.names:aliases[a.asname or a.name.split('.')[0]]=a.name if a.asname else a.name.split('.')[0]
  if isinstance(n,ast.ImportFrom):
   for a in n.names:
    if a.name!='*':aliases[a.asname or a.name]=(n.module or '')+'.'+a.name
 def name(n):
  if isinstance(n,ast.Name):return aliases.get(n.id,n.id)
  if isinstance(n,ast.Attribute):return name(n.value)+'.'+n.attr
  return '<computed_callable>'
 for n in ast.walk(tree):
  if not isinstance(n,ast.Call):continue
  called=name(n.func)
  if called not in ('runpy.run_path','runpy.run_module','importlib.util.spec_from_file_location','importlib.machinery.SourceFileLoader'):continue
  literal={}
  for i,a in enumerate(n.args):
   if isinstance(a,ast.Constant) and isinstance(a.value,str):literal[str(i)]=a.value
  loader_rows.append({'path':path,'line':n.lineno,'source_role':role(path),'syntactic_callable_address':called,'expression':ast.unparse(n),'literal_string_arguments':literal,'argument_identity':'literal_strings_only' if len(literal)==len(n.args) and not n.keywords else 'contains_computed_or_nonstring_or_keyword_arguments','executed_client_established':False})
modulebase='policy-engine/src/polisyos/foundry/methods/catalog/causal/'
retired=[]
for n in ('id_engine','causal_engine','interference'):
 old=modulebase+n+'.py';new=modulebase+n+'/__init__.py';r=subprocess.run(['git','cat-file','-e',sha+':'+old],cwd=root,capture_output=True)
 blob=subprocess.check_output(['git','rev-parse',sha+':'+new],cwd=root,text=True).strip();data=subprocess.check_output(['git','show',sha+':'+new],cwd=root)
 retired.append({'retired_filename':old,'retired_blob_present':r.returncode==0,'supported_package_initializer':new,'oid':blob,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'filename_loader_policy':'No alias shim; absent retired filename refuses while maintained package imports/real identification are independently exercised by installed consumers.'})
result={'schema':'policyos.e02.filename_loader_basis.v1','source_sha':sha,'source_tree':census['source_tree'],'executing_party':'F/causal_api read-only derived classifier','tracked_denominator':census['denominator'],'complete_input_basis':{'census_path':str(scratch/'census-8236-full.json'),'bytes':(scratch/'census-8236-full.json').stat().st_size,'sha256':hashlib.sha256((scratch/'census-8236-full.json').read_bytes()).hexdigest(),'tracked_manifest_sha256':census['tracked_manifest_sha256']},'gitgrep_command':argv,'gitgrep_exit_code':proc.returncode,'lexical_rows':rows,'lexical_counts_by_role':dict(collections.Counter(r['source_role'] for r in rows)),'loader_ast_rows':loader_rows,'loader_ast_counts_by_role':dict(collections.Counter(r['source_role'] for r in loader_rows)),'python_lexical_candidate_paths':python_candidates,'retirement_source_bindings':retired,'supported_window_git_refs':[{'path':'policy-engine/src/polisyos/foundry/methods/catalog/causal/README.md','source_sha':sha,'sections':'Causal engine and interference compatibility surface; filename loading and supported package addresses'},{'path':'policy-engine/docs/reference/foundry/causal-engine-architecture.md','source_sha':sha,'sections':'Module Map and causal facade ABI'}],'limitations':['Complete chosen tracked Git tree only; ignored/untracked/external/private plugins excluded.','git grep -I does not traverse binary/symlink targets; excluded counts named by maintained full census.','Literal filename mentions include historical receipts and docs, not established runtime clients.','AST loader rows resolve literal imported aliases in lexical candidate Python files; reassignments/computed callable aliases, arbitrary plugin/config/exec flow remain unresolved.','No inferred absence of dynamic/external filename clients; actual supported package/runpy/file-loader refusal and FQN/pickle/pydoc/monkeypatch/registry consumers are independent installed executions.']}
p=scratch/'filename-loader-8236-classification.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'source_sha':sha,'lexical_rows':len(rows),'lexical_counts_by_role':result['lexical_counts_by_role'],'loader_ast_rows':len(loader_rows),'loader_ast_counts_by_role':result['loader_ast_counts_by_role'],'retired_file_checks':retired,'output':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))
