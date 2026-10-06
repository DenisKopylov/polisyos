"""Restore only synthetic deciding CAS bytes into a fresh fixture and reopen all refs."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS


def main() -> None:
    repo = Path(sys.argv[1]).resolve()
    destination = Path(sys.argv[2]).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    folder = Path(__file__).resolve().parent
    archive = json.loads((folder / "native-deciding-cas.json").read_text())
    witness = json.loads((folder / "pcl-74b26eb067de/native-witness-output.json").read_text())
    roots = {}
    files = 0
    for root in archive["roots"]:
        restored = destination / root["archive_root_key"]
        for record in root["files"]:
            data = base64.b64decode(record["content_base64"], validate=True)
            if not len(data) == record["bytes"]:
                raise ValueError("Receipt verification failed")
            if not hashlib.sha256(data).hexdigest() == record["sha256"]:
                raise ValueError("Receipt verification failed")
            path = (restored / record["path"]).resolve()
            path.relative_to(restored)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            files += 1
        roots[root["original_root"]] = FileSystemCAS(restored)
    test = (
        repo
        / "policy-engine/tests/unit/foundry/methods/catalog/econometrics"
        / "test_advanced_persistence.py"
    )
    spec = importlib.util.spec_from_file_location("pcl_native_oracle", test)
    if not (spec is not None and spec.loader is not None):
        raise ValueError("Receipt verification failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for record in witness["artifacts"]:
        module._assert_fresh_source_and_pairs(
            roots[record["cas_root"]], ArtifactRef.model_validate(record["diagnostics_ref"])
        )
    result = {
        "source_candidate_sha": archive["source_candidate_sha"],
        "restore_root": str(destination),
        "archived_file_hashes": files,
        "fresh_artifacts": len(witness["artifacts"]),
        "source_rows_per_artifact": 100,
        "oracle": "fresh restored source row vs persisted interval endpoints "
        "plus reopened report/receipt",
        "outcome": "PASS",
        "production_data": False,
    }
    (folder / "archive-readback.json").write_text(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
