"""Validate Core JSON against an explicit artifact-owner ABI.

An owner profile is supplied by the defining producer contract or typed workflow
context. It is never inferred from the selected manifest or a caller-provided
label. A successful read proves selected-view and payload conformity only; it
does not attest producer authenticity, admissibility, or authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from typing import Any, Generic, Literal, NoReturn, TypeVar, cast

from pydantic import BaseModel

from polisyos.common.canonical import (
    CanonicalResourceLimits,
    _admit_canon_spec,
    _bounded_canonical_encoding,
    _BoundedArtifactWriterContext,
    _issue_bounded_artifact_writer_context,
)
from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.canon import CanonSpec, CanonViolation
from polisyos.core.canon.canon_json import _CANONICAL_TYPES, CORE_V3_TAG_POLICY_ID

from ._manifest_lifecycle import ManifestLifecycle
from .canonical_profile import (
    CoreJsonArtifactBoundedRead,
    CoreJsonReadLimits,
    artifact_ref_for_manifest,
    decode_core_json_payload,
    read_core_json_artifact_bounded,
    read_core_manifest_profile,
    read_core_manifest_profile_bounded,
    validate_core_model_bounded_read,
    validate_core_model_json_artifact,
)
from .ids import ArtifactID
from .manifest import ArtifactManifest, ArtifactRef, CanonInfo, InputRef, ProducerInfo, SchemaInfo
from .protocol import CoreJSONArtifactBoundedMemberReader
from .write_contract import ArtifactWriteOptions

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


_WRITER_POLICY_TOKEN = object()
_PREPARED_WRITE_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class CoreJsonWriterPolicy(Generic[_ModelT]):
    """Code-owned policy for an explicitly requested local bounded writer cohort.

    Obtain this from the defining producer, never from a manifest or HTTP label.
    It appoints a representation and resource domain, not G acceptance or an
    installed-reader readiness fact. Admission recomputes current reader behavior.
    """

    policy_id: str
    producer_component: str
    owner: CoreArtifactOwnerProfile
    model: type[_ModelT]
    spec: CanonSpec
    limits: CanonicalResourceLimits
    read_limits: CoreJsonReadLimits
    input_contracts: tuple[tuple[str, str, str], ...]
    value_limits: tuple[str, int, int, int]
    _identity: tuple[object, ...]
    _token: object


def _writer_refuse(code: str) -> NoReturn:
    raise CanonicalProfileRefusalError(code)


def _plain_writer_model(model: type[BaseModel]) -> None:
    """Admit the actual plain DTO domain; do not substitute generic raw fields."""
    if type(model) is not type(BaseModel) or not issubclass(model, BaseModel):
        _writer_refuse("core_json_writer_model_unqualified")
    overrides = {
        "__init__",
        "__new__",
        "model_validate",
        "model_post_init",
        "__get_pydantic_core_schema__",
        "__getattribute__",
        "__getattr__",
    }
    for ancestor in type.__getattribute__(model, "__mro__"):
        if ancestor is BaseModel:
            break
        if overrides.intersection(type.__getattribute__(ancestor, "__dict__")):
            _writer_refuse("core_json_writer_model_callbacks_unqualified")
    allowed_schema_nodes = {
        "model",
        "model-fields",
        "model-field",
        "default",
        "str",
        "dict",
        "any",
        "literal",
        "int",
        "bool",
        "float",
        "nullable",
        "list",
        "union",
        "none",
    }
    root_schema = model.__pydantic_core_schema__
    if type(root_schema) is not dict or root_schema.get("type") != "model":
        _writer_refuse("core_json_writer_model_domain_unqualified")
    pending = [root_schema]
    while pending:
        node = pending.pop()
        if type(node) is dict:
            kind = node.get("type")
            # This is the primitive DTO domain. Nested/recursive model graphs
            # are unqualified, including every constructor/post-init branch;
            # no per-child callback allowlist can confer admission.
            if kind == "model" and (
                node is not root_schema
                or node.get("cls") is not model
                or node.get("custom_init") not in (None, False)
                or node.get("post_init") not in (None, False)
            ):
                _writer_refuse("core_json_writer_model_domain_unqualified")
            if type(kind) is str and kind not in allowed_schema_nodes:
                _writer_refuse("core_json_writer_model_callbacks_unqualified")
            if node.get("default_factory") is not None:
                _writer_refuse("core_json_writer_model_callbacks_unqualified")
            if kind == "literal" and any(
                item is not None and type(item) not in (str, bool, int, float)
                for item in node.get("expected", ())
            ):
                _writer_refuse("core_json_writer_model_callbacks_unqualified")
            pending.extend(item for item in node.values() if type(item) in (dict, list, tuple))
        elif type(node) in (list, tuple):
            pending.extend(node)
    decorators = model.__pydantic_decorators__
    if (
        model.model_config.get("extra") != "forbid"
        or model.model_computed_fields
        or any(
            getattr(decorators, name)
            for name in (
                "field_validators",
                "model_validators",
                "field_serializers",
                "model_serializers",
            )
        )
        or any(
            item.alias is not None
            or item.validation_alias is not None
            or item.serialization_alias is not None
            or item.exclude not in (None, False)
            or item.exclude_if is not None
            for item in model.model_fields.values()
        )
    ):
        _writer_refuse("core_json_writer_model_callbacks_unqualified")


def _writer_policy_identity(policy: CoreJsonWriterPolicy[Any]) -> tuple[object, ...]:
    policy.owner._require_unchanged_snapshot()
    return (
        policy.policy_id,
        policy.producer_component,
        policy.owner.kind,
        policy.owner.media_type,
        policy.owner._schema_keys,
        policy.owner._payload_rules,
        id(policy.model),
        tuple(getattr(policy.spec, item.name) for item in fields(CanonSpec)),
        (
            policy.limits.policy_id,
            policy.limits.max_wire_bytes,
            policy.limits.max_wire_depth,
            policy.limits.max_elements,
        ),
        (
            policy.read_limits.max_bytes,
            policy.read_limits.max_depth,
            policy.read_limits.max_elements,
            policy.read_limits.max_manifest_bytes,
        ),
        policy.input_contracts,
        policy.value_limits,
    )


def _writer_metadata_preflight(value: object, max_bytes: int) -> None:
    """Bound real primitive metadata before full JSON buffer materialization."""
    _bounded_canonical_encoding(
        value,
        CanonSpec(),
        CanonicalResourceLimits("core_json_writer.metadata.preflight", max_bytes, 4, max_bytes),
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
        _preflight_only=True,
    )


def declare_core_json_writer_policy(
    *,
    owner: CoreArtifactOwnerProfile,
    model: type[_ModelT],
    spec: CanonSpec,
    producer_component: str,
    limits: CanonicalResourceLimits,
    read_limits: CoreJsonReadLimits,
    input_contracts: tuple[tuple[str, str, str], ...],
    value_limits: tuple[str, int, int, int],
) -> CoreJsonWriterPolicy[_ModelT]:
    """Declare a real producer's policy; this is not a ready/activation flag.

    Only callback-free plain DTOs and exact primitive projections are supported.
    The defining producer supplies this trusted context, as with Core's existing
    read-owner profile. Callers cannot infer appointment from stored declarations.
    """
    if (
        type(owner) is not CoreArtifactOwnerProfile
        or type(owner.kind) is not str
        or type(owner.media_type) is not str
        or type(owner._schema_keys) is not tuple
        or any(
            type(key) is not tuple or len(key) != 2 or any(type(part) is not str for part in key)
            for key in owner._schema_keys
        )
    ):
        _writer_refuse("core_json_writer_owner_invalid")
    if type(producer_component) is not str or not producer_component:
        _writer_refuse("core_json_writer_producer_context_invalid")
    if type(limits) is not CanonicalResourceLimits or type(read_limits) is not CoreJsonReadLimits:
        _writer_refuse("core_json_writer_resource_policy_missing")
    manifest_cap = read_limits.max_manifest_bytes
    if type(manifest_cap) is not int or manifest_cap < 1:
        _writer_refuse("core_json_writer_resource_policy_invalid")
    if (
        len(owner._schema_keys) != 1
        or type(input_contracts) is not tuple
        or not input_contracts
        or len(input_contracts) > manifest_cap
        or any(
            type(row) is not tuple
            or len(row) != 3
            or any(type(part) is not str or not part for part in row)
            for row in input_contracts
        )
    ):
        _writer_refuse("core_json_writer_metadata_domain_unqualified")
    selected = _admit_canon_spec(spec, CanonSpec, violation_type=CanonViolation)
    # All variable source labels and actual repeated roles are charged before
    # frozen copies, input/model projections or ManifestLifecycle serialization.
    _writer_metadata_preflight(
        {
            "kind": owner.kind,
            "media_type": owner.media_type,
            "schema_keys": owner._schema_keys,
            "payload_rules": owner._payload_rules,
            "producer_component": producer_component,
            "policy_id": limits.policy_id,
            "canon": {item.name: getattr(selected, item.name) for item in fields(CanonSpec)},
            "input_contracts": input_contracts,
        },
        manifest_cap,
    )
    owner._require_unchanged_snapshot()
    owner = CoreArtifactOwnerProfile(
        kind=owner.kind,
        media_type=owner.media_type,
        schema_variants=owner.schema_variants,
        payload_schema_version_by_manifest=owner.payload_schema_version_by_manifest,
    )
    _plain_writer_model(model)
    if selected.name != "polisyos.canon.json" or selected.version != "0.3.0":
        _writer_refuse("core_json_writer_profile_unqualified")
    if type(limits) is not CanonicalResourceLimits or type(read_limits) is not CoreJsonReadLimits:
        _writer_refuse("core_json_writer_resource_policy_missing")
    frozen_limits = CanonicalResourceLimits(
        limits.policy_id, limits.max_wire_bytes, limits.max_wire_depth, limits.max_elements
    )
    frozen_read = CoreJsonReadLimits(
        read_limits.max_bytes,
        read_limits.max_depth,
        read_limits.max_elements,
        read_limits.max_manifest_bytes,
    )
    if (
        (frozen_read.max_bytes, frozen_read.max_depth, frozen_read.max_elements)
        != (frozen_limits.max_wire_bytes, frozen_limits.max_wire_depth, frozen_limits.max_elements)
        or type(input_contracts) is not tuple
        or not input_contracts
        or any(
            type(row) is not tuple
            or len(row) != 3
            or any(type(value) is not str or not value for value in row)
            for row in input_contracts
        )
        or len({row[0] for row in input_contracts}) != len(input_contracts)
    ):
        _writer_refuse("core_json_writer_resource_policy_invalid")
    if (
        type(value_limits) is not tuple
        or len(value_limits) != 4
        or type(value_limits[0]) is not str
        or value_limits[0] not in model.model_fields
        or any(type(item) is not int for item in value_limits[1:])
        or value_limits[1] < 1
        or value_limits[2] < 0
        or value_limits[3] < 1
    ):
        _writer_refuse("core_json_writer_value_domain_invalid")
    expected_schema = (
        getattr(model, "ARTIFACT_SCHEMA_NAME", None),
        getattr(model, "ARTIFACT_SCHEMA_VERSION", None),
    )
    if (
        owner.kind != getattr(model, "ARTIFACT_KIND", None)
        or owner.media_type != getattr(model, "ARTIFACT_MEDIA_TYPE", None)
        or owner._schema_keys != (expected_schema,)
    ):
        _writer_refuse("core_json_writer_owner_model_mismatch")
    result = object.__new__(CoreJsonWriterPolicy)
    for name, value in {
        "policy_id": frozen_limits.policy_id,
        "producer_component": producer_component,
        "owner": owner,
        "model": model,
        "spec": selected,
        "limits": frozen_limits,
        "read_limits": frozen_read,
        "input_contracts": input_contracts,
        "value_limits": value_limits,
        "_token": _WRITER_POLICY_TOKEN,
    }.items():
        object.__setattr__(result, name, value)
    object.__setattr__(result, "_identity", _writer_policy_identity(result))
    return result


def _require_writer_policy(policy: object) -> CoreJsonWriterPolicy[Any]:
    if (
        type(policy) is not CoreJsonWriterPolicy
        or getattr(policy, "_token", None) is not _WRITER_POLICY_TOKEN
        or type(policy._identity) is not tuple
    ):
        _writer_refuse("core_json_writer_policy_unbound_or_changed")
    # Reuse the same source-policy validation instead of trusting a mutable
    # dataclass field or its prior marker. All compared identity values are
    # validated primitive snapshots, including the actual model identity.
    current = declare_core_json_writer_policy(
        owner=policy.owner,
        model=policy.model,
        spec=policy.spec,
        producer_component=policy.producer_component,
        limits=policy.limits,
        read_limits=policy.read_limits,
        input_contracts=policy.input_contracts,
        value_limits=policy.value_limits,
    )
    if current._identity != policy._identity:
        _writer_refuse("core_json_writer_policy_unbound_or_changed")
    return current


def _primitive_identity(value: object) -> object:
    """Freeze exact primitive value/type identity after physical admission."""
    if type(value) is dict:
        return (
            "dict",
            tuple((key, _primitive_identity(item)) for key, item in sorted(value.items())),
        )
    if type(value) is list:
        return ("list", tuple(_primitive_identity(item) for item in value))
    if value is None or type(value) in (bool, int, float, str):
        # Generic canonical floats retain their historical zero normalization.
        return (type(value), value)
    _writer_refuse("core_json_writer_projection_unqualified")


def _require_writer_value_domain(
    policy: CoreJsonWriterPolicy[Any], snapshot: dict[str, object]
) -> None:
    member, max_nodes, max_depth, max_integer_bits = policy.value_limits
    value = snapshot.get(member)
    if type(value) is not dict:
        _writer_refuse("core_json_writer_value_domain_invalid")
    # The Common snapshot is already physically bounded and callback-free. This
    # retains the producer's separate logical value domain; it is not a renamed
    # wire-node or byte budget.
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > max_nodes or depth > max_depth:
            _writer_refuse("core_json_writer_value_domain_exceeded")
        if type(item) is int and item.bit_length() > max_integer_bits:
            _writer_refuse("core_json_writer_value_domain_exceeded")
        if type(item) is dict:
            if any(type(key) is not str or not key for key in item):
                _writer_refuse("core_json_writer_value_domain_invalid")
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)


def _validate_writer_model_value(policy: CoreJsonWriterPolicy[_ModelT], value: object) -> _ModelT:
    _plain_writer_model(policy.model)
    typed = policy.model.model_validate(value, strict=True)
    rules = policy.owner._payload_rules
    if type(rules) is tuple:
        expected = dict(rules)[policy.owner._schema_keys[0]]
        actual = getattr(typed, "schema_version", None)
        if type(actual) is not str or actual != expected:
            _writer_refuse("core_json_writer_payload_version_mismatch")
    elif "schema_version" in policy.model.model_fields:
        _writer_refuse("core_json_writer_payload_version_relation_invalid")
    return typed


def _snapshot_writer_input(
    ref: object, role: str, kind: str, media_type: str
) -> tuple[str, str, str]:
    """Copy only native stored ref fields, bypassing caller getters/serializers."""
    mro = type.__getattribute__(type(ref), "__mro__")
    if not any(base is ArtifactRef for base in mro):
        _writer_refuse("core_json_writer_input_owner_mismatch")
    try:
        storage = BaseModel.__dict__["__dict__"].__get__(ref, type(ref))
    except (AttributeError, TypeError) as exc:
        raise CanonicalProfileRefusalError("core_json_writer_input_owner_mismatch") from exc
    if type(storage) is not dict or set(storage) != set(ArtifactRef.model_fields):
        _writer_refuse("core_json_writer_input_owner_mismatch")
    aid, actual_kind, actual_media, profile = (
        storage["artifact_id"],
        storage["kind"],
        storage["media_type"],
        storage["manifest_profile_sha256"],
    )
    if (
        type(aid) is not ArtifactID
        or type(actual_kind) is not str
        or type(actual_media) is not str
        or type(profile) is not str
        or actual_kind != kind
        or actual_media != media_type
        or re.fullmatch(r"sha256:[0-9a-f]{64}", profile) is None
    ):
        _writer_refuse("core_json_writer_input_owner_mismatch")
    aid_storage = BaseModel.__dict__["__dict__"].__get__(aid, ArtifactID)
    root = aid_storage.get("root") if type(aid_storage) is dict else None
    if type(root) is not str or re.fullmatch(r"sha256:[0-9a-f]{64}", root) is None:
        _writer_refuse("core_json_writer_input_owner_mismatch")
    return root, role, profile


def _require_unshadowed_owner_methods(owner: object) -> None:
    """Refuse instance dispatch substitutions generically over the real owner ABI."""
    for name in vars(owner):
        if type(name) is not str:
            _writer_refuse("core_json_writer_backend_callbacks_unqualified")
        for base in type.__getattribute__(type(owner), "__mro__"):
            declared = type.__getattribute__(base, "__dict__").get(name)
            if callable(declared) or isinstance(declared, (classmethod, staticmethod)):
                _writer_refuse("core_json_writer_backend_callbacks_unqualified")


def _require_local_writer_backend(store: object) -> Any:
    from pathlib import Path

    from ._atomic_write import AtomicFileWriter
    from ._layout import CASPathLayout
    from .ownership import ArtifactOwnershipIndex, _RootTransactionCoordinator
    from .signing import SigningConfig
    from .store import FileSystemCAS

    if (
        type(store) is not FileSystemCAS
        or store._read_only is not False
        or store._ownership_enforced is not False
        or store._storage_admission is not None
        or type(store._signing_config) is not SigningConfig
        or store._signing_config.enabled is not False
        or store._hpc_enabled is not False
        or store._tracer is not None
        or store._metrics is not None
        or type(store._files) is not AtomicFileWriter
        or type(store._layout) is not CASPathLayout
        or type(store.root) is not type(Path("."))
        or type(store.base) is not type(Path("."))
        or type(store._layout.root) is not type(Path("."))
        or type(store._layout.base) is not type(Path("."))
        or store._layout.base != store.base
        or type(store._manifests) is not ManifestLifecycle
        or vars(store._manifests)
        or type(store._ownership_index) is not ArtifactOwnershipIndex
        or type(store._coordinator) is not _RootTransactionCoordinator
        or store._ownership_index._coordinator is not store._coordinator
        or type(store._ownership_index.root) is not type(Path("."))
        or type(store._coordinator.root) is not type(Path("."))
        or store._layout.root != store.root
        or store._coordinator.root != store.root
        or store._ownership_index.root != store.root
    ):
        _writer_refuse("core_json_writer_backend_unqualified")
    for owner in (
        store,
        store._manifests,
        store._files,
        store._layout,
        store._ownership_index,
        store._coordinator,
    ):
        _require_unshadowed_owner_methods(owner)
    return store


@dataclass(frozen=True, slots=True, init=False)
class _PreparedCoreJsonWrite:
    """Private sealed representation; never reconstruct this from persisted data."""

    policy: CoreJsonWriterPolicy[Any]
    store_identity: object
    data: bytes
    context: _BoundedArtifactWriterContext
    input_fields: tuple[tuple[str, str, str], ...]
    value_identity: object
    token: object
    seal: tuple[object, ...]


def _prepared_write_options(prepared: _PreparedCoreJsonWrite) -> ArtifactWriteOptions:
    policy = _require_writer_policy(prepared.policy)
    schema_name, schema_version = policy.owner._schema_keys[0]
    return ArtifactWriteOptions(
        kind=policy.owner.kind,
        media_type=policy.owner.media_type,
        schema=SchemaInfo(name=schema_name, version=schema_version),
        canon=CanonInfo.from_spec(policy.spec),
        producer=ProducerInfo(component=policy.producer_component, version=policy.policy_id),
        inputs=[
            InputRef(
                artifact_id=ArtifactID.model_validate(aid),
                role=role,
                manifest_profile_sha256=profile,
            )
            for aid, role, profile in prepared.input_fields
        ],
    )


def _prepared_write_identity(prepared: _PreparedCoreJsonWrite) -> tuple[object, ...]:
    return (
        prepared.policy._identity,
        prepared.store_identity,
        hashlib.sha256(prepared.data).hexdigest(),
        prepared.input_fields,
        prepared.value_identity,
        prepared.context.spec_fields,
        prepared.context.limit_fields,
    )


def _validate_prepared_core_json_write(
    store: object, prepared: _PreparedCoreJsonWrite
) -> ArtifactWriteOptions:
    if (
        type(prepared) is not _PreparedCoreJsonWrite
        or getattr(prepared, "token", None) is not _PREPARED_WRITE_TOKEN
        or prepared.store_identity is not store
        or type(prepared.data) is not bytes
    ):
        _writer_refuse("core_json_writer_preparation_unverified")
    _require_local_writer_backend(store)
    policy = _require_writer_policy(prepared.policy)
    _admit_canon_spec(
        policy.spec,
        CanonSpec,
        violation_type=CanonViolation,
        artifact_writer=True,
        _artifact_writer_context=prepared.context,
    )
    if (
        prepared.seal != _prepared_write_identity(prepared)
        or len(prepared.data) > prepared.context.limits.max_wire_bytes
        or prepared.context.limits.max_wire_bytes > policy.limits.max_wire_bytes
    ):
        _writer_refuse("core_json_writer_payload_limit")
    return _prepared_write_options(prepared)


def _preflight_prepared_core_json_manifest(
    store: object,
    prepared: _PreparedCoreJsonWrite,
    manifest: ArtifactManifest,
) -> None:
    """Preflight the actual source manifest projection before its serializer."""
    _validate_prepared_core_json_write(store, prepared)
    if type(manifest) is not ArtifactManifest:
        _writer_refuse("core_json_writer_manifest_owner_mismatch")
    _writer_metadata_preflight(
        manifest.model_dump(mode="json", by_alias=True, exclude_none=True),
        prepared.policy.read_limits.max_manifest_bytes,
    )


def _validate_prepared_core_json_manifest(
    store: object, prepared: _PreparedCoreJsonWrite, manifest: ArtifactManifest, raw_manifest: bytes
) -> None:
    """Recompute owner/profile/value on the actual bytes before CAS publication."""
    options = _validate_prepared_core_json_write(store, prepared)
    policy = prepared.policy
    if type(manifest) is not ArtifactManifest:
        _writer_refuse("core_json_writer_manifest_owner_mismatch")
    if type(raw_manifest) is not bytes or len(raw_manifest) > policy.read_limits.max_manifest_bytes:
        _writer_refuse("core_json_writer_manifest_limit")
    if (
        manifest.kind != policy.owner.kind
        or manifest.media_type != policy.owner.media_type
        or _profile_schema_key(manifest.artifact_schema) not in policy.owner._schema_keys
        or manifest.canon != options.canon
        or manifest.inputs != options.inputs
        or manifest.producer != options.producer
        or manifest.env is not None
        or manifest.governance is not None
        or manifest.tenant_context is not None
        or manifest.same_input_closure is not None
        or manifest.authority is not None
        or manifest.warnings
        or manifest.byte_size != len(prepared.data)
        or type(manifest.artifact_id) is not ArtifactID
        or manifest.artifact_id.root != "sha256:" + hashlib.sha256(prepared.data).hexdigest()
        or manifest.integrity.sha256 != hashlib.sha256(prepared.data).hexdigest()
    ):
        _writer_refuse("core_json_writer_manifest_owner_mismatch")
    read = decode_core_json_payload(raw_manifest, prepared.data)
    if (
        read.status != "declared_bytes_conformant"
        or read.reader_policy_id != CORE_V3_TAG_POLICY_ID
        or _primitive_identity(read.value) != prepared.value_identity
    ):
        _writer_refuse("core_json_writer_reader_not_conformant")
    _validate_writer_model_value(policy, read.value)


def _require_writer_read_manifest(
    policy: CoreJsonWriterPolicy[Any], manifest: ArtifactManifest
) -> None:
    if (
        manifest.kind != policy.owner.kind
        or manifest.media_type != policy.owner.media_type
        or _profile_schema_key(manifest.artifact_schema) not in policy.owner._schema_keys
        or manifest.canon != CanonInfo.from_spec(policy.spec)
        or manifest.manifest_schema_version != "v3"
        or tuple(edge.role for edge in manifest.inputs)
        != tuple(row[0] for row in policy.input_contracts)
        or any(
            type(edge.manifest_profile_sha256) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", edge.manifest_profile_sha256) is None
            for edge in manifest.inputs
        )
        or manifest.producer
        != ProducerInfo(component=policy.producer_component, version=policy.policy_id)
        or manifest.env is not None
        or manifest.governance is not None
        or manifest.tenant_context is not None
        or manifest.same_input_closure is not None
        or manifest.authority is not None
        or manifest.warnings
    ):
        _writer_refuse("core_json_writer_read_owner_or_profile_mismatch")


def read_core_json_writer_artifact_bounded(
    store: object,
    ref: ArtifactRef,
    *,
    policy: CoreJsonWriterPolicy[_ModelT],
    max_bytes: int | None = None,
) -> CoreJsonArtifactBoundedRead:
    """Read the exact source-owned artifact independently of writer activation.

    Read-only bounded backend ports are sufficient here. This returns Core's
    sealed bounded view after full owner/profile/domain/typed validation; it
    does not attest that the actual producer used the writing API.
    """
    admitted = cast("CoreJsonWriterPolicy[_ModelT]", _require_writer_policy(policy))
    limit = admitted.read_limits.max_bytes if max_bytes is None else max_bytes
    if type(limit) is not int or not 0 < limit <= admitted.read_limits.max_bytes:
        _writer_refuse("core_json_writer_read_limit_invalid")
    aid, _role, selected_profile = _snapshot_writer_input(
        ref, "selected_output", admitted.owner.kind, admitted.owner.media_type
    )
    ref = ArtifactRef(
        artifact_id=ArtifactID.model_validate(aid),
        kind=admitted.owner.kind,
        media_type=admitted.owner.media_type,
        manifest_profile_sha256=selected_profile,
    )
    reader = cast("CoreJSONArtifactBoundedMemberReader", store)
    read = read_core_manifest_profile_bounded(
        reader, ref, max_manifest_bytes=admitted.read_limits.max_manifest_bytes
    )
    _require_writer_read_manifest(admitted, read.manifest)
    limits = CoreJsonReadLimits(
        limit,
        admitted.read_limits.max_depth,
        admitted.read_limits.max_elements,
        admitted.read_limits.max_manifest_bytes,
    )
    bounded = read_core_json_artifact_bounded(reader, ref, limits=limits, manifest_read=read)
    value = bounded.value
    if type(value) is not dict or set(value) != set(admitted.model.model_fields):
        _writer_refuse("core_json_writer_model_fields_incomplete")
    _primitive_identity(value)
    _require_writer_value_domain(admitted, value)
    _validate_writer_model_value(admitted, value)
    validate_core_model_bounded_read(admitted.model, bounded)
    return bounded


def put_core_json_artifact_bounded(
    store: object,
    value: object,
    *,
    policy: CoreJsonWriterPolicy[_ModelT],
    inputs: tuple[ArtifactRef, ...],
    max_bytes: int | None = None,
) -> tuple[CoreOwnedModelRead[_ModelT], int]:
    """Produce one explicit local source-owned `.3` artifact with actual readback.

    The ordinary JSON writer stays fenced. An explicit policy request is not a
    ready flag: actual source/domain/vector/reader behavior is recomputed before
    publication. Installed/other backend/whole-package activation is not claimed.
    """
    admitted = cast("CoreJsonWriterPolicy[_ModelT]", _require_writer_policy(policy))
    store = _require_local_writer_backend(store)
    if type(inputs) is not tuple or len(inputs) != len(admitted.input_contracts):
        _writer_refuse("core_json_writer_inputs_unbound")
    input_fields: list[tuple[str, str, str]] = []
    for ref, (role, kind, media_type) in zip(inputs, admitted.input_contracts, strict=True):
        input_fields.append(_snapshot_writer_input(ref, role, kind, media_type))
    limit = admitted.limits.max_wire_bytes if max_bytes is None else max_bytes
    if type(limit) is not int or not 0 < limit <= admitted.limits.max_wire_bytes:
        _writer_refuse("core_json_writer_remaining_capacity_invalid")
    limits = CanonicalResourceLimits(
        admitted.policy_id, limit, admitted.limits.max_wire_depth, admitted.limits.max_elements
    )
    context = _issue_bounded_artifact_writer_context(admitted.spec, limits)
    selected = _admit_canon_spec(
        admitted.spec,
        CanonSpec,
        violation_type=CanonViolation,
        artifact_writer=True,
        _artifact_writer_context=context,
    )
    data, snapshot = _bounded_canonical_encoding(
        value,
        selected,
        limits,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
        _primitive_json_only=True,
    )
    if type(snapshot) is not dict or set(snapshot) != set(admitted.model.model_fields):
        _writer_refuse("core_json_writer_model_fields_incomplete")
    _require_writer_value_domain(admitted, snapshot)
    _validate_writer_model_value(admitted, snapshot)
    prepared = object.__new__(_PreparedCoreJsonWrite)
    for name, item in {
        "policy": admitted,
        "store_identity": store,
        "data": data,
        "context": context,
        "input_fields": tuple(input_fields),
        "value_identity": _primitive_identity(snapshot),
        "token": _PREPARED_WRITE_TOKEN,
    }.items():
        object.__setattr__(prepared, name, item)
    object.__setattr__(prepared, "seal", _prepared_write_identity(prepared))
    options = _validate_prepared_core_json_write(store, prepared)
    manifest = store._manifests.build(
        artifact_id=ArtifactID.from_sha256_hex(hashlib.sha256(data).hexdigest()),
        data=data,
        sha=hashlib.sha256(data).hexdigest(),
        opts=options,
        created_at=datetime.max.replace(tzinfo=UTC),
    )
    _preflight_prepared_core_json_manifest(store, prepared, manifest)
    _validate_prepared_core_json_manifest(
        store, prepared, manifest, store._manifests.to_bytes(manifest)
    )
    ref = store._put_bounded_core_json_write(prepared)
    bounded = read_core_json_writer_artifact_bounded(store, ref, policy=admitted)
    if _primitive_identity(bounded.value) != prepared.value_identity:
        _writer_refuse("core_json_writer_readback_value_mismatch")
    typed = validate_core_model_bounded_read(admitted.model, bounded)
    canon = bounded.manifest.canon
    if type(canon) is not CanonInfo:
        _writer_refuse("core_json_writer_readback_profile_missing")
    return CoreOwnedModelRead(
        value=typed, artifact_ref=ref, canon_profile=canon.model_copy(deep=True)
    ), len(data)


__all__ = [
    "CoreArtifactOwnerProfile",
    "CoreJsonWriterPolicy",
    "CoreOwnedModelRead",
    "declare_core_json_writer_policy",
    "put_core_json_artifact_bounded",
    "read_core_json_writer_artifact_bounded",
    "validate_owned_core_model_json_artifact",
]
