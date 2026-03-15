from __future__ import annotations

import json
from typing import Any, Mapping

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TRINITY_BUNDLE_SCHEMA_VERSION, TrinityBundle


class TrinityLoadError(ValueError):
    pass


def _parse_str_payload(payload: str, *, fmt: str) -> Any:
    text = payload.strip()
    if fmt == "json":
        return json.loads(text)
    if fmt == "yaml":
        import yaml

        return yaml.safe_load(text)
    # auto
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml

        return yaml.safe_load(text)


def _parse_bytes_payload(payload: bytes, *, fmt: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrinityLoadError("Payload bytes must be UTF-8 decodable") from exc
    return _parse_str_payload(text, fmt=fmt)


def _normalize_payload(payload: Any, *, fmt: str) -> Any:
    if isinstance(payload, (str, bytes)):
        return _parse_str_payload(payload, fmt=fmt) if isinstance(payload, str) else _parse_bytes_payload(payload, fmt=fmt)
    return payload


def _ensure_mapping(payload: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise TrinityLoadError(f"{label} payload must be a mapping")
    return payload


def _ensure_schema_version(payload: Mapping[str, Any], *, target: str) -> None:
    version = payload.get("schema_version")
    if version is None:
        raise TrinityLoadError("schema_version is required")
    if str(version) != target:
        raise TrinityLoadError(
            f"Unsupported schema_version '{version}'; expected '{target}'"
        )


def load_problem_frame(
    payload: bytes | str | Mapping[str, Any] | ProblemFrame,
    *,
    fmt: str = "auto",
    target_schema_version: str = "1.0",
) -> ProblemFrame:
    if isinstance(payload, ProblemFrame):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                f"Unsupported schema_version '{payload.schema_version}'; expected '{target_schema_version}'"
            )
        return payload
    parsed = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(parsed, label="ProblemFrame")
    _ensure_schema_version(mapping, target=target_schema_version)
    return ProblemFrame.model_validate(mapping)


def load_policy_spec(
    payload: bytes | str | Mapping[str, Any] | PolicySpec,
    *,
    fmt: str = "auto",
    target_schema_version: str = "1.0",
) -> PolicySpec:
    if isinstance(payload, PolicySpec):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                f"Unsupported schema_version '{payload.schema_version}'; expected '{target_schema_version}'"
            )
        return payload
    parsed = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(parsed, label="PolicySpec")
    _ensure_schema_version(mapping, target=target_schema_version)
    return PolicySpec.model_validate(mapping)


def load_model_spec(
    payload: bytes | str | Mapping[str, Any] | ModelSpec,
    *,
    fmt: str = "auto",
    target_schema_version: str = "1.0",
) -> ModelSpec:
    if isinstance(payload, ModelSpec):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                f"Unsupported schema_version '{payload.schema_version}'; expected '{target_schema_version}'"
            )
        return payload
    parsed = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(parsed, label="ModelSpec")
    _ensure_schema_version(mapping, target=target_schema_version)
    return ModelSpec.model_validate(mapping)


def load_trinity_bundle(
    payload: bytes | str | Mapping[str, Any] | TrinityBundle,
    *,
    fmt: str = "auto",
    target_schema_version: str = TRINITY_BUNDLE_SCHEMA_VERSION,
) -> TrinityBundle:
    if isinstance(payload, TrinityBundle):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                f"Unsupported schema_version '{payload.schema_version}'; expected '{target_schema_version}'"
            )
        return payload
    parsed = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(parsed, label="TrinityBundle")
    _ensure_schema_version(mapping, target=target_schema_version)
    return TrinityBundle.model_validate(mapping)


__all__ = [
    "TrinityLoadError",
    "load_problem_frame",
    "load_policy_spec",
    "load_model_spec",
    "load_trinity_bundle",
]
