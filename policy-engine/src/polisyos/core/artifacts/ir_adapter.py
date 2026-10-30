"""Bridge core artifact stores into the IR artifact-store protocol."""

from __future__ import annotations

import ast
import builtins as _builtins
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    TypeGuard,
    cast,
    get_args,
    get_origin,
    overload,
)

from pydantic import BaseModel, WithJsonSchema

from polisyos.common.canonical import _admit_canon_spec
from polisyos.common.canonical_profile import (
    _normalize_canonical_profile_mapping,
)

from .backends.config import ArtifactStoreConfig, build_artifact_store
from .ids import ArtifactID
from .manifest import (
    ArtifactAuthorityInfo,
    ArtifactChildReleaseInfo,
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    CanonInfo,
    EnvInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
    _canon_info_for_spec,
)
from .manifest import (
    ArtifactRef as CoreArtifactRef,
)
from .protocol import (
    RawManifestBytesReader,
    VerifiableArtifactReader,
    matches_runtime_protocol,
    matches_runtime_protocol_definition,
    runtime_protocol_requirements,
)
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts._integrity_ops import VerificationReport
    from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.ir import ArtifactSelector
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore
    from polisyos.ir.artifacts import StorePutOptions
    from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec


def _coerce_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        payload = dict(value)
        if not all(isinstance(key, str) for key in payload):
            raise TypeError("Adapter payload mapping keys must be strings")
        return payload
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        if not isinstance(dumped, Mapping):
            raise TypeError("Adapter model_dump() must return a mapping")
        return _coerce_payload(dumped)
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return _coerce_payload(asdict(value))
    if hasattr(value, "__dict__"):
        return _coerce_payload(vars(value))
    raise TypeError(f"Cannot coerce {type(value)!r} into adapter payload")


def _coerce_model(value: Any | None, model_type: type[Any], field_name: str) -> Any | None:
    if value is None:
        return None
    try:
        payload = (
            _pydantic_option_payload(value, field_name)
            if isinstance(value, BaseModel)
            else _coerce_payload(value)
        )
        payload = _coerce_nested_model_values(payload, field_name)
        return model_type.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Invalid adapter option {field_name!r}") from exc


def _pydantic_option_payload(value: BaseModel, field_name: str) -> dict[str, Any]:
    """Read stored model values without trusting a Pydantic instance's prior validation."""
    try:
        raw_fields = object.__getattribute__(value, "__dict__")
        model_fields = getattr(type(value), "model_fields", None)
        fields_set = object.__getattribute__(value, "__pydantic_fields_set__")
        extras = object.__getattribute__(value, "__pydantic_extra__")
    except AttributeError as exc:
        raise TypeError(f"Invalid adapter option {field_name!r}") from exc
    if (
        not isinstance(raw_fields, Mapping)
        or not isinstance(model_fields, Mapping)
        or not isinstance(fields_set, (set, frozenset))
        or not all(isinstance(name, str) for name in fields_set)
    ):
        raise TypeError(f"Invalid adapter option {field_name!r}")

    payload = dict(raw_fields)
    declared_fields = set(model_fields)
    if isinstance(extras, Mapping):
        payload.update(extras)
    elif extras is not None:
        raise TypeError(f"Invalid adapter option {field_name!r}")
    if not all(isinstance(name, str) for name in payload):
        raise TypeError(f"Invalid adapter option {field_name!r}")
    unexpected_fields = (set(payload) | set(fields_set)) - declared_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise TypeError(f"Invalid adapter option {field_name!r}: unexpected field(s) {unexpected}")
    return payload


def _coerce_nested_model_values(value: Any, field_name: str) -> Any:
    """Project nested Pydantic instances to raw values before model validation."""
    return _coerce_nested_value(value, field_name, set())


def _coerce_nested_value(value: Any, field_name: str, active_ids: set[int]) -> Any:
    """Recursively remove prevalidated model instances from an option payload."""
    if isinstance(value, BaseModel):
        value_id = id(value)
        if value_id in active_ids:
            raise TypeError(f"Cyclic adapter option {field_name!r}")
        active_ids.add(value_id)
        try:
            payload = _pydantic_option_payload(value, field_name)
            if getattr(type(value), "__pydantic_root_model__", False) is True:
                if "root" not in payload:
                    return payload
                root_value = _coerce_nested_value(payload["root"], field_name, active_ids)
                return type(value).model_validate(root_value)
            return {
                name: _coerce_nested_value(item, field_name, active_ids)
                for name, item in payload.items()
            }
        finally:
            active_ids.remove(value_id)

    if isinstance(value, Mapping):
        value_id = id(value)
        if value_id in active_ids:
            raise TypeError(f"Cyclic adapter option {field_name!r}")
        active_ids.add(value_id)
        try:
            return {
                name: _coerce_nested_value(item, field_name, active_ids)
                for name, item in value.items()
            }
        finally:
            active_ids.remove(value_id)

    if isinstance(value, (list, tuple)):
        value_id = id(value)
        if value_id in active_ids:
            raise TypeError(f"Cyclic adapter option {field_name!r}")
        active_ids.add(value_id)
        try:
            items = [_coerce_nested_value(item, field_name, active_ids) for item in value]
            return tuple(items) if isinstance(value, tuple) else items
        finally:
            active_ids.remove(value_id)

    return value


def _coerce_canon_option(value: Any | None, field_name: str) -> CanonInfo | None:
    """Strictly revalidate every canon carrier before comparing or persisting it."""
    if value is None:
        return None
    payload = (
        _pydantic_option_payload(value, field_name)
        if isinstance(value, BaseModel)
        else _coerce_payload(value)
    )
    missing_fields = set(CanonInfo.model_fields) - set(payload)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise TypeError(
            f"Invalid adapter option {field_name!r}: incomplete canon profile ({missing})"
        )
    payload = _normalize_canonical_profile_mapping(payload)
    try:
        return CanonInfo.model_validate(payload, strict=True)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Invalid adapter option {field_name!r}") from exc


