from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

repo = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
fixture_repo = Path(sys.argv[3]).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(repo / "policy-engine" / "src"))
sys.path.insert(0, str(repo / "policy-engine" / "tests" / "unit" / "data_forge" / "domains" / "ukraine"))
sys.path.insert(0, str(fixture_repo / "policy-engine" / "tests" / "unit" / "data_forge" / "domains" / "ukraine"))

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.ukraine import adapters
from polisyos.data_forge.domains.ukraine.builders import STAGE_BUILDERS, demography
from polisyos.data_forge.domains.ukraine.models import StageId
from polisyos.data_forge.read_api.ukraine import (
    load_verified_stage_artifacts,
    load_verified_stage_output_bytes,
)
from test_orchestrator import _seed_explicit_period_d3_inputs

# Hold the optional-source producer timestamp constant so byte parity compares
# the migration behavior rather than wall-clock text in the skipped-source receipts.
adapters.utc_now_iso = lambda: "2026-01-01T00:00:00+00:00"
assert STAGE_BUILDERS[StageId.D3].__module__.endswith("builders.demography")

orchestrator = _seed_explicit_period_d3_inputs(out)
config = orchestrator.config
build_root = config.build_root.root.resolve()
before = {
    path.relative_to(build_root).as_posix()
    for path in build_root.rglob("*")
    if path.is_file()
}
summary = orchestrator.build_stage(StageId.D3)
manifest = summary.manifest
after = {
    path.relative_to(build_root).as_posix()
    for path in build_root.rglob("*")
    if path.is_file()
}

outputs: list[dict[str, Any]] = []
for record in manifest.outputs:
    path = Path(record.path)
    payload = path.read_bytes()
    outputs.append(
        {
            "name": path.name,
            "relative_path": path.resolve().relative_to(build_root).as_posix(),
            "record_sha256": record.sha256,
            "record_size_bytes": record.size_bytes,
            "record_row_count": record.row_count,
            "record_nnz": record.nnz,
            "actual_sha256": hashlib.sha256(payload).hexdigest(),
            "actual_size_bytes": len(payload),
        }
    )

cas = FileSystemCAS(out / "cas")
receipt = load_verified_stage_artifacts(
    orchestrator.stage_manifest_path(StageId.D3),
    store=cas,
    allowed_root=build_root,
    expected_stage="d3",
)
readbacks: list[dict[str, Any]] = []
for name, artifact in sorted(receipt.outputs.items()):
    payload = load_verified_stage_output_bytes(cas, receipt, name)
    if payload != Path(artifact.source_path).read_bytes():
        raise AssertionError(f"D3 public readback differs from persisted output {name}")
    readbacks.append({"name": name, "sha256": artifact.sha256, "size_bytes": artifact.size_bytes})
manifest_bytes = cas.get_bytes(receipt.manifest_ref.artifact_id)
if manifest_bytes != orchestrator.stage_manifest_path(StageId.D3).read_bytes():
    raise AssertionError("D3 public readback differs from persisted stage manifest")

result = {
    "tag": out.name,
    "status": summary.status,
    "stage": manifest.stage_id.value,
    "registered_builder": STAGE_BUILDERS[StageId.D3].__module__,
    "demography_module": demography.__file__,
    "inputs": [
        {
            "path": Path(record.path).resolve().relative_to(build_root).as_posix(),
            "sha256": record.sha256,
            "size_bytes": record.size_bytes,
            "row_count": record.row_count,
        }
        for record in manifest.inputs
    ],
    "warnings": list(manifest.warnings),
    "errors": list(manifest.errors),
    "findings": [item.model_dump(mode="json") for item in manifest.findings],
    "metrics": dict(manifest.metrics),
    "outputs": sorted(outputs, key=lambda item: item["relative_path"]),
    "writes": sorted(after - before),
    "read_api": {
        "passed": True,
        "output_count": len(readbacks),
        "outputs": readbacks,
        "manifest_sha256": receipt.manifest_sha256,
        "manifest_readback_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "manifest_readback_size_bytes": len(manifest_bytes),
    },
}
encoded = json.dumps(result, sort_keys=True, indent=2, default=str)
(out / "result.json").write_text(encoded + "\n")
print(encoded)
