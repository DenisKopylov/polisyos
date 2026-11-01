"""Fresh-interpreter CAS custody and process-interruption fixture worker."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.signing import Ed25519Verifier, KeyPair, SigningConfig
from polisyos.core.artifacts.store import ArtifactTransactionPendingError, FileSystemCAS, PutOptions


def _options(request: dict[str, Any]) -> PutOptions:
    return PutOptions(
        kind="cas.restart.interrupted",
        media_type="text/plain",
        schema=SchemaInfo(name="cas.restart.interrupted", version="1"),
        producer=ProducerInfo(component="tests.cas01", version="1.0"),
        inputs=[InputRef.model_validate(request["basis"])],
    )


def _install_interruption(store: FileSystemCAS, boundary: str, phase: str) -> None:
    """Exit at a real publication call or matching file/directory fsync syscall."""
    original_publish = store._publish_transaction_member
    original_fsync = os.fsync

    def stop() -> None:
        print(json.dumps({"cut": boundary, "phase": phase, "pid": os.getpid()}), flush=True)
        os._exit(73)

    def publish(stage_path, final_path, *, expected_sha256):
        selected = (
            (boundary == "blob" and final_path.suffix == ".blob")
            or (
                boundary == "default"
                and final_path.name.endswith(".manifest.json")
                and ".view." not in final_path.name
            )
            or (boundary == "view" and ".view." in final_path.name)
        )
        if selected and phase == "before":
            stop()
        result = original_publish(stage_path, final_path, expected_sha256=expected_sha256)
        if selected and phase == "after":
            stop()
        return result

    def is_selected_descriptor(descriptor: int) -> bool:
        observed = os.fstat(descriptor)
        if boundary == "owner_pointer" and stat.S_ISDIR(observed.st_mode):
            expected = store._ownership_index.directory.stat()
            return (observed.st_dev, observed.st_ino) == (expected.st_dev, expected.st_ino)
        if boundary != "owner_generation_file" or not stat.S_ISREG(observed.st_mode):
            return False
        directory = store._ownership_index.directory / "generations"
        for temporary in directory.glob("*.tmp-*"):
            expected = temporary.stat()
            if (observed.st_dev, observed.st_ino) == (expected.st_dev, expected.st_ino):
                return True
        return False

    def fsync(descriptor: int) -> None:
        selected = is_selected_descriptor(descriptor)
        if selected and phase == "before":
            stop()
        original_fsync(descriptor)
        if selected and phase == "after":
            stop()

    store._publish_transaction_member = publish
    os.fsync = fsync


def main() -> None:
    """Perform one requested operation using real scoped, signed CAS owners."""
    request = json.loads(sys.argv[1])
    config = SigningConfig.model_validate(request["config"])
    store = FileSystemCAS(Path(request["root"]), signing_config=config).for_tenant(
        "tenant-a", cell_id="cell-a"
    )
    mode = request["mode"]
    if mode == "interrupt":
        _install_interruption(store, request["boundary"], request["phase"])
        store.put_bytes(
            bytes.fromhex(request["payload_hex"]), _options(request), return_selected_profile=True
        )
        raise AssertionError("requested interruption was never reached")

    pair = KeyPair.from_private_pem(config.private_key_file.read_bytes())
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(pair.public_key, key_id=pair.key_id)
    refs = [ArtifactRef.model_validate(row) for row in request["prior_refs"]]
    target = ArtifactRef.model_validate(request["target_ref"])
    result: dict[str, Any] = {
        "pid": os.getpid(),
        "store_origin": str(Path(store_module.__file__).resolve()),
    }
    if mode == "recover":
        target = store.put_bytes(
            bytes.fromhex(request["payload_hex"]), _options(request), return_selected_profile=True
        )
        result["target_ref"] = target.model_dump(mode="json")
        result["target_payload_sha256"] = hashlib.sha256(store.get_bytes(target)).hexdigest()
        result["target_signature_ok"] = store.verify_signature(target, verifier).ok
        result["target_manifest"] = store.get_manifest(target).model_dump(mode="json")
        result["pending"] = store._ownership_index._read_transaction_intent(target.artifact_id)
    elif mode == "read_pending":
        try:
            store.get_bytes(target.artifact_id)
        except ArtifactTransactionPendingError as exc:
            result["target_read_code"] = exc.code
        else:
            raise AssertionError("unfinished transaction was exposed as a completed artifact")
        result["pending"] = store._ownership_index._read_transaction_intent(target.artifact_id)
    else:
        raise ValueError(f"unknown fixture action: {mode}")
    # Observe preservation after the operation, through a newly opened reader.
    # A pre-recovery observation cannot prove that recovery preserved these views.
    fresh = FileSystemCAS(store.root, signing_config=config).for_tenant(
        "tenant-a", cell_id="cell-a"
    )
    result["prior"] = [
        {
            "ref": ref.model_dump(mode="json"),
            "payload_sha256": hashlib.sha256(fresh.get_bytes(ref)).hexdigest(),
            "manifest_sha256": hashlib.sha256(fresh.get_manifest_bytes(ref)).hexdigest(),
            "signature_ok": fresh.verify_signature(ref, verifier).ok,
        }
        for ref in refs
    ]
    result["default_sha256"] = hashlib.sha256(
        fresh.get_manifest_bytes(refs[0].artifact_id)
    ).hexdigest()
    foreign = FileSystemCAS(store.root, signing_config=config).for_tenant(
        "tenant-b", cell_id="cell-b"
    )
    denied = []
    for ref in [*refs, target]:
        try:
            foreign.get_bytes(ref)
        except PermissionError:
            denied.append(str(ref.artifact_id))
        else:
            raise AssertionError("another tenant read the fixture's owned artifact")
    result["foreign_denied"] = denied
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
