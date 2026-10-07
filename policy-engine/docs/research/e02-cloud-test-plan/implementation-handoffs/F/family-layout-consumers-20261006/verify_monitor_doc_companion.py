"""Verify a documentation-only companion preserves actual executable owners."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path('/workspace/e02-F-fry-20261006')
SCRATCH = Path('/tmp/e02-F-continuation-20261006/foundry')
PYTHON = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
SCIENCE = '7f05b6259e0c78fac81a0baa4bff41e648a9d771'
MONITOR = 'ec6944c8c5b4807f291c96919309472de60de127'
PATH = 'policy-engine/src/polisyos/foundry/methods/lifecycle/output_monitor.py'


def source(sha, path):
    return subprocess.check_output(['git', 'show', sha + ':' + path], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def executable_ast(data):
    tree = ast.parse(data)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                del body[0]
    return ast.dump(tree, include_attributes=False).encode()


def main():
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    old, new = source(MONITOR, PATH), source(sha, PATH)
    assert executable_ast(old) == executable_ast(new)
    paths = [
        'policy-engine/src/polisyos/foundry/methods/backends/dispatch.py',
        'policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py',
        'policy-engine/tests/unit/foundry/methods/catalog/mechanism/test_families.py',
        'policy-engine/tests/unit/foundry/mechanisms/test_mechanism_design.py',
        'policy-engine/tests/unit/foundry/contracts/test_layout.py',
        'policy-engine/tests/unit/foundry/compile/test_trinity_compiler.py',
        'policy-engine/docs/reference/foundry/state.md',
        'policy-engine/src/polisyos/ir/kernel/slots.py',
        'policy-engine/src/polisyos/foundry/contracts/state.py',
        'policy-engine/src/polisyos/foundry/execute/executor.py',
        'policy-engine/mkdocs.yml', 'policy-engine/architecture/tooling/mkdocs/generated.yml',
        'policy-engine/pyproject.toml', 'policy-engine/uv.lock',
    ]
    inputs = []
    for path in paths:
        base = MONITOR if path.endswith('backends/dispatch.py') else SCIENCE
        left, right = source(base, path), source(sha, path)
        assert left == right, path
        inputs.append({'path': path, 'source_sha': base, 'candidate_sha': sha, 'bytes': len(right), 'sha256': digest(right), 'byte_equivalent': True})
    delta = subprocess.check_output(['git', 'diff', '--name-only', SCIENCE, sha], cwd=ROOT, text=True).splitlines()
    assert set(delta) == {PATH, 'policy-engine/src/polisyos/foundry/methods/lifecycle/README.md'}, delta
    report = {
        'candidate_sha': sha, 'scientific_source_sha': SCIENCE, 'monitor_source_sha': MONITOR,
        'doc_only_changed_paths': delta,
        'monitor_raw_source_hashes': {MONITOR: digest(old), sha: digest(new)},
        'executable_ast_without_docstrings_sha256': digest(executable_ast(new)),
        'executable_ast_equal': True, 'unchanged_scientific_and_docs_inputs': inputs,
        'scope': 'No numerical replay; executable monitor AST and exact native/docs consumer inputs unchanged after Args/Returns and README wording companion.'
    }
    (SCRATCH / 'monitor-doc-equivalence.json').write_text(json.dumps(report, indent=2) + '\n')
    python_paths = [
        'src/polisyos/foundry/methods/lifecycle/output_monitor.py',
        'tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py',
        'tests/unit/foundry/mechanisms/test_mechanism_design.py',
    ]
    commands = {
        'ruff': [PYTHON, '-m', 'ruff', 'check', *python_paths],
        'format': [PYTHON, '-m', 'ruff', 'format', '--check', *python_paths],
        'diff': ['git', 'diff', '--check', SCIENCE, sha],
    }
    checks = []
    for name, argv in commands.items():
        start = time.monotonic()
        run = subprocess.run(argv, cwd=ROOT / 'policy-engine', capture_output=True)
        out = SCRATCH / f'monitor-doc-{name}.stdout.txt'
        err = SCRATCH / f'monitor-doc-{name}.stderr.txt'
        out.write_bytes(run.stdout); err.write_bytes(run.stderr)
        checks.append({'name': name, 'command': ' '.join(argv), 'target_sha': sha, 'environment': {'interpreter': PYTHON, 'shared_environment_read_only': True},
                       'input_closure': 'Only final owned changed Python/doc companion and exact source Git diff.', 'outcome': 'PASS' if run.returncode == 0 else 'FAIL',
                       'exit_code': run.returncode, 'wall_seconds': time.monotonic() - start, 'output': str(out), 'stderr': str(err)})
    assert all(c['outcome'] == 'PASS' for c in checks), checks
    (SCRATCH / 'monitor-doc-quality.json').write_text(json.dumps({'source': sha, 'checks': checks}, indent=2) + '\n')
    print(json.dumps({'candidate_sha': sha, 'executable_ast_equal': True, 'unchanged_inputs': len(inputs), 'quality': [c['outcome'] for c in checks]}, indent=2))


if __name__ == '__main__':
    main()
