"""Bridge core artifact stores into the IR artifact-store protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast, overload

from .backends.config import ArtifactStoreConfig, build_artifact_store
from .ids import ArtifactID
from .manifest import ArtifactGovernanceInfo, CanonInfo, InputRef, SchemaInfo
from .write_contract import ArtifactWriteOptions

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
    from polisyos.core.canon.canon_json import CanonSpec as CoreCanonSpec
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore
    from polisyos.ir.artifacts import StorePutOptions
    from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec


def _coerce_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        if isinstance(dumped, dict):
            return dict(dumped)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError(f"Cannot coerce {type(value)!r} into adapter payload")


def _coerce_canon_spec(spec: IRCanonSpec | None) -> CoreCanonSpec | None:
    if spec is None:
        return None
    from polisyos.core.canon import CanonSpec as CoreCanonSpec

    payload = _coerce_payload(spec)
    return CoreCanonSpec(
        name=str(payload.get("name", "polisyos.canon.json")),
        version=str(payload.get("version", "0.2.0")),
        forbid_floats=bool(payload.get("forbid_floats", True)),
        forbid_nan_inf=bool(payload.get("forbid_nan_inf", True)),
        exclude_none=bool(payload.get("exclude_none", True)),
        max_depth=int(payload.get("max_depth", 128)),
        sort_keys=bool(payload.get("sort_keys", True)),
        separators=cast(
            "tuple[str, str]",
            tuple(payload.get("separators", (",", ":"))),
        ),
        ensure_ascii=bool(payload.get("ensure_ascii", False)),
    )


def _coerce_schema(schema: Any | None) -> SchemaInfo | None:
    if schema is None:
        return None
    if isinstance(schema, SchemaInfo):
        return schema
    return SchemaInfo.model_validate(_coerce_payload(schema))


def _coerce_inputs(inputs: Any | None) -> list[InputRef] | None:
    if not inputs:
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
    if isinstance(opts, ArtifactWriteOptions):
        return opts
    payload = _coerce_payload(opts)
    return ArtifactWriteOptions(
        kind=str(payload["kind"]),
        media_type=str(payload["media_type"]),
        schema=_coerce_schema(payload.get("schema")),
        producer=payload.get("producer"),
        env=payload.get("env"),
        inputs=_coerce_inputs(payload.get("inputs")),
        canon=_coerce_canon_info(payload.get("canon")),
        governance=_coerce_governance(payload.get("governance")),
    )


@dataclass(frozen=True, slots=True)
class CoreToIRArtifactStoreAdapter:
    """Adapt a core CAS store so IR helpers can consume it without concrete coupling."""

    store: CoreArtifactStore

    def put_json(
        self,
        obj: Any,
        opts: StorePutOptions | Any,
        canon_spec: IRCanonSpec | None = None,
    ) -> Any:
        return self.store.put_json(
            obj,
            _coerce_write_options(opts),
            canon_spec=_coerce_canon_spec(canon_spec),
        )

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
