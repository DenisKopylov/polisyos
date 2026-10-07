"""Independent process consumer for direct CAS duplicate publication."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactIntegrityError, FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo

_PAYLOAD = b"independent direct put consumer record"
_CHILD = r"""
import json, sys
from pathlib import Path
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactRef
import polisyos.core.artifacts.store as source
assert Path(source.__file__).resolve().is_relative_to(Path(sys.argv[2]))
ref = ArtifactRef.model_validate_json(sys.stdin.read())
store = FileSystemCAS(Path(sys.argv[1]))
data = store.get_bytes(ref)
manifest = store.get_manifest(ref)
print(json.dumps({"bytes": data.hex(), "kind": manifest.kind,
                  "size": manifest.byte_size, "verified": store.verify(ref).ok}))
"""


@pytest.mark.parametrize("damage", ["same_size", "short"])
def test_damaged_duplicate_put_is_refused_before_fresh_process_retry_consumer(
    tmp_path: Path,
    damage: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    opts = PutOptions(
        kind="tests.independent.put",
        media_type="application/octet-stream",
        schema=SchemaInfo(name="tests.independent.put", version="1"),
        producer=ProducerInfo(component="independent.consumer", version="1"),
    )
    ref = store.put_bytes(_PAYLOAD, opts)
    blob, manifest_path = store._paths(ref.artifact_id)
    manifest_before = manifest_path.read_bytes()
    bad = b"?" * len(_PAYLOAD) if damage == "same_size" else b"short"
    blob.write_bytes(bad)
    if os.environ.get("E02_B_PROPERTY_REMOVAL") == "cas-put-digest":
        import hashlib

        from polisyos.core.artifacts import ownership
        from polisyos.core.artifacts import store as source

        real_hash = source._file_content_hash
        real_owner_hash = ownership._file_sha256

        monkeypatch.setattr(
            "polisyos.core.artifacts.store._file_content_hash",
            lambda target: (
                hashlib.sha256(_PAYLOAD).hexdigest() if target == blob else real_hash(target)
            ),
        )
        # Publication independently reconciles the same persisted blob again.
        # Remove that byte predicate too, preserving every manifest and owner
        # check, so this control removes the property across its full put path.
        monkeypatch.setattr(
            "polisyos.core.artifacts.ownership._file_sha256",
            lambda target: (
                "sha256:" + hashlib.sha256(_PAYLOAD).hexdigest()
                if target == blob
                else real_owner_hash(target)
            ),
        )
    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        store.put_bytes(_PAYLOAD, opts)
    assert blob.read_bytes() == bad
    assert manifest_path.read_bytes() == manifest_before
    # An independently retained operator copy supplies repair bytes; a put
    # rejection is not permission to fabricate recovery provenance.
    quarantine = tmp_path / "refused-blob.bin"
    quarantine.write_bytes(bad)
    blob.write_bytes(_PAYLOAD)
    retry = store.put_bytes(_PAYLOAD, opts)
    assert retry == ref
    source_root = Path(__file__).resolve().parents[4] / "src"
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, str(store.root), str(source_root)],
        input=retry.model_dump_json(),
        env={**os.environ, "PYTHONPATH": str(source_root)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {
        "bytes": _PAYLOAD.hex(),
        "kind": opts.kind,
        "size": len(_PAYLOAD),
        "verified": True,
    }
    assert quarantine.read_bytes() == bad
