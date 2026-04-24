"""
Supporting record types for method execution artifacts.

Provides frozen dataclasses used by MethodArtifact, ChainArtifact,
and ExecutionEvidence for slot bindings, timing, device info, and
chain node tracking.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ._artifacts_fingerprint import _float_payload

if TYPE_CHECKING:
    from uuid import UUID

    from .linker import SlotBinding

__all__ = [
    "ChainNodeRecord",
    "DeviceInfo",
    "MethodTiming",
    "SlotBindingRecord",
]


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
        binding: SlotBinding,
        *,
        node_id_map: Mapping[UUID, str] | None = None,
    ) -> SlotBindingRecord:
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
            result["jit_compile_time_seconds"] = _float_payload(self.jit_compile_time_seconds)
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
    def current(cls) -> DeviceInfo:
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
