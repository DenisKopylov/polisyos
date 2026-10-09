import ast, collections, dataclasses, hashlib, json, os, subprocess, sys
from pathlib import Path
from typing import Final
root=Path('/workspace/ORCH04-C10/policy-engine')
source_path=root/'tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py'
source=source_path.read_text(); tree=ast.parse(source)
names={'_CONSTRUCTOR_TARGETS','_DYNAMIC_TARGET_MARKERS','_PROMOTION_PORT_TARGET','_CallSite','_module_name','_attribute_name','_scan_python_source','_source_role','_production_python_paths','_assert_constructor_contract'}
kept=[]
for node in tree.body:
 name=getattr(node,'name',None)
 if isinstance(node, ast.AnnAssign) and isinstance(node.target,ast.Name): name=node.target.id
 if name in names: kept.append(node)
ns={'ast':ast,'os':os,'subprocess':subprocess,'dataclass':dataclasses.dataclass,'Path':Path,'Final':Final}
exec(compile(ast.Module(body=kept,type_ignores=[]),str(source_path),'exec'),ns)
old_role=ns['_source_role']
def proposed_role(path):
 if path.split('/',1)[0] in {'docs','dev-oracles','workers'} and not path.startswith('docs/research/'): return 'production_capable'
 return old_role(path)
ns['_source_role']=proposed_role
paths,fs=ns['_production_python_paths'](root)
constructors=[]; promotions=[]; ambiguous=[]
for rel in sorted(paths):
 c,p,a=ns['_scan_python_source'](source=(root/rel).read_text(),module=ns['_module_name'](root,root/rel),source_path=rel)
 constructors.extend(c);promotions.extend(p);ambiguous.extend(a)
extras=[dataclasses.asdict(r) for r in constructors if not r.source_path.startswith(('src/','tools/'))]
report={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'test_blob':subprocess.check_output(['git','hash-object',str(source_path)],cwd=root,text=True).strip(),'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'paths':sorted(paths),'paths_count':len(paths),'filesystem_equal':paths==fs,'constructors':[dataclasses.asdict(r) for r in constructors],'new_family_calls':extras,'promotion_calls':[dataclasses.asdict(r) for r in promotions],'ambiguous':ambiguous}
try: ns['_assert_constructor_contract'](tuple(constructors),tuple(promotions),tuple(ambiguous));report['contract']='PASS'
except AssertionError:report['contract']='FAIL'
def norm(obj):
 if isinstance(obj,(set,frozenset)):return sorted(obj)
 raise TypeError
Path('/workspace/ORCH04-evidence/c10/complete-scanner-proposed-role-diagnostic.json').write_text(json.dumps(report,indent=2,default=norm)+'\n')
print(json.dumps({k:report[k] for k in ['paths_count','filesystem_equal','contract','new_family_calls','ambiguous']},default=norm))