def _coerce_model_list(
    value: Any | None,
    model_type: type[Any],
    field_name: str,
) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(value, Sequence):
        raise TypeError(f"Invalid adapter option {field_name!r}: expected a sequence")
    return [_coerce_model(item, model_type, field_name) for item in value]


def _required_option_text(value: Any | None, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"Adapter write option {field_name!r} must be a string")
    return value


_WRITE_OPTION_NORMALIZERS: dict[str, Any] = {
    "kind": _required_option_text,
    "media_type": _required_option_text,
    "schema": lambda value, name: _coerce_model(value, SchemaInfo, name),
    "producer": lambda value, name: _coerce_model(value, ProducerInfo, name),
    "env": lambda value, name: _coerce_model(value, EnvInfo, name),
    "inputs": lambda value, name: _coerce_model_list(value, InputRef, name),
    "canon": _coerce_canon_option,
    "governance": lambda value, name: _coerce_model(value, ArtifactGovernanceInfo, name),
    "tenant_context": lambda value, name: _coerce_model(value, ArtifactTenantContextInfo, name),
    "same_input_closure": lambda value, name: _coerce_model(
        value, ArtifactSameInputClosureInfo, name
    ),
    "authority": lambda value, name: _coerce_model(value, ArtifactAuthorityInfo, name),
    "child_release": lambda value, name: _coerce_model(value, ArtifactChildReleaseInfo, name),
    "warnings": lambda value, name: _coerce_model_list(value, WarningRecord, name),
}


def _coerce_write_options(
    opts: ArtifactWriteOptions | StorePutOptions | Mapping[str, Any],
) -> ArtifactWriteOptions:
    payload = _coerce_payload(opts)
    allowed_fields = set(_WRITE_OPTION_NORMALIZERS)
    if allowed_fields != set(ArtifactWriteOptions.__dataclass_fields__):
        raise RuntimeError("Core ArtifactWriteOptions changed without adapter projection support")
    unexpected_fields = set(payload) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise TypeError(f"Unexpected adapter write option field(s): {unexpected}")
    normalized = {
        field_name: normalize(payload.get(field_name), field_name)
        for field_name, normalize in _WRITE_OPTION_NORMALIZERS.items()
    }
    return ArtifactWriteOptions(**normalized)


