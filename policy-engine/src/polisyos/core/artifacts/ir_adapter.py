"""Bridge core artifact stores into the IR artifact-store protocol."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, overload

from .backends.config import ArtifactStoreConfig, build_artifact_store
from .ids import ArtifactID
from .manifest import (
    ArtifactAuthorityInfo,
    ArtifactGovernanceInfo,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    CanonInfo,
    EnvInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
)
from .manifest import (
    ArtifactRef as CoreArtifactRef,
)
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from pathlib import Path

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
    "canon": lambda value, name: _coerce_model(value, CanonInfo, name),
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
    if isinstance(value, (ArtifactID, CoreArtifactRef)):
        return value
    if isinstance(value, Mapping):
        return CoreArtifactRef.model_validate(_coerce_payload(value))

    artifact_id = getattr(value, "artifact_id", None)
    kind = getattr(value, "kind", None)
    media_type = getattr(value, "media_type", None)
    if artifact_id is not None and kind is not None and media_type is not None:
        selector = {
            "artifact_id": artifact_id,
            "kind": kind,
            "media_type": media_type,
        }
        if hasattr(value, "manifest_profile_sha256"):
            selector["manifest_profile_sha256"] = value.manifest_profile_sha256
        return CoreArtifactRef.model_validate(selector)
    return ArtifactID.model_validate(str(value))


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
        data = ir_canon.to_canonical_bytes(obj, spec)
        write_options = _coerce_write_options(opts)
        write_options = replace(
            write_options,
            media_type="application/json",
            canon=write_options.canon or CanonInfo.from_spec(spec),
        )
        return self.store.put_bytes(data, write_options)

    def get_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        return self.store.get_bytes(_coerce_core_artifact_selector(artifact_id))

    def get_manifest(self, artifact_id: ArtifactSelector) -> Any:
        return self.store.get_manifest(_coerce_core_artifact_selector(artifact_id))

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes:
        """Return the exact selected raw sidecar bytes from the wrapped Core owner."""
        reader = getattr(self.store, "get_manifest_bytes", None)
        if not callable(reader):
            raise TypeError("Core artifact store must expose get_manifest_bytes for IR reads")
        manifest_bytes = reader(_coerce_core_artifact_selector(artifact_id))
        if not isinstance(manifest_bytes, bytes):
            raise TypeError("Core get_manifest_bytes() must return bytes")
        return manifest_bytes

    def iter_artifact_ids(self) -> list[Any]:
        return list(self.store.iter_artifact_ids())


@overload
def ensure_ir_artifact_store(store: IRArtifactStore) -> IRArtifactStore: ...


@overload
def ensure_ir_artifact_store(store: CoreArtifactStore) -> IRArtifactStore: ...


def ensure_ir_artifact_store(store: IRArtifactStore | CoreArtifactStore) -> IRArtifactStore:
    """Return an IR-compatible store, wrapping core stores when needed."""

    if isinstance(store, CoreToIRArtifactStoreAdapter):
        return store
    from polisyos.core.artifacts.protocol import ArtifactStore as RuntimeCoreArtifactStore

    if isinstance(store, RuntimeCoreArtifactStore):
        return CoreToIRArtifactStoreAdapter(store)
    return store


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
