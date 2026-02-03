from __future__ import annotations

import json
from typing import Any, Mapping

from polisyos.ir.legacy.surface import PolicySurfaceIR
from polisyos.ir.legacy.trinity_v0 import TrinityBundle as LegacyTrinityBundle


class LegacyLoadError(ValueError):
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
        raise LegacyLoadError("Payload bytes must be UTF-8 decodable") from exc
    return _parse_str_payload(text, fmt=fmt)


def _normalize_payload(payload: Any, *, fmt: str) -> Any:
    if isinstance(payload, (str, bytes)):
        return _parse_str_payload(payload, fmt=fmt) if isinstance(payload, str) else _parse_bytes_payload(payload, fmt=fmt)
    return payload


def _ensure_mapping(payload: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise LegacyLoadError(f"{label} payload must be a mapping")
    return payload


def load_policy_surface_ir(
    payload: bytes | str | Mapping[str, Any] | PolicySurfaceIR,
    *,
    fmt: str = "auto",
) -> PolicySurfaceIR:
    if isinstance(payload, PolicySurfaceIR):
        return payload
    parsed = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(parsed, label="PolicySurfaceIR")
    return PolicySurfaceIR.model_validate(mapping)


def load_legacy_trinity_bundle(
    payload: bytes | str | Mapping[str, Any] | LegacyTrinityBundle,
    *,
    fmt: str = "auto",
) -> LegacyTrinityBundle:
    if isinstance(payload, LegacyTrinityBundle):
        return payload
    parsed = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(parsed, label="LegacyTrinityBundle")
    return LegacyTrinityBundle.model_validate(mapping)


__all__ = [
    "LegacyLoadError",
    "load_policy_surface_ir",
    "load_legacy_trinity_bundle",
]