def _coerce_core_artifact_selector(value: Any) -> ArtifactID | CoreArtifactRef:
    """Preserve an exact typed view while adapting an IR artifact selector."""
    if isinstance(value, ArtifactID):
        return value
    if isinstance(value, CoreArtifactRef):
        # A declared Core ref subtype can carry domain payload fields in
        # addition to the selector. Project only the actual base selector
        # schema so the IR boundary retains its strict foreign-object refusal
        # while preserving the selected profile, kind, and media type.
        raw_fields = object.__getattribute__(value, "__dict__")
        selector_payload = {
            name: raw_fields[name] for name in CoreArtifactRef.model_fields if name in raw_fields
        }
        try:
            return CoreArtifactRef.model_validate(selector_payload)
        except (TypeError, ValueError) as exc:
            raise TypeError("Invalid Core artifact selector") from exc
    if isinstance(value, str):
        return ArtifactID.model_validate(value)

    root_model = _is_string_root_model(value)
    if root_model and isinstance(value, BaseModel):
        original_snapshot = _core_string_root_snapshot(value)
        try:
            stored_id = ArtifactID.model_validate(original_snapshot[0])
        except (TypeError, ValueError) as exc:
            raise TypeError("Invalid Core artifact selector") from exc
        model_dump = getattr(value, "model_dump", None)
        if _core_string_root_snapshot(value) != original_snapshot:
            raise TypeError("Invalid Core artifact selector")
        if not callable(model_dump):
            raise TypeError("Invalid Core artifact selector")
        dumped = model_dump(mode="python")
        if _core_string_root_snapshot(value) != original_snapshot:
            raise TypeError("Invalid Core artifact selector")
        if type(dumped) is not str:
            raise TypeError("Invalid Core artifact selector")
        try:
            projected_id = ArtifactID.model_validate(dumped)
        except (TypeError, ValueError) as exc:
            raise TypeError("Invalid Core artifact selector") from exc
        if projected_id.root != stored_id.root:
            raise TypeError("Invalid Core artifact selector")
        return stored_id

    allowed_fields = frozenset({"root"}) if root_model else None
    original_selector_fields = _core_selector_public_fields(value)
    _refuse_unknown_core_selector_fields(
        value,
        selector_fields=original_selector_fields,
        allowed_fields=allowed_fields,
    )
    model_dump = getattr(value, "model_dump", None)
    # Attribute lookup may itself be caller-controlled. Preserve the pre-lookup snapshot and
    # reject any new fields before invoking a returned projection method.
    original_selector_fields |= _core_selector_public_fields(value)
    _refuse_unknown_core_selector_fields(
        value,
        selector_fields=original_selector_fields,
        allowed_fields=allowed_fields,
    )
    if callable(model_dump):
        dumped = model_dump(mode="python")
        original_selector_fields |= _core_selector_public_fields(value)
        _refuse_unknown_core_selector_fields(
            value,
            selector_fields=original_selector_fields,
            allowed_fields=allowed_fields,
        )
        if isinstance(dumped, str):
            if not root_model:
                raise TypeError("Invalid Core artifact selector")
            return ArtifactID.model_validate(dumped)
        if not isinstance(dumped, Mapping):
            raise TypeError("Invalid Core artifact selector")
        _refuse_unknown_core_selector_fields(dumped)
        value = dumped

    if (
        isinstance(value, Mapping)
        or hasattr(value, "__dataclass_fields__")
        or hasattr(value, "__dict__")
    ):
        try:
            if callable(model_dump):
                _refuse_unknown_core_selector_fields(value)
            else:
                _refuse_unknown_core_selector_fields(
                    value,
                    selector_fields=original_selector_fields,
                    allowed_fields=allowed_fields,
                )
            payload = _coerce_payload(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("Invalid Core artifact selector") from exc
        try:
            return CoreArtifactRef.model_validate(payload)
        except (TypeError, ValueError) as exc:
            raise TypeError("Invalid Core artifact selector") from exc

    # Protocol-only refs can expose the selector fields as properties without
    # a mapping/model payload. Derive that field set from the Core schema and
    # reject declared extensions instead of projecting a fixed key subset.
    selector_fields = CoreArtifactRef.model_fields
    required_fields = tuple(name for name, field in selector_fields.items() if field.is_required())
    if all(hasattr(value, name) for name in required_fields):
        _refuse_unknown_core_selector_fields(value)
        payload = {name: getattr(value, name) for name in selector_fields if hasattr(value, name)}
        try:
            return CoreArtifactRef.model_validate(payload)
        except (TypeError, ValueError) as exc:
            raise TypeError("Invalid Core artifact selector") from exc

    # Arbitrary objects are never stringified into IDs as a fallback.
    raise TypeError("Invalid Core artifact selector")


def _is_schema_only_string_annotation(annotation: Any) -> bool:
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


def _is_string_root_model(value: Any) -> bool:
    """Recognize exact Pydantic string roots, including the Core/IR ArtifactID ABI."""
    model_fields = getattr(type(value), "model_fields", None)
    root_field = model_fields.get("root") if isinstance(model_fields, Mapping) else None
    return (
        isinstance(value, BaseModel)
        and getattr(type(value), "__pydantic_root_model__", False) is True
        and isinstance(model_fields, Mapping)
        and set(model_fields) == {"root"}
        and _is_schema_only_string_annotation(getattr(root_field, "annotation", None))
    )


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


def _core_selector_public_fields(value: Any) -> frozenset[str]:
    """Inventory public selector fields without invoking a caller projection method."""
    supplied: set[str] = set()
    scalar_root_model = _is_string_root_model(value) and isinstance(value, BaseModel)
    if scalar_root_model:
        try:
            supplied.update(_pydantic_option_payload(value, "artifact selector"))
        except TypeError as exc:
            raise TypeError("Invalid Core artifact selector") from exc
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Invalid Core artifact selector")
        supplied.update(value)
    model_fields = getattr(type(value), "model_fields", None)
    if isinstance(model_fields, Mapping):
        supplied.update(model_fields)
    if hasattr(value, "__dict__"):
        supplied.update(name for name in vars(value) if not name.startswith("_"))
    if is_dataclass(value):
        supplied.update(item.name for item in fields(value) if not item.name.startswith("_"))
    for cls in type(value).__mro__:
        if cls is BaseModel:
            break
        annotations = cls.__dict__.get("__annotations__", {})
        class_vars = cls.__dict__.get("__class_vars__", ())
        if not isinstance(class_vars, (set, frozenset, tuple, list)):
            class_vars = ()
        supplied.update(
            name
            for name, annotation in annotations.items()
            if not name.startswith("_")
            and name not in class_vars
            and not _is_classvar_annotation(annotation)
        )
        if not scalar_root_model:
            supplied.update(
                name
                for name, member in cls.__dict__.items()
                if not name.startswith("_") and isinstance(member, property)
            )
        slots = cls.__dict__.get("__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        supplied.update(
            name for name in slots if isinstance(name, str) and not name.startswith("_")
        )
    return frozenset(supplied)


def _core_string_root_snapshot(value: BaseModel) -> tuple[str, frozenset[str]]:
    """Snapshot a typed scalar root from its stored Pydantic input fields."""
    try:
        payload = _pydantic_option_payload(value, "artifact selector")
    except TypeError as exc:
        raise TypeError("Invalid Core artifact selector") from exc
    if set(payload) != {"root"} or not isinstance(payload["root"], str):
        raise TypeError("Invalid Core artifact selector")
    root_text = _builtins.str.__str__(payload["root"])
    if type(root_text) is not str:
        raise TypeError("Invalid Core artifact selector")
    selector_fields = _core_selector_public_fields(value)
    _refuse_unknown_core_selector_fields(
        value,
        selector_fields=selector_fields,
        allowed_fields=frozenset({"root"}),
    )
    return root_text, selector_fields


def _refuse_unknown_core_selector_fields(
    value: Any,
    *,
    selector_fields: frozenset[str] | set[str] | None = None,
    allowed_fields: frozenset[str] | set[str] | None = None,
) -> None:
    """Reject every inventoried field outside Core ``ArtifactRef`` or a typed root."""
    supplied = (
        _core_selector_public_fields(value)
        if selector_fields is None
        else frozenset(selector_fields)
    )
    allowed = (
        frozenset(CoreArtifactRef.model_fields)
        if allowed_fields is None
        else frozenset(allowed_fields)
    )
    unexpected_fields = supplied - allowed
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise TypeError(f"Invalid Core artifact selector: unexpected field(s): {unexpected}")


def _snapshot_owned_write_options_for_ir(value: object) -> ArtifactWriteOptions:
    """Snapshot supported write DTOs or Mapping carriers without caller model dumps."""
    from polisyos.core.artifacts.manifest import (
        ArtifactAuthorityInfo,
        ArtifactEncryptionPolicyInfo,
        ArtifactGovernanceInfo,
        ArtifactRetentionPolicyInfo,
        ArtifactSameInputClosureInfo,
        ArtifactTenantContextInfo,
        EnvInfo,
        GitInfo,
        ProducerInfo,
        WarningRecord,
    )
    from polisyos.core.artifacts.manifest import (
        CanonInfo as CoreCanonInfo,
    )
    from polisyos.core.artifacts.manifest import (
        InputRef as CoreInputRef,
    )
    from polisyos.core.artifacts.manifest import (
        SchemaInfo as CoreSchemaInfo,
    )
    from polisyos.ir.artifacts import StorePutOptions

    model_fields: dict[type[BaseModel], dict[str, type[BaseModel]]] = {
        CoreSchemaInfo: {},
        CoreCanonInfo: {},
        ProducerInfo: {"git": GitInfo},
        GitInfo: {},
        EnvInfo: {},
        CoreInputRef: {},
        ArtifactGovernanceInfo: {
            "retention": ArtifactRetentionPolicyInfo,
            "encryption": ArtifactEncryptionPolicyInfo,
        },
        ArtifactRetentionPolicyInfo: {},
        ArtifactEncryptionPolicyInfo: {},
        ArtifactTenantContextInfo: {},
        ArtifactSameInputClosureInfo: {},
        ArtifactAuthorityInfo: {},
        ArtifactChildReleaseInfo: {},
        WarningRecord: {},
    }
    list_fields: dict[
        type[ArtifactWriteOptions] | type[StorePutOptions], dict[str, type[BaseModel]]
    ] = {
        ArtifactWriteOptions: {"inputs": CoreInputRef, "warnings": WarningRecord},
        StorePutOptions: {"inputs": CoreInputRef, "warnings": WarningRecord},
    }
    option_model_fields: dict[str, type[BaseModel]] = {
        "schema": CoreSchemaInfo,
        "producer": ProducerInfo,
        "env": EnvInfo,
        "canon": CoreCanonInfo,
        "governance": ArtifactGovernanceInfo,
        "tenant_context": ArtifactTenantContextInfo,
        "same_input_closure": ArtifactSameInputClosureInfo,
        "authority": ArtifactAuthorityInfo,
        "child_release": ArtifactChildReleaseInfo,
    }
    active_ids: set[int] = set()

    def snapshot_pairs(
        mapping: Mapping[object, object],
    ) -> tuple[tuple[object, object], ...]:
        try:
            return tuple(mapping.items())
        except Exception as exc:
            raise TypeError("Invalid owned artifact write options") from exc

    def snapshot_sequence(item: object) -> tuple[object, ...]:
        if isinstance(item, (str, bytes, bytearray, Mapping)) or not isinstance(item, Sequence):
            raise TypeError("Invalid owned artifact write options")
        try:
            return tuple(item)
        except Exception as exc:
            raise TypeError("Invalid owned artifact write options") from exc

    def pydantic_state_storage(
        item: BaseModel,
        raw: dict[str, object],
        name: str,
        value: object,
    ) -> str:
        from types import MemberDescriptorType

        effective_member = next(
            (cls.__dict__[name] for cls in type(item).__mro__ if name in cls.__dict__),
            None,
        )
        if type(effective_member) is MemberDescriptorType:
            if name in raw:
                raise TypeError("Invalid owned artifact write options")
            return "slot"
        if effective_member is None:
            if name in raw:
                if raw[name] is not value:
                    raise TypeError("Invalid owned artifact write options")
                return "dict"
            if value is None:
                return "class"
        raise TypeError("Invalid owned artifact write options")

    def snapshot_model_state(
        item: BaseModel,
        *,
        expected_type: type[BaseModel] | None = None,
        allow_extras: bool = False,
    ) -> tuple[
        tuple[tuple[object, object], ...],
        tuple[tuple[object, object], ...] | None,
        frozenset[str],
    ]:
        try:
            raw = object.__getattribute__(item, "__dict__")
            declared_fields = getattr(type(item), "model_fields", None)
            fields_set = object.__getattribute__(item, "__pydantic_fields_set__")
            extras = object.__getattribute__(item, "__pydantic_extra__")
        except AttributeError as exc:
            raise TypeError("Invalid owned artifact write options") from exc
        if (
            type(raw) is not dict
            or not isinstance(declared_fields, Mapping)
            or not isinstance(fields_set, (set, frozenset))
            or not all(type(name) is str for name in fields_set)
        ):
            raise TypeError("Invalid owned artifact write options")

        declared_name_values = tuple(declared_fields)
        if not all(type(name) is str for name in declared_name_values):
            raise TypeError("Invalid owned artifact write options")
        declared_names: frozenset[str] = frozenset(
            name for name in declared_name_values if type(name) is str
        )
        raw_names = frozenset(raw)
        if not all(type(name) is str for name in raw_names):
            raise TypeError("Invalid owned artifact write options")
        private = object.__getattribute__(item, "__pydantic_private__")
        state_values = {
            "__pydantic_fields_set__": fields_set,
            "__pydantic_extra__": extras,
            "__pydantic_private__": private,
        }
        raw_state_names = frozenset(
            name
            for name, state_value in state_values.items()
            if pydantic_state_storage(item, raw, name, state_value) == "dict"
        )
        raw_field_names = raw_names - raw_state_names
        if raw_state_names & declared_names or not raw_field_names <= declared_names:
            raise TypeError("Invalid owned artifact write options")
        if expected_type is not None:
            expected_fields = frozenset(expected_type.model_fields)
            if not declared_names <= expected_fields:
                raise TypeError("Invalid owned artifact write options")

        if extras is None:
            extra_pairs = None
            extra_names: frozenset[str] = frozenset()
        elif isinstance(extras, Mapping):
            extra_pairs = snapshot_pairs(extras)
            extra_name_values = frozenset(key for key, _ in extra_pairs)
            extra_name_set: set[str] = set()
            for name in extra_name_values:
                if type(name) is not str:
                    raise TypeError("Invalid owned artifact write options")
                extra_name_set.add(name)
            extra_names = frozenset(extra_name_set)
            if len(extra_names) != len(extra_pairs) or raw_field_names & extra_names:
                raise TypeError("Invalid owned artifact write options")
        else:
            raise TypeError("Invalid owned artifact write options")
        if extra_pairs and not allow_extras:
            raise TypeError("Invalid owned artifact write options")
        if not fields_set <= raw_names | extra_names:
            raise TypeError("Invalid owned artifact write options")
        raw_pairs = tuple(
            (name, nested) for name, nested in raw.items() if name not in raw_state_names
        )
        return raw_pairs, extra_pairs, frozenset(fields_set)

    def snapshot_json_model(
        item: BaseModel,
        pairs: tuple[tuple[object, object], ...],
        extra_pairs: tuple[tuple[object, object], ...] | None,
        fields_set: frozenset[str],
    ) -> BaseModel:
        from types import MemberDescriptorType

        raw_snapshot: dict[str, object] = {}
        for key, nested in pairs:
            if type(key) is not str or key in raw_snapshot:
                raise TypeError("Invalid owned artifact write options")
            raw_snapshot[key] = snapshot_json_value(nested)

        extra_snapshot: dict[str, object] | None = None
        if extra_pairs is not None:
            extra_snapshot = {}
            for key, nested in extra_pairs:
                if type(key) is not str or key in extra_snapshot:
                    raise TypeError("Invalid owned artifact write options")
                extra_snapshot[key] = snapshot_json_value(nested)

        private = object.__getattribute__(item, "__pydantic_private__")
        private_snapshot: dict[str, object] | None = None
        if private is not None:
            if not isinstance(private, Mapping):
                raise TypeError("Invalid owned artifact write options")
            declared_private = getattr(type(item), "__private_attributes__", None)
            if not isinstance(declared_private, Mapping):
                raise TypeError("Invalid owned artifact write options")
            private_snapshot = {}
            for key, nested in snapshot_pairs(private):
                if type(key) is not str or key not in declared_private or key in private_snapshot:
                    raise TypeError("Invalid owned artifact write options")
                private_snapshot[key] = snapshot_json_value(nested)

        slot_values: list[tuple[MemberDescriptorType, object]] = []
        for cls in type(item).__mro__:
            if cls is BaseModel or cls is object:
                break
            declared_slots = cls.__dict__.get("__slots__", ())
            if isinstance(declared_slots, str):
                slots = (declared_slots,)
            elif type(declared_slots) in (tuple, list, dict):
                slots = tuple(declared_slots)
            else:
                raise TypeError("Invalid owned artifact write options")
            for slot in slots:
                if type(slot) is not str:
                    raise TypeError("Invalid owned artifact write options")
                if slot in {
                    "__dict__",
                    "__weakref__",
                    "__pydantic_fields_set__",
                    "__pydantic_extra__",
                    "__pydantic_private__",
                }:
                    continue
                descriptor_name = slot
                if slot.startswith("__") and not slot.endswith("__"):
                    descriptor_name = f"_{cls.__name__.lstrip('_')}{slot}"
                descriptor = cls.__dict__.get(descriptor_name)
                if type(descriptor) is not MemberDescriptorType:
                    raise TypeError("Invalid owned artifact write options")
                try:
                    slot_value = descriptor.__get__(item, type(item))
                except AttributeError:
                    continue
                slot_values.append((descriptor, snapshot_json_value(slot_value)))

        copied = object.__new__(type(item))
        for name, source_value, snapshot_value in (
            (
                "__pydantic_fields_set__",
                object.__getattribute__(item, "__pydantic_fields_set__"),
                set(fields_set),
            ),
            (
                "__pydantic_extra__",
                object.__getattribute__(item, "__pydantic_extra__"),
                extra_snapshot,
            ),
            ("__pydantic_private__", private, private_snapshot),
        ):
            storage = pydantic_state_storage(
                item, object.__getattribute__(item, "__dict__"), name, source_value
            )
            if storage == "slot":
                descriptor = next(
                    cls.__dict__[name] for cls in type(item).__mro__ if name in cls.__dict__
                )
                descriptor.__set__(copied, snapshot_value)
            elif storage == "dict":
                raw_snapshot[name] = snapshot_value
        object.__setattr__(copied, "__dict__", raw_snapshot)
        for descriptor, slot_value in slot_values:
            descriptor.__set__(copied, slot_value)
        return copied

    def snapshot_json_value(item: object) -> object:
        if item is None or type(item) in (str, bool, int, float):
            return item
        if isinstance(item, BaseModel):
            identity = id(item)
            if identity in active_ids:
                raise TypeError("Invalid owned artifact write options")
            active_ids.add(identity)
            try:
                pairs, extra_pairs, fields_set = snapshot_model_state(item, allow_extras=True)
                return snapshot_json_model(item, pairs, extra_pairs, fields_set)
            finally:
                active_ids.remove(identity)
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in active_ids:
                raise TypeError("Invalid owned artifact write options")
            active_ids.add(identity)
            try:
                pairs = snapshot_pairs(item)
                output: dict[object, object] = {}
                for key, nested in pairs:
                    output[key] = snapshot_json_value(nested)
                if len(output) != len(pairs):
                    raise TypeError("Invalid owned artifact write options")
                return output
            except Exception as exc:
                raise TypeError("Invalid owned artifact write options") from exc
            finally:
                active_ids.remove(identity)
        if isinstance(item, str):
            text_value = _builtins.str.__str__(item)
            if type(text_value) is not str:
                raise TypeError("Invalid owned artifact write options")
            return text_value
        if isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray)):
            identity = id(item)
            if identity in active_ids:
                raise TypeError("Invalid owned artifact write options")
            active_ids.add(identity)
            try:
                return tuple(snapshot_json_value(nested) for nested in snapshot_sequence(item))
            finally:
                active_ids.remove(identity)
        return item

    def snapshot_model(item: object, expected_type: type[BaseModel]) -> dict[str, object]:
        if isinstance(item, BaseModel):
            pairs, extra_pairs, _fields_set = snapshot_model_state(
                item, expected_type=expected_type
            )
            if extra_pairs:
                raise TypeError("Invalid owned artifact write options")
        elif isinstance(item, Mapping):
            pairs = snapshot_pairs(item)
        else:
            raise TypeError("Invalid owned artifact write options")
        known_fields = expected_type.model_fields
        nested_models = model_fields[expected_type]
        output: dict[str, object] = {}
        for name, nested in pairs:
            if type(name) is not str or name not in known_fields or name in output:
                raise TypeError("Invalid owned artifact write options")
            if name in nested_models:
                output[name] = (
                    None if nested is None else snapshot_model(nested, nested_models[name])
                )
            else:
                output[name] = snapshot_json_value(nested)
        return output

    option_pairs: tuple[tuple[object, object], ...]
    if type(value) is ArtifactWriteOptions:
        option_type: type[ArtifactWriteOptions] | type[StorePutOptions] = ArtifactWriteOptions
        option_fields = ArtifactWriteOptions.__dataclass_fields__
        raw_options = object.__getattribute__(value, "__dict__")
        if type(raw_options) is not dict or set(raw_options) != set(option_fields):
            raise TypeError("Invalid owned artifact write options")
        option_pairs = tuple((name, object.__getattribute__(value, name)) for name in option_fields)
    elif type(value) is StorePutOptions:
        option_type = StorePutOptions
        option_fields = StorePutOptions.__dataclass_fields__
        raw_options = object.__getattribute__(value, "__dict__")
        if type(raw_options) is not dict or set(raw_options) != set(option_fields):
            raise TypeError("Invalid owned artifact write options")
        option_pairs = tuple((name, object.__getattribute__(value, name)) for name in option_fields)
    elif isinstance(value, Mapping):
        option_type = ArtifactWriteOptions
        option_fields = ArtifactWriteOptions.__dataclass_fields__
        option_pairs = snapshot_pairs(value)
    else:
        raise TypeError("Invalid owned artifact write options")

    raw_snapshot: dict[str, object] = {}
    for name, item in option_pairs:
        if type(name) is not str or name not in option_fields or name in raw_snapshot:
            raise TypeError("Invalid owned artifact write options")
        if name in list_fields[option_type]:
            item_type = list_fields[option_type][name]
            if item is None:
                raw_snapshot[name] = None
            elif not isinstance(item, (str, bytes, bytearray, Mapping)) and isinstance(
                item, Sequence
            ):
                children = [snapshot_model(child, item_type) for child in snapshot_sequence(item)]
                raw_snapshot[name] = tuple(children)
            else:
                raise TypeError("Invalid owned artifact write options")
        elif name in option_model_fields:
            expected_type = option_model_fields[name]
            raw_snapshot[name] = None if item is None else snapshot_model(item, expected_type)
        else:
            raw_snapshot[name] = snapshot_json_value(item)

    warning_values = raw_snapshot.get("warnings")
    validation_snapshot = {**raw_snapshot, "warnings": None}
    try:
        normalized = _coerce_write_options(validation_snapshot)
        if warning_values is None:
            return normalized
        if not isinstance(warning_values, (list, tuple)):
            raise TypeError("Invalid owned artifact write options")
        warnings = [WarningRecord.model_validate(item) for item in warning_values]
        return replace(normalized, warnings=warnings)
    except Exception as exc:
        raise TypeError("Invalid owned artifact write options") from exc


