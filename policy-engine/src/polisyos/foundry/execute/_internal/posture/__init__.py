"""Resolve effective Foundry execution posture from compile-time plans and run-time overrides."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.contracts.foundry import ExecPlan, FoundryExecConfig
from polisyos.core.observability.determinism import parse_determinism_tier
from polisyos.foundry.runtime.fingerprint import EnvironmentFingerprint

__all__ = [
    "ResolvedExecutionPosture",
    "resolve_execution_posture",
]

_POSTURE_CAPTURE_FAILURES = (
    AttributeError,
    ImportError,
    ModuleNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True, slots=True)
class ResolvedExecutionPosture:
    """Effective runtime posture after applying request overrides and plan defaults."""

    seed: int
    seed_source: str
    determinism_tier: str | None
    nan_guard_enabled: bool
    max_steps: int | None
    mode: str
    jit: bool
    capture_env: bool
    current_environment_fingerprint: str | None
    notes: tuple[str, ...]


def resolve_execution_posture(
    exec_plan: ExecPlan,
    exec_config: FoundryExecConfig | None = None,
) -> ResolvedExecutionPosture:
    """Resolve the effective execution posture with request overrides taking precedence."""
    config = exec_config or FoundryExecConfig()
    explicit = set(getattr(config, "model_fields_set", set()))

    if "seed" in explicit:
        seed = int(config.seed)
        seed_source = "exec_config.seed"
    elif isinstance(exec_plan.random_seed, int):
        seed = int(exec_plan.random_seed)
        seed_source = "exec_plan.random_seed"
    else:
        seed = int(config.seed)
        seed_source = "default.seed"

    if "mode" in explicit:
        mode = config.mode
    else:
        mode = exec_plan.mode

    if "max_steps" in explicit:
        max_steps = config.max_steps
    else:
        max_steps = exec_plan.max_steps

    determinism_tier = exec_plan.determinism_tier
    nan_guard_enabled = bool(exec_plan.nan_guard_enabled)
    jit = bool(exec_plan.jit)
    capture_env = bool(config.capture_env)

    notes: list[str] = [f"seed_source:{seed_source}"]
    if jit:
        notes.append("unsupported_exec_hint:jit=eager_only")
    if mode != "dev":
        notes.append(f"unsupported_exec_hint:mode={mode}")

    current_environment_fingerprint: str | None = None
    parsed_tier = parse_determinism_tier(determinism_tier)
    if determinism_tier and parsed_tier is None:
        notes.append(f"unknown_determinism_tier:{determinism_tier}")
    elif parsed_tier is not None:
        try:
            current_environment_fingerprint = EnvironmentFingerprint.capture(
                parsed_tier,
                seed,
            ).compute_hash()
            if (
                exec_plan.environment_fingerprint
                and current_environment_fingerprint != exec_plan.environment_fingerprint
            ):
                notes.append(
                    "environment_fingerprint_mismatch:"
                    f"{exec_plan.environment_fingerprint}->{current_environment_fingerprint}"
                )
        except _POSTURE_CAPTURE_FAILURES as exc:  # pragma: no cover - defensive logging path
            notes.append(f"environment_fingerprint_unavailable:{type(exc).__name__}")
    elif exec_plan.environment_fingerprint:
        notes.append("environment_fingerprint_unverified:missing_determinism_tier")

    return ResolvedExecutionPosture(
        seed=seed,
        seed_source=seed_source,
        determinism_tier=determinism_tier,
        nan_guard_enabled=nan_guard_enabled,
        max_steps=max_steps,
        mode=mode,
        jit=jit,
        capture_env=capture_env,
        current_environment_fingerprint=current_environment_fingerprint,
        notes=tuple(notes),
    )
