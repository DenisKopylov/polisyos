from __future__ import annotations

import asyncio
from collections.abc import Iterator, Mapping
from contextlib import nullcontext
from dataclasses import fields
from decimal import Decimal
from typing import ClassVar

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts import (
    CanonInfo,
    FileSystemCAS,
    PutOptions,
    read_core_json_artifact,
)
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
)
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.backends.gcs_store import GCSArtifactStore
from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.canon import CanonSpec, CanonViolation, to_canonical_bytes
from polisyos.core.security.namespace import NamespacedArtifactStore
from polisyos.fabric.storage.tenant_cas import TenantScopedCAS
from polisyos.ir.artifacts.io import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
from polisyos.ir.model_layer.canon import CanonViolation as IRCanonViolation


class _ProjectionSpy(BaseModel):
    value: int
    events: ClassVar[list[str]] = []

    def model_dump(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.events.append("projection")
        return super().model_dump(*args, **kwargs)


class _TraversalSpy(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        _ProjectionSpy.events.append("mapping-get")
        raise AssertionError(key)

    def __iter__(self) -> Iterator[str]:
        _ProjectionSpy.events.append("mapping-iterate")
        raise AssertionError("mapping was traversed")

    def __len__(self) -> int:
        _ProjectionSpy.events.append("mapping-length")
        raise AssertionError("mapping length was read")


class _DecimalSpy(Decimal):
    def __str__(self) -> str:
        _ProjectionSpy.events.append("decimal-expand")
        return super().__str__()


class _Sink:
    def __init__(self) -> None:
        self.events: list[str] = []

    def put_json(self, *_args: object, **_kwargs: object) -> object:
        self.events.append("json")
        return object()

    def put_bytes(self, *_args: object, **_kwargs: object) -> object:
        self.events.append("bytes")
        return object()


@pytest.fixture(autouse=True)
def _reset_projection_spy() -> None:
    _ProjectionSpy.events.clear()


@pytest.mark.parametrize("backend", ["filesystem", "s3", "gcs"])
@pytest.mark.parametrize("payload", ["model", "mapping", "decimal"])
def test_concrete_json_writers_refuse_v3_before_projection_or_emission(
    backend: str, payload: str, tmp_path, monkeypatch
) -> None:
    if backend == "filesystem":
        store = FileSystemCAS(tmp_path / "cas")
    elif backend == "s3":
        store = S3ArtifactStore.__new__(S3ArtifactStore)
    else:
        store = GCSArtifactStore.__new__(GCSArtifactStore)
    emissions: list[object] = []
    monkeypatch.setattr(store, "put_bytes", lambda *args, **kwargs: emissions.append(args))
    value: object = {
        "model": lambda: _ProjectionSpy(value=7),
        "mapping": _TraversalSpy,
        "decimal": lambda: _DecimalSpy("7.5"),
    }[payload]()

    with pytest.raises(CanonViolation, match="canonical_writer_profile_unavailable"):
        store.put_json(
            value,
            PutOptions(kind="test.v3", media_type="application/json"),
            CanonSpec(version="0.3.0"),
        )

    assert _ProjectionSpy.events == []
    assert emissions == []


def test_core_v2_real_store_still_projects_and_reads_fresh(tmp_path) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    ref = store.put_json(
        _ProjectionSpy(value=7),
        PutOptions(kind="test.v2", media_type="application/json"),
        CanonSpec(),
    )
    assert _ProjectionSpy.events
    assert FileSystemCAS(root).get_bytes(ref) == b'{"value":7}'


def test_ir_adapter_and_ir_helper_refuse_v3_before_projection_or_store() -> None:
    sink = _Sink()
    adapter = CoreToIRArtifactStoreAdapter(store=sink)
    options = PutOptions(kind="test.ir", media_type="application/json")
    with pytest.raises(IRCanonViolation, match="canonical_writer_profile_unavailable"):
        adapter.put_json(_ProjectionSpy(value=7), options, IRCanonSpec(version="0.3.0"))
    with pytest.raises(IRCanonViolation, match="canonical_writer_profile_unavailable"):
        put_json_artifact(
            adapter,
            _ProjectionSpy(value=7),
            kind="test.ir",
            schema_name="test",
            schema_version="1",
            canon_spec=IRCanonSpec(version="0.3.0"),
        )
    assert _ProjectionSpy.events == []
    assert sink.events == []


def test_ir_adapter_v2_reuses_real_store(tmp_path) -> None:
    root = tmp_path / "cas"
    adapter = CoreToIRArtifactStoreAdapter(store=FileSystemCAS(root))
    ref = adapter.put_json(
        {"value": 7},
        PutOptions(kind="test.ir", media_type="application/json"),
        IRCanonSpec(),
    )
    assert FileSystemCAS(root).get_bytes(ref) == b'{"value":7}'


def test_ir_adapter_admits_spec_before_selected_writer_preflight() -> None:
    spec = IRCanonSpec()
    observations: list[tuple[bytes, str]] = []

    class _EmissionReachedError(Exception):
        pass

    class _Store:
        @property
        def put_bytes(self):
            object.__setattr__(spec, "version", "0.3.0")

            def emit(data, opts, *, return_selected_profile=False):
                observations.append((data, opts.canon.version))
                raise _EmissionReachedError

            return emit

    adapter = CoreToIRArtifactStoreAdapter(store=_Store())
    options = PutOptions(kind="test.ir-spec", media_type="application/json")
    with pytest.raises(_EmissionReachedError):
        adapter.put_json({"value": 7}, options, spec, return_selected_profile=True)
    assert spec.version == "0.3.0"
    assert observations == [(b'{"value":7}', "0.2.0")]


def test_ir_adapter_refuses_v3_before_selected_writer_lookup() -> None:
    events: list[str] = []

    class _Store:
        @property
        def put_bytes(self):
            events.append("lookup")
            raise AssertionError("writer preflight ran")

    with pytest.raises(IRCanonViolation, match="canonical_writer_profile_unavailable"):
        CoreToIRArtifactStoreAdapter(store=_Store()).put_json(
            {"value": 7},
            PutOptions(kind="test.ir-spec", media_type="application/json"),
            IRCanonSpec(version="0.3.0"),
            return_selected_profile=True,
        )
    assert events == []


@pytest.mark.parametrize("owner", ["core", "ir"])
def test_callback_cannot_change_the_admitted_writer_profile(owner: str, tmp_path) -> None:
    spec = CanonSpec() if owner == "core" else IRCanonSpec()

    class _MutatingModel(BaseModel):
        def model_dump(self, *args: object, **kwargs: object) -> dict[str, str]:
            object.__setattr__(spec, "version", "0.3.0")
            return {"_type": "decimal", "value": "1.0"}

    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    options = PutOptions(kind="test.spec-snapshot", media_type="application/json")
    if owner == "core":
        ref = store.put_json(_MutatingModel(), options, spec)
    else:
        ref = CoreToIRArtifactStoreAdapter(store=store).put_json(_MutatingModel(), options, spec)
    fresh = FileSystemCAS(root)
    assert fresh.get_bytes(ref) == b'{"_type":"decimal","value":"1.0"}'
    assert fresh.get_manifest(ref).canon.version == "0.2.0"


@pytest.mark.parametrize("wrapper", ["cache", "namespace", "tenant"])
def test_sync_wrappers_refuse_v3_before_their_wrapped_store(wrapper: str) -> None:
    sink = _Sink()
    if wrapper == "cache":
        store = CachingArtifactStore(remote=sink, local=sink, write_through=True)
    elif wrapper == "namespace":
        store = NamespacedArtifactStore(sink, tenant_id="test")
    else:
        # The refusal must occur before quota admission needs any tenant state.
        store = TenantScopedCAS.__new__(TenantScopedCAS)
    with pytest.raises(CanonViolation, match="canonical_writer_profile_unavailable"):
        store.put_json(
            _ProjectionSpy(value=7),
            PutOptions(kind="test.wrapper", media_type="application/json"),
            CanonSpec(version="0.3.0"),
        )
    assert _ProjectionSpy.events == []
    assert sink.events == []


@pytest.mark.parametrize("wrapper", [AsyncArtifactStoreAdapter, AsyncFileSystemArtifactStore])
def test_async_wrappers_refuse_v3_before_scheduling_wrapped_store(
    wrapper: type,
) -> None:
    sink = _Sink()
    store = wrapper(store=sink)
    with pytest.raises(CanonViolation, match="canonical_writer_profile_unavailable"):
        asyncio.run(
            store.put_json(
                _ProjectionSpy(value=7),
                PutOptions(kind="test.async", media_type="application/json"),
                CanonSpec(version="0.3.0"),
            )
        )
    assert _ProjectionSpy.events == []
    assert sink.events == []


@pytest.mark.parametrize("wrapper", ["cache", "namespace", "tenant", "async", "async-fs"])
def test_forwarders_freeze_the_admitted_spec_before_wrapped_preflight(
    wrapper: str, monkeypatch
) -> None:
    spec = CanonSpec()
    observed_versions: list[str] = []

    class _EmissionReachedError(Exception):
        pass

    class _MutatingStore:
        @property
        def put_json(self):
            object.__setattr__(spec, "version", "0.3.0")

            def write(_obj, opts, canon_spec, *, return_selected_profile=False):
                observed_versions.append(canon_spec.version)
                raise _EmissionReachedError

            return write

    wrapped = _MutatingStore()
    options = PutOptions(kind="test.forwarded-spec", media_type="application/json")
    if wrapper == "cache":
        store = CachingArtifactStore(remote=wrapped, local=wrapped, write_through=False)
    elif wrapper == "namespace":
        store = NamespacedArtifactStore(wrapped, tenant_id="test")
    elif wrapper == "tenant":
        store = TenantScopedCAS.__new__(TenantScopedCAS)
        store._cas = wrapped
        monkeypatch.setattr(store, "_storage_mutation", lambda: nullcontext())
    elif wrapper == "async":
        store = AsyncArtifactStoreAdapter(store=wrapped)
    else:
        store = AsyncFileSystemArtifactStore(store=wrapped)

    with pytest.raises(_EmissionReachedError):
        result = store.put_json({"value": 7}, options, spec, return_selected_profile=True)
        if wrapper in {"async", "async-fs"}:
            asyncio.run(result)
    assert spec.version == "0.3.0"
    assert observed_versions == ["0.2.0"]


@pytest.mark.parametrize(
    "surface",
    [
        "filesystem",
        "s3",
        "gcs",
        "ir-adapter",
        "ir-io",
        "cache",
        "namespace",
        "tenant",
        "async",
        "async-fs",
    ],
)
@pytest.mark.parametrize("carrier", ["separator-subclass", "spec-accessor"])
def test_unadmitted_writer_spec_never_calls_untrusted_carriers(
    surface: str, carrier: str, tmp_path
) -> None:
    events: list[str] = []

    class _SeparatorTrap(tuple):
        def __iter__(self):
            events.append("separators")
            raise AssertionError("untrusted separator iterator ran")

    class _CoreSpecTrap(CanonSpec):
        def __getattribute__(self, name: str):
            events.append("spec-access")
            raise AssertionError(f"untrusted spec accessor ran: {name}")

    class _IRSpecTrap(IRCanonSpec):
        def __getattribute__(self, name: str):
            events.append("spec-access")
            raise AssertionError(f"untrusted spec accessor ran: {name}")

    ir_surface = surface in {"ir-adapter", "ir-io"}
    spec_type = IRCanonSpec if ir_surface else CanonSpec
    if carrier == "separator-subclass":
        spec = spec_type(version="0.3.0", separators=_SeparatorTrap((",", ":")))
        expected_error = "canonical_spec_invalid"
    else:
        spec = (_IRSpecTrap if ir_surface else _CoreSpecTrap)(version="0.3.0")
        expected_error = "canonical_writer_profile_unavailable"

    sink = _Sink()
    opts = PutOptions(kind="test.config", media_type="application/json")
    if surface == "filesystem":
        store = FileSystemCAS(tmp_path / "cas")
    elif surface == "s3":
        store = S3ArtifactStore.__new__(S3ArtifactStore)
    elif surface == "gcs":
        store = GCSArtifactStore.__new__(GCSArtifactStore)
    elif surface in {"ir-adapter", "ir-io"}:
        store = CoreToIRArtifactStoreAdapter(store=sink)
    elif surface == "cache":
        store = CachingArtifactStore(remote=sink, local=sink)
    elif surface == "namespace":
        store = NamespacedArtifactStore(sink, tenant_id="test")
    elif surface == "tenant":
        store = TenantScopedCAS.__new__(TenantScopedCAS)
    elif surface == "async":
        store = AsyncArtifactStoreAdapter(store=sink)
    else:
        store = AsyncFileSystemArtifactStore(store=sink)

    with pytest.raises(ValueError, match=expected_error):
        if surface == "ir-io":
            put_json_artifact(
                store,
                _ProjectionSpy(value=7),
                kind="test.config",
                schema_name="test",
                schema_version="1",
                canon_spec=spec,
            )
        else:
            result = store.put_json(_ProjectionSpy(value=7), opts, spec)
            if surface in {"async", "async-fs"}:
                asyncio.run(result)
    assert events == []
    assert _ProjectionSpy.events == []
    assert sink.events == []


def test_every_declared_spec_field_refuses_a_nonprimitive_before_projection(tmp_path) -> None:
    malformed: dict[str, object] = {
        "name": object(),
        "version": object(),
        "forbid_floats": 1,
        "forbid_nan_inf": 1,
        "exclude_none": 1,
        "max_depth": True,
        "sort_keys": 1,
        "separators": [",", ":"],
        "ensure_ascii": 1,
    }
    assert set(malformed) == {field.name for field in fields(CanonSpec)}
    store = FileSystemCAS(tmp_path / "cas")
    opts = PutOptions(kind="test.invalid-config", media_type="application/json")
    for name, value in malformed.items():
        spec = CanonSpec(**{name: value})
        with pytest.raises(CanonViolation, match="canonical_spec_invalid"):
            store.put_json(_ProjectionSpy(value=7), opts, spec)
    assert _ProjectionSpy.events == []
    assert store.iter_artifact_ids() == []


@pytest.mark.parametrize("surface", ["core", "ir-adapter", "ir-io"])
def test_admission_does_not_call_caller_metaclass_equality(surface: str, tmp_path) -> None:
    events: list[str] = []

    class _EqualityTrap(type):
        def __eq__(cls, other: object) -> bool:
            events.append("metaclass-equality")
            raise AssertionError("caller metaclass equality ran")

    class _CoreSpecTrap(CanonSpec, metaclass=_EqualityTrap):
        pass

    class _IRSpecTrap(IRCanonSpec, metaclass=_EqualityTrap):
        pass

    sink = _Sink()
    if surface == "core":
        store = FileSystemCAS(tmp_path / "cas")
        spec = _CoreSpecTrap(version="0.3.0")
    else:
        store = CoreToIRArtifactStoreAdapter(store=sink)
        spec = _IRSpecTrap(version="0.3.0")

    with pytest.raises(ValueError, match="canonical_writer_profile_unavailable"):
        if surface == "ir-io":
            put_json_artifact(
                store,
                {"value": 7},
                kind="test.metaclass",
                schema_name="test",
                schema_version="1",
                canon_spec=spec,
            )
        else:
            store.put_json(
                {"value": 7}, PutOptions(kind="test.metaclass", media_type="application/json"), spec
            )
    assert events == []
    assert sink.events == []


def test_raw_v3_import_uses_selected_reader_without_granting_authority(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    raw = b'{"candidate":true}'
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.raw",
            media_type="application/json",
            canon=CanonInfo(version="0.3.0"),
        ),
    )
    read = read_core_json_artifact(store, ref)
    assert read.status == "declared_bytes_conformant"
    assert read.value == {"candidate": True}
    assert read.reader_policy_id == "core-tag-policy@2"


def test_fresh_selected_v3_reader_preserves_raw_type_mapping_from_real_cas(tmp_path) -> None:
    root = tmp_path / "cas"
    wire = to_canonical_bytes({"_type": "future"}, CanonSpec(version="0.3.0"))
    assert wire == b'{"_type":"mapping","entries":[["_type","future"]]}'
    store = FileSystemCAS(root)
    ref = store.put_bytes(
        wire,
        PutOptions(
            kind="test.v3.selected-reader",
            media_type="application/json",
            canon=CanonInfo(version="0.3.0"),
        ),
        return_selected_profile=True,
    )

    fresh = FileSystemCAS(root)
    read = read_core_json_artifact(fresh, ref)
    assert read.value == {"_type": "future"}
    assert type(read.value) is dict
    assert read.reader_policy_id == "core-tag-policy@2"
