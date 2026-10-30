"""Typed contracts that describe how IR payloads cross the artifact-store boundary."""

from __future__ import annotations

import ast
import builtins as _builtins
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import Field as DataclassField
from dataclasses import asdict, dataclass, fields, is_dataclass
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Protocol,
    get_args,
    get_origin,
    runtime_checkable,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    WithJsonSchema,
    field_validator,
)

from polisyos.ir.model_layer.canon import CanonViolation

if TYPE_CHECKING:
    from polisyos.ir.migrations.base import IRRepresentationRegistration, ResolvedSchemaAdmission
    from polisyos.ir.model_layer.canon import CanonSpec

_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")


_TRUSTED_ARTIFACT_REF_FACADE_EXTRACTORS: dict[type[object], Callable[[object], object]] = {}


def _register_trusted_artifact_ref_facade(
    facade_type: type[object],
    extractor: Callable[[object], object],
) -> None:
    """Register one exact code-owned facade type and its raw model extractor."""
    if type(facade_type) is not type or not callable(extractor):
        raise TypeError("Artifact reference facade registration is malformed")
    existing = _TRUSTED_ARTIFACT_REF_FACADE_EXTRACTORS.get(facade_type)
    if existing is not None and existing is not extractor:
        raise ValueError("Artifact reference facade type already has another extractor")
    _TRUSTED_ARTIFACT_REF_FACADE_EXTRACTORS[facade_type] = extractor


def _is_pydantic_model_instance(value: object) -> bool:
    """Identify actual Pydantic model storage without honoring a class view."""
    try:
        actual_mro = type.__getattribute__(type(value), "__mro__")
    except (AttributeError, TypeError):
        return False
    return BaseModel in actual_mro


def _reject_unbacked_pydantic_class_view(value: object) -> None:
    """Reject a class view that claims Pydantic storage absent from the physical type."""
    if _is_pydantic_model_instance(value):
        return
    try:
        claims_pydantic_model = isinstance(value, BaseModel)
    except Exception as exc:
        raise TypeError("Artifact reference class view is malformed") from exc
    if claims_pydantic_model:
        raise TypeError(
            "Artifact reference class view claims Pydantic model without actual Pydantic storage"
        )


def _trusted_artifact_ref_facade_target(value: object) -> object | None:
    """Resolve an exact code-registered facade to its underlying Pydantic model."""
    extractor = _TRUSTED_ARTIFACT_REF_FACADE_EXTRACTORS.get(type(value))
    if extractor is None:
        return None
    try:
        target = extractor(value)
    except Exception as exc:
        raise TypeError("Artifact reference facade could not expose its model snapshot") from exc
    if not _is_pydantic_model_instance(target):
        raise TypeError("Artifact reference facade must resolve to an actual Pydantic model")
    return target


_ARTIFACT_ID_VALIDATION_SCHEMA_PATTERN = r"^[0-9A-Fa-f]{64}$"
_ARTIFACT_ID_SERIALIZATION_SCHEMA_PATTERN = r"^[0-9a-f]{64}$"


def _add_artifact_id_json_schema_constraints(schema: dict[str, Any], model: type[Any]) -> None:
    """Bind schema-only wire grammar to the owning ArtifactID prefix."""
    schema_pattern = schema.get("pattern")
    if schema_pattern == _ARTIFACT_ID_VALIDATION_SCHEMA_PATTERN:
        hex_pattern = "[0-9A-Fa-f]"
    elif schema_pattern == _ARTIFACT_ID_SERIALIZATION_SCHEMA_PATTERN:
        hex_pattern = "[0-9a-f]"
    else:
        raise ValueError("ArtifactID JSON Schema is missing its typed wire marker")

    prefix = _builtins.str.__str__(model.prefix)
    wire_length = _builtins.len(prefix) + 64
    schema.update(
        {
            "pattern": f"^{re.escape(prefix)}{hex_pattern}{{64}}$",
            "minLength": wire_length,
            "maxLength": wire_length,
        }
    )


def _is_schema_only_string_annotation(annotation: object) -> bool:
    """Recognize string annotations carrying JSON Schema metadata only."""
    if annotation is str:
        return True
    if get_origin(annotation) is not Annotated:
        return False
    arguments = get_args(annotation)
    return (
        len(arguments) > 1
        and arguments[0] is str
        and all(type(metadata) is WithJsonSchema for metadata in arguments[1:])
    )


def _is_string_root_model(value: object) -> bool:
    """Return whether a value is a Pydantic scalar root whose only field is ``str``."""
    model_fields = getattr(type(value), "model_fields", None)
    root_field = model_fields.get("root") if isinstance(model_fields, Mapping) else None
    return (
        _is_pydantic_model_instance(value)
        and getattr(type(value), "__pydantic_root_model__", False) is True
        and isinstance(model_fields, Mapping)
        and set(model_fields) == {"root"}
        and _is_schema_only_string_annotation(getattr(root_field, "annotation", None))
    )


