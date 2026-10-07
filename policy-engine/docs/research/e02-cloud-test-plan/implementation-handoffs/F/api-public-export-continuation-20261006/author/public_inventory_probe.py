import json
from tools.devx.architecture import guardrails as g
rows=[]
for p in g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST):
 for module in p.supported_entrypoints:
  try:
   result=g._entrypoint_inventory(module)
   rows.append(dict(module=module,outcome='PASS',exports=list(result.exports),export_resolution=result.export_resolution))
  except Exception as exc:
   rows.append(dict(module=module,outcome='ERROR',error=repr(exc),notes=getattr(exc,'__notes__',[])))
print(json.dumps(dict(selector='Declared manifest supported_entrypoints, bounded static resolver only',rows=rows),indent=2))
raise SystemExit(int(any(row['outcome']!='PASS' for row in rows)))
