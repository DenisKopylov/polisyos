"""Low-level helper utilities shared across environment sub-modules."""

from __future__ import annotations

import os
import subprocess
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.core.canon import streaming_hash

if TYPE_CHECKING:
    from ._env_models import CPUInfo, GPUInfo, JAXInfo, RiskLevel, SystemLibraryInfo

__all__ = [
    "DEFAULT_COMMAND_TIMEOUT",
    "MAX_LIBRARY_BYTES",
    "SYSTEM_LIBRARY_NAMES",
    "estimate_precision_loss",
    "fingerprint_system_libraries",
    "format_xla_flags",
    "hash_file",
    "parse_xla_flags",
    "risk_order",
    "safe_package_version",
    "safe_run",
    "short_hash",
]

DEFAULT_COMMAND_TIMEOUT = 1.5
MAX_LIBRARY_BYTES = 64 * 1024 * 1024
SYSTEM_LIBRARY_NAMES = (
    "libcuda.so",
    "libcudnn.so",
    "libcublas.so",
    "libcublasLt.so",
    "libcudart.so",
)


def _safe_run(cmd: list[str], timeout: float = DEFAULT_COMMAND_TIMEOUT) -> str | None:
    """
    Safely execute a system command with timeout.

    Returns None if command fails or is not available.
    Never raises exceptions.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _safe_package_version(package: str) -> str | None:
    """Safely get installed package version."""
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def _hash_file(path: Path, *, max_bytes: int | None = None) -> str | None:
    """Compute SHA256 hash of a file."""
    if not path.exists():
        return None
    try:
        if max_bytes is not None:
            size = path.stat().st_size
            if size > max_bytes:
                return None
        with open(path, "rb") as f:
            return streaming_hash(iter(lambda: f.read(8192), b""))
    except OSError:
        return None


def _short_hash(value: str | None) -> str | None:
    if not value:
        return value
    return value[:24] + "..." if len(value) > 24 else value


def _risk_order(risk: RiskLevel) -> int:
    from ._env_models import RiskLevel

    order = {
        RiskLevel.CRITICAL: 0,
        RiskLevel.HIGH: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.LOW: 3,
        RiskLevel.INFO: 4,
    }
    return order[risk]


def _format_xla_flags(flags: dict[str, str]) -> str:
    if not flags:
        return ""
    parts = [f"{key}={value}" for key, value in sorted(flags.items())]
    return " ".join(parts)


def _parse_xla_flags(flags_str: str) -> dict[str, str]:
    """Parse XLA_FLAGS environment variable into dict."""
    result: dict[str, str] = {}
    for flag in flags_str.split():
        if "=" in flag:
            key, value = flag.split("=", 1)
            result[key.lstrip("-")] = value
        elif flag.startswith("--"):
            result[flag.lstrip("-")] = "true"
    return result


def _estimate_precision_loss(
    cpu: CPUInfo,
    gpu: GPUInfo,
    jax_info: JAXInfo,
) -> str | None:
    arch = cpu.architecture.lower()
    if arch in {"arm64", "aarch64"}:
        return "arch_fma_variance"
    if jax_info.jax_version and gpu.available and not jax_info.deterministic_ops_enabled:
        return "gpu_nondeterministic"
    return None


def _fingerprint_system_libraries(libs: dict[str, SystemLibraryInfo]) -> str:
    from polisyos.core.canon import truncated_hash

    if not libs:
        return ""
    parts = []
    for name in sorted(libs):
        info = libs[name]
        if info.sha256:
            parts.append(f"{name}:{info.sha256}")
        else:
            parts.append(f"{name}:nohash")
    return truncated_hash("|".join(parts), length=16)


safe_run = _safe_run
safe_package_version = _safe_package_version
hash_file = _hash_file
short_hash = _short_hash
risk_order = _risk_order
format_xla_flags = _format_xla_flags
parse_xla_flags = _parse_xla_flags
estimate_precision_loss = _estimate_precision_loss
fingerprint_system_libraries = _fingerprint_system_libraries
