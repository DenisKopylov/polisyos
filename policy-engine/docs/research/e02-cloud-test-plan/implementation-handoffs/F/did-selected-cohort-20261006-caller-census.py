import ast,subprocess,pathlib,json,hashlib,re,collections
root=pathlib.Path('/workspace/e02-F-cau-20261006'); paths=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines(); records=[]; denominator=collections.Counter();parse_errors=[];decode_errors=[]
for path in paths:
 p=root/path;suffix=p.suffix
 if suffix not in {'.py','.json','.yaml','.yml','.toml','.md','.txt'}:continue
 denominator[suffix]+=1;b=p.read_bytes()
 try:source=b.decode()
 except UnicodeError as e:decode_errors.append({'path':path,'reason':str(e)});continue
 hits=[]
 for i,line in enumerate(source.splitlines(),1):
  kinds=[]
  if re.search(r'\bDifferenceInDifferences\b',line):kinds.append('legacy_class_literal')
  if 'causal.inference.difference_in_differences' in line:kinds.append('legacy_fqn_literal')
  if 'outcome_panel' in line or 'treatment_indicator' in line:kinds.append('old_slot_literal')
  if kinds:hits.append({'line':i,'kinds':kinds,'text':line})
 wildcard=[]
 if suffix=='.py':
  try:tree=ast.parse(source)
  except SyntaxError as e:parse_errors.append({'path':path,'reason':str(e)});continue
  for n in ast.walk(tree):
   if isinstance(n,ast.ImportFrom) and n.module and n.module.endswith('.did') and any(a.name=='*' for a in n.names):wildcard.append(n.lineno)
 if hits or wildcard:
  if '/src/' in '/'+path:
   role='canonical_historical_adapter_definition' if path.endswith('/causal/did.py') else 'other_method_slot_names' if all(h['kinds']==['old_slot_literal'] for h in hits) else 'live_production_reference_needs_review'
  elif '/tests/' in '/'+path:role='historical_replay_or_consumer_test'
  elif '/architecture/baselines/' in '/'+path:role='historical_structural_baseline'
  elif '/docs/' in '/'+path:role='source_card_or_historical_receipt_documentation'
  else:role='other_needs_review'
  records.append({'path':path,'sha256':hashlib.sha256(b).hexdigest(),'role':role,'hits':hits,'did_wildcard_import_lines':wildcard})
value={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'tree_sha':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip(),'complete_tracked_file_types':dict(denominator),'all_tracked_git_paths_sha256':hashlib.sha256(('\n'.join(paths)+'\n').encode()).hexdigest(),'decode_errors':decode_errors,'python_ast_parse_errors':parse_errors,'records':records,'limits':'Complete tracked literal/AST census is navigation plus source-role classification; actual default registry/dispatch/persisted-reader tests establish runtime witnesses separately. External production plans not admitted in cloud remain G input-dependent.'}
path=pathlib.Path('/workspace/e02-F-20261006-receipts/cau/caller-census-final.json');path.write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps({'source_sha':value['source_sha'],'complete_tracked_file_types':dict(denominator),'record_count':len(records),'decode_errors':len(decode_errors),'parse_errors':len(parse_errors),'roles':dict(collections.Counter(r['role'] for r in records)),'live_references':[r['path'] for r in records if 'needs_review' in r['role']]}))
