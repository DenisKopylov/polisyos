from __future__ import annotations
import json,pathlib,subprocess,sys
root=pathlib.Path.cwd();base='198076863e143dea9f89f02734b13d50dae3eed5'
paths=subprocess.check_output(['git','diff','--name-only',base,'HEAD','--','policy-engine/src','policy-engine/tests'],cwd=root.parent,text=True).splitlines()
paths=[str(pathlib.Path(p).relative_to('policy-engine')) for p in paths if p.endswith('.py')]
assert paths, 'Empty source/test selector must not invoke repository-wide Ruff'
print(json.dumps({'whole_changed_python_path_denominator':paths,'count':len(paths),'base_sha':base,'target_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}),flush=True)
for argv in [[sys.executable,'-m','ruff','check',*paths],[sys.executable,'-m','ruff','format','--check',*paths]]:
 print(json.dumps({'argv':argv}),flush=True);status=subprocess.call(argv,cwd=root)
 if status: sys.exit(status)
