from __future__ import annotations
import importlib.abc, importlib.util, pathlib, sys, json, hashlib, runpy, subprocess
root=pathlib.Path('/workspace/e02-F-economics-20261006/policy-engine')
scratch=pathlib.Path('/tmp/e02-F-continuation-20261006/economics/fiscal-precision')
target='polisyos.foundry.execute.mechanisms.fiscal'
mode=sys.argv[1]
base=subprocess.check_output(['git','show','e84acb04fbe1fbebdfa5a54f87ff0fc72640a4ef:policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py'],cwd=root)
candidate=(scratch/'fiscal.py.candidate').read_bytes()
source=candidate if mode=='candidate' else base
class Loader(importlib.abc.Loader):
    def create_module(self,spec):return None
    def exec_module(self,module):
        module.__file__=str(root/'src/polisyos/foundry/execute/mechanisms/fiscal.py')
        exec(compile(source,module.__file__,'exec'),module.__dict__)
class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='polisyos.foundry.execute.mechanisms.fiscal':return importlib.util.spec_from_loader(fullname,Loader(),origin=str(root/'src/polisyos/foundry/execute/mechanisms/fiscal.py'))
        return None
sys.meta_path.insert(0,Finder())
print(json.dumps({'mode':mode,'counterfactual':mode=='candidate','canonical_source_sha256':hashlib.sha256(base).hexdigest(),'executed_source_sha256':hashlib.sha256(source).hexdigest(),'override_target':target if mode=='candidate' else None}),flush=True)
if sys.argv[2]=='pytest':
    import pytest
    raise SystemExit(pytest.main(sys.argv[3:]))
runpy.run_path(sys.argv[2],run_name='__main__')
