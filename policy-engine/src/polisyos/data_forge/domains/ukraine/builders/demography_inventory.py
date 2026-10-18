"""Explicit candidate-only Ukraine demographic inventory stage builder."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.ukraine.builders.common import StageBuildResult
from polisyos.data_forge.domains.ukraine.demography.source_inventory import (
    InventoryBuildRequest,
    produce_candidate_inventory,
)
from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord

if TYPE_CHECKING:
    from polisyos.data_forge.domains.ukraine.models import PipelineConfig

_REQUEST_ERROR = "demography inventory requires an explicit producer request file"


def build_demography_source_inventory_stage(config: PipelineConfig) -> StageBuildResult:
    """Build one candidate inventory from an explicitly named verified stage."""
    request_path = config.demography_inventory_request_path
    if request_path is None:
        raise ValueError(_REQUEST_ERROR)
    try:
        request_bytes = request_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{_REQUEST_ERROR}: {request_path}") from exc
    request = InventoryBuildRequest.model_validate_json(request_bytes)
    store = FileSystemCAS(config.build_root.resolved_cas_root)
    produced = produce_candidate_inventory(request, store=store)
    envelope = produced.envelope

    output_dir = (
        config.build_root.bundles_dir / "demography_source_inventory" / envelope.inventory_id
    )
    output_path = output_dir / "inventory.json"
    if output_path.resolve() in {Path(item.path).resolve() for item in produced.stage_inputs}:
        raise ValueError("candidate inventory output path collides with a selected producer input")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_bytes = envelope.model_dump_json(indent=2).encode("utf-8")
    if output_path.exists():
        if output_path.read_bytes() != output_bytes:
            raise ValueError("inventory identity already exists with different bytes")
    else:
        output_path.write_bytes(output_bytes)

    return StageBuildResult(
        outputs={"inventory.json": ArtifactRecord.from_path(output_path)},
        warnings=[
            "candidate_only: source owner, semantic completeness, and currentness "
            "are not established"
        ],
        metrics={
            "inventory_id": envelope.inventory_id,
            "source_status": envelope.evidence_band,
            "source_stage_id": envelope.source_stage_receipt.stage_id,
            "source_run_id": envelope.source_stage_receipt.run_id,
            "member_count": len(envelope.members),
        },
        inputs=list(produced.stage_inputs),
    )
