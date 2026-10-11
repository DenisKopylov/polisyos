"""Persist method, chain, and execution-evidence artifacts with CAS provenance edges.

These helpers answer "what code/signature/specialization ran, in what chain,
over which input/output state artifacts, with which RNG/device context?" They
complement backend runners (execution) and specialization/cache (compiled
variant selection) by writing immutable provenance receipts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)

from ._chain import ChainArtifact
from ._evidence import ExecutionEvidence, _to_artifact_id
from ._fingerprint import (
    ARTIFACTS_VERSION,
    SourceFingerprint,
    compute_source_fingerprint,
    compute_source_hash,
)
from ._method import MethodArtifact
from ._records import ChainNodeRecord, DeviceInfo, MethodTiming, SlotBindingRecord

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS

__version__ = ARTIFACTS_VERSION
logger = get_logger(__name__)


__all__ = [
    "ChainArtifact",
    "ChainNodeRecord",
    "DeviceInfo",
    "ExecutionEvidence",
    "MethodArtifact",
    "MethodTiming",
    "SlotBindingRecord",
    "SourceFingerprint",
    "compute_source_fingerprint",
    "compute_source_hash",
    "store_chain_artifact",
    "store_execution_evidence",
    "store_method_artifact",
]


def store_method_artifact(
    cas: FileSystemCAS,
    artifact: MethodArtifact,
    *,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist one method artifact, optionally returning the profile from that write.

    Args:
        cas: CAS receiving the immutable artifact.
        artifact: Method identity and specialization to persist.
        return_selected_profile: Return the exact selected manifest profile emitted by this write.

    Returns:
        The content-addressed reference, including the selected profile when requested.

    Raises:
        TypeError: If the selected-profile option is not a boolean.
        ValueError: If the CAS does not return a profile for an opted-in write.
    """
    from polisyos.core.artifacts.store import PutOptions

    if type(return_selected_profile) is not bool:
        raise TypeError("return_selected_profile must be a bool")

    content = artifact.to_canonical_bytes()
    options = PutOptions(
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
    )
    if return_selected_profile:
        ref = cas.put_bytes(content, options, return_selected_profile=True)
        if ref.manifest_profile_sha256 is None:
            raise ValueError("artifact_write_selected_profile_missing")
        return ref
    return cas.put_bytes(content, options)


def store_chain_artifact(
    cas: FileSystemCAS,
    artifact: ChainArtifact,
) -> ArtifactRef:
    """Persist a `ChainArtifact` and link it to its component method artifacts."""
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
    cas: FileSystemCAS,
    evidence: ExecutionEvidence,
) -> ArtifactRef:
    """Persist an `ExecutionEvidence` receipt linked to chain/input/output refs."""
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
        inputs.append(InputRef(artifact_id=_to_artifact_id(evidence.rng_artifact_id), role="rng"))

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
