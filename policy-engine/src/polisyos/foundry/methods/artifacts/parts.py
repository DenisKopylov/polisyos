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

from ._chain import ChainArtifact, CompiledChainPlan
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

    from ..components.composer import CompiledMethodChain
    from ..selection.registry import MethodRegistry

__version__ = ARTIFACTS_VERSION
logger = get_logger(__name__)


__all__ = [
    "ChainArtifact",
    "ChainNodeRecord",
    "CompiledChainPlan",
    "DeviceInfo",
    "ExecutionEvidence",
    "MethodArtifact",
    "MethodTiming",
    "SlotBindingRecord",
    "SourceFingerprint",
    "compute_source_fingerprint",
    "compute_source_hash",
    "load_compiled_chain_plan",
    "store_compiled_chain_plan",
    "store_chain_artifact",
    "store_execution_evidence",
    "store_method_artifact",
]


def store_method_artifact(
    cas: FileSystemCAS,
    artifact: MethodArtifact,
) -> ArtifactRef:
    """Persist one `MethodArtifact` describing code identity and specialization."""
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


def store_compiled_chain_plan(
    cas: FileSystemCAS,
    plan: CompiledChainPlan,
) -> ArtifactRef:
    """Persist one cold executable plan through the normal guarded CAS writer."""
    from polisyos.core.artifacts.store import PutOptions

    return cas.put_bytes(
        plan.to_canonical_bytes(),
        PutOptions(
            kind="foundry.compiled_chain_plan",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.compiled_chain_plan",
                version=CompiledChainPlan.SCHEMA_VERSION,
            ),
            producer=ProducerInfo(component="foundry.artifacts", version=__version__),
        ),
    )


def load_compiled_chain_plan(
    cas: FileSystemCAS,
    ref: ArtifactRef,
    *,
    registry: MethodRegistry | None = None,
) -> CompiledMethodChain:
    """Guard-read a selected plan view and rebuild its current cold chain.

    The exact reference is retained for both public CAS reads. Its manifest and
    blob verification grant no authority over method code or execution policy.
    """
    if (
        not isinstance(ref, ArtifactRef)
        or ref.kind != "foundry.compiled_chain_plan"
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("Compiled plan requires an exact typed selected-manifest reference")
    manifest = cas.get_manifest(ref)
    schema = manifest.artifact_schema
    if (
        schema is None
        or schema.name != "polisyos.foundry.compiled_chain_plan"
        or schema.version != CompiledChainPlan.SCHEMA_VERSION
    ):
        raise ValueError("Compiled plan manifest schema mismatch")
    content = cas.get_bytes(ref)
    return CompiledChainPlan.from_canonical_bytes(content).to_chain(registry=registry)


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
