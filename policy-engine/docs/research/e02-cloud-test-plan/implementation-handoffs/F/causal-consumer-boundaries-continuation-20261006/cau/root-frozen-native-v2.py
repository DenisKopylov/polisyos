"""Supply Git-frozen native module objects at pytest's supported collection hook."""
import importlib,json,pytest
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
names=["test_did_diagnostic_consumer","test_causal_input_byte_binding"]
modules={name:importlib.import_module("tests.unit.scientist.nodes.builtins.simulate."+name) for name in names}
bindings=[]
for name,module in modules.items():
    assert module.__frozen_e02_source_sha__==owner.__frozen_e02_source_sha__
    bindings.append({"module":module.__name__,"source_sha":module.__frozen_e02_source_sha__,"source_sha256":module.__frozen_e02_source_sha256__})
class FrozenNativeModule(pytest.Module):
    def _getobj(self):
        return modules[self.path.stem]
class FrozenCollection:
    def pytest_pycollect_makemodule(self,module_path,parent):
        if module_path.stem in modules:
            return FrozenNativeModule.from_parent(parent,path=module_path)
    def pytest_collection_modifyitems(self,items):
        assert all(getattr(item.module,"__frozen_e02_source_sha__",None)==owner.__frozen_e02_source_sha__ for item in items)
        print(json.dumps({"collected_frozen_native_tests":len(items),"source_sha":owner.__frozen_e02_source_sha__}),flush=True)
print(json.dumps({"frozen_owner_sha":owner.__frozen_e02_source_sha__,"frozen_owner_sha256":owner.__frozen_e02_source_sha256__,"native_test_bindings":bindings,"harness":"supported pytest collection hook returns exact Git native test modules; genuine inherited fixtures/child consumers unchanged"},indent=2),flush=True)
raise SystemExit(pytest.main(["-o","addopts=","-q","-p","no:cacheprovider",*[("tests/unit/scientist/nodes/builtins/simulate/"+n+".py") for n in names]],plugins=[FrozenCollection()]))
