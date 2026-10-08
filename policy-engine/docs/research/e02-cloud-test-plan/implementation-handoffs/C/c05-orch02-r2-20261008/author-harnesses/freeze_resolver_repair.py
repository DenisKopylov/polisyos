"""Bind the minimal canonical dispatch repair to immutable staged Git inputs."""
import ast,collections,hashlib,json,subprocess
from pathlib import Path
repo=Path('/workspace/orch02-c05');out=Path('/workspace/orch02-r2/c05/resolver-repair');out.mkdir(exist_ok=True)
path='policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/loaders.py';parent='2734ee49f6985ff2bd7ad6e3c4d6089a7d7848ca';old='2a7f9bf8f02aa8e751614f751b6d9ee2af2dfe5e'
def git(*args):return subprocess.check_output(['git',*args],cwd=repo)
tree=git('write-tree').decode().strip();before=git('show',parent+':'+path).decode();after=git('show',tree+':'+path).decode();prior=git('show',old+':'+path).decode()
contracts={n.target.id:ast.unparse(n.annotation) for n in ast.parse(before).body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='__make_implementation_proxy' and n.target.id=='_to_iso3'}
controls=[]
class Normalize(ast.NodeTransformer):
 def visit_Call(self,n):
  self.generic_visit(n)
  if isinstance(n.func,ast.Call) and isinstance(n.func.func,ast.Name) and n.func.func.id=='cast' and len(n.func.args)==2:
   expr=n.func.args[1]
   if isinstance(expr,ast.Call) and isinstance(expr.func,ast.Name) and expr.func.id=='__resolve_implementation_dependency':
    name,owner=[ast.literal_eval(a) for a in expr.args]
    if name not in contracts:return n
    annotation=ast.literal_eval(n.func.args[0]);assert annotation==contracts[name]
    controls.append({'name':name,'owner':owner,'exact_callable_contract':annotation,'line':n.lineno})
    n.func=ast.Name(id=name,ctx=ast.Load())
  return n
normalized=Normalize().visit(ast.parse(after));assert ast.dump(normalized)==ast.dump(ast.parse(before))
prior_calls=collections.Counter()
for n in ast.walk(ast.parse(prior)):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='__resolve_implementation_dependency' and len(n.args)==2:
  try:k=tuple(ast.literal_eval(a) for a in n.args)
  except ValueError:continue
  if k[0] in contracts:prior_calls[k]+=1
new_calls=collections.Counter((r['name'],r['owner']) for r in controls);assert prior_calls==new_calls,(prior_calls,new_calls)
patch=git('diff','--cached','--binary','--full-index');(out/'resolver-dispatch-forward.patch').write_bytes(patch)
binding=json.loads(Path('/workspace/orch02-r2/c05/frozen/source-freeze.json').read_text())
for r in binding['all_binding_rows']:
 try:
  raw=git('show',tree+':'+r['path']);blob=git('rev-parse',tree+':'+r['path']).decode().strip();v={'blob':blob,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
 except subprocess.CalledProcessError:v=None
 r['identities']['resolver_repair_tree']=v
binding['refs']['resolver_repair_tree']=tree
(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
d={'schema':'policyos.e02.c05.resolver-forward-freeze.v1','source_parent':parent,'tree':tree,'changed_paths':git('diff','--cached','--name-only').decode().splitlines(),'patch_sha256':hashlib.sha256(patch).hexdigest(),'patch_bytes':len(patch),'precedence':'Existing canonical request-context > explicit-global > owner; missing globals resolve owner. No resolver, session/cache owner, or public proxy definition changes.','actual_call_count':len(controls),'name_owner_denominator':len(new_calls),'controls':controls,'normalized_new_AST_equals2734_AST':True,'resolution_quantity_equals_pre_typed_2a7_AST':True,'supplier_binding_rows':len(binding['all_binding_rows']),'supplier_denominator':46,'native_initial_receipt':'/workspace/orch02-r2/native-c05-c12/c05-native-initial-receipt-2734ee49.json','required_invocation_new2734':'/workspace/orch02-r2/c05/required-invocation/command.json','native_forward_status':'UNRUN_PENDING_NONAUTHOR_GO'}
(out/'freeze.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:d[k] for k in ['tree','changed_paths','patch_sha256','patch_bytes','actual_call_count','name_owner_denominator']},indent=2))
