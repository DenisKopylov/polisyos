"""Explicit process bootstrap helpers for env defaults, validation, and logging.

This module is intentionally side-effect free on import. Entry points that want
to mutate process environment variables or initialize logging must call
`apply_process_bootstrap()` explicitly.
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

from polisyos.common.env_parsing import parse_bool, parse_int

try:  # pragma: no cover - optional dependency
    load_dotenv: Any | None
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None

try:  # pragma: no cover - optional dependency
    logger: Any | None
    from loguru import logger
except ModuleNotFoundError:  # pragma: no cover
    logger = None

_LOGGING_BOOTSTRAPPED = False
_LOGGING_LOCK = threading.Lock()


@dataclass(frozen=True)
class EnvVarSpec:
    """Document one supported environment variable."""

    name: str
    owner: str
    default: str
    description: str


@dataclass(frozen=True)
class ProcessBootstrapConfig:
    """Resolved bootstrap settings derived from env and host topology."""

    total_cores: int
    reserved_cores: int
    allowed_cores: int
    log_level: str
    duckdb_memory_limit: str
    duckdb_threads: int
    multi_tenant_enabled: bool
    cell_registry_path: str
    default_cell_tier: str
    jax_platform_name: str
    jax_platforms: str
    jax_enable_x64: str
    jax_disable_most_optimizations: str
    jax_check_tracer_leaks: str
    xla_python_client_preallocate: str
    xla_flags: str
    scientist_torch_device: str
    scientist_torch_num_threads: str
    scientist_torch_num_interop_threads: str
    omp_num_threads: str
    openblas_num_threads: str
    veclib_maximum_threads: str
    numexpr_num_threads: str


_ENV_REGISTRY: tuple[EnvVarSpec, ...] = (
    EnvVarSpec(
        name="LOG_LEVEL",
        owner="common",
        default="DEBUG",
        description="Runtime log verbosity for console output.",
    ),
    EnvVarSpec(
        name="DUCKDB_MEMORY_LIMIT",
        owner="common",
        default="4GB",
        description="Default DuckDB memory limit used by local workloads.",
    ),
    EnvVarSpec(
        name="DUCKDB_THREADS",
        owner="common",
        default="<allowed_cores>",
        description="Default DuckDB worker-thread count.",
    ),
    EnvVarSpec(
        name="POLISYOS_MULTI_TENANT_ENABLED",
        owner="runtime",
        default="false",
        description="Enable multi-tenant runtime behaviors by default.",
    ),
    EnvVarSpec(
        name="POLISYOS_CELL_REGISTRY_PATH",
        owner="runtime",
        default="",
        description="Filesystem path to the tenant/cell routing registry.",
    ),
    EnvVarSpec(
        name="POLISYOS_DEFAULT_CELL_TIER",
        owner="runtime",
        default="shared",
        description="Fallback cell tier used when no tenant-specific route exists.",
    ),
    EnvVarSpec(
        name="JAX_PLATFORM_NAME",
        owner="common",
        default="cpu",
        description="Default JAX platform selection for safe local execution.",
    ),
    EnvVarSpec(
        name="JAX_PLATFORMS",
        owner="common",
        default="cpu",
        description="Preferred JAX platform order; kept aligned with JAX_PLATFORM_NAME.",
    ),
    EnvVarSpec(
        name="JAX_ENABLE_X64",
        owner="common",
        default="false",
        description="Disable x64 by default for predictable resource usage.",
    ),
    EnvVarSpec(
        name="JAX_DISABLE_MOST_OPTIMIZATIONS",
        owner="common",
        default="true",
        description="Favor deterministic/local-safe JAX execution posture.",
    ),
    EnvVarSpec(
        name="JAX_CHECK_TRACER_LEAKS",
        owner="common",
        default="false",
        description="Keep tracer-leak checks disabled unless explicitly debugging JAX internals.",
    ),
    EnvVarSpec(
        name="XLA_PYTHON_CLIENT_PREALLOCATE",
        owner="common",
        default="false",
        description="Disable eager accelerator memory reservation by default.",
    ),
    EnvVarSpec(
        name="XLA_FLAGS",
        owner="common",
        default="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=<allowed_cores>",
        description="CPU threading posture for XLA-backed workloads.",
    ),
    EnvVarSpec(
        name="SCIENTIST_TORCH_DEVICE",
        owner="scientist",
        default="cpu",
        description="Default Torch device for Scientist compute paths.",
    ),
    EnvVarSpec(
        name="SCIENTIST_TORCH_NUM_THREADS",
        owner="scientist",
        default="<allowed_cores>",
        description="Default Torch thread pool size for intra-op work.",
    ),
    EnvVarSpec(
        name="SCIENTIST_TORCH_NUM_INTEROP_THREADS",
        owner="scientist",
        default="1",
        description="Default Torch inter-op parallelism for local hosts.",
    ),
    EnvVarSpec(
        name="OMP_NUM_THREADS",
        owner="scientist",
        default="<allowed_cores>",
        description="Default OpenMP thread count for numerical kernels.",
    ),
    EnvVarSpec(
        name="OPENBLAS_NUM_THREADS",
        owner="scientist",
        default="<allowed_cores>",
        description="Default OpenBLAS thread count.",
    ),
    EnvVarSpec(
        name="VECLIB_MAXIMUM_THREADS",
        owner="scientist",
        default="<allowed_cores>",
        description="Default Accelerate/vecLib thread count on macOS.",
    ),
    EnvVarSpec(
        name="NUMEXPR_NUM_THREADS",
        owner="scientist",
        default="<allowed_cores>",
        description="Default NumExpr worker-thread count.",
    ),
)


def get_env_registry() -> tuple[EnvVarSpec, ...]:
    """Return the supported env-var registry used by explicit bootstrap."""
    return _ENV_REGISTRY


def build_process_bootstrap_config(
    *,
    env: Mapping[str, str] | None = None,
    total_cores: int | None = None,
) -> ProcessBootstrapConfig:
    """Resolve bootstrap defaults from environment and host CPU topology."""
    source = env or os.environ
    cores = max(1, total_cores or multiprocessing.cpu_count())
    reserved_cores = max(1, int(cores * 0.20))
    allowed_cores = max(1, cores - reserved_cores)
    xla_flags = source.get("XLA_FLAGS", "").strip() or (
        f"--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads={allowed_cores}"
    )
    return ProcessBootstrapConfig(
        total_cores=cores,
        reserved_cores=reserved_cores,
        allowed_cores=allowed_cores,
        log_level=(source.get("LOG_LEVEL", "DEBUG").strip() or "DEBUG"),
        duckdb_memory_limit=(source.get("DUCKDB_MEMORY_LIMIT", "4GB").strip() or "4GB"),
        duckdb_threads=max(1, parse_int(source.get("DUCKDB_THREADS"), allowed_cores)),
        multi_tenant_enabled=parse_bool(source.get("POLISYOS_MULTI_TENANT_ENABLED"), False),
        cell_registry_path=source.get("POLISYOS_CELL_REGISTRY_PATH", "").strip(),
        default_cell_tier=(source.get("POLISYOS_DEFAULT_CELL_TIER", "shared").strip() or "shared"),
        jax_platform_name=(source.get("JAX_PLATFORM_NAME", "cpu").strip() or "cpu"),
        jax_platforms=(source.get("JAX_PLATFORMS", "cpu").strip() or "cpu"),
        jax_enable_x64=(source.get("JAX_ENABLE_X64", "false").strip() or "false"),
        jax_disable_most_optimizations=(
            source.get("JAX_DISABLE_MOST_OPTIMIZATIONS", "true").strip() or "true"
        ),
        jax_check_tracer_leaks=(source.get("JAX_CHECK_TRACER_LEAKS", "false").strip() or "false"),
        xla_python_client_preallocate=(
            source.get("XLA_PYTHON_CLIENT_PREALLOCATE", "false").strip() or "false"
        ),
        xla_flags=xla_flags,
        scientist_torch_device=(source.get("SCIENTIST_TORCH_DEVICE", "cpu").strip() or "cpu"),
        scientist_torch_num_threads=(
            source.get("SCIENTIST_TORCH_NUM_THREADS", str(allowed_cores)).strip()
            or str(allowed_cores)
        ),
        scientist_torch_num_interop_threads=(
            source.get("SCIENTIST_TORCH_NUM_INTEROP_THREADS", "1").strip() or "1"
        ),
        omp_num_threads=(
            source.get("OMP_NUM_THREADS", str(allowed_cores)).strip() or str(allowed_cores)
        ),
        openblas_num_threads=(
            source.get("OPENBLAS_NUM_THREADS", str(allowed_cores)).strip() or str(allowed_cores)
        ),
        veclib_maximum_threads=(
            source.get("VECLIB_MAXIMUM_THREADS", str(allowed_cores)).strip() or str(allowed_cores)
        ),
        numexpr_num_threads=(
            source.get("NUMEXPR_NUM_THREADS", str(allowed_cores)).strip() or str(allowed_cores)
        ),
    )


def validate_process_bootstrap_config(config: ProcessBootstrapConfig) -> list[str]:
    """Return configuration conflicts that should be addressed before bootstrap."""
    conflicts: list[str] = []
    if config.duckdb_threads < 1:
        conflicts.append("DUCKDB_THREADS must be >= 1")
    if config.allowed_cores < 1:
        conflicts.append("allowed_cores must remain >= 1")
    if config.jax_platform_name and config.jax_platforms:
        platforms = {
            token.strip().lower() for token in config.jax_platforms.split(",") if token.strip()
        }
        if platforms and config.jax_platform_name.lower() not in platforms:
            conflicts.append(
                "JAX_PLATFORM_NAME must be included in JAX_PLATFORMS when both are set"
            )
    for field_name in (
        "scientist_torch_num_threads",
        "scientist_torch_num_interop_threads",
        "omp_num_threads",
        "openblas_num_threads",
        "veclib_maximum_threads",
        "numexpr_num_threads",
    ):
        try:
            if int(getattr(config, field_name)) < 1:
                conflicts.append(f"{field_name} must be >= 1")
        except ValueError:
            conflicts.append(f"{field_name} must be an integer")
    return conflicts


def apply_process_bootstrap(
    *,
    env: MutableMapping[str, str] | None = None,
    config: ProcessBootstrapConfig | None = None,
    load_dotenv_file: bool = True,
    configure_logging_sinks: bool = True,
    logs_root: Path | str = Path("logs"),
) -> ProcessBootstrapConfig:
    """Apply resolved env defaults and optional logging bootstrap explicitly."""
    if load_dotenv_file and load_dotenv is not None:
        load_dotenv(override=False)
    target_env = env if env is not None else os.environ
    resolved = config or build_process_bootstrap_config(env=target_env)
    conflicts = validate_process_bootstrap_config(resolved)
    if conflicts:
        raise ValueError("; ".join(conflicts))

    target_env["JAX_PLATFORM_NAME"] = resolved.jax_platform_name
    target_env["JAX_PLATFORMS"] = resolved.jax_platforms
    target_env["JAX_ENABLE_X64"] = resolved.jax_enable_x64
    target_env["JAX_DISABLE_MOST_OPTIMIZATIONS"] = resolved.jax_disable_most_optimizations
    target_env["JAX_CHECK_TRACER_LEAKS"] = resolved.jax_check_tracer_leaks
    target_env.setdefault(
        "XLA_PYTHON_CLIENT_PREALLOCATE",
        resolved.xla_python_client_preallocate,
    )
    target_env.setdefault("XLA_FLAGS", resolved.xla_flags)
    target_env.setdefault("SCIENTIST_TORCH_DEVICE", resolved.scientist_torch_device)
    target_env.setdefault(
        "SCIENTIST_TORCH_NUM_THREADS",
        resolved.scientist_torch_num_threads,
    )
    target_env.setdefault(
        "SCIENTIST_TORCH_NUM_INTEROP_THREADS",
        resolved.scientist_torch_num_interop_threads,
    )
    target_env.setdefault("OMP_NUM_THREADS", resolved.omp_num_threads)
    target_env.setdefault("OPENBLAS_NUM_THREADS", resolved.openblas_num_threads)
    target_env.setdefault("VECLIB_MAXIMUM_THREADS", resolved.veclib_maximum_threads)
    target_env.setdefault("NUMEXPR_NUM_THREADS", resolved.numexpr_num_threads)
    target_env.setdefault("DUCKDB_MEMORY_LIMIT", resolved.duckdb_memory_limit)
    target_env.setdefault("DUCKDB_THREADS", str(resolved.duckdb_threads))
    target_env.setdefault(
        "POLISYOS_MULTI_TENANT_ENABLED",
        "true" if resolved.multi_tenant_enabled else "false",
    )
    target_env.setdefault("POLISYOS_CELL_REGISTRY_PATH", resolved.cell_registry_path)
    target_env.setdefault("POLISYOS_DEFAULT_CELL_TIER", resolved.default_cell_tier)

    if configure_logging_sinks:
        configure_logging(
            log_level=resolved.log_level,
            logs_root=logs_root,
        )
    return resolved


def configure_logging(*, log_level: str = "DEBUG", logs_root: Path | str = Path("logs")) -> None:
    """Configure console and JSON log sinks once per process."""
    global _LOGGING_BOOTSTRAPPED
    if logger is None:
        return
    if _LOGGING_BOOTSTRAPPED:
        return
    with _LOGGING_LOCK:
        if _LOGGING_BOOTSTRAPPED:
            return
        logs_path = Path(logs_root)
        logs_path.mkdir(parents=True, exist_ok=True)
        logger.remove()
        logger.add(
            sys.stderr,
            level=log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
        )
        logger.add(
            str(logs_path / "system.log"),
            rotation="10 MB",
            retention="10 days",
            serialize=True,
            level="INFO",
            encoding="utf-8",
        )
        _LOGGING_BOOTSTRAPPED = True


def current_runtime_toggles(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Expose runtime toggles without triggering process bootstrap."""
    resolved = build_process_bootstrap_config(env=env)
    return {
        "log_level": resolved.log_level,
        "duckdb_memory_limit": resolved.duckdb_memory_limit,
        "duckdb_threads": resolved.duckdb_threads,
        "multi_tenant_enabled": resolved.multi_tenant_enabled,
        "cell_registry_path": resolved.cell_registry_path,
        "default_cell_tier": resolved.default_cell_tier,
    }


__all__ = [
    "EnvVarSpec",
    "ProcessBootstrapConfig",
    "apply_process_bootstrap",
    "build_process_bootstrap_config",
    "configure_logging",
    "current_runtime_toggles",
    "get_env_registry",
    "validate_process_bootstrap_config",
]
