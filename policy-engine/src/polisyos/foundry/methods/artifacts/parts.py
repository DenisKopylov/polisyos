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
    CanonInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)

from ._chain import ChainArtifact
from ._evidence import ExecutionEvidence, _to_artifact_id
from ._fingerprint import (
    _ARTIFACT_CANON,
    ARTIFACTS_VERSION,
    SourceFingerprint,
    compute_source_fingerprint,
    compute_source_hash,
)
from ._method import MethodArtifact
from ._records import ChainNodeRecord, DeviceInfo, MethodTiming, SlotBindingRecord

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts.store import FileSystemCAS

    from ..components.composer import CompiledMethodChain
    from ..registry import MethodRegistry

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
    "load_compiled_chain",
    "load_execution_evidence",
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
    *,
    method_refs: Mapping[str, ArtifactRef] | None = None,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist a chain and bind executable recipes to selected method views.

    Args:
        cas: Artifact store receiving the recipe.
        artifact: Versioned chain recipe; legacy recipe-only objects stay 1.0.
        method_refs: Exact method views, or resolve the current store views.
        return_selected_profile: Return the selected profile from this write.

    Returns:
        The persisted recipe reference.

    Raises:
        ValueError: If a method reference has the wrong identity/type/profile.
        TypeError: If the selected-profile option is not boolean.
    """
    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import PutOptions

    if type(return_selected_profile) is not bool:
        raise TypeError("return_selected_profile must be a bool")
    content = artifact.to_canonical_bytes()
    unique_method_ids = sorted(set(artifact.method_artifact_ids))
    inputs = []
    if artifact.execution_recipe is None:
        inputs = [
            InputRef(artifact_id=ArtifactID.from_sha256_hex(aid), role="method")
            for aid in unique_method_ids
        ]
    else:
        if method_refs is not None and set(method_refs) != set(unique_method_ids):
            raise ValueError("chain_selected_method_set_mismatch")
        for aid in unique_method_ids:
            selected = (
                method_refs[aid]
                if method_refs is not None
                else ArtifactRef(
                    artifact_id=ArtifactID.from_sha256_hex(aid),
                    kind="foundry.method_artifact",
                    media_type="application/json",
                    manifest_profile_sha256=artifact_manifest_profile_sha256(cas.get_manifest(aid)),
                )
            )
            if (
                selected.artifact_id.hex != aid
                or selected.kind != "foundry.method_artifact"
                or selected.media_type != "application/json"
                or selected.manifest_profile_sha256 is None
            ):
                raise ValueError("chain_selected_method_profile_mismatch")
            manifest = cas.get_manifest(selected)
            if (
                manifest.artifact_schema is None
                or manifest.artifact_schema.name != "polisyos.foundry.method_artifact"
                or manifest.artifact_schema.version != MethodArtifact.SCHEMA_VERSION
            ):
                raise ValueError("chain_selected_method_schema_mismatch")
            MethodArtifact.from_canonical_bytes(cas.get_bytes(selected))
            inputs.append(input_ref_from_artifact_ref(selected, role="method"))
    options = PutOptions(
        kind="foundry.chain_artifact",
        media_type="application/json",
        canon=CanonInfo.from_spec(artifact.canonical_spec)
        if artifact.canonical_spec is not None
        else None,
        schema=SchemaInfo(
            name="polisyos.foundry.chain_artifact",
            version=artifact.schema_version,
        ),
        producer=ProducerInfo(
            component="foundry.artifacts",
            version=__version__,
        ),
        inputs=inputs,
    )
    if return_selected_profile:
        return cas.put_bytes(content, options, return_selected_profile=True)
    return cas.put_bytes(content, options)


def load_compiled_chain(
    cas: FileSystemCAS,
    ref: ArtifactRef,
    *,
    registry: MethodRegistry | None = None,
) -> CompiledMethodChain:
    """Rebuild a selected executable recipe through the current composer.

    Args:
        cas: Store holding the recipe and its selected method-artifact inputs.
        ref: Exact selected chain view, never an inferred default authority.
        registry: Current method registry; no serialized Python is executed.

    Returns:
        A freshly validated chain with authored parameters and occurrence IDs.

    Raises:
        ValueError: If legacy, source, ABI, profile or replay meaning is unavailable.
        FileNotFoundError: If an actual selected artifact member is missing.
    """
    from polisyos.core.canon import from_canonical_bytes

    from ..registry import MethodRegistry
    from ._chain import _rebuild_chain_recipe

    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ValueError("selected_chain_manifest_profile_required")
    if ref.kind != "foundry.chain_artifact" or ref.media_type != "application/json":
        raise ValueError("selected_chain_type_mismatch")
    manifest = cas.get_manifest(ref)
    if manifest.artifact_schema is None or (
        manifest.artifact_schema.name != "polisyos.foundry.chain_artifact"
        or manifest.artifact_schema.version != ChainArtifact.SCHEMA_VERSION
    ):
        raise ValueError("historical_chain_recipe_not_executable")
    from ._chain import _RECIPE_CANON

    if manifest.canon != CanonInfo.from_spec(_RECIPE_CANON):
        raise ValueError("selected_chain_canonical_profile_mismatch")
    payload = from_canonical_bytes(cas.get_bytes(ref))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != ChainArtifact.SCHEMA_VERSION
    ):
        raise ValueError("unsupported_chain_artifact_schema")
    try:
        methods = {}
        for source in manifest.inputs:
            if source.role != "method" or source.manifest_profile_sha256 is None:
                raise ValueError("selected_chain_method_view_required")
            selected = ArtifactRef(
                artifact_id=source.artifact_id,
                kind="foundry.method_artifact",
                media_type="application/json",
                manifest_profile_sha256=source.manifest_profile_sha256,
            )
            method_manifest = cas.get_manifest(selected)
            if method_manifest.artifact_schema is None or (
                method_manifest.artifact_schema.name != "polisyos.foundry.method_artifact"
                or method_manifest.artifact_schema.version != MethodArtifact.SCHEMA_VERSION
            ):
                raise ValueError("selected_chain_method_schema_mismatch")
            aid = selected.artifact_id.hex
            if aid in methods:
                raise ValueError("duplicate_selected_chain_method")
            methods[aid] = MethodArtifact.from_canonical_bytes(cas.get_bytes(selected))
        if set(methods) != set(payload["method_artifact_ids"]):
            raise ValueError("selected_chain_method_set_mismatch")
        return _rebuild_chain_recipe(
            payload, methods, registry if registry is not None else MethodRegistry.get_instance()
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid_chain_execution_recipe") from exc


def store_execution_evidence(
    cas: FileSystemCAS,
    evidence: ExecutionEvidence,
    *,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist an `ExecutionEvidence` receipt linked to chain/input/output refs."""
    from polisyos.core.artifacts.store import PutOptions

    if type(return_selected_profile) is not bool:
        raise TypeError("return_selected_profile must be a bool")
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

    options = PutOptions(
        kind="foundry.execution_evidence",
        canon=CanonInfo.from_spec(_ARTIFACT_CANON),
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
    )
    if return_selected_profile:
        return cas.put_bytes(content, options, return_selected_profile=True)
    return cas.put_bytes(content, options)


