"""Remove collection semantics in memory while preserving producer/markers."""
import ast
import hashlib
import inspect
import json
import pathlib
import runpy
import sys

from polisyos.scientist.governance.passes import confidence_pass as owner

mode = sys.argv[1]
packet = json.loads(pathlib.Path(sys.argv[2]).read_bytes())
test_path = pathlib.Path(sys.argv[3])
source = inspect.getsource(owner)
tree = ast.parse(source)
cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ConfidencePass")
method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "validate")
changed = 0
if mode == "causal_role":
    for node in method.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == "causal_ref":
            call = node.body[0].value
            assert isinstance(call, ast.Call) and call.func.attr == "append"
            node.body[0] = ast.copy_location(ast.Assign(targets=[ast.Name(id="_unconsumed_causal_issue", ctx=ast.Store())], value=call.args[0]), node.body[0])
            changed += 1
elif mode == "collection_drop":
    for node in ast.walk(method):
        if isinstance(node, ast.ExceptHandler) and any(isinstance(item, ast.Constant) and item.value == "load_simulation_result" for item in ast.walk(node)):
            for item in node.body:
                if isinstance(item, ast.Return):
                    assert isinstance(item.value, ast.Name) and item.value.id == "issues"
                    item.value = ast.Subscript(value=ast.Name(id="issues", ctx=ast.Load()), slice=ast.Slice(lower=ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=1))), ctx=ast.Load())
                    changed += 1
else:
    raise ValueError(mode)
assert changed == 1
ast.fix_missing_locations(tree)
namespace = dict(owner.__dict__)
exec(compile(tree, str(pathlib.Path(owner.__file__).resolve()), "exec"), namespace)
original_class = owner.ConfidencePass
owner.ConfidencePass.validate = namespace["ConfidencePass"].validate
assert owner.ConfidencePass is original_class
spec = {**packet, "relabelled": True, "causal_location": "index", "simulation_kind": "none" if mode == "causal_role" else "corrupt", "simulation_location": "top_string", "min_ratio": 0.0}
print(json.dumps({"mode":mode,"source_path":owner.__file__,"source_sha256":hashlib.sha256(source.encode()).hexdigest(),"one_memory_only_change":changed,"preserved_class_identity":True,"preserved_marker_constants": ["CONFIDENCE_GATE_ELIGIBILITY_LOW","CONFIDENCE_SIM_RESULT_LOAD_FAILED","current source, graph, estimand, and target"],"native_bundle_ref":packet["bundle_ref"],"native_report_ref":packet["report_ref"],"original_candidate_ci_unchanged":True,"spec":spec},sort_keys=True))
read = runpy.run_path(str(test_path), run_name="tmle_persisted_consumer_removal")["_read"]
read(spec)
raise AssertionError("Removal survived the real consumer discriminator")
