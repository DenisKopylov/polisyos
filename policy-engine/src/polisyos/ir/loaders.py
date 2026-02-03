from __future__ import annotations

import json
from typing import Any, Mapping, Union, overload

from polisyos.ir.legacy.surface import PolicySurfaceIR
from polisyos.ir.legacy.trinity_v0 import TrinityBundle as LegacyTrinityBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.migration_report import MigrationReport
from polisyos.ir.legacy.migrations.surface_to_trinity import (
    is_legacy_trinity_bundle_payload,
    is_trinity_bundle_payload,
    migrate_surface_ir_to_trinity,
    migrate_trinity_bundle_v0_to_trinity,
    migrate_trinity_to_surface_ir,
)


class PolicyLoadError(ValueError):
    pass


def _parse_str_payload(payload: str, *, fmt: str) -> Any:
    text = payload.strip()
    if fmt == "json":
        return json.loads(text)
    if fmt == "yaml":
        import yaml

        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml

        return yaml.safe_load(text)


def _parse_bytes_payload(payload: bytes, *, fmt: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PolicyLoadError("Payload bytes must be UTF-8 decodable") from exc
    return _parse_str_payload(text, fmt=fmt)


def _normalize_payload(payload: Any, *, fmt: str) -> Any:
    if isinstance(payload, (str, bytes)):
        return _parse_str_payload(payload, fmt=fmt) if isinstance(payload, str) else _parse_bytes_payload(payload, fmt=fmt)
    return payload


def _ensure_mapping(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise PolicyLoadError(f"Unsupported policy payload type: {type(payload)}")
    return payload


PolicyArtifacts = Union[PolicySurfaceIR, TrinityBundle]


@overload
def load_policy(
    payload: Any,
    *,
    as_trinity: bool = False,
    auto_migrate: bool = True,
    fmt: str = "auto",
) -> PolicySurfaceIR: ...


@overload
def load_policy(
    payload: Any,
    *,
    as_trinity: bool = True,
    auto_migrate: bool = True,
    fmt: str = "auto",
) -> TrinityBundle: ...


def load_policy(
    payload: Any,
    *,
    as_trinity: bool = False,
    auto_migrate: bool = True,
    fmt: str = "auto",
) -> PolicyArtifacts:
    """Unified loader for legacy and canonical Trinity formats."""
    # Typed inputs
    if isinstance(payload, PolicySurfaceIR):
        if as_trinity:
            if not auto_migrate:
                raise PolicyLoadError("Auto-migrate disabled for legacy PolicySurfaceIR")
            bundle, _ = migrate_surface_ir_to_trinity(payload)
            return bundle
        return payload

    if isinstance(payload, TrinityBundle):
        if as_trinity:
            return payload
        if not auto_migrate:
            raise PolicyLoadError("Auto-migrate disabled for TrinityBundle -> PolicySurfaceIR")
        surface, _ = migrate_trinity_to_surface_ir(payload)
        return surface

    if isinstance(payload, LegacyTrinityBundle):
        if not auto_migrate:
            raise PolicyLoadError("Auto-migrate disabled for legacy TrinityBundle")
        bundle, _ = migrate_trinity_bundle_v0_to_trinity(payload)
        if as_trinity:
            return bundle
        surface, _ = migrate_trinity_to_surface_ir(bundle)
        return surface

    # Parse bytes/str
    normalized = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(normalized)

    if is_trinity_bundle_payload(mapping) and "schema_version" in mapping:
        bundle = TrinityBundle.model_validate(mapping)
        if as_trinity:
            return bundle
        if not auto_migrate:
            raise PolicyLoadError("Auto-migrate disabled for TrinityBundle -> PolicySurfaceIR")
        surface, _ = migrate_trinity_to_surface_ir(bundle)
        return surface

    if is_legacy_trinity_bundle_payload(mapping):
        if not auto_migrate:
            raise PolicyLoadError("Auto-migrate disabled for legacy TrinityBundle")
        legacy_bundle = LegacyTrinityBundle.model_validate(mapping)
        bundle, _ = migrate_trinity_bundle_v0_to_trinity(legacy_bundle)
        if as_trinity:
            return bundle
        surface, _ = migrate_trinity_to_surface_ir(bundle)
        return surface

    if "semantic" in mapping or str(mapping.get("schema_version", "")).startswith("2."):
        legacy_ir = PolicySurfaceIR.model_validate(mapping)
        if as_trinity:
            if not auto_migrate:
                raise PolicyLoadError("Auto-migrate disabled for legacy PolicySurfaceIR")
            bundle, _ = migrate_surface_ir_to_trinity(legacy_ir)
            return bundle
        return legacy_ir

    raise PolicyLoadError(
        "Unsupported policy payload: expected PolicySurfaceIR (schema_version 2.x), "
        "legacy TrinityBundle, or canonical TrinityBundle format."
    )


def load_trinity_bundle(
    payload: Any,
    *,
    fmt: str = "auto",
) -> tuple[TrinityBundle, MigrationReport | None]:
    """Load payload as canonical TrinityBundle and return optional MigrationReport."""
    if isinstance(payload, TrinityBundle):
        return payload, None
    if isinstance(payload, PolicySurfaceIR):
        bundle, report = migrate_surface_ir_to_trinity(payload)
        return bundle, report
    if isinstance(payload, LegacyTrinityBundle):
        bundle, report = migrate_trinity_bundle_v0_to_trinity(payload)
        return bundle, report

    normalized = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(normalized)

    if is_trinity_bundle_payload(mapping) and "schema_version" in mapping:
        return TrinityBundle.model_validate(mapping), None
    if is_legacy_trinity_bundle_payload(mapping):
        legacy_bundle = LegacyTrinityBundle.model_validate(mapping)
        bundle, report = migrate_trinity_bundle_v0_to_trinity(legacy_bundle)
        return bundle, report
    if "semantic" in mapping or str(mapping.get("schema_version", "")).startswith("2."):
        legacy_ir = PolicySurfaceIR.model_validate(mapping)
        bundle, report = migrate_surface_ir_to_trinity(legacy_ir)
        return bundle, report

    raise PolicyLoadError(
        "Unsupported policy payload for TrinityBundle loader."
    )


def load_trinity(payload: Any, *, fmt: str = "auto") -> TrinityBundle:
    """Convenience function to always load as canonical Trinity bundle."""
    bundle, _ = load_trinity_bundle(payload, fmt=fmt)
    return bundle


def load_legacy(payload: Any, *, fmt: str = "auto") -> PolicySurfaceIR:
    """Convenience function to always load as legacy PolicySurfaceIR."""
    return load_policy(payload, as_trinity=False, fmt=fmt)


__all__ = [
    "PolicyLoadError",
    "load_policy",
    "load_trinity",
    "load_trinity_bundle",
    "load_legacy",
]