def _project_owned_write_options_for_ir(
    options: ArtifactWriteOptions,
) -> StorePutOptions:
    """Project normalized Core options into the complete neutral IR contract."""
    from polisyos.ir.artifacts.contracts import StorePutOptions

    if type(options) is not ArtifactWriteOptions:
        raise TypeError("Invalid Core owned write options")

    def project(value: Any) -> Any:
        if value is None or type(value) in (str, bool, int, float):
            return value
        if isinstance(value, BaseModel):
            dumped = value.model_dump(mode="json", by_alias=True, exclude_none=True)
            return project(dumped)
        if isinstance(value, Mapping):
            projected: dict[str, Any] = {}
            for key, item in value.items():
                if type(key) is not str or key in projected:
                    raise TypeError("Invalid Core owned write option mapping")
                projected[key] = project(item)
            return projected
        if type(value) in (list, tuple):
            return [project(item) for item in value]
        raise TypeError("Invalid Core owned write option value")

    projected_options: dict[str, Any] = {}
    for option_field in fields(ArtifactWriteOptions):
        projected_options[option_field.name] = project(getattr(options, option_field.name))
    return StorePutOptions(**projected_options)


def _preflight_owned_write_options_for_ir(
    options: ArtifactWriteOptions,
) -> StorePutOptions:
    try:
        return _project_owned_write_options_for_ir(options)
    except Exception as exc:
        raise TypeError("Invalid owned artifact write options") from exc


