"""
ChainArtifact -- immutable artifact capturing a method chain's composition
and topology for CAS-backed provenance (Law J).
"""

from __future__ import annotations

import graphlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

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
    CanonSpec,
    from_canonical_bytes,
    to_canonical_bytes,
    truncated_hash,
)
from polisyos.core.canon import (
    content_hash as compute_content_hash,
)

from ._fingerprint import (
    ARTIFACTS_VERSION,
    HASH_TRUNCATE_LENGTH,
    _artifact_id_from_bytes,
    _float_payload,
    _utc_now,
)
from ._method import MethodArtifact
from ._records import ChainNodeRecord, SlotBindingRecord

if TYPE_CHECKING:
    from ..components.composer import CompiledMethodChain, MethodNode
    from ..selection.registry import MethodRegistry

__all__ = [
    "ChainArtifact",
    "CompiledChainPlan",
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


# Legacy ChainArtifact remains a provenance recipe. The distinct wire below
# carries a reversible executable plan without changing that recipe's identity.
_PLAN_CANON = CanonSpec(forbid_floats=False, exclude_none=False)


class _PlanNode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    node_id: str
    method_fqn: str
    signature_abi: str
    instance_index: int = Field(ge=0)
    insertion_order: int = Field(ge=0)
    commutes_with: list[str]
    static_params_json: str
    params_json: str


class _PlanBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_slot: str
    target_slot: str
    conversion_factor_hex: str | None
    requires_fx_rate: bool


class _PlanEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: str
    target_id: str
    bindings: list[_PlanBinding]


class _PlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0.0"]
    nodes: list[_PlanNode]
    data_flow: list[_PlanEdge]
    predecessors: dict[str, list[str]]
    execution_order: list[str]
    cache_keys: dict[str, str]
    warnings: list[str]


def _plain_json(value: Any, active: set[int] | None = None) -> None:
    """Refuse non-JSON values and reserved canonical tags without coercion."""
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) in (list, dict):
        ancestors = set() if active is None else active
        if id(value) in ancestors:
            raise ValueError("Compiled plan parameters cannot contain JSON cycles")
        ancestors.add(id(value))
        try:
            if type(value) is list:
                for item in value:
                    _plain_json(item, ancestors)
            else:
                for key, item in value.items():
                    if type(key) is not str or key == "_type":
                        raise ValueError(
                            "Compiled plan parameters require untagged string JSON keys"
                        )
                    _plain_json(item, ancestors)
        finally:
            ancestors.remove(id(value))
        return
    raise ValueError("Compiled plan parameters must be finite plain JSON values")


def _params_bytes(params: Mapping[str, Any]) -> bytes:
    values = dict(params)
    _plain_json(values)
    return to_canonical_bytes(values, _PLAN_CANON)


def _read_params(encoded: str) -> dict[str, Any]:
    values = from_canonical_bytes(encoded.encode("utf-8"))
    if type(values) is not dict:
        raise ValueError("Compiled plan parameters must be a JSON object")
    _plain_json(values)
    if _params_bytes(values) != encoded.encode("utf-8"):
        raise ValueError("Compiled plan parameter encoding is not canonical")
    return values


def _binding_payload(binding: Any) -> dict[str, Any]:
    factor = binding.conversion_factor
    return {
        "source_slot": binding.source_slot,
        "target_slot": binding.target_slot,
        "conversion_factor_hex": float(factor).hex() if factor is not None else None,
        "requires_fx_rate": binding.requires_fx_rate,
    }


