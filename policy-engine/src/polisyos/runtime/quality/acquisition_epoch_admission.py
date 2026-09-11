"""Run acquisition epoch admission from persisted evidence and emit its audited receipt.

Invoke with ``python -m polisyos.runtime.quality.acquisition_epoch_admission``.
The existing acquisition owner composes qualification and persists its result;
this local entry point resolves configured owners and reads that result back.
The unallocated predicate-policy authority remains a typed negative.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts  # noqa: TC001 - Pydantic resolves these fields at runtime.
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.data_forge import read_api
from polisyos.fabric import data_plane  # noqa: TC001 - Pydantic resolves this field at runtime.
from polisyos.runtime.quality import acquisition_executor, semantic_epoch

if TYPE_CHECKING:
    from collections.abc import Sequence


class AcquisitionEpochAdmissionRequest(BaseModel):
    """Local owner paths and persisted evidence selectors for one admission attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    repo_root: Path
    authority_repo_root: Path
    baseline_path: Path
    cas_root: Path
    overlay_path: Path
    epoch_history_root: Path
    epoch_id: int = Field(ge=1)
    raw_evidence_ref: data_plane.JournalEventRef
    epoch_scope_identity: semantic_epoch.EpochScopeIdentity
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_evidence_ref: artifacts.ArtifactRef
    visibility_knowledge_cutoff_evidence_ref: artifacts.ArtifactRef
    purpose_admission_cutoff_evidence_ref: artifacts.ArtifactRef
    facet_source_refs: dict[str, artifacts.ArtifactRef]
    live_source_execution: read_api.catalog.LiveSourceExecutionEvidence | None = None


def run_admission(
    request: AcquisitionEpochAdmissionRequest,
) -> semantic_epoch.PersistedSemanticEpochProductionReceipt:
    """Invoke the existing producer and admit its complete persisted negative statement.

    Args:
        request: Operational paths and existing evidence references. Canonical
            owners independently reopen the decisive inputs.

    Returns:
        The persisted producer receipt after exact CAS and statement readback.

    Raises:
        ValueError: An owner input or persisted receipt cannot be verified.
        RuntimeError: The producer returns an unsupported activation result.
    """

    authority = read_api.catalog.CanonicalAcquisitionAuthority.from_provision(
        repo_root=request.authority_repo_root,
        baseline_path=request.baseline_path,
    )
    store = build_artifact_store(
        ArtifactStoreConfig(
            backend="filesystem",
            root=str(request.cas_root),
        ),
    )
    receipt = acquisition_executor.admit_acquisition_with_production_semantic_epoch(
        repo_root=request.repo_root,
        epoch_id=request.epoch_id,
        raw_evidence_ref=request.raw_evidence_ref,
        artifact_store=store,
        authority=authority,
        overlay_path=request.overlay_path,
        epoch_history_root=request.epoch_history_root,
        epoch_scope_identity=request.epoch_scope_identity,
        authority_purpose=request.authority_purpose,
        valid_effect_coordinate_evidence_ref=request.valid_effect_coordinate_evidence_ref,
        visibility_knowledge_cutoff_evidence_ref=(
            request.visibility_knowledge_cutoff_evidence_ref
        ),
        purpose_admission_cutoff_evidence_ref=request.purpose_admission_cutoff_evidence_ref,
        facet_source_refs=request.facet_source_refs,
        live_source_execution=request.live_source_execution,
    )
    if type(receipt) is not semantic_epoch.PersistedSemanticEpochProductionReceipt:
        raise RuntimeError("acquisition_epoch_activation_consumer_not_established")
    statement = epoch_contract.SemanticEpochProductionReceiptStatement.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=receipt.receipt_ref,
            expected_kind="epoch.production_receipt",
            expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
        )
    )
    projected = receipt.model_dump(
        mode="json",
        include=set(epoch_contract.SemanticEpochProductionReceiptStatement.model_fields),
    )
    if statement.model_dump(mode="json") != projected:
        raise ValueError("acquisition_epoch_production_receipt_content_mismatch")
    return semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(
        {
            **statement.model_dump(mode="python"),
            "receipt_ref": receipt.receipt_ref,
            "receipt_content_hash": receipt.receipt_content_hash,
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Read an admission request and print the exact persisted owner receipt.

    Args:
        argv: CLI arguments, or ``None`` to use the process arguments.

    Returns:
        One for a typed negative receipt; two for invalid/unresolved input or
        receipt evidence. Positive activation is outside this command's consumer.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True, help="Strict admission request JSON")
    args = parser.parse_args(argv)
    try:
        request = AcquisitionEpochAdmissionRequest.model_validate_json(args.request.read_bytes())
        receipt = run_admission(request)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        sys.stderr.write(json.dumps({"error": str(exc), "error_type": type(exc).__name__}) + "\n")
        return 2
    sys.stdout.write(receipt.model_dump_json() + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