def _prepare_selected_core_write_options_for_ir(
    options: ArtifactWriteOptions,
) -> ArtifactWriteOptions:
    """Freeze the validated Core JSON projection before selected CAS emission."""
    projected = _preflight_owned_write_options_for_ir(options)
    try:
        return _coerce_write_options(projected)
    except Exception as exc:
        raise TypeError("Invalid owned artifact write options") from exc


def _emit_selected_core_write(
    store: Any,
    data: bytes,
    options: ArtifactWriteOptions,
) -> CoreArtifactRef:
    """Emit one selected write and reconcile its returned Core-owned manifest."""
    import hashlib
    from copy import deepcopy

    from polisyos.common.borrowed_execution import _OwnedEffectOutcomeUnknownError

    from ..run.child_custody import _ManagedStore
    from ._manifest_lifecycle import ManifestLifecycle

    if type(options) is not ArtifactWriteOptions:
        raise TypeError("Invalid Core owned write options")
    expected_options = deepcopy(options)
    write_options = options
    managed = type(store) is _ManagedStore
    if managed:
        # Only the exact Core custody owner can add a private marker and
        # normalize its selected inputs. A lookalike store cannot appoint it.
        write_options = replace(options, child_release=None)
        owner_options = store._options(write_options)
        if options.child_release is not None and options != owner_options:
            raise ValueError("artifact_write_managed_owner_options_mismatch")
        expected_options = owner_options
    ref = store.put_bytes(data, write_options, return_selected_profile=True)
    if type(ref) is not CoreArtifactRef:
        raise ValueError("artifact_write_selected_ref_invalid")
    if ref.manifest_profile_sha256 is None:
        raise ValueError("artifact_write_selected_profile_missing")
    expected_id = "sha256:" + hashlib.sha256(data).hexdigest()
    if (
        str(ref.artifact_id) != expected_id
        or ref.kind != expected_options.kind
        or ref.media_type != expected_options.media_type
    ):
        raise ValueError("artifact_write_selected_ref_mismatch")
    try:
        manifest = store.get_manifest(ref)
    except _OwnedEffectOutcomeUnknownError:
        raise
    except Exception as exc:
        raise ValueError("artifact_write_selected_manifest_unavailable") from exc
    if type(manifest) is not ArtifactManifest:
        raise ValueError("artifact_write_selected_manifest_invalid")
    if (
        str(manifest.artifact_id) != expected_id
        or ManifestLifecycle.profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise ValueError("artifact_write_selected_profile_mismatch")
    if managed:
        store._require_owned_release_profile(ref, manifest)
    for option_field in fields(ArtifactWriteOptions):
        name = option_field.name
        manifest_name = "artifact_schema" if name == "schema" else name
        if manifest_name not in type(manifest).model_fields:
            raise ValueError("artifact_write_selected_manifest_options_mismatch")
        expected = getattr(expected_options, name)
        actual = getattr(manifest, manifest_name)
        if name == "inputs":
            expected = list(expected or [])
        elif name == "warnings":
            expected = [
                warning.model_dump(mode="json", by_alias=True, exclude_none=True)
                for warning in expected or []
            ]
            actual = [
                warning.model_dump(mode="json", by_alias=True, exclude_none=True)
                for warning in actual or []
            ]
        if actual != expected:
            raise ValueError("artifact_write_selected_manifest_options_mismatch")
    return ref


@dataclass(frozen=True, slots=True)
class _CoreToIRArtifactReadMethods:
    """Adapt existing Core reads and exact selectors without writer capabilities."""

    store: VerifiableArtifactReader

    def get_bytes(self, artifact_id: ArtifactSelector | CoreArtifactRef) -> bytes:
        return self.store.get_bytes(_coerce_core_artifact_selector(artifact_id))

    def has(self, artifact_id: ArtifactSelector | CoreArtifactRef) -> bool:
        return self.store.has(_coerce_core_artifact_selector(artifact_id))

    def get_manifest(self, artifact_id: ArtifactSelector | CoreArtifactRef) -> ArtifactManifest:
        return self.store.get_manifest(_coerce_core_artifact_selector(artifact_id))

    def get_manifest_by_profile(
        self,
        artifact_id: ArtifactID | str,
        manifest_profile_sha256: str,
    ) -> ArtifactManifest:
        """Resolve a selected manifest view from its profile-bearing lineage edge."""
        aid = ArtifactID.model_validate(artifact_id)
        resolver = getattr(self.store, "get_manifest_by_profile", None)
        if callable(resolver):
            return ArtifactManifest.model_validate(resolver(aid, manifest_profile_sha256))
        manifest = ArtifactManifest.model_validate(self.store.get_manifest(aid))
        from ._manifest_lifecycle import ManifestLifecycle

        if ManifestLifecycle.profile_sha256(manifest) != manifest_profile_sha256:
            raise TypeError("Core artifact store cannot resolve a non-default manifest profile")
        return manifest

    def get_raw_manifest_bytes(
        self,
        artifact_id: ArtifactSelector | CoreArtifactRef,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        """Delegate exact raw sidecar access to the wrapped Core owner."""
        reader = getattr(self.store, "get_raw_manifest_bytes", None)
        if not callable(reader):
            raise TypeError("Core artifact store must expose get_raw_manifest_bytes for IR reads")
        selected = _coerce_core_artifact_selector(artifact_id)
        raw = reader(
            selected,
            **(
                {"manifest_profile_sha256": manifest_profile_sha256}
                if manifest_profile_sha256 is not None
                else {}
            ),
        )
        if not isinstance(raw, bytes):
            raise TypeError("Core get_raw_manifest_bytes() must return bytes")
        return raw

    def get_manifest_bytes(self, artifact_id: ArtifactSelector | CoreArtifactRef) -> bytes:
        """Return the exact selected raw sidecar bytes from the wrapped Core owner."""
        return self.get_raw_manifest_bytes(artifact_id)

    def verify(self, artifact_id: ArtifactSelector | CoreArtifactRef) -> VerificationReport:
        """Verify a selector against its exact Core artifact and manifest view."""
        return self.store.verify(_coerce_core_artifact_selector(artifact_id))


@dataclass(frozen=True, slots=True)
class _CoreToIRArtifactReaderAdapter(_CoreToIRArtifactReadMethods):
    """Admit an actual raw-capable Core reader without adding writable methods."""

    def __post_init__(self) -> None:
        if not (
            matches_runtime_protocol_definition(self.store, VerifiableArtifactReader)
            and matches_runtime_protocol_definition(self.store, RawManifestBytesReader)
        ):
            raise TypeError(
                "Core read-only IR adapter requires get_raw_manifest_bytes and verifiable reads"
            )


@dataclass(frozen=True, slots=True)
class CoreToIRArtifactStoreAdapter(_CoreToIRArtifactReadMethods):
    """Adapt a core CAS store so IR helpers can consume it without concrete coupling."""

    store: CoreArtifactStore

    def prepare_owned_write_options(self, options: object) -> StorePutOptions:
        """Return one detached, fully normalized Core write-options projection.

        Mapping carriers are snapshotted by the strict Core option normalizer once;
        concrete metadata validation and field ownership stay on the Core side.
        """
        normalized = _snapshot_owned_write_options_for_ir(options)
        from ..run.child_custody import _ManagedStore

        if type(self.store) is _ManagedStore:
            normalized = self.store._options(normalized)
        return _preflight_owned_write_options_for_ir(normalized)

    def put_json(
        self,
        obj: Any,
        opts: StorePutOptions | Mapping[str, Any] | ArtifactWriteOptions,
        canon_spec: IRCanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> Any:
        import polisyos.ir.model_layer.canon as ir_canon

        from .protocol import _validate_return_selected_profile

        _validate_return_selected_profile(return_selected_profile)
        spec = _admit_canon_spec(
            canon_spec,
            ir_canon.CanonSpec,
            violation_type=ir_canon.CanonViolation,
            artifact_writer=True,
        )
        if return_selected_profile:
            from .protocol import _require_return_selected_profile_writer

            _require_return_selected_profile_writer(self.store, "put_bytes")

        write_options = (
            _snapshot_owned_write_options_for_ir(opts)
            if return_selected_profile
            else _coerce_write_options(opts)
        )
        canon = _canon_info_for_spec(
            spec, write_options.canon, violation_type=ir_canon.CanonViolation
        )
        data = ir_canon.to_canonical_bytes(obj, spec)
        write_options = replace(
            write_options,
            media_type="application/json",
            canon=canon,
        )
        if return_selected_profile:
            write_options = _prepare_selected_core_write_options_for_ir(write_options)
            return _emit_selected_core_write(self.store, data, write_options)
        return self.store.put_bytes(data, write_options)

    def put_bytes(
        self,
        data: bytes,
        opts: StorePutOptions | Mapping[str, Any] | ArtifactWriteOptions,
        *,
        return_selected_profile: bool = False,
    ) -> CoreArtifactRef:
        """Persist caller-owned canonical bytes with complete Core write options."""
        from .protocol import _validate_return_selected_profile

        _validate_return_selected_profile(return_selected_profile)
        if return_selected_profile:
            from .protocol import _require_return_selected_profile_writer

            _require_return_selected_profile_writer(self.store, "put_bytes")
        if not isinstance(data, bytes):
            raise TypeError("IR artifact bytes must be bytes")
        write_options = (
            _snapshot_owned_write_options_for_ir(opts)
            if return_selected_profile
            else _coerce_write_options(opts)
        )
        if return_selected_profile:
            write_options = _prepare_selected_core_write_options_for_ir(write_options)
            return _emit_selected_core_write(self.store, data, write_options)
        return self.store.put_bytes(data, write_options)

    def iter_artifact_ids(self) -> list[Any]:
        return list(self.store.iter_artifact_ids())


@overload
def ensure_ir_artifact_store(
    store: CoreArtifactStore,
) -> CoreToIRArtifactStoreAdapter: ...


@overload
def ensure_ir_artifact_store(
    store: VerifiableArtifactReader,
) -> _CoreToIRArtifactReadMethods: ...


@overload
def ensure_ir_artifact_store(store: IRArtifactStore) -> IRArtifactStore: ...


def ensure_ir_artifact_store(
    store: IRArtifactStore | CoreArtifactStore | VerifiableArtifactReader,
) -> IRArtifactStore | _CoreToIRArtifactReadMethods:
    """Adapt Core read or write capabilities without upgrading a read-only owner."""

    if isinstance(store, (CoreToIRArtifactStoreAdapter, _CoreToIRArtifactReaderAdapter)):
        return store
    from polisyos.core.artifacts.protocol import ArtifactStore as RuntimeCoreArtifactStore

    def is_core_store(value: object) -> TypeGuard[CoreArtifactStore]:
        return matches_runtime_protocol_definition(value, RuntimeCoreArtifactStore)

    def is_core_reader(value: object) -> TypeGuard[VerifiableArtifactReader]:
        return matches_runtime_protocol_definition(value, VerifiableArtifactReader)

    if is_core_store(store):
        return CoreToIRArtifactStoreAdapter(store)
    if is_core_reader(store):
        return _CoreToIRArtifactReaderAdapter(store)
    return cast("IRArtifactStore", store)


def matches_artifact_store_protocol[ProtocolT](
    value: object,
    protocol: type[ProtocolT],
) -> TypeGuard[ProtocolT]:
    """Resolve a store Protocol through dynamic facades and adapter owners.

    ``GuardedDependencyProxy`` exposes methods dynamically through
    ``__getattr__``. Runtime ``isinstance`` checks inspect statically declared
    attributes and therefore reject that exact guarded handle. This resolver
    discovers every public requirement on the Protocol MRO, then resolves each
    member on the same object without unwrapping or replacing the facade.

    The Core-to-IR adapter has a stronger raw-manifest method of its own that
    delegates lazily. When the source Protocol requires that raw-reader method,
    inspect the adapter's real owner too; the adapter must not create a stronger
    capability merely by declaring a forwarding method.
    """
    candidate = value
    if (
        isinstance(value, _CoreToIRArtifactReadMethods)
        and runtime_protocol_requirements(protocol).get("get_raw_manifest_bytes") is True
    ):
        candidate = value.store
    return matches_runtime_protocol(candidate, protocol)


def build_ir_artifact_store(
    root: Path,
    *,
    metrics: MetricsRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
) -> IRArtifactStore:
    """Construct the default local IR-compatible CAS store for Scientist helpers."""

    return CoreToIRArtifactStoreAdapter(
        build_artifact_store(
            ArtifactStoreConfig(backend="filesystem", root=str(root)),
            metrics=metrics,
            tracer=tracer,
        )
    )


__all__ = [
    "CoreToIRArtifactStoreAdapter",
    "build_ir_artifact_store",
    "ensure_ir_artifact_store",
]
