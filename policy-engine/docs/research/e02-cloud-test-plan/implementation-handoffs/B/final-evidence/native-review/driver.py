"""Read a terminal native cohort; never execute pytest or alter its source tree."""

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--aborted', type=Path, required=True)
    parser.add_argument('--cohort', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    reads, issues, unresolved = [], [], []

    def read(path, interpretation):
        path = Path(path)
        try:
            data = path.read_bytes()
        except OSError as error:
            reads.append({'path': str(path), 'outcome': 'ERROR',
                          'interpretation': interpretation, 'error': repr(error)})
            raise
        reads.append({'path': str(path), 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest(),
                      'outcome': 'READ', 'interpretation': interpretation})
        return data

    def git(*argv):
        return subprocess.check_output(['git', '-C', str(args.repo), *argv], text=True).strip()

    def snapshot():
        return {'sha': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'),
                'branch': git('symbolic-ref', 'HEAD'), 'status': git('status', '--porcelain')}

    def require(condition, message):
        if not condition:
            issues.append(message)

    before = snapshot()
    wrapper_raw = read(args.native / 'wrapper.json', 'Full terminal wrapper and source/input identities')
    wrapper = json.loads(wrapper_raw)
    require(bool(wrapper.get('finished_utc')), 'Terminal finished_utc missing')
    native_raw = read(args.native / 'native.txt', 'Full stdout: summaries, diagnostics and warning sections')
    junit_raw = read(args.native / 'cohort.xml', 'Complete XML tree; enumerate every testcase')
    cohort_raw = read(args.cohort, 'Complete cohort JSON; selected paths and declared retained_nonpass')
    cohort = json.loads(cohort_raw)
    for name, raw in [('native.txt', native_raw), ('cohort.xml', junit_raw)]:
        measured = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        require(wrapper['outputs'][name] == measured, f'{name} bytes differ from terminal wrapper')
    require(wrapper['input']['sha256'] == hashlib.sha256(cohort_raw).hexdigest(),
            'Current cohort input differs from bytes used to build actual pytest argv')
    require(wrapper['input']['bytes'] == len(cohort_raw), 'Cohort input byte length mismatch')
    paths = cohort['test_paths']
    require(len(paths) == len(set(paths)), 'Duplicate whole-file inputs')
    require(wrapper['whole_file_count'] == len(paths) == cohort['whole_file_count'],
            'Whole-file denominator mismatch')
    argv_paths = [v for v in wrapper['command_argv'] if v.startswith('tests/') and v.endswith('.py')]
    require(argv_paths == paths, 'Actual pytest argv test path list differs from cohort input')
    require(wrapper['command_argv'][0] == wrapper['interpreter']['executable'],
            'Actual child executable differs from package/module origin preflight executable')
    require(wrapper['source_before'] == wrapper['source_after'] == before,
            'Terminal source snapshots differ from current independently read source')
    require(before['sha'] == args.target == cohort['final_head'], 'Frozen SHA mismatch')
    require(before['tree'] == cohort['final_tree'], 'Frozen tree mismatch')
    require(not before['status'] and bool(before['branch']), 'Source is not clean and attached')
    require(wrapper['source_unchanged'], 'Wrapper source changed during native execution')

    prefix_map = {path[:-3].replace('/', '.'): path for path in paths}
    source_asts = {}
    for path in paths:
        actual = read(args.repo / 'policy-engine' / path,
                      'AST parse for source-bound xfail strictness; full file hash against frozen Git object')
        expected = subprocess.check_output(['git', '-C', str(args.repo), 'show',
                                           args.target + ':policy-engine/' + path])
        require(actual == expected, 'Selected test source differs from frozen Git object: ' + path)
        source_asts[path] = ast.parse(actual)

    def file_for_case(classname):
        matches = [prefix for prefix in prefix_map
                   if classname == prefix or classname.startswith(prefix + '.')]
        return prefix_map[max(matches, key=len)] if matches else None

    def strict_marker(path, name):
        function_name = name.split('[', 1)[0]
        matches = []
        for function in ast.walk(source_asts[path]):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) or function.name != function_name:
                continue
            for decorator in function.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'xfail':
                    strict = next((v.value.value for v in decorator.keywords
                                   if v.arg == 'strict' and isinstance(v.value, ast.Constant)), None)
                    reason = next((v.value.value for v in decorator.keywords
                                   if v.arg == 'reason' and isinstance(v.value, ast.Constant)), None)
                    matches.append({'line': decorator.lineno, 'strict_literal': strict, 'reason_literal': reason})
        return matches

    root = ET.fromstring(junit_raw)
    cases = list(root.iter('testcase'))
    counts = Counter()
    per_file = {path: Counter() for path in paths}
    nonpass = []
    for case in cases:
        file = file_for_case(case.get('classname', ''))
        require(file is not None, 'JUnit testcase could not be routed to an actual selected file: ' + str(case.attrib))
        status, detail = 'PASS', None
        for tag, outcome in [('error', 'ERROR'), ('failure', 'FAIL'), ('skipped', 'SKIP')]:
            element = case.find(tag)
            if element is not None:
                status = 'XFAIL' if tag == 'skipped' and element.get('type') == 'pytest.xfail' else outcome
                detail = {'attributes': dict(element.attrib), 'text': element.text or ''}
                break
        counts[status] += 1
        if file:
            per_file[file][status] += 1
        if status != 'PASS':
            record = {'file': file, 'classname': case.get('classname'), 'name': case.get('name'),
                      'status': status, 'detail': detail}
            record['matching_retained_declarations'] = [d for d in cohort['retained_nonpass']
                                                       if d['path'] == file and d['node'] == case.get('name').split('[', 1)[0]]
            if status == 'XFAIL' and file:
                record['source_xfail_markers'] = strict_marker(file, case.get('name'))
                record['strict_from_actual_source'] = any(x['strict_literal'] is True for x in record['source_xfail_markers'])
                if not record['strict_from_actual_source']:
                    unresolved.append({'class': 'xfail_strictness_not_established', 'case': record['name']})
            nonpass.append(record)
    suites = [dict(s.attrib) for s in root.iter('testsuite')]
    declared_total = sum(int(s['tests']) for s in suites)
    declared_failures = sum(int(s['failures']) for s in suites)
    declared_errors = sum(int(s['errors']) for s in suites)
    declared_skips = sum(int(s['skipped']) for s in suites)
    require(declared_total == len(cases) == sum(counts.values()), 'JUnit total testcase reconciliation failed')
    require(declared_failures == counts['FAIL'] and declared_errors == counts['ERROR'], 'JUnit failure/error attributes mismatch')
    require(declared_skips == counts['SKIP'] + counts['XFAIL'], 'JUnit skipped attribute reconciliation failed')

    stdout = native_raw.decode('utf-8')
    summary_lines = [line for line in stdout.splitlines()
                     if re.search(r'\bin [\d.]+s\b', line) and re.search(r'\d+ (passed|failed|errors?|xfailed)', line)]
    require(len(summary_lines) == 1, 'Final complete stdout summary is ambiguous or missing')
    summary_line = summary_lines[-1] if summary_lines else ''
    summary = {kind.rstrip('s') if kind in ['warnings', 'errors'] else kind: int(number)
               for number, kind in re.findall(r'(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected)', summary_line)}
    for key, outcome in [('passed', 'PASS'), ('failed', 'FAIL'), ('error', 'ERROR'), ('skipped', 'SKIP'), ('xfailed', 'XFAIL')]:
        require(summary.get(key, 0) == counts[outcome], 'stdout/JUnit mismatch: ' + key)
    require(summary.get('xpassed', 0) == 0, 'Non-strict XPASS needs explicit testcase reconciliation')
    strict_xpass = [r for r in nonpass if r['status'] == 'FAIL' and '[XPASS(strict)]' in json.dumps(r['detail'])]
    warning_section_match = re.search(r'^=+ warnings summary =+\n(.*?)(?=^-- Docs:|^=+ short test summary|\Z)', stdout, re.M | re.S)
    warning_section = warning_section_match.group(1) if warning_section_match else ''
    warning_counts = Counter()
    for block in re.split(r'\n\s*\n', warning_section.strip()):
        category = re.search(r'\b([A-Za-z_][A-Za-z_0-9]*Warning):', block)
        if not category:
            continue
        header_lines = [line for line in block.splitlines() if line.startswith('tests/')]
        number = sum(int(m.group(1)) if (m := re.search(r': (\d+) warnings?$', line)) else 1
                     for line in header_lines)
        warning_counts[category.group(1)] += number
    require(sum(warning_counts.values()) == summary.get('warning', 0), 'Warning section/terminal count mismatch')

    changed_paths = git('diff', '--name-only', wrapper['source_base'], args.target,
                        '--', 'policy-engine/src').splitlines()
    changed_python = [path for path in changed_paths if path.endswith('.py')]
    expected_modules = {path.split('/src/', 1)[1][:-3].replace('/', '.').removesuffix('.__init__'): path
                        for path in changed_python}
    origins = wrapper['interpreter']['changed_source_origins']
    require(set(expected_modules) == set(origins), 'Complete changed-module denominator differs from origin records')
    origin_review = []
    for module, rel in expected_modules.items():
        record = origins[module]
        origin = Path(record['origin'])
        expected = args.repo / rel
        actual = read(origin, 'Actual production origin file bytes bound to frozen Git object')
        git_bytes = subprocess.check_output(['git', '-C', str(args.repo), 'show', args.target + ':' + rel])
        ok = origin.resolve() == expected.resolve() and origin.is_relative_to(args.repo) and actual == git_bytes
        ok = ok and hashlib.sha256(actual).hexdigest() == record['sha256'] and record['matches_expected']
        require(ok, 'Production origin/content mismatch: ' + module)
        origin_review.append({'module': module, 'path': str(origin), 'sha256': hashlib.sha256(actual).hexdigest(),
                              'matches_frozen_git_and_acceptance_path': ok})

    aborted_wrapper_raw = read(args.aborted / 'wrapper.json', 'Full original harness wrapper; qualify its exit-only FAIL')
    aborted_wrapper = json.loads(aborted_wrapper_raw)
    aborted_stdout = read(args.aborted / 'native.txt', 'Original no-pytest precollection diagnostic')
    aborted_qualification = {'recorded_exit': aborted_wrapper['exit_code'], 'recorded_outcome': aborted_wrapper['outcome'],
                             'reviewed_outcome': 'UNRUN', 'product_failure': 'not_established',
                             'test_case_denominator': 0, 'diagnostic': aborted_stdout.decode('utf-8'),
                             'actual_child_executable': aborted_wrapper['command_argv'][0],
                             'identity_preflight_executable': aborted_wrapper['interpreter']['executable'],
                             'reason': 'Resolved venv symlink launched base Python without pytest and stopped before collection. No product case was executed.'}
    require(b'No module named pytest' in aborted_stdout and not (args.aborted / 'cohort.xml').exists(),
            'Original harness UNRUN qualification premise differs from actual bytes')
    require(aborted_wrapper['outputs']['native.txt'] == {'bytes': len(aborted_stdout), 'sha256': hashlib.sha256(aborted_stdout).hexdigest()},
            'Aborted native bytes mismatch')
    after = snapshot()
    require(before == after, 'Source changed during independent review')
    unadvertised = [r for r in nonpass if not r['matching_retained_declarations']]
    retained_source_reviews = []
    for declaration in cohort['retained_nonpass']:
        path, ref = declaration['existing_log'].split('@')
        data = subprocess.check_output(['git', '-C', str(args.repo), 'show', ref + ':' + path])
        reads.append({'git_object': path + '@' + ref, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest(), 'outcome': 'READ',
                      'interpretation': 'Complete prior deciding log; match declared node only, historical counts unused'})
        require(declaration['node'].encode() in data and b'FAILED' in data,
                'Declared retained nonpass source log does not contain its actual failure: ' + declaration['node'])
        wave = next((w for w in cohort['native_waves']
                     if declaration['path'] in w['whole_test_files'] and w['receipt_path'].endswith('.json')), None)
        owner = None
        if wave:
            receipt_path, receipt_ref = wave['receipt_path'], wave['family_head']
            owner_raw = subprocess.check_output(['git', '-C', str(args.repo), 'show', receipt_ref + ':' + receipt_path])
            owner_data = json.loads(owner_raw)
            reads.append({'git_object': receipt_path + '@' + receipt_ref, 'bytes': len(owner_raw),
                          'sha256': hashlib.sha256(owner_raw).hexdigest(), 'outcome': 'READ',
                          'interpretation': 'Owner receipt limitations and exact declared retained scope; historical counts unused'})
            owner = {'reference': receipt_path + '@' + receipt_ref,
                     'sha256': hashlib.sha256(owner_raw).hexdigest(),
                     'limitations': owner_data.get('limitations_and_next_owner', owner_data.get('limitations', []))}
        retained_source_reviews.append({'declaration': declaration,
                                        'existing_log_sha256': hashlib.sha256(data).hexdigest(),
                                        'existing_log_bytes': len(data), 'prior_failure_node_observed': True,
                                        'owner_receipt': owner,
                                        'classification': 'Advertised retained nonpass; actual current FAIL/XFAIL remains unchanged. No inherited-red attribution.'})
    zero_case_files = [path for path, values in per_file.items() if not values]
    if zero_case_files:
        unresolved.append({'class': 'selected_file_without_routed_junit_case', 'paths': zero_case_files})
    report = {'schema': 'policyos.e02.B.native_cohort_independent_review.v1',
              'reviewer': 'B EXE leaf independent final root cohort output review',
              'command_argv': sys.argv, 'environment': {'python': sys.version, 'executable': sys.executable,
                                                       'platform': platform.platform()},
              'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
              'wall_s': time.monotonic() - clock, 'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'target_sha': args.target, 'target_tree': before['tree'], 'source_before': before, 'source_after': after,
              'source_unchanged': before == after, 'input_reads': reads,
              'git_reads': {'commands': ['rev-parse HEAD/HEAD^{tree}', 'symbolic-ref HEAD', 'status --porcelain',
                                        'diff --name-only source_base target -- policy-engine/src', 'show target:path'],
                           'test_git_objects_compared': len(paths), 'production_git_objects_compared': len(changed_python)},
              'predicate_basis': 'recomputed', 'whole_file_denominator': len(paths),
              'case_count_basis': 'Every actual JUnit testcase, reconciled with suite attributes and complete terminal stdout; historical case counts are not read for arithmetic.',
              'junit_case_denominator': len(cases), 'junit_suites': suites,
              'case_outcomes': {status: counts[status] for status in ['PASS', 'FAIL', 'ERROR', 'SKIP', 'XFAIL']},
              'strict_xfail_count': sum(r.get('strict_from_actual_source', False) for r in nonpass),
              'strict_xpass_count': len(strict_xpass), 'non_strict_xpass_count': summary.get('xpassed', 0),
              'terminal_summary': summary_line, 'stdout_counts': summary, 'warning_counts': dict(warning_counts),
              'complete_warning_section': warning_section, 'nonpass_cases': nonpass,
              'new_unadvertised_nonpass_count': len(unadvertised), 'new_unadvertised_nonpass_cases': unadvertised,
              'retained_nonpass_owner_and_log_reviews': retained_source_reviews,
              'per_selected_file_actual_cases': {p: dict(v) for p, v in per_file.items()},
              'production_module_origins': origin_review, 'production_module_denominator': len(changed_python),
              'module_origin_scope': 'Exact-child-interpreter preflight resolutions with same cwd/env plus independent actual content readback; not a trace of every child import.',
              'native_execution': {'exit_code': wrapper['exit_code'], 'recorded_outcome': wrapper['outcome'],
                                   'wall_s': wrapper['wall_s'], 'max_rss_kib': wrapper['max_rss_kib'],
                                   'measurement_error': wrapper['measurement_error']},
              'previous_harness_qualification': aborted_qualification,
              'review_outcome': 'PASS' if not issues else 'ERROR', 'audit_issues': issues,
              'unresolved_by_construction': unresolved,
              'limitations': ['The native test suite outcome remains actual FAIL; advertised retained nonpass does not change pytest success.',
                              'This review makes no inherited-red attribution and performs no test rerun.',
                              'Typed nonpass declarations locate intended retained scope; canonical semantic authority/formal finding closure remains with the source owner.',
                              'Historical per-wave counts, unselected production data/live optional backends, current institutional authorization and full served/runtime-invocation admission are outside this review.']}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['target_sha', 'target_tree', 'review_outcome', 'whole_file_denominator',
                                           'junit_case_denominator', 'case_outcomes', 'strict_xfail_count', 'strict_xpass_count',
                                           'warning_counts', 'new_unadvertised_nonpass_count', 'production_module_denominator',
                                           'source_unchanged', 'audit_issues', 'unresolved_by_construction']}, indent=2))
    return int(bool(issues))


if __name__ == '__main__':
    sys.exit(main())
