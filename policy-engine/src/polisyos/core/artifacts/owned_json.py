"""Validate Core JSON against an explicit artifact-owner ABI.

An owner profile is supplied by the defining producer contract or typed workflow
context. It is never inferred from the selected manifest or a caller-provided
label. A successful read proves selected-view and payload conformity only; it
does not attest producer authenticity, admissibility, or authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Literal, NoReturn, TypeVar

from pydantic import BaseModel

from polisyos.common.canonical_profile import CanonicalProfileRefusalError

from .canonical_profile import (
    artifact_ref_for_manifest,
    read_core_manifest_profile,
    validate_core_model_json_artifact,
)
from .manifest import ArtifactRef, CanonInfo, SchemaInfo

_ModelT = TypeVar("_ModelT", bound=BaseModel)
type _SchemaKey = tuple[str, str] | Literal["absent"]
type _PayloadVersionRule = tuple[_SchemaKey, str]


def _invalid_owner_profile() -> NoReturn:
    """Refuse malformed explicit owner metadata instead of guessing a default."""
    raise ValueError("core_artifact_owner_profile_invalid")


def _schema_key(schema: SchemaInfo) -> tuple[str, str]:
    """Return the exact schema identity after strict value checks."""
    if (
        type(schema) is not SchemaInfo
        or type(schema.name) is not str
        or not schema.name
        or type(schema.version) is not str
        or not schema.version
    ):
        _invalid_owner_profile()
    return schema.name, schema.version


def _normalize_payload_version_rules(
    raw_rules: object,
    schema_keys: tuple[_SchemaKey, ...],
) -> tuple[_PayloadVersionRule, ...]:
    """Validate and canonically order a complete schema-version relation."""
    if type(raw_rules) is not tuple or not raw_rules:
        _invalid_owner_profile()
    rules_by_key: dict[_SchemaKey, str] = {}
    for raw_rule in raw_rules:
        if type(raw_rule) is not tuple or len(raw_rule) != 2:
            _invalid_owner_profile()
        raw_key, payload_version = raw_rule
        if type(raw_key) is str:
            if raw_key != "absent":
                _invalid_owner_profile()
            rule_key: _SchemaKey = "absent"
        elif (
            type(raw_key) is tuple
            and len(raw_key) == 2
            and type(raw_key[0]) is str
            and raw_key[0]
            and type(raw_key[1]) is str
            and raw_key[1]
        ):
            rule_key = (raw_key[0], raw_key[1])
        else:
            _invalid_owner_profile()
        if type(payload_version) is not str or not payload_version or rule_key in rules_by_key:
            _invalid_owner_profile()
        rules_by_key[rule_key] = payload_version
    if set(rules_by_key) != set(schema_keys):
        _invalid_owner_profile()
    return tuple((key, rules_by_key[key]) for key in schema_keys)


@dataclass(frozen=True, slots=True)
class CoreArtifactOwnerProfile:
    """Declare the exact finite ABI a Core JSON owner accepts.

    ``schema_variants`` is either a non-empty finite tuple of copied ``SchemaInfo``
    values or the explicit literal ``"absent"``. ``payload_schema_version_by_manifest``
    maps every accepted schema identity (``(name, version)``) to its exact payload
    ``schema_version`` value. The ``"absent"`` key represents a schema-less manifest.
    Models without a ``schema_version`` field must say ``"not_applicable"`` instead.

    Args:
        kind: Exact manifest artifact kind emitted by the defining owner.
        media_type: Exact manifest media type emitted by the defining owner.
        schema_variants: Finite allowed schemas, or the explicit ``"absent"`` state.
        payload_schema_version_by_manifest: Complete schema-to-payload-version relation,
            or ``"not_applicable"`` for models without that payload field.

    Raises:
        ValueError: If a field is empty, incomplete, ambiguous, or malformed.
    """

    kind: str
    media_type: str
    schema_variants: tuple[SchemaInfo, ...] | Literal["absent"]
    payload_schema_version_by_manifest: tuple[_PayloadVersionRule, ...] | Literal["not_applicable"]
    _schema_keys: tuple[_SchemaKey, ...] = field(init=False, repr=False)
    _payload_rules: tuple[_PayloadVersionRule, ...] | Literal["not_applicable"] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Capture validated immutable identities for later comparisons."""
        if (
            type(self.kind) is not str
            or not self.kind
            or type(self.media_type) is not str
            or not self.media_type
        ):
            _invalid_owner_profile()

        if type(self.schema_variants) is str and self.schema_variants == "absent":
            schema_keys: tuple[_SchemaKey, ...] = ("absent",)
        else:
            if type(self.schema_variants) is not tuple or not self.schema_variants:
                _invalid_owner_profile()
            copied_schemas_by_key: dict[tuple[str, str], SchemaInfo] = {}
            schema_keys_list: list[tuple[str, str]] = []
            for schema in self.schema_variants:
                key = _schema_key(schema)
                if key in schema_keys_list:
                    _invalid_owner_profile()
                schema_keys_list.append(key)
                copied_schemas_by_key[key] = SchemaInfo(name=key[0], version=key[1])
            sorted_schema_keys = tuple(sorted(schema_keys_list))
            copied_schemas = tuple(copied_schemas_by_key[key] for key in sorted_schema_keys)
            schema_keys = sorted_schema_keys
            object.__setattr__(self, "schema_variants", copied_schemas)
        object.__setattr__(self, "_schema_keys", schema_keys)

        raw_rules = self.payload_schema_version_by_manifest
        if type(raw_rules) is str:
            if raw_rules != "not_applicable":
                _invalid_owner_profile()
            object.__setattr__(self, "_payload_rules", "not_applicable")
            return
        normalized_rules = _normalize_payload_version_rules(raw_rules, schema_keys)
        object.__setattr__(self, "_payload_rules", normalized_rules)
        object.__setattr__(self, "payload_schema_version_by_manifest", normalized_rules)

    def _require_unchanged_snapshot(self) -> None:
        """Reject nested SchemaInfo mutation after the owner was constructed."""
        if type(self.schema_variants) is str:
            if self.schema_variants != "absent":
                _invalid_owner_profile()
            current_keys: tuple[_SchemaKey, ...] = ("absent",)
        else:
            if type(self.schema_variants) is not tuple:
                _invalid_owner_profile()
            current_keys = tuple(sorted(_schema_key(schema) for schema in self.schema_variants))
        if current_keys != self._schema_keys:
            _invalid_owner_profile()

        snapshot_rules = self._payload_rules
        public_rules = self.payload_schema_version_by_manifest
        if type(snapshot_rules) is str:
            if snapshot_rules != "not_applicable":
                _invalid_owner_profile()
            if type(public_rules) is not str or public_rules != "not_applicable":
                _invalid_owner_profile()
            return
        normalized_snapshot_rules = _normalize_payload_version_rules(snapshot_rules, current_keys)
        normalized_public_rules = _normalize_payload_version_rules(public_rules, current_keys)
        if normalized_snapshot_rules != normalized_public_rules:
            _invalid_owner_profile()


