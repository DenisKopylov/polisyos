"""Hash retained fixture paths, then read copied artifacts through genuine CAS."""

import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path("/workspace/e02-B-current-coordination")
LANE = Path("/workspace/e02-B-current-execution-state")
OUT = LANE / "_build/current-execution-state/deadline-cohort-investigation/readback"
ORIGINAL = ROOT / ".polisyos/e02-B-current/raw/review/final-B-cohort-pytest/test_workflow_cas_wait_cannot_1/cas"
REPLAY = LANE / "_build/current-execution-state/deadline-cohort-investigation/native/pytest/test_workflow_cas_wait_cannot_0/cas"
sys.path[:0] = [str(ROOT / "policy-engine/src"), str(ROOT / "policy-engine")]

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS


def inventory(root):
    result = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            result.append({"path": path.relative_to(root).as_posix(), "bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()})
    return result


def main():
    OUT.mkdir(parents=True)
    observations = []
    for label, original in [("original-whole-cohort-failure", ORIGINAL), ("unchanged-narrow-native-replay", REPLAY)]:
        before = inventory(original)
        copied = OUT / label / "cas"
        shutil.copytree(original, copied)
        assert inventory(copied) == before
        store = FileSystemCAS(copied)
        refs = []
        for path in sorted((copied / "artifacts/sha256").rglob("*.view.*.manifest.json")):
            manifest = json.loads(path.read_text())
            profile = "sha256:" + path.name.split(".view.")[1].split(".manifest.json")[0]
            ref = ArtifactRef.model_validate({"artifact_id": manifest["artifact_id"],
                "kind": manifest["kind"], "media_type": manifest["media_type"],
                "manifest_profile_sha256": profile})
            verified = store.verify(ref)
            assert verified.ok
            data = store.get_bytes(ref)
            assert hashlib.sha256(data).hexdigest() == str(ref.artifact_id).split(":")[1]
            refs.append({"ref": ref.model_dump(mode="json"), "verify": verified.model_dump(mode="json"),
                         "byte_size": len(data), "payload": json.loads(data) if manifest["kind"].startswith("scientist.") else None})
        trace = (copied / "runs/R_deadline/trace.jsonl").read_bytes()
        events = [json.loads(line) for line in trace.splitlines()]
        assert inventory(original) == before
        observations.append({"label": label, "original_path": str(original), "copy_path": str(copied),
            "original_file_inventory": before, "original_file_count": len(before),
            "fresh_cas_consumer": refs, "trace_sha256": hashlib.sha256(trace).hexdigest(),
            "trace_bytes": len(trace), "events": events, "original_bytes_unchanged": True})
    report = {"schema": "policyos.e02.deadline_fixture_readback.v1", "observations": observations,
              "qualification": "Original retained directories are hashed/read only; genuine FileSystemCAS verify/full selected ref/get_bytes operates on isolated exact copies. Reconstructed selected refs identify physical artifacts and do not assert an executor acknowledgement."}
    (OUT / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
