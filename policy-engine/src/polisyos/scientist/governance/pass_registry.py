from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import EntryPoint
from typing import Any

from polisyos.core.discovery import list_entry_points
from polisyos.core.governance.passes.base import ValidatorPass
from polisyos.core.governance.profiles import ValidationProfile

from .pass_entrypoints import builtin_governance_pass_factories
from .pipeline import ValidationPipeline

ENTRY_POINT_GROUP_GOVERNANCE_PASSES = "polisyos.scientist_governance_passes"

RUNTIME_ALLOWED_PASS_IDS: frozenset[str] = frozenset(
    {
        "confidence",
        "equity",
        "pii_check",
        "refutation",
        "literature_gate",
        "sutva_check",
        "transportability_required",
        "human_review_required",
    }
)


def load_governance_passes() -> list[ValidatorPass]:
    entry_points = list(list_entry_points(group=ENTRY_POINT_GROUP_GOVERNANCE_PASSES))
    providers = _resolve_providers(entry_points)

    validators: list[ValidatorPass] = []
    pass_sources: dict[str, str] = {}
    for source_name, provider in providers:
        validator = _instantiate_validator(source_name=source_name, provider=provider)
        existing_source = pass_sources.get(validator.pass_id)
        if existing_source is not None:
            raise ValueError(
                "Duplicate governance pass_id "
                f"'{validator.pass_id}' discovered from {existing_source} and {source_name}."
            )
        pass_sources[validator.pass_id] = source_name
        validators.append(validator)

    if not validators:
        raise RuntimeError(
            "No governance passes discovered from entry points or fallback factories."
        )

    return validators


def build_governance_pipeline() -> ValidationPipeline:
    return ValidationPipeline(load_governance_passes())


def runtime_profile(profile: ValidationProfile) -> ValidationProfile:
    return ValidationProfile(
        level=profile.level,
        pass_ids=frozenset(
            pass_id for pass_id in profile.pass_ids if pass_id in RUNTIME_ALLOWED_PASS_IDS
        ),
        thresholds=dict(profile.thresholds),
        short_circuit_on_blocker=profile.short_circuit_on_blocker,
    )


def _resolve_providers(
    entry_points: list[EntryPoint],
) -> list[tuple[str, Callable[[], ValidatorPass] | type[ValidatorPass]]]:
    if not entry_points:
        fallbacks = builtin_governance_pass_factories()
        return [
            (f"fallback:{name}", factory)
            for name, factory in sorted(fallbacks.items(), key=lambda item: item[0])
        ]

    resolved: list[tuple[str, Callable[[], ValidatorPass] | type[ValidatorPass]]] = []
    for entry_point in entry_points:
        source_name = f"entry_point:{entry_point.name}"
        try:
            target = entry_point.load()
        except Exception as exc:
            raise RuntimeError(f"Failed to load governance pass from {source_name}: {exc}") from exc
        provider = _coerce_provider(target=target, source_name=source_name)
        resolved.append((source_name, provider))
    return resolved


def _coerce_provider(
    *,
    target: Any,
    source_name: str,
) -> Callable[[], ValidatorPass] | type[ValidatorPass]:
    if isinstance(target, type):
        if not issubclass(target, ValidatorPass):
            raise TypeError(
                f"{source_name} must point to ValidatorPass subclass or zero-arg factory, "
                f"got class {target.__name__}."
            )
        return target

    if callable(target):
        return target

    raise TypeError(
        f"{source_name} must point to ValidatorPass subclass or zero-arg factory, "
        f"got {type(target).__name__}."
    )


def _instantiate_validator(
    *,
    source_name: str,
    provider: Callable[[], ValidatorPass] | type[ValidatorPass],
) -> ValidatorPass:
    try:
        if isinstance(provider, type):
            validator = provider()
        else:
            validator = provider()
    except TypeError as exc:
        raise TypeError(
            f"{source_name} must be instantiable without required arguments: {exc}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to instantiate governance pass from {source_name}: {exc}"
        ) from exc

    if not isinstance(validator, ValidatorPass):
        raise TypeError(
            f"{source_name} returned {type(validator).__name__}; expected ValidatorPass instance."
        )
    return validator


__all__ = [
    "ENTRY_POINT_GROUP_GOVERNANCE_PASSES",
    "RUNTIME_ALLOWED_PASS_IDS",
    "load_governance_passes",
    "build_governance_pipeline",
    "runtime_profile",
]
