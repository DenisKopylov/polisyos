"""Method artifacts facade assembled from decomposed sub-modules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)

from ._artifacts_chain import CHAIN_ID_NAMESPACE, ChainArtifact
from ._artifacts_evidence import ExecutionEvidence, _to_artifact_id
from ._artifacts_fingerprint import (
    ARTIFACTS_VERSION,
    HASH_TRUNCATE_LENGTH,
    SOURCE_UNAVAILABLE,
    SourceFingerprint,
    compute_source_fingerprint,
    compute_source_hash,
)
from ._artifacts_method import MethodArtifact
from ._artifacts_records import ChainNodeRecord, DeviceInfo, MethodTiming, SlotBindingRecord

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS

__version__ = ARTIFACTS_VERSION
logger = logging.getLogger(__name__)


__all__ = [
    "MethodArtifact",
    "ChainArtifact",
    "ExecutionEvidence",
    "SlotBindingRecord",
    "MethodTiming",
    "DeviceInfo",
    "ChainNodeRecord",
    "SourceFingerprint",
    "compute_source_hash",
    "compute_source_fingerprint",
    "store_method_artifact",
    "store_chain_artifact",
    "store_execution_evidence",
]


def store_method_artifact(
    cas: "FileSystemCAS",
    artifact: MethodArtifact,
) -> ArtifactRef:
    """Store a MethodArtifact in CAS."""
    from polisyos.core.artifacts.store import PutOptions

    content = artifact.to_canonical_bytes()
    return cas.put_bytes(
        content,
        PutOptions(
            kind="foundry.method_artifact",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.method_artifact",
                version=MethodArtifact.SCHEMA_VERSION,
            ),
            producer=ProducerInfo(
                component="foundry.artifacts",
                version=__version__,
            ),
        ),
    )


def store_chain_artifact(
    cas: "FileSystemCAS",
    artifact: ChainArtifact,
) -> ArtifactRef:
    """Store a ChainArtifact in CAS."""
    from polisyos.core.artifacts.store import PutOptions

    content = artifact.to_canonical_bytes()
    unique_method_ids = sorted(set(artifact.method_artifact_ids))
    return cas.put_bytes(
        content,
        PutOptions(
            kind="foundry.chain_artifact",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.chain_artifact",
                version=ChainArtifact.SCHEMA_VERSION,
            ),
            producer=ProducerInfo(
                component="foundry.artifacts",
                version=__version__,
            ),
            inputs=[
                InputRef(artifact_id=ArtifactID.from_sha256_hex(aid), role="method")
                for aid in unique_method_ids
            ],
        ),
    )


def store_execution_evidence(
    cas: "FileSystemCAS",
    evidence: ExecutionEvidence,
) -> ArtifactRef:
    """Store ExecutionEvidence in CAS."""
    from polisyos.core.artifacts.store import PutOptions

    content = evidence.to_canonical_bytes()
    inputs: list[InputRef] = [
        InputRef(artifact_id=_to_artifact_id(evidence.chain_artifact_id), role="chain")
    ]
    for aid in evidence.input_state_artifact_ids:
        inputs.append(InputRef(artifact_id=_to_artifact_id(aid), role="input_state"))
    for aid in evidence.output_state_artifact_ids:
        inputs.append(InputRef(artifact_id=_to_artifact_id(aid), role="output_state"))
    if evidence.params_artifact_id:
        inputs.append(
            InputRef(artifact_id=_to_artifact_id(evidence.params_artifact_id), role="params")
        )
    if evidence.rng_artifact_id:
        inputs.append(
            InputRef(artifact_id=_to_artifact_id(evidence.rng_artifact_id), role="rng")
        )

    return cas.put_bytes(
        content,
        PutOptions(
            kind="foundry.execution_evidence",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.execution_evidence",
                version=ExecutionEvidence.SCHEMA_VERSION,
            ),
            producer=ProducerInfo(
                component="foundry.runtime",
                version=__version__,
            ),
            inputs=inputs,
        ),
    )
