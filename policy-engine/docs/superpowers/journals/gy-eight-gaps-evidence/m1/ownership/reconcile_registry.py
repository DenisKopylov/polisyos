"""Reconcile the complete registry output identity set by independent parsers."""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib
from tools.quality.validation.check_layer3_gy_generated_public_lifecycle_audit import _validate_gy_family_metadata

root = Path.cwd()
registry = root / 'architecture/generated_artifacts.toml'
current_bytes = registry.read_bytes()
base_bytes = subprocess.check_output(['git', 'show', '43580c80b:policy-engine/architecture/generated_artifacts.toml'])
parsed = [tomllib.loads(x.decode()) for x in (base_bytes, current_bytes)]
sets = []
counts = []
for raw, document in zip((base_bytes, current_bytes), parsed, strict=True):
    text = raw.decode()
    named = {p for f in document['family'] for p in f.get('outputs', [])}
    independent = set()
    arrays = re.findall(r'(?m)^outputs = (\[.*?\])', text, re.S)
    for literal in arrays:
        independent.update(ast.literal_eval(literal))
    assert named == independent, sorted(named ^ independent)
    family_count = len(document['family'])
    assert family_count == len(re.findall(r'(?m)^\[\[family\]\]$', text))
    sets.append(named)
    counts.append({'families': family_count, 'unique_output_paths': len(named), 'output_occurrences': sum(len(f.get('outputs', [])) for f in document['family'])})
base, current = parsed
before_set, after_set = sets
base_ids = {f['id'] for f in base['family']}
current_families = {f['id']: f for f in current['family']}
assert len(current_families) == len(current['family'])
new_families = [f for f in current['family'] if f['id'] not in base_ids]
violations = json.loads(json.loads((root / '_build/gy-gaps/m1/baseline.json').read_text())['stdout'])['violations']
missing_paths = {v['path'] for v in violations if v['code'] == 'layer3_gy_artifact_not_registered'}
independent_missing_paths = sorted(dict.fromkeys(v['path'] for v in violations if v['code'] == 'layer3_gy_artifact_not_registered'))
assert missing_paths == set(independent_missing_paths)
claims = Counter(p for f in current['family'] for p in f.get('outputs', []))
missing_or_duplicate = {p: claims[p] for p in sorted(missing_paths) if claims[p] != 1}
source_integrity_issues = []
metadata_issues = []
for f in current['family']:
    if f.get('gy_lifecycle_family') is True:
        _validate_gy_family_metadata(f, metadata_issues)
    if f['id'] in base_ids or f['lifecycle'] != 'source_committed':
        continue
    for p in f['outputs']:
        expected = f['source_integrity_sha256'][p]
        actual = 'sha256:' + hashlib.sha256((root / p).read_bytes()).hexdigest()
        if expected != actual:
            source_integrity_issues.append({'family_id': f['id'], 'path': p, 'expected': expected, 'actual': actual})
removed_paths = sorted(before_set - after_set)
extra_nonfamily_changes = [key for key in set(base) | set(current) if key != 'family' and (key not in base or key not in current or base[key] != current[key])]
splits = []
for suffix, source_id in [('n13a-acquisition-census', 'policy-design-case-layer3-gy-n13a-frozen-acquisition-evidence'), ('n13b-acquisition-executor', 'policy-design-case-layer3-gy-n13b-frozen-acquisition-evidence')]:
    family_id = 'policy-design-case-layer3-gy-' + suffix
    original = next(f for f in base['family'] if f['id'] == family_id)
    generated = current_families[family_id]['outputs']
    source = current_families[source_id]['outputs']
    assert not set(generated) & set(source)
    assert set(original['outputs']) == set(generated) | set(source)
    splits.append({'generated_family': family_id, 'source_family': source_id, 'original': len(original['outputs']), 'generated': len(generated), 'source': len(source), 'lost_identities': [], 'gained_identities': []})
assert registry.read_bytes() == current_bytes, 'Registry changed concurrently; rerun this read-only reconciliation.'
report = {
    'base_commit': '43580c80b',
    'current_registry_sha256': 'sha256:' + hashlib.sha256(current_bytes).hexdigest(),
    'denominator': 'Complete family/output arrays in base and current generated_artifacts.toml; complete baseline violation array for not_registered identity claims. TOML parsed output sets reconciled with independent Python literal parsing; family counts reconciled with table headers.',
    'base': counts[0], 'current': counts[1],
    'baseline_not_registered_path_count': len(missing_paths),
    'baseline_missing_or_duplicate_claims': missing_or_duplicate,
    'original_output_paths_removed': removed_paths,
    'new_output_path_count': len(after_set - before_set),
    'nonfamily_scope_changes': extra_nonfamily_changes,
    'ownership_splits': splits,
    'new_source_family_ids': [f['id'] for f in new_families if f['lifecycle'] == 'source_committed'],
    'source_integrity_issues': source_integrity_issues,
    'gy_metadata_issues': metadata_issues,
    'unreadable_cases': [],
}
print(json.dumps(report, indent=2))
raise SystemExit(bool(missing_or_duplicate or removed_paths or extra_nonfamily_changes or source_integrity_issues or metadata_issues))
