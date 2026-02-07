"""
Method execution artifacts for provenance tracking (Law J).

This module provides immutable artifact types that capture:
- Method identity and compilation context (MethodArtifact)
- Chain composition and topology (ChainArtifact)
- Execution evidence and timing (ExecutionEvidence)

All artifacts are:
- Frozen (immutable after creation)
- Deterministically hashable (canonical serialization)
- CAS-compatible (serialize to ArtifactManifest)
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Mapping, Sequence
from uuid import UUID, uuid4, uuid5

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    IntegrityInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.canon import to_canonical_bytes

from .specialization import Specialization

if TYPE_CHECKING:
    from .base import MethodMetadata, MethodSignature
    from .composer import CompiledMethodChain, MethodNode
    from .linker import SlotBinding

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

__version__ = "1.0.0"

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

HASH_TRUNCATE_LENGTH: int = 32  # 128 bits of SHA256
SOURCE_UNAVAILABLE: str = "unavailable"
CHAIN_ID_NAMESPACE = uuid5(UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), "polisyos.chain")


# =============================================================================
# Utility Functions
# =============================================================================


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def _float_payload(value: float | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {"_type": "float_hex", "value": float(value).hex()}


def _artifact_id_from_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _compute_deterministic_hash(data: Mapping[str, Any]) -> str:
    """Compute deterministic hash of dictionary data."""
    canonical = to_canonical_bytes(dict(data))
    return hashlib.sha256(canonical).hexdigest()[:HASH_TRUNCATE_LENGTH]


def _hash_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _safe_run(cmd: Sequence[str]) -> str | None:
    try:
        result = subprocess.run(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def _find_git_root(start: Path) -> Path | None:
    path = start
    if path.is_file():
        path = path.parent
    for parent in (path,) + tuple(path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _git_blob_hash(root: Path, relpath: str) -> str | None:
    output = _safe_run(["git", "-C", str(root), "ls-tree", "-r", "HEAD", "--", relpath])
    if not output:
        return None
    line = output.splitlines()[0]
    parts = line.split()
    if len(parts) < 3:
        return None
    return parts[2]


def _resolve_module_file(cls: type) -> Path | None:
    try:
        file_path = inspect.getsourcefile(cls) or inspect.getfile(cls)
    except (TypeError, OSError):
        return None
    if not file_path:
        return None
    return Path(file_path)


def _strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]


def _normalized_source_hash(source: str) -> str | None:
    try:
        tree = ast.parse(source)
        _strip_docstrings(tree)
        dumped = ast.dump(tree, include_attributes=False)
    except (SyntaxError, ValueError, TypeError):
        return None
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:HASH_TRUNCATE_LENGTH]


def compute_source_hash(
    cls: type,
    *,
    fallback_value: str = SOURCE_UNAVAILABLE,
) -> str:
    """
    Compute SHA256 hash of a class's source code.

    Args:
        cls: The class to hash
        fallback_value: Value to return if source unavailable

    Returns:
        32-character hex digest or fallback value
    """
    try:
        source = inspect.getsource(cls)
        source = source.replace("\r\n", "\n").replace("\r", "\n")
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:HASH_TRUNCATE_LENGTH]
    except (OSError, TypeError) as exc:
        logger.warning(
            "Could not retrieve source for %s: %s. Using fallback value.",
            getattr(cls, "__name__", "<unknown>"),
            exc,
        )
        return fallback_value


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    """Structured fingerprint for method source provenance."""

    strategy: str
    source_hash: str | None = None
    normalized_source_hash: str | None = None
    module_file: str | None = None
    module_file_sha256: str | None = None
    git_commit: str | None = None
    git_tree: str | None = None
    git_blob: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "source_hash": self.source_hash,
            "normalized_source_hash": self.normalized_source_hash,
            "module_file": self.module_file,
            "module_file_sha256": self.module_file_sha256,
            "git_commit": self.git_commit,
            "git_tree": self.git_tree,
            "git_blob": self.git_blob,
        }


def compute_source_fingerprint(
    cls: type,
    *,
    fallback_value: str = SOURCE_UNAVAILABLE,
) -> SourceFingerprint:
    """Compute source fingerprint with file and git context when available."""
    source_hash = fallback_value
    normalized_hash: str | None = None

    try:
        source = inspect.getsource(cls)
        source = source.replace("\r\n", "\n").replace("\r", "\n")
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:HASH_TRUNCATE_LENGTH]
        normalized_hash = _normalized_source_hash(source)
    except (OSError, TypeError) as exc:
        logger.warning(
            "Could not retrieve source for %s: %s. Using fallback value.",
            getattr(cls, "__name__", "<unknown>"),
            exc,
        )

    module_file_path = _resolve_module_file(cls)
    module_file = None
    module_file_sha256 = None
    git_commit = None
    git_tree = None
    git_blob = None

    if module_file_path is not None:
        module_file_sha256 = _hash_file(module_file_path)
        git_root = _find_git_root(module_file_path)
        if git_root is not None:
            try:
                rel_path = module_file_path.resolve().relative_to(git_root.resolve())
                module_file = str(rel_path)
                git_blob = _git_blob_hash(git_root, str(rel_path))
            except ValueError:
                module_file = module_file_path.name
            git_commit = _safe_run(["git", "-C", str(git_root), "rev-parse", "HEAD"])
            git_tree = _safe_run(
                ["git", "-C", str(git_root), "rev-parse", "HEAD^{tree}"]
            )
        else:
            module_file = module_file_path.name

    if git_tree or git_blob:
        strategy = "git_tree"
    elif module_file_sha256:
        strategy = "file_sha256"
    elif source_hash != fallback_value:
        strategy = "inspect"
    else:
        strategy = "unavailable"

    return SourceFingerprint(
        strategy=strategy,
        source_hash=None if source_hash == fallback_value else source_hash,
        normalized_source_hash=normalized_hash,
        module_file=module_file,
        module_file_sha256=module_file_sha256,
        git_commit=git_commit,
        git_tree=git_tree,
        git_blob=git_blob,
    )


def _specialization_payload(spec: Specialization) -> dict[str, Any]:
    input_shapes = [
        {
            "name": name,
            "shape": list(shape_spec.shape),
            "dtype": shape_spec.dtype,
        }
        for name, shape_spec in sorted(spec.input_shapes, key=lambda item: item[0])
    ]
    return {
        "method_fqn": spec.method_fqn,
        "static_params_hash": spec.static_params_hash,
        "input_shapes": input_shapes,
        "backend": {
            "platform": spec.backend.platform,
            "device_count": spec.backend.device_count,
            "precision": spec.backend.precision,
            "xla_flags": sorted(spec.backend.xla_flags),
            "device_kinds": list(spec.backend.device_kinds),
            "jax_version": spec.backend.jax_version,
            "jaxlib_version": spec.backend.jaxlib_version,
            "config_fingerprint": spec.backend.config_fingerprint,
        },
        "jit_enabled": spec.jit_enabled,
        "vmap_axis": spec.vmap_axis,
        "donate_argnums": list(spec.donate_argnums),
    }


def _stable_node_id(node: "MethodNode") -> str:
    node_key = node.node_key
    if node_key is None:
        return f"{node.method_fqn}|unknown|{node.instance_index}"
    return f"{node_key.method_fqn}|{node_key.static_params_digest}|{node.instance_index}"


def _to_artifact_id(value: str | ArtifactID) -> ArtifactID:
    if isinstance(value, ArtifactID):
        return value
    if value.startswith(ArtifactID.prefix):
        return ArtifactID.model_validate(value)
    return ArtifactID.from_sha256_hex(value)


# =============================================================================
# Supporting Record Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class SlotBindingRecord:
    """
    Serializable record of a slot binding.

    This is a simplified version of SlotBinding suitable for CAS storage.
    """

    source_method: str
    source_slot: str
    target_method: str
    target_slot: str
    source_node_id: str | None = None
    target_node_id: str | None = None
    conversion_factor: float | None = None
    requires_fx_rate: bool = False

    @classmethod
    def from_binding(
        cls,
        binding: "SlotBinding",
        *,
        node_id_map: Mapping[UUID, str] | None = None,
    ) -> "SlotBindingRecord":
        source_node_id = None
        target_node_id = None
        if binding.source_node_id is not None:
            source_node_id = (
                node_id_map.get(binding.source_node_id)
                if node_id_map is not None
                else str(binding.source_node_id)
            )
        if binding.target_node_id is not None:
            target_node_id = (
                node_id_map.get(binding.target_node_id)
                if node_id_map is not None
                else str(binding.target_node_id)
            )

        return cls(
            source_method=binding.source_method,
            source_slot=binding.source_slot,
            target_method=binding.target_method,
            target_slot=binding.target_slot,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            conversion_factor=binding.conversion_factor,
            requires_fx_rate=binding.requires_fx_rate,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for canonical serialization."""
        return {
            "source_method": self.source_method,
            "source_slot": self.source_slot,
            "target_method": self.target_method,
            "target_slot": self.target_slot,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "conversion_factor": _float_payload(self.conversion_factor),
            "requires_fx_rate": self.requires_fx_rate,
        }


