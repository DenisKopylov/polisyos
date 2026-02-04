from __future__ import annotations

import json
from typing import Any, Mapping

from polisyos.ir.migration_report import MigrationReport
from polisyos.ir.trinity import TrinityBundle


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
    if isinstance(payload, str):
        return _parse_str_payload(payload, fmt=fmt)
    if isinstance(payload, bytes):
        return _parse_bytes_payload(payload, fmt=fmt)
    return payload


def _ensure_mapping(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise PolicyLoadError(f"Unsupported policy payload type: {type(payload)}")
    return payload


def _looks_like_legacy_surface(mapping: Mapping[str, Any]) -> bool:
    if "semantic" in mapping or "advisory" in mapping:
        return True
    version = str(mapping.get("schema_version", ""))
    return version.startswith("2.")


def load_policy(
    payload: Any,
    *,
    as_trinity: bool = True,
    auto_migrate: bool = True,
    fmt: str = "auto",
) -> TrinityBundle:
    """Load policy payload as canonical TrinityBundle.

    Legacy PolicySurfaceIR loading was removed in Stage 3 cleanup.
    """
    if not as_trinity:
        raise PolicyLoadError(
            "Legacy PolicySurfaceIR output is removed. Use load_trinity()/load_policy(as_trinity=True)."
        )
    bundle, _ = load_trinity_bundle(payload, fmt=fmt, auto_migrate=auto_migrate)
    return bundle


def load_trinity_bundle(
    payload: Any,
    *,
    fmt: str = "auto",
    auto_migrate: bool = True,
) -> tuple[TrinityBundle, MigrationReport | None]:
    """Load payload as canonical TrinityBundle and return optional migration report."""
    if isinstance(payload, TrinityBundle):
        return payload, None

    normalized = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(normalized)

    if _looks_like_legacy_surface(mapping):
        raise PolicyLoadError(
            "Legacy PolicySurfaceIR payload is no longer supported by runtime loaders. "
            "Migrate payloads to TrinityBundle before loading."
        )

    try:
        return TrinityBundle.model_validate(mapping), None
    except Exception as exc:  # pragma: no cover - defensive path
        if auto_migrate:
            raise PolicyLoadError(
                "Unsupported policy payload for TrinityBundle loader."
            ) from exc
        raise PolicyLoadError("Unsupported policy payload for TrinityBundle loader") from exc


def load_trinity(payload: Any, *, fmt: str = "auto") -> TrinityBundle:
    """Convenience function to always load as canonical Trinity bundle."""
    bundle, _ = load_trinity_bundle(payload, fmt=fmt)
    return bundle


def load_legacy(payload: Any, *, fmt: str = "auto") -> TrinityBundle:
    raise PolicyLoadError(
        "load_legacy() was removed with PolicySurfaceIR decommissioning. "
        "Use load_trinity() and TrinityBundle payloads."
    )


__all__ = [
    "PolicyLoadError",
    "load_policy",
    "load_trinity",
    "load_trinity_bundle",
    "load_legacy",
]
