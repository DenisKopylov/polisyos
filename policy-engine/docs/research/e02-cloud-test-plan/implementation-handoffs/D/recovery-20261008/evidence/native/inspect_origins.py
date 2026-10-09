import hashlib,importlib,json,pathlib,sys
result=[]
for name in sys.argv[1:]:
 module=importlib.import_module(name);p=pathlib.Path(module.__file__);result.append({'module':name,'actual_file':str(p),'resolved_file':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
print(json.dumps({'schema':'orch04.actual_import_origins.v1','modules':result,'scope':'actual import origins only, not numerical or semantic conformance'},indent=2))
