"""Reconcile every reported F1 test identity against the independent full AST population."""
import ast
import hashlib
import json
import re
from pathlib import Path

root = Path.cwd()
receipt_path = root / '_build/gy-gaps/f1/owner-closure-final-green.json'
receipt = json.loads(receipt_path.read_text())
module_path = 'tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py'
source = (root / module_path).read_bytes()
tree = ast.parse(source)
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name.startswith('test_layer3_workflow_failure_authority_')}
selected = {selector for selector in receipt['command'] if selector.startswith('tests/') and '::' in selector}
complete_selectors = {module_path + '::' + name for name in functions}
assert selected == complete_selectors


def statuses(result):
    found = {}
    for line in (result['stdout'] + result['stderr']).splitlines():
        match = re.fullmatch(r'(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (tests/.*)', line)
        if match:
            assert match[2] not in found
            found[match[2]] = match[1]
    return found

expected = set()
for name, definition in functions.items():
    selector = module_path + '::' + name
    parameters = []
    for decorator in definition.decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'parametrize':
            names = ast.literal_eval(decorator.args[0])
            names = names.split(',') if isinstance(names, str) else list(names)
            values = ast.literal_eval(decorator.args[1])
            assert not any(keyword.arg == 'ids' for keyword in decorator.keywords)
            identifiers = []
            for index, value in enumerate(values):
                row = [value] if len(names) == 1 else value
                assert len(row) == len(names)
                # Pytest's documented automatic IDs: literal primitive values;
                # argument name and row position for a structured value.
                identifiers.append('-'.join(str(item) if item is None or isinstance(item, (str, int, float, bool))
                                            else parameter + str(index)
                                            for parameter, item in zip(names, row, strict=True)))
            parameters.append(identifiers)
    assert len(parameters) <= 1
    expected.update(selector + '[' + identity + ']' for identity in parameters[0]) if parameters else expected.add(selector)
observed = statuses(receipt)
comparisons = {}
for name in ('owner-first-green.json', 'custody-review-red.json', 'owner-final-green.json'):
    previous_path = root / '_build/gy-gaps/f1' / name
    previous = statuses(json.loads(previous_path.read_text()))
    comparisons[name] = {
        'receipt_sha256': hashlib.sha256(previous_path.read_bytes()).hexdigest(),
        'lost_case_identities': sorted(set(previous) - set(observed)),
        'added_case_identities': sorted(set(observed) - set(previous)),
        'status_changes': {key: {'before': previous[key], 'after': observed[key]}
                           for key in sorted(set(previous) & set(observed)) if previous[key] != observed[key]},
    }
print(json.dumps({'source_path': module_path, 'source_sha256': hashlib.sha256(source).hexdigest(),
                  'complete_module_function_denominator': len(functions),
                  'selected_function_count': len(selected),
                  'expected_ast_identity_count': len(expected),
                  'observed_reported_identity_count': len(observed),
                  'missing': sorted(expected - set(observed)), 'unexpected': sorted(set(observed) - expected),
                  'complete_current_statuses': observed, 'comparisons': comparisons}, sort_keys=True))
assert receipt['returncode'] == 0 and not receipt['timed_out']
assert expected == set(observed) and all(status == 'PASSED' for status in observed.values())
assert all(not comparison['lost_case_identities'] for comparison in comparisons.values())
