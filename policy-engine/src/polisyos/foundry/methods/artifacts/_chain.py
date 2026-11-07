"""
ChainArtifact -- immutable artifact capturing a method chain's composition
and topology for CAS-backed provenance (Law J).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID, uuid5

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    CanonInfo,
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
    _ARTIFACT_CANON,
    _ARTIFACT_CANON_PROFILE,
    ARTIFACTS_VERSION,
    HASH_TRUNCATE_LENGTH,
    _artifact_id_from_bytes,
    _finite_artifact_float,
    _float_payload,
    _require_source_bound_operation,
    _utc_now,
)
from ._method import MethodArtifact
from ._records import ChainNodeRecord, SlotBindingRecord

if TYPE_CHECKING:
    from ..components.composer import CompiledMethodChain, MethodNode
    from ..registry import MethodRegistry

__all__ = [
    "ChainArtifact",
]

logger = get_logger(__name__)

CHAIN_ID_NAMESPACE = uuid5(UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), "polisyos.chain")
_RECIPE_CANON = CanonSpec(version="0.2.0", forbid_floats=False, exclude_none=False)


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
    execution_recipe: bytes | None = field(default=None, repr=False)

    # Schema version
    SCHEMA_VERSION: ClassVar[str] = "1.1.0"

    _artifact_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.chain_id, UUID) or not isinstance(self.composed_at, datetime):
            raise ValueError("invalid_chain_artifact_identity_or_time")
        if any(type(v) is not str for v in (self.chain_hash, self.topology_hash)):
            raise ValueError("invalid_chain_artifact_hash_field")
        for name in ("method_fqns", "method_artifact_ids", "execution_order", "warnings"):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or any(type(v) is not str for v in values):
                raise ValueError("invalid_chain_artifact_string_sequence")
            object.__setattr__(self, name, tuple(values))
        for node in self.nodes:
            if (
                not isinstance(node, ChainNodeRecord)
                or any(
                    type(v) is not str
                    for v in (node.node_id, node.method_fqn, node.method_artifact_id)
                )
                or (
                    node.static_params_hash is not None and type(node.static_params_hash) is not str
                )
                or type(node.instance_index) is not int
            ):
                raise ValueError("invalid_chain_artifact_node_record")
        for binding in self.bindings:
            if (
                not isinstance(binding, SlotBindingRecord)
                or any(
                    type(v) is not str
                    for v in (
                        binding.source_method,
                        binding.source_slot,
                        binding.target_method,
                        binding.target_slot,
                    )
                )
                or any(
                    v is not None and type(v) is not str
                    for v in (binding.source_node_id, binding.target_node_id)
                )
                or type(binding.requires_fx_rate) is not bool
            ):
                raise ValueError("invalid_chain_artifact_binding_record")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(
            self,
            "bindings",
            tuple(
                replace(
                    binding, conversion_factor=_finite_artifact_float(binding.conversion_factor)
                )
                if binding.conversion_factor is not None
                else binding
                for binding in self.bindings
            ),
        )
        if self.execution_recipe is not None and type(self.execution_recipe) is not bytes:
            raise TypeError("execution_recipe must be immutable canonical bytes")
        object.__setattr__(self, "_artifact_id", _artifact_id_from_bytes(self.to_canonical_bytes()))

    @property
    def schema_version(self) -> str:
        """Keep legacy recipe-only objects in their original 1.0 profile."""
        return "1.0.0" if self.canonical_spec is None else self.SCHEMA_VERSION

    @property
    def canonical_spec(self) -> CanonSpec | None:
        """Return the exact encoder profile; valid nonnumeric 1.0 bytes stay unchanged."""
        if self.execution_recipe is not None:
            return _RECIPE_CANON
        if any(binding.conversion_factor is not None for binding in self.bindings):
            return _ARTIFACT_CANON
        return None

    @classmethod
    def from_canonical_bytes(cls, data: bytes) -> ChainArtifact:
        """Read an immutable composition record, without claiming it is executable.

        Args:
            data: Complete canonical record bytes.

        Returns:
            The typed record. Executable reconstruction requires ``load_compiled_chain``.

        Raises:
            ValueError: If the version, numeric profile, shape or canonical bytes disagree.
        """
        payload = from_canonical_bytes(data)
        if not isinstance(payload, dict) or payload.get("schema_version") not in ("1.0.0", "1.1.0"):
            raise ValueError("unsupported_chain_artifact_schema")
        try:
            recipe = payload.get("execution_recipe")
            artifact = cls(
                chain_id=uuid5(CHAIN_ID_NAMESPACE, payload["chain_hash"]),
                chain_hash=payload["chain_hash"],
                topology_hash=payload["topology_hash"],
                method_fqns=tuple(payload["method_fqns"]),
                method_artifact_ids=tuple(payload["method_artifact_ids"]),
                nodes=tuple(ChainNodeRecord(**row) for row in payload["nodes"]),
                bindings=tuple(SlotBindingRecord(**row) for row in payload["bindings"]),
                execution_order=tuple(payload["execution_order"]),
                warnings=tuple(payload["warnings"]),
                composed_at=_utc_now(),
                execution_recipe=to_canonical_bytes(recipe, _RECIPE_CANON)
                if recipe is not None
                else None,
            )
            if artifact.to_canonical_bytes() != data:
                raise ValueError("chain_artifact_not_canonical_or_profile_unavailable")
            return artifact
        except (KeyError, TypeError) as exc:
            raise ValueError("invalid_chain_artifact_record") from exc

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

        from ..components.composer import reconcile_validation_context

        context = reconcile_validation_context(chain)

        node_id_map: dict[UUID, str] = {}
        for node_id in chain.dag.nodes:
            node = chain.get_node(node_id)
            node_id_map[node_id] = _stable_node_id(node)

        recipe = to_canonical_bytes(
            {
                "schema_version": 1,
                "execution_profile": "ordinary-class-source-v1",
                "mode": context.mode.name,
                "linker_config": asdict(chain.linker_config),
                "nodes": [
                    {
                        "node_id": node_id_map[node.id],
                        "node_uuid": str(node.id),
                        "method_fqn": node.method_fqn,
                        "method_artifact_id": artifact_map[node.id].artifact_id,
                        "signature_abi_digest": chain.signatures[node.id].abi_digest(),
                        "static_params": dict(node.static_params),
                        "dynamic_params": dict(node.params),
                    }
                    for node in sorted(
                        chain.dag.nodes.values(), key=lambda item: item._insertion_order
                    )
                ],
                "edges": [
                    {
                        "source": str(source),
                        "target": str(target),
                        "link_mode": edge.link_mode,
                        "mapping": {b.source_slot: b.target_slot for b in edge.bindings},
                    }
                    for (source, target), edge in chain.dag.edges.items()
                ],
                "predecessors": {
                    str(node): sorted(str(parent) for parent in parents)
                    for node, parents in chain.dag.predecessors.items()
                },
            },
            _RECIPE_CANON,
        )

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

        topology_hash = cls._compute_topology_hash(nodes, binding_records, spec=_RECIPE_CANON)
        chain_hash = cls._compute_chain_hash(nodes, binding_records, execution_recipe=recipe)

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
            execution_recipe=recipe,
        )

    @staticmethod
    def _compute_topology_hash(
        nodes: Sequence[ChainNodeRecord],
        bindings: Sequence[SlotBindingRecord],
        *,
        spec: CanonSpec | None = None,
    ) -> str:
        """Compute deterministic hash of chain topology."""
        if spec is None and any(b.conversion_factor is not None for b in bindings):
            spec = _ARTIFACT_CANON
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
                    "conversion_factor": (
                        _finite_artifact_float(b.conversion_factor)
                        if b.conversion_factor is not None
                        else None
                    )
                    if spec is not None
                    else _float_payload(b.conversion_factor),
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
        content = to_canonical_bytes({"nodes": node_payload, "bindings": binding_payload}, spec)
        return truncated_hash(content, length=HASH_TRUNCATE_LENGTH)

    @staticmethod
    def _compute_chain_hash(
        nodes: Sequence[ChainNodeRecord],
        bindings: Sequence[SlotBindingRecord],
        *,
        execution_recipe: bytes | None = None,
    ) -> str:
        """Compute deterministic hash of chain semantics."""
        spec = (
            _RECIPE_CANON
            if execution_recipe is not None
            else (
                _ARTIFACT_CANON if any(b.conversion_factor is not None for b in bindings) else None
            )
        )
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
                    "conversion_factor": (
                        _finite_artifact_float(b.conversion_factor)
                        if b.conversion_factor is not None
                        else None
                    )
                    if spec is not None
                    else _float_payload(b.conversion_factor),
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
        payload = {"nodes": node_payload, "bindings": binding_payload}
        if execution_recipe is not None:
            payload["execution_recipe"] = from_canonical_bytes(execution_recipe)
        content = to_canonical_bytes(payload, spec)
        return truncated_hash(content, length=HASH_TRUNCATE_LENGTH)

    def _identity_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "chain_hash": self.chain_hash,
            "topology_hash": self.topology_hash,
            "method_fqns": list(self.method_fqns),
            "method_artifact_ids": list(self.method_artifact_ids),
            "nodes": [n.to_dict() for n in self.nodes],
            "bindings": [b.to_dict() for b in self.bindings],
            "execution_order": list(self.execution_order),
            "warnings": list(self.warnings),
        }
        if self.canonical_spec is not None:
            payload["bindings"] = [
                {
                    **record.to_dict(),
                    "conversion_factor": (
                        _finite_artifact_float(record.conversion_factor)
                        if record.conversion_factor is not None
                        else None
                    ),
                }
                for record in self.bindings
            ]
            payload["canonical_profile"] = _ARTIFACT_CANON_PROFILE
        if self.execution_recipe is not None:
            payload["execution_recipe"] = from_canonical_bytes(self.execution_recipe)
            payload["canonical_profile"] = "core-canon-0.2.0-finite-floats-preserve-null-v1"
        return payload

    def to_canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes for CAS storage."""
        return to_canonical_bytes(self._identity_payload(), self.canonical_spec)

    def to_manifest(self) -> ArtifactManifest:
        """Convert to CAS-storable manifest."""
        content = self.to_canonical_bytes()
        content_hash = compute_content_hash(content)

        return ArtifactManifest(
            artifact_id=ArtifactID.from_sha256_hex(content_hash),
            kind="foundry.chain_artifact",
            media_type="application/json",
            byte_size=len(content),
            canon=CanonInfo.from_spec(self.canonical_spec)
            if self.canonical_spec is not None
            else None,
            created_at=self.composed_at,
            artifact_schema=SchemaInfo(
                name="polisyos.foundry.chain_artifact",
                version=self.schema_version,
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


def _rebuild_chain_recipe(
    payload: dict[str, Any],
    methods: Mapping[str, MethodArtifact],
    registry: MethodRegistry,
) -> CompiledMethodChain:
    """Resolve declared methods and replay the one canonical composition owner."""
    from ..compiler.specialization import compute_static_params_hash
    from ..components.composer import MethodComposer, SemanticValidationLevel
    from ..components.linker import LinkerConfig, SlotLinker

    recipe = payload.get("execution_recipe")
    if (
        not isinstance(recipe, dict)
        or set(recipe)
        != {
            "schema_version",
            "execution_profile",
            "mode",
            "linker_config",
            "nodes",
            "edges",
            "predecessors",
        }
        or type(recipe["schema_version"]) is not int
        or recipe["schema_version"] != 1
    ):
        raise ValueError("unsupported_chain_execution_recipe")
    if recipe["execution_profile"] != "ordinary-class-source-v1":
        raise ValueError("unsupported_chain_execution_profile")
    config = recipe["linker_config"]
    if (
        not isinstance(config, dict)
        or set(config) != set(asdict(LinkerConfig()))
        or any(type(value) is not bool for value in config.values())
    ):
        raise ValueError("unsupported_chain_linker_context")
    mode = SemanticValidationLevel[recipe["mode"]]
    composer = MethodComposer(registry=registry, linker=SlotLinker(LinkerConfig(**config)))
    artifacts_by_node: dict[UUID, MethodArtifact] = {}
    if not isinstance(recipe["nodes"], list) or not isinstance(recipe["edges"], list):
        raise ValueError("invalid_chain_recipe_records")
    for record in recipe["nodes"]:
        if not isinstance(record, dict) or set(record) != {
            "node_id",
            "node_uuid",
            "method_fqn",
            "method_artifact_id",
            "signature_abi_digest",
            "static_params",
            "dynamic_params",
        }:
            raise ValueError("invalid_chain_recipe_node")
        method_class = registry.get(record["method_fqn"])
        signature = method_class.signature
        artifact = methods[record["method_artifact_id"]]
        current = MethodArtifact.from_method(method_class, artifact.specialization)
        if (
            signature.abi_digest() != record["signature_abi_digest"]
            or artifact.fqn != signature.fqn
            or artifact.specialization.method_fqn != signature.fqn
            or artifact.source_available is not True
            or current.source_available is not True
            or artifact.source_hash != current.source_hash
            or artifact.source_module != current.source_module
            or artifact.signature_hash != current.signature_hash
            or artifact.metadata_hash != current.metadata_hash
            or artifact.source_fingerprint.module_file_sha256 is None
            or artifact.source_fingerprint.module_file_sha256
            != current.source_fingerprint.module_file_sha256
        ):
            raise ValueError("chain_method_source_or_abi_mismatch")
        _require_source_bound_operation(method_class)
        static, dynamic = record["static_params"], record["dynamic_params"]
        if (
            not isinstance(static, dict)
            or not isinstance(dynamic, dict)
            or set(static) & set(dynamic)
        ):
            raise ValueError("invalid_chain_authored_parameters")
        if compute_static_params_hash(static) != artifact.specialization.static_params_hash:
            raise ValueError("chain_method_static_specialization_mismatch")
        node = composer.add(signature.fqn, **static, **dynamic)
        if to_canonical_bytes(
            [dict(node.static_params), dict(node.params)], _RECIPE_CANON
        ) != to_canonical_bytes([static, dynamic], _RECIPE_CANON):
            raise ValueError("chain_parameter_partition_mismatch")
        node_id = UUID(record["node_uuid"])
        if node_id in artifacts_by_node:
            raise ValueError("duplicate_chain_node_occurrence")
        restored = replace(node, id=node_id)
        if _stable_node_id(restored) != record["node_id"]:
            raise ValueError("chain_occurrence_identity_mismatch")
        # add() remains the sole parameter/occurrence constructor. Restore the
        # recorded UUID only after its typed result has been reconciled.
        del composer._dag.nodes[node.id]
        del composer._dag.predecessors[node.id]
        del composer._dag.successors[node.id]
        del composer._signatures[node.id]
        composer._dag.add_node(restored)
        composer._signatures[node_id] = signature
        artifacts_by_node[node_id] = artifact
    for edge in recipe["edges"]:
        if not isinstance(edge, dict) or set(edge) != {"source", "target", "link_mode", "mapping"}:
            raise ValueError("invalid_chain_recipe_edge")
        if edge["link_mode"] not in {"auto", "explicit"}:
            raise ValueError("unsupported_chain_link_mode")
        source, target = UUID(edge["source"]), UUID(edge["target"])
        composer.connect(
            composer.dag.nodes[source],
            composer.dag.nodes[target],
            None if edge["link_mode"] == "auto" else edge["mapping"],
        )
    chain = composer.build(validate_semantics=mode)
    # Re-emission recomputes requires-only adjacency, levels, full ABI/mode,
    # diagnostics, every parameter and authored edge. Stored order alone is
    # never treated as evidence that a prerequisite exists.
    rebuilt = ChainArtifact.from_chain(chain, artifacts_by_node)
    if rebuilt.to_canonical_bytes() != to_canonical_bytes(payload, _RECIPE_CANON):
        raise ValueError("chain_execution_recipe_replay_mismatch")
    from .._internal.executable_identity import _ExecutableIdentity, _signature_binding

    implementations = {}
    for node_id, signature in chain.signatures.items():
        method_class = registry.get(signature.fqn)
        implementations[node_id] = _ExecutableIdentity(
            method_class, method_class.pure_step, _signature_binding(signature)
        )
    return replace(
        chain, _source_registry=registry, _source_implementations=MappingProxyType(implementations)
    )
