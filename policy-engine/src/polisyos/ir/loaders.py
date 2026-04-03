"""Load canonical Trinity bundles from dict, JSON, YAML, or bytes payloads."""
from __future__ import annotations

import json
from typing import Any, Mapping

from polisyos.ir.trinity import TrinityBundle


class PolicyLoadError(ValueError):
    """Raise when a payload cannot be parsed or validated as a Trinity bundle."""
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


def load_policy(
    payload: Any,
    *,
    auto_migrate: bool = True,
    fmt: str = "auto",
) -> TrinityBundle:
    """Parse and validate a policy payload as a canonical ``TrinityBundle``.

    Args:
        payload: Existing ``TrinityBundle``, mapping, JSON/YAML string, or UTF-8
            bytes payload.
        auto_migrate: Preserve the public loader signature; malformed payloads
            currently raise ``PolicyLoadError`` instead of applying migrations.
        fmt: ``"json"``, ``"yaml"``, or ``"auto"`` format hint for string/bytes
            payloads.

    Returns:
        The validated canonical Trinity bundle.

    Raises:
        PolicyLoadError: If the payload cannot be decoded, parsed, or validated.

    Example:
        >>> bundle = load_policy('{"schema_version": "1.0", "problem_frame": {...}}', fmt="json")
    """
    bundle, _ = load_trinity_bundle(payload, fmt=fmt, auto_migrate=auto_migrate)
    return bundle


def load_trinity_bundle(
    payload: Any,
    *,
    fmt: str = "auto",
    auto_migrate: bool = True,
) -> tuple[TrinityBundle, None]:
    """Load payload as canonical TrinityBundle and return optional migration report."""
    if isinstance(payload, TrinityBundle):
        return payload, None

    normalized = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(normalized)

    try:
        return TrinityBundle.model_validate(mapping), None
    except Exception as exc:
        if auto_migrate:
            raise PolicyLoadError("Payload is not a valid TrinityBundle.") from exc
        raise PolicyLoadError("Unsupported policy payload for TrinityBundle loader") from exc


def load_trinity(payload: Any, *, fmt: str = "auto") -> TrinityBundle:
    """Convenience function to always load as canonical Trinity bundle."""
    bundle, _ = load_trinity_bundle(payload, fmt=fmt)
    return bundle


__all__ = [
    "PolicyLoadError",
    "load_policy",
    "load_trinity",
    "load_trinity_bundle",
]