def _normalize_scalar_artifact_id(value: object) -> ArtifactID:
    """Normalize a string ID, native IR ID, or exact scalar root-model ID."""
    facade_target = _trusted_artifact_ref_facade_target(value)
    if facade_target is not None:
        value = facade_target
    if isinstance(value, str):
        return ArtifactID.model_validate(value)
    if _is_pydantic_model_instance(value) and isinstance(value, ArtifactID):
        return value
    if not _is_string_root_model(value):
        raise TypeError("Artifact ID selector must be a string scalar")
    original_snapshot = _string_root_model_snapshot(value)
    stored_id = ArtifactID.model_validate(original_snapshot[0])
    model_dump = getattr(value, "model_dump", None)
    if _string_root_model_snapshot(value) != original_snapshot:
        raise TypeError("Artifact ID root model changed during projection lookup")
    if not callable(model_dump):
        raise TypeError("Artifact ID root model must expose model_dump()")
    dumped = model_dump(mode="python")
    if _string_root_model_snapshot(value) != original_snapshot:
        raise TypeError("Artifact ID root model changed during projection")
    if type(dumped) is not str:
        raise TypeError("Artifact ID root model projection must be a native string")
    projected_id = ArtifactID.model_validate(dumped)
    if projected_id.root != stored_id.root:
        raise TypeError("Artifact ID root model projection changed its stored root")
    return stored_id


class ArtifactID(
    RootModel[
        Annotated[
            str,
            WithJsonSchema(
                {
                    "type": "string",
                    "pattern": _ARTIFACT_ID_VALIDATION_SCHEMA_PATTERN,
                    "minLength": 64,
                    "maxLength": 64,
                },
                mode="validation",
            ),
            WithJsonSchema(
                {
                    "type": "string",
                    "pattern": _ARTIFACT_ID_SERIALIZATION_SCHEMA_PATTERN,
                    "minLength": 64,
                    "maxLength": 64,
                },
                mode="serialization",
            ),
        ]
    ]
):
    """IR-local artifact ID model compatible with CAS interfaces."""

    model_config = ConfigDict(json_schema_extra=_add_artifact_id_json_schema_constraints)

    prefix: ClassVar[str] = "sha256:"

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value: object) -> str:
        if not isinstance(value, str):
            value = str(value)
        # str() may return a str subclass on Python 3.14; normalize its native payload.
        value = _builtins.str.__str__(value)
        prefix = _builtins.str.__str__(cls.prefix)
        if not value.startswith(prefix):
            raise ValueError("ArtifactID must start with sha256:")
        hex64 = value[_builtins.len(prefix) :].lower()
        if not _SHA256_HEX_RE.fullmatch(hex64):
            raise ValueError("sha256 hex must be 64 lowercase characters [0-9a-f]")
        return f"{prefix}{hex64}"

    @classmethod
    def from_sha256_hex(cls, hex64: str) -> ArtifactID:
        if isinstance(hex64, str):
            hex64 = _builtins.str.__str__(hex64)
        hex64 = hex64.lower()
        if isinstance(hex64, str):
            # Preserve external .lower() callbacks while normalizing their subclass result.
            hex64 = _builtins.str.__str__(hex64)
        if not _SHA256_HEX_RE.fullmatch(hex64):
            raise ValueError("sha256 hex must be 64 characters [0-9a-f]")
        prefix = _builtins.str.__str__(cls.prefix)
        return cls(f"{prefix}{hex64}")

    @property
    def hex(self) -> str:
        algo, hex64 = self.root.split(":", 1)
        if algo != "sha256":
            raise ValueError(f"Unsupported algo: {algo}")
        if not _SHA256_HEX_RE.fullmatch(hex64):
            raise ValueError("Invalid sha256 hex")
        return hex64

    def __str__(self) -> str:
        return self.root


class SchemaInfo(BaseModel):
    """Describe the schema name and version stamped onto a persisted artifact payload."""

    model_config = ConfigDict(extra="forbid")
    name: str
    version: str


class CanonInfo(BaseModel):
    """Record the canonicalization rules that were in force when an artifact was serialized."""

    model_config = ConfigDict(extra="forbid")

    name: str = "polisyos.canon.json"
    version: str = "0.2.0"
    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    exclude_none: bool = True
    max_depth: int = 128
    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False

    @classmethod
    def from_spec(cls, spec: CanonSpec) -> CanonInfo:
        return cls(
            name=spec.name,
            version=spec.version,
            forbid_floats=spec.forbid_floats,
            forbid_nan_inf=spec.forbid_nan_inf,
            exclude_none=spec.exclude_none,
            max_depth=spec.max_depth,
            sort_keys=spec.sort_keys,
            separators=spec.separators,
            ensure_ascii=spec.ensure_ascii,
        )


