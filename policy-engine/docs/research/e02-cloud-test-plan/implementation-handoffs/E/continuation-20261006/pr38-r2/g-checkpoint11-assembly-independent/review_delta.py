"""Independent read-only G11 delta joins and current plan preparation, no replay."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import platform
import runpy
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('/workspace/e02-E-continuation-20261006')
OUT = Path(__file__).resolve().parent
E = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/'
RESEARCH = 'policy-engine/docs/research/e02-cloud-test-plan/'
BASE = '94d3e6ee67b70a5ef4f71e529275aa7db0fddcde'
DOC = 'c311546deb347c185b30a2652c2ee9a5e1535e95'
G = '127dc7ab8365d29eb656fe32c0c894f6cc971286'
NOW = 'a9f78817c873be5b35a08155f2593b229d9fdbb6'
TREE = 'c02e043c3e1c8222c28aa71187fa8db4e2fdeea7'
MAIN = '198076863e143dea9f89f02734b13d50dae3eed5'
A = '577521c6651bba048d6bdfdc13f36a383c8146c6'
TEST = 'policy-engine/tests/unit/remediation/test_req_01_installed.py'
cache = {}


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def read(path, ref=NOW):
    key = (ref, path)
    if key not in cache:
        cache[key] = git('show', ref + ':' + path)
    return cache[key]


def sha(value):
    return hashlib.sha256(value).hexdigest()


def asset(path, ref=NOW):
    b = read(path, ref)
    return {'path': path, 'bytes': len(b), 'sha256': sha(b), 'git_blob': git('rev-parse', ref + ':' + path).decode().strip()}


def load(path):
    return json.loads(read(path))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def tree(ref):
    output = {}
    for row in git('ls-tree', '-rz', ref).split(b'\0'):
        if row:
            meta, path = row.split(b'\t', 1)
            mode, kind, blob = meta.decode().split()
            assert kind == 'blob'
            output[path.decode()] = (mode, blob)
    return output


CURRENT, PREVIOUS = tree(NOW), tree(BASE)


def snapshot():
    digest, total = hashlib.sha256(), 0
    for path, (mode, blob) in sorted(CURRENT.items()):
        f = ROOT / path
        b = os.readlink(f).encode() if mode == '120000' else f.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest() == blob
        total += len(b)
        digest.update(path.encode() + b'\0' + str(len(b)).encode() + b'\0' + hashlib.sha256(b).digest())
    config = (ROOT / git('rev-parse', '--git-path', 'config').decode().strip()).read_bytes()
    return {'head': git('rev-parse', 'HEAD').decode().strip(), 'tree': git('rev-parse', 'HEAD^{tree}').decode().strip(), 'tracked_dirty': git('status', '--porcelain=v1', '--untracked-files=no').decode(), 'tracked_paths': len(CURRENT), 'tracked_bytes': total, 'frame_format': 'sorted UTF8path NUL decimalBytes NUL rawSHA256digest', 'framed_sha256': digest.hexdigest(), 'private_Git_config': {'bytes': len(config), 'sha256': sha(config), 'copied': False}}


before = snapshot()
assert before['head'] == NOW and before['tree'] == TREE and not before['tracked_dirty']
doc_paths = git('diff', '--name-only', BASE, DOC).decode().splitlines()
g_paths = git('diff', '--name-only', DOC, NOW).decode().splitlines()
assert len(doc_paths) == 16 and all(x.startswith(E) for x in doc_paths)
assert len(g_paths) == 68
assert [x for x in g_paths if not x.startswith(RESEARCH)] == [TEST]
assert read(TEST) == read(TEST, A) == read(TEST, '5650b7aed7991606d62cd8510b377698a778ce39')
assert all(read(path) == read(path, G) for path in g_paths)
proof_prefixes = ('policy-engine/src/', 'policy-engine/architecture/', 'policy-engine/schemas/', E + 'wave-controls/')
proof_paths = sorted(path for path in CURRENT if path.startswith(proof_prefixes))
assert all(CURRENT[path] == PREVIOUS[path] for path in proof_paths)
assert all(path in CURRENT for path in PREVIOUS if path.startswith(proof_prefixes))
test_changes = [x for x in git('diff', '--name-only', BASE, NOW, '--', 'policy-engine/tests').decode().splitlines()]
assert test_changes == [TEST]

prior_primary = E + 'final-assembly-delta-independent/independent-assembly-review-94d3.json'
assert sha(read(prior_primary)) == 'bc87f3d175bee92a534cd700c6f0b4b9578ad9a474e67b8e37073f6b1d494aa0'
prior = load(prior_primary)
assert prior['candidate'] == BASE and prior['disposition'].startswith('GO')
portable = load(E + 'final-assembly-delta-independent/portable-copy-index.json')
for rec in portable['records']:
    b = read(rec['copied_path'])
    assert len(b) == rec['bytes'] and sha(b) == rec['sha256'] and (ROOT / rec['copied_path']).read_bytes() == b
assert portable['complete'] is True

prompt = RESEARCH + 'execution-prompts/continuation-2026-10-06/E-resume-after-pr38.md'
text = read(prompt).decode()
assert 'до stochastic draws и stochastic evaluator callbacks' in text
assert 'Детерминированные nominal/gradient diagnostics допускаются как явно limited candidate' in text
assert 'Если конкретный API обещает pre-callback refusal' in text
welfare_review_path = E + 'independent-welfare/welfare-independent-review-884681.json'
welfare = load(welfare_review_path)
law = welfare['missing_joint_law']
assert law['evaluator_calls'] == 6 and law['nominal_calls'] == 1 and law['gradient_base_calls'] == 1 and law['finite_difference_calls'] == 4
assert law['stochastic_attempts'] == 0 and law['unattempted'] == 128 and law['gate_eligible'] is False
assert read(welfare_review_path) == read(welfare_review_path, BASE)
assert read('policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py') == read('policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py', BASE)

# Read actual G's completed source-bound selector evidence; never execute the wheel test.
run_path = RESEARCH + 'integration/checks/2026-10-06-sixth-wave/A-compiler/replay-4/run-result.json'
run = load(run_path)
assert run['candidate_commit'] == A and run['candidate_tree'] == git('rev-parse', A + '^{tree}').decode().strip()
assert run['test_source_sha256'] == sha(read(TEST)) and run['outcome'] == 'PASS'
base_output = RESEARCH + 'integration/checks/2026-10-06-sixth-wave/A-compiler/replay-4/'
for name, bytes_field, hash_field in [('pytest.stdout.txt', 'pytest_stdout_bytes', 'pytest_stdout_sha256'), ('pytest.stderr.txt', 'pytest_stderr_bytes', 'pytest_stderr_sha256')]:
    b = read(base_output + name)
    assert len(b) == run[bytes_field] and sha(b) == run[hash_field]
xml = read(base_output + 'installed-wheel.junit.xml')
assert len(xml) == run['junit']['bytes'] and sha(xml) == run['junit']['sha256']
cases = list(ET.fromstring(xml).iter('testcase'))
assert len(cases) == 1 and not any(list(c.iter('failure')) or list(c.iter('error')) or list(c.iter('skipped')) for c in cases)
assert cases[0].attrib['name'] == 'test_installed_wheel_keeps_active_compiler_and_retires_legacy_helpers'
wheel = load(base_output + 'wheel-source-reconciliation.json')
assert wheel['candidate'] == A and wheel['python_entry_denominator'] == wheel['matched_candidate_git_blobs'] == 3143 and wheel['unmatched_python_paths'] == []

# Prepare on this actual SHA, without materializing output or invoking main/execute.
ns = runpy.run_path(str(ROOT / (E + 'wave-controls/plan_wave.py')), run_name='readonly_G11_assembly')
planning_output = OUT / 'prepared-wave-a9f78817'
assert not planning_output.exists() and not planning_output.is_symlink()
plan = ns['prepare'](argparse.Namespace(repo=ROOT, candidate=NOW, comparison_base=MAIN, output_root=planning_output, no_owner_packets=False))
assert plan['execution_state'] == 'NOT_RUN' and not plan['missing_required_paths']
assert all(x['in_candidate_history'] for x in plan['required_upstream'].values())
assert not planning_output.exists()
selected = {path for paths in plan['groups'].values() for path in paths}
assert TEST not in selected and TEST in plan['changed_foreign_tests_outside_E_wave'] and ns['family_for'](TEST) is None
assert len(selected) == plan['native_test_path_count']
actual_lint = [x.removeprefix('policy-engine/') for x in git('diff', '--name-only', '--diff-filter=ACMR', MAIN, NOW, '--', 'policy-engine').decode().splitlines() if x.endswith('.py') and x in CURRENT]
assert actual_lint == plan['changed_python_lint_paths'] and TEST.removeprefix('policy-engine/') in actual_lint
prior_plan = load(E + 'final-assembly-delta-independent/prepared-plan-94d3.json')
assert selected == {path for paths in prior_plan['groups'].values() for path in paths}
new_lint = sorted(set(actual_lint) - set(prior_plan['changed_python_lint_paths']))
test_ast = ast.parse(read(TEST))
test_functions = [n.name for n in test_ast.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
assert len(test_functions) == 1
exclusion_reason = 'A-owned REQ-01 installed-wheel/compiler test is outside declared E seven-family numeric wave. It creates/builds/installs a wheel and fresh environment; G has bounded exact A-candidate selector evidence, not composed E/G-wheel acceptance. Keep selected in complete changed-Python Ruff/format input and staged full-umbrella selector if reached; no duplicate standalone wheel build in this assembly review.'

negatives = []
def reject(name, check):
    try:
        check()
    except AssertionError:
        negatives.append({'control': name, 'outcome': 'REJECTED'})
    else:
        raise AssertionError(('not_discriminating', name))

def verify_test_metadata(rec):
    assert rec['candidate_commit'] == A and rec['test_source_sha256'] == sha(read(TEST))
    assert rec['junit']['bytes'] == len(xml) and rec['junit']['sha256'] == sha(xml)
for key, value in [('candidate_commit', NOW), ('test_source_sha256', '0' * 64)]:
    bad = copy.deepcopy(run); bad[key] = value
    reject('G_installed_' + key, lambda bad=bad: verify_test_metadata(bad))
bad = copy.deepcopy(run); bad['junit']['bytes'] += 1
reject('G_installed_corrupt_JUnit_bytes', lambda: verify_test_metadata(bad))
def verify_plan_metadata(rec):
    assert rec['candidate_sha'] == NOW and rec['candidate_tree_sha'] == TREE and rec['execution_state'] == 'NOT_RUN'
    assert rec['native_test_path_count'] == len(selected) and rec['changed_python_lint_paths'] == actual_lint
for key, value in [('candidate_sha', BASE), ('native_test_path_count', len(selected) + 1), ('execution_state', 'PASS')]:
    bad = copy.deepcopy(plan); bad[key] = value
    reject('prepared_plan_' + key, lambda bad=bad: verify_plan_metadata(bad))
bad = copy.deepcopy(plan); bad['changed_python_lint_paths'].remove(TEST.removeprefix('policy-engine/'))
reject('installed_native_test_omitted_from_lint', lambda: verify_plan_metadata(bad))
def verify_law_metadata(rec):
    assert rec['evaluator_calls'] == law['evaluator_calls'] and rec['stochastic_attempts'] == 0 and rec['gate_eligible'] is False
for key, value in [('evaluator_calls', 0), ('stochastic_attempts', 6), ('gate_eligible', True)]:
    bad = dict(law, **{key: value})
    reject('amended_law_' + key, lambda bad=bad: verify_law_metadata(bad))

assert git('rev-parse', 'origin/main').decode().strip() == MAIN
for ref in [MAIN, G, DOC, '1ddcd7b3905e52c0d19db091823a64830139fa64']:
    assert subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', ref, NOW], check=False).returncode == 0
after = snapshot()
assert after == before
footprint = [dict(asset(path), part='root16doc_companion' if path in doc_paths else 'G11_A_installed_native_test' if path == TEST else 'G11_docs_evidence', exact_G127=path in g_paths) for path in sorted(set(doc_paths + g_paths))]
write('complete-84-path-footprint.json', footprint)
write('prepared-plan-a9f78817.json', plan)
write('negative-controls.json', negatives)
review = {
    'schema': 'e02.E.independent-G11-assembly-delta.v1', 'reviewer': '/root/cal_uq_r3; read-only joins, no own CAL mechanism approval',
    'disposition': 'GO_bounded_source_readiness_for_corrected_freeze', 'base': BASE, 'doc_companion': DOC, 'G_checkpoint': G, 'candidate': NOW, 'tree': TREE,
    'source_before': before, 'source_after': after, 'immutable': before == after,
    'footprint': {'full_paths': len(footprint), 'doc16': len(doc_paths), 'G68': len(g_paths), 'production_source_changed': 0, 'harness_changed': 0, 'E_owned_native_tests_changed': 0, 'A_installed_native_tests_added': 1, 'new_G_evidence_docs': 67, 'all_G68_exact_fetched_G_blobs': True},
    'unchanged_source_reuse': {'exact_production_architecture_schema_harness_paths': len(proof_paths), 'all_complete_Git_blobs_equal94d': True, 'assembly_primary': asset(prior_primary), 'copy_records_verified': len(portable['records']), 'CAL_independent_mechanism_basis': 'Unchanged DoE independent CAL receipt; no self-review or numerical result repeated', 'prior_global_reds': 'Actual5e1086PASS/3FAIL/351ERROR and P41not_established remain distinct'},
    'amendment': {'full_prompt': asset(prompt), 'source_math_unchanged': True, 'six_deterministic_diagnostics': law, 'prior_welfare_review': asset(welfare_review_path), 'basis': 'Latest tracked instruction admits deterministic nominal/gradient limited candidate with zero stochastic attempts, withheld intervals/authority. Individual malformed/unsupported law and APIs with strict pre-callback admission retain their stronger existing criterion; no globalcallback0 invention.', 'new_numeric_execution_claimed': False, 'semantic_or_authority_promotion': False},
    'installed_REQ01': {'test': asset(TEST), 'owner': 'A; G checkpoint11 acceptance', 'AST_test_function_count': len(test_functions), 'selected_in_E_numeric_wave': False, 'exclusion_reason': exclusion_reason, 'selected_in_changed_Python_lint': True, 'G_exact_A_selector_evidence': asset(run_path), 'G_actual_JUnit': {'tests': len(cases), 'PASS': 1, 'FAIL': 0, 'ERROR': 0, 'SKIP': 0, 'candidate': A}, 'wheel_source_evidence': wheel, 'bounded_scope': 'RecordingResolver fixture; production resolver/source admission and composed E/G wheel acceptance UNRUN', 'new_wheel_build_or_test_run': False},
    'prepared_not_executed': {'native_files': plan['native_test_path_count'], 'A_owner_packet_files': len(plan['owner_packet_extra_inputs']), 'total_numeric_file_inputs': plan['test_input_path_count_including_owner_packets'], 'lint_Python_paths': len(actual_lint), 'new_lint_paths_vs94d': new_lint, 'all_native_and_A_inputs': 'prepared-plan-a9f78817.json', 'group_path_counts': plan['group_path_counts'], 'changed_foreign_tests_outside_E_wave': plan['changed_foreign_tests_outside_E_wave'], 'runtime_JUnit_cases': 'UNRUN', 'numerical_and_global_gates': 'UNRUN', 'planning_output_directory_materialized': False},
    'negative_controls': negatives,
    'limitations_and_next_owner': {'root': 'Append exact moderate review; freeze distinct clean source and run corrected common wave once with freshly recomputed input denominator', 'independent_audit': 'Recompute actual corrected-wave outputs; no source edits or test launches during run', 'G_A': 'A installed selector belongs to exactA577candidate; composed wheel/full REQ01/source resolver remain separate checks. G integration acceptance/finding closure/production local source law remain separate.', 'other_owners': 'A default ForecastOwner/verifier/fresh served consumer; D Search codec/ranking; Core/IR/execute admissions and B201/B202 appointment/ratification unresolved'},
    'ledger': {'held': ['B194','B197','B201','B202'], 'B198': 'closed regression preserved', 'partial_open': 'preserved; no automatic proposal acceptance'}, 'finding_closure': False,
    'command': {'argv': [sys.executable, str(Path(__file__).resolve())], 'cwd': str(ROOT), 'exit_code': 0, 'stdout': 'review.stdout.txt', 'stderr': 'review.stderr.txt'},
    'environment': {'python': sys.executable, 'version': sys.version, 'platform': platform.platform(), 'UV_NO_SYNC': os.getenv('UV_NO_SYNC'), 'PYTHONDONTWRITEBYTECODE': os.getenv('PYTHONDONTWRITEBYTECODE'), 'CPU_worker_caps': {k: os.getenv(k) for k in ns['CAP_VARIABLES']}},
    'cleanup': {'performed': 'none; native Trash unavailable', 'permanent_delete': False, 'unique_deciding_outputs_preserved': True, 'repeatable_future_planning_path': str(planning_output), 'planning_path_exists': False},
}
write('independent-G11-assembly-review-a9f78817.json', review)
print(json.dumps({'disposition': review['disposition'], 'candidate': NOW, 'tree': TREE, 'footprint': review['footprint'], 'native_files': plan['native_test_path_count'], 'A_packets': len(plan['owner_packet_extra_inputs']), 'lint_Python_paths': len(actual_lint), 'new_lint_paths_vs94d': new_lint, 'negatives': len(negatives), 'source_immutable': before == after}, indent=2))
