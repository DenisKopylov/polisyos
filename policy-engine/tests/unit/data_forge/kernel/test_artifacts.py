from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts._integrity_ops import ArtifactIntegrityError
from polisyos.core.artifacts.manifest import CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.domains.legal.contracts import LexValidationError
from polisyos.data_forge.kernel import DataForgeValidationError
from polisyos.data_forge.kernel.artifacts import load_json_artifact


def _put_json(cas: FileSystemCAS, payload: object):
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    options = PutOptions(
        kind="test.data-forge.kernel-json",
        media_type="application/json",
        canon=CanonInfo.from_spec(spec),
    )
    return cas.put_json(payload, options, canon_spec=spec, return_selected_profile=True)


def test_kernel_json_loader_reads_a_real_filesystem_cas_artifact(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    ref = _put_json(cas, {"status": "candidate", "count": 2})

    assert load_json_artifact(cas, str(ref.artifact_id)) == {"status": "candidate", "count": 2}


def test_kernel_json_loader_refuses_digest_mismatch_after_real_cas_read(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    ref = _put_json(cas, {"value": "before"})
    blob_path, _manifest_path = cas._paths(ref.artifact_id)
    blob_path.write_bytes(b'{"value":"after"}')

    with pytest.raises(ArtifactIntegrityError):
        load_json_artifact(cas, str(ref.artifact_id))


@pytest.mark.parametrize(
    "error_cls",
    [DataForgeValidationError, LexValidationError],
    ids=["generic-kernel-owner", "legal-caller-override"],
)
def test_kernel_json_loader_rejects_non_object_payload_with_selected_error_owner(
    tmp_path: Path,
    error_cls: type[Exception],
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    ref = _put_json(cas, ["not", "an", "object"])

    with pytest.raises(error_cls, match="payload must be a JSON object"):
        load_json_artifact(cas, str(ref.artifact_id), error_cls=error_cls)


def test_kernel_json_loader_can_wrap_a_real_cas_read_error_with_cause(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    missing_id = "sha256:" + "a" * 64

    with pytest.raises(DataForgeValidationError) as raised:
        load_json_artifact(
            cas,
            missing_id,
            payload_label="fixture",
            wrap_read_errors=True,
            read_error_prefix="failed to read",
        )

    assert str(raised.value).startswith(f"failed to read {missing_id}: ")
    assert isinstance(raised.value.__cause__, FileNotFoundError)
