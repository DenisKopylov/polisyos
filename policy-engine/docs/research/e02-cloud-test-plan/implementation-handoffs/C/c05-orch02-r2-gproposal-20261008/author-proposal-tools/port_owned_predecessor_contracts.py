"""Select necessary existing CAT method contracts pathwise in unapplied G artifacts."""
import ast,hashlib,json,subprocess
from pathlib import Path
root=Path('/workspace/orch02-r2/c05/g-patch');d=json.loads((root/'reconciliation.json').read_text());repo='/workspace/orch02-c05';source='5ccbfa15c5671623a4c1ff7a3145460c5ca5a857'
def methods(text,cls):
 lines=text.splitlines(keepends=True);node=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef) and n.name==cls)
 return {n.name:(min([n.lineno]+[q.lineno for q in n.decorator_list]),n.end_lineno,''.join(lines[min([n.lineno]+[q.lineno for q in n.decorator_list])-1:n.end_lineno])) for n in node.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
controls=[]
for r in d['paths']:
 path=r['path'];folder=Path(r['folder']);text=(folder/'postimage').read_text()
 if path.endswith('fabric/retrieval/service.py'):
  selected=['_source_policy','_selected_catalog_source_ids','_catalog_source_is_enabled','resolve','_resolve_via_catalog'];cls='RetrievalService'
 elif path.endswith('batch/config.py'):
  selected=['load_registry','default_registry_path','uses_custom_registry'];cls='DatasetBatchConfig'
 else:continue
 original=subprocess.check_output(['git','-C',repo,'show',source+':'+path],text=True);new_methods=methods(original,cls);current=methods(text,cls);lines=text.splitlines(keepends=True);edits=[];added=[]
 for name in selected:
  contract=new_methods[name][2]
  if name in current:
   a,b,old=current[name];edits.append((a-1,b,contract));before_sha=hashlib.sha256(old.encode()).hexdigest()
  else:added.append(contract);before_sha=None
  controls.append({'path':path,'method':cls+'.'+name,'source_ref':source,'source_path':path,'source_contract_sha256':hashlib.sha256(contract.encode()).hexdigest(),'proposal_pre_method_sha256':before_sha,'selection':'Existing owner CAT profile/currentness prerequisite; not a new local producer'})
 for a,b,s in sorted(edits,reverse=True):lines[a:b]=[s]
 text=''.join(lines)
 if added:
  anchor='    def _catalog_date_window('
  text=text.replace(anchor,'\n\n'.join(added)+'\n\n'+anchor,1)
 if cls=='DatasetBatchConfig':
  marker='from polisyos.data_forge.kernel.io import ensure_dirs, snapshot_component_dir'
  text=text.replace(marker,'from polisyos.data_forge.domains.catalog.registry import default_catalog_source_registry_path\n'+marker,1)
 ast.parse(text);compile(text,path,'exec');(folder/'postimage').write_text(text)
(root/'owned-predecessor-method-selection.json').write_text(json.dumps({'state':'UNAPPLIED_EXISTING_OWNER_CONTRACT_SELECTION','source':source,'methods':controls,'foreign_resource_locators':'Keep G catalog_default_resource_path call sites; do not replace G _resources.py or physical resource helpers.','native_G_claim':False},indent=2)+'\n')
