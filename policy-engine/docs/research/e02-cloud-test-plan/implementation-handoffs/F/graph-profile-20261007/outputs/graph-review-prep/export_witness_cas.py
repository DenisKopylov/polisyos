"""Transfer the exact selected CAS payload and manifest bytes, without refitting."""

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, "/workspace/e02-F-closeout-20261006/policy-engine/src")
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS


def scan(value, refs, locator=""):
    if isinstance(value, dict):
        if isinstance(value.get("artifact_id"), str) and value.get("kind") and value.get("media_type"):
            refs.setdefault(json.dumps(value, sort_keys=True), []).append(locator)
        for key, child in value.items():
            scan(child, refs, locator + "/" + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan(child, refs, locator + "/" + str(index))


def digest(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main():
    output = HERE / "selected-cas-exports"
    output.mkdir(exist_ok=True)
    all_rows = []
    for name in ("freshpid-native", "freshpid-native-corrected"):
        folder = HERE / name
        refs = {}
        sources = [folder / "fresh-reader-inputs.json"]
        if (folder / "native-witness.json").exists():
            sources.append(folder / "native-witness.json")
        for source in sources:
            scan(json.loads(source.read_bytes()), refs, str(source))
        store = FileSystemCAS(folder / "cas")
        for serialized, locators in sorted(refs.items()):
            ref = ArtifactRef.model_validate(json.loads(serialized))
            manifest = store.get_manifest_bytes(ref)
            payload = store.get_bytes(ref)
            assert hashlib.sha256(payload).hexdigest() == ref.artifact_id.hex
            stem = name + "-" + ref.artifact_id.hex
            body_path = output / (stem + ".payload.json")
            manifest_path = output / (stem + ".manifest.json")
            body_path.write_bytes(payload)
            manifest_path.write_bytes(manifest)
            all_rows.append(
                {
                    "case": name,
                    "artifact_ref": ref.model_dump(mode="json"),
                    "native_record_locators": locators,
                    "payload": {"path": str(body_path), **digest(payload)},
                    "manifest": {"path": str(manifest_path), **digest(manifest)},
                    "check": "PASS",
                }
            )
    index = {"schema": "selected_native_cas_byte_transfer/1.0", "check": "PASS", "refs": all_rows}
    (HERE / "selected-cas-export-index.json").write_text(json.dumps(index, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"check": "PASS", "selected_ref_count": len(all_rows), "payload_manifest_files": len(all_rows) * 2}))


if __name__ == "__main__":
    main()
