"""Capture compact execution-environment fingerprints for reproducible Foundry runs."""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as package_version
from typing import TYPE_CHECKING

from polisyos.common.logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from polisyos.core.artifacts.environment import EnvironmentManifest

from polisyos.core.canon import truncated_hash
from polisyos.core.observability.determinism import (
    DeterminismTier,
)
from polisyos.core.observability.determinism import (
    get_determinism_tier as _get_determinism_tier,
)

_FINGERPRINT_PROBE_FAILURES = (
    AttributeError,
    ImportError,
    ModuleNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

_PACKAGE_METADATA_FAILURES = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

_PACKAGE_VERSION_FAILURES = (PackageNotFoundError, *_PACKAGE_METADATA_FAILURES)


@dataclass(frozen=True, slots=True)
class EnvironmentFingerprint:
    """
    Lightweight environment capture for agent policy reproducibility.

    Captures only the fields that materially affect neural network
    computation results. Designed to be:
    - Fast to capture (<100ms)
    - Compact to serialize (<1KB JSON)
    - Sufficient for compatibility checking
    """

    python_version: str
    platform_system: str
    platform_machine: str

    jax_version: str
    jaxlib_version: str
    xla_flags: str
    x64_enabled: bool
    deterministic_ops: bool

    cpu_count: int
    cuda_version: str | None
    cudnn_version: str | None
    device_name: str | None

    determinism_tier: DeterminismTier
    random_seed: int

    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def capture(cls, tier: DeterminismTier, seed: int) -> "EnvironmentFingerprint":
        """
        Capture current environment for artifact storage.

        Performance target: < 100ms (no subprocess calls for fast path).
        """
        import jax

        xla_flags = os.environ.get("XLA_FLAGS", "")

        x64_enabled = getattr(jax.config, "x64_enabled", False)
        if callable(x64_enabled):
            x64_enabled = x64_enabled()
        x64_enabled = bool(x64_enabled)

        deterministic_ops = "--xla_gpu_deterministic_ops=true" in xla_flags

        devices = jax.devices()
        if devices:
            device = devices[0]
            device_name = f"{device.platform}:{device.device_kind}"
        else:
            device_name = "cpu"

        return cls(
            python_version=platform.python_version(),
            platform_system=platform.system(),
            platform_machine=platform.machine(),
            jax_version=jax.__version__,
            jaxlib_version=_get_jaxlib_version(),
            xla_flags=xla_flags,
            x64_enabled=x64_enabled,
            deterministic_ops=deterministic_ops,
            cpu_count=os.cpu_count() or 1,
            cuda_version=_get_cuda_version_fast(),
            cudnn_version=_get_cudnn_version(),
            device_name=device_name,
            determinism_tier=tier,
            random_seed=seed,
        )

    @classmethod
    def from_environment_manifest(
        cls,
        manifest: "EnvironmentManifest",
        tier: DeterminismTier,
        seed: int,
    ) -> "EnvironmentFingerprint":
        """Create fingerprint from existing full EnvironmentManifest."""
        return cls(
            python_version=manifest.python.version,
            platform_system=manifest.os.system,
            platform_machine=manifest.cpu.architecture,
            jax_version=manifest.jax.jax_version or "unknown",
            jaxlib_version=manifest.jax.jaxlib_version or "unknown",
            xla_flags="|".join(manifest.jax.xla_flags) if manifest.jax.xla_flags else "",
            x64_enabled=manifest.jax.x64_enabled,
            deterministic_ops=manifest.jax.deterministic_ops_enabled,
            cpu_count=manifest.cpu.core_count,
            cuda_version=manifest.gpu.cuda_version,
            cudnn_version=manifest.gpu.cudnn_version,
            device_name=manifest.gpu.model_name,
            determinism_tier=tier,
            random_seed=seed,
        )

    def compute_hash(self) -> str:
        """
        Compute 16-char hash for quick equality checks and artifact naming.

        Only includes fields that affect computation, not metadata.
        """
        critical_fields = "|".join(
            [
                self.python_version,
                self.platform_machine,
                self.jax_version,
                self.jaxlib_version,
                str(self.x64_enabled),
                str(self.deterministic_ops),
                self.cuda_version or "no-cuda",
                self.device_name or "no-device",
                self.determinism_tier.value,
                str(self.random_seed),
            ]
        )
        return truncated_hash(critical_fields, length=16)

    def compatibility_score(self, other: "EnvironmentFingerprint") -> float:
        """
        Calculate compatibility score with another environment.

        Returns:
            1.0: Identical environments (bit-exact reproducibility expected)
            0.8-0.99: Minor differences (likely reproducible with warnings)
            0.5-0.79: Moderate differences (results may vary)
            0.0-0.49: Critical differences (reproducibility not guaranteed)
        """
        if self.compute_hash() == other.compute_hash():
            return 1.0

        score = 1.0

        if self.platform_machine != other.platform_machine:
            return 0.0

        self_jax_major = self.jax_version.split(".")[0:2]
        other_jax_major = other.jax_version.split(".")[0:2]
        if self_jax_major != other_jax_major:
            score *= 0.3
        elif self.jax_version != other.jax_version:
            score *= 0.9

        if self.cuda_version != other.cuda_version:
            if self.cuda_version is None or other.cuda_version is None:
                score *= 0.5
            else:
                score *= 0.7

        if self.determinism_tier != other.determinism_tier:
            score *= 0.8

        if self.x64_enabled != other.x64_enabled:
            score *= 0.7

        if self.random_seed != other.random_seed:
            score *= 0.95

        return max(0.0, min(1.0, score))

    def validate_for_tier(self) -> list[str]:
        """Validate that environment matches claimed determinism tier."""
        warnings: list[str] = []

        if self.determinism_tier == DeterminismTier.STRICT_CPU:
            if self.device_name and "gpu" in self.device_name.lower():
                warnings.append(
                    "STRICT_CPU tier claimed but running on GPU device: "
                    f"{self.device_name}"
                )
            if not self.deterministic_ops:
                warnings.append(
                    "STRICT_CPU tier requires XLA_FLAGS=--xla_gpu_deterministic_ops=true"
                )

        elif self.determinism_tier == DeterminismTier.BEST_EFFORT_GPU:
            if not self.cuda_version:
                warnings.append("BEST_EFFORT_GPU tier claimed but no CUDA detected")

        return warnings


def _get_jaxlib_version() -> str:
    """Get jaxlib version without importing heavy modules."""
    try:
        return package_version("jaxlib")
    except _PACKAGE_VERSION_FAILURES:
        return "unknown"


def _get_cuda_version_fast() -> str | None:
    """
    Fast CUDA version detection without subprocess.

    Checks environment variables and jaxlib bindings first.
    Falls back to None rather than slow subprocess calls.
    """
    cuda_ver = os.environ.get("CUDA_VERSION")
    if cuda_ver:
        if "." in cuda_ver:
            major, minor, *_ = cuda_ver.split(".")
            return f"{major}.{minor}"
        return cuda_ver

    try:
        import jax

        for device in jax.devices():
            if device.platform == "gpu":
                cuda_home = os.environ.get("CUDA_HOME", "")
                return (
                    cuda_home.split("/")[-1].replace("cuda-", "")
                    if cuda_home
                    else "detected"
                )
    except _FINGERPRINT_PROBE_FAILURES as exc:
        logger.debug("Ignored exception: %s", exc)

    return None


def _get_cudnn_version() -> str | None:
    """Get cuDNN version if available."""
    try:
        jaxlib_ver = package_version("jaxlib")
        if "cuda" in jaxlib_ver:
            return "bundled"
    except _PACKAGE_VERSION_FAILURES as exc:
        logger.debug("Ignored exception: %s", exc)
    return None


def get_determinism_tier() -> DeterminismTier | None:
    """Compatibility shim for determinism tier lookup."""
    return _get_determinism_tier()


def configure_determinism(tier: DeterminismTier) -> dict[str, str]:
    """
    Configure JAX/XLA for the specified determinism tier.

    Returns dict of environment variables that should be set.

    WARNING: Must be called BEFORE importing JAX for flags to take effect.
    """
    env_vars: dict[str, str] = {}

    if tier == DeterminismTier.STRICT_CPU:
        env_vars["JAX_PLATFORMS"] = "cpu"
        env_vars["XLA_FLAGS"] = "--xla_gpu_deterministic_ops=true"
        env_vars["XLA_FLAGS"] += " --xla_cpu_multi_thread_eigen=false"
        env_vars["OMP_NUM_THREADS"] = "1"
        env_vars["MKL_NUM_THREADS"] = "1"

    elif tier == DeterminismTier.BEST_EFFORT_GPU:
        env_vars["XLA_FLAGS"] = "--xla_gpu_deterministic_ops=true"
        env_vars["TF_CUDNN_DETERMINISTIC"] = "1"

    return env_vars
