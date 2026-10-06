"""Read-only canonical SCM owner audit and native drift discriminators."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from polisyos.ir.migrations.base import negotiate_schema_version
from tools.quality.diagnostics import gen_schema as gen
from tools.quality.diagnostics import generate_ir_reference_catalog as ref

ROOT = Path('/workspace/e02-F-graph-20261006')
CWD = ROOT / 'policy-engine'
SCRATCH = Path('/tmp/e02-F-continuation-20261006/foundry/schema-review')
SHA = 'eaf9d0e0ee2dae728351cbb3dfc333474c88931b'
KEY = 'structural_causal_model_spec'
SNAPSHOT = CWD / 'schemas/snapshots/ir/structural_causal_model_spec.schema.json'
MANIFEST = CWD / 'schemas/snapshots/ir/_manifest.json'


def data_at(sha, path):
    return subprocess.check_output(['git', 'show', f'{sha}:{path}'], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def section(text):
    prefix = '### `polisyos.ir.analytics.structural_causal_model.StructuralCausalModelSpec` '
    start = text.index(prefix)
    end = text.find('\n### ', start + len(prefix))
    return text[start:end if end >= 0 else len(text)]


def main():
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
    mode = sys.argv[1]
    resolved = gen._resolve_entry(gen.select_abi_entries([KEY])[0])
    actual_payload = gen._load_or_generate_entry_payload(resolved, cache_root=None, pydantic_version=gen._import_version('pydantic'))
    schema_text = gen._json_dump(actual_payload['schema_payload'], fmt='pretty')
    actual_manifest = json.loads(MANIFEST.read_text())
    expected_manifest = copy.deepcopy(actual_manifest)
    entry = expected_manifest['models'][KEY]
    for name in ('schema_version', 'sha256_full', 'sha256_semantic'):
        entry[name] = actual_payload[name]
    expected_manifest['content_hash'] = gen._schema_hash(expected_manifest['models'])
    errors = []
    if mode == 'audit':
        gen._assert_file_equals(SNAPSHOT, schema_text, errors)
        gen._assert_manifest_equals(MANIFEST, expected_manifest, errors)
        assert not errors, errors
        paths = subprocess.check_output(['git', 'diff', '--name-only', SHA + '^', SHA], cwd=ROOT, text=True).splitlines()
        assert len(paths) == 10
        before = json.loads(data_at(SHA + '^', str(MANIFEST.relative_to(ROOT))))
        assert len(before['models']) == len(actual_manifest['models']) == 99
        assert {k:v for k,v in before['models'].items() if k != KEY} == {k:v for k,v in actual_manifest['models'].items() if k != KEY}
        assert {k:v for k,v in before.items() if k not in ('models','content_hash')} == {k:v for k,v in actual_manifest.items() if k not in ('models','content_hash')}
        before_snapshot = json.loads(data_at(SHA + '^', str(SNAPSHOT.relative_to(ROOT))))
        only_default = copy.deepcopy(before_snapshot)
        only_default['properties']['schema_version']['default'] = '1.1'
        assert only_default == json.loads(SNAPSHOT.read_text())
        output = SCRATCH / 'canonical-generated'
        ref.IR_REFERENCE_PATH = output / 'schema-catalog.md'
        ref.SCHEMA_REFERENCE_PATH = output / 'schemas.md'
        command = ['--models', KEY, '--output-dir', str(output / 'snapshots'), '--cache-dir', str(output / 'cache')]
        assert gen.main(command) == 0
        # Compare complete owner section/row. Do not copy generated full documents into Git evidence.
        generated_section = section(ref.IR_REFERENCE_PATH.read_text())
        actual_catalog_path = CWD / 'docs/reference/ir/schema-catalog.md'
        assert section(actual_catalog_path.read_text()) == generated_section
        old_catalog = data_at(SHA + '^', str(actual_catalog_path.relative_to(ROOT))).decode()
        assert actual_catalog_path.read_text() == old_catalog.replace(section(old_catalog), generated_section, 1)
        actual_schemas_path = CWD / 'docs/reference/schemas.md'
        old_schemas = data_at(SHA + '^', str(actual_schemas_path.relative_to(ROOT))).decode()
        prefix = '| `structural_causal_model_spec` |'
        row = next(x for x in ref.SCHEMA_REFERENCE_PATH.read_text().splitlines() if x.startswith(prefix))
        old_row = next(x for x in old_schemas.splitlines() if x.startswith(prefix))
        assert actual_schemas_path.read_text() == old_schemas.replace(old_row, row, 1)
        directions = []
        for producer, consumer, readable in [('1.0','1.1',True),('1.1','1.0',False),('1.2','1.1',False),('1.2','1.0',False),('2.0','1.1',False),('1.0','1.2',False)]:
            decision = negotiate_schema_version(KEY, producer, consumer)
            assert decision.can_read is readable and not decision.migration_required
            directions.append({'producer':producer,'consumer':consumer,'can_read':decision.can_read,'reason':decision.reason})
        result = {'source_sha':SHA,'mode':mode,'outcome':'PASS','changed_paths':paths,'canonical_runtime_snapshot_equal':True,'selected_manifest_entry_equal':True,'complete_manifest_other_entries_retained':98,'manifest_header_unchanged':True,'snapshot_only_default_changed':True,'generated_owner_docs_section_and_row_equal':True,'all_other_doc_bytes_retained':True,'schema_directions':directions,'generator_argv':command,'source_writes':False}
    else:
        real_read = Path.read_text
        target = SNAPSHOT if mode == 'snapshot_old_default' else MANIFEST
        mutated = json.loads(target.read_text())
        if mode == 'snapshot_old_default':
            mutated['properties']['schema_version']['default'] = '1.0'
        elif mode == 'manifest_old_version':
            mutated['models'][KEY]['schema_version'] = '1.0'
        elif mode == 'manifest_stale_hash':
            mutated['models'][KEY]['sha256_full'] = '0' * 64
        else:
            raise ValueError(mode)
        retained = target.read_bytes()
        def drift(path, *args, **kwargs):
            return json.dumps(mutated, indent=2, sort_keys=True) + '\n' if path == target else real_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', drift):
            if target == SNAPSHOT:
                gen._assert_file_equals(target, schema_text, errors)
            else:
                gen._assert_manifest_equals(target, expected_manifest, errors)
        assert errors and target.read_bytes() == retained
        result = {'source_sha':SHA,'mode':mode,'outcome':'FAIL','expected_rejection_met':True,'canonical_check_errors':errors,'property_removed':'current default/version/native-schema digest','markers_retained':'schema names, field names, model keys, original provider code, other98 manifest entries','source_writes':False,'target_path':str(target.relative_to(ROOT)),'original_source_sha256':digest(retained)}
    print(json.dumps(result, indent=2))
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)
    raise SystemExit(0 if mode == 'audit' else 1)


if __name__ == '__main__':
    main()
