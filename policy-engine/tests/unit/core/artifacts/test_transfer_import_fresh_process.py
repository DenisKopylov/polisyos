"""Exercise an imported selected view through an independent CAS process."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo

PAYLOAD = b"a persisted import must survive a new reader process"
_READ_SCRIPT = """
import json
import sys
from pathlib import Path

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS

store = FileSystemCAS(Path(sys.argv[1]), tenant_id="tenant-b", cell_id="cell-a")
ref = ArtifactRef.model_validate_json(sys.argv[2])
report = store.verify(ref)
read_error = None
try:
    data = store.get_bytes(ref)
except Exception as error:
    data = None
    read_error = type(error).__name__
print(json.dumps({
    "verify_ok": report.ok,
    "data_hex": data.hex() if data is not None else None,
    "read_error": read_error,
    "manifest_hex": store.get_manifest_bytes(ref).hex(),
}, sort_keys=True))
"""


def _fresh_process_read(root: Path, ref: ArtifactRef) -> dict[str, object]:
    """Read one selected artifact from a new process and return its observation."""
    result = subprocess.run(
        [sys.executable, "-c", _READ_SCRIPT, str(root), ref.model_dump_json()],
        cwd=Path(__file__).parents[4],
        capture_output=True,
        check=True,
        text=True,
        timeout=20,
    )
    return json.loads(result.stdout)


def test_imported_view_survives_fresh_process_and_rejects_disk_corruption(
    tmp_path: Path,
) -> None:
    """A fresh CAS process reads imported bytes and refuses a corrupted blob."""
    options = PutOptions(
        kind="tests.cas.import.fresh_process",
        media_type="application/octet-stream",
        tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-b", cell_id="cell-a"),
    )
    producer = FileSystemCAS(tmp_path / "producer", tenant_id="tenant-b", cell_id="cell-a")
    produced_ref = producer.put_bytes(PAYLOAD, options)
    original_manifest = producer.get_manifest_bytes(produced_ref)
    bundle = producer.export_subgraph([produced_ref], tmp_path / "bundle", compress=False)

    target_root = tmp_path / "target"
    target = FileSystemCAS(target_root, tenant_id="tenant-b", cell_id="cell-a")
    imported = target.import_subgraph(bundle.output_path, verify_integrity=True)
    assert imported.verification_failed == []
    selected_ref = next(
        ref for ref in imported.imported_refs if ref.artifact_id == produced_ref.artifact_id
    )
    assert target.get_manifest_bytes(selected_ref) == original_manifest

    healthy = _fresh_process_read(target_root, selected_ref)
    assert healthy == {
        "data_hex": PAYLOAD.hex(),
        "manifest_hex": original_manifest.hex(),
        "read_error": None,
        "verify_ok": True,
    }

    blob_path = (
        target_root
        / "artifacts"
        / "sha256"
        / produced_ref.artifact_id.hex[:2]
        / produced_ref.artifact_id.hex[2:4]
        / f"{produced_ref.artifact_id.hex}.blob"
    )
    blob_path.write_bytes(b"corrupted content with a different digest")
    corrupted = _fresh_process_read(target_root, selected_ref)
    assert corrupted["verify_ok"] is False
    assert corrupted["data_hex"] is None
    assert corrupted["read_error"] == "ArtifactIntegrityError"
    assert corrupted["manifest_hex"] == original_manifest.hex()
