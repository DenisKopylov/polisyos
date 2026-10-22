"""Typed contracts that describe how IR payloads cross the artifact-store boundary."""

from __future__ import annotations

import builtins as _builtins
import re
from collections.abc import Mapping
from dataclasses import Field as DataclassField
from dataclasses import asdict, dataclass, fields, is_dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Protocol,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.ir.model_layer.canon import CanonSpec

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_string_root_model(value: object) -> bool:
    """Return whether a value is a Pydantic scalar root whose only field is ``str``."""
    model_fields = getattr(type(value), "model_fields", None)
    root_field = model_fields.get("root") if isinstance(model_fields, Mapping) else None
    return (
        getattr(type(value), "__pydantic_root_model__", False) is True
        and isinstance(model_fields, Mapping)
        and set(model_fields) == {"root"}
        and getattr(root_field, "annotation", None) is str
    )


def _normalize_scalar_artifact_id(value: object) -> ArtifactID:
    """Normalize a string ID, native IR ID, or exact scalar root-model ID."""
    if isinstance(value, str):
        return ArtifactID.model_validate(value)
    if isinstance(value, ArtifactID):
        return value
    if not _is_string_root_model(value):
        raise TypeError("Artifact ID selector must be a string scalar")
    model_dump = getattr(value, "model_dump", None)
    if not callable(model_dump):
        raise TypeError("Artifact ID root model must expose model_dump()")
    dumped = model_dump(mode="python")
    if not isinstance(dumped, str):
        raise TypeError("Artifact ID root model must dump to a string")
    return ArtifactID.model_validate(dumped)


class ArtifactID(RootModel[str]):
    """IR-local artifact ID model compatible with CAS interfaces."""

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
        if not _SHA256_HEX_RE.match(hex64):
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
        if not _SHA256_HEX_RE.match(hex64):
            raise ValueError("sha256 hex must be 64 characters [0-9a-f]")
        prefix = _builtins.str.__str__(cls.prefix)
        return cls(f"{prefix}{hex64}")

    @property
    def hex(self) -> str:
        algo, hex64 = self.root.split(":", 1)
        if algo != "sha256":
            raise ValueError(f"Unsupported algo: {algo}")
        if not _SHA256_HEX_RE.match(hex64):
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
    warnings: list[_MetadataOption] | None = None


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
    """Coerce loose lineage inputs into validated ``InputRef`` records before persistence."""
    if not inputs:
        return []
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


def normalize_artifact_ref(ref: object) -> dict[str, str]:
    """Normalize a store-specific artifact handle into the stable IR ref mapping boundary."""
    from polisyos.ir.registry.refs import ArtifactRefModel

    field_inventory = _validated_dataclass_field_inventory(ref)
    if field_inventory is not None:
        _refuse_unknown_model_fields(
            {name for name in field_inventory.raw_names if not name.startswith("_")},
            ArtifactRefModel.model_fields,
        )

    model_dump = getattr(ref, "model_dump", None)
    if callable(model_dump):
        model_fields = getattr(type(ref), "model_fields", None)
        _refuse_unknown_model_fields(model_fields, ArtifactRefModel.model_fields)
        payload = model_dump(mode="python")
        if not isinstance(payload, Mapping):
            raise TypeError("Artifact reference model_dump() must return a mapping")
        _refuse_unknown_model_fields(_declared_public_fields(ref), ArtifactRefModel.model_fields)
        payload = dict(payload)
    elif isinstance(ref, Mapping):
        payload = dict(ref)
        declared_fields = _declared_public_fields(ref)
        if hasattr(ref, "__dict__"):
            declared_fields.update(name for name in vars(ref) if not name.startswith("_"))
        _refuse_unknown_model_fields(declared_fields, ArtifactRefModel.model_fields)
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
            _refuse_unknown_model_fields(
                _selector_public_fields(ref, field_inventory), ArtifactRefModel.model_fields
            )
        else:
            # Empty marker metadata is not dataclass attestation; require the ordinary object shape.
            payload = _object_artifact_ref_payload(
                ref, ArtifactRefModel.model_fields, field_inventory=field_inventory
            )
    elif hasattr(ref, "__dict__"):
        payload = _object_artifact_ref_payload(ref, ArtifactRefModel.model_fields)
    else:
        model_fields = ArtifactRefModel.model_fields
        payload = _structural_artifact_ref_payload(ref, model_fields)
    if not all(isinstance(key, str) for key in payload):
        raise TypeError("Artifact reference payload keys must be strings")
    validated = ArtifactRefModel.model_validate(payload)
    return {key: str(value) for key, value in dict(validated).items()}


def _declared_public_fields(value: object) -> set[str]:
    """Return declared annotations, properties, and slots for a structural ref."""
    names: set[str] = set()
    for cls in type(value).__mro__:
        if cls is BaseModel:
            break
        names.update(
            name for name in cls.__dict__.get("__annotations__", {}) if not name.startswith("_")
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
) -> dict[str, Any]:
    """Normalize an ordinary object selector without trusting dataclass-shaped markers."""
    instance_payload = (
        {name: value for name, value in vars(ref).items() if not name.startswith("_")}
        if hasattr(ref, "__dict__")
        else {}
    )
    required_fields = {name for name, field in model_fields.items() if field.is_required()}
    _refuse_unknown_model_fields(_selector_public_fields(ref, field_inventory), model_fields)
    if required_fields <= set(instance_payload):
        return instance_payload
    return _structural_artifact_ref_payload(ref, model_fields)


def _structural_artifact_ref_payload(
    ref: object,
    model_fields: Mapping[str, Any],
) -> dict[str, Any]:
    """Project only an exact structural ref, rejecting declared extensions."""
    required_fields = tuple(name for name, field in model_fields.items() if field.is_required())
    if not all(hasattr(ref, name) for name in required_fields):
        raise TypeError("Artifact reference selector does not expose the required fields")
    _refuse_unknown_model_fields(_declared_public_fields(ref), model_fields)
    return {
        field_name: getattr(ref, field_name)
        for field_name in model_fields
        if hasattr(ref, field_name)
    }


def _refuse_unknown_model_fields(
    supplied: object,
    allowed: Mapping[str, Any],
) -> None:
    """Refuse declared selector fields outside the canonical ref model."""
    if isinstance(supplied, Mapping):
        supplied_fields = set(supplied)
    elif isinstance(supplied, set):
        supplied_fields = supplied
    else:
        return
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
