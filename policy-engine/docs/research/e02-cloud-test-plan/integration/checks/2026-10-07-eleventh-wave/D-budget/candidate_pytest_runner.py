from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.abc
import importlib.machinery
import json
import os
import sys
from pathlib import Path

candidate_root = Path(os.environ['D_BUDGET_CANDIDATE_ROOT']).resolve()
candidate_src = (candidate_root / 'src').resolve()
search_tests = (candidate_root / 'tests/unit/scientist/methods/search').resolve()
live_project = Path(os.environ['D_BUDGET_LIVE_PROJECT']).resolve()
live_src = (live_project / 'src').resolve()
manifest_path = Path(os.environ['D_BUDGET_SOURCE_MANIFEST']).resolve()
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
expected = {row['path']: row['sha256'] for row in manifest['files']}

# The reused venv's editable-install .pth adds the live G checkout. Remove only
# those product-root entries; retain its site-packages for installed dependencies.
removed = []
for entry in list(sys.path):
    resolved = Path(entry or os.getcwd()).resolve()
    if resolved in {live_project, live_src}:
        sys.path.remove(entry)
        removed.append(str(resolved))
for entry in [str(candidate_src), str(search_tests)]:
    if entry not in sys.path:
        sys.path.insert(0, entry)

if any(Path(entry or os.getcwd()).resolve() in {live_project, live_src} for entry in sys.path):
    raise SystemExit('candidate import guard: live G product path remains on sys.path')

class CandidateOnlyPolisyosFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != 'polisyos' and not fullname.startswith('polisyos.'):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None:
            return None
        if spec.origin and spec.origin not in {'built-in', 'frozen'}:
            origin = Path(spec.origin).resolve()
            try:
                relative = origin.relative_to(candidate_root).as_posix()
            except ValueError as exc:
                raise ImportError(f'non-candidate Polisyos origin: {origin}') from exc
            key = 'policy-engine/' + relative
            actual = hashlib.sha256(origin.read_bytes()).hexdigest()
            if expected.get(key) != actual:
                raise ImportError(f'Polisyos origin not bound to candidate Git blob: {key}')
        else:
            locations = list(spec.submodule_search_locations or [])
            if not locations or any(
                not Path(location).resolve().is_relative_to(candidate_src)
                for location in locations
            ):
                raise ImportError(f'non-candidate namespace origin: {fullname}')
        return None

sys.meta_path.insert(0, CandidateOnlyPolisyosFinder())
preloaded = [name for name in sys.modules if name == 'polisyos' or name.startswith('polisyos.')]
if preloaded:
    raise SystemExit(f'candidate import guard: Polisyos modules loaded before guard: {preloaded}')

import pytest

print('candidate_sha=' + manifest['candidate_sha'])
print('candidate_tree=' + manifest['candidate_tree'])
print('live_paths_removed=' + json.dumps(removed))
print('candidate_src=' + str(candidate_src))
print('cwd=' + os.getcwd())
print('sys_path=' + json.dumps(sys.path))
print('pytest_version=' + importlib.metadata.version('pytest'))
print('pytest_argv=' + json.dumps(sys.argv[1:]))

try:
    pytest_exit = int(pytest.main(sys.argv[1:]))
except BaseException as exc:
    pytest_exit = 2
    print(f'pytest_wrapper_exception={type(exc).__name__}: {exc}', file=sys.stderr)

origins = []
origin_problems = []
for name, module in sorted(sys.modules.items()):
    if name != 'polisyos' and not name.startswith('polisyos.'):
        continue
    spec = getattr(module, '__spec__', None)
    origin_raw = getattr(module, '__file__', None) or getattr(spec, 'origin', None)
    if not origin_raw or origin_raw in {'built-in', 'frozen'}:
        origin_problems.append({'module': name, 'origin': origin_raw, 'problem': 'missing filesystem origin'})
        continue
    origin = Path(origin_raw).resolve()
    try:
        relative = origin.relative_to(candidate_root).as_posix()
    except ValueError:
        origin_problems.append({'module': name, 'origin': str(origin), 'problem': 'outside candidate root'})
        continue
    key = 'policy-engine/' + relative
    actual_sha = hashlib.sha256(origin.read_bytes()).hexdigest()
    expected_sha = expected.get(key)
    row = {'module': name, 'origin': str(origin), 'manifest_path': key, 'sha256': actual_sha, 'expected_sha256': expected_sha}
    origins.append(row)
    if expected_sha != actual_sha:
        origin_problems.append({**row, 'problem': 'origin bytes do not match candidate Git blob'})

report = {
    'candidate_sha': manifest['candidate_sha'],
    'candidate_tree': manifest['candidate_tree'],
    'cwd': os.getcwd(),
    'live_paths_removed': removed,
    'remaining_live_product_paths': [entry for entry in sys.path if Path(entry or os.getcwd()).resolve() in {live_project, live_src}],
    'pytest_exit_code': pytest_exit,
    'polisyos_modules_loaded': len(origins) + len(origin_problems),
    'polisyos_origins_matched': sum(1 for row in origins if row.get('expected_sha256') == row.get('sha256')),
    'origins': origins,
    'origin_problems': origin_problems,
}
Path(os.environ['D_BUDGET_ORIGINS_PATH']).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('candidate_origin_check=' + ('PASS' if not origin_problems else 'FAIL'))
print(f'candidate_origin_modules={len(origins)}')
print(f'candidate_origin_problems={len(origin_problems)}')
print(f'pytest_exit_code={pytest_exit}')
sys.exit(pytest_exit if not origin_problems else 98)
