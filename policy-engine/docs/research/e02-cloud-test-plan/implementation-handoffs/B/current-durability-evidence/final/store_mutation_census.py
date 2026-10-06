"""Complete canonical owner AST census; navigation, not a behavioral oracle."""
import ast,hashlib,json,subprocess,sys
from pathlib import Path
root=Path('/workspace/e02-B-current-durability');sha=sys.argv[1]
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==sha
p=root/'policy-engine/src/polisyos/runtime/http/services/control_plane_store.py';source=p.read_text();assert source==subprocess.check_output(['git','show',f'{sha}:{p.relative_to(root)}'],cwd=root,text=True)
tree=ast.parse(source);owner=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ControlPlaneStore');methods={n.name:n for n in owner.body if isinstance(n,ast.FunctionDef)}
mutation_inlets={'_execute','_sqlite_mutation_connection','_postgres_mutation_cursor'}
read_or_factory={'_fetchone':'read-only SQL intake','_fetchall':'read-only SQL intake','_ensure_sqlite_schema':'fresh-instance constructor DDL','_ensure_postgres_schema':'fresh-instance constructor DDL','_job_transaction':'canonical actual SQL transaction owner','_postgres_cursor':'canonical raw resource factory','_sqlite_connection':'canonical raw resource factory'}
rows=[];unadmitted=[];calls={}
for name,method in methods.items():
 actual=[];self_calls=set()
 for node in ast.walk(method):
  if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute):continue
  if isinstance(node.func.value,ast.Name) and node.func.value.id=='self':
   self_calls.add(node.func.attr)
   if node.func.attr in mutation_inlets|{'_sqlite_connection','_postgres_cursor','_job_transaction'}:
    actual.append({'callee':node.func.attr,'line':node.lineno})
 calls[name]=self_calls
 raw=[c for c in actual if c['callee'] in {'_sqlite_connection','_postgres_cursor'}]
 if raw and name not in read_or_factory:unadmitted.append({'method':name,'calls':raw})
 if actual:rows.append({'method':name,'line':method.lineno,'inlets':actual,'scope_exception':read_or_factory.get(name)})
mutators={name for name in methods if calls[name]&mutation_inlets}-mutation_inlets
while True:
 new=mutators|{name for name in methods if calls[name]&mutators and name not in read_or_factory and name!='__init__'}
 if new==mutators:break
 mutators=new
print(json.dumps({'target_sha':sha,'target_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip(),'source':str(p.relative_to(root)),'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'denominator':{'source_files':1,'file_type':'Python AST','owner_class':'ControlPlaneStore','all_owner_methods':len(methods),'SQL_or_transaction_inlet_methods':len(rows),'publication_mutator_methods_including_delegators':len(mutators)},'full_inlet_census':rows,'all_mutator_methods':sorted(mutators),'unadmitted_raw_resource_methods':unadmitted,'callback_loan_scope':'HumanDecisionWriteFence and HumanDecisionRecoveryFence receive actual execute/load callbacks only within canonical admitted mutation connection/cursor contexts; public DTO construction does not grant store admission.','limitations':['Static source/inlet census is navigation and reviewer denominator, not runtime PASS.','Actual ControlWorker-bound injected store instance; unbound admin APIs and arbitrary raw SQL/new store instances are not universal store authorization.','No live PostgreSQL/backend, multi-host, external idempotency or power-loss claim.']},indent=2))
assert not unadmitted
