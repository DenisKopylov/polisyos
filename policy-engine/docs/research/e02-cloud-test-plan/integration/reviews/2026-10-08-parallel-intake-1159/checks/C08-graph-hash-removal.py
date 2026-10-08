import inspect
import json
import runpy
import sys
from pathlib import Path
root, checkout, source, out, selectors = sys.argv[1:]
sys.path.insert(0, str(Path(checkout) / "policy-engine/src"))
import polisyos.ir.analytics.causal as causal
text = inspect.getsource(causal._partial_proof_graph_input)
removed = '    if actual_bytes_hash != expected or typed_payload_hash != expected:\n        raise ValueError("Partial graph proof original graph content does not match its basis.")\n'
assert text.count(removed) == 1, "one exact property guard"
mutant = text.replace(removed, "")
assert all(token in mutant for token in ["graph_payload_sha256", "actual_bytes_hash", "typed_payload_hash", "get_manifest", "load_causal_graph_model", "causal_graph"])
exec(compile(mutant, causal.__file__, "exec"), causal.__dict__)
Path(out, "removal-recipe.json").write_text(json.dumps({"source": source, "function": "polisyos.ir.analytics.causal._partial_proof_graph_input", "removed": removed, "in_memory_only": True, "actual_source_files_unchanged": True, "remaining": "Actual graph/CAS/type/hash derivation and markers/lineage stay; only rejection on content mismatch removed", "expected": "one stale-hash test assertion FAIL and unchanged correct-graph positive PASS"}, indent=2) + "\n")
sys.argv = ["exact_pytest.py", root, checkout, source, out, selectors]
runpy.run_path(str(Path(root) / "policy-engine/_build/e02-g-continuation-20261006/R/watch-20261008-1025/exact_pytest.py"), run_name="__main__")
