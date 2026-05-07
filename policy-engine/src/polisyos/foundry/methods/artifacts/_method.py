"""
MethodArtifact -- immutable artifact capturing a method's identity and
compilation context for CAS-backed provenance (Law J).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    IntegrityInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.canon import (
    content_hash as compute_content_hash,
)
from polisyos.core.canon import (
    to_canonical_bytes,
)

from ._fingerprint import (
    ARTIFACTS_VERSION,
    SOURCE_UNAVAILABLE,
    SourceFingerprint,
    _artifact_id_from_bytes,
    _compute_deterministic_hash,
    _utc_now,
    compute_source_fingerprint,
    compute_source_hash,
)
from ..specialization import Specialization

if TYPE_CHECKING:
    from ..base import MethodMetadata, MethodSignature

__all__ = [
    "MethodArtifact",
]

logger = get_logger(__name__)


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
    ) -> MethodArtifact:
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

        signature_hash = _compute_deterministic_hash(
            {
                "name": sig.name,
                "namespace": sig.namespace,
                "version": sig.version,
                "input_slots": sorted([s.name for s in sig.input_slots]),
                "output_slots": sorted([s.name for s in sig.output_slots]),
                "parameters": sorted([p.name for p in sig.parameters]),
            }
        )

        metadata_hash = _compute_deterministic_hash(
            {
                "description": meta.description,
                "tags": sorted(meta.tags) if meta.tags else [],
                "citations": list(meta.citations),
                "equations": dict(meta.equations),
            }
        )

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
        content_hash = compute_content_hash(content)

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
                version=ARTIFACTS_VERSION,
            ),
            integrity=IntegrityInfo(sha256=content_hash),
        )

    @property
    def artifact_id(self) -> str:
        """Compute artifact ID from content."""
        return self._artifact_id
