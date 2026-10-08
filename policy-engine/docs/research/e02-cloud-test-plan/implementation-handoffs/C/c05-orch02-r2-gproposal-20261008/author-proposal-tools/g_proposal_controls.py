"""Record exact pathwise suppliers and preservation checks for unapplied G docs."""
import ast,difflib,hashlib,json,subprocess
from pathlib import Path
root=Path('/workspace/orch02-r2/c05/g-patch');repo=Path('/workspace/orch02-c05-r2-gproposal')
d=json.loads((root/'reconciliation.json').read_text());f=json.loads((root/'foreign-public-companions.json').read_text())
refs={'G':d['G'],'CAT':d['CAT'],'DFI':'ab44166335130463178e65dfc29a252c96afe479','r2_source':'2734ee49f6985ff2bd7ad6e3c4d6089a7d7848ca','forward_tree':'9633ae3e5fdbdcc6a6a76af3d7ef29bdaa12fd09','final_source':'5ccbfa15c5671623a4c1ff7a3145460c5ca5a857'}
extra=['policy-engine/src/polisyos/data_forge/domains/catalog/source_modules.py','policy-engine/src/polisyos/data_forge/domains/catalog/batch/source_registry.py','policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py','policy-engine/src/polisyos/core/artifacts/protocol.py','policy-engine/src/polisyos/core/artifacts/backends/config.py']
b=json.loads(Path('/workspace/orch02-r2/c05/frozen/source-freeze.json').read_text())
paths=sorted({r['path'] for r in b['all_binding_rows']}|{r['path'] for r in d['paths']}|{r['path'] for r in f['rows']}|set(extra))
def raw(ref,path):
 r=subprocess.run(['git','show',ref+':'+path],cwd=repo,capture_output=True);return r.stdout if r.returncode==0 else None
def identity(ref,path):
 x=raw(ref,path)
 if x is None:return None
 blob=subprocess.check_output(['git','hash-object','--stdin'],input=x,cwd=repo).decode().strip()
 return {'blob':blob,'sha256':hashlib.sha256(x).hexdigest(),'bytes':len(x)}
def definitions(text):
 result={}
 def walk(nodes,prefix=''):
  for n in nodes:
   if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
    name=prefix+n.name;result[name]=ast.dump(n)
    if isinstance(n,ast.ClassDef):walk(n.body,name+'.')
 walk(ast.parse(text).body);return result
preservation=[]
for r in d['paths']:
 if not r['path'].endswith('.py'):continue
 folder=Path(r['folder']);texts={x:(folder/x).read_text() for x in ['G','CAT','postimage']};defs={x:definitions(t) for x,t in texts.items()}
 foreign={k:v for k,v in defs['G'].items() if defs['CAT'].get(k)!=v}
 missing=[k for k,v in foreign.items() if k not in defs['postimage']]
 changed=[k for k,v in foreign.items() if defs['postimage'].get(k)!=v and k in defs['postimage']]
 selected=r['path'].endswith(('manifests.py','generation_basis.py','selection.py'))
 allowed={'DatasetBatchConfig','DatasetBatchConfig.run_signature','DatasetBatchConfig.default_registry_path','DatasetBatchConfig.load_registry','DatasetBatchConfig.uses_custom_registry','_load_wvs_bulk_rows','__resolve_implementation_dependency','RetrievalService','RetrievalService.__init__','RetrievalService._source_policy_for_profile','RetrievalService._source_policy','RetrievalService.resolve','RetrievalService._resolve_via_catalog'}
 unexpected=[k for k in missing+changed if not selected and k not in allowed]
 assert not unexpected,(r['path'],unexpected)
 locators={k:hashlib.sha256(v.encode()).hexdigest() for k,v in defs['G'].items() if 'catalog_default_resource_path' in v and defs['postimage'].get(k)==v}
 preservation.append({'path':r['path'],'foreign_definition_count':len(foreign),'preserved_foreign_definitions':[k for k,v in foreign.items() if defs['postimage'].get(k)==v],'owned_overlap_or_selected_contract_changes':missing+changed,'unexpected_changes':unexpected,'resource_locator_AST_hashes':locators,'selected_predecessor_contract':selected})
