"""Isolated retained-marker property removal; never changes the candidate files."""
import ast
import hashlib
import inspect
import json
import sys
import textwrap

import pytest

from polisyos.foundry.calibration import identifiability as module

original = textwrap.dedent(inspect.getsource(module._load_execute_response_matrix))
tree = ast.parse(original)
function = tree.body[0]
removed = []
for index, node in enumerate(function.body):
    if isinstance(node, ast.If) and any(isinstance(child, ast.Attribute) and child.attr == 'model_copy' for child in ast.walk(node.test)):
        removed.append(ast.get_source_segment(original, node))
        function.body[index] = ast.Pass()
assert len(removed) == 1
mutated = ast.unparse(ast.fix_missing_locations(tree))
assert 'profile' not in removed[0] and 'response basis differs' in removed[0]
exec(compile(mutated, '<retained-response-basis-guard-removal>', 'exec'), module.__dict__)
print(json.dumps({'control':'remove runtime expected-basis predicate only',
 'candidate_source_sha':'c9125bc5e4d2992adeae468a79189d1fa535c88b',
 'function_original_sha256':hashlib.sha256(original.encode()).hexdigest(),
 'removed_predicate':removed[0], 'mutated_function_sha256':hashlib.sha256(mutated.encode()).hexdigest(),
 'markers_retained':['execute_scalar_state_response_v1','gate_eligible=False','units','exact CAS matrix and response numerical result'],
 'expected':'native positive PASS; forged-unit retained-marker test FAIL because the actual property is removed'}))
sys.exit(pytest.main(sys.argv[1:]))
