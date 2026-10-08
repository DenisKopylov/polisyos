"""List all actual derived-value update sites, without editing repository files."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/workspace/e02-F-economics-20261006')
OUT = Path(__file__).parent
REF = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
BASE = 'policy-engine/docs/research/e02-cloud-test-plan/'
TRANSFER = BASE + 'implementation-handoffs/F/continuation-transfer-20261007/'
CURRENT = [TRANSFER + n for n in ['index.json', 'full-audit.json', 'REPORT.md',
                                 'G-local-causal-reruns.json', 'G-source-integration-order.json']]
CURRENT += [BASE + 'closure-decisions/' + n for n in ['F.md', 'method-decisions.md', 'runtime-profiles.md']]
CURRENT += [BASE + 'implementation-handoffs/F/continuation-closeout-20261007.json',
            BASE + 'implementation-handoffs/F/continuation-closeout-20261007/README.md']
AFFECTED = ['B204', 'B212', 'B213', 'B214', 'B218', 'B56', 'LA-037']
json_locs, doc_locs, source = [], [], []

def document_role(path):
    if '/continuation-closeout-20261007' in path:
        return 'frozen closeout evidence carrier: preserve literal; new slice cross-links/supersedes by Git ref'
    return 'current operating ledger/view: update only affected recommendation/binding fields'

def escape(k):
    return str(k).replace('~', '~0').replace('/', '~1')

def visit(value, path, owner):
    if isinstance(value, dict):
        if isinstance(value.get('finding_id'), str) and value['finding_id'] in AFFECTED:
            json_locs.append({'document': owner, 'pointer': path or '/', 'role': 'affected-ID-object',
                              'finding_id': value['finding_id'], 'keys': list(value)})
        for k, v in value.items():
            visit(v, path + '/' + escape(k), owner)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            visit(v, path + '/' + str(i), owner)
    elif isinstance(value, str):
        if ('continuation-transfer-20261007/' in value or
            any(x in value for x in AFFECTED) or
            any(x in value for x in ['source519_scanner', 'FAIL103', 'FAIL38', 'not_established'])):
            json_locs.append({'document': owner, 'pointer': path, 'role': 'dependent-reference-or-caption',
                              'value': value})

for path in CURRENT:
    p = subprocess.run(['git', 'show', REF + ':' + path], cwd=ROOT, capture_output=True)
    assert p.returncode == 0, p.stderr.decode()
    b = p.stdout
    source.append({'git_ref': REF, 'path': path, 'bytes': len(b), 'role': document_role(path),
                   'sha256': hashlib.sha256(b).hexdigest()})
    if path.endswith('.json'):
        visit(json.loads(b), '', path)
    else:
        for i, line in enumerate(b.decode().splitlines(), 1):
            if (any(x in line for x in AFFECTED) or 'continuation-transfer-20261007' in line or
                any(x in line for x in ['33', '35', '519e', 'formal', '103', '38', 'P41', 'scanner'])):
                doc_locs.append({'document': path, 'line': i, 'text': line,
                                 'role': 'current-caption-or-link; preserve explicit historical quotations'})

grep = subprocess.run(['git', 'grep', '-l', '-e', 'continuation-transfer-20261007/index.json',
                       '-e', 'continuation-transfer-20261007/full-audit.json',
                       '-e', 'continuation-transfer-20261007/per-ID/B214.json', REF, '--', '*.json', '*.md'],
                      cwd=ROOT, capture_output=True)
assert grep.returncode == 0
all_refs = []
for text in grep.stdout.decode().splitlines():
    _, path = text.split(':', 1)
    all_refs.append({'path': path, 'role': document_role(path) if path in CURRENT else
                     'immutable review/negative/template snapshot; do not rewrite as current ledger'})

for loc in json_locs + doc_locs:
    loc['document_role'] = document_role(loc['document'])

(OUT / 'full-dependent-footprint.json').write_text(json.dumps({
    'source_ref': REF, 'read_only': True, 'sources': source,
    'json_locators': json_locs, 'document_locators': doc_locs,
    'all_tracked_reference_carriers': all_refs,
    'update_rule': 'New current ledger/ref bindings replace only current views. Frozen closeout receipts and raw '
                   'review/negative/template companions retain byte identity and receive explicit supersession links.'
}, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'current_documents': len(source), 'json_locators': len(json_locs),
                  'doc_locators': len(doc_locs), 'all_tracked_reference_carriers': len(all_refs)}))
