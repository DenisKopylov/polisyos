"""Preserve canonical exports while removing the admitted facade routing."""
from pathlib import Path
import ast, importlib.util, json, subprocess, sys, tomllib

R=Path('/workspace/e02-E-continuation-20261006');REF='bf3b54c3a894d2d9d9bfb0cd13edb13177405f33'
def blob(path):return subprocess.check_output(['git','show',REF+':'+path],cwd=R)
guard_path=R/'policy-engine/tools/devx/architecture/guardrails.py'
assert guard_path.read_bytes()==blob('policy-engine/tools/devx/architecture/guardrails.py')
spec=importlib.util.spec_from_file_location('e02_routing_negative_guard',guard_path);guard=importlib.util.module_from_spec(spec);sys.modules[spec.name]=guard;spec.loader.exec_module(guard)
allowed={}
for p in tomllib.loads(blob('policy-engine/architecture/public_surface/contract.toml').decode())['package']:
    allowed.setdefault(guard._root_for_module(p['module']),set()).update(p['supported_entrypoints'])
from polisyos import calibration as cal
from polisyos.foundry import uncertainty as uncertainty
from polisyos.foundry.calibration.report import load_calibration_report
assert len(cal.__all__)==29 and len(uncertainty.__all__)==20
assert cal.load_foundry_calibration_report is uncertainty.load_foundry_calibration_report is load_calibration_report
path='policy-engine/src/polisyos/calibration/__init__.py';source=blob(path).decode();mutant=source.replace('from polisyos.foundry.uncertainty import load_foundry_calibration_report','from polisyos.foundry.calibration.report import load_calibration_report as load_foundry_calibration_report');assert mutant!=source
def exports(text):return ast.literal_eval(next(n.value for n in ast.parse(text).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__all__' for t in n.targets)))
assert exports(source)==exports(mutant)
edges={}
for n in ast.walk(ast.parse(mutant)):
    if isinstance(n,ast.ImportFrom) and n.level==0 and n.module:
        guard._maybe_add_deep_import(edges=edges,allowed_entrypoints=allowed,source_module='polisyos.calibration',source_root='calibration',source_file=R/path,target_module=n.module)
print(json.dumps({'control':'AST property-removal of admitted routing; canonical exports/reader implementation unchanged, no source files edited','exports':{'calibration':len(cal.__all__),'uncertainty':len(uncertainty.__all__)},'canonical_identity':True,'introduced_private_edges':list(edges),'source_sha':REF}),flush=True)
assert not edges,'names remain present but private cross-root edge returns when admitted routing is removed'
