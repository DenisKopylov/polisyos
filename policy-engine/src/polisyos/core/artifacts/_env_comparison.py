"""Environment comparison and diffing logic."""

from __future__ import annotations

from ._env_models import (
    EnvironmentDiff,
    EnvironmentManifest,
    RiskLevel,
)
from ._env_utils import _risk_order, _short_hash

__all__ = [
    "compare_environments",
]


def compare_environments(a: EnvironmentManifest, b: EnvironmentManifest) -> list[EnvironmentDiff]:
    """
    Compare two environment manifests and return differences.

    Returns list of EnvironmentDiff ordered by risk level (critical first).
    """
    diffs: list[EnvironmentDiff] = []

    # --- CPU checks ---

    if a.cpu.architecture != b.cpu.architecture:
        diffs.append(
            EnvironmentDiff(
                field_path="cpu.architecture",
                field_name="CPU Architecture",
                value_a=a.cpu.architecture,
                value_b=b.cpu.architecture,
                risk_level=RiskLevel.CRITICAL,
                explanation=(
                    "Different CPU architectures will produce different floating-point results"
                ),
            )
        )

    for flag, name in [("has_avx512", "AVX-512"), ("has_avx2", "AVX2"), ("has_amx", "AMX")]:
        if getattr(a.cpu, flag) != getattr(b.cpu, flag):
            diffs.append(
                EnvironmentDiff(
                    field_path=f"cpu.{flag}",
                    field_name=f"CPU {name} Support",
                    value_a=getattr(a.cpu, flag),
                    value_b=getattr(b.cpu, flag),
                    risk_level=RiskLevel.HIGH,
                    explanation=(
                        f"{name} affects vectorized operations and may cause numerical differences"
                    ),
                )
            )

    # --- GPU checks ---

    if a.gpu.device_count != b.gpu.device_count:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.device_count",
                field_name="GPU Device Count",
                value_a=a.gpu.device_count,
                value_b=b.gpu.device_count,
                risk_level=RiskLevel.HIGH,
                explanation="Different GPU counts can change device assignment and parallelism",
            )
        )

    if a.gpu.model_name != b.gpu.model_name:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.model_name",
                field_name="GPU Model",
                value_a=a.gpu.model_name,
                value_b=b.gpu.model_name,
                risk_level=RiskLevel.MEDIUM,
                explanation="Different GPU models may produce different numerical behavior",
            )
        )

    uuids_a = set(a.gpu.device_uuids)
    uuids_b = set(b.gpu.device_uuids)
    if uuids_a or uuids_b:
        if uuids_a != uuids_b:
            diffs.append(
                EnvironmentDiff(
                    field_path="gpu.device_uuids",
                    field_name="GPU UUIDs",
                    value_a=sorted(uuids_a),
                    value_b=sorted(uuids_b),
                    risk_level=RiskLevel.HIGH,
                    explanation="GPU UUID changes indicate different physical devices",
                )
            )

    if a.gpu.cuda_version != b.gpu.cuda_version:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.cuda_version",
                field_name="CUDA Version",
                value_a=a.gpu.cuda_version,
                value_b=b.gpu.cuda_version,
                risk_level=RiskLevel.HIGH,
                explanation="Different CUDA versions have different kernel implementations",
            )
        )

    if a.gpu.cuda_driver_version != b.gpu.cuda_driver_version:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.cuda_driver_version",
                field_name="CUDA Driver Version",
                value_a=a.gpu.cuda_driver_version,
                value_b=b.gpu.cuda_driver_version,
                risk_level=RiskLevel.HIGH,
                explanation="Driver version affects GPU operation behavior",
            )
        )

    if a.gpu.cudnn_version != b.gpu.cudnn_version:
        diffs.append(
            EnvironmentDiff(
                field_path="gpu.cudnn_version",
                field_name="cuDNN Version",
                value_a=a.gpu.cudnn_version,
                value_b=b.gpu.cudnn_version,
                risk_level=RiskLevel.HIGH,
                explanation="cuDNN version affects convolution algorithm selection",
            )
        )

    # --- JAX / XLA checks ---

    if a.jax.jax_version != b.jax.jax_version:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.jax_version",
                field_name="JAX Version",
                value_a=a.jax.jax_version,
                value_b=b.jax.jax_version,
                risk_level=RiskLevel.HIGH,
                explanation="JAX version affects computation graph compilation",
            )
        )

    if a.jax.xla_flags != b.jax.xla_flags:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.xla_flags",
                field_name="XLA Flags",
                value_a=a.jax.xla_flags,
                value_b=b.jax.xla_flags,
                risk_level=RiskLevel.HIGH,
                explanation="XLA flags affect compiler optimizations and determinism",
            )
        )

    if a.jax.deterministic_ops_enabled != b.jax.deterministic_ops_enabled:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.deterministic_ops_enabled",
                field_name="XLA Deterministic Ops",
                value_a=a.jax.deterministic_ops_enabled,
                value_b=b.jax.deterministic_ops_enabled,
                risk_level=RiskLevel.CRITICAL,
                explanation="Non-deterministic ops will cause different results on each run",
            )
        )

    if a.jax.x64_enabled != b.jax.x64_enabled:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.x64_enabled",
                field_name="JAX X64 Enabled",
                value_a=a.jax.x64_enabled,
                value_b=b.jax.x64_enabled,
                risk_level=RiskLevel.HIGH,
                explanation="64-bit precision changes numerical results",
            )
        )

    if a.jax.default_backend != b.jax.default_backend:
        diffs.append(
            EnvironmentDiff(
                field_path="jax.default_backend",
                field_name="JAX Default Backend",
                value_a=a.jax.default_backend,
                value_b=b.jax.default_backend,
                risk_level=RiskLevel.HIGH,
                explanation="Backend selection affects device-specific computations",
            )
        )

    # --- Python ---

    if a.python.version != b.python.version:
        diffs.append(
            EnvironmentDiff(
                field_path="python.version",
                field_name="Python Version",
                value_a=a.python.version,
                value_b=b.python.version,
                risk_level=RiskLevel.MEDIUM,
                explanation="Minor Python version differences rarely affect numerical results",
            )
        )

    # --- Dependencies ---

    if a.dependencies and b.dependencies:
        if a.dependencies.lockfile_hash != b.dependencies.lockfile_hash:
            diffs.append(
                EnvironmentDiff(
                    field_path="dependencies.lockfile_hash",
                    field_name="Dependency Lockfile Hash",
                    value_a=_short_hash(a.dependencies.lockfile_hash),
                    value_b=_short_hash(b.dependencies.lockfile_hash),
                    risk_level=RiskLevel.HIGH,
                    explanation="Package version changes may affect computation",
                )
            )
    elif a.dependencies or b.dependencies:
        diffs.append(
            EnvironmentDiff(
                field_path="dependencies.lockfile_hash",
                field_name="Dependency Lockfile Hash",
                value_a=a.dependencies.lockfile_hash if a.dependencies else None,
                value_b=b.dependencies.lockfile_hash if b.dependencies else None,
                risk_level=RiskLevel.LOW,
                explanation="Missing lockfile information reduces reproducibility guarantees",
            )
        )

    # --- Git ---

    if a.git and b.git:
        if a.git.commit_sha != b.git.commit_sha:
            diffs.append(
                EnvironmentDiff(
                    field_path="git.commit_sha",
                    field_name="Git Commit",
                    value_a=a.git.commit_short,
                    value_b=b.git.commit_short,
                    risk_level=RiskLevel.MEDIUM,
                    explanation="Code changes between commits",
                )
            )

        if a.git.dirty or b.git.dirty:
            diffs.append(
                EnvironmentDiff(
                    field_path="git.dirty",
                    field_name="Uncommitted Changes",
                    value_a=a.git.dirty,
                    value_b=b.git.dirty,
                    risk_level=RiskLevel.LOW,
                    explanation="Working directory has uncommitted changes",
                )
            )

    # --- System libraries ---

    system_keys = set(a.system_libraries) | set(b.system_libraries)
    for name in sorted(system_keys):
        info_a = a.system_libraries.get(name)
        info_b = b.system_libraries.get(name)
        if info_a is None or info_b is None:
            diffs.append(
                EnvironmentDiff(
                    field_path=f"system_libraries.{name}",
                    field_name=f"System Library {name}",
                    value_a=info_a.model_dump() if info_a else None,
                    value_b=info_b.model_dump() if info_b else None,
                    risk_level=RiskLevel.MEDIUM,
                    explanation="Missing system library metadata may hide runtime differences",
                )
            )
            continue
        if info_a.sha256 != info_b.sha256:
            diffs.append(
                EnvironmentDiff(
                    field_path=f"system_libraries.{name}.sha256",
                    field_name=f"System Library {name}",
                    value_a=_short_hash(info_a.sha256),
                    value_b=_short_hash(info_b.sha256),
                    risk_level=RiskLevel.HIGH,
                    explanation="System library changes can alter runtime behavior",
                )
            )

    # --- Precision hint ---

    if a.expected_precision_loss != b.expected_precision_loss:
        diffs.append(
            EnvironmentDiff(
                field_path="expected_precision_loss",
                field_name="Expected Precision Loss",
                value_a=a.expected_precision_loss,
                value_b=b.expected_precision_loss,
                risk_level=RiskLevel.INFO,
                explanation="Precision hint differs across environments",
            )
        )

    diffs.sort(key=lambda diff: _risk_order(diff.risk_level))
    return diffs
