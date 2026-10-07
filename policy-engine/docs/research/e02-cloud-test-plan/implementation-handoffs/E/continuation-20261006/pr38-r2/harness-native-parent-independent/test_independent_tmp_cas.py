"""Independent harness IO witness; no product numerical authority claim."""

import hashlib
import json
import os
import sys
from pathlib import Path

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def test_tmp_path_native_cas_and_fresh_integrity(tmp_path: Path) -> None:
    callback = Path(os.environ["E02_INDEPENDENT_CALLBACK"])
    callback.write_text(json.dumps({"entry_count": 1, "tmp_path": str(tmp_path)}))
    expected = Path(os.environ["E02_INDEPENDENT_BASETEMP"])
    if not (tmp_path.is_relative_to(expected)):
        raise AssertionError
    payload = {"atoms": [-2, 7], "weights": [3, 1], "label": "independent harness IO"}
    expected_raw = b'{"atoms":[-2,7],"label":"independent harness IO","weights":[3,1]}'
    expected_hash = hashlib.sha256(expected_raw).hexdigest()
    root = tmp_path / "configured-cas"
    producer = FileSystemCAS(root)
    ref = producer.put_json(
        payload,
        PutOptions(
            kind="tests.e02.independent_harness",
            media_type="application/json",
            schema=SchemaInfo(name="tests.e02.IndependentHarnessFixture", version="1"),
        ),
    )
    fresh = FileSystemCAS(root)
    raw = fresh.get_bytes(ref)
    if not (raw == expected_raw):
        raise AssertionError
    if not (hashlib.sha256(raw).hexdigest() == expected_hash == ref.artifact_id.hex):
        raise AssertionError
    if not (json.loads(raw) == payload):
        raise AssertionError
    manifest = fresh.get_manifest(ref)
    if not (manifest.kind == "tests.e02.independent_harness"):
        raise AssertionError
    if not (manifest.artifact_schema.name == "tests.e02.IndependentHarnessFixture"):
        raise AssertionError
    if not (manifest.artifact_schema.version == "1"):
        raise AssertionError
    if not (fresh.verify(ref).ok):
        raise AssertionError
    origins = {
        name: str(Path(module.__file__).resolve())
        for name, module in tuple(sys.modules.items())
        if (name == "polisyos" or name.startswith("polisyos."))
        and getattr(module, "__file__", None)
    }
    source = Path(os.environ["E02_INDEPENDENT_SOURCE_ROOT"]).resolve()
    if not (origins and all(Path(path).is_relative_to(source) for path in origins.values())):
        raise AssertionError
    result = {
        "entry_count": 1,
        "tmp_path": str(tmp_path),
        "cas_root": str(root),
        "ref": ref.model_dump(mode="json"),
        "expected_payload": payload,
        "expected_raw_sha256": expected_hash,
        "fresh_readback": True,
        "manifest_kind": manifest.kind,
        "manifest_schema": manifest.artifact_schema.model_dump(mode="json"),
        "polisyos_module_origins": origins,
    }
    callback.write_text(json.dumps(result, indent=2) + "\n")
    _write_stdout(
        json.dumps(
            {
                "independent_native_cas_readback": True,
                "content_sha256": expected_hash,
                "module_origins": len(origins),
            }
        )
    )