def _decode_plan(content: bytes) -> _PlanPayload:
    payload = _PlanPayload.model_validate(from_canonical_bytes(content))
    if to_canonical_bytes(payload.model_dump(), _PLAN_CANON) != content:
        raise ValueError("Compiled plan bytes must use the canonical wire encoding")
    ids = {node.node_id for node in payload.nodes}
    if len(ids) != len(payload.nodes):
        raise ValueError("Compiled plan has duplicate node UUIDs")
    for node in payload.nodes:
        if str(UUID(node.node_id)) != node.node_id:
            raise ValueError("Compiled plan node ID must be a canonical UUID")
        _read_params(node.static_params_json)
        _read_params(node.params_json)
    if set(payload.predecessors) != ids or set(payload.cache_keys) != ids:
        raise ValueError("Compiled plan must cover every concrete node")
    if set(payload.execution_order) != ids or len(payload.execution_order) != len(ids):
        raise ValueError("Compiled plan execution order must cover every concrete node once")
    for parents in payload.predecessors.values():
        if len(parents) != len(set(parents)) or not set(parents).issubset(ids):
            raise ValueError("Compiled plan has duplicate or missing predecessor occurrences")
    try:
        graphlib.TopologicalSorter(payload.predecessors).prepare()
    except graphlib.CycleError as exc:
        from polisyos.foundry.methods.exceptions import CyclicDependencyError

        fqns = {node.node_id: node.method_fqn for node in payload.nodes}
        cycle = exc.args[1] if len(exc.args) > 1 else list(ids)
        raise CyclicDependencyError([fqns[node_id] for node_id in cycle]) from exc
    positions = {node_id: index for index, node_id in enumerate(payload.execution_order)}
    for node_id, parents in payload.predecessors.items():
        if any(positions[parent] >= positions[node_id] for parent in parents):
            raise ValueError("Compiled plan order violates its effective predecessors")
    pairs: set[tuple[str, str]] = set()
    for edge in payload.data_flow:
        pair = (edge.source_id, edge.target_id)
        if edge.source_id not in ids or edge.target_id not in ids or pair in pairs:
            raise ValueError("Compiled plan has duplicate or missing data-flow occurrences")
        pairs.add(pair)
        for binding in edge.bindings:
            factor = binding.conversion_factor_hex
            if factor is not None and not math.isfinite(float.fromhex(factor)):
                raise ValueError("Compiled plan conversion factor must be finite")
    return payload