class InputRef(BaseModel):
    """Identify an upstream artifact that should be recorded in persistence lineage metadata."""

    model_config = ConfigDict(extra="forbid")
    artifact_id: ArtifactID
    role: str
    manifest_profile_sha256: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )


@dataclass(frozen=True, slots=True)
class ArtifactOwnerDeclaration[OwnerSourceT, OwnerConsumerT]:
    """Bind a trusted consumer and DTO ABI to exact registered artifact representations."""

    contract_id: str
    dto_fqn: str
    abi_key: str
    registry_key: str
    kind: str
    media_type: str
    purpose: str
    policy_revision: str
    accepted_wire_policies: tuple[tuple[str, str], ...]
    payload_version_of: Callable[[object], str | None]
    validate_source: Callable[[object, ResolvedSchemaAdmission], OwnerSourceT]
    project_for_consumer: Callable[[OwnerSourceT, ResolvedSchemaAdmission], OwnerConsumerT]
    validate_profile: Callable[[CanonInfo, IRRepresentationRegistration], bool]

    def __post_init__(self) -> None:
        """Reject incomplete declarations before they can be used as trusted owner context."""
        for field_name in (
            "contract_id",
            "dto_fqn",
            "abi_key",
            "registry_key",
            "kind",
            "media_type",
            "purpose",
            "policy_revision",
        ):
            value = getattr(self, field_name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"Artifact owner declaration requires a nonempty {field_name}")
        policies = self.accepted_wire_policies
        if type(policies) is not tuple or not policies:
            raise ValueError("Artifact owner declaration requires trusted wire policies")
        normalized_policies: list[tuple[str, str]] = []
        for policy in policies:
            if (
                type(policy) is not tuple
                or len(policy) != 2
                or any(type(value) is not str or not value.strip() for value in policy)
            ):
                raise ValueError("Artifact owner wire policies must be exact non-empty pairs")
            normalized_policies.append(policy)
        if len(set(normalized_policies)) != len(normalized_policies):
            raise ValueError("Artifact owner wire policies must be unique")
        for field_name in (
            "payload_version_of",
            "validate_source",
            "project_for_consumer",
            "validate_profile",
        ):
            if not callable(getattr(self, field_name)):
                raise TypeError(f"Artifact owner declaration requires callable {field_name}")


@dataclass(frozen=True, slots=True)
class OwnedArtifactRead[OwnerConsumerT]:
    """Retain the exact shared admission context and byte witness for one typed read."""

    value: OwnerConsumerT
    raw_bytes: bytes
    admission: ResolvedSchemaAdmission
    contract_id: str
    dto_fqn: str
    abi_key: str
    registry_key: str
    purpose: str
    owner_policy_revision: str
    manifest_profile_sha256: str | None


@dataclass(frozen=True)
class PutOptions:
    """Collect the metadata that IR helpers attach when persisting a JSON artifact."""

    kind: str
    media_type: str
    schema: SchemaInfo | None = None
    producer: Any = None
    env: Any = None
    inputs: list[InputRef] | None = None
    canon: CanonInfo | None = None


type _MetadataOption = BaseModel | Mapping[str, Any]


class ArtifactViewRef(Protocol):
    """Describe an exact artifact view without importing its owning store layer."""

    @property
    def artifact_id(self) -> object: ...

    @property
    def kind(self) -> str: ...

    @property
    def media_type(self) -> str: ...

    @property
    def manifest_profile_sha256(self) -> str | None: ...


type ArtifactSelector = ArtifactID | RootModel[str] | ArtifactViewRef | Mapping[str, Any] | str


@dataclass(frozen=True)
class StorePutOptions:
    """Typed metadata projection compatible with Core ``ArtifactWriteOptions``."""

    kind: str
    media_type: str
    schema: _MetadataOption | None = None
    producer: _MetadataOption | None = None
    env: _MetadataOption | None = None
    inputs: list[_MetadataOption] | None = None
    canon: _MetadataOption | None = None
    governance: _MetadataOption | None = None
    tenant_context: _MetadataOption | None = None
    same_input_closure: _MetadataOption | None = None
    authority: _MetadataOption | None = None
    child_release: _MetadataOption | None = None
    warnings: list[_MetadataOption] | None = None


class OwnedWriteOptionsPreparer(Protocol):
    """Normalize a selected owner write into the neutral IR options contract.

    Concrete stores own normalization of their native write DTOs. The shared IR
    owner path consumes only this detached, complete-facet projection.
    """

    def prepare_owned_write_options(self, options: object) -> StorePutOptions: ...


