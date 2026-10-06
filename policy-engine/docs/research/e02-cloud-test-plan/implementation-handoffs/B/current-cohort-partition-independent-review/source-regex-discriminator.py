"""Compare AST string literals with stdlib regex; no pytest/parser invocation."""
import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source-sha', required=True)
args = parser.parse_args()
repo = Path('/workspace/e02-B-current-runtime')
relative = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-cohort-result-partition.py'
source = subprocess.check_output(['git', 'show', args.source_sha + ':' + relative], cwd=repo)
pytest_path = Path('/workspace/polisyos/policy-engine/.venv/lib/python3.14/site-packages/_pytest/junitxml.py')
pytest_source = pytest_path.read_bytes()

def literal(data, name, variable):
    tree = ast.parse(data)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    assignment = next(n for n in function.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets))
    return ast.literal_eval(assignment.value)

native = literal(pytest_source, 'bin_xml_escape', 'illegal_xml_re')
interpreted = literal(source, '_xml_name', 'pattern')

def escape(pattern, value):
    return re.sub(pattern, lambda m: f'#x{ord(m[0]):02X}' if ord(m[0]) <= 255 else f'#x{ord(m[0]):04X}', value)

cases = []
for value in ['test_case[ascii]', 'test_case[\x07]', 'test_case[😀]', 'test_case[𝄞]']:
    expected, actual = escape(native, value), escape(interpreted, value)
    cases.append({'value': value, 'pytest9_literal_regexp_result': expected, 'partition_literal_regexp_result': actual, 'equal': expected == actual})
print(json.dumps({'kind': 'SOURCE_LITERAL_DISCRIMINATOR_ONLY', 'product_tests_collection_or_actual_partition_executed': False, 'source_sha': args.source_sha, 'source_tree': subprocess.check_output(['git', 'rev-parse', args.source_sha + '^{tree}'], cwd=repo, text=True).strip(), 'parser': {'path': relative, 'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()}, 'pytest_source': {'path': str(pytest_path), 'bytes': len(pytest_source), 'sha256': hashlib.sha256(pytest_source).hexdigest()}, 'patterns_identical': native == interpreted, 'native_pattern_repr': repr(native), 'parser_pattern_repr': repr(interpreted), 'cases': cases, 'equal_cases': sum(c['equal'] for c in cases), 'different_cases': sum(not c['equal'] for c in cases), 'scope': 'A definite pinned native9 source forward-map difference, not an actual rootwave affected-case count or parser acceptance run.'}, ensure_ascii=False, indent=2))
