"""Read Core JSON artifacts against their exact raw manifest profile."""

from __future__ import annotations

import json
import types
from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, RootModel, TypeAdapter, ValidationError
from pydantic.errors import PydanticUserError

from polisyos.common.canonical_profile import (
    CanonicalProfileDeclaration,
    CanonicalProfileRead,
    CanonicalProfileRefusalError,
    _bind_selected_artifact_identity,
    decode_profiled_canonical_bytes,
    parse_canonical_profile,
    require_declared_profile,
)
from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, CanonInfo
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def artifact_ref_for_manifest(manifest: ArtifactManifest) -> ArtifactRef:
    """Return the exact typed CAS view selected by ``manifest``."""
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )


def _core_spec(profile: CanonInfo) -> CanonSpec:
    return CanonSpec(
        name=profile.name,
        version=profile.version,
        forbid_floats=profile.forbid_floats,
        forbid_nan_inf=profile.forbid_nan_inf,
        exclude_none=profile.exclude_none,
        max_depth=profile.max_depth,
        sort_keys=profile.sort_keys,
        separators=profile.separators,
        ensure_ascii=profile.ensure_ascii,
    )


def _core_spec_from_profile(profile: BaseModel) -> object:
    """Adapt the shared profile callback to Core's concrete profile model."""
    if not isinstance(profile, CanonInfo):
        raise TypeError("Core canonicalization requires CanonInfo")
    return _core_spec(profile)


def _encode_core_profiled_value(value: Any, spec: object) -> bytes:
    """Encode only with the concrete Core spec built from its selected profile."""
    if not isinstance(spec, CanonSpec):
        raise TypeError("Core canonicalization requires CanonSpec")
    return to_canonical_bytes(value, spec)


def _require_exact_bytes(value: object, refusal_code: str) -> bytes:
    """Narrow an untyped storage result only after checking its runtime type."""
    if type(value) is not bytes:
        raise CanonicalProfileRefusalError(refusal_code)
    return value