@runtime_checkable
class ArtifactStore(Protocol):
    """Minimal CAS protocol required by IR helpers for writing JSON and reading raw bytes."""

    def put_json(
        self,
        obj: object,
        opts: StorePutOptions | Mapping[str, Any],
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> object: ...

    def get_bytes(self, artifact_id: ArtifactSelector) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactSelector) -> object: ...

    def get_raw_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        """Return exact selected raw sidecar bytes before typed model construction."""
        ...

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        """Return the exact raw sidecar bytes for this ID or selected view."""
        ...

    def iter_artifact_ids(self) -> list[Any]: ...


def _string_key_payload(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("Input reference payload must be a mapping")
    payload: dict[str, object] = {}
    seen: set[str] = set()
    for key in tuple(value):
        if not isinstance(key, str):
            raise TypeError("Input reference payload keys must be strings")
        if key in seen:
            raise TypeError(f"Input reference payload contains duplicate key: {key}")
        seen.add(key)
        try:
            item = value[key]
        except KeyError as exc:
            raise TypeError(
                f"Input reference payload key has no corresponding value: {key}"
            ) from exc
        payload[key] = item
    return payload


def _as_payload(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return _string_key_payload(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _string_key_payload(model_dump(mode="python"))
    return {
        "artifact_id": getattr(value, "artifact_id", value),
        "role": getattr(value, "role", "input"),
        "manifest_profile_sha256": getattr(value, "manifest_profile_sha256", None),
    }


def normalize_input_refs(inputs: Sequence[object] | None) -> list[InputRef]:
    """Coerce a declared input sequence into validated refs before persistence."""
    if inputs is None:
        return []
    if isinstance(inputs, (str, bytes, bytearray, memoryview, Mapping)) or not isinstance(
        inputs, Sequence
    ):
        raise CanonViolation("ir_artifact_inputs_invalid")
    normalized: list[InputRef] = []
    for value in inputs:
        payload = _as_payload(value)
        if "artifact_id" in payload:
            payload["artifact_id"] = str(payload["artifact_id"])
        normalized.append(InputRef.model_validate(payload))
    return normalized


def to_store_put_options(opts: PutOptions) -> StorePutOptions:
    """Convert to store put options."""
    schema = opts.schema.model_dump(mode="python") if opts.schema is not None else None
    canon = opts.canon.model_dump(mode="python") if opts.canon is not None else None
    input_payloads: list[_MetadataOption] = []
    for entry in opts.inputs or []:
        input_payloads.append(entry.model_dump(mode="python"))
    inputs = input_payloads or None
    governance_option = getattr(opts, "governance", None)
    governance = (
        governance_option.model_dump(mode="python") if governance_option is not None else None
    )
    return StorePutOptions(
        kind=opts.kind,
        media_type=opts.media_type,
        schema=schema,
        producer=opts.producer,
        env=opts.env,
        inputs=inputs,
        canon=canon,
        governance=governance,
    )


@dataclass(frozen=True, slots=True)
class _DataclassFieldInventory:
    """Validated raw and value-bearing field names for one dataclass selector."""

    raw_names: frozenset[str]
    value_names: frozenset[str]


def _validated_dataclass_field_inventory(
    value: object,
) -> _DataclassFieldInventory | None:
    """Validate raw dataclass metadata before any selector projection.

    An empty marker provides no dataclass attestation. Callers may still accept its object through
    the ordinary strict mapping or structural-selector checks.
    """
    if not is_dataclass(value):
        return None
    if isinstance(value, type):
        raise TypeError("Artifact reference dataclass selector must be an instance")

    missing = object()
    raw_metadata: object = missing
    try:
        for cls in type(value).__mro__:
            namespace = cls.__dict__
            if "__dataclass_fields__" in namespace:
                raw_metadata = namespace["__dataclass_fields__"]
                break
    except Exception as exc:
        raise TypeError(
            "Artifact reference dataclass selector has malformed field metadata"
        ) from exc
    if raw_metadata is missing or not isinstance(raw_metadata, Mapping):
        raise TypeError("Artifact reference dataclass selector has malformed field metadata")

    raw_mapping: Mapping[object, object] = raw_metadata
    try:
        raw_length = len(raw_mapping)
        raw_keys = tuple(raw_mapping)
        if raw_length != len(raw_keys):
            raise TypeError("Dataclass field metadata length does not match its keys")

        raw_fields: dict[str, object] = {}
        field_identities: set[int] = set()
        for key in raw_keys:
            if not isinstance(key, str) or not key.isidentifier() or key in raw_fields:
                raise TypeError("Dataclass field metadata has an invalid or duplicate key")
            field = raw_mapping[key]
            if not isinstance(field, DataclassField):
                raise TypeError("Dataclass field metadata contains a non-Field value")
            if not isinstance(field.name, str) or not field.name.isidentifier():
                raise TypeError("Dataclass field metadata contains an invalid Field name")
            if field.name != key:
                raise TypeError("Dataclass field metadata key does not match Field.name")
            if id(field) in field_identities:
                raise TypeError("Dataclass field metadata reuses a Field object")
            field_identities.add(id(field))
            raw_fields[key] = field

        raw_items = tuple(raw_mapping.items())
        if len(raw_items) != raw_length:
            raise TypeError("Dataclass field metadata items do not match its length")
        item_keys: set[str] = set()
        for item in raw_items:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("Dataclass field metadata contains a malformed item")
            item_key, item_field = item
            if (
                not isinstance(item_key, str)
                or item_key not in raw_fields
                or item_key in item_keys
                or item_field is not raw_fields[item_key]
            ):
                raise TypeError("Dataclass field metadata items disagree with its keys")
            item_keys.add(item_key)
        if item_keys != set(raw_fields):
            raise TypeError("Dataclass field metadata items omit a key")

        derived_fields = fields(value)
        value_names: set[str] = set()
        value_field_identities: set[int] = set()
        for field in derived_fields:
            if not isinstance(field, DataclassField):
                raise TypeError("Dataclass value fields contain a non-Field value")
            field_name = field.name
            if (
                not isinstance(field_name, str)
                or not field_name.isidentifier()
                or field_name in value_names
                or id(field) in value_field_identities
                or raw_fields.get(field_name) is not field
                or not hasattr(value, field_name)
            ):
                raise TypeError("Dataclass value fields disagree with raw field metadata")
            value_names.add(field_name)
            value_field_identities.add(id(field))
    except Exception as exc:
        raise TypeError(
            "Artifact reference dataclass selector has malformed field metadata"
        ) from exc

    if not raw_fields:
        if value_names:
            raise TypeError("Artifact reference dataclass selector has malformed field metadata")
        return None
    return _DataclassFieldInventory(
        raw_names=frozenset(raw_fields),
        value_names=frozenset(value_names),
    )


def _artifact_ref_mapping_shape_matches(
    value: Mapping[object, object], expected_keys: frozenset[str]
) -> bool:
    """Return whether a mapping still exposes the frozen selector key shape."""
    try:
        current_length = len(value)
        current_keys = tuple(value)
    except Exception:
        return False
    return (
        current_length == len(expected_keys)
        and len(current_keys) == len(expected_keys)
        and all(isinstance(key, str) for key in current_keys)
        and len(set(current_keys)) == len(current_keys)
        and frozenset(current_keys) == expected_keys
    )


def _artifact_ref_mapping_snapshot(
    value: Mapping[object, object],
) -> tuple[dict[str, object], frozenset[str]]:
    """Materialize one mapping payload and retain the exact key-shape witness."""
    try:
        original_length = len(value)
        original_keys = tuple(value)
    except Exception as exc:
        raise TypeError("Artifact reference mapping payload is malformed") from exc
    if original_length != len(original_keys):
        raise TypeError("Artifact reference mapping changed during normalization")
    if not all(isinstance(key, str) for key in original_keys):
        raise TypeError("Artifact reference payload keys must be strings")
    key_set = frozenset(original_keys)
    if len(key_set) != len(original_keys):
        raise TypeError("Artifact reference mapping contains duplicate keys")

    payload: dict[str, object] = {}
    try:
        for key in original_keys:
            payload[key] = value[key]
    except Exception as exc:
        raise TypeError(
            "Artifact reference mapping payload changed during materialization"
        ) from exc
    if len(payload) != original_length or frozenset(payload) != key_set:
        raise TypeError("Artifact reference mapping payload lost its frozen key shape")
    if not _artifact_ref_mapping_shape_matches(value, key_set):
        raise TypeError("Artifact reference mapping changed during materialization")
    return payload, key_set


def _pydantic_artifact_ref_stored_payload(value: object) -> dict[str, object]:
    """Read Pydantic field storage and extras without trusting a projection method."""
    if not _is_pydantic_model_instance(value):
        raise TypeError("Artifact reference model has malformed stored values")
    try:
        raw_fields = object.__getattribute__(value, "__dict__")
        extras = object.__getattribute__(value, "__pydantic_extra__")
    except AttributeError as exc:
        raise TypeError("Artifact reference model has malformed stored values") from exc
    if not isinstance(raw_fields, Mapping):
        raise TypeError("Artifact reference model has malformed stored values")
    payload = dict(raw_fields)
    if extras is not None:
        if not isinstance(extras, Mapping):
            raise TypeError("Artifact reference model has malformed extra values")
        for key, item in extras.items():
            if key in payload:
                raise TypeError("Artifact reference model has overlapping stored values")
            payload[key] = item
    return payload


def normalize_artifact_ref(ref: object) -> dict[str, str]:
    """Normalize a store-specific artifact handle into the stable IR ref mapping boundary."""
    from polisyos.ir.registry.refs import ArtifactRefModel

    facade_target = _trusted_artifact_ref_facade_target(ref)
    if facade_target is not None:
        return normalize_artifact_ref(facade_target)
    _reject_unbacked_pydantic_class_view(ref)

    mapping_snapshot = (
        _artifact_ref_mapping_snapshot(ref)
        if isinstance(ref, Mapping) and not _is_pydantic_model_instance(ref)
        else None
    )
    field_inventory = _validated_dataclass_field_inventory(ref)
    original_selector_fields = frozenset(_selector_public_fields(ref, field_inventory))
    if mapping_snapshot is None:
        _refuse_unknown_model_fields(original_selector_fields, ArtifactRefModel.model_fields)
    else:
        _mapping_payload, mapping_payload_fields = mapping_snapshot
        if not _artifact_ref_mapping_shape_matches(ref, mapping_payload_fields):
            raise TypeError("Artifact reference mapping changed during selector inspection")
        _refuse_unknown_model_fields(
            original_selector_fields - mapping_payload_fields, ArtifactRefModel.model_fields
        )

    # Freeze the caller shape before consulting a projection method. A custom model_dump can
    # mutate a structural selector before returning a narrower mapping. Mapping inputs instead
    # validate their frozen raw payload so unknown payload keys remain Pydantic errors.
    model_dump = (
        getattr(ref, "model_dump", None)
        if mapping_snapshot is None and _is_pydantic_model_instance(ref)
        else None
    )
    selector_fields = original_selector_fields
    if mapping_snapshot is None:
        selector_fields |= frozenset(_selector_public_fields(ref, field_inventory))
        _refuse_unknown_model_fields(selector_fields, ArtifactRefModel.model_fields)
    else:
        mapping_payload_fields = mapping_snapshot[1]
        selector_fields |= frozenset(_selector_public_fields(ref, field_inventory))
        if not _artifact_ref_mapping_shape_matches(ref, mapping_payload_fields):
            raise TypeError("Artifact reference mapping changed during selector inspection")
        _refuse_unknown_model_fields(
            selector_fields - mapping_payload_fields, ArtifactRefModel.model_fields
        )
    if callable(model_dump):
        model_fields = getattr(type(ref), "model_fields", None)
        _refuse_unknown_model_fields(model_fields, ArtifactRefModel.model_fields)
        try:
            stored_model = ArtifactRefModel.model_validate(
                _pydantic_artifact_ref_stored_payload(ref)
            )
        except Exception as exc:
            raise TypeError("Artifact reference model has invalid stored values") from exc
        projected_payload = model_dump(mode="python")
        if not isinstance(projected_payload, Mapping):
            raise TypeError("Artifact reference model_dump() must return a mapping")
        try:
            projected_model = ArtifactRefModel.model_validate(dict(projected_payload))
        except Exception as exc:
            raise TypeError("Artifact reference model_dump() projection is invalid") from exc
        if projected_model != stored_model:
            raise TypeError(
                "Artifact reference model_dump() projection disagrees with stored values"
            )
        try:
            current_model = ArtifactRefModel.model_validate(
                _pydantic_artifact_ref_stored_payload(ref)
            )
        except Exception as exc:
            raise TypeError("Artifact reference model changed during projection") from exc
        if current_model != stored_model:
            raise TypeError("Artifact reference model changed during projection")
        selector_fields |= frozenset(_selector_public_fields(ref, field_inventory))
        _refuse_unknown_model_fields(selector_fields, ArtifactRefModel.model_fields)
        payload = stored_model.model_dump(mode="python")
    elif mapping_snapshot is not None:
        mapping_payload, mapping_payload_fields = mapping_snapshot
        if not _artifact_ref_mapping_shape_matches(ref, mapping_payload_fields):
            raise TypeError("Artifact reference mapping changed before validation")
        payload = mapping_payload
    elif is_dataclass(ref):
        if isinstance(ref, type):
            raise TypeError("Artifact reference dataclass selector must be an instance")
        if field_inventory is not None:
            # An allowed selector member cannot disappear merely because dataclasses omits a
            # ClassVar or InitVar from the value projection.
            missing_value_fields = sorted(
                (field_inventory.raw_names - field_inventory.value_names)
                & ArtifactRefModel.model_fields.keys()
            )
            if missing_value_fields:
                raise TypeError(
                    "Artifact reference dataclass selector fields must be value-bearing: "
                    + ", ".join(missing_value_fields)
                )
            try:
                payload = asdict(ref)
            except Exception as exc:
                raise TypeError(
                    "Artifact reference dataclass selector has malformed field values"
                ) from exc
            if frozenset(payload) != field_inventory.value_names:
                raise TypeError("Artifact reference dataclass selector has malformed field values")
            selector_fields |= frozenset(_selector_public_fields(ref, field_inventory))
            _refuse_unknown_model_fields(selector_fields, ArtifactRefModel.model_fields)
        else:
            # Empty marker metadata is not dataclass attestation; require the ordinary object shape.
            payload = _object_artifact_ref_payload(
                ref,
                ArtifactRefModel.model_fields,
                field_inventory=field_inventory,
                selector_fields=selector_fields,
            )
    elif hasattr(ref, "__dict__"):
        payload = _object_artifact_ref_payload(
            ref,
            ArtifactRefModel.model_fields,
            field_inventory=field_inventory,
            selector_fields=selector_fields,
        )
    else:
        model_fields = ArtifactRefModel.model_fields
        payload = _structural_artifact_ref_payload(
            ref,
            model_fields,
            field_inventory=field_inventory,
            selector_fields=selector_fields,
        )
    if not all(isinstance(key, str) for key in payload):
        raise TypeError("Artifact reference payload keys must be strings")
    validated = ArtifactRefModel.model_validate(payload)
    return {key: str(value) for key, value in dict(validated).items()}


def _pydantic_model_input_fields(value: BaseModel) -> frozenset[str]:
    """Inventory a Pydantic instance from stored values, fields-set, and extras."""
    if not _is_pydantic_model_instance(value):
        raise TypeError("Artifact reference model has malformed field metadata")
    try:
        raw_fields = object.__getattribute__(value, "__dict__")
        model_fields = getattr(type(value), "model_fields", None)
        fields_set = object.__getattribute__(value, "__pydantic_fields_set__")
        extras = object.__getattribute__(value, "__pydantic_extra__")
    except AttributeError as exc:
        raise TypeError("Artifact reference model has malformed field metadata") from exc
    if (
        not isinstance(raw_fields, Mapping)
        or not isinstance(model_fields, Mapping)
        or not isinstance(fields_set, (set, frozenset))
    ):
        raise TypeError("Artifact reference model has malformed field metadata")
    names = set(raw_fields) | set(model_fields) | set(fields_set)
    if extras is not None:
        if not isinstance(extras, Mapping):
            raise TypeError("Artifact reference model has malformed extra fields")
        names.update(extras)
    if not all(isinstance(name, str) for name in names):
        raise TypeError("Artifact reference model has malformed field names")
    return frozenset(names)


def _string_root_model_snapshot(
    value: object,
) -> tuple[str, frozenset[str], frozenset[str]]:
    """Snapshot only stored inputs for a schema-only scalar Pydantic root."""
    if not _is_pydantic_model_instance(value):
        raise TypeError("Artifact ID root model has malformed stored fields")
    fields = _pydantic_model_input_fields(value)
    try:
        raw_fields = object.__getattribute__(value, "__dict__")
        model_fields = getattr(type(value), "model_fields", None)
        fields_set = object.__getattribute__(value, "__pydantic_fields_set__")
    except AttributeError as exc:
        raise TypeError("Artifact ID root model has malformed stored fields") from exc
    if (
        not isinstance(raw_fields, Mapping)
        or not isinstance(model_fields, Mapping)
        or set(model_fields) != {"root"}
        or not isinstance(fields_set, (set, frozenset))
        or not all(isinstance(name, str) for name in fields_set)
    ):
        raise TypeError("Artifact ID root model has malformed stored fields")

    declared_fields = set(fields)
    for cls in type(value).__mro__:
        if cls is BaseModel:
            break
        annotations = cls.__dict__.get("__annotations__", {})
        if not isinstance(annotations, Mapping):
            raise TypeError("Artifact ID root model has malformed annotations")
        class_vars = cls.__dict__.get("__class_vars__", ())
        if not isinstance(class_vars, (set, frozenset, tuple, list)):
            raise TypeError("Artifact ID root model has malformed class-variable metadata")
        declared_fields.update(
            name
            for name, annotation in annotations.items()
            if not name.startswith("_")
            and name not in class_vars
            and not _is_classvar_annotation(annotation)
        )
        slots = cls.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        elif not isinstance(slots, (tuple, list)):
            raise TypeError("Artifact ID root model has malformed slots")
        if not all(isinstance(name, str) for name in slots):
            raise TypeError("Artifact ID root model has malformed slots")
        declared_fields.update(name for name in slots if not name.startswith("_"))

    public_fields = frozenset(name for name in declared_fields if not name.startswith("_"))
    if public_fields != frozenset({"root"}) or "root" not in raw_fields:
        raise TypeError("Artifact ID root model has unexpected stored fields")
    root = raw_fields["root"]
    if not isinstance(root, str):
        raise TypeError("Artifact ID root model must store a string root")
    root_text = _builtins.str.__str__(root)
    if type(root_text) is not str:
        raise TypeError("Artifact ID root model must store a native string root")
    return root_text, public_fields, frozenset(fields_set)


def _is_classvar_annotation(annotation: object) -> bool:
    """Recognize ClassVar without evaluating future-annotation strings."""
    if annotation is ClassVar or get_origin(annotation) is ClassVar:
        return True
    if not isinstance(annotation, str):
        return False
    try:
        expression = ast.parse(annotation, mode="eval").body
    except SyntaxError:
        return False
    if isinstance(expression, ast.Subscript):
        expression = expression.value
    if isinstance(expression, ast.Name):
        return expression.id == "ClassVar"
    return (
        isinstance(expression, ast.Attribute)
        and expression.attr == "ClassVar"
        and isinstance(expression.value, ast.Name)
        and expression.value.id in {"typing", "typing_extensions"}
    )


def _declared_public_fields(value: object) -> set[str]:
    """Return declared annotations, properties, and slots for a structural ref."""
    names: set[str] = set()
    for cls in type(value).__mro__:
        if cls is BaseModel:
            break
        annotations = cls.__dict__.get("__annotations__", {})
        class_vars = cls.__dict__.get("__class_vars__", ())
        if not isinstance(class_vars, (set, frozenset, tuple, list)):
            class_vars = ()
        names.update(
            name
            for name, annotation in annotations.items()
            if not name.startswith("_")
            and name not in class_vars
            and not _is_classvar_annotation(annotation)
        )
        names.update(
            name
            for name, member in cls.__dict__.items()
            if not name.startswith("_") and isinstance(member, property)
        )
        slots = cls.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        names.update(name for name in slots if isinstance(name, str) and not name.startswith("_"))
    return names


def _selector_public_fields(
    value: object,
    field_inventory: _DataclassFieldInventory | None = None,
) -> set[str]:
    """Collect public selector fields before projecting a supported ref shape."""
    names = _declared_public_fields(value)
    if _is_pydantic_model_instance(value):
        names.update(_pydantic_model_input_fields(value))
    if isinstance(value, Mapping):
        names.update(name for name in value if isinstance(name, str))
    if hasattr(value, "__dict__"):
        names.update(name for name in vars(value) if not name.startswith("_"))
    if field_inventory is None:
        field_inventory = _validated_dataclass_field_inventory(value)
    if field_inventory is not None:
        names.update(name for name in field_inventory.raw_names if not name.startswith("_"))
    return names


def _object_artifact_ref_payload(
    ref: object,
    model_fields: Mapping[str, Any],
    *,
    field_inventory: _DataclassFieldInventory | None = None,
    selector_fields: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Normalize an ordinary object selector without trusting dataclass-shaped markers."""
    instance_payload = (
        {name: value for name, value in vars(ref).items() if not name.startswith("_")}
        if hasattr(ref, "__dict__")
        else {}
    )
    required_fields = {name for name, field in model_fields.items() if field.is_required()}
    if selector_fields is None:
        selector_fields = frozenset(_selector_public_fields(ref, field_inventory))
    _refuse_unknown_model_fields(selector_fields, model_fields)
    if required_fields <= set(instance_payload):
        return instance_payload
    return _structural_artifact_ref_payload(
        ref,
        model_fields,
        field_inventory=field_inventory,
        selector_fields=selector_fields,
    )


def _structural_artifact_ref_payload(
    ref: object,
    model_fields: Mapping[str, Any],
    *,
    field_inventory: _DataclassFieldInventory | None = None,
    selector_fields: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Project only an exact structural ref, rejecting declared extensions."""
    if selector_fields is None:
        selector_fields = frozenset(_selector_public_fields(ref, field_inventory))
    _refuse_unknown_model_fields(selector_fields, model_fields)
    required_fields = tuple(name for name, field in model_fields.items() if field.is_required())
    if not all(hasattr(ref, name) for name in required_fields):
        raise TypeError("Artifact reference selector does not expose the required fields")
    payload = {
        field_name: getattr(ref, field_name)
        for field_name in model_fields
        if hasattr(ref, field_name)
    }
    projected_fields = frozenset(_selector_public_fields(ref, field_inventory))
    _refuse_unknown_model_fields(selector_fields | projected_fields, model_fields)
    return payload


def _refuse_unknown_model_fields(
    supplied: object,
    allowed: Mapping[str, Any],
) -> None:
    """Refuse declared selector fields outside the canonical ref model."""
    if not isinstance(supplied, (Mapping, set, frozenset)):
        return
    supplied_fields = set(supplied)
    unknown = supplied_fields - set(allowed)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise TypeError(f"Artifact reference selector has unexpected field(s): {names}")


__all__ = [
    "ArtifactID",
    "ArtifactSelector",
    "ArtifactStore",
    "ArtifactViewRef",
    "CanonInfo",
    "InputRef",
    "PutOptions",
    "SchemaInfo",
    "StorePutOptions",
    "normalize_artifact_ref",
    "normalize_input_refs",
    "to_store_put_options",
]
