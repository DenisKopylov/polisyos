"""Reconcile the exact checker-only source delta without executing benchmarks."""

import ast
import copy
import hashlib
import json
import subprocess

REPO = '/workspace/e02-F-cau-20261006'
BASE = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
CANDIDATE = 'e1c4bb28c9d5ff936ae1c047619c56cf12ba5347'
PATH = 'policy-engine/benchmarks/natural_experiments/policy_natural_experiments.py'


def git(*args):
    return subprocess.check_output(['git', '-C', REPO, *args])


def source(sha, path):
    raw = git('show', sha + ':' + path)
    return raw, {
        'source_sha': sha, 'path': path, 'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'git_blob': git('rev-parse', sha + ':' + path).decode().strip(),
    }


def main():
    before, before_ref = source(BASE, PATH)
    after, after_ref = source(CANDIDATE, PATH)
    old = ast.parse(before)
    new = ast.parse(after)
    old_case = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == '_case_clean_rollout')
    new_case = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == '_case_clean_rollout')
    old_checker = next(n for n in old_case.body if isinstance(n, ast.FunctionDef) and n.name == 'checker')
    new_checker = next(n for n in new_case.body if isinstance(n, ast.FunctionDef) and n.name == 'checker')
    assert ast.dump(old_checker) != ast.dump(new_checker)
    new_case.body[new_case.body.index(new_checker)] = copy.deepcopy(old_checker)
    assert ast.dump(old) == ast.dump(new), 'Source mutation escaped the single checker'
    changed_paths = git('diff', '--name-only', BASE, CANDIDATE).decode().splitlines()
    assert changed_paths == [PATH]
    did_path = 'policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py'
    did_before, did_before_ref = source(BASE, did_path)
    did_after, did_after_ref = source(CANDIDATE, did_path)
    assert did_before == did_after
    print(json.dumps({
        'check': 'PASS', 'base': before_ref, 'candidate': after_ref,
        'changed_paths': changed_paths,
        'oracle': 'Replace only new nested checker AST with old checker; entire module AST equals base.',
        'fixture_runner_all_other_benchmark_bodies_unchanged': True,
        'diagnostic_and_estimators_byte_unchanged': True,
        'did_before': did_before_ref, 'did_after': did_after_ref,
        'scope': 'Exact two files and whole benchmark AST; no full gate denominator or P41 inference.',
    }, indent=2))


if __name__ == '__main__':
    main()
