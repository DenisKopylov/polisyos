"""Pydantic / dataclass models for environment manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from polisyos.core.canon import truncated_hash

from .manifest import ArtifactRef

__all__ = [
    "RiskLevel",
    "CPUInfo",
    "GPUInfo",
    "OSInfo",
    "PythonInfo",
    "JAXInfo",
    "GitInfo",
    "DependencyInfo",
    "ContainerInfo",
    "TEEInfo",
    "SystemLibraryInfo",
    "EnvironmentDiff",
    "EnvironmentManifest",
    "EnvironmentManifestRef",
]


class RiskLevel(str, Enum):
    """Risk level for environment differences."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class CPUInfo(BaseModel):
    """CPU hardware information."""

    model_config = ConfigDict(extra="ignore")

    architecture: str = Field(..., description="CPU architecture (x86_64, arm64)")
    model_name: str = Field(..., description="CPU model name")
    core_count: int = Field(..., ge=1, description="Number of physical cores")
    thread_count: int = Field(..., ge=1, description="Number of logical threads")

    has_avx: bool = Field(default=False, description="AVX support")
    has_avx2: bool = Field(default=False, description="AVX2 support")
    has_avx512: bool = Field(default=False, description="AVX-512 support")
    has_amx: bool = Field(default=False, description="AMX (Advanced Matrix Extensions)")
    has_neon: bool = Field(default=False, description="ARM NEON support")

    @property
    def fingerprint(self) -> str:
        """Generate fingerprint for CPU capabilities."""
        flags = (
            f"{self.architecture}:{self.has_avx}:{self.has_avx2}:"
            f"{self.has_avx512}:{self.has_amx}:{self.has_neon}"
        )
        return truncated_hash(flags, length=16)

    @computed_field(alias="fingerprint", return_type=str)
    def fingerprint_field(self) -> str:
        """Expose the fingerprint through Pydantic serialization."""
        return self.fingerprint


class GPUInfo(BaseModel):
    """GPU hardware information."""

    model_config = ConfigDict(extra="forbid")

    available: bool = Field(default=False, description="Whether GPU is available")
    device_count: int = Field(default=0, ge=0, description="Number of GPU devices")
    model_name: str | None = Field(default=None, description="GPU model name")
    device_names: list[str] = Field(default_factory=list, description="GPU device names")
    device_uuids: list[str] = Field(default_factory=list, description="GPU device UUIDs")
    memory_gb: float | None = Field(default=None, ge=0, description="GPU memory in GB")

    cuda_version: str | None = Field(default=None, description="CUDA toolkit version")
    cuda_driver_version: str | None = Field(default=None, description="CUDA driver version")
    cudnn_version: str | None = Field(default=None, description="cuDNN version")
    topology: str | None = Field(default=None, description="GPU topology summary")

    metal_available: bool = Field(default=False, description="Metal API available")
    metal_device_name: str | None = Field(default=None, description="Metal device name")


class OSInfo(BaseModel):
    """Operating system information."""

    model_config = ConfigDict(extra="forbid")

    system: str = Field(..., description="OS name (Linux, Darwin, Windows)")
    release: str = Field(..., description="OS release version")
    version: str = Field(..., description="OS version string")
    kernel_version: str | None = Field(default=None, description="Kernel version")
    libc_version: str | None = Field(default=None, description="libc version (glibc)")


class PythonInfo(BaseModel):
    """Python runtime information."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(..., description="Python version (e.g., 3.11.5)")
    implementation: str = Field(..., description="Python implementation (CPython)")
    compiler: str = Field(..., description="Compiler used to build Python")
    executable_hash: str | None = Field(default=None, description="Hash of Python executable")


class JAXInfo(BaseModel):
    """JAX/XLA runtime information."""

    model_config = ConfigDict(extra="forbid")

    jax_version: str | None = Field(default=None, description="JAX version")
    jaxlib_version: str | None = Field(default=None, description="jaxlib version")
    xla_version: str | None = Field(default=None, description="XLA version hash")

    default_backend: str | None = Field(default=None, description="Default JAX backend")
    available_backends: list[str] = Field(default_factory=list, description="Available backends")
    device_count: int = Field(default=0, ge=0, description="Number of JAX devices")

    xla_flags: dict[str, str] = Field(default_factory=dict, description="Active XLA flags")

    deterministic_ops_enabled: bool = Field(default=False, description="XLA deterministic ops")
    x64_enabled: bool = Field(default=False, description="64-bit precision enabled")


class GitInfo(BaseModel):
    """Git repository information."""

    model_config = ConfigDict(extra="forbid")

    commit_sha: str = Field(..., min_length=7, max_length=40, description="Git commit SHA")
    commit_short: str = Field(..., min_length=7, max_length=8, description="Short commit SHA")
    branch: str | None = Field(default=None, description="Current branch name")
    dirty: bool = Field(default=False, description="Working directory has uncommitted changes")
    tags: list[str] = Field(default_factory=list, description="Tags pointing to commit")


class DependencyInfo(BaseModel):
    """Dependency lockfile information."""

    model_config = ConfigDict(extra="forbid")

    lockfile_path: str = Field(..., description="Path to lockfile (uv.lock)")
    lockfile_hash: str = Field(..., description="SHA256 hash of lockfile content")
    lockfile_modified: datetime | None = Field(default=None, description="Last modification time")

    key_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Versions of critical packages (jax, equinox, etc.)",
    )


class ContainerInfo(BaseModel):
    """Container/Docker information."""

    model_config = ConfigDict(extra="forbid")

    in_container: bool = Field(default=False, description="Running inside container")
    docker_image_sha: str | None = Field(default=None, description="Docker image SHA256")
    docker_image_tag: str | None = Field(default=None, description="Docker image tag")
    container_runtime: str | None = Field(
        default=None,
        description="Container runtime (docker, podman)",
    )


class TEEInfo(BaseModel):
    """TEE attestation metadata captured during execution."""

    model_config = ConfigDict(extra="forbid")

    platform: str | None = None
    attestation_status: str = "not_applicable"
    report_hash: str | None = None
    measurement: str | None = None
    tcb_version: str | None = None
    verified_at: str | None = None


class SystemLibraryInfo(BaseModel):
    """System library fingerprint."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(..., description="Library filename (basename only)")
    sha256: str | None = Field(default=None, description="SHA256 hash of library content")
    size_bytes: int | None = Field(default=None, ge=0, description="Size in bytes")
    modified_at: datetime | None = Field(default=None, description="Last modification time")


