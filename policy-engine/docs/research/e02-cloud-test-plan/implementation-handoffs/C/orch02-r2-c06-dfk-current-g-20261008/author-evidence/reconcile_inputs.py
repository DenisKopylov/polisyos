"""Retain complete Git object denominators without copying source snapshots."""
from __future__ import annotations
import ast
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path('/workspace/orch02-r2-c06-dfk-g')
OUT = Path('/workspace/orch02-r2/c06-dfk')
G = 'dee58973f7673299070b7c7374f419b0adb8175c'
OLD = 'cbbfffd367fe283813a8177575d26c0ede8d20c4'
BASE = 'a13f6c1acfe15a6750d71c6e86521f119d794def'
PUBLISHED = 'e4bd1527c941ff880a5d34898c57428c7be4b1cc'
TREE = subprocess.check_output(['git', 'write-tree'], cwd=ROOT).decode().strip()

def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=ROOT)

def inventory(ref: str) -> list[dict[str, str]]:
    result = []
    for entry in git('ls-tree', '-rz', ref).split(b'\0'):
        if entry:
            meta, name = entry.split(b'\t', 1)
            mode, kind, blob = meta.decode().split()
            result.append(dict(path=name.decode(), mode=mode, kind=kind, git_object=blob))
    return result

def compressed(name: str, value: object) -> dict[str, object]:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    encoded = gzip.compress(raw, mtime=0)
    assert gzip.decompress(encoded) == raw
    (OUT/name).write_bytes(encoded)
    return dict(path=name, bytes=len(encoded), sha256=hashlib.sha256(encoded).hexdigest(),
                decoded_bytes=len(raw), decoded_sha256=hashlib.sha256(raw).hexdigest())

snapshots = {ref: inventory(ref) for ref in (G, BASE, OLD, PUBLISHED, TREE)}
denominator = compressed('full-git-input-denominator.json.gz', snapshots)
graph = git('rev-list', '--parents', G, BASE, OLD, PUBLISHED).decode().splitlines()
dag = compressed('complete-input-dag.json.gz', graph)
g_paths = {row['path']: row for row in snapshots[G]}
current_paths = {row['path']: row for row in snapshots[TREE]}
changed = sorted(path for path in set(g_paths)|set(current_paths)
                 if g_paths.get(path) != current_paths.get(path))
assert changed == [
    'policy-engine/release-fragments/unreleased/2026-10-08-orch02-r2-c06-dfk-census.toml',
    'policy-engine/tests/unit/remediation/test_dfk_01.py',
    'policy-engine/tools/quality/validation/schema_fqn_census.py']
test_path = changed[1]
before = git('show', f'{G}:{test_path}').decode()
after = git('show', f'{TREE}:{test_path}').decode()
before_functions = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(before).body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
after_functions = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(after).body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
assert all(after_functions[name] == value for name, value in before_functions.items())
g_tool_python = [p for p in g_paths if p.startswith('policy-engine/tools/') and p.endswith('.py')]
ast_candidates, parse_errors = [], []
for path in g_tool_python:
    try:
        tree = ast.parse(git('show', f'{G}:{path}').decode(), filename=path)
        candidates = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and any(token in node.name.lower() for token in ('census', 'git_status', 'porcelain'))]
        if candidates:
            ast_candidates.append(dict(path=path, definitions=candidates, git_blob=g_paths[path]['git_object']))
    except (SyntaxError, UnicodeDecodeError) as exc:
        parse_errors.append(dict(path=path, error=str(exc)))

dependency_paths = [
    'tools/registry.py', 'tools/cli.py', 'tools/lib/runner.py', 'tools/lib/fs.py',
    'tools/lib/output.py', 'tools/lib/preflight.py', 'tools/lib/timing.py', 'tools/lib/imports.py',
    'pyproject.toml', 'hatch.toml', 'uv.lock', 'tests/conftest.py',
    'src/polisyos/runtime/quality/production_invocation.py',
    'tools/quality/validation/check_production_invocation.py',
    'docs/how-to/author-measurement-instruments.md', 'tools/AGENTS.md',
    'ops/release/release-fragment-policy.toml', 'docs/reference/tools.md',
    'tools/quality/validation/README.md',
    'src/polisyos/data_forge/kernel/pipeline/schemas/README.md']
dependencies = []
for suffix in dependency_paths:
    path = 'policy-engine/'+suffix
    references = {}
    for ref, rows in snapshots.items():
        row = next((r for r in rows if r['path'] == path), None)
        references[ref] = row
    dependencies.append(dict(path=path, references=references))
result = dict(
    schema='policyos.orch02.r2.c06.dfk.source-reconciliation.v1', base_G=G,
    candidate_tree=TREE, complete_git_input_denominator=denominator, complete_ancestor_dag=dag,
    changed_paths=changed, all_other_G_entries_preserved=True,
    preserved_G_test_functions=sorted(before_functions), preserved_function_ast=True,
    full_G_tools_python_AST_denominator=len(g_tool_python), AST_candidates=ast_candidates,
    AST_parse_errors=parse_errors, explicit_dependencies=dependencies,
    adoption=dict(previous_own_source=OLD, G_path_history=[],
                  interpretation='G has no ancestry entry for the tool; capability absence is not retirement authority.',
                  non_test_caller='tools.cli -> tools.lib.runner.invoke_tool_main -> schema_fqn_census.main',
                  command='polisyos-tools validation schema-fqn-census --repo-root PATH',
                  lifecycle='ACTIVE by existing AST autodiscovery; G public lifecycle adjudication not admitted.',
                  retirement='All current G compatibility-pending production surfaces and tests preserved.'),
    generated_companion_owner='G/team-devx: render tools registry reference docs and adjudicate public inventory/lifecycle',
    current_source_acceptance='not_admitted_by_G', formal_closure_ids=[])
(OUT/'source-reconciliation.json').write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n')
print(json.dumps(dict(candidate_tree=TREE, changed_paths=changed, preserved_G_test_functions=len(before_functions),
                     complete_G_entries=len(snapshots[G]), full_G_tools_python_AST_denominator=len(g_tool_python),
                     AST_candidates=len(ast_candidates), AST_parse_errors=len(parse_errors), DAG_commits=len(graph))))