@dataclass(frozen=True, slots=True)
class CompiledChainPlan:
    """Byte-immutable, reversible cold execution plan in wire version 1.0.0.

    This internal artifact API selects the current registry implementation and
    reconciles its ABI. It attests neither historical source code nor cached
    results, checkpoint prefixes, scientific validity or permission to execute.
    Parameters support finite plain JSON values with string keys; arbitrary
    Python values and the canonical ``_type`` parameter key are unsupported.
    """

    content: bytes
    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    def __post_init__(self) -> None:
        if type(self.content) is not bytes:
            raise TypeError("CompiledChainPlan content must be immutable bytes")
        _decode_plan(self.content)

    @classmethod
    def from_chain(cls, chain: CompiledMethodChain) -> CompiledChainPlan:
        """Capture concrete nodes, data flow and the frozen effective graph."""
        successors = {node_id: set() for node_id in chain.dag.nodes}
        for node_id, parents in chain.dag.predecessors.items():
            for parent in parents:
                if parent not in successors or node_id not in successors:
                    raise ValueError("Compiled plan has an unknown effective occurrence")
                successors[parent].add(node_id)
        if successors != {node_id: set(ids) for node_id, ids in chain.dag.successors.items()}:
            raise ValueError("Compiled plan effective adjacency disagrees")
        bindings = []
        for (source, target), link in chain.dag.edges.items():
            if (
                source not in chain.dag.nodes
                or target not in chain.dag.nodes
                or link.source_id != source
                or link.target_id != target
                or link.source_fqn != chain.signatures[source].fqn
                or link.target_fqn != chain.signatures[target].fqn
            ):
                raise ValueError("Compiled plan data-flow identity disagrees")
            for binding in link.bindings:
                if binding.source_node_id != source or binding.target_node_id != target:
                    raise ValueError("Compiled plan binding occurrence disagrees")
                bindings.append(binding)
        bindings.sort(
            key=lambda binding: (
                str(binding.target_node_id),
                binding.target_slot,
                str(binding.source_node_id),
                binding.source_slot,
            )
        )
        if tuple(bindings) != chain.bindings:
            raise ValueError("Compiled plan flat bindings disagree with data flow")
        nodes = []
        for node_id, node in chain.dag.nodes.items():
            signature = chain.signatures[node_id]
            if node.id != node_id or node.method_fqn != signature.fqn:
                raise ValueError("Compiled plan node/signature identity disagrees")
            nodes.append(
                {
                    "node_id": str(node_id),
                    "method_fqn": node.method_fqn,
                    "signature_abi": signature.abi_digest(),
                    "instance_index": node.instance_index,
                    "insertion_order": node._insertion_order,
                    "commutes_with": sorted(node.commutes_with),
                    "static_params_json": _params_bytes(node.static_params).decode("utf-8"),
                    "params_json": _params_bytes(node.params).decode("utf-8"),
                }
            )
        payload = {
            "schema_version": cls.SCHEMA_VERSION,
            "nodes": nodes,
            "data_flow": [
                {
                    "source_id": str(source),
                    "target_id": str(target),
                    "bindings": [_binding_payload(binding) for binding in link.bindings],
                }
                for (source, target), link in chain.dag.edges.items()
            ],
            "predecessors": {
                str(node_id): sorted(str(parent) for parent in parents)
                for node_id, parents in chain.dag.predecessors.items()
            },
            "execution_order": [str(node_id) for node_id in chain.execution_order],
            "cache_keys": {str(node_id): key for node_id, key in chain.cache_keys.items()},
            "warnings": list(chain.warnings),
        }
        return cls(to_canonical_bytes(payload, _PLAN_CANON))

    @classmethod
    def from_canonical_bytes(cls, content: bytes) -> CompiledChainPlan:
        """Validate persisted plan bytes without executing any method body."""
        return cls(content)

    def to_canonical_bytes(self) -> bytes:
        """Return the immutable canonical wire bytes for persistence."""
        return self.content

    def to_chain(self, *, registry: MethodRegistry | None = None) -> CompiledMethodChain:
        """Rebuild and reconcile the plan through the current canonical owners.

        Raises:
            ValueError: Payload, ABI, binding, graph or order differs from the
                canonical current composition. Existing composer/linker typed
                refusals propagate before this function returns a runnable chain.
        """
        from ..components.composer import MethodComposer, MethodNode, SemanticValidationLevel
        from ..selection.registry import MethodRegistry

        payload = _decode_plan(self.content)
        current = registry if registry is not None else MethodRegistry.get_instance()
        restored = []
        for record in payload.nodes:
            signature = current.get(record.method_fqn).signature
            if signature.abi_digest() != record.signature_abi:
                raise ValueError(f"Compiled plan current signature ABI mismatch: {record.node_id}")
            restored.append(
                MethodNode(
                    id=UUID(record.node_id),
                    method_fqn=record.method_fqn,
                    params=_read_params(record.params_json),
                    static_params=_read_params(record.static_params_json),
                    instance_index=record.instance_index,
                    commutes_with=frozenset(record.commutes_with),
                    _insertion_order=record.insertion_order,
                )
            )
        composer = MethodComposer.from_nodes(restored, registry=current)
        nodes_by_id = composer.dag.nodes
        for edge in payload.data_flow:
            mapping = {binding.source_slot: binding.target_slot for binding in edge.bindings}
            if len(mapping) != len(edge.bindings):
                raise ValueError("Compiled plan repeats a source slot within one connection")
            actual = composer.connect(
                nodes_by_id[UUID(edge.source_id)], nodes_by_id[UUID(edge.target_id)], mapping
            )
            if [_binding_payload(binding) for binding in actual.bindings] != [
                binding.model_dump() for binding in edge.bindings
            ]:
                raise ValueError("Compiled plan binding compatibility mismatch")
        chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
        for record in payload.nodes:
            if chain.signatures[UUID(record.node_id)].abi_digest() != record.signature_abi:
                raise ValueError(f"Compiled plan restored signature ABI mismatch: {record.node_id}")
        actual_parents = {
            str(node_id): sorted(str(parent) for parent in parents)
            for node_id, parents in chain.dag.predecessors.items()
        }
        if actual_parents != payload.predecessors:
            raise ValueError("Compiled plan effective dependency mismatch")
        if [str(node_id) for node_id in chain.execution_order] != payload.execution_order:
            raise ValueError("Compiled plan execution order mismatch")
        if {str(node_id): key for node_id, key in chain.cache_keys.items()} != payload.cache_keys:
            raise ValueError("Compiled plan composition cache-key mismatch")
        return chain
