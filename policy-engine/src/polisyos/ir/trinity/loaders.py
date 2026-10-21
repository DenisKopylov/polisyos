"""Public trinity loaders module API."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from polisyos.ir.artifacts.io import get_json_artifact
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TRINITY_BUNDLE_SCHEMA_VERSION, TrinityBundle

if TYPE_CHECKING:
    from polisyos.ir.artifacts.contracts import ArtifactSelector, ArtifactStore


class TrinityLoadError(ValueError):
    """Trinity load error exception."""

    pass


def _parse_str_payload(payload: str, *, fmt: str) -> object:
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


def _parse_bytes_payload(payload: bytes, *, fmt: str) -> object:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TrinityLoadError("Payload bytes must be UTF-8 decodable") from exc
    return _parse_str_payload(text, fmt=fmt)


def _normalize_payload(payload: object, *, fmt: str) -> object:
    if isinstance(payload, (str, bytes)):
        return (
            _parse_str_payload(payload, fmt=fmt)
            if isinstance(payload, str)
            else _parse_bytes_payload(payload, fmt=fmt)
        )
    return payload


def _ensure_mapping(payload: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise TrinityLoadError(f"{label} payload must be a mapping")
    return payload


def _ensure_schema_version(payload: Mapping[str, Any], *, target: str) -> None:
    version = payload.get("schema_version")
    if version is None:
        raise TrinityLoadError("schema_version is required")
    if str(version) != target:
        raise TrinityLoadError(f"Unsupported schema_version '{version}'; expected '{target}'")


def load_problem_frame(
    payload: bytes | str | Mapping[str, Any] | ProblemFrame,
    *,
    fmt: str = "auto",
    target_schema_version: str = "1.0",
) -> ProblemFrame:
    """Load problem frame."""
    if isinstance(payload, ProblemFrame):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                "Unsupported schema_version '"
                f"{payload.schema_version}"
                "'; expected '"
                f"{target_schema_version}"
                "'"
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
    """Load policy spec."""
    if isinstance(payload, PolicySpec):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                "Unsupported schema_version '"
                f"{payload.schema_version}"
                "'; expected '"
                f"{target_schema_version}"
                "'"
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
    """Load model spec."""
    if isinstance(payload, ModelSpec):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                "Unsupported schema_version '"
                f"{payload.schema_version}"
                "'; expected '"
                f"{target_schema_version}"
                "'"
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
    """Load trinity bundle."""
    if isinstance(payload, TrinityBundle):
        if payload.schema_version != target_schema_version:
            raise TrinityLoadError(
                "Unsupported schema_version '"
                f"{payload.schema_version}"
                "'; expected '"
                f"{target_schema_version}"
                "'"
            )
        return payload
    parsed = _normalize_payload(payload, fmt=fmt)
    mapping = _ensure_mapping(parsed, label="TrinityBundle")
    _ensure_schema_version(mapping, target=target_schema_version)
    return TrinityBundle.model_validate(mapping)


def _manifest_value(manifest: object, field: str, *, model_attribute: str | None = None) -> object:
    if isinstance(manifest, Mapping):
        if field in manifest:
            return manifest[field]
        if model_attribute is not None:
            return manifest.get(model_attribute)
        return None
    return getattr(manifest, model_attribute or field, None)


def load_trinity_bundle_artifact(store: ArtifactStore, selector: ArtifactSelector) -> TrinityBundle:
    """Load a persisted Trinity bundle through its selected IR CAS view.

    The IR JSON reader verifies the selected profile and byte conformance. This
    boundary adds Trinity's manifest owner metadata and payload-version checks
    before returning the typed bundle.
    """
    payload = get_json_artifact(store, selector)
    manifest = store.get_manifest(selector)
    schema = _manifest_value(manifest, "schema", model_attribute="artifact_schema")
    schema_name = _manifest_value(schema, "name")
    schema_version = _manifest_value(schema, "version")
    if (
        _manifest_value(manifest, "kind") != TrinityBundle.ARTIFACT_KIND
        or _manifest_value(manifest, "media_type") != TrinityBundle.ARTIFACT_MEDIA_TYPE
        or schema_name != TrinityBundle.ARTIFACT_SCHEMA_NAME
        or schema_version != TrinityBundle.ARTIFACT_SCHEMA_VERSION
    ):
        raise TrinityLoadError("TrinityBundle artifact manifest does not match its IR owner")

    bundle = load_trinity_bundle(payload)
    if bundle.schema_version != schema_version:
        raise TrinityLoadError(
            "TrinityBundle payload schema_version does not match its selected artifact manifest"
        )
    return bundle


__all__ = [
    "TrinityLoadError",
    "load_model_spec",
    "load_policy_spec",
    "load_problem_frame",
    "load_trinity_bundle",
    "load_trinity_bundle_artifact",
]
