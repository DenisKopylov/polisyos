from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

root = Path("/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/obs-parity-review")
repo = root / "candidate"
sys.path.insert(0, str(repo / "policy-engine" / "src"))
from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.read_api.ukraine import (
    UkraineStageArtifactVerificationError,
    load_verified_stage_artifacts,
)

build_root = root / "shared-build"
artifact = build_root / "runtime" / "d1" / "trade_graph_sparse.npz"
base = json.loads((root / "base-run7" / "result.json").read_text())
candidate = json.loads((root / "candidate-run7" / "result.json").read_text())
base_record = next(
    item for item in base["stages"]["d1"]["outputs"]
    if item["path"] == "runtime/d1/trade_graph_sparse.npz"
)
candidate_record = next(
    item for item in candidate["stages"]["d1"]["outputs"]
    if item["path"] == "runtime/d1/trade_graph_sparse.npz"
)
assert base_record["actual_sha256"] == candidate_record["actual_sha256"]
original = artifact.read_bytes()
mutated = bytes([original[0] ^ 1]) + original[1:]
artifact.write_bytes(mutated)
actual_sha = hashlib.sha256(mutated).hexdigest()
assert actual_sha != base_record["actual_sha256"]
assert actual_sha != candidate_record["actual_sha256"]
cas = FileSystemCAS(root / "negative-control-cas")
manifest = build_root / "manifests" / "build_run_d1.json"
try:
    load_verified_stage_artifacts(
        manifest,
        store=cas,
        allowed_root=build_root,
        expected_stage="d1",
    )
except UkraineStageArtifactVerificationError as exc:
    assert "content hash mismatch for output trade_graph_sparse.npz" in str(exc), str(exc)
    print(
        "PASS mutation removal control: registered D1 output changed while stage manifest "
        f"remained intact; equal_base_candidate_sha256={base_record['actual_sha256']}; "
        f"mutated_sha256={actual_sha}; read_api_rejection={exc}"
    )
else:
    raise AssertionError("public read API admitted a mutated registered D1 output")
