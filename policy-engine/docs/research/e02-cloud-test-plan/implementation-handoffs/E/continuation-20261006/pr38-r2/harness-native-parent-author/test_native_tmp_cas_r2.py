"""Real tmp_path/CAS harness witness; no calibration or production-law claim."""

from __future__ import annotations

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


def test_real_tmp_path_cas_and_fresh_readback(tmp_path: Path) -> None:
    callback = Path(os.environ["NATIVE_CALLBACK_RECEIPT"])
    callback.write_text(json.dumps({"native_callback_count": 1, "tmp_path": str(tmp_path)}))
    expected = Path(os.environ["NATIVE_EXPECTED_BASETEMP"])
    if not (tmp_path.is_relative_to(expected)):
        raise AssertionError
    payload = {"witness": "native tmp_path -> CAS -> fresh readback", "value": 7}
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        payload,
        PutOptions(
            kind="tests.e02.native_harness",
            media_type="application/json",
            schema=SchemaInfo(name="tests.e02.NativeHarnessWitness", version="1"),
        ),
    )
    fresh = FileSystemCAS(tmp_path / "cas")
    raw = fresh.get_bytes(ref)
    if not (json.loads(raw) == payload):
        raise AssertionError
    manifest = fresh.get_manifest(ref)
    if not (manifest.kind == "tests.e02.native_harness"):
        raise AssertionError
    if not (manifest.artifact_schema.name == "tests.e02.NativeHarnessWitness"):
        raise AssertionError
    if not (manifest.integrity.sha256.removeprefix("sha256:") == hashlib.sha256(raw).hexdigest()):
        raise AssertionError
    if not (fresh.verify(ref).ok):
        raise AssertionError
    _write_stdout(
        json.dumps(
            {
                "scope": "native harness IO only",
                "ref": str(ref.artifact_id),
                "tmp_path": str(tmp_path),
                "manifest_kind": manifest.kind,
                "fresh_cas_readback": True,
            }
        )
    )
