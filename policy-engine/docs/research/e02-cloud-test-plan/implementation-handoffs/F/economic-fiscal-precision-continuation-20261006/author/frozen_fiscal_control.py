from __future__ import annotations
import hashlib, importlib.abc, importlib.util, json, pathlib, subprocess, sys
root=pathlib.Path("/workspace/e02-F-economics-20261006")
sha="1324d2fcd7b75e448ad0fa1cce128a79101df1aa"
assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()==sha
name="polisyos.foundry.execute.mechanisms.fiscal"
path="policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py"
original=subprocess.check_output(["git","show",sha+":"+path],cwd=root)
source=original.decode()
mode=sys.argv[1]
if mode=="early32":
    old="dtype=jnp.promote_types(jnp.asarray(rate).dtype, jnp.float32)"
    assert source.count(old)==2
    source=source.replace(old,"dtype=jnp.float32")
elif mode=="calculation32":
    old="jnp.promote_types(state.agents.reported_income.dtype, jnp.float32)"
    assert source.count(old)==1
    source=source.replace(old,"jnp.float32")
    old="jnp.promote_types(state.agents.income.dtype, jnp.float32)"
    assert source.count(old)==1
    source=source.replace(old,"jnp.float32")
elif mode=="calculation64":
    old="jnp.promote_types(state.agents.reported_income.dtype, jnp.float32)"
    assert source.count(old)==1
    source=source.replace(old,"jnp.float64")
    old="jnp.promote_types(state.agents.income.dtype, jnp.float32)"
    assert source.count(old)==1
    source=source.replace(old,"jnp.float64")
elif mode=="base":
    source=subprocess.check_output(["git","show","e84acb04fbe1fbebdfa5a54f87ff0fc72640a4ef:"+path],cwd=root).decode()
else: raise ValueError(mode)
for marker in ("def _validate_rate", "def compute_tax", "class TaxSubsidy", "class IncomeTax"):
    assert marker in source
executed=source.encode()
print(json.dumps(dict(mode=mode,scope="memory-only canonical fiscal module removal/control; all other imports native frozen tree",source_sha=sha,original_sha256=hashlib.sha256(original).hexdigest(),executed_sha256=hashlib.sha256(executed).hexdigest(),markers_preserved=True)),flush=True)
class Loader(importlib.abc.Loader):
    def create_module(self,spec):return None
    def exec_module(self,module):
        module.__file__=str(root/path)
        exec(compile(source,module.__file__,"exec"),module.__dict__)
class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname==name:
            return importlib.util.spec_from_loader(fullname,Loader(),origin=str(root/pathlib.Path("policy-engine/src/polisyos/foundry/execute/mechanisms/fiscal.py")))
        return None
sys.meta_path.insert(0,Finder())
import pytest
exit_code=pytest.main(sys.argv[2:])
census=[]
for fullname,module in sorted(sys.modules.items()):
    f=getattr(module,"__file__",None)
    if not f:continue
    file=pathlib.Path(f)
    try: rel=file.resolve().relative_to(root)
    except (ValueError,OSError):continue
    if file.suffix!=".py" or not file.is_file():continue
    data=file.read_bytes()
    result=subprocess.run(["git","show","e84acb04fbe1fbebdfa5a54f87ff0fc72640a4ef:"+str(rel)],cwd=root,capture_output=True)
    census.append(dict(module=fullname,path=str(rel),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),equal_base=result.returncode==0 and data==result.stdout,executed_override=fullname==name))
print(json.dumps(dict(imported_python_census=census,denominator=len(census),scope="actual sys.modules repository Python imports only; external/native plugins and unimported files outside denominator",exit_code=int(exit_code))),flush=True)
sys.exit(exit_code)
