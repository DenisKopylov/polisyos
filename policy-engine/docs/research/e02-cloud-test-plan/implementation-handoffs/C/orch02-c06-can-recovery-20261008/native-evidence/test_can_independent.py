from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation


class MappingReader:
    def __init__(self,store,manifest):
        self.store,self.manifest=store,manifest
        self.byte_reads=0

    def get_manifest(self,artifact_id):
        return self.manifest

    def get_bytes(self,artifact_id):
        self.byte_reads+=1
        return self.store.get_bytes(artifact_id)


def test_real_cas_nondefault_separators_decimal_and_unicode(tmp_path):
    store=FileSystemCAS(tmp_path/'cas')
    payload={'amount':Decimal('12.30'),'label':'путь'}
    ref=put_json_artifact(ensure_ir_artifact_store(store),payload,kind='test.independent',schema_name='test.independent',schema_version='1',canon_spec=CanonSpec(separators=(', ',': '),ensure_ascii=True))
    expected=json.dumps({'amount':{'_type':'decimal','value':'12.30'},'label':'путь'},sort_keys=True,separators=(', ',': '),ensure_ascii=True).encode()
    assert store.get_bytes(ref['artifact_id'])==expected
    assert ref['artifact_id']=='sha256:'+sha256(expected).hexdigest()
    fresh=FileSystemCAS(tmp_path/'cas')
    mapping=fresh.get_manifest(ref['artifact_id']).model_dump(mode='json')
    before=deepcopy(mapping)
    assert mapping['canon']['separators']==[', ',': ']
    reader=MappingReader(fresh,mapping)
    assert get_json_artifact(reader,ref['artifact_id'])==payload
    assert reader.byte_reads==1
    assert mapping==before


@pytest.mark.parametrize('tag',[{'_type':'float_hex','value':'0x1.4000000000000p+0'},{'_type':'bytes_hex','value':'6162'},{'_type':'array_digest','dtype':'float64','shape':[1],'sha256':'0'*64}])
def test_declared_raw_core_bypass_has_same_profile_but_ir_tag_rejection_after_bytes(tmp_path,tag):
    store=FileSystemCAS(tmp_path/'cas')
    ref=store.put_json({'value':tag},PutOptions(kind='test.core-bypass',media_type='application/json'))
    fresh=FileSystemCAS(tmp_path/'cas')
    manifest=fresh.get_manifest(ref.artifact_id).model_dump(mode='json')
    assert manifest['canon']['name']=='polisyos.canon.json'
    assert manifest['canon']['version']=='0.2.0'
    reader=MappingReader(fresh,manifest)
    with pytest.raises(CanonViolation,match='Unknown canonical _type'):
        get_json_artifact(reader,ref.artifact_id)
    assert reader.byte_reads==1
