"""Independent in-memory removal of retained issue collection, keeping markers."""
import ast
import inspect
import json
from pathlib import Path
import textwrap
import pytest
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass
fn = ConfidencePass.validate
before = (id(fn), fn.__name__, fn.__module__, fn.__qualname__, fn.__doc__, str(inspect.signature(fn)), repr(fn.__annotations__))
tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
changes = 0
for handler in ast.walk(tree):
    if not isinstance(handler, ast.ExceptHandler):
        continue
    terminal = handler.body[-1]
    if not isinstance(terminal, ast.Return) or not isinstance(terminal.value, ast.Name):
        continue
    if terminal.value.id == 'issues':
        terminal.value = ast.List(elts=[ast.Subscript(value=ast.Name(id='issues', ctx=ast.Load()),
            slice=ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=1)), ctx=ast.Load())], ctx=ast.Load())
        changes += 1
assert changes == 1, changes
ast.fix_missing_locations(tree)
namespace = {}
exec(compile(tree, fn.__code__.co_filename, 'exec'), fn.__globals__, namespace)
old = fn.__code__
fn.__code__ = namespace['validate'].__code__
after = (id(fn), fn.__name__, fn.__module__, fn.__qualname__, fn.__doc__, str(inspect.signature(fn)), repr(fn.__annotations__))
assert before == after
print(json.dumps({'control': 'Keep only latest degraded issue, dropping accumulated prior blocker',
                 'public_markers_preserved': list(before), 'in_memory_only': True}))
try:
    result = pytest.main([str(Path(__file__).parent/'test_mixed_refs.py'), '-k', 'index_bad_simulation',
        '-o', 'addopts=', '-o', 'cache_dir='+str(Path(__file__).parent/'removal-cache'), '-q', '-s',
        '--tb=short', '--basetemp='+str(Path(__file__).parent/'removal-tmp')])
finally:
    fn.__code__ = old
raise SystemExit(result)
