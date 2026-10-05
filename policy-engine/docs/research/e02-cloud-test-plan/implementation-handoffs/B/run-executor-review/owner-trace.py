"""Trace the scoped common owner and its stdlib worker/callback delegate."""
import ast
import hashlib
import inspect
import subprocess
from pathlib import Path
from concurrent.futures import Future
import concurrent.futures.thread as thread

paths = [Path(p) for p in subprocess.check_output(
    ['git', 'ls-files', 'src/polisyos/common'], text=True
).splitlines() if p.endswith('.py')]
print('Scope: complete tracked common Python files:', len(paths))
for path in paths:
    print('INPUT', path, 'sha256', hashlib.sha256(path.read_bytes()).hexdigest())
    tree = ast.parse(path.read_text())
    for cls in [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]:
        if any('ThreadPoolExecutor' in ast.unparse(base) for base in cls.bases):
            print('Executor subclass:', path, cls.name, 'methods:', [
                node.name for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ])
print('Code trace: submit delegates directly to stdlib submit; initializer only marks thread identity.')
for obj in (thread.ThreadPoolExecutor.submit, thread._WorkItem.run, Future.set_result,
            Future._invoke_callbacks):
    path = Path(inspect.getsourcefile(obj))
    print('STDLIB', obj.__qualname__, path, 'sha256', hashlib.sha256(path.read_bytes()).hexdigest())
    print(inspect.getsource(obj))
print('Scoped missing capability: physical worker admission held through all user callbacks, or an owned nonblocking callback scheduling boundary. The canonical subclass does not wrap its delegated _WorkItem.run/Future callback lifecycle. Whole-repository absence, reflective/third-party callback consumers and general deadlock freedom are not established.')
