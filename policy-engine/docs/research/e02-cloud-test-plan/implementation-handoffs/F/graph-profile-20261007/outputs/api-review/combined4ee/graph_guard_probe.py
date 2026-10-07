import ast
import hashlib
import inspect
import json
import os
import sys
import textwrap
from pathlib import Path
import pytest
import polisyos.foundry.methods.catalog.causal.graph_reconciliation as owner
import polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph as node

MODE = sys.argv[1]
assert MODE in {'untouched', 'removed'}
old = owner._validate_reconciliation_profile
static = owner._validate_static_admg
text = textwrap.dedent(inspect.getsource(old))
parsed = ast.parse(text)
function = parsed.body[0]
assert isinstance(function, ast.FunctionDef)
conditions = [statement for statement in function.body if isinstance(statement, ast.If)]
assert len(conditions) == 1
predicate = conditions[0].test
original_dump = ast.dump(parsed, include_attributes=False)
original_literals = sorted(node.value for node in ast.walk(parsed) if isinstance(node, ast.Constant) and isinstance(node.value, str))
if MODE == 'removed':
    conditions[0].test = ast.BoolOp(op=ast.And(), values=[predicate, ast.Constant(value=False)])
    ast.fix_missing_locations(parsed)
    new_literals = sorted(node.value for node in ast.walk(parsed) if isinstance(node, ast.Constant) and isinstance(node.value, str))
    assert original_literals == new_literals
    private = dict(owner.__dict__)
    exec(compile(parsed, str(Path(__file__).resolve()) + ':memory-only-removal', 'exec'), private)
    replacement = private[old.__name__]
    assert replacement.__name__ == old.__name__ and replacement.__qualname__ == old.__qualname__
    assert replacement.__module__ == old.__module__ and replacement.__doc__ == old.__doc__
    owner._validate_reconciliation_profile = replacement
    node._validate_reconciliation_profile = replacement
    assert owner._validate_static_admg is static
    assert owner.GraphType.MGRAPH.value == 'mgraph' and owner.GraphType.ADMG.value == 'admg'
print(json.dumps({'mode': MODE, 'canonical_owner': owner.__file__, 'node_owner': node.__file__, 'original_function': text, 'original_function_sha256': hashlib.sha256(text.encode()).hexdigest(), 'original_function_ast_sha256': hashlib.sha256(original_dump.encode()).hexdigest(), 'replacement_ast': ast.dump(parsed, include_attributes=False), 'retained_string_literals': original_literals, 'actual_scope': 'only runtime family predicate disabled in isolated process; same static guard, GraphType enum objects, function identity names/docstrings/message retained; no source writes or metadata shim'}, ensure_ascii=False), flush=True)
prefix = 'tests/unit/scientist/methods/causal/test_graph_intake_current_content.py::'
selectors = [prefix + name for name in ['test_mgraph_producer_and_node_refuse_without_retyping_or_publishing','test_supplied_mgraph_result_and_selected_cache_apply_same_profile_boundary','test_same_admg_shape_has_real_producer_node_and_fresh_reader','test_genuine_producer_to_fresh_reader_preserves_known_relations']]
code = pytest.main(['-q','-ra','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--basetemp=/tmp/e02-F-graph-profile-20261007/api-review/combined4ee/graph-' + MODE + '-tmp','--junitxml=/tmp/e02-F-graph-profile-20261007/api-review/combined4ee/graph-' + MODE + '.xml', *selectors])
root = Path('/workspace/e02-F-closeout-20261006/policy-engine/src').resolve()
origins=[]
for name, module in sorted(sys.modules.items()):
    if name == 'polisyos' or name.startswith('polisyos.'):
        path = getattr(module, '__file__', None)
        if path:
            path = Path(path).resolve()
            assert path.is_relative_to(root), (name, str(path))
            origins.append({'module': name, 'path': str(path)})
print(json.dumps({'actual_pytest_exit_code': int(code), 'origins': origins, 'fresh_reader_scope': 'same-process reopened FileSystemCAS; no fresh child or admitted real-world Runtime authority claim'}, ensure_ascii=False), flush=True)
raise SystemExit(code)
