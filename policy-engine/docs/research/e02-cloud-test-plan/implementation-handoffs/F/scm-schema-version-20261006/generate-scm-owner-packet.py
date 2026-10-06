"""Run the existing canonical generator, then apply/check only the admitted SCM owner packet."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from tools.quality.diagnostics import gen_schema as generator
from tools.quality.diagnostics import generate_ir_reference_catalog as reference

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
root = Path('/workspace/e02-F-graph-20261006/policy-engine')
scratch = Path('/tmp/e02-F-continuation-20261006/graph/scm-version-generated')
scratch.mkdir(exist_ok=True)
reference.IR_REFERENCE_PATH = scratch / 'schema-catalog.md'
reference.SCHEMA_REFERENCE_PATH = scratch / 'schemas.md'
command = ['--models', 'structural_causal_model_spec', '--output-dir', str(scratch / 'snapshots'), '--cache-dir', str(scratch / 'generator-cache')]
code = generator.main(command)
if code:
    raise SystemExit(code)
key = 'structural_causal_model_spec'
selected = json.loads((scratch / 'snapshots/ir/_manifest.json').read_text())['models'][key]
actual_snapshot = root / 'schemas/snapshots/ir/structural_causal_model_spec.schema.json'
expected_snapshot = (scratch / 'snapshots/ir/structural_causal_model_spec.schema.json').read_bytes()
actual_manifest = root / 'schemas/snapshots/ir/_manifest.json'
original_manifest_bytes = actual_manifest.read_bytes()
original_manifest = json.loads(original_manifest_bytes)
merged_models = {**original_manifest['models'], key: selected}
manifest_text = original_manifest_bytes.decode()
entry_pattern = r'^    "structural_causal_model_spec": \{\n.*?^    \}(,?)$'
entry_match = re.search(entry_pattern, manifest_text, flags=re.M | re.S)
assert entry_match is not None
block = '\n'.join('  ' + line for line in json.dumps({key: selected}, indent=2, sort_keys=True).splitlines()[1:-1]) + entry_match.group(1)
new_manifest_text = manifest_text[:entry_match.start()] + block + manifest_text[entry_match.end():]
new_manifest_text, count = re.subn(r'"content_hash": "[0-9a-f]{64}"', '"content_hash": "' + generator._schema_hash(merged_models) + '"', new_manifest_text)
assert count == 1
new_manifest = json.loads(new_manifest_text)
assert new_manifest['models'] == merged_models
assert {k:v for k,v in original_manifest.items() if k not in ['models','content_hash']} == {k:v for k,v in new_manifest.items() if k not in ['models','content_hash']}
header = '### `polisyos.ir.analytics.structural_causal_model.StructuralCausalModelSpec` '
def scm_section(text):
    start = text.index(header)
    end = text.find('\n### ', start + len(header))
    return text[start:end if end >= 0 else len(text)]
actual_catalog = root / 'docs/reference/ir/schema-catalog.md'
actual_schemas = root / 'docs/reference/schemas.md'
old_catalog = actual_catalog.read_text()
new_section = scm_section(reference.IR_REFERENCE_PATH.read_text())
old_section = scm_section(old_catalog)
new_catalog = old_catalog.replace(old_section, new_section, 1)
old_schemas = actual_schemas.read_text()
row_prefix = '| `structural_causal_model_spec` |'
old_row = next(line for line in old_schemas.splitlines() if line.startswith(row_prefix))
new_row = next(line for line in reference.SCHEMA_REFERENCE_PATH.read_text().splitlines() if line.startswith(row_prefix))
new_schemas = old_schemas.replace(old_row, new_row, 1)
updates = [(actual_snapshot, expected_snapshot), (actual_manifest, new_manifest_text.encode()), (actual_catalog, new_catalog.encode()), (actual_schemas, new_schemas.encode())]
inputs=[]
for path,expected in updates:
    old = path.read_bytes()
    inputs.append({'path':str(path.relative_to(root)), 'read_bytes':len(old), 'read_sha256':hashlib.sha256(old).hexdigest(), 'canonical_owner_packet_bytes':len(expected), 'canonical_owner_packet_sha256':hashlib.sha256(expected).hexdigest(), 'equal_before':old == expected})
    if args.apply:
        path.write_bytes(expected)
    else:
        assert old == expected, path
nonowner = {'schema_catalog_full_equivalence':new_catalog == reference.IR_REFERENCE_PATH.read_text(), 'schema_reference_full_equivalence':new_schemas == reference.SCHEMA_REFERENCE_PATH.read_text(), 'interpretation':'Full canonical references generated/read; only the approved SCM section/row is applied. Any full-document drift is separate and not attributed as inherited.'}
report = {'canonical_generator':str(Path(generator.__file__)), 'argv':command, 'generator_exit_code':code, 'selected_abi_entries':[key], 'apply':args.apply, 'inputs':inputs, 'manifest_other_entries_retained':len(original_manifest['models']) - 1, 'manifest_header_retained':True, 'canonical_full_reference_outputs':[str(reference.IR_REFERENCE_PATH),str(reference.SCHEMA_REFERENCE_PATH)], 'non_owner_reference_scope':nonowner, 'owner_packet_check':'PASS'}
(scratch/'owner-packet.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
