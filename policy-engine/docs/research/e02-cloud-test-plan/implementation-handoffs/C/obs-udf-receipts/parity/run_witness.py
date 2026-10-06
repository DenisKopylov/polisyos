from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

repo = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
os.environ["POLISYOS_UKRAINE_DATA_D1_CONTRACT_NODE_LIMIT"] = "2"
sys.path.insert(0, str(repo / "policy-engine" / "src"))
sys.path.insert(0, str(repo / "policy-engine" / "tests" / "unit" / "remediation"))
fixture_repo = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else repo
sys.path.insert(0, str(fixture_repo / "policy-engine" / "tests" / "unit" / "remediation"))

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.ukraine.manifests import (
    BuildRunManifest,
    PartAGateManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId, build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator
from polisyos.data_forge.read_api.ukraine import (
    load_verified_stage_artifacts,
    load_verified_stage_output_bytes,
    load_verified_release_artifacts,
    load_verified_release_artifact_bytes,
)
from test_udf_02 import _seed_normalized_sources

# Hold only the known producer-owned handoff timestamp constant for cross-revision byte parity.
from polisyos.data_forge.domains.ukraine.builders import release as release_builders

_real_handoff_builder = release_builders._build_d5_release_handoff_request

def _fixed_time_handoff_builder(**kwargs: Any) -> Any:
    request = _real_handoff_builder(**kwargs)
    return request.model_copy(update={"created_at": "2026-01-01T00:00:00+00:00"})

release_builders._build_d5_release_handoff_request = _fixed_time_handoff_builder
build_root = Path(os.environ.get("WITNESS_BUILD_ROOT", str(out / "build"))).resolve()
config = build_default_pipeline_config(root=build_root)
config.server.require_server_for_build = False
orchestrator = UkraineDataOrchestrator(config)
orchestrator.ensure_layout()
write_manifest(
    config.build_root.part_a_gate_manifest_path,
    PartAGateManifest(status="passed", passed=True),
)
_seed_normalized_sources(orchestrator, StageId.D0_P0)
_seed_normalized_sources(orchestrator, StageId.D1)

stages = [StageId.D0_P0, StageId.D1, StageId.D2, StageId.D4, StageId.D5]
result: dict[str, Any] = {"tag": out.name, "stages": {}}
for stage_id in stages:
    if stage_id is StageId.D4:
        write_manifest(
            orchestrator.stage_manifest_path(StageId.D3),
            BuildRunManifest(
                run_id="d3-udf-02-independent-parity-prerequisite",
                stage_id=StageId.D3,
                status="completed",
                started_at="2026-08-26T10:00:00+00:00",
                finished_at="2026-08-26T10:01:00+00:00",
            ),
        )
    summary = orchestrator.build_stage(stage_id)
    manifest_path = orchestrator.stage_manifest_path(stage_id)
    manifest = summary.manifest
    root = config.build_root.root.resolve()
    stage_record: dict[str, Any] = {
        "status": summary.status,
        "run_id": manifest.run_id,
        "warnings": list(manifest.warnings),
        "errors": list(manifest.errors),
        "findings": [item.model_dump(mode="json") for item in manifest.findings],
        "metrics": dict(manifest.metrics),
        "inputs": [],
        "outputs": [],
        "read_api": {"passed": False},
    }
    for input_record in manifest.inputs:
        input_path = Path(input_record.path)
        try:
            normalized_input = input_path.resolve().relative_to(root).as_posix()
        except (OSError, ValueError):
            normalized_input = input_path.name
        stage_record["inputs"].append(
            {
                "path": normalized_input,
                "sha256": input_record.sha256,
                "size_bytes": input_record.size_bytes,
                "row_count": input_record.row_count,
            }
        )
    for output_record in manifest.outputs:
        output_path = Path(output_record.path)
        relpath = output_path.resolve().relative_to(root).as_posix()
        if output_path.is_dir():
            children = {}
            for child in sorted(output_path.rglob("*")):
                if child.is_file():
                    data = child.read_bytes()
                    children[child.relative_to(output_path).as_posix()] = {
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "size_bytes": len(data),
                    }
            file_digest = hashlib.sha256(
                json.dumps(children, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            file_size = sum(child["size_bytes"] for child in children.values())
            stage_record["outputs"].append(
                {
                    "path": relpath,
                    "is_directory": True,
                    "record_sha256": output_record.sha256,
                    "record_size_bytes": output_record.size_bytes,
                    "child_inventory_sha256": file_digest,
                    "child_count": len(children),
                    "child_size_bytes": file_size,
                    "children": children,
                }
            )
        else:
            data = output_path.read_bytes()
            stage_record["outputs"].append(
                {
                    "path": relpath,
                    "is_directory": False,
                    "record_sha256": output_record.sha256,
                    "record_size_bytes": output_record.size_bytes,
                    "actual_sha256": hashlib.sha256(data).hexdigest(),
                    "actual_size_bytes": len(data),
                    "row_count": output_record.row_count,
                    "nnz": output_record.nnz,
                }
            )
    try:
        cas = FileSystemCAS(out / "cas" / stage_id.value)
        if stage_id is StageId.D5:
            release_manifest_path = root / "bundles" / "d5" / "release_manifest_v1.json"
            receipt = load_verified_release_artifacts(
                release_manifest_path,
                store=cas,
                allowed_root=root,
                expected_stage="d5",
            )
            readbacks: list[dict[str, Any]] = []
            for bundle_name, files in sorted(receipt.bundle_contents.items()):
                for relative_name, artifact in sorted(files.items()):
                    data = load_verified_release_artifact_bytes(cas, artifact)
                    if data != Path(artifact.source_path).read_bytes():
                        raise AssertionError(
                            f"public release readback differs from persisted bundle {bundle_name}:{relative_name}"
                        )
                    readbacks.append(
                        {
                            "name": f"bundle:{bundle_name}:{relative_name}",
                            "sha256": artifact.sha256,
                            "size_bytes": artifact.size_bytes,
                        }
                    )
            for name, artifact in sorted(receipt.evidence.items()):
                data = load_verified_release_artifact_bytes(cas, artifact)
                if data != Path(artifact.source_path).read_bytes():
                    raise AssertionError(f"public release readback differs from persisted evidence {name}")
                readbacks.append(
                    {
                        "name": f"evidence:{name}",
                        "sha256": artifact.sha256,
                        "size_bytes": artifact.size_bytes,
                    }
                )
            stored_manifest_bytes = cas.get_bytes(receipt.manifest_ref.artifact_id)
            if stored_manifest_bytes != release_manifest_path.read_bytes():
                raise AssertionError("public release readback differs from persisted release manifest")
            stage_record["read_api"] = {
                "passed": True,
                "stage_id": receipt.stage_id,
                "output_count": len(readbacks),
                "outputs": readbacks,
                "manifest_sha256": receipt.manifest_sha256,
                "manifest_readback_sha256": hashlib.sha256(stored_manifest_bytes).hexdigest(),
                "manifest_readback_size_bytes": len(stored_manifest_bytes),
            }
        else:
            receipt = load_verified_stage_artifacts(
                manifest_path,
                store=cas,
                allowed_root=root,
                expected_stage=stage_id.value,
            )
            readbacks = []
            for name, artifact in sorted(receipt.outputs.items()):
                data = load_verified_stage_output_bytes(cas, receipt, name)
                source = Path(artifact.source_path).read_bytes()
                if data != source:
                    raise AssertionError(f"public readback differs from persisted output {name}")
                readbacks.append(
                    {"name": name, "sha256": artifact.sha256, "size_bytes": artifact.size_bytes}
                )
            stored_manifest_bytes = cas.get_bytes(receipt.manifest_ref.artifact_id)
            if stored_manifest_bytes != manifest_path.read_bytes():
                raise AssertionError("public stage readback differs from persisted stage manifest")
            stage_record["read_api"] = {
                "passed": True,
                "stage_id": receipt.stage_id,
                "output_count": len(readbacks),
                "outputs": readbacks,
                "manifest_sha256": receipt.manifest_sha256,
                "manifest_readback_sha256": hashlib.sha256(stored_manifest_bytes).hexdigest(),
                "manifest_readback_size_bytes": len(stored_manifest_bytes),
            }
    except Exception as exc:
        stage_record["read_api"] = {
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    result["stages"][stage_id.value] = stage_record
    if summary.status != "completed":
        break

encoded = json.dumps(result, sort_keys=True, indent=2, default=str)
(out / "result.json").write_text(encoded + "\n")
print(encoded)
