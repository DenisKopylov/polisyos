"""
ExecutionEvidence -- immutable evidence bundle for a method chain execution,
serving as the "receipt" for CAS-backed provenance (Law J).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Sequence
from uuid import UUID, uuid4

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
)

from ._artifacts_fingerprint import (
    ARTIFACTS_VERSION,
    _artifact_id_from_bytes,
    _float_payload,
    _utc_now,
)
from ._artifacts_records import DeviceInfo, MethodTiming

__all__ = [
    "ExecutionEvidence",
]

logger = get_logger(__name__)


def _to_artifact_id(value: str | ArtifactID) -> ArtifactID:
    if isinstance(value, ArtifactID):
        return value
    if value.startswith(ArtifactID.prefix):
        return ArtifactID.model_validate(value)
    return ArtifactID.from_sha256_hex(value)


@dataclass(frozen=True, slots=True)
class ExecutionEvidence:
    """
    Evidence bundle for a method chain execution.

    This is the "receipt" -- it proves what inputs produced what outputs,
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
        content_hash = compute_content_hash(content)

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
                version=ARTIFACTS_VERSION,
            ),
            inputs=inputs,
            integrity=IntegrityInfo(sha256=content_hash),
        )

    @property
    def artifact_id(self) -> str:
        """Compute artifact ID from content."""
        return self._artifact_id
