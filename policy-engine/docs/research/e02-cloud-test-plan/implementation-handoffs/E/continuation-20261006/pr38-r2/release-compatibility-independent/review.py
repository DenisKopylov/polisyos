"""Independent selected release-row review on immutable Git source; no code edits."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tomllib

ROOT = Path('/workspace/e02-E-continuation-20261006')
PRODUCT = ROOT / 'policy-engine'
OUT = Path('/workspace/e02-E-pr38-r2-receipts/release-compatibility-G53-independent')
SOURCE = '25ab29c0f527c90f4281a4cf04256acb8f62f051'
BASE = 'a2677935015e8a0e7f2dfd5412b671e13fb3175a'
G = '53b309019913b938909d6dc0fc13f8edb409f368'
DDM = '4c5afb1dc10b4e3f4dbc10b50ca6066de9b08ccb'


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def blob(ref: str, path: str) -> bytes:
    return git('show', ref + ':' + path)


def identity(ref: str, path: str) -> dict:
    data = blob(ref, path)
    return {'sha': ref, 'path': path, 'blob': git('rev-parse', ref + ':' + path).decode().strip(),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


changed = git('diff', '--name-only', BASE, SOURCE).decode().splitlines()
assert len(changed) == 6 and all(p.startswith('policy-engine/release-fragments/unreleased/') and p.endswith('.toml') for p in changed)
assert git('rev-parse', SOURCE + '^').decode().strip() == BASE
assert git('rev-parse', SOURCE + '^{tree}').decode().strip() == '51343543823afdec2dd86f7e76e1590b1dca0a70'

native_paths = [
    'tools/ops_runners/release/check_compatibility_release_gates.py',
    'tools/ops_runners/release/build_release_notes.py',
    'tools/lib/imports.py',
]
for relative in native_paths:
    assert (PRODUCT / relative).read_bytes() == blob(SOURCE, 'policy-engine/' + relative)

sys.path.insert(0, str(PRODUCT))
native = importlib.import_module('tools.ops_runners.release.check_compatibility_release_gates')
notes = importlib.import_module('tools.ops_runners.release.build_release_notes')
policy_path = 'policy-engine/architecture/gates/compatibility_release.toml'
policy = tomllib.loads(blob(SOURCE, policy_path).decode())
contract_path = 'policy-engine/architecture/public_surface/contract.toml'
contract = tomllib.loads(blob(SOURCE, contract_path).decode())
assert blob(SOURCE, contract_path) == blob(BASE, contract_path)
supported = {}
for package in contract['package']:
    for name in set([package['module'], *package.get('supported_entrypoints', [])]):
        supported[name] = {'owner': package['owner'], 'classification': package['classification'],
                           'version_owner': package.get('version_owner', contract['public_surface']['version_owner'])}
assert supported['polisyos.calibration']['owner'] == 'team-scientist'
assert supported['polisyos.foundry.uncertainty']['owner'] == 'team-polisyos'
assert supported['polisyos.ddm']['owner'] == 'team-scientist'

fixture = OUT / 'selected-fragments'
fixture.mkdir(parents=True, exist_ok=True)
for path in changed:
    (fixture / Path(path).name).write_bytes(blob(SOURCE, path))
fragments = notes.load_fragments(fixture)
rows = notes.structured_compatibility_changes(fragments)
errors, findings = native._validate_fragments(PRODUCT, policy, fragments, breaking_classes=())
assert len(fragments) == len(rows) == 6 and not errors and not findings


def canonical(fragment: dict) -> None:
    """Resolve row owner/classification/version from tracked contract + G decision."""
    changes = fragment.get('compatibility_change', [])
    assert isinstance(changes, list) and len(changes) == 1, 'one owner-scoped structured row is required'
    row = changes[0]
    names = re.findall(r'polisyos\.[A-Za-z0-9_.]+', row['surface'])
    assert len(names) == 1 and names[0] in supported, 'one declared canonical surface is required'
    module = names[0]
    expected = supported[module]
    assert row['owner'] == expected['owner'], 'structured owner must match canonical contract'
    assert fragment['owner'] == expected['owner'], 'note owner must match its single canonical surface'
    assert row['surface'].split(':', 1)[0] == expected['classification'], 'row classification must match canonical contract'
    assert fragment['surface_classification'].split(':', 1)[0] == expected['classification'], 'note classification must match canonical contract'
    if module == 'polisyos.ddm':
        assert row['change_class'] == fragment['change_class'] == 'persisted-artifact-format', 'DDM is a persisted format migration, not a facade API change'
        assert row['impact'] == 'compatible_with_migration', 'DDM version transition has directional reader migration'
        assert row['version_owner'] == 'team-scientist', 'G53 and migration documentation name the DDM registry owner'
        assert row.get('migration_docs') == fragment.get('migration_docs') == ['src/polisyos/ddm/integration/model_registry_gate.md'], 'DDM migration must bind its canonical reader migration document'
    else:
        assert row['change_class'] == fragment['change_class'] == 'python-public-api'
        assert row['impact'] == 'additive'
        assert row['version_owner'] == expected['version_owner'] == 'team-architecture'
        assert fragment.get('public_surface_inventory_reviewed') is True
        assert row.get('public_surface_inventory_reviewed') is True


for fragment in fragments:
    canonical(fragment)

# Complete actual current surface evidence comes from the pinned source, not G53's
# historical 7f 28/19 surface counts. AST literals and committed inventory agree.
inventory_path = 'policy-engine/architecture/public_surface/inventory.json'
inventory = json.loads(blob(SOURCE, inventory_path))
assert blob(SOURCE, inventory_path) == blob(BASE, inventory_path)
exports = {}
for module, path, expected_count in [
    ('polisyos.calibration', 'policy-engine/src/polisyos/calibration/__init__.py', 29),
    ('polisyos.foundry.uncertainty', 'policy-engine/src/polisyos/foundry/uncertainty/__init__.py', 20),
    ('polisyos.ddm', 'policy-engine/src/polisyos/ddm/__init__.py', 17),
]:
    assignments = [n for n in ast.walk(ast.parse(blob(SOURCE, path))) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in n.targets)]
    assert len(assignments) == 1
    names = ast.literal_eval(assignments[0].value)
    entry = next(e for p in inventory['packages'] for e in p['entrypoints'] if e['module'] == module)
    assert len(names) == expected_count == entry['export_count']
    assert set(names) == set(entry['exports'])
    assert blob(SOURCE, path) == blob(BASE, path)
    exports[module] = {'count': expected_count, 'classification': supported[module]['classification'], 'canonical_owner': supported[module]['owner'], 'source': identity(SOURCE, path), 'exports': names, 'inventory_mode': entry['facade_mode_observed']}

# Link existence alone is insufficient: bind each referenced source doc/test to
# exact Git bytes and ensure the actual parser's filesystem view sees those bytes.
doc_refs = []
for f in fragments:
    for relative in set(f.get('evidence', []) + f.get('migration_docs', []) + f.get('runbook_docs', []) + f['compatibility_change'][0].get('migration_docs', []) + f['compatibility_change'][0].get('runbook_docs', [])):
        full = 'policy-engine/' + relative
        data = blob(SOURCE, full)
        assert (PRODUCT / relative).read_bytes() == data
        doc_refs.append(identity(SOURCE, full))

controls = []
for i, fragment in enumerate(fragments):
    row = fragment['compatibility_change'][0]
    for field in policy['compatibility_release_gates']['required_structured_fields']:
        modified = copy.deepcopy(fragment)
        modified['compatibility_change'][0].pop(field)
        e, _ = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        assert any(x.message == f'missing `{field}`' for x in e)
        controls.append({'kind': 'required-row-field-removal', 'row_id': row['id'], 'field': field, 'actual_generic_parser': [x.as_dict() for x in e], 'outcome': 'REFUSED'})
    for location in ['note', 'row']:
        modified = copy.deepcopy(fragment)
        target = modified if location == 'note' else modified['compatibility_change'][0]
        target['owner'] = 'E'
        e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        assert not e and not f, 'generic parser validates owner presence, not canonical owner identity'
        try:
            canonical(modified)
        except AssertionError as exc:
            reason = str(exc)
        else:
            raise AssertionError('Present but fake E owner was accepted as canonical')
        controls.append({'kind': 'present-but-fake-canonical-owner', 'row_id': row['id'], 'location': location, 'owner': 'E', 'other_fields_retained': True, 'actual_generic_parser': 'PASS', 'canonical_owner_predicate': 'REFUSED', 'reason': reason})
    for field, value in [('version_owner', 'E'), ('surface', 'public_experimental: polisyos.ddm' if 'polisyos.ddm' in row['surface'] else 'internal: ' + re.findall(r'polisyos\.[A-Za-z0-9_.]+', row['surface'])[0])]:
        modified = copy.deepcopy(fragment)
        modified['compatibility_change'][0][field] = value
        e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        assert not e and not f
        try:
            canonical(modified)
        except AssertionError as exc:
            reason = str(exc)
        else:
            raise AssertionError('Corrupt canonical field was accepted')
        controls.append({'kind': 'canonical-field-corruption', 'row_id': row['id'], 'field': field, 'value': value, 'other_fields_retained': True, 'actual_generic_parser': 'PASS', 'canonical_predicate': 'REFUSED', 'reason': reason})
    modified = copy.deepcopy(fragment)
    modified['compatibility_change'] = []
    e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
    assert not e and f
    try:
        canonical(modified)
    except AssertionError as exc:
        reason = str(exc)
    else:
        raise AssertionError('Empty structured carrier accepted as a complete six-row receipt')
    controls.append({'kind': 'structured-row-carrier-removal', 'row_id': row['id'], 'actual_generic_parser': 'warning only', 'canonical_predicate': 'REFUSED', 'reason': reason})

for fragment in fragments:
    row = fragment['compatibility_change'][0]
    if row['change_class'] == 'python-public-api':
        modified = copy.deepcopy(fragment)
        modified['public_surface_inventory_reviewed'] = False
        modified['compatibility_change'][0]['public_surface_inventory_reviewed'] = False
        e, _ = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        assert any(x.check == 'public-surface-review' for x in e)
        controls.append({'kind': 'inventory-review-removal', 'row_id': row['id'], 'both_fields_removed': True, 'actual_generic_parser': [x.as_dict() for x in e], 'outcome': 'REFUSED'})
    else:
        for field, value in [('impact', 'additive'), ('change_class', 'internal'), ('migration_docs', [])]:
            modified = copy.deepcopy(fragment)
            modified['compatibility_change'][0][field] = value
            if field == 'migration_docs':
                modified['migration_docs'] = []
            e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
            assert not e and not f
            try:
                canonical(modified)
            except AssertionError as exc:
                reason = str(exc)
            else:
                raise AssertionError('DDM migration meaning was erased but accepted')
            controls.append({'kind': 'DDM-directional-migration-corruption', 'row_id': row['id'], 'field': field, 'value': value, 'other_fields_retained': True, 'actual_generic_parser': 'PASS', 'canonical_G53_profile': 'REFUSED', 'reason': reason})

ddm_identity = []
for path in ['policy-engine/src/polisyos/ddm/integration/model_registry.py', 'policy-engine/src/polisyos/ddm/integration/model_registry_record.schema.json', 'policy-engine/src/polisyos/ddm/integration/model_registry_record.v1.schema.json', 'policy-engine/src/polisyos/ddm/__init__.py', 'policy-engine/tests/unit/ddm/test_registry_schema_compatibility.py']:
    assert blob(DDM, path) == blob(SOURCE, path)
    ddm_identity.append({'old': identity(DDM, path), 'current': identity(SOURCE, path), 'identical': True})
ddm_review_path = Path('/workspace/e02-E-pr38-r2-receipts/independent-doe-reviewer/review.json')
ddm_bytes = ddm_review_path.read_bytes()
assert hashlib.sha256(ddm_bytes).hexdigest() == '032c1beef8ba54e2042926439852a13895c83d569c41dce7f5f2064edea314ec'
ddm_review = json.loads(ddm_bytes)['families']['ddm']
assert ddm_review['implementation_sha'] == DDM and ddm_review['code_verdict'] == 'GO_bounded_mechanism'

result = {
    'schema': 'e02.E.selected-compatibility-metadata-review.v1',
    'source_sha': SOURCE, 'source_tree': git('rev-parse', SOURCE + '^{tree}').decode().strip(), 'base_sha': BASE,
    'G_owner_decision_sha': G, 'G_owner_decision': identity(G, 'policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/E-r2-owner-actions-2026-10-06.md'),
    'reviewer': 'independent backtest_r3 leaf; metadata only, no BKT/Welfare code review',
    'footprint': changed, 'code_schema_test_inventory_contract_changes': [],
    'actual_native_parser': 'tools.ops_runners.release.check_compatibility_release_gates._validate_fragments + build_release_notes.load_fragments/structured_compatibility_changes',
    'native_parser_source': [identity(SOURCE, 'policy-engine/' + p) for p in native_paths],
    'canonical_owner_basis': {'contract': identity(SOURCE, contract_path), 'public_version_owner': contract['public_surface']['version_owner'], 'selected_packages': {k: supported[k] for k in exports}, 'DDM_persisted_version_owner': 'team-scientist per explicit G53 owner decision and canonical migration doc'},
    'selected_fragment_count': len(fragments), 'structured_rows': rows, 'actual_native_errors': [], 'actual_native_findings': [],
    'fragment_source': [identity(SOURCE, p) for p in changed], 'current_exports': exports,
    'historical_G53_counts': 'G53 7f calibration28/uncertainty19 source is historical; current pinned source29/20 is verified against exact unchanged inventory',
    'docs_and_evidence_refs': doc_refs, 'negative_controls': controls,
    'DDM_unchanged_source_reuse': {'source': DDM, 'independent_receipt_path': str(ddm_review_path), 'independent_receipt_sha256': hashlib.sha256(ddm_bytes).hexdigest(), 'code_verdict': ddm_review['code_verdict'], 'original_suite': ddm_review['suite'], 'property_identities': ddm_identity, 'new_DDM_code_review_performed': False, 'authority': 'Library consistency only; no current feed/time/institutional signoff/served deployment or LA054/055/056 closure'},
    'environment': {'python_executable': sys.executable, 'python': platform.python_version(), 'platform': platform.platform(), 'cwd': str(PRODUCT), 'new_environment': False, 'new_worktree': False, 'caps_added': False, 'production_data_used': False},
    'verdict': 'GO-bounded-canonical-owner-release-metadata',
    'limits': ['Selected six-row parser and canonical-owner reconciliation only; no generic/global CI PASS', 'No code/schema API semantics changed in this metadata delta', 'Structured parser presence checks alone do not establish canonical ownership', 'Current29/20 reconciliation is reused from independent r5 and verified from pinned source/inventory, no dynamic numerical family rerun', 'DDM17 internal facade and independently reviewed v1/v2 code are unchanged; deployment/version rollout and current-feed/signoff owner decisions remain separate', 'B197/B194/B201/B202 and remaining finding ledger statuses are unchanged'],
}
(OUT / 'review.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({'verdict': result['verdict'], 'source': SOURCE, 'fragments': len(fragments), 'structured_rows': len(rows), 'canonical_counts': {k: v['count'] for k, v in exports.items()}, 'controls': len(controls), 'present_fake_E_owner_generic_PASS_canonical_REFUSED': sum(x['kind'] == 'present-but-fake-canonical-owner' for x in controls), 'output': str(OUT / 'review.json')}))
