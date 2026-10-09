"""Run pytest against an immutable checkout and reconcile every actual product origin."""
from __future__ import annotations

import argparse
import hashlib
import importlib.abc
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def tree_blobs(root, ref):
    entries = {}
    for entry in git(root, 'ls-tree', '-rz', '--full-tree', ref).split(b'\0'):
        if entry:
            mode_type_sha, path = entry.split(b'\t', 1)
            mode, kind, sha = mode_type_sha.split()
            if kind == b'blob':
                entries[os.fsdecode(path)] = sha.decode()
    return entries


class MutationFinder(importlib.abc.MetaPathFinder):
    def __init__(self, name, path):
        self.name, self.path = name, path

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.name:
            return importlib.util.spec_from_file_location(fullname, self.path)
        return None


class OriginPlugin:
    def __init__(self, args, candidate, baseline):
        self.args, self.candidate, self.baseline = args, candidate, baseline

    def pytest_sessionfinish(self, session, exitstatus):
        origins, unresolved, problems = [], [], []
        for name, module in sorted(sys.modules.items()):
            if not (name == 'polisyos' or name.startswith('polisyos.') or name == 'tools' or name.startswith('tools.')):
                continue
            filename = getattr(module, '__file__', None)
            if filename is None:
                unresolved.append({'module': name, 'reason': 'namespace_or_dynamic_without_file', 'spec_origin': str(getattr(getattr(module, '__spec__', None), 'origin', None))})
                continue
            path = Path(filename).resolve()
            data = path.read_bytes()
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            mutation = self.args.mutant_path and path == self.args.mutant_path.resolve()
            if mutation:
                relative = self.args.mutant_canonical_path
            else:
                try:
                    relative = path.relative_to(self.args.target.resolve()).as_posix()
                except ValueError:
                    relative = None
            row = {'module': name, 'origin': str(path), 'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'git_blob': blob, 'candidate_blob': self.candidate.get(relative), 'G_blob': self.baseline.get(relative), 'mutation': bool(mutation)}
            row['equals_candidate'] = blob == row['candidate_blob']
            row['equals_selected_G'] = blob == row['G_blob']
            origins.append(row)
            if relative is None or (not mutation and not row['equals_candidate']):
                problems.append(row)
        end_sha = git(self.args.target, 'rev-parse', 'HEAD').decode().strip()
        end_status = git(self.args.target, 'status', '--porcelain=v1').decode()
        if end_sha != self.args.expected_sha or end_status:
            problems.append({'reason': 'checkout_changed_during_wave', 'head': end_sha, 'status': end_status})
        receipt = {
            'source_commit': self.args.expected_sha, 'source_tree': git(self.args.target, 'rev-parse', self.args.expected_sha + '^{tree}').decode().strip(),
            'selected_G': self.args.base_sha, 'end_source_commit': end_sha, 'end_status': end_status,
            'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(), 'sys_path': sys.path,
            'actual_product_module_file_origin_denominator': len(origins), 'origins': origins, 'unresolved_module_origins': unresolved,
            'origin_problems': problems, 'pytest_exitstatus': int(exitstatus),
            'installed_distributions': sorted([{'name': d.metadata['Name'], 'version': d.version} for d in importlib.metadata.distributions()], key=lambda d: d['name'].lower()),
            'selected_environment': {key: os.environ.get(key) for key in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONDONTWRITEBYTECODE', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'JAX_PLATFORMS', 'JAX_PLATFORM_NAME', 'XLA_PYTHON_CLIENT_PREALLOCATE', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
            'qualification': 'Complete actual file-origin denominator for this finite process; namespace/dynamic origins enumerated separately. No unexecuted consumer, repository-wide runtime, producer authority or integrated acceptance claim.',
        }
        self.args.origins.write_text(json.dumps(receipt, indent=2) + '\n')
        print('ORIGIN_RECONCILIATION ' + json.dumps({'file_origins': len(origins), 'unresolved_modules': len(unresolved), 'problems': len(problems)}))
        if problems:
            session.exitstatus = 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--base-sha', required=True)
    parser.add_argument('--origins', type=Path, required=True)
    parser.add_argument('--mutant-module')
    parser.add_argument('--mutant-path', type=Path)
    parser.add_argument('--mutant-canonical-path')
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert git(args.target, 'rev-parse', 'HEAD').decode().strip() == args.expected_sha
    assert not git(args.target, 'status', '--porcelain=v1'), 'source checkout must be clean'
    candidate = tree_blobs(args.target, args.expected_sha)
    baseline = tree_blobs(args.target, args.base_sha)
    product = args.target / 'policy-engine'
    sys.path[:0] = [str(product / 'src'), str(product)]
    sys.dont_write_bytecode = True
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    if args.mutant_module:
        sys.meta_path.insert(0, MutationFinder(args.mutant_module, args.mutant_path))
    import pytest
    argv = args.pytest_args[1:] if args.pytest_args[:1] == ['--'] else args.pytest_args
    return pytest.main(argv, plugins=[OriginPlugin(args, candidate, baseline)])


if __name__ == '__main__':
    raise SystemExit(main())