@dataclass(frozen=True, slots=True)
class CoreOwnedModelRead(Generic[_ModelT]):
    """Return a typed Core value bound to its exact selected artifact profile.

    The selected ref and canonical profile are read facts. They do not claim who
    produced the bytes or whether downstream use is admissible or authoritative.
    """

    value: _ModelT
    artifact_ref: ArtifactRef
    canon_profile: CanonInfo


def _refuse(code: str) -> NoReturn:
    """Raise one stable refusal for an owner-bound read."""
    raise CanonicalProfileRefusalError(code)


def _profile_schema_key(schema: SchemaInfo | None) -> _SchemaKey:
    """Return a selected manifest's schema identity, preserving explicit absence."""
    if schema is None:
        return "absent"
    return _schema_key(schema)


def validate_owned_core_model_json_artifact(
    model: type[_ModelT],
    store: object,
    selector: object,
    *,
    expected_owner: CoreArtifactOwnerProfile,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> CoreOwnedModelRead[_ModelT]:
    """Validate a selected Core JSON artifact against its explicit owner contract.

    ``expected_owner`` must come from the defining producer contract or a typed
    workflow context. It must not be constructed from the selected manifest, ref,
    HTTP input, or another self-label. Matching this ABI is not producer
    authenticity, admissibility, or authority proof.

    Args:
        model: Strict Pydantic model used to validate the admitted payload.
        store: Core artifact store exposing raw selected-manifest reads.
        selector: Artifact ID or exact selected artifact reference.
        expected_owner: Explicit producer-owned kind, media, and schema contract.
        raw_payload_bytes: Optional caller-provided bytes, still checked against the
            selected artifact identity and canonical profile.
        manifest_profile_sha256: Optional exact selected manifest profile digest.

    Returns:
        The validated model, actual profile-bound Core reference, and parsed
        canonicalization profile.

    Raises:
        CanonicalProfileRefusalError: If the selected owner, schema, payload version,
            profile, or bytes do not satisfy the explicit contract.
        ValueError: If the caller supplies a malformed owner profile.
    """
    if type(expected_owner) is not CoreArtifactOwnerProfile:
        _refuse("canon_profile_owned_artifact_owner_invalid")
    expected_owner._require_unchanged_snapshot()
    if not isinstance(model, type) or not issubclass(model, BaseModel):
        _refuse("canon_profile_owned_artifact_model_invalid")
    if raw_payload_bytes is not None and type(raw_payload_bytes) is not bytes:
        _refuse("canon_profile_payload_bytes_invalid")
    if manifest_profile_sha256 is not None and (
        type(manifest_profile_sha256) is not str or not manifest_profile_sha256
    ):
        _refuse("canon_profile_selection_unverified")

    has_payload_schema_version = "schema_version" in model.model_fields
    payload_rules = expected_owner._payload_rules
    if type(payload_rules) is str:
        if payload_rules != "not_applicable":
            _refuse("canon_profile_owned_artifact_payload_version_relation_invalid")
        payload_version_relation_not_applicable = True
    elif type(payload_rules) is tuple:
        payload_version_relation_not_applicable = False
    else:
        _refuse("canon_profile_owned_artifact_payload_version_relation_invalid")
    if has_payload_schema_version == payload_version_relation_not_applicable:
        _refuse("canon_profile_owned_artifact_payload_version_relation_invalid")

    try:
        manifest, declaration = read_core_manifest_profile(
            store,
            selector,
            manifest_profile_sha256=manifest_profile_sha256,
        )
    except CanonicalProfileRefusalError:
        raise
    except (TypeError, ValueError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified") from exc
    if manifest.kind != expected_owner.kind:
        _refuse("canon_profile_owned_artifact_kind_mismatch")
    if manifest.media_type != expected_owner.media_type:
        _refuse("canon_profile_owned_artifact_media_type_mismatch")

    selected_schema_key = _profile_schema_key(manifest.artifact_schema)
    if selected_schema_key not in expected_owner._schema_keys:
        _refuse("canon_profile_owned_artifact_schema_mismatch")
    if declaration.status != "declared" or not isinstance(declaration.profile, CanonInfo):
        _refuse("canon_profile_not_verified")

    selected_ref = artifact_ref_for_manifest(manifest)
    selected_profile_sha256 = selected_ref.manifest_profile_sha256
    if selected_profile_sha256 is None or (
        manifest_profile_sha256 is not None and selected_profile_sha256 != manifest_profile_sha256
    ):
        _refuse("canon_profile_selection_unverified")

    typed_model = validate_core_model_json_artifact(
        model,
        store,
        selected_ref,
        raw_payload_bytes=raw_payload_bytes,
        manifest_profile_sha256=selected_profile_sha256,
    )
    if has_payload_schema_version:
        if type(payload_rules) is not tuple:
            _refuse("canon_profile_owned_artifact_payload_version_relation_invalid")
        payload_versions = dict(payload_rules)
        expected_payload_version = payload_versions[selected_schema_key]
        actual_payload_version = getattr(typed_model, "schema_version", None)
        if (
            type(actual_payload_version) is not str
            or actual_payload_version != expected_payload_version
        ):
            _refuse("canon_profile_owned_payload_schema_version_mismatch")

    return CoreOwnedModelRead(
        value=typed_model,
        artifact_ref=selected_ref.model_copy(deep=True),
        canon_profile=declaration.profile.model_copy(deep=True),
    )


__all__ = [
    "CoreArtifactOwnerProfile",
    "CoreOwnedModelRead",
    "validate_owned_core_model_json_artifact",
]