facades=[]
for r in f['rows']:
 old=raw(refs['G'],r['path']).decode();new=(root/'foreign-postimages'/r['path']).read_text();a,b=ast.parse(old),ast.parse(new)
 def assignments(t):
  q={}
  for n in t.body:
   if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):q[n.targets[0].id]=n.value
   if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name):q[n.target.id]=n.value
  return q
 old_assign,new_assign=assignments(a),assignments(b);checks=[]
 for name in ['_LAZY_IMPORTS','_LAZY_EXPORTS','_EXPORTS']:
  if name not in old_assign:continue
  old_map={ast.dump(k):ast.dump(v) for k,v in zip(old_assign[name].keys,old_assign[name].values)};new_map={ast.dump(k):ast.dump(v) for k,v in zip(new_assign[name].keys,new_assign[name].values)}
  assert all(new_map.get(k)==v for k,v in old_map.items());checks.append({'symbol':name,'old_entries':len(old_map),'new_entries':len(new_map),'every_old_entry_unchanged':True})
 if '__all__' in old_assign:
  try:
   old_names=ast.literal_eval(old_assign['__all__']);new_names=ast.literal_eval(new_assign['__all__']);assert all(x in new_names for x in old_names)
  except ValueError:
   assert ast.dump(old_assign['__all__'])==ast.dump(new_assign['__all__'])
  checks.append({'symbol':'__all__','every_old_entry_retained':True})
 old_defs,new_defs=definitions(old),definitions(new)
 changed=[k for k,v in old_defs.items() if new_defs.get(k)!=v]
 assert changed==(['__getattr__'] if r['path'].endswith('read_api/catalog.py') else []),(r['path'],changed)
 facades.append({'path':r['path'],'checks':checks,'additive_alias_dispatch_only':changed,'old_serving_function_count':len(old_defs),'old_CatalogSelectionError_preserved':r['path'].endswith('read_api/catalog.py')})
rows=[];contract_deltas=[]
owned={r['path'] for r in d['paths']};public={r['path'] for r in f['rows']}
for path in paths:
 identities={name:identity(ref,path) for name,ref in refs.items()};row={'path':path,'identities':identities,'supplied_in_owned_unapplied_patch':path in owned,'supplied_in_foreign_public_unapplied_patch':path in public,'same_G_CAT_bytes':identities['G']==identities['CAT']}
 if path not in owned and path not in public and identities['G']!=identities['CAT']:
  old_bytes=raw(refs['G'],path) or b'';cat_bytes=raw(refs['CAT'],path) or b''
  if path.endswith('.py'):
   old_defs,cat_defs=definitions(old_bytes.decode()),definitions(cat_bytes.decode())
   row['selected_contract_definition_changes']=[k for k,v in cat_defs.items() if old_defs.get(k)!=v]
   row['G_only_definition_names']=[k for k in old_defs if k not in cat_defs]
  row['status']='HELD_EXACT_PREDECESSOR_CONTRACT_OWNER_SELECTION_REQUIRED'
  contract_deltas.append('diff --git a/'+path+' b/'+path+'\n'+''.join(difflib.unified_diff(old_bytes.decode().splitlines(keepends=True),cat_bytes.decode().splitlines(keepends=True),fromfile='a/'+path if old_bytes else '/dev/null',tofile='b/'+path)))
 else:row['status']='UNAPPLIED_PATCH' if path in owned or path in public else 'G_BYTES_MATCH_SELECTED_SUPPLIER'
 rows.append(row)
contract=''.join(contract_deltas).encode();(root/'selected-predecessor-contract-reference.patch').write_bytes(contract)
report={'schema':'policyos.e02.c05.G-proposal-source-controls.v1','state':'UNAPPLIED_HELD_NOT_G_RUNTIME_OR_SOURCE_ACCEPTANCE','refs':refs,'dependency_path_count':len(rows),'rows':rows,'foreign_definition_preservation':preservation,'public_facade_preservation':facades,'selected_predecessor_reference':{'path':'selected-predecessor-contract-reference.patch','sha256':hashlib.sha256(contract).hexdigest(),'bytes':len(contract),'classification':'Historical G-to-selected-CAT contract bytes for owner selection, NOT a composition/apply proposal. Preserve G-only functions/locators before any supplier admission.'},'DFI_CAT_DAG':'c05-independent-source-DAG-66151f3b.json','formal_closure_ids':[],'native_G_claim':False}
(root/'source-controls.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'paths':len(rows),'reference_bytes':len(contract),'reference_sha256':hashlib.sha256(contract).hexdigest(),'facades':facades},indent=2))
