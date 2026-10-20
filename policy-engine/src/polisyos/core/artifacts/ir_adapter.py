"""Bridge core artifact stores into the IR artifact-store protocol."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, TypeGuard, cast, overload

from pydantic import BaseModel

from polisyos.common.canonical_profile import (
    _normalize_canonical_profile_mapping,
)

from .backends.config import ArtifactStoreConfig, build_artifact_store
from .ids import ArtifactID
from .manifest import (
    ArtifactAuthorityInfo,
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
from .protocol import matches_runtime_protocol, runtime_protocol_requirements
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

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        if isinstance(dumped, str):
            if not _is_string_root_model(value):
                raise TypeError("Invalid Core artifact selector")
            return ArtifactID.model_validate(dumped)
        if not isinstance(dumped, Mapping):
            raise TypeError("Invalid Core artifact selector")
        _refuse_unknown_core_selector_fields(value)
        value = dumped

    if (
        isinstance(value, Mapping)
        or hasattr(value, "__dataclass_fields__")
        or hasattr(value, "__dict__")
    ):
        try:
            _refuse_unknown_core_selector_fields(value)
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


def _is_string_root_model(value: Any) -> bool:
    """Recognize exact Pydantic string roots, including the Core/IR ArtifactID ABI."""
    model_fields = getattr(type(value), "model_fields", None)
    root_field = model_fields.get("root") if isinstance(model_fields, Mapping) else None
    return (
        getattr(type(value), "__pydantic_root_model__", False) is True
        and isinstance(model_fields, Mapping)
        and set(model_fields) == {"root"}
        and getattr(root_field, "annotation", None) is str
    )


def _refuse_unknown_core_selector_fields(value: Any) -> None:
    """Reject every supplied or declared field outside Core ``ArtifactRef``."""
    allowed = set(CoreArtifactRef.model_fields)
    supplied: set[str] = set()
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Invalid Core artifact selector")
        supplied.update(value)
    model_fields = getattr(type(value), "model_fields", None)
    if isinstance(model_fields, Mapping):
        supplied.update(model_fields)
    if hasattr(value, "__dict__"):
        supplied.update(name for name in vars(value) if not name.startswith("_"))
    if hasattr(value, "__dataclass_fields__"):
        supplied.update(name for name in value.__dataclass_fields__ if not name.startswith("_"))
    for cls in type(value).__mro__:
        if cls is BaseModel:
            break
        supplied.update(
            name for name in cls.__dict__.get("__annotations__", {}) if not name.startswith("_")
        )
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
    unexpected_fields = supplied - allowed
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise TypeError(f"Invalid Core artifact selector: unexpected field(s): {unexpected}")


@dataclass(frozen=True, slots=True)
class CoreToIRArtifactStoreAdapter:
    """Adapt a core CAS store so IR helpers can consume it without concrete coupling."""

    store: CoreArtifactStore

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
        if return_selected_profile:
            from .protocol import _require_return_selected_profile_writer

            _require_return_selected_profile_writer(self.store, "put_bytes")

        spec = canon_spec or ir_canon.CanonSpec()
        write_options = _coerce_write_options(opts)
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
            ref = self.store.put_bytes(data, write_options, return_selected_profile=True)
            if ref.manifest_profile_sha256 is None:
                raise ValueError("artifact_write_selected_profile_missing")
            return ref
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
        write_options = _coerce_write_options(opts)
        if return_selected_profile:
            ref = self.store.put_bytes(data, write_options, return_selected_profile=True)
            if ref.manifest_profile_sha256 is None:
                raise ValueError("artifact_write_selected_profile_missing")
            return ref
        return self.store.put_bytes(data, write_options)

    def get_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        return self.store.get_bytes(_coerce_core_artifact_selector(artifact_id))

    def has(self, artifact_id: ArtifactSelector) -> bool:
        return self.store.has(_coerce_core_artifact_selector(artifact_id))

    def get_manifest(self, artifact_id: ArtifactSelector) -> Any:
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
        artifact_id: ArtifactSelector,
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

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        """Return the exact selected raw sidecar bytes from the wrapped Core owner."""
        return self.get_raw_manifest_bytes(artifact_id)

    def verify(self, artifact_id: ArtifactSelector) -> VerificationReport:
        """Verify a selector against its exact Core artifact and manifest view."""
        return self.store.verify(_coerce_core_artifact_selector(artifact_id))

    def iter_artifact_ids(self) -> list[Any]:
        return list(self.store.iter_artifact_ids())


@overload
def ensure_ir_artifact_store(
    store: CoreArtifactStore,
) -> CoreToIRArtifactStoreAdapter: ...


@overload
def ensure_ir_artifact_store(store: IRArtifactStore) -> IRArtifactStore: ...


def ensure_ir_artifact_store(
    store: IRArtifactStore | CoreArtifactStore,
) -> IRArtifactStore:
    """Return an IR-compatible store, wrapping core stores when needed."""

    if isinstance(store, CoreToIRArtifactStoreAdapter):
        return store
    from polisyos.core.artifacts.protocol import (
        ArtifactStore as RuntimeCoreArtifactStore,
    )

    if isinstance(store, RuntimeCoreArtifactStore) or matches_artifact_store_protocol(
        store, RuntimeCoreArtifactStore
    ):
        return CoreToIRArtifactStoreAdapter(cast("CoreArtifactStore", store))
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
        isinstance(value, CoreToIRArtifactStoreAdapter)
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