class EnvironmentDiff(BaseModel):
    """Difference between two environment manifests."""

    model_config = ConfigDict(extra="forbid")

    field_path: str = Field(..., description="Dot-notation path to differing field")
    field_name: str = Field(..., description="Human-readable field name")
    value_a: Any = Field(..., description="Value in first manifest")
    value_b: Any = Field(..., description="Value in second manifest")
    risk_level: RiskLevel = Field(..., description="Risk level of this difference")
    explanation: str = Field(..., description="Human-readable explanation")


class EnvironmentManifest(BaseModel):
    """
    Complete environment fingerprint for reproducible simulations.

    Captures all factors that can affect simulation results:
    - Hardware (CPU architecture, instruction sets, GPU)
    - Software (OS, Python, drivers)
    - Runtimes (JAX, XLA, CUDA)
    - Code/Config (Git commit, lockfile hash, Docker image)
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of capture",
    )

    cpu: CPUInfo
    gpu: GPUInfo

    os: OSInfo
    python: PythonInfo

    jax: JAXInfo

    git: GitInfo | None = None
    dependencies: DependencyInfo | None = None
    container: ContainerInfo | None = None
    tee: TEEInfo | None = None
    system_libraries: dict[str, SystemLibraryInfo] = Field(
        default_factory=dict,
        description="Hashes of key system libraries",
    )
    expected_precision_loss: str | None = Field(
        default=None,
        description="Hint for cross-platform numeric drift",
    )

    custom_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom metadata",
    )

    @property
    def fingerprint(self) -> str:
        """
        Generate a compact fingerprint for quick equality checks.
        Includes only fields that affect reproducibility.
        """
        from ._env_utils import fingerprint_system_libraries, format_xla_flags

        lib_fingerprint = fingerprint_system_libraries(self.system_libraries)
        xla_flags = format_xla_flags(self.jax.xla_flags)
        critical_fields = [
            self.cpu.fingerprint,
            self.gpu.cuda_version or "no-cuda",
            self.gpu.cuda_driver_version or "no-cuda-driver",
            self.gpu.cudnn_version or "no-cudnn",
            self.python.version,
            self.jax.jax_version or "no-jax",
            self.jax.jaxlib_version or "no-jaxlib",
            self.jax.xla_version or "no-xla",
            xla_flags or "no-xla-flags",
            str(self.jax.deterministic_ops_enabled),
            str(self.jax.x64_enabled),
            self.dependencies.lockfile_hash if self.dependencies else "no-lock",
            self.git.commit_sha if self.git else "no-git",
            lib_fingerprint or "no-system-libs",
        ]
        combined = "|".join(critical_fields)
        return truncated_hash(combined, length=32)

    @computed_field(alias="fingerprint", return_type=str)
    def fingerprint_field(self) -> str:
        """Expose the manifest fingerprint through Pydantic serialization."""
        return self.fingerprint

    def compatibility_score(self, other: "EnvironmentManifest") -> float:
        """
        Calculate compatibility score between two environments.

        Returns:
            float: 1.0 = identical, 0.0 = completely incompatible
        """
        from ._env_comparison import compare_environments
        from ._env_utils import risk_order

        if self.fingerprint == other.fingerprint:
            return 1.0

        diffs = compare_environments(self, other)
        if not diffs:
            return 1.0

        risk_weights = {
            RiskLevel.CRITICAL: 0.0,
            RiskLevel.HIGH: 0.3,
            RiskLevel.MEDIUM: 0.7,
            RiskLevel.LOW: 0.9,
            RiskLevel.INFO: 1.0,
        }
        worst_risk = min(diffs, key=lambda diff: risk_order(diff.risk_level)).risk_level
        return risk_weights[worst_risk]


class EnvironmentManifestRef(ArtifactRef):
    """Typed reference to EnvironmentManifest artifact."""

    kind: str = "foundry.environment_manifest"
    media_type: str = "application/json"