def read_core_manifest_profile(
    store: object,
    selector: object,
    *,
    manifest_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> tuple[ArtifactManifest, CanonicalProfileDeclaration]:
    """Read and verify the raw profile before typed manifest admission.

    The optional raw-manifest capability preserves the selected storage view while
    allowing malformed-present CanonInfo to remain distinguishable from absence.
    Absence refuses by default; an explicit candidate-only opt-in never establishes
    historical eligibility. Typed resolution follows strict raw profile parsing.
    """
    raw_reader = getattr(store, "get_raw_manifest_bytes", None)
    manifest_reader = getattr(store, "get_manifest", None)
    if not callable(raw_reader):
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable")
    if not callable(manifest_reader):
        raise CanonicalProfileRefusalError("canon_profile_typed_manifest_unavailable")
    try:
        if manifest_profile_sha256 is None:
            raw_manifest_bytes = raw_reader(selector)
        else:
            raw_manifest_bytes = raw_reader(
                selector,
                manifest_profile_sha256=manifest_profile_sha256,
            )
    except FileNotFoundError:
        raise
    except (AttributeError, NotImplementedError, TypeError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable") from exc
    declaration = parse_canonical_profile(
        raw_manifest_bytes,
        profile_model=CanonInfo,
        allow_profile_absent=allow_profile_absent,
    )
    try:
        if manifest_profile_sha256 is None:
            typed_manifest = ArtifactManifest.model_validate(manifest_reader(selector))
        else:
            resolver = getattr(store, "get_manifest_by_profile", None)
            selected_artifact_id = getattr(selector, "artifact_id", selector)
            if callable(resolver):
                typed_manifest = ArtifactManifest.model_validate(
                    resolver(selected_artifact_id, manifest_profile_sha256)
                )
            else:
                typed_manifest = ArtifactManifest.model_validate(manifest_reader(selector))
                if artifact_manifest_profile_sha256(typed_manifest) != manifest_profile_sha256:
                    raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
        raw_typed_manifest = ArtifactManifest.model_validate_json(raw_manifest_bytes)
    except FileNotFoundError:
        raise
    except CanonicalProfileRefusalError:
        raise
    except (TypeError, ValidationError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_invalid") from exc
    if raw_typed_manifest != typed_manifest:
        raise CanonicalProfileRefusalError("canon_profile_selected_manifest_changed")
    if isinstance(selector, ArtifactRef) and (
        selector.artifact_id != typed_manifest.artifact_id
        or selector.kind != typed_manifest.kind
        or selector.media_type != typed_manifest.media_type
        or (
            selector.manifest_profile_sha256 is not None
            and selector.manifest_profile_sha256 != artifact_manifest_profile_sha256(typed_manifest)
        )
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    if (
        manifest_profile_sha256 is not None
        and artifact_manifest_profile_sha256(typed_manifest) != manifest_profile_sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    return typed_manifest, declaration


def decode_core_json_payload(
    raw_manifest_bytes: bytes,
    raw_payload_bytes: bytes,
    *,
    allow_profile_absent: bool = False,
) -> CanonicalProfileRead:
    """Decode exact signed/selected bytes against a strictly parsed Core profile.

    Profile absence refuses by default. An explicit absence opt-in yields an
    unqualified candidate read whose semantic value cannot enter authority use.
    """
    declaration = parse_canonical_profile(
        raw_manifest_bytes,
        profile_model=CanonInfo,
        allow_profile_absent=allow_profile_absent,
    )
    read = decode_profiled_canonical_bytes(
        raw_payload_bytes,
        declaration,
        profile_model=CanonInfo,
        make_spec=_core_spec_from_profile,
        decode=lambda raw, max_depth: from_canonical_bytes(raw, max_depth=max_depth),
        encode=_encode_core_profiled_value,
    )
    return read


def read_core_json_artifact(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
    allow_profile_absent: bool = False,
) -> CanonicalProfileRead:
    """Read one selected Core JSON view through its raw and typed manifest boundary.

    Profile absence refuses by default. The explicit compatibility option is
    candidate-only; no path here labels a missing profile as historical.
    """
    get_bytes = getattr(store, "get_bytes", None)
    if not callable(get_bytes):
        raise CanonicalProfileRefusalError("canon_profile_payload_unavailable")
    typed_manifest, declaration = read_core_manifest_profile(
        store,
        selector,
        manifest_profile_sha256=manifest_profile_sha256,
        allow_profile_absent=allow_profile_absent,
    )
    selected_ref = artifact_ref_for_manifest(typed_manifest)
    if (
        manifest_profile_sha256 is not None
        and selected_ref.manifest_profile_sha256 != manifest_profile_sha256
    ):
        raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
    if isinstance(selector, ArtifactRef) and selector.manifest_profile_sha256 is not None:
        payload_selector: object = selector
    elif declaration.status != "absent" or manifest_profile_sha256 is not None:
        payload_selector = selected_ref
    else:
        # Unqualified compatibility is candidate-only; it does not establish history,
        # producer attestation, or a selected profile identity.
        payload_selector = selector
    if raw_payload_bytes is None:
        raw_payload_bytes = get_bytes(payload_selector)
        if declaration.status == "absent":
            latest_manifest, latest_declaration = read_core_manifest_profile(
                store,
                payload_selector,
                manifest_profile_sha256=manifest_profile_sha256,
                allow_profile_absent=allow_profile_absent,
            )
            if latest_manifest != typed_manifest or latest_declaration != declaration:
                raise CanonicalProfileRefusalError("canon_profile_selected_manifest_changed")
    if (
        type(raw_payload_bytes) is bytes
        and content_hash(raw_payload_bytes) != typed_manifest.artifact_id.hex
    ):
        raise CanonicalProfileRefusalError("canon_profile_selected_payload_identity_mismatch")
    read = decode_profiled_canonical_bytes(
        raw_payload_bytes,
        declaration,
        profile_model=CanonInfo,
        make_spec=_core_spec_from_profile,
        decode=lambda raw, max_depth: from_canonical_bytes(raw, max_depth=max_depth),
        encode=_encode_core_profiled_value,
    )
    return _bind_selected_artifact_identity(
        read,
        artifact_id=str(typed_manifest.artifact_id),
        manifest_profile_sha256=artifact_manifest_profile_sha256(typed_manifest),
    )


def load_core_json_artifact(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> Any:
    """Return only a selected Core JSON value whose declared profile conforms."""
    return require_declared_profile(
        read_core_json_artifact(
            store,
            selector,
            raw_payload_bytes=raw_payload_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )
    )


def read_core_json_artifact_bytes(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> bytes:
    """Verify a selected Core JSON byte view before a caller's typed decoder."""
    read = read_core_json_artifact(
        store,
        selector,
        raw_payload_bytes=raw_payload_bytes,
        manifest_profile_sha256=manifest_profile_sha256,
    )
    require_declared_profile(read)
    return read.raw_payload_bytes


def _without_annotated(annotation: Any) -> Any:
    """Strip validation metadata for shape adaptation; the model applies it once."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return _without_annotated(args[0])
    if not args:
        return annotation
    stripped = tuple(_without_annotated(argument) for argument in args)
    if origin is types.UnionType:
        result = stripped[0]
        for option in stripped[1:]:
            result = result | option
        return result
    try:
        return origin[stripped[0] if len(stripped) == 1 else stripped]
    except (AttributeError, TypeError):
        return annotation


def _core_type_adapter(annotation: Any, model_config: ConfigDict) -> TypeAdapter[Any]:
    """Build the public Pydantic adapter with the owning model's JSON settings."""
    annotation = _without_annotated(annotation)
    try:
        return TypeAdapter(annotation, config=model_config)
    except PydanticUserError:
        # BaseModel-containing annotations own their configuration on the model class.
        return TypeAdapter(annotation)


def _unwrap_annotated(annotation: Any) -> Any:
    """Return an annotation's structural type while leaving metadata on its adapter."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _base_model_type(annotation: Any) -> type[BaseModel] | None:
    """Return the BaseModel class at an annotation's structural root."""
    annotation = _unwrap_annotated(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _direct_alias_keys(alias: object) -> tuple[str, ...]:
    """Collect direct string aliases from a Pydantic alias or AliasChoices."""
    if isinstance(alias, str):
        return (alias,)
    choices = getattr(alias, "choices", ())
    if not isinstance(choices, (tuple, list)):
        return ()
    return tuple(key for choice in choices for key in _direct_alias_keys(choice))


_CORE_SCHEMA_WRAPPERS = frozenset(
    {
        "default",
        "function-after",
        "function-before",
        "function-wrap",
        "nullable",
    }
)


def _core_schema_model_type(
    schema: Any,
    definitions: Mapping[str, Any],
) -> type[BaseModel] | None:
    """Resolve one CoreSchema branch to its declared model class without validating it."""
    seen: set[str] = set()
    while isinstance(schema, Mapping):
        schema_type = schema.get("type")
        if schema_type == "definition-ref":
            reference = schema.get("schema_ref")
            if not isinstance(reference, str) or reference in seen:
                return None
            seen.add(reference)
            schema = definitions.get(reference)
            continue
        if schema_type in _CORE_SCHEMA_WRAPPERS:
            schema = schema.get("schema")
            continue
        if schema_type == "json-or-python":
            schema = schema.get("python_schema")
            continue
        if schema_type == "model":
            model = schema.get("cls")
            if isinstance(model, type) and issubclass(model, BaseModel):
                return model
            return None
        return None
    return None


def _core_schema_union_model_types(schema: Any) -> tuple[type[BaseModel], ...]:
    """Read declared model branches from one union annotation schema."""
    definitions: dict[str, Any] = {}
    while isinstance(schema, Mapping):
        schema_type = schema.get("type")
        if schema_type == "definitions":
            for definition in schema.get("definitions", ()):
                if isinstance(definition, Mapping):
                    reference = definition.get("ref")
                    if isinstance(reference, str):
                        definitions[reference] = definition
            schema = schema.get("schema")
            continue
        if schema_type in _CORE_SCHEMA_WRAPPERS:
            schema = schema.get("schema")
            continue
        if schema_type == "json-or-python":
            schema = schema.get("python_schema")
            continue
        break

    if not isinstance(schema, Mapping):
        return ()
    if schema.get("type") not in {"tagged-union", "union"}:
        model = _core_schema_model_type(schema, definitions)
        return (model,) if model is not None else ()
    choices = schema.get("choices")
    if isinstance(choices, Mapping):
        branch_values = tuple(choices.values())
    elif isinstance(choices, (tuple, list)):
        branch_values = tuple(
            choice[0] if isinstance(choice, tuple) else choice for choice in choices
        )
    else:
        return ()

    models: list[type[BaseModel]] = []
    for branch in branch_values:
        model = _core_schema_model_type(branch, definitions)
        if model is not None and model not in models:
            models.append(model)
    return tuple(models)


def _literal_values(annotation: Any) -> tuple[Any, ...]:
    """Return direct Literal values used as schema-discriminating descriptors."""
    annotation = _unwrap_annotated(annotation)
    return get_args(annotation) if get_origin(annotation) is Literal else ()


def _literal_wire_value(value: Any) -> Any:
    """Return the JSON-visible value of an Enum Literal without coercing its type."""
    return value.value if isinstance(value, Enum) else value


def _same_literal_value(candidate: Any, expected: Any) -> bool:
    """Compare one decoded JSON value to a declared Literal value strictly."""
    expected_wire = _literal_wire_value(expected)
    return type(candidate) is type(expected_wire) and candidate == expected_wire


def _model_field_keys(field_name: str, field: Any) -> tuple[str, ...]:
    """Collect the direct JSON keys accepted by one declared Pydantic field."""
    return tuple(
        dict.fromkeys(
            key
            for alias in (
                field.serialization_alias,
                field.alias,
                field.validation_alias,
                field_name,
            )
            for key in _direct_alias_keys(alias)
        )
    )


def _model_mapping_shape_matches(model: type[BaseModel], value: Mapping[Any, Any]) -> bool:
    """Check only required keys and extra-field policy; leave values for terminal validation."""
    if any(not isinstance(key, str) for key in value):
        return False
    allowed_keys: set[str] = set()
    for field_name, field in model.model_fields.items():
        field_keys = _model_field_keys(field_name, field)
        allowed_keys.update(field_keys)
        if field.is_required() and not any(key in value for key in field_keys):
            return False
    return not (model.model_config.get("extra") == "forbid" and set(value) - allowed_keys)


def _core_union_model_branch(
    schema: Any,
    models: tuple[type[BaseModel], ...],
    value: Mapping[Any, Any],
    *,
    discriminator: Any = None,
) -> type[BaseModel] | None:
    """Choose only a uniquely described union model; never validate a branch early."""
    if not models:
        return None

    schema_discriminator = (
        schema.get("discriminator")
        if isinstance(schema, Mapping) and schema.get("type") == "tagged-union"
        else None
    )
    explicit_discriminator = discriminator or schema_discriminator

    literal_descriptors: dict[tuple[str, type[Any], Any], set[type[BaseModel]]] = {}
    for model in models:
        for field_name, field in model.model_fields.items():
            values = _literal_values(field.annotation)
            if not values:
                continue
            for key in _model_field_keys(field_name, field):
                for literal in values:
                    wire_value = _literal_wire_value(literal)
                    try:
                        descriptor = (key, type(wire_value), wire_value)
                        literal_descriptors.setdefault(descriptor, set()).add(model)
                    except TypeError:
                        continue

    if isinstance(explicit_discriminator, str):
        if explicit_discriminator not in value:
            return None
        tag = value[explicit_discriminator]
        matches: set[type[BaseModel]] = set()
        for (key, _value_type, expected), owners in literal_descriptors.items():
            if key == explicit_discriminator and _same_literal_value(tag, expected):
                matches.update(owners)
        if len(matches) == 1:
            return next(iter(matches))
        return None

    unique_descriptors = {
        descriptor: next(iter(owners))
        for descriptor, owners in literal_descriptors.items()
        if len(owners) == 1
    }
    matched_models: set[type[BaseModel]] = set()
    for (key, _value_type, expected), model in unique_descriptors.items():
        if key in value and _same_literal_value(value[key], expected):
            matched_models.add(model)
    if len(matched_models) == 1:
        return next(iter(matched_models))
    if len(matched_models) > 1:
        raise _typed_union_refusal(
            value, "Core union input matches multiple unique Literal branches"
        )

    shape_matches = [model for model in models if _model_mapping_shape_matches(model, value)]
    if len(shape_matches) == 1:
        return shape_matches[0]
    return None


def _typed_union_refusal(value: Any, reason: str) -> ValidationError:
    """Create a normal Pydantic typed refusal for an ambiguous schema adaptation."""
    return ValidationError.from_exception_data(
        "Core typed union",
        [
            {
                "type": "value_error",
                "loc": (),
                "input": value,
                "ctx": {"error": ValueError(reason)},
            }
        ],
    )


def _core_model_payload(model: type[_ModelT], value: Any) -> Any:
    """Reify one Core-decoded model mapping without running validators early."""
    if issubclass(model, RootModel):
        root_field = model.model_fields["root"]
        return _core_typed_value(root_field.annotation, value, model.model_config)

    if not isinstance(value, Mapping):
        return value

    normalized = dict(value)
    for name, field in model.model_fields.items():
        candidates = tuple(
            dict.fromkeys(
                key
                for alias in (
                    field.serialization_alias,
                    field.alias,
                    field.validation_alias,
                    name,
                )
                for key in _direct_alias_keys(alias)
            )
        )
        present = [key for key in candidates if key in value]
        if len(present) > 1:
            raise ValueError(f"ambiguous Core JSON aliases for field {name!r}")
        if not present:
            continue
        source_key = present[0]
        typed_value = _core_typed_value(
            field.annotation,
            value[source_key],
            model.model_config,
            discriminator=field.discriminator,
        )
        if source_key != name:
            normalized.pop(source_key, None)
        normalized[name] = typed_value

    return normalized


def _contains_base_model(annotation: Any) -> bool:
    """Return whether an annotation contains a model that must wait for terminal validation."""
    if _base_model_type(annotation) is not None:
        return True
    return any(
        _contains_base_model(argument) for argument in get_args(_unwrap_annotated(annotation))
    )


def _core_typed_value(
    annotation: Any,
    value: Any,
    model_config: ConfigDict,
    *,
    discriminator: Any = None,
) -> Any:
    """Validate a decoded Core value using its declared Pydantic type and strict mode.

    Core's decoder has already reconstructed its declared native tags. This helper
    supplies the remaining JSON-to-Python shape adaptation (for example list to
    tuple and JSON strings to Enum/date/bytes fields) from the requested annotation.
    """
    model_type = _base_model_type(annotation)
    if model_type is not None:
        return _core_model_payload(model_type, value)

    adapter = _core_type_adapter(annotation, model_config)
    contains_model = _contains_base_model(annotation)
    python_error: ValidationError | None = None
    if not contains_model:
        try:
            return adapter.validate_python(value, strict=True)
        except ValidationError as exc:
            python_error = exc

    base = _unwrap_annotated(annotation)
    origin = get_origin(base)
    args = get_args(base)

    if origin in (Union, types.UnionType):
        if value is None:
            return None
        schema = adapter.core_schema
        model_options = _core_schema_union_model_types(schema)
        if isinstance(value, Mapping):
            model_option = _core_union_model_branch(
                schema,
                model_options,
                value,
                discriminator=discriminator,
            )
            if model_option is not None:
                return _core_model_payload(model_option, value)
        for option in args:
            if _contains_base_model(option):
                continue
            try:
                return _core_typed_value(option, value, model_config)
            except ValidationError:
                continue

    if origin is tuple and isinstance(value, (list, tuple)):
        if len(args) == 2 and args[1] is Ellipsis:
            item_annotations = (args[0],) * len(value)
            valid_shape = True
        elif len(args) == len(value):
            item_annotations = args
            valid_shape = True
        else:
            item_annotations = ()
            valid_shape = False
        if valid_shape:
            candidate = tuple(
                _core_typed_value(
                    item_annotation,
                    item,
                    model_config,
                    discriminator=discriminator,
                )
                for item_annotation, item in zip(item_annotations, value, strict=True)
            )
            return candidate if contains_model else adapter.validate_python(candidate, strict=True)

    if isinstance(origin, type) and issubclass(origin, Sequence) and isinstance(value, list):
        item_annotation = args[0] if args else Any
        sequence_candidate = [
            _core_typed_value(item_annotation, item, model_config, discriminator=discriminator)
            for item in value
        ]
        return (
            sequence_candidate
            if contains_model
            else adapter.validate_python(sequence_candidate, strict=True)
        )

    if isinstance(origin, type) and issubclass(origin, Mapping) and isinstance(value, Mapping):
        key_annotation, item_annotation = args if len(args) == 2 else (Any, Any)
        mapping_candidate = {
            _core_typed_value(
                key_annotation, key, model_config, discriminator=discriminator
            ): _core_typed_value(
                item_annotation,
                item,
                model_config,
                discriminator=discriminator,
            )
            for key, item in value.items()
        }
        return (
            mapping_candidate
            if contains_model
            else adapter.validate_python(mapping_candidate, strict=True)
        )

    if origin in (set, frozenset) and isinstance(value, (list, tuple, set, frozenset)):
        item_annotation = args[0] if args else Any
        items = (
            _core_typed_value(item_annotation, item, model_config, discriminator=discriminator)
            for item in value
        )
        set_candidate = set(items) if origin is set else frozenset(items)
        return (
            set_candidate if contains_model else adapter.validate_python(set_candidate, strict=True)
        )

    if contains_model:
        return value

    if python_error is None:
        return value
    if type(value) is float and _unwrap_annotated(annotation) is Decimal:
        # JSON parsing must not turn a forbidden decimal float into an accepted Decimal.
        raise python_error from None
    try:
        raw_json = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError):
        raise python_error from None
    try:
        return adapter.validate_json(raw_json, strict=True)
    except ValidationError:
        raise python_error from None


def validate_core_model_json_artifact(
    model: type[_ModelT],
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
    manifest_profile_sha256: str | None = None,
) -> _ModelT:
    """Strictly validate a Pydantic model after selected-profile byte admission."""
    manifest, _declaration = read_core_manifest_profile(
        store,
        selector,
        manifest_profile_sha256=manifest_profile_sha256,
    )
    selected_profile_sha256 = artifact_manifest_profile_sha256(manifest)
    _validate_model_artifact_manifest(model, manifest)
    read = read_core_json_artifact(
        store,
        selector,
        raw_payload_bytes=raw_payload_bytes,
        manifest_profile_sha256=selected_profile_sha256,
    )
    value = require_declared_profile(read)
    normalized = _core_model_payload(model, value)
    typed_model = model.model_validate(normalized, strict=True, by_alias=False, by_name=True)
    _validate_model_payload_schema_version(model, typed_model, manifest)
    return typed_model


def _validate_model_artifact_manifest(model: type[BaseModel], manifest: ArtifactManifest) -> None:
    """Require a declared typed-artifact owner ABI to match its selected manifest."""
    expected_kind = getattr(model, "ARTIFACT_KIND", None)
    if expected_kind is not None and manifest.kind != expected_kind:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_kind_mismatch")

    expected_media_type = getattr(model, "ARTIFACT_MEDIA_TYPE", None)
    if expected_media_type is not None and manifest.media_type != expected_media_type:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_media_type_mismatch")

    expected_schema_name = getattr(model, "ARTIFACT_SCHEMA_NAME", None)
    expected_schema_version = getattr(model, "ARTIFACT_SCHEMA_VERSION", None)
    schema = manifest.artifact_schema
    if expected_schema_name is not None and (schema is None or schema.name != expected_schema_name):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_name_mismatch")

    if expected_schema_version is not None:
        if not isinstance(expected_schema_version, str) or not expected_schema_version:
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
        if schema is None:
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_missing")
        declared_versions = getattr(model, "ARTIFACT_SCHEMA_VERSIONS", None)
        if declared_versions is None:
            supported_versions = {expected_schema_version}
            legacy_version = getattr(model, "LEGACY_ARTIFACT_SCHEMA_VERSION", None)
            if legacy_version is not None:
                if not isinstance(legacy_version, str) or not legacy_version:
                    raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
                supported_versions.add(legacy_version)
        else:
            if (
                not isinstance(declared_versions, (tuple, list, set, frozenset))
                or not declared_versions
                or any(not isinstance(value, str) or not value for value in declared_versions)
                or expected_schema_version not in declared_versions
            ):
                raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
            supported_versions = set(declared_versions)
        if schema.version not in supported_versions:
            raise CanonicalProfileRefusalError(
                "canon_profile_typed_artifact_schema_version_unsupported"
            )


def _validate_model_payload_schema_version(
    model: type[BaseModel],
    typed_model: BaseModel,
    manifest: ArtifactManifest,
) -> None:
    """Require payload and selected schema versions to follow the owner's exact relation."""
    schema = manifest.artifact_schema
    required_by_version = getattr(model, "ARTIFACT_REQUIRED_FIELDS_BY_SCHEMA_VERSION", {})
    if not isinstance(required_by_version, Mapping):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    for manifest_version, required_fields in required_by_version.items():
        if not isinstance(manifest_version, str) or not manifest_version:
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
        if not isinstance(required_fields, (tuple, list, set, frozenset)) or any(
            not isinstance(field_name, str) or not field_name for field_name in required_fields
        ):
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    if schema is not None and schema.version in required_by_version:
        for field_name in required_by_version[schema.version]:
            if (
                field_name not in model.model_fields
                or getattr(typed_model, field_name, None) is None
            ):
                raise CanonicalProfileRefusalError(
                    "canon_profile_typed_artifact_required_field_missing"
                )
    if "schema_version" not in model.model_fields:
        return
    current_version = getattr(model, "ARTIFACT_SCHEMA_VERSION", None)
    if current_version is None:
        return
    if not isinstance(current_version, str) or not current_version:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    schema = manifest.artifact_schema
    if schema is None:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_version_mismatch")
    declared_versions = getattr(model, "ARTIFACT_SCHEMA_VERSIONS", None)
    if declared_versions is None:
        supported_manifest_versions = {current_version}
        legacy_version = getattr(model, "LEGACY_ARTIFACT_SCHEMA_VERSION", None)
        if legacy_version is not None:
            supported_manifest_versions.add(legacy_version)
    else:
        if (
            not isinstance(declared_versions, (tuple, list, set, frozenset))
            or not declared_versions
            or any(not isinstance(value, str) or not value for value in declared_versions)
            or current_version not in declared_versions
        ):
            raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
        supported_manifest_versions = set(declared_versions)
    if schema.version not in supported_manifest_versions:
        raise CanonicalProfileRefusalError(
            "canon_profile_typed_artifact_schema_version_unsupported"
        )
    version_map = getattr(model, "ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST", {})
    if not isinstance(version_map, Mapping) or any(
        not isinstance(manifest_version, str)
        or not manifest_version
        or not isinstance(payload_version, str)
        or not payload_version
        or manifest_version not in supported_manifest_versions
        for manifest_version, payload_version in version_map.items()
    ):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    expected_payload_version = version_map.get(schema.version, schema.version)
    payload_version = getattr(typed_model, "schema_version", None)
    if not isinstance(payload_version, str) or payload_version != expected_payload_version:
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_schema_version_mismatch")


def _split_core_json_frames(payload: bytes) -> list[bytes]:
    """Split exact uint64 length-prefixed Core canonical JSON records."""
    if type(payload) is not bytes:
        raise CanonicalProfileRefusalError("canon_profile_payload_bytes_invalid")
    records: list[bytes] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 8:
            raise CanonicalProfileRefusalError("canon_frame_truncated_length")
        size = int.from_bytes(payload[offset : offset + 8], "big")
        offset += 8
        end = offset + size
        if end > len(payload):
            raise CanonicalProfileRefusalError("canon_frame_truncated_payload")
        records.append(payload[offset:end])
        offset = end
    if not records:
        raise CanonicalProfileRefusalError("canon_frame_empty")
    return records


def load_core_json_frame_records(
    store: object,
    selector: object,
    *,
    raw_payload_bytes: bytes | None = None,
) -> list[Any]:
    """Load selected Core JSON frames only after profile and byte conformance."""
    get_bytes = getattr(store, "get_bytes", None)
    if not callable(get_bytes):
        raise CanonicalProfileRefusalError("canon_profile_payload_unavailable")
    manifest, declaration = read_core_manifest_profile(store, selector)
    if declaration.status != "declared" or declaration.profile is None:
        raise CanonicalProfileRefusalError("canon_profile_not_verified")
    selected_ref = artifact_ref_for_manifest(manifest)
    payload = get_bytes(selected_ref) if raw_payload_bytes is None else raw_payload_bytes
    if type(payload) is not bytes or content_hash(payload) != manifest.artifact_id.hex:
        raise CanonicalProfileRefusalError("canon_profile_selected_payload_identity_mismatch")
    records = _split_core_json_frames(payload)
    values: list[Any] = []
    for raw_record in records:
        read = decode_profiled_canonical_bytes(
            raw_record,
            declaration,
            profile_model=CanonInfo,
            make_spec=_core_spec_from_profile,
            decode=lambda raw, max_depth: from_canonical_bytes(raw, max_depth=max_depth),
            encode=_encode_core_profiled_value,
        )
        values.append(require_declared_profile(read))
    return values


async def aload_core_json_artifact(
    store: object,
    selector: object,
) -> Any:
    """Asynchronously verify and decode one selected Core JSON artifact."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError

    raw_reader = getattr(store, "get_raw_manifest_bytes", None)
    manifest_reader = getattr(store, "get_manifest", None)
    payload_reader = getattr(store, "get_bytes", None)
    if not callable(raw_reader):
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable")
    if not callable(manifest_reader):
        raise CanonicalProfileRefusalError("canon_profile_typed_manifest_unavailable")
    if not callable(payload_reader):
        raise CanonicalProfileRefusalError("canon_profile_payload_unavailable")

    selected_profile = getattr(selector, "manifest_profile_sha256", None)
    try:
        raw_manifest = _require_exact_bytes(
            await raw_reader(selector), "canon_profile_raw_manifest_invalid"
        )
        declaration = parse_canonical_profile(
            raw_manifest,
            profile_model=CanonInfo,
            allow_profile_absent=False,
        )
        if declaration.status != "declared":
            raise CanonicalProfileRefusalError("canon_profile_not_verified")
        manifest = await manifest_reader(selector)
        payload = _require_exact_bytes(
            await payload_reader(selector), "canon_profile_payload_bytes_invalid"
        )
    except (AttributeError, NotImplementedError, TypeError) as exc:
        raise CanonicalProfileRefusalError("canon_profile_raw_manifest_unavailable") from exc

    class _PrefetchedAsyncView:
        def get_raw_manifest_bytes(self, _selector: object) -> bytes:
            return raw_manifest

        def get_manifest(self, _selector: object) -> object:
            return manifest

        def get_manifest_by_profile(self, _artifact_id: object, profile: str) -> object:
            if profile != selected_profile:
                raise CanonicalProfileRefusalError("canon_profile_selection_unverified")
            return manifest

        def get_bytes(self, _selector: object) -> bytes:
            return payload

    return read_core_json_artifact(
        _PrefetchedAsyncView(),
        selector,
        raw_payload_bytes=payload,
    ).value


__all__ = [
    "aload_core_json_artifact",
    "artifact_ref_for_manifest",
    "decode_core_json_payload",
    "load_core_json_artifact",
    "load_core_json_frame_records",
    "read_core_json_artifact",
    "read_core_json_artifact_bytes",
    "read_core_manifest_profile",
    "validate_core_model_json_artifact",
]
