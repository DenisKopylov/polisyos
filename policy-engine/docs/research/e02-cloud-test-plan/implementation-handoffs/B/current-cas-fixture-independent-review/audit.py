"""Read immutable test/source/evidence Git objects; never execute product/tests."""
import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path('/workspace/e02-B-current-runtime')
BASE = 'f53842e1c635dc390f47073f6ad1526a3f2e12c5'
TARGET = '14e909cf4f5e97473a19745d7e34026b66ce41c2'
SEMANTIC = '5494f7d056ddc251107f416299db76400a96efce'
PUBLICATION = '97305720bf87c6c0c1dfd614d4e99a8acb8bf55a'
TEST = 'policy-engine/tests/unit/core/artifacts/test_multi_tenant_shared_cas.py'
FUNCTION = 'test_exact_view_import_uses_deny_only_owner_transaction_and_exact_retry'
HANDOFF = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/cas-current-exact-view-fixture.json'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)

def raw(sha, path):
    return git('show', sha + ':' + path)

def ref(sha, path):
    data = raw(sha, path)
    return {'path': path, 'source_sha': sha, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def parse(sha):
    return ast.parse(raw(sha, TEST))

a, b = parse(BASE), parse(TARGET)
fa = next(x for x in a.body if getattr(x, 'name', None) == FUNCTION)
fb = next(x for x in b.body if getattr(x, 'name', None) == FUNCTION)
old_asserts = [ast.dump(x, include_attributes=False) for x in ast.walk(fa) if isinstance(x, ast.Assert)]
new_asserts = [ast.dump(x, include_attributes=False) for x in ast.walk(fb) if isinstance(x, ast.Assert)]
setup_old = [ast.unparse(x) for x in fa.body[:3]]
setup_new = [ast.unparse(x) for x in fb.body[:4]]
fa.body, fb.body = fa.body[3:], fb.body[4:]
post_setup = ast.dump(fa, include_attributes=False) == ast.dump(fb, include_attributes=False)
a.body = [x for x in a.body if getattr(x, 'name', None) != FUNCTION]
b.body = [x for x in b.body if getattr(x, 'name', None) != FUNCTION]
others = ast.dump(a, include_attributes=False) == ast.dump(b, include_attributes=False)
format_only = ast.dump(parse(SEMANTIC), include_attributes=False) == ast.dump(parse(TARGET), include_attributes=False)
paths = git('diff', '--name-only', BASE, TARGET).decode().splitlines()
assert paths == [TEST] and post_setup and others and format_only
assert old_asserts == new_asserts and len(old_asserts) == 9 and len(fa.body) == 26
handoff = json.loads(raw(PUBLICATION, HANDOFF))
seen, bound_refs = set(), []

def walk(value):
    if isinstance(value, dict):
        if all(isinstance(value.get(k), str) for k in ('path', 'source_sha', 'sha256')) and isinstance(value.get('bytes'), int):
            key = value['source_sha'], value['path']
            if key not in seen:
                seen.add(key)
                actual = ref(*key)
                assert actual == {k: value[k] for k in actual}, actual
                bound_refs.append(actual)
        for item in value.values():
            walk(item)
    elif isinstance(value, list):
        for item in value:
            walk(item)

walk(handoff)
case_counts = []
for check in handoff['checks']:
    if 'junit' not in check:
        continue
    r = check['junit']
    cases = ET.fromstring(raw(r['source_sha'], r['path'])).findall('.//testcase')
    failures = sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
    skips = sum(c.find('skipped') is not None for c in cases)
    assert len(cases) == check['actual_cases'] and failures == check['failed'] and skips == check['skipped']
    case_counts.append({'check': check['name'], 'tests': len(cases), 'failed': failures, 'skipped': skips, 'target_sha': check['target_sha']})
    if check['name'] == 'frozen-whole-consumers':
        frozen_check = check
        frozen_cases = [{'classname': c.get('classname'), 'name': c.get('name'), 'pass': c.find('failure') is None and c.find('error') is None and c.find('skipped') is None} for c in cases]
assert frozen_check['target_sha'] == TARGET and frozen_check['target_tree'] == git('rev-parse', TARGET + '^{tree}').decode().strip()
assert len(frozen_cases) == 46 and all(c['pass'] for c in frozen_cases)
assert sum('test_scoped_import_refuses_before_any_stage_or_claim' in c['name'] for c in frozen_cases) == 12
assert git('diff', '--name-only', BASE, TARGET, '--', 'policy-engine/src') == b''
assert raw(BASE, 'policy-engine/tests/unit/core/artifacts/test_import_admission_noop.py') == raw(TARGET, 'policy-engine/tests/unit/core/artifacts/test_import_admission_noop.py')
print(json.dumps({'result': 'PASS', 'mode': 'source/evidence-only; no product or pytest execution', 'base_sha': BASE, 'target_sha': TARGET, 'target_tree': frozen_check['target_tree'], 'publication_sha': PUBLICATION, 'publication_tree': git('rev-parse', PUBLICATION + '^{tree}').decode().strip(), 'changed_tracked_paths': paths, 'source_changed_paths': [], 'ast': {'other_statements_identical': others, 'target_postsetup26_statements_identical': post_setup, 'asserts_identical': len(old_asserts), 'semantic_to_format_whole_file_identical': format_only, 'old_setup': setup_old, 'new_setup': setup_new}, 'bound_refs': bound_refs, 'bound_ref_count': len(bound_refs), 'bound_bytes': sum(r['bytes'] for r in bound_refs), 'author_check_counts_reconciled': case_counts, 'frozen_author_check': frozen_check, 'frozen_author_cases': frozen_cases, 'historical_failure_qualification': 'Baseline unbound and first for_tenant-only source remain legitimately pre-stage rejected. They do not establish product fault at the intended durable boundary; full source/context change is explicit.', 'limitation': 'No independently executed runtime here. Read/AST/hash/JUnit verification is independent;46 actual executions were performed by author at frozen target, with the recorded partial input closure.'}, indent=2) + '\n')