@dataclass(frozen=True, slots=True)
class MethodTiming:
    """Timing record for a single method execution."""

    method_fqn: str
    node_id: str
    duration_seconds: float
    jit_compile_time_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for canonical serialization."""
        result = {
            "method_fqn": self.method_fqn,
            "node_id": self.node_id,
            "duration_seconds": _float_payload(self.duration_seconds),
        }
        if self.jit_compile_time_seconds is not None:
            result["jit_compile_time_seconds"] = _float_payload(
                self.jit_compile_time_seconds
            )
        return result


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Execution hardware context."""

    platform: str
    device_count: int
    precision: str
    jax_version: str
    jaxlib_version: str
    backend: str = "jax"
    library_versions: Mapping[str, str] = field(default_factory=dict)
    solver_name: str = ""
    solver_version: str = ""

    @classmethod
    def current(cls) -> "DeviceInfo":
        """Capture current JAX device information."""
        import jax
        import jaxlib

        backend = jax.default_backend()
        devices = jax.devices()

        return cls(
            platform=str(backend),
            device_count=len(devices),
            precision="float32",
            jax_version=jax.__version__,
            jaxlib_version=jaxlib.__version__,
            backend="jax",
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for canonical serialization."""
        return {
            "platform": self.platform,
            "device_count": self.device_count,
            "precision": self.precision,
            "jax_version": self.jax_version,
            "jaxlib_version": self.jaxlib_version,
            "backend": self.backend,
            "library_versions": dict(sorted(self.library_versions.items())),
            "solver_name": self.solver_name,
            "solver_version": self.solver_version,
        }


@dataclass(frozen=True, slots=True)
class ChainNodeRecord:
    """Stable record of a node in a chain composition."""

    node_id: str
    method_fqn: str
    method_artifact_id: str
    static_params_hash: str | None
    instance_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "method_fqn": self.method_fqn,
            "method_artifact_id": self.method_artifact_id,
            "static_params_hash": self.static_params_hash,
            "instance_index": self.instance_index,
        }


# =============================================================================
# MethodArtifact
# =============================================================================


@dataclass(frozen=True, slots=True)
class MethodArtifact:
    """
    Artifact capturing a method's identity and compilation context.

    Stored in CAS for reproducibility. Enables tracing any result
    back to the exact source code and parameters that produced it.
    """

    # Identity
    fqn: str
    signature_hash: str
    metadata_hash: str

    # Source info
    source_module: str
    source_hash: str
    source_available: bool
    source_fingerprint: SourceFingerprint

    # Compilation context
    specialization: Specialization
    compiled_at: datetime

    # Schema version for forward compatibility
    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    _artifact_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_artifact_id", _artifact_id_from_bytes(self.to_canonical_bytes()))

    @classmethod
    def from_method(
        cls,
        method_class: type,
        specialization: Specialization,
        *,
        compiled_at: datetime | None = None,
    ) -> "MethodArtifact":
        """
        Create artifact from a method class.

        Args:
            method_class: Class implementing FoundryMethod protocol
            specialization: Compilation specialization key
            compiled_at: Override timestamp (for testing)

        Returns:
            Immutable MethodArtifact
        """
        sig: MethodSignature = method_class.signature
        meta: MethodMetadata = method_class.metadata

        signature_hash = _compute_deterministic_hash({
            "name": sig.name,
            "namespace": sig.namespace,
            "version": sig.version,
            "input_slots": sorted([s.name for s in sig.input_slots]),
            "output_slots": sorted([s.name for s in sig.output_slots]),
            "parameters": sorted([p.name for p in sig.parameters]),
        })

        metadata_hash = _compute_deterministic_hash({
            "description": meta.description,
            "tags": sorted(meta.tags) if meta.tags else [],
            "citations": list(meta.citations),
            "equations": dict(meta.equations),
        })

        source_hash = compute_source_hash(method_class)
        source_available = source_hash != SOURCE_UNAVAILABLE
        source_fingerprint = compute_source_fingerprint(method_class)

        return cls(
            fqn=sig.fqn,
            signature_hash=signature_hash,
            metadata_hash=metadata_hash,
            source_module=method_class.__module__,
            source_hash=source_hash,
            source_available=source_available,
            source_fingerprint=source_fingerprint,
            specialization=specialization,
            compiled_at=compiled_at or _utc_now(),
        )

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "fqn": self.fqn,
            "signature_hash": self.signature_hash,
            "metadata_hash": self.metadata_hash,
            "source_module": self.source_module,
            "source_hash": self.source_hash,
            "source_available": self.source_available,
            "source_fingerprint": self.source_fingerprint.to_dict(),
            "specialization": _specialization_payload(self.specialization),
            "specialization_key": self.specialization.cache_key,
        }

    def to_canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes for CAS storage."""
        return to_canonical_bytes(self._identity_payload())

    def to_manifest(self) -> ArtifactManifest:
        """Convert to CAS-storable manifest."""
        content = self.to_canonical_bytes()
        content_hash = hashlib.sha256(content).hexdigest()

        return ArtifactManifest(
            artifact_id=ArtifactID.from_sha256_hex(content_hash),
            kind="foundry.method_artifact",
            media_type="application/json",
            byte_size=len(content),
            created_at=self.compiled_at,
            artifact_schema=SchemaInfo(
                name="polisyos.foundry.method_artifact",
                version=self.SCHEMA_VERSION,
            ),
            producer=ProducerInfo(
                component="foundry.artifacts",
                version=__version__,
            ),
            integrity=IntegrityInfo(sha256=content_hash),
        )

    @property
    def artifact_id(self) -> str:
        """Compute artifact ID from content."""
        return self._artifact_id


# =============================================================================
# ChainArtifact
# =============================================================================


@dataclass(frozen=True, slots=True)
class ChainArtifact:
    """
    Artifact capturing a method chain's composition.

    This is the "recipe" for a simulation — it records which methods
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
        chain: "CompiledMethodChain",
        method_artifacts: Sequence[MethodArtifact] | Mapping[UUID, MethodArtifact],
        *,
        chain_id: UUID | None = None,
        composed_at: datetime | None = None,
    ) -> "ChainArtifact":
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
                raise ValueError(
                    "method_artifacts must match chain execution order length"
                )
            artifact_map = {
                node_id: artifact
                for node_id, artifact in zip(chain.execution_order, method_artifacts)
            }

        node_id_map: dict[UUID, str] = {}
        for node_id in chain.dag.nodes:
            node = chain.get_node(node_id)
            node_id_map[node_id] = _stable_node_id(node)

        method_fqns = tuple(
            chain.signatures[node_id].fqn for node_id in chain.execution_order
        )
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
            SlotBindingRecord.from_binding(b, node_id_map=node_id_map)
            for b in chain.bindings
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
        return hashlib.sha256(content).hexdigest()[:HASH_TRUNCATE_LENGTH]

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
        return hashlib.sha256(content).hexdigest()[:HASH_TRUNCATE_LENGTH]

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
        content_hash = hashlib.sha256(content).hexdigest()

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
                version=__version__,
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


# =============================================================================
# ExecutionEvidence
# =============================================================================


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    """
    Evidence bundle for a method chain execution.

    This is the "receipt" — it proves what inputs produced what outputs,
    how long it took, and with what RNG state (for reproducibility).
    """

    # Identity
    execution_id: UUID
    chain_artifact_id: str

    # Input/Output hashes
    input_state_hash: str
    input_params_hash: str
    output_state_hash: str

    # References to data artifacts
    input_state_artifact_ids: tuple[str, ...] = ()
    output_state_artifact_ids: tuple[str, ...] = ()
    params_artifact_id: str | None = None
    rng_artifact_id: str | None = None

    # Timing
    started_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime = field(default_factory=_utc_now)
    method_timings: tuple[MethodTiming, ...] = ()

    # Reproducibility
    rng_key_used: tuple[int, int] | None = None
    device_info: DeviceInfo = field(default_factory=DeviceInfo.current)

    # Status
    success: bool = True
    error_message: str | None = None

    # Schema version
    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    _artifact_id: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_artifact_id", _artifact_id_from_bytes(self.to_canonical_bytes()))

    @property
    def duration_seconds(self) -> float:
        """Total execution duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()

    @classmethod
    def create(
        cls,
        chain_artifact_id: str,
        input_state_hash: str,
        input_params_hash: str,
        output_state_hash: str,
        started_at: datetime,
        completed_at: datetime,
        method_timings: Sequence[MethodTiming],
        *,
        rng_key_used: tuple[int, int] | None = None,
        device_info: DeviceInfo | None = None,
        execution_id: UUID | None = None,
        input_state_artifact_ids: Sequence[str] | None = None,
        output_state_artifact_ids: Sequence[str] | None = None,
        params_artifact_id: str | None = None,
        rng_artifact_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> "ExecutionEvidence":
        """
        Create execution evidence.

        Args:
            chain_artifact_id: CAS ID of the chain used
            input_state_hash: Hash of input state
            input_params_hash: Hash of dynamic parameters
            output_state_hash: Hash of output state
            started_at: Execution start time
            completed_at: Execution end time
            method_timings: Per-method timing records
            rng_key_used: Optional JAX PRNG key
            device_info: Optional hardware context (auto-detected if None)
            execution_id: Optional override for ID
            input_state_artifact_ids: Optional input state artifact refs
            output_state_artifact_ids: Optional output state artifact refs
            params_artifact_id: Optional params artifact ref
            rng_artifact_id: Optional RNG artifact ref
            success: Whether execution succeeded
            error_message: Error message if failed

        Returns:
            Immutable ExecutionEvidence
        """
        return cls(
            execution_id=execution_id or uuid4(),
            chain_artifact_id=chain_artifact_id,
            input_state_hash=input_state_hash,
            input_params_hash=input_params_hash,
            output_state_hash=output_state_hash,
            input_state_artifact_ids=tuple(input_state_artifact_ids or ()),
            output_state_artifact_ids=tuple(output_state_artifact_ids or ()),
            params_artifact_id=params_artifact_id,
            rng_artifact_id=rng_artifact_id,
            started_at=started_at,
            completed_at=completed_at,
            method_timings=tuple(method_timings),
            rng_key_used=rng_key_used,
            device_info=device_info or DeviceInfo.current(),
            success=success,
            error_message=error_message,
        )

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "execution_id": str(self.execution_id),
            "chain_artifact_id": self.chain_artifact_id,
            "input_state_hash": self.input_state_hash,
            "input_params_hash": self.input_params_hash,
            "output_state_hash": self.output_state_hash,
            "input_state_artifact_ids": list(self.input_state_artifact_ids),
            "output_state_artifact_ids": list(self.output_state_artifact_ids),
            "params_artifact_id": self.params_artifact_id,
            "rng_artifact_id": self.rng_artifact_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": _float_payload(self.duration_seconds),
            "method_timings": [t.to_dict() for t in self.method_timings],
            "rng_key_used": list(self.rng_key_used) if self.rng_key_used else None,
            "device_info": self.device_info.to_dict(),
            "success": self.success,
            "error_message": self.error_message,
        }

    def to_canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes for CAS storage."""
        return to_canonical_bytes(self._identity_payload())

    def to_manifest(self) -> ArtifactManifest:
        """Convert to CAS-storable manifest."""
        content = self.to_canonical_bytes()
        content_hash = hashlib.sha256(content).hexdigest()

        inputs: list[InputRef] = [
            InputRef(artifact_id=_to_artifact_id(self.chain_artifact_id), role="chain")
        ]
        for aid in self.input_state_artifact_ids:
            inputs.append(InputRef(artifact_id=_to_artifact_id(aid), role="input_state"))
        for aid in self.output_state_artifact_ids:
            inputs.append(
                InputRef(artifact_id=_to_artifact_id(aid), role="output_state")
            )
        if self.params_artifact_id:
            inputs.append(
                InputRef(artifact_id=_to_artifact_id(self.params_artifact_id), role="params")
            )
        if self.rng_artifact_id:
            inputs.append(
                InputRef(artifact_id=_to_artifact_id(self.rng_artifact_id), role="rng")
            )

        return ArtifactManifest(
            artifact_id=ArtifactID.from_sha256_hex(content_hash),
            kind="foundry.execution_evidence",
            media_type="application/json",
            byte_size=len(content),
            created_at=self.completed_at,
            artifact_schema=SchemaInfo(
                name="polisyos.foundry.execution_evidence",
                version=self.SCHEMA_VERSION,
            ),
            producer=ProducerInfo(
                component="foundry.runtime",
                version=__version__,
            ),
            inputs=inputs,
            integrity=IntegrityInfo(sha256=content_hash),
        )

    @property
    def artifact_id(self) -> str:
        """Compute artifact ID from content."""
        return self._artifact_id


# =============================================================================
# CAS Storage Functions
# =============================================================================


def store_method_artifact(
    cas: "FileSystemCAS",
    artifact: MethodArtifact,
) -> ArtifactRef:
    """
    Store a MethodArtifact in CAS.

    Args:
        cas: FileSystem CAS instance
        artifact: MethodArtifact to store

    Returns:
        ArtifactRef pointing to stored artifact
    """
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
    """
    Store a ChainArtifact in CAS.

    Args:
        cas: FileSystem CAS instance
        artifact: ChainArtifact to store

    Returns:
        ArtifactRef pointing to stored artifact
    """
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
    """
    Store ExecutionEvidence in CAS.

    Args:
        cas: FileSystem CAS instance
        evidence: ExecutionEvidence to store

    Returns:
        ArtifactRef pointing to stored artifact
    """
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
