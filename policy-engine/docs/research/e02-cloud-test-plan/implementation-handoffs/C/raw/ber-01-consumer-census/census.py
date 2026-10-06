from __future__ import annotations

import collections
import json
import re
import subprocess
from pathlib import Path

repo = Path('/Users/deniskopylov/.codex/worktrees/e02-c-berl-20261006/polisyos')
raw = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/berl-schema-consumers')
patterns = {
    'bundle_type': re.compile(r'ExplanationBundle', re.IGNORECASE),
    'bundle_wire': re.compile(r'explanation_bundle', re.IGNORECASE),
    'persisted_validator': re.compile(r'validate_persisted_explanation_bundle'),
    'generated_schema_helper': re.compile(r'generated_explanation_bundle_schema'),
    'schema_resource_path': re.compile(r'explanation_bundle\.schema\.json'),
    'berl_contract_import': re.compile(r'polisyos\.berl(?:\.contracts)?'),
    'resource_loader': re.compile(r'importlib\.resources|resources\.files\(|resources\.read_text\(|pkgutil\.get_data\(|\.read_bytes\(\)|\.read_text\(\)'),
}
paths = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).decode().split('\0')
paths = [p for p in paths if p]
exts = collections.Counter(Path(p).suffix.lower() or '[no suffix]' for p in paths)
kind_counts = collections.Counter()
all_hits: dict[str, list[dict[str, object]]] = {k: [] for k in patterns}
binary_paths: list[str] = []
undecodable_paths: list[str] = []
text_count = 0
for rel in paths:
    data = (repo / rel).read_bytes()
    if b'\0' in data:
        binary_paths.append(rel)
        kind_counts['binary'] += 1
        continue
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        undecodable_paths.append(rel)
        kind_counts['non_utf8'] += 1
        continue
    text_count += 1
    kind = rel.split('/', 2)[1] if rel.startswith('policy-engine/') and rel.count('/') >= 1 else 'repo-root'
    if '/src/' in rel:
        kind_counts['src'] += 1
    elif '/tests/' in rel:
        kind_counts['tests'] += 1
    elif '/docs/' in rel:
        kind_counts['docs'] += 1
    elif kind == 'repo-root' or Path(rel).name in {'pyproject.toml', 'MANIFEST.in', 'setup.cfg', 'setup.py'}:
        kind_counts['root_or_packaging'] += 1
    else:
        kind_counts['other_text'] += 1
    for line_no, line in enumerate(text.splitlines(), 1):
        for name, pattern in patterns.items():
            if pattern.search(line):
                all_hits[name].append({'path': rel, 'line': line_no, 'text': line[:300]})
summary = {
    'repo': str(repo),
    'head': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD']).decode().strip(),
    'tree': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD^{tree}']).decode().strip(),
    'total_tracked_path_denominator': len(paths),
    'tracked_suffix_denominator': dict(sorted(exts.items())),
    'text_file_count_utf8_no_nul': text_count,
    'tracked_file_kinds': dict(sorted(kind_counts.items())),
    'binary_paths': binary_paths,
    'non_utf8_paths': undecodable_paths,
    'pattern_hit_file_counts': {k: len({entry['path'] for entry in v}) for k, v in all_hits.items()},
    'pattern_hit_line_counts': {k: len(v) for k, v in all_hits.items()},
    'pattern_hits': all_hits,
}
(raw / 'tracked-consumer-census.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k != 'pattern_hits'}, indent=2, ensure_ascii=False))
print('FULL_HIT_DETAILS=' + str(raw / 'tracked-consumer-census.json'))
