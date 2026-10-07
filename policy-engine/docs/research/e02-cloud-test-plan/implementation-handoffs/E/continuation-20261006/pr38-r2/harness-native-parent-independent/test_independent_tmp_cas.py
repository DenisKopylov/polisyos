"""Independent harness IO witness; no product numerical authority claim."""
import hashlib
import json
import os
from pathlib import Path
import sys

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo


def test_tmp_path_native_cas_and_fresh_integrity(tmp_path):
    callback = Path(os.environ['E02_INDEPENDENT_CALLBACK'])
    callback.write_text(json.dumps({'entry_count':1,'tmp_path':str(tmp_path)}))
    expected = Path(os.environ['E02_INDEPENDENT_BASETEMP'])
    assert tmp_path.is_relative_to(expected)
    payload = {'atoms':[-2,7], 'weights':[3,1], 'label':'independent harness IO'}
    expected_raw = b'{"atoms":[-2,7],"label":"independent harness IO","weights":[3,1]}'
    expected_hash = hashlib.sha256(expected_raw).hexdigest()
    root = tmp_path / 'configured-cas'
    producer = FileSystemCAS(root)
    ref = producer.put_json(payload, PutOptions(kind='tests.e02.independent_harness', media_type='application/json', schema=SchemaInfo(name='tests.e02.IndependentHarnessFixture',version='1')))
    fresh = FileSystemCAS(root)
    raw = fresh.get_bytes(ref)
    assert raw == expected_raw
    assert hashlib.sha256(raw).hexdigest() == expected_hash == ref.artifact_id.hex
    assert json.loads(raw) == payload
    manifest = fresh.get_manifest(ref)
    assert manifest.kind == 'tests.e02.independent_harness'
    assert manifest.artifact_schema.name == 'tests.e02.IndependentHarnessFixture'
    assert manifest.artifact_schema.version == '1'
    assert fresh.verify(ref).ok
    origins = {name:str(Path(module.__file__).resolve()) for name,module in tuple(sys.modules.items()) if (name=='polisyos' or name.startswith('polisyos.')) and getattr(module,'__file__',None)}
    source = Path(os.environ['E02_INDEPENDENT_SOURCE_ROOT']).resolve()
    assert origins and all(Path(path).is_relative_to(source) for path in origins.values())
    result = {'entry_count':1,'tmp_path':str(tmp_path),'cas_root':str(root),'ref':ref.model_dump(mode='json'),'expected_payload':payload,'expected_raw_sha256':expected_hash,'fresh_readback':True,'manifest_kind':manifest.kind,'manifest_schema':manifest.artifact_schema.model_dump(mode='json'),'polisyos_module_origins':origins}
    callback.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'independent_native_cas_readback':True,'content_sha256':expected_hash,'module_origins':len(origins)}))
