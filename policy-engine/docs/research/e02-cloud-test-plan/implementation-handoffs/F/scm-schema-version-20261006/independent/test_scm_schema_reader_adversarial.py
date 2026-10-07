"""Independent public CAS reader adversaries for current versus historical SCM wire versions."""

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.analytics.structural_causal_model import (
    StructuralCausalModelSpec,
    load_structural_causal_model_spec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.registry.refs import StructuralCausalModelSpecRef


def persist_raw(store, payload, envelope_version):
    raw = store.put_json(payload, PutOptions(kind='ir.structural_causal_model_spec', media_type='application/json',
                         schema=SchemaInfo(name='ir.structural_causal_model_spec', version=envelope_version)),
                         canon_spec=CanonSpec(forbid_floats=False))
    return StructuralCausalModelSpecRef.model_validate(raw.model_dump(mode='json'))


@pytest.mark.parametrize('payload_version', ['missing', '1.0'])
def test_legacy_gcm_marker_never_inherits_new_worker_records_or_wire_version(tmp_path, payload_version):
    model = StructuralCausalModelSpec(schema_version='1.0', graph=CausalGraphModel(graph_type=GraphType.DAG, nodes=['X'], edges=[]), fit_method='gcm', fitted=True)
    payload = model.model_dump(mode='json')
    if payload_version == 'missing':
        payload.pop('schema_version')
    store = FileSystemCAS(tmp_path)
    original_ref = persist_raw(store, payload, '1.0')
    original_payload = get_json_artifact(store, original_ref.artifact_id)
    loaded = load_structural_causal_model_spec(FileSystemCAS(tmp_path), original_ref)
    assert loaded.schema_version == '1.0'
    assert loaded.fit_method == 'gcm' and loaded.training_rows is None and loaded.fit_provenance is None
    # Historical fit marker is no newly observed backend witness. Native read must leave the original immutable CAS payload intact.
    assert get_json_artifact(store, original_ref.artifact_id) == original_payload
    rewritten = persist_structural_causal_model_spec(store, loaded)
    fresh = load_structural_causal_model_spec(FileSystemCAS(tmp_path), rewritten)
    assert fresh == loaded and store.get_manifest(rewritten.artifact_id).artifact_schema.version == '1.0'
    assert persist_structural_causal_model_spec(FileSystemCAS(tmp_path), fresh).artifact_id == rewritten.artifact_id


@pytest.mark.parametrize(('payload_version','envelope_version'), [('missing','1.1'),('1.0','1.1'),('1.1','1.0'),('1.2','1.2'),('2.0','2.0')])
def test_wrong_or_future_real_cas_wire_versions_fail_closed(tmp_path, payload_version, envelope_version):
    model = StructuralCausalModelSpec(graph=CausalGraphModel(graph_type=GraphType.DAG,nodes=['X'],edges=[]),fit_method='manual')
    payload = model.model_dump(mode='json')
    if payload_version == 'missing':
        payload.pop('schema_version')
    else:
        payload['schema_version'] = payload_version
    store = FileSystemCAS(tmp_path)
    ref = persist_raw(store,payload,envelope_version)
    with pytest.raises(ValueError, match='SCM artifact requires a supported CAS schema manifest|SCM payload and CAS schema versions differ'):
        load_structural_causal_model_spec(FileSystemCAS(tmp_path),ref)


def test_current_wire_gcm_marker_without_real_records_is_rejected_after_cas(tmp_path):
    payload = StructuralCausalModelSpec(graph=CausalGraphModel(graph_type=GraphType.DAG,nodes=['X'],edges=[]),fit_method='manual').model_dump(mode='json')
    payload.update(fit_method='gcm',fitted=True)
    store=FileSystemCAS(tmp_path)
    ref=persist_raw(store,payload,'1.1')
    with pytest.raises(ValueError,match='selected GCM fit requires training rows and observed worker provenance'):
        load_structural_causal_model_spec(FileSystemCAS(tmp_path),ref)


def test_future_constructor_cannot_persist_unsupported_wire_version(tmp_path):
    model=StructuralCausalModelSpec(schema_version='1.2',graph=CausalGraphModel(graph_type=GraphType.DAG,nodes=['X'],edges=[]),fit_method='manual')
    with pytest.raises(ValueError,match='SCM payload and supported CAS schema versions must match'):
        persist_structural_causal_model_spec(FileSystemCAS(tmp_path),model)
