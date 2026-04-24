"""
ChainArtifact -- immutable artifact capturing a method chain's composition
and topology for CAS-backed provenance (Law J).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID, uuid5

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    InputRef,
    IntegrityInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.canon import (
    content_hash as compute_content_hash,
)
from polisyos.core.canon import (
    to_canonical_bytes,
    truncated_hash,
)

from ._artifacts_fingerprint import (
    ARTIFACTS_VERSION,
    HASH_TRUNCATE_LENGTH,
    _artifact_id_from_bytes,
    _float_payload,
    _utc_now,
)
from ._artifacts_method import MethodArtifact
from ._artifacts_records import ChainNodeRecord, SlotBindingRecord

if TYPE_CHECKING:
    from .composer import CompiledMethodChain, MethodNode

__all__ = [
    "ChainArtifact",
]

logger = get_logger(__name__)

CHAIN_ID_NAMESPACE = uuid5(UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), "polisyos.chain")


def _stable_node_id(node: MethodNode) -> str:
    node_key = node.node_key
    if node_key is None:
        return f"{node.method_fqn}|unknown|{node.instance_index}"
    return f"{node_key.method_fqn}|{node_key.static_params_digest}|{node.instance_index}"


@dataclass(frozen=True, slots=True)
class ChainArtifact:
    """
    Artifact capturing a method chain's composition.

    This is the "recipe" for a simulation -- it records which methods
    are connected, in what order, and with what bindings.
    """

    # Identity
    chain_id: UUID
    chain_hash: str
    topology_hash: str

    # Composition
    method_fqns: tuple[str, ...]
    method_artifact_ids: tuple[str, ...]
    nodes: tuple[ChainNodeRecord, ...]
    bindings: tuple[SlotBindingRecord, ...]
    execution_order: tuple[str, ...]

    # Metadata
    composed_at: datetime
    warnings: tuple[str, ...]

    # Schema version
    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    _artifact_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_artifact_id", _artifact_id_from_bytes(self.to_canonical_bytes()))

    @classmethod
    def from_chain(
        cls,
        chain: CompiledMethodChain,
        method_artifacts: Sequence[MethodArtifact] | Mapping[UUID, MethodArtifact],
        *,
        chain_id: UUID | None = None,
        composed_at: datetime | None = None,
    ) -> ChainArtifact:
        """
        Create artifact from a compiled chain.

        Args:
            chain: Compiled method chain from Composer
            method_artifacts: Artifacts for each method in chain
            chain_id: Override ID (for testing)
            composed_at: Override timestamp (for testing)

        Returns:
            Immutable ChainArtifact
        """
        if isinstance(method_artifacts, Mapping):
            artifact_map = dict(method_artifacts)
        else:
            if len(method_artifacts) != len(chain.execution_order):
                raise ValueError("method_artifacts must match chain execution order length")
            artifact_map = {
                node_id: artifact
                for node_id, artifact in zip(chain.execution_order, method_artifacts)
            }

        node_id_map: dict[UUID, str] = {}
        for node_id in chain.dag.nodes:
            node = chain.get_node(node_id)
            node_id_map[node_id] = _stable_node_id(node)

        method_fqns = tuple(chain.signatures[node_id].fqn for node_id in chain.execution_order)
        method_artifact_ids = tuple(
            artifact_map[node_id].artifact_id for node_id in chain.execution_order
        )

        nodes: list[ChainNodeRecord] = []
        for node_id, node in chain.dag.nodes.items():
            artifact = artifact_map.get(node_id)
            if artifact is None:
                raise ValueError(f"Missing MethodArtifact for node {node_id}")
            nodes.append(
                ChainNodeRecord(
                    node_id=node_id_map[node_id],
                    method_fqn=node.method_fqn,
                    method_artifact_id=artifact.artifact_id,
                    static_params_hash=artifact.specialization.static_params_hash,
                    instance_index=node.instance_index,
                )
            )

        binding_records = tuple(
            SlotBindingRecord.from_binding(b, node_id_map=node_id_map) for b in chain.bindings
        )
        if any(
            record.source_node_id is None or record.target_node_id is None
            for record in binding_records
        ):
            raise ValueError(
                "All bindings must include source and target node IDs for deterministic hashing"
            )

        topology_hash = cls._compute_topology_hash(nodes, binding_records)
        chain_hash = cls._compute_chain_hash(nodes, binding_records)

        execution_order = tuple(node_id_map[nid] for nid in chain.execution_order)
        chain_identifier = chain_id or uuid5(CHAIN_ID_NAMESPACE, chain_hash)

        return cls(
            chain_id=chain_identifier,
            chain_hash=chain_hash,
            topology_hash=topology_hash,
            method_fqns=method_fqns,
            method_artifact_ids=method_artifact_ids,
            nodes=tuple(sorted(nodes, key=lambda n: n.node_id)),
            bindings=binding_records,
            execution_order=execution_order,
            composed_at=composed_at or _utc_now(),
            warnings=chain.warnings,
        )

    @staticmethod
    def _compute_topology_hash(
        nodes: Sequence[ChainNodeRecord],
        bindings: Sequence[SlotBindingRecord],
    ) -> str:
        """Compute deterministic hash of chain topology."""
        node_payload = sorted(
            [{"node_id": n.node_id} for n in nodes],
            key=lambda item: item["node_id"],
        )
        binding_payload = sorted(
            [
                {
                    "src_node_id": b.source_node_id,
                    "src_slot": b.source_slot,
                    "tgt_node_id": b.target_node_id,
                    "tgt_slot": b.target_slot,
                    "conversion_factor": _float_payload(b.conversion_factor),
                    "requires_fx_rate": b.requires_fx_rate,
                }
                for b in bindings
            ],
            key=lambda item: (
                item["src_node_id"] or "",
                item["src_slot"],
                item["tgt_node_id"] or "",
                item["tgt_slot"],
            ),
        )
        content = to_canonical_bytes({"nodes": node_payload, "bindings": binding_payload})
        return truncated_hash(content, length=HASH_TRUNCATE_LENGTH)

    @staticmethod
    def _compute_chain_hash(
        nodes: Sequence[ChainNodeRecord],
        bindings: Sequence[SlotBindingRecord],
    ) -> str:
        """Compute deterministic hash of chain semantics."""
        node_payload = sorted(
            [
                {
                    "node_id": n.node_id,
                    "method_artifact_id": n.method_artifact_id,
                    "method_fqn": n.method_fqn,
                }
                for n in nodes
            ],
            key=lambda item: item["node_id"],
        )
        binding_payload = sorted(
            [
                {
                    "src_node_id": b.source_node_id,
                    "src_slot": b.source_slot,
                    "tgt_node_id": b.target_node_id,
                    "tgt_slot": b.target_slot,
                    "conversion_factor": _float_payload(b.conversion_factor),
                    "requires_fx_rate": b.requires_fx_rate,
                }
                for b in bindings
            ],
            key=lambda item: (
                item["src_node_id"] or "",
                item["src_slot"],
                item["tgt_node_id"] or "",
                item["tgt_slot"],
            ),
        )
        content = to_canonical_bytes({"nodes": node_payload, "bindings": binding_payload})
        return truncated_hash(content, length=HASH_TRUNCATE_LENGTH)

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "chain_hash": self.chain_hash,
            "topology_hash": self.topology_hash,
            "method_fqns": list(self.method_fqns),
            "method_artifact_ids": list(self.method_artifact_ids),
            "nodes": [n.to_dict() for n in self.nodes],
            "bindings": [b.to_dict() for b in self.bindings],
            "execution_order": list(self.execution_order),
            "warnings": list(self.warnings),
        }

    def to_canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes for CAS storage."""
        return to_canonical_bytes(self._identity_payload())

    def to_manifest(self) -> ArtifactManifest:
        """Convert to CAS-storable manifest."""
        content = self.to_canonical_bytes()
        content_hash = compute_content_hash(content)

        return ArtifactManifest(
            artifact_id=ArtifactID.from_sha256_hex(content_hash),
            kind="foundry.chain_artifact",
            media_type="application/json",
            byte_size=len(content),
            created_at=self.composed_at,
            artifact_schema=SchemaInfo(
                name="polisyos.foundry.chain_artifact",
                version=self.SCHEMA_VERSION,
            ),
            producer=ProducerInfo(
                component="foundry.artifacts",
                version=ARTIFACTS_VERSION,
            ),
            inputs=[
                InputRef(artifact_id=ArtifactID.from_sha256_hex(aid), role="method")
                for aid in sorted(set(self.method_artifact_ids))
            ],
            integrity=IntegrityInfo(sha256=content_hash),
        )

    @property
    def artifact_id(self) -> str:
        """Compute artifact ID from content."""
        return self._artifact_id

    @property
    def method_count(self) -> int:
        """Number of methods in chain."""
        return len(self.nodes)

    @property
    def has_warnings(self) -> bool:
        """Whether chain has validation warnings."""
        return len(self.warnings) > 0
