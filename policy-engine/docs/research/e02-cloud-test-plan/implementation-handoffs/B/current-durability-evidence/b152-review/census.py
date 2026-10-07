"""Literal Python importer/call/definition census of the finite source/tools scope."""
import ast,hashlib,json,pathlib,subprocess
root=pathlib.Path('/workspace/e02-B-current-durability');pe=root/'policy-engine';rows=[];failures=[];files=[]
for base in ['src','tools']:
 for p in sorted((pe/base).rglob('*.py')):
  if '__pycache__' not in p.parts:files.append(p)
for p in files:
 b=p.read_bytes()
 try:t=ast.parse(b,filename=str(p))
 except SyntaxError as exc:failures.append({'path':str(p.relative_to(root)),'error':str(exc)});continue
 hits=[]
 for n in ast.walk(t):
  if isinstance(n,ast.ImportFrom):
   for a in n.names:
    if a.name in ['build_cas_integrity_report','VerifiedSnapshotArtifactStore','VerifiedArtifactSnapshot']:hits.append({'kind':'import_from','line':n.lineno,'module':n.module,'name':a.name,'alias':a.asname})
  elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ['build_cas_integrity_report','get_verified_snapshot']:hits.append({'kind':'definition','line':n.lineno,'name':n.name})
  elif isinstance(n,ast.Call):
   name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
   if name in ['build_cas_integrity_report','get_verified_snapshot']:hits.append({'kind':'call','line':n.lineno,'name':name})
 if hits:rows.append({'path':str(p.relative_to(root)),'sha256':hashlib.sha256(b).hexdigest(),'hits':hits})
rec={'target_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'scope':'All .py files recursively under policy-engine/src and policy-engine/tools; tests/docs excluded; literal import/call/definition census, no reflection/alias-universal claim','files':len(files),'parse_errors':failures,'records':rows}
print(json.dumps(rec,indent=2))
