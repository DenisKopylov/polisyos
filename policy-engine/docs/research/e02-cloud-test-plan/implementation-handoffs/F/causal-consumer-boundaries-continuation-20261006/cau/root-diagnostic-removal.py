"""Remove only canonical consumer diagnostic recomputation; retain genuine jobs, CAS, target markers."""
import hashlib,inspect,json,pytest
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
original=owner._verify_selected_did_diagnostics
print(json.dumps({"source_sha":owner.__frozen_e02_source_sha__,"source_sha256":owner.__frozen_e02_source_sha256__,"removal":"only _verify_selected_did_diagnostics body -> return None; target verifier, producer, markers, CAS, real dispatcher unchanged","original_function_sha256":hashlib.sha256(inspect.getsource(original).encode()).hexdigest()}),flush=True)
def removed_diagnostic_check(output, *, observational_data, staggered):
    return None
owner._verify_selected_did_diagnostics=removed_diagnostic_check
raise SystemExit(pytest.main(["-o","addopts=","-q","-p","no:cacheprovider","tests/unit/scientist/nodes/builtins/simulate/test_did_diagnostic_consumer.py","-k","changed_only_diagnostic_window or fresh_cas_reader_refuses"]))
