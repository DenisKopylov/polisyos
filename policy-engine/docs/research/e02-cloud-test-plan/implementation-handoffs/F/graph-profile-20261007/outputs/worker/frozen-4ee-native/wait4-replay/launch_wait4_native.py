"""Execute first actual focused native wave with forward corrected timing harness."""
from pathlib import Path
import hashlib,importlib.util,json,sys
D=Path(__file__).parent;script=D.parent.parent/'run_frozen_focused_native_wait4.py';R=Path('/workspace/e02-F-closeout-20261006');SHA='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
def binding(p):b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
spec=importlib.util.spec_from_file_location('fit_frozen_native_wait4_runner',script);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.D=D
sys.argv=[str(script),'--candidate',SHA,'--checkout',str(R),'--parent-python',str(R/'policy-engine/.venv/bin/python'),'--worker-python',str(R/'policy-engine/workers/dowhy-014/.venv/bin/python')]
with (D/'launcher-input.json').open('xb') as f:f.write((json.dumps({'argv':sys.argv,'launcher':binding(Path(__file__)),'runner':binding(script),'receipt_directory':str(D),'original_versions_full_refs':[binding(D.parent/(n+'-versions.stdout.json')) for n in ['parent','worker']],'scope':'Original launcher never reached pytest. This is first actual focused three-test wave; only timing/output-directory/unique metrics port differ from prior scratch harness.'},indent=2)+'\n').encode())
sys.exit(m.main())
