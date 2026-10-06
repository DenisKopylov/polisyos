"""Preload immutable native test modules before pytest's assertion rewrite finder."""
import hashlib,importlib,json,pytest
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
names=["test_did_diagnostic_consumer","test_causal_input_byte_binding"]
bindings=[]
for name in names:
    module=importlib.import_module("tests.unit.scientist.nodes.builtins.simulate."+name)
    assert module.__frozen_e02_source_sha__==owner.__frozen_e02_source_sha__
    bindings.append({"module":module.__name__,"source_sha":module.__frozen_e02_source_sha__,"source_sha256":module.__frozen_e02_source_sha256__})
print(json.dumps({"frozen_owner_sha":owner.__frozen_e02_source_sha__,"frozen_owner_sha256":owner.__frozen_e02_source_sha256__,"native_test_bindings":bindings,"harness":"preload exact Git native test modules before pytest rewriting; child inherits exact owner selector; no product/source modification"},indent=2),flush=True)
raise SystemExit(pytest.main(["-o","addopts=","-q","-p","no:cacheprovider",*[("tests/unit/scientist/nodes/builtins/simulate/"+n+".py") for n in names]]))
