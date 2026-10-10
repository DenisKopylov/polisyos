from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import CanonInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.artifacts.io import get_json_artifact
from polisyos.ir.model_layer.canon import (
    CanonSpec,
    CanonViolation,
    from_canonical_bytes,
    to_canonical_bytes,
)


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


def main() -> None:
    with TemporaryDirectory(prefix="can-options-") as temporary:
        root = Path(temporary) / "cas"
        store = FileSystemCAS(root)
        exact_bytes = b'{"fraction":1.5}'
        ref = store.put_bytes(
            exact_bytes,
            ArtifactWriteOptions(
                kind="prototype.raw-profile",
                media_type="application/json",
                canon=CanonInfo(forbid_floats=True),
            ),
        )
        sidecar = store._manifest_path_for_ref(ref.artifact_id, None)
        raw_manifest = json.loads(store.get_manifest_bytes(ref))
        raw_manifest["canon"].pop("max_depth")
        sidecar.write_text(json.dumps(raw_manifest, separators=(",", ":")), encoding="utf-8")
        raw_after = json.loads(store.get_manifest_bytes(ref))
        materialized = store.get_manifest(ref).canon
        decoded = get_json_artifact(ensure_ir_artifact_store(store), ref.artifact_id)
        _emit(
            {
                "sidecar_raw_missing_max_depth": "max_depth" not in raw_after["canon"],
                "typed_manifest_filled_max_depth": materialized.max_depth,
                "reader_accepted_incomplete_raw_profile": decoded == {"fraction": 1.5},
                "reader_accepted_numeric_float_under_forbid_floats": isinstance(
                    decoded["fraction"], float
                ),
                "payload_bytes_preserved": store.get_bytes(ref) == exact_bytes,
            }
        )

        value = from_canonical_bytes(exact_bytes)
        try:
            to_canonical_bytes(value, CanonSpec(forbid_floats=True))
        except CanonViolation as exc:
            _emit({"profile_reencoder_refuses": str(exc)})
        else:
            raise AssertionError("forbid_floats unexpectedly re-encoded a plain numeric float")

        tag_ref = FileSystemCAS(root).put_json(
            {"_type": "float_hex", "value": "0x1.8p+1"},
            ArtifactWriteOptions(kind="prototype.core-tag", media_type="application/json"),
        )
        try:
            get_json_artifact(ensure_ir_artifact_store(FileSystemCAS(root)), tag_ref.artifact_id)
        except CanonViolation as exc:
            _emit({"same_name_version_core_tag_refused": str(exc)})
        else:
            raise AssertionError("IR reader unexpectedly accepted a Core-only tag")

        profileless_ref = FileSystemCAS(root).put_bytes(
            b'{"historical":true}',
            ArtifactWriteOptions(kind="prototype.profileless", media_type="application/json"),
        )
        try:
            get_json_artifact(
                ensure_ir_artifact_store(FileSystemCAS(root)), profileless_ref.artifact_id
            )
        except CanonViolation as exc:
            _emit({"profileless_history_refused": str(exc)})
        else:
            raise AssertionError("IR reader unexpectedly admitted a profile-less artifact")


if __name__ == "__main__":
    main()