def load_execution_evidence(cas: FileSystemCAS, ref: ArtifactRef) -> ExecutionEvidence:
    """Read a selected 1.1 declared provenance record with its actual profile.

    Args:
        cas: Store containing the immutable evidence and selected manifest.
        ref: Exact selected evidence reference.

    Returns:
        The canonical typed evidence, without independently attesting its assertions.

    Raises:
        ValueError: If selection, kind, schema or canonical profile is unavailable.
        FileNotFoundError: If the selected content or manifest is missing.
    """
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise ValueError("selected_execution_evidence_profile_required")
    if ref.kind != "foundry.execution_evidence" or ref.media_type != "application/json":
        raise ValueError("selected_execution_evidence_type_mismatch")
    manifest = cas.get_manifest(ref)
    if manifest.artifact_schema != SchemaInfo(
        name="polisyos.foundry.execution_evidence", version=ExecutionEvidence.SCHEMA_VERSION
    ) or manifest.canon != CanonInfo.from_spec(_ARTIFACT_CANON):
        raise ValueError("selected_execution_evidence_profile_mismatch")
    evidence = ExecutionEvidence.from_canonical_bytes(cas.get_bytes(ref))
    if manifest.inputs != evidence.to_manifest().inputs:
        raise ValueError("selected_execution_evidence_input_lineage_mismatch")
    return evidence
