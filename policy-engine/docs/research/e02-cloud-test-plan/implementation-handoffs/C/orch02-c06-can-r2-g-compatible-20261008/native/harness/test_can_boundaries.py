"""Independent actual current-G store witnesses for the declared C02/G seams."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json

import pytest

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo, WarningRecord
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.artifacts.contracts import CanonInfo as IRCanonInfo
from polisyos.ir.artifacts.io import get_json_artifact


class MappingReader:
    def __init__(self, store, artifact_id):
        self.store = store
        self.manifest = store.get_manifest(artifact_id).model_dump(mode='json')
        self.manifest_reads = self.byte_reads = 0

    def get_manifest(self, artifact_id):
        self.manifest_reads += 1
        return self.manifest

    def get_bytes(self, artifact_id):
        self.byte_reads += 1
        return self.store.get_bytes(artifact_id)


def witness(name, **values):
    print('CAN_BOUNDARY_WITNESS ' + json.dumps({'case': name, **values}, ensure_ascii=False, sort_keys=True))


def test_actual_raw_core_profile_is_not_serialization_conformance(tmp_path):
    root = tmp_path / 'raw-core'
    payload = b'{"fraction":1.5}'
    ref = FileSystemCAS(root).put_bytes(payload, ArtifactWriteOptions(
        kind='fixture.independent.raw', media_type='application/json', canon=CoreCanonInfo()))
    fresh = FileSystemCAS(root)
    reader = MappingReader(fresh, str(ref.artifact_id))
    assert reader.manifest['canon']['forbid_floats'] is True
    before = deepcopy(reader.manifest)
    loaded = get_json_artifact(reader, str(ref.artifact_id))
    assert loaded == {'fraction': 1.5} and type(loaded['fraction']) is float
    assert reader.byte_reads == reader.manifest_reads == 1
    assert reader.manifest == before and fresh.get_bytes(str(ref.artifact_id)) == payload
    witness('raw_profile_not_producer_conformance', persisted_manifest=before,
            payload_utf8=payload.decode(), payload_sha256=hashlib.sha256(payload).hexdigest(),
            typed_value={'fraction': {'type': 'float', 'value': loaded['fraction']}},
            manifest_reads=reader.manifest_reads, byte_reads=reader.byte_reads,
            disposition='same_declared_Core/IR_profile_and_provenance_class; C02/G held')


@pytest.mark.parametrize('missing_field', tuple(IRCanonInfo.model_fields))
def test_actual_raw_sidecar_missing_fields_are_materialized_by_core(tmp_path, missing_field):
    root = tmp_path / 'raw-sidecar'
    payload = {'exact': Decimal('7.250')}
    producer = FileSystemCAS(root)
    ref = producer.put_json(payload, ArtifactWriteOptions(
        kind='fixture.independent.raw-sidecar', media_type='application/json'))
    raw_path = producer._manifest_path_for_ref(ref.artifact_id, None)
    before_raw = raw_path.read_bytes()
    raw = json.loads(before_raw)
    del raw['canon'][missing_field]
    after_raw = json.dumps(raw, ensure_ascii=False, separators=(',', ':')).encode()
    raw_path.write_bytes(after_raw)
    assert missing_field not in json.loads(raw_path.read_bytes())['canon']
    fresh = FileSystemCAS(root)
    reader = MappingReader(fresh, str(ref.artifact_id))
    assert set(IRCanonInfo.model_fields) <= set(reader.manifest['canon'])
    assert reader.manifest['canon'][missing_field] == CoreCanonInfo().model_dump(mode='json')[missing_field]
    byte_before = fresh.get_bytes(str(ref.artifact_id))
    loaded = get_json_artifact(reader, str(ref.artifact_id))
    assert loaded == payload and type(loaded['exact']) is Decimal
    assert reader.manifest_reads == reader.byte_reads == 1
    assert raw_path.read_bytes() == after_raw and fresh.get_bytes(str(ref.artifact_id)) == byte_before
    witness('raw_sidecar_materialized_before_reader', missing_field=missing_field,
            raw_profile=raw['canon'], presented_complete_profile=reader.manifest['canon'],
            raw_manifest_before_sha256=hashlib.sha256(before_raw).hexdigest(),
            raw_manifest_after_sha256=hashlib.sha256(after_raw).hexdigest(),
            payload_utf8=byte_before.decode(), payload_sha256=hashlib.sha256(byte_before).hexdigest(),
            typed_value={'exact': {'type': 'Decimal', 'value': str(loaded['exact'])}},
            manifest_reads=reader.manifest_reads, byte_reads=reader.byte_reads,
            selected_view='default manifest addressed by ArtifactID, scratch-only sidecar fault',
            disposition='same_declared_manifest_view_identity_class; strict presented Mapping is not original raw-field evidence')


def test_typed_vs_mapping_write_options_warning_boundary(tmp_path):
    warning = WarningRecord(code='independent.boundary', msg='portable warning witness')
    rows = []
    for as_mapping in (False, True):
        root = tmp_path / ('mapping-options' if as_mapping else 'typed-options')
        opts = ArtifactWriteOptions(kind='fixture.independent.options', media_type='application/json', warnings=[warning])
        passed = {'kind': opts.kind, 'media_type': opts.media_type, 'warnings': [warning.model_dump(mode='python')]} if as_mapping else opts
        ref = ensure_ir_artifact_store(FileSystemCAS(root)).put_json({'value': 1}, passed)
        fresh = FileSystemCAS(root)
        reader = MappingReader(fresh, str(ref.artifact_id))
        assert len(reader.manifest['warnings']) == (0 if as_mapping else 1)
        assert get_json_artifact(reader, str(ref.artifact_id)) == {'value': 1}
        exact = fresh.get_bytes(str(ref.artifact_id))
        rows.append({'options_input': 'Mapping' if as_mapping else 'ArtifactWriteOptions',
                     'persisted_manifest': reader.manifest, 'payload_utf8': exact.decode(),
                     'payload_sha256': hashlib.sha256(exact).hexdigest(),
                     'manifest_reads': reader.manifest_reads, 'byte_reads': reader.byte_reads})
    assert rows[0]['payload_sha256'] == rows[1]['payload_sha256']
    witness('Mapping_options_warning_loss', rows=rows,
            disposition='actionable C02/G coercion-contract seam; reader does not close warning fidelity')
