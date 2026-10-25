"""Public trinity loaders module API."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.artifacts import ArtifactStore
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact,
    _put_owned_json_artifact,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TRINITY_BUNDLE_SCHEMA_VERSION, TrinityBundle

if TYPE_CHECKING:
    from polisyos.ir.artifacts._lineage import InputRefLike
    from polisyos.ir.artifacts.contracts import ArtifactSelector


class TrinityLoadError(ValueError):
    """Trinity load error exception."""

    pass


_TRINITY_BUNDLE_POLICY = ("ir.trinity.trinity_bundle.wire-law", "1")
_TRINITY_BUNDLE_OWNER = declare_model_owner(
    TrinityBundle,
    contract_id="ir.trinity.trinity_bundle.owner.v1",
    dto_fqn="polisyos.ir.trinity.TrinityBundle",
    abi_key="ir.trinity.trinity_bundle.owner.v1.dto-abi.v1",
    registry_key="ir.trinity_bundle",
    kind=TrinityBundle.ARTIFACT_KIND,
    media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
    purpose="trinity_bundle",
    policy_revision="ir.trinity.trinity_bundle.owner.v1.admission.v1",
    accepted_wire_policies=(_TRINITY_BUNDLE_POLICY,),
    payload_version_field="schema_version",
    validate_profile=owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        OwnedJSONRepresentation(
            schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
            schema_version=TRINITY_BUNDLE_SCHEMA_VERSION,
            payload_version=TRINITY_BUNDLE_SCHEMA_VERSION,
            wire_policy_ref=_TRINITY_BUNDLE_POLICY[0],
            wire_policy_revision=_TRINITY_BUNDLE_POLICY[1],
            profile_ref=None,
            compatibility=CompatibilityMode.NONE,
            notes=(
                "Exact owner-bound TrinityBundle JSON representation; unknown history remains opaque.",
            ),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


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


def _trinity_owner_error(exc: CanonViolation) -> TrinityLoadError:
    """Preserve the public Trinity refusal boundary for shared owner failures."""
    code = getattr(exc, "code", str(exc))
    if code in {
        "ir_owned_artifact_manifest_identity_invalid",
        "ir_owned_artifact_manifest_identity_mismatch",
        "ir_owned_artifact_owner_contract_mismatch",
        "ir_owned_artifact_representation_unregistered",
    }:
        return TrinityLoadError("TrinityBundle artifact manifest does not match its IR owner")
    if code == "ir_owned_artifact_profile_refused":
        return TrinityLoadError("TrinityBundle artifact profile does not match its IR owner")
    if code in {
        "ir_owned_artifact_payload_version_invalid",
        "ir_owned_artifact_representation_unreadable",
    }:
        return TrinityLoadError(
            "Unsupported schema_version; TrinityBundle payload is not an admitted owner representation"
        )
    return TrinityLoadError("TrinityBundle artifact failed IR owner admission")


def persist_trinity_bundle_artifact(
    store: ArtifactStore,
    bundle: TrinityBundle,
    *,
    inputs: Sequence[InputRefLike] | None = None,
) -> ArtifactRefModel:
    """Persist a Trinity bundle under its exact owner-declared JSON representation."""
    selected_ref = _put_owned_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        owner=_TRINITY_BUNDLE_OWNER,
        schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
        schema_version=TRINITY_BUNDLE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.from_selected_write(selected_ref)


def load_trinity_bundle_artifact(store: ArtifactStore, selector: ArtifactSelector) -> TrinityBundle:
    """Load a persisted Trinity bundle through exact owner and profile admission."""
    try:
        return _get_owned_json_artifact(store, selector, owner=_TRINITY_BUNDLE_OWNER)
    except CanonViolation as exc:
        raise _trinity_owner_error(exc) from exc


__all__ = [
    "TrinityLoadError",
    "load_model_spec",
    "load_policy_spec",
    "load_problem_frame",
    "load_trinity_bundle",
    "load_trinity_bundle_artifact",
    "persist_trinity_bundle_artifact",
]
