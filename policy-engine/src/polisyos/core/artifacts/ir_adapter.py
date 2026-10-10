"""Bridge core artifact stores into the IR artifact-store protocol."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, cast, overload

from pydantic import BaseModel

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
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts._integrity_ops import VerificationReport
    from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore
    from polisyos.ir.artifacts import StorePutOptions
    from polisyos.ir.artifacts.contracts import ArtifactSelector
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
        model_fields = getattr(type(value), "model_fields", None)
        if isinstance(model_fields, Mapping):
            unexpected_fields = set(model_fields) - set(CoreArtifactRef.model_fields)
            if unexpected_fields:
                unexpected = ", ".join(sorted(unexpected_fields))
                raise TypeError(
                    f"Invalid Core artifact selector: unexpected field(s): {unexpected}"
                )
        return _coerce_payload(dumped)
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return _coerce_payload(asdict(value))
    if hasattr(value, "__dict__"):
        return _coerce_payload(vars(value))
    raise TypeError(f"Cannot coerce {type(value)!r} into adapter payload")


def _coerce_model(value: Any | None, model_type: type[Any], field_name: str) -> Any | None:
    if value is None or isinstance(value, model_type):
        return value
    try:
        return model_type.model_validate(_coerce_payload(value))
    except (TypeError, ValueError) as exc:
        raise TypeError(f"Invalid adapter option {field_name!r}") from exc


def _coerce_canon_option(value: Any | None, field_name: str) -> CanonInfo | None:
    """Refuse incomplete supplied profiles before model defaults apply."""
    if value is None or isinstance(value, CanonInfo):
        return value
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="python")
        if not isinstance(payload, Mapping):
            raise TypeError(f"Invalid adapter option {field_name!r}")
    else:
        payload = _coerce_payload(value)
    missing_fields = set(CanonInfo.model_fields) - set(payload)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise TypeError(
            f"Invalid adapter option {field_name!r}: incomplete canon profile ({missing})"
        )
    return _coerce_model(payload, CanonInfo, field_name)


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
    if isinstance(opts, ArtifactWriteOptions):
        return opts
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
    ) -> Any:
        import polisyos.ir.model_layer.canon as ir_canon

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
        return self.store.put_bytes(data, write_options)

    def put_bytes(
        self,
        data: bytes,
        opts: StorePutOptions | Mapping[str, Any] | ArtifactWriteOptions,
    ) -> CoreArtifactRef:
        """Persist caller-owned canonical bytes with the complete Core write options."""
        if not isinstance(data, bytes):
            raise TypeError("IR artifact bytes must be bytes")
        return self.store.put_bytes(data, _coerce_write_options(opts))

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

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        """Return the exact selected raw sidecar bytes from the wrapped Core owner."""
        reader = getattr(self.store, "get_manifest_bytes", None)
        if not callable(reader):
            raise TypeError("Core artifact store must expose get_manifest_bytes for IR reads")
        manifest_bytes = reader(_coerce_core_artifact_selector(artifact_id))
        if not isinstance(manifest_bytes, bytes):
            raise TypeError("Core get_manifest_bytes() must return bytes")
        return manifest_bytes

    def verify(self, artifact_id: ArtifactSelector) -> VerificationReport:
        """Verify a selector against its exact Core artifact and manifest view."""
        return self.store.verify(_coerce_core_artifact_selector(artifact_id))

    def iter_artifact_ids(self) -> list[Any]:
        return list(self.store.iter_artifact_ids())


@overload
def ensure_ir_artifact_store(store: CoreArtifactStore) -> CoreToIRArtifactStoreAdapter: ...


@overload
def ensure_ir_artifact_store(store: IRArtifactStore) -> IRArtifactStore: ...


def ensure_ir_artifact_store(store: IRArtifactStore | CoreArtifactStore) -> IRArtifactStore:
    """Return an IR-compatible store, wrapping core stores when needed."""

    if isinstance(store, CoreToIRArtifactStoreAdapter):
        return store
    from polisyos.core.artifacts.protocol import ArtifactStore as RuntimeCoreArtifactStore

    if isinstance(store, RuntimeCoreArtifactStore) or _matches_core_store_protocol(store):
        return CoreToIRArtifactStoreAdapter(cast("CoreArtifactStore", store))
    return store


def _matches_core_store_protocol(store: Any) -> bool:
    """Recognize Core stores behind dynamic facades that hide members from ``isinstance``.

    Timeout attempts wrap the shared store in a delegating facade. Python's
    runtime Protocol check inspects declared attributes statically, so it does
    not see that facade's ``__getattr__`` delegation and would otherwise pass
    the raw Core store into IR readers. Derive the required call surface from
    the Core protocol itself, then resolve those members dynamically.
    """
    from polisyos.core.artifacts.protocol import ArtifactStore as RuntimeCoreArtifactStore

    required_methods = tuple(
        name
        for name, member in vars(RuntimeCoreArtifactStore).items()
        if not name.startswith("_") and callable(member)
    )
    return bool(required_methods) and all(
        callable(getattr(store, name, None)) for name in required_methods
    )


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
