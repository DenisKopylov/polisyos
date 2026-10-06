"""Remove polynomial evaluation in memory while keeping fit fields and method markers."""
import ast
import hashlib
import inspect
import json
import pathlib
import subprocess

import pytest
from polisyos.foundry.methods.catalog.causal import gcm_query

path = pathlib.Path(inspect.getsourcefile(gcm_query._polynomial_predict))
body = path.read_bytes()
tree = ast.parse(body)
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_polynomial_predict')
function.body.insert(0, ast.Return(value=ast.Constant(value=None)))
replacement = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
exec(compile(replacement, str(path) + ':memory-property-removal', 'exec'), gcm_query.__dict__)
root = path.parents[7]
print(json.dumps({'source_path': str(path), 'source_sha256': hashlib.sha256(body).hexdigest(), 'source_sha': subprocess.check_output(['git','rev-parse','HEAD'], cwd=root,text=True).strip(), 'removal': 'early None from actual polynomial evaluator; complete original function body remains unreachable; polynomial fit fields and method signatures unchanged', 'filesystem_changed': path.read_bytes() != body}))
code = pytest.main(['-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short','tests/unit/foundry/methods/catalog/causal/test_polynomial_helper_cas_consumers.py::test_existing_polynomial_helper_to_typed_cas_real_query_and_fresh_reader','tests/unit/foundry/methods/catalog/causal/test_polynomial_helper_cas_consumers.py::test_existing_polynomial_fit_helper_shared_residual_twin_cas_and_fresh_reader'])
assert path.read_bytes() == body
raise SystemExit(code)
