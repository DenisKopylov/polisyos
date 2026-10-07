"""Bridge core artifact stores into the IR artifact-store protocol."""

from __future__ import annotations

from dataclasses import MISSING, dataclass, fields, is_dataclass, replace
from typing import TYPE_CHECKING, Any, overload

from .backends.config import ArtifactStoreConfig, build_artifact_store
from .ids import ArtifactID
from .manifest import (
    ArtifactAuthorityInfo,
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    CanonInfo,
    EnvInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
)
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore
    from polisyos.ir.artifacts import StorePutOptions
    from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec


def _coerce_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        if isinstance(dumped, dict):
            return dict(dumped)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Cannot coerce {type(value)!r} into adapter payload")


def _coerce_schema(schema: Any | None) -> SchemaInfo | None:
    if schema is None:
        return None
    if isinstance(schema, SchemaInfo):
        return schema
    return SchemaInfo.model_validate(_coerce_payload(schema))


def _coerce_model(model_type: type, value: Any | None) -> Any | None:
    if value is None or isinstance(value, model_type):
        return value
    return model_type.model_validate(_coerce_payload(value))


def _coerce_inputs(inputs: Any | None) -> list[InputRef] | None:
    if inputs is None:
        return None
    return [InputRef.model_validate(_coerce_payload(item)) for item in inputs]


def _coerce_canon_info(canon: Any | None) -> CanonInfo | None:
    if canon is None:
        return None
    if isinstance(canon, CanonInfo):
        return canon
    return CanonInfo.model_validate(_coerce_payload(canon))


def _coerce_governance(governance: Any | None) -> ArtifactGovernanceInfo | None:
    if governance is None:
        return None
    if isinstance(governance, ArtifactGovernanceInfo):
        return governance
    return ArtifactGovernanceInfo.model_validate(_coerce_payload(governance))


def _coerce_write_options(opts: Any) -> ArtifactWriteOptions:
    payload = _coerce_payload(opts)
    converters = {
        "schema": _coerce_schema,
        "producer": lambda value: _coerce_model(ProducerInfo, value),
        "env": lambda value: _coerce_model(EnvInfo, value),
        "inputs": _coerce_inputs,
        "canon": _coerce_canon_info,
        "governance": _coerce_governance,
        "tenant_context": lambda value: _coerce_model(ArtifactTenantContextInfo, value),
        "same_input_closure": lambda value: _coerce_model(ArtifactSameInputClosureInfo, value),
        "authority": lambda value: _coerce_model(ArtifactAuthorityInfo, value),
        "warnings": lambda values: (
            None if values is None else [_coerce_model(WarningRecord, value) for value in values]
        ),
    }
    options: dict[str, Any] = {}
    for field in fields(ArtifactWriteOptions):
        name = field.name
        if name in {"kind", "media_type"}:
            options[name] = str(payload[name])
            continue
        if name in payload:
            value = payload[name]
        elif field.default is not MISSING:
            value = field.default
        elif field.default_factory is not MISSING:
            value = field.default_factory()
        else:
            raise TypeError(f"IR write options are missing required Core field: {name}")
        converter = converters.get(name)
        options[name] = converter(value) if converter is not None else value
    return ArtifactWriteOptions(**options)


@dataclass(frozen=True, slots=True)
class CoreToIRArtifactStoreAdapter:
    """Adapt a core CAS store so IR helpers can consume it without concrete coupling."""

    store: CoreArtifactStore

    def put_bytes(
        self,
        data: bytes,
        opts: StorePutOptions | ArtifactWriteOptions,
    ) -> ArtifactRef:
        """Persist bytes with Core's typed manifest contract."""
        return self.store.put_bytes(data, _coerce_write_options(opts))

    def put_json(
        self,
        obj: Any,
        opts: StorePutOptions | Any,
        canon_spec: IRCanonSpec | None = None,
    ) -> Any:
        import polisyos.ir.model_layer.canon as ir_canon
        from polisyos.ir.artifacts.io import _put_canonical_json_bytes

        spec = canon_spec or ir_canon.CanonSpec()
        write_options = _coerce_write_options(opts)
        write_options = replace(
            write_options,
            media_type="application/json",
        )
        return _put_canonical_json_bytes(self, obj, write_options, spec)

    def get_bytes(self, artifact_id: Any) -> bytes:
        return self.store.get_bytes(ArtifactID.model_validate(str(artifact_id)))

    def get_manifest(self, artifact_id: Any) -> Any:
        return self.store.get_manifest(ArtifactID.model_validate(str(artifact_id)))

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
