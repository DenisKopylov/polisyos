from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

import pytest
from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    CanonInfo,
    CoreJsonReadLimits,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    aload_core_json_artifact,
    artifact_ref_for_manifest,
    load_core_json_artifact,
    load_core_json_frame_records,
    read_core_json_artifact,
    read_core_json_artifact_bounded,
    read_core_json_artifact_bytes,
    validate_core_model_bounded_read,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.protocol import CoreJSONArtifactStore
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.canon.canon_json import (
    CORE_TAG_POLICY_ID,
    FloatHexRepresentation,
)
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    MetricsRef,
    ProgramGraph,
    SimulationResult,
)
from polisyos.core.registry import (
    build_default_registry_bundle,
    load_registry_bundle_content,
)
from polisyos.fabric.connectors.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    KPISpec,
    OptimizationDirection,
    ProblemDomain,
    ProblemFrame,
    SuccessCriterion,
)
from polisyos.ir.kernel.units import (
    CountUnit,
    DimensionlessUnit,
    DurationUnit,
    GenericUnit,
    MoneyUnit,
    RateUnit,
    UnitsRegistry,
)
from polisyos.ir.kernel.values import MoneyValue
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
from polisyos.runtime.http.resilience import (
    BlockingDependencyGuard,
    GuardedDependencyProxy,
)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: int


class _NestedTuplePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    values: tuple[tuple[str, ...], ...]


def _profiled_json_store(tmp_path, payload: object):
    store = FileSystemCAS(tmp_path / "cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    raw = to_canonical_bytes(payload, spec)
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.selected_profile.json",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
    )
    return store, ref, raw


def _raw_profiled_json_store(root, payload: object, spec: CanonSpec):
    """Persist raw JSON under Core profile wire settings without normalizing its tags."""
    raw = json.dumps(
        payload,
        sort_keys=spec.sort_keys,
        separators=spec.separators,
        ensure_ascii=spec.ensure_ascii,
        allow_nan=False,
    ).encode("utf-8")
    store = FileSystemCAS(root)
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.selected_profile.raw-json",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    return store, ref, raw


def test_core_selected_profile_read_names_its_tag_policy(tmp_path) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 7})

    read = read_core_json_artifact(store, ref)

    assert read.reader_policy_id == CORE_TAG_POLICY_ID
    assert read.status == "declared_bytes_conformant"


def test_core_json_facade_returns_only_profile_conformant_selected_values(
    tmp_path,
) -> None:
    store, ref, raw = _profiled_json_store(tmp_path, {"value": 7})

    assert read_core_json_artifact_bytes(store, ref) == raw
    assert load_core_json_artifact(store, ref) == {"value": 7}
    assert validate_core_model_json_artifact(_Payload, store, ref) == _Payload(value=7)


def test_registry_consumer_reads_selected_cas_views_through_guarded_proxy(
    tmp_path, monkeypatch, request
) -> None:
    """The public registry reader resolves all CAS bytes through the exact guard."""
    store = FileSystemCAS(tmp_path / "guarded-registry-cas")
    bundle = build_default_registry_bundle(store)
    guard = BlockingDependencyGuard(
        dependency_name="test-guarded-registry-cas",
        timeout_seconds=2.0,
        breaker=CircuitBreaker(
            "test-guarded-registry-cas",
            CircuitBreakerConfig(min_throughput=1),
        ),
    )
    request.addfinalizer(guard.close)
    guard_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    guarded_run = guard.run

    def record_guard_call(function, *args, **kwargs):
        guard_calls.append((function.__name__, args, kwargs))
        return guarded_run(function, *args, **kwargs)

    monkeypatch.setattr(guard, "run", record_guard_call)
    guarded_store = GuardedDependencyProxy(target=store, guard=guard)

    content = load_registry_bundle_content(guarded_store, bundle.bundle_ref)

    assert content.bundle_ref == bundle.bundle_ref
    assert content.slot_registry.slots
    assert guarded_store._target is store
    assert [name for name, _args, _kwargs in guard_calls[:3]] == [
        "get_raw_manifest_bytes",
        "get_manifest",
        "get_bytes",
    ]
    assert guard_calls[0][1][0] == bundle.bundle_ref


def test_ir_adapter_cannot_make_base_only_store_a_core_json_reader(tmp_path) -> None:
    """A static adapter facade does not substitute for its owner's raw-reader method."""

    class BaseOnlyFacade:
        def __init__(self, target: FileSystemCAS) -> None:
            self.target = target
            self.payload_reads = 0

        def __getattr__(self, name: str):
            if name == "get_raw_manifest_bytes":
                raise AttributeError(name)
            if name == "get_bytes":
                return self._get_bytes
            return getattr(self.target, name)

        def _get_bytes(self, *args, **kwargs):
            self.payload_reads += 1
            return self.target.get_bytes(*args, **kwargs)

    backing_store = FileSystemCAS(tmp_path / "base-only-registry-cas")
    bundle = build_default_registry_bundle(backing_store)
    weak_owner = BaseOnlyFacade(backing_store)
    adapter = CoreToIRArtifactStoreAdapter(weak_owner)

    assert not isinstance(weak_owner, CoreJSONArtifactStore)
    assert isinstance(adapter, CoreJSONArtifactStore)
    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_raw_manifest_unavailable",
    ):
        load_registry_bundle_content(adapter, bundle.bundle_ref)
    assert weak_owner.payload_reads == 0


def test_guarded_raw_reader_denial_is_not_reclassified_as_missing_capability(
    tmp_path, monkeypatch, request
) -> None:
    """Operational guard denial remains visible and prevents all later CAS reads."""
    store = FileSystemCAS(tmp_path / "denied-raw-reader-cas")
    bundle = build_default_registry_bundle(store)

    def deny_raw_manifest(*args, **kwargs):
        raise PermissionError("test raw-manifest guard denial")

    monkeypatch.setattr(store, "get_raw_manifest_bytes", deny_raw_manifest)
    guard = BlockingDependencyGuard(
        dependency_name="test-denied-raw-reader-cas",
        timeout_seconds=2.0,
        breaker=CircuitBreaker(
            "test-denied-raw-reader-cas",
            CircuitBreakerConfig(min_throughput=1),
        ),
        unavailable_exception_types=(PermissionError,),
    )
    request.addfinalizer(guard.close)
    guard_calls: list[str] = []
    guarded_run = guard.run

    def record_guard_call(function, *args, **kwargs):
        guard_calls.append(function.__name__)
        return guarded_run(function, *args, **kwargs)

    monkeypatch.setattr(guard, "run", record_guard_call)

    with pytest.raises(RuntimeDependencyUnavailableError):
        load_registry_bundle_content(
            GuardedDependencyProxy(target=store, guard=guard),
            bundle.bundle_ref,
        )

    assert guard_calls == ["deny_raw_manifest"]


def test_typed_core_reader_reifies_empty_nested_variadic_tuples(tmp_path) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"values": []})

    assert validate_core_model_json_artifact(_NestedTuplePayload, store, ref) == (
        _NestedTuplePayload(values=())
    )


def _simulation_result_for_artifact_version(version: str) -> SimulationResult:
    return SimulationResult(
        schema_version=version,
        exec_plan_ref=ExecPlanRef(artifact_id=f"sha256:{'a' * 64}"),
        metrics_ref=MetricsRef(artifact_id=f"sha256:{'b' * 64}"),
    )


def _put_simulation_result_view(
    store: FileSystemCAS,
    result: SimulationResult,
    *,
    schema_name: str | None = None,
    schema_version: str | None = None,
    kind: str | None = None,
    media_type: str | None = None,
):
    payload = result.to_artifact_payload()
    spec = CanonSpec(forbid_floats=False)
    options = PutOptions(
        kind=kind or SimulationResult.ARTIFACT_KIND,
        media_type=media_type or SimulationResult.ARTIFACT_MEDIA_TYPE,
        schema=SchemaInfo(
            name=schema_name or SimulationResult.ARTIFACT_SCHEMA_NAME,
            version=schema_version or result.schema_version,
        ),
        canon=CanonInfo.from_spec(spec),
    )
    if media_type is not None and media_type != "application/json":
        return store.put_bytes(
            to_canonical_bytes(payload, spec),
            options,
            return_selected_profile=True,
        )
    return store.put_json(
        payload,
        options,
        canon_spec=spec,
        return_selected_profile=True,
    )


@pytest.mark.parametrize("version", ["1.3", "1.4"])
def test_typed_core_reader_accepts_only_owner_supported_simulation_versions(
    tmp_path, version
) -> None:
    store = FileSystemCAS(tmp_path / f"simulation-{version}")
    result = _simulation_result_for_artifact_version(version)
    ref = _put_simulation_result_view(store, result)

    restored = validate_core_model_json_artifact(SimulationResult, store, ref)

    assert restored == result
    assert restored.schema_version == version
    assert ref.manifest_profile_sha256 is not None


@pytest.mark.parametrize(
    (
        "payload_version",
        "manifest_name",
        "manifest_version",
        "kind",
        "media_type",
        "reason",
    ),
    [
        pytest.param(
            "1.3",
            "polisyos.other.SimulationResult",
            "1.3",
            None,
            None,
            "canon_profile_typed_artifact_schema_name_mismatch",
            id="wrong-schema-name",
        ),
        pytest.param(
            "1.3",
            None,
            "9.0",
            None,
            None,
            "canon_profile_typed_artifact_schema_version_unsupported",
            id="unsupported-version",
        ),
        pytest.param(
            "1.3",
            None,
            "1.4",
            None,
            None,
            "canon_profile_typed_artifact_schema_version_mismatch",
            id="payload-version-mismatch",
        ),
        pytest.param(
            "1.3",
            None,
            None,
            "foundry.metrics",
            None,
            "canon_profile_typed_artifact_kind_mismatch",
            id="wrong-kind",
        ),
        pytest.param(
            "1.3",
            None,
            None,
            None,
            "application/jsonl",
            "canon_profile_typed_artifact_media_type_mismatch",
            id="wrong-media-type",
        ),
    ],
)
def test_typed_core_reader_refuses_simulation_schema_contract_drift(
    tmp_path,
    payload_version,
    manifest_name,
    manifest_version,
    kind,
    media_type,
    reason,
) -> None:
    store = FileSystemCAS(tmp_path / reason)
    result = _simulation_result_for_artifact_version(payload_version)
    ref = _put_simulation_result_view(
        store,
        result,
        schema_name=manifest_name,
        schema_version=manifest_version,
        kind=kind,
        media_type=media_type,
    )

    with pytest.raises(CanonicalProfileRefusalError, match=reason):
        validate_core_model_json_artifact(SimulationResult, store, ref)


def test_typed_core_reader_refuses_a_different_selected_manifest_profile(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "simulation-wrong-profile")
    result = _simulation_result_for_artifact_version("1.3")
    ref = _put_simulation_result_view(store, result)
    wrong_profile_ref = ref.model_copy(update={"manifest_profile_sha256": f"sha256:{'c' * 64}"})

    with pytest.raises(FileNotFoundError):
        validate_core_model_json_artifact(SimulationResult, store, wrong_profile_ref)


def _put_program_graph_view(
    tmp_path,
    payload: ProgramGraph,
    *,
    manifest_version: str | None = None,
):
    store = FileSystemCAS(tmp_path / "program-graph-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    ref = store.put_json(
        payload,
        PutOptions(
            kind=ProgramGraph.ARTIFACT_KIND,
            media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
                version=manifest_version or ProgramGraph.ARTIFACT_SCHEMA_VERSION,
            ),
            canon=CanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    return store, artifact_ref_for_manifest(store.get_manifest(ref))


def _program_graph_payload(*, payload_version: str = "0.2") -> ProgramGraph:
    return ProgramGraph(
        schema_version=payload_version,
        ir_ref=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="ir.policy_spec",
            media_type="application/json",
        ),
    )


def test_typed_core_reader_preserves_program_graph_owner_version_mapping(
    tmp_path,
) -> None:
    program_graph = _program_graph_payload()
    store, selected_ref = _put_program_graph_view(tmp_path, program_graph)

    restored = validate_core_model_json_artifact(ProgramGraph, store, selected_ref)

    assert restored == program_graph
    assert selected_ref.manifest_profile_sha256 is not None


def test_typed_core_reader_refuses_program_graph_payload_version_drift(
    tmp_path,
) -> None:
    store, selected_ref = _put_program_graph_view(
        tmp_path,
        _program_graph_payload(payload_version="0.3"),
    )

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_version_mismatch",
    ):
        validate_core_model_json_artifact(ProgramGraph, store, selected_ref)


def test_typed_core_reader_refuses_unsupported_program_graph_manifest_version(
    tmp_path,
) -> None:
    store, selected_ref = _put_program_graph_view(
        tmp_path,
        _program_graph_payload(),
        manifest_version="9.0",
    )

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_version_unsupported",
    ):
        validate_core_model_json_artifact(ProgramGraph, store, selected_ref)


def test_core_json_missing_profile_is_refused_before_selected_semantics(
    tmp_path, monkeypatch
) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 7})
    original_raw_reader = store.get_raw_manifest_bytes
    original_manifest_reader = store.get_manifest
    selected_id = str(ref.artifact_id)

    def absent_profile(selector, *, manifest_profile_sha256=None):
        raw = original_raw_reader(selector, manifest_profile_sha256=manifest_profile_sha256)
        if str(getattr(selector, "artifact_id", selector)) != selected_id:
            return raw
        payload = json.loads(raw)
        payload.pop("canon", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def typed_absent_profile(selector):
        manifest = original_manifest_reader(selector)
        if str(getattr(selector, "artifact_id", selector)) != selected_id:
            return manifest
        return manifest.model_copy(update={"canon": None})

    monkeypatch.setattr(store, "get_raw_manifest_bytes", absent_profile)
    monkeypatch.setattr(store, "get_manifest", typed_absent_profile)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        load_core_json_artifact(store, ref.artifact_id)


def test_core_json_present_malformed_profile_is_not_treated_as_absent(
    tmp_path, monkeypatch
) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 7})
    original_raw_reader = store.get_raw_manifest_bytes
    selected_id = str(ref.artifact_id)

    def malformed_present(selector, *, manifest_profile_sha256=None):
        raw = original_raw_reader(selector, manifest_profile_sha256=manifest_profile_sha256)
        if str(getattr(selector, "artifact_id", selector)) == selected_id:
            return b'{"canon":null}'
        return raw

    monkeypatch.setattr(store, "get_raw_manifest_bytes", malformed_present)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_invalid"):
        read_core_json_artifact_bytes(store, ref)


def test_core_unknown_profile_remains_an_exact_raw_only_candidate(tmp_path) -> None:
    raw = b'{"candidate":true}'
    store = FileSystemCAS(tmp_path / "unknown-profile-cas")
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.unknown-profile",
            media_type="application/json",
            canon=CanonInfo(name="polisyos.canon.future"),
        ),
    )

    read = read_core_json_artifact(store, ref)

    assert read.status == "declared_unknown_candidate"
    assert read.raw_only_candidate_bytes == raw
    assert read.selected_artifact_id == str(ref.artifact_id)
    assert read.selected_manifest_profile_sha256 is not None
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_not_verified"):
        _ = read.value


def test_core_frame_loader_verifies_manifest_profile_and_each_record(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path / "framed-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    records = [to_canonical_bytes({"value": value}, spec) for value in (3, 5)]
    raw = b"".join(len(record).to_bytes(8, "big") + record for record in records)
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.selected_profile.frames",
            media_type="application/vnd.polisyos.test-frames+json",
            canon=CanonInfo.from_spec(spec),
        ),
    )

    assert load_core_json_frame_records(store, ref) == [{"value": 3}, {"value": 5}]

    original_raw_reader = store.get_raw_manifest_bytes
    selected_id = str(ref.artifact_id)

    def absent_frame_profile(selector, *, manifest_profile_sha256=None):
        sidecar = original_raw_reader(selector, manifest_profile_sha256=manifest_profile_sha256)
        if str(getattr(selector, "artifact_id", selector)) == selected_id:
            payload = json.loads(sidecar)
            payload.pop("canon", None)
            return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sidecar

    monkeypatch.setattr(store, "get_raw_manifest_bytes", absent_frame_profile)
    with pytest.raises(CanonicalProfileRefusalError, match="canon_profile_absent"):
        load_core_json_frame_records(store, ref.artifact_id)


def test_async_core_json_facade_preserves_the_selected_profile_guard(tmp_path) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 11})
    async_store = AsyncArtifactStoreAdapter(store, timeout_seconds=5.0)

    assert asyncio.run(aload_core_json_artifact(async_store, ref)) == {"value": 11}


@pytest.mark.parametrize(
    ("profile_variant", "expected_error"),
    [
        ("incomplete", "canon_profile_incomplete"),
        ("unsupported", "canon_profile_not_verified"),
    ],
)
def test_async_core_refuses_nonreadable_raw_profile_before_typed_or_payload_reads(
    tmp_path, monkeypatch, profile_variant, expected_error
) -> None:
    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 17})
    selected_id = str(ref.artifact_id)
    original_raw_reader = store.get_raw_manifest_bytes
    original_manifest_reader = store.get_manifest
    original_payload_reader = store.get_bytes
    manifest_reads: list[object] = []
    payload_reads: list[object] = []

    def nonreadable_profile(selector, *, manifest_profile_sha256=None):
        raw = original_raw_reader(selector, manifest_profile_sha256=manifest_profile_sha256)
        if str(getattr(selector, "artifact_id", selector)) != selected_id:
            return raw
        if profile_variant == "incomplete":
            return b'{"canon":{}}'
        manifest = json.loads(raw)
        manifest["canon"]["version"] = "9.9.0"
        return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()

    def record_manifest(selector):
        manifest_reads.append(selector)
        return original_manifest_reader(selector)

    def record_payload(selector):
        payload_reads.append(selector)
        return original_payload_reader(selector)

    monkeypatch.setattr(store, "get_raw_manifest_bytes", nonreadable_profile)
    monkeypatch.setattr(store, "get_manifest", record_manifest)
    monkeypatch.setattr(store, "get_bytes", record_payload)
    async_store = AsyncArtifactStoreAdapter(store, timeout_seconds=5.0)

    with pytest.raises(CanonicalProfileRefusalError, match=expected_error):
        asyncio.run(aload_core_json_artifact(async_store, ref))

    assert manifest_reads == []
    assert payload_reads == []


def test_typed_core_reader_preserves_the_selected_manifest_view(tmp_path, monkeypatch) -> None:
    from polisyos.core.artifacts import artifact_ref_for_manifest
    from polisyos.scientist.methods.autotune.models import load_json_artifact

    store, ref, _raw = _profiled_json_store(tmp_path, {"value": 13})
    selected_ref = artifact_ref_for_manifest(store.get_manifest(ref))
    observed_selectors = []
    original_raw_reader = store.get_raw_manifest_bytes

    def record_selector(selector, *, manifest_profile_sha256=None):
        observed_selectors.append(selector)
        return original_raw_reader(selector, manifest_profile_sha256=manifest_profile_sha256)

    monkeypatch.setattr(store, "get_raw_manifest_bytes", record_selector)

    assert load_json_artifact(store, selected_ref) == {"value": 13}
    assert observed_selectors[0] == selected_ref


_ANNOTATED_VALIDATION_COUNT = 0


def _count_annotated_validation(value: int) -> int:
    global _ANNOTATED_VALIDATION_COUNT
    _ANNOTATED_VALIDATION_COUNT += 1
    return value


_CountingInt = Annotated[int, AfterValidator(_count_annotated_validation)]


class _WireState(str, Enum):
    READY = "ready"
    REVIEW = "review"


class _NestedTypedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    state: _WireState = Field(
        validation_alias=AliasChoices("state_input", "legacy_state"),
        serialization_alias="wire_state",
    )
    rows: tuple[tuple[str, int], ...]


class _TypedCorePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    observed_at: datetime
    observed_on: date
    amount: Decimal
    payload_bytes: bytes
    ratio: float
    checked_count: _CountingInt
    row_ids: tuple[int, ...]
    nested: _NestedTypedPayload
    selected: _NestedTypedPayload | tuple[str, ...]
    groups: list[tuple[str, _WireState]]
    opaque_tags: dict[str, object]


def _profiled_core_json_store(tmp_path, payload: object, *, return_selected_profile: bool = False):
    store = FileSystemCAS(tmp_path / "typed-cas")
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    ref = store.put_json(
        payload,
        PutOptions(
            kind="test.selected_profile.typed-json",
            media_type="application/json",
            canon=CanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=return_selected_profile,
    )
    return store, ref, store.get_bytes(ref)


def _typed_core_payload(*, payload_bytes: bytes) -> _TypedCorePayload:
    return _TypedCorePayload(
        observed_at=datetime(2026, 10, 13, 9, 15, tzinfo=UTC),
        observed_on=date(2026, 10, 13),
        amount=Decimal("13.25"),
        payload_bytes=payload_bytes,
        ratio=1.25,
        checked_count=2,
        row_ids=(3, 5),
        nested=_NestedTypedPayload(
            state=_WireState.READY,
            rows=(("alpha", 2), ("beta", 4)),
        ),
        selected=_NestedTypedPayload(state=_WireState.REVIEW, rows=(("gamma", 6),)),
        groups=[("delta", _WireState.READY), ("epsilon", _WireState.REVIEW)],
        opaque_tags={
            "array": {
                "_type": "array_digest",
                "dtype": "int64",
                "shape": [2],
                "sha256": "a" * 64,
            },
        },
    )


@pytest.mark.parametrize("writer_form", ["python-model", "json-model-dump"])
def test_typed_core_reader_reifies_declared_types_after_both_writer_forms(
    tmp_path, writer_form
) -> None:
    source = _typed_core_payload(
        payload_bytes=b"raw\x00bytes" if writer_form == "python-model" else b"readable"
    )
    payload = (
        source if writer_form == "python-model" else source.model_dump(mode="json", by_alias=True)
    )
    store, ref, raw = _profiled_core_json_store(tmp_path, payload)
    before_validation_count = _ANNOTATED_VALIDATION_COUNT

    restored = validate_core_model_json_artifact(_TypedCorePayload, store, ref)

    assert restored == source
    assert before_validation_count + 1 == _ANNOTATED_VALIDATION_COUNT
    assert restored.nested.state is _WireState.READY
    assert restored.nested.rows == (("alpha", 2), ("beta", 4))
    assert isinstance(restored.row_ids, tuple)
    assert isinstance(restored.groups[0], tuple)
    assert restored.observed_at == source.observed_at
    assert restored.observed_on == source.observed_on
    assert restored.amount == source.amount
    assert restored.payload_bytes == source.payload_bytes
    assert restored.ratio == source.ratio
    assert restored.opaque_tags["array"]["_type"] == "array_digest"
    assert read_core_json_artifact_bytes(store, ref) == raw


def test_typed_core_reader_refuses_wrong_shape_and_selected_byte_drift(
    tmp_path,
) -> None:
    source = _typed_core_payload(payload_bytes=b"readable")
    malformed = source.model_dump(mode="json", by_alias=True)
    malformed["row_ids"] = [3, True]
    store, ref, raw = _profiled_core_json_store(tmp_path, malformed)

    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(_TypedCorePayload, store, ref)

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_selected_payload_identity_mismatch",
    ):
        validate_core_model_json_artifact(
            _TypedCorePayload,
            store,
            ref,
            raw_payload_bytes=raw + b" ",
        )


def test_core_canonical_writer_rejects_unknown_typed_tag() -> None:
    with pytest.raises(ValueError, match="Unknown canonical _type"):
        to_canonical_bytes({"value": {"_type": "future-unregistered-tag"}})


@pytest.mark.parametrize(
    "tagged_value",
    [
        pytest.param({"_type": "bytes_hex", "value": "00ff"}, id="bytes-hex"),
        pytest.param({"_type": "float_hex", "value": "0x1.4p+0"}, id="float-hex"),
    ],
)
def test_selected_core_reader_refuses_nonnormal_reserved_tags_before_typed_adapter(
    tmp_path, tagged_value
) -> None:
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    payload = {"opaque": tagged_value}

    # The public Core writer rejects aliases whose decoded values re-encode differently.
    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_payload_nonconformant",
    ):
        to_canonical_bytes(payload, spec)

    # This generic raw control preserves the JSON mapping while binding the actual
    # CoreCanonInfo flags, so the reader refusal is about payload conformance only.
    root = tmp_path / "nonnormal-tag-cas"
    store, selected_ref, raw = _raw_profiled_json_store(root, payload, spec)
    assert selected_ref.manifest_profile_sha256 is not None
    assert store.get_bytes(selected_ref) == raw

    fresh_reader = FileSystemCAS(root)
    assert fresh_reader.get_bytes(selected_ref) == raw
    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_payload_nonconformant",
    ):
        read_core_json_artifact(fresh_reader, selected_ref)


class _TaggedAmountOne(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["amount_one"]
    amount: Decimal


class _TaggedAmountTwo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mode: Literal["amount_two"]
    amount: Decimal


class _SchemaDerivedUnionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    selected: _TaggedAmountOne | _TaggedAmountTwo


class _AmbiguousAmountOne(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    amount: Decimal


class _AmbiguousAmountTwo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    amount: Decimal


class _SchemaAmbiguousUnionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    selected: _AmbiguousAmountOne | _AmbiguousAmountTwo


def _trinity_money_bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_core_union",
            domain=ProblemDomain.FISCAL,
            kpis=[
                KPISpec(
                    kpi_id="kpi_core_union",
                    metric_id="metric_core_union",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
            success_criteria=[
                SuccessCriterion(
                    criterion_id="criterion_core_union",
                    kpi_id="kpi_core_union",
                    operator=">=",
                    threshold=MoneyValue(amount=Decimal("13.25"), currency="USD"),
                )
            ],
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="constraint_core_union",
                    value=MoneyValue(amount=Decimal("13.25"), currency="USD"),
                )
            ],
        ),
        policy_spec=PolicySpec(
            policy_id="policy_core_union",
            problem_frame_ref="sha256:" + "a" * 64,
            interventions=[],
        ),
        model_spec=ModelSpec(
            model_id="model_core_union",
            data_snapshot_ref="sha256:" + "b" * 64,
        ),
    )


def _write_selected_trinity(tmp_path, payload: object):
    store_root = tmp_path / "trinity-cas"
    store = FileSystemCAS(store_root)
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    ref = store.put_json(
        payload,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            canon=CanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    selected_ref = artifact_ref_for_manifest(store.get_manifest(ref))
    return store_root, selected_ref, store.get_bytes(selected_ref)


@pytest.mark.parametrize("writer_form", ["python-model", "json-model-dump"])
def test_trinity_core_reader_reifies_multi_model_union_from_selected_fresh_view(
    tmp_path, writer_form
) -> None:
    source = _trinity_money_bundle()
    payload = (
        source if writer_form == "python-model" else source.model_dump(mode="json", by_alias=True)
    )
    store_root, selected_ref, raw = _write_selected_trinity(tmp_path, payload)
    fresh_reader = FileSystemCAS(store_root)

    selected_read = read_core_json_artifact(fresh_reader, selected_ref)
    restored = validate_core_model_json_artifact(TrinityBundle, fresh_reader, selected_ref)

    assert selected_read.selected_artifact_id == str(selected_ref.artifact_id)
    assert selected_read.selected_manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert restored == source
    assert isinstance(restored.problem_frame.success_criteria[0].threshold, MoneyValue)
    assert restored.problem_frame.success_criteria[0].threshold.amount == Decimal("13.25")
    assert isinstance(restored.problem_frame.hard_constraints[0].value, MoneyValue)
    assert restored.problem_frame.hard_constraints[0].value.amount == Decimal("13.25")
    assert read_core_json_artifact_bytes(fresh_reader, selected_ref) == raw


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["problem_frame"]["hard_constraints"][0].update(
            value={"kind": "future_amount", "amount": "13.25", "currency": "USD"}
        ),
        lambda payload: payload["problem_frame"]["success_criteria"][0].update(
            threshold={"amount": 13.25, "currency": "USD"}
        ),
    ],
    ids=["unknown-model-variant", "wrong-scalar-type"],
)
def test_trinity_core_reader_refuses_unknown_union_variant_and_scalar(tmp_path, mutation) -> None:
    payload = _trinity_money_bundle().model_dump(mode="json", by_alias=True)
    mutation(payload)
    store_root, selected_ref, _raw = _write_selected_trinity(tmp_path, payload)

    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(
            TrinityBundle,
            FileSystemCAS(store_root),
            selected_ref,
        )


def test_schema_derived_union_reifies_unique_literal_branches_and_refuses_unknown_tag(
    tmp_path,
) -> None:
    source = _SchemaDerivedUnionPayload(
        selected=_TaggedAmountTwo(mode="amount_two", amount=Decimal("7.50"))
    )
    payload = source.model_dump(mode="json", by_alias=True)
    store, ref, _raw = _profiled_core_json_store(tmp_path, payload)

    restored = validate_core_model_json_artifact(_SchemaDerivedUnionPayload, store, ref)

    assert restored == source
    assert isinstance(restored.selected, _TaggedAmountTwo)
    assert restored.selected.amount == Decimal("7.50")

    malformed = {"selected": {"kind": "unknown", "amount": "7.50"}}
    bad_store, bad_ref, _bad_raw = _profiled_core_json_store(tmp_path / "bad", malformed)
    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(
            _SchemaDerivedUnionPayload,
            bad_store,
            bad_ref,
        )

    conflicting = {
        "selected": {
            "kind": "amount_one",
            "mode": "amount_two",
            "amount": "7.50",
        }
    }
    conflict_store, conflict_ref, _conflict_raw = _profiled_core_json_store(
        tmp_path / "conflicting", conflicting
    )
    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(
            _SchemaDerivedUnionPayload,
            conflict_store,
            conflict_ref,
        )


def test_schema_derived_union_refuses_ambiguous_model_shape(tmp_path) -> None:
    malformed = {"selected": {"amount": "7.50"}}
    store, ref, _raw = _profiled_core_json_store(tmp_path, malformed)

    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(_SchemaAmbiguousUnionPayload, store, ref)


class _NullablePopulationRow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    numeric_id: str
    row_index: int


class _NullablePopulation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    columns: tuple[str, ...]
    rows: tuple[_NullablePopulationRow, ...]
    literal_target_row_indices: tuple[int, ...]
    refusal_reasons: tuple[str, ...]


class _NullableRecursiveCoreNode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    label: str
    children: tuple[_NullableRecursiveCoreNode, ...] = ()


class _NullableTaggedRowOne(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["nullable_one"]
    row_indices: tuple[int, ...]


class _NullableTaggedRowTwo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["nullable_two"]
    row_indices: tuple[int, ...]


class _NullableTypedCoreEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    population: _NullablePopulation | None
    tree: _NullableRecursiveCoreNode | None
    selected: (
        Annotated[
            _NullableTaggedRowOne | _NullableTaggedRowTwo,
            Field(discriminator="kind"),
        ]
        | None
    )
    nullable_note: str | None


def _nullable_typed_core_envelope() -> _NullableTypedCoreEnvelope:
    return _NullableTypedCoreEnvelope(
        population=_NullablePopulation(
            columns=("numeric_id", "row_index"),
            rows=(_NullablePopulationRow(numeric_id="n1", row_index=0),),
            literal_target_row_indices=(0,),
            refusal_reasons=(),
        ),
        tree=_NullableRecursiveCoreNode(
            label="root",
            children=(_NullableRecursiveCoreNode(label="child"),),
        ),
        selected=_NullableTaggedRowTwo(kind="nullable_two", row_indices=(2, 4)),
        nullable_note=None,
    )


def test_nullable_model_branches_reify_nested_tuples_through_fresh_cas_reader(
    tmp_path,
) -> None:
    source = _nullable_typed_core_envelope()
    payload = source.model_dump(mode="json")
    _store, ref, raw = _profiled_core_json_store(tmp_path / "populated", payload)
    fresh_reader = FileSystemCAS(tmp_path / "populated" / "typed-cas")

    restored = validate_core_model_json_artifact(
        _NullableTypedCoreEnvelope,
        fresh_reader,
        ref,
    )

    assert restored == source
    assert isinstance(restored.population, _NullablePopulation)
    assert isinstance(restored.population.columns, tuple)
    assert isinstance(restored.population.rows, tuple)
    assert isinstance(restored.population.rows[0], _NullablePopulationRow)
    assert isinstance(restored.population.literal_target_row_indices, tuple)
    assert isinstance(restored.population.refusal_reasons, tuple)
    assert isinstance(restored.tree, _NullableRecursiveCoreNode)
    assert isinstance(restored.tree.children, tuple)
    assert isinstance(restored.tree.children[0], _NullableRecursiveCoreNode)
    assert isinstance(restored.selected, _NullableTaggedRowTwo)
    assert isinstance(restored.selected.row_indices, tuple)
    assert restored.nullable_note is None
    assert read_core_json_artifact_bytes(fresh_reader, ref) == raw

    explicit_nulls = {
        **payload,
        "population": None,
        "tree": None,
        "selected": None,
    }
    _null_store, null_ref, _null_raw = _profiled_core_json_store(
        tmp_path / "explicit-nulls",
        explicit_nulls,
    )
    null_reader = FileSystemCAS(tmp_path / "explicit-nulls" / "typed-cas")
    restored_nulls = validate_core_model_json_artifact(
        _NullableTypedCoreEnvelope,
        null_reader,
        null_ref,
    )
    assert restored_nulls.population is None
    assert restored_nulls.tree is None
    assert restored_nulls.selected is None
    assert restored_nulls.nullable_note is None


def test_nullable_model_branch_keeps_required_optional_fields_required(
    tmp_path,
) -> None:
    payload = _nullable_typed_core_envelope().model_dump(mode="json")
    payload.pop("population")
    _store, ref, _raw = _profiled_core_json_store(tmp_path, payload)

    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(
            _NullableTypedCoreEnvelope,
            FileSystemCAS(tmp_path / "typed-cas"),
            ref,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["population"]["rows"][0].update(row_index=True),
        lambda payload: payload["population"].update(unexpected="extra"),
        lambda payload: payload["selected"].update(kind="future_variant"),
        lambda payload: payload["selected"]["row_indices"].__setitem__(0, True),
    ],
    ids=[
        "strict-nested-tuple-item",
        "forbidden-nested-field",
        "unknown-discriminator",
        "strict-discriminated-tuple-item",
    ],
)
def test_nullable_model_branches_refuse_malformed_nested_values(tmp_path, mutation) -> None:
    payload = _nullable_typed_core_envelope().model_dump(mode="json")
    mutation(payload)
    _store, ref, _raw = _profiled_core_json_store(tmp_path, payload)

    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(
            _NullableTypedCoreEnvelope,
            FileSystemCAS(tmp_path / "typed-cas"),
            ref,
        )


_UNIT_BEFORE_VALIDATOR_COUNT = 0
_UNIT_MODEL_VALIDATOR_COUNT = 0


def _count_unit_probe_before(value: list[str]) -> list[str]:
    global _UNIT_BEFORE_VALIDATOR_COUNT
    _UNIT_BEFORE_VALIDATOR_COUNT += 1
    return value


class _UnitValidatorProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    labels: Annotated[list[str], BeforeValidator(_count_unit_probe_before)]

    @model_validator(mode="after")
    def count_model_validation(self) -> _UnitValidatorProbe:
        global _UNIT_MODEL_VALIDATOR_COUNT
        _UNIT_MODEL_VALIDATOR_COUNT += 1
        return self


class _UnitsRegistryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    registry: UnitsRegistry
    probe: _UnitValidatorProbe


def _units_registry_envelope() -> _UnitsRegistryEnvelope:
    return _UnitsRegistryEnvelope(
        registry=UnitsRegistry(
            units={
                "usd": MoneyUnit(currency="USD", nominal_year=2025),
                "ratio": RateUnit(base="ratio"),
                "people": CountUnit(label="people"),
                "duration": DurationUnit(unit="day"),
                "index": DimensionlessUnit(label="index"),
                "generic": GenericUnit(label="other", description="generic"),
            }
        ),
        probe=_UnitValidatorProbe(labels=["one", "two"]),
    )


def _write_selected_units_registry(tmp_path, payload: object):
    store_root = tmp_path / "units-registry-cas"
    store = FileSystemCAS(store_root)
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    ref = store.put_json(
        payload,
        PutOptions(
            kind="polisyos.ir.kernel.UnitsRegistryEnvelope",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.kernel.UnitsRegistryEnvelope", version="1.0"),
            canon=CanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )
    selected_ref = artifact_ref_for_manifest(store.get_manifest(ref))
    return store_root, selected_ref, store.get_bytes(selected_ref)


@pytest.mark.parametrize("writer_form", ["python-model", "json-model-dump"])
def test_units_registry_discriminator_reifies_nested_union_and_runs_validators_once(
    tmp_path, writer_form
) -> None:
    global _UNIT_BEFORE_VALIDATOR_COUNT, _UNIT_MODEL_VALIDATOR_COUNT
    source = _units_registry_envelope()
    payload = (
        source if writer_form == "python-model" else source.model_dump(mode="json", by_alias=True)
    )
    store_root, selected_ref, raw = _write_selected_units_registry(tmp_path, payload)
    fresh_reader = FileSystemCAS(store_root)
    _UNIT_BEFORE_VALIDATOR_COUNT = 0
    _UNIT_MODEL_VALIDATOR_COUNT = 0

    selected = read_core_json_artifact(fresh_reader, selected_ref)
    restored = validate_core_model_json_artifact(_UnitsRegistryEnvelope, fresh_reader, selected_ref)

    assert selected.selected_artifact_id == str(selected_ref.artifact_id)
    assert selected.selected_manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert restored == source
    assert type(restored.registry.units["usd"]) is MoneyUnit
    assert type(restored.registry.units["ratio"]) is RateUnit
    assert type(restored.registry.units["people"]) is CountUnit
    assert type(restored.registry.units["duration"]) is DurationUnit
    assert type(restored.registry.units["index"]) is DimensionlessUnit
    assert type(restored.registry.units["generic"]) is GenericUnit
    assert _UNIT_BEFORE_VALIDATOR_COUNT == 1
    assert _UNIT_MODEL_VALIDATOR_COUNT == 1
    assert read_core_json_artifact_bytes(fresh_reader, selected_ref) == raw


def test_units_registry_discriminator_refuses_unknown_present_kind(tmp_path) -> None:
    payload = _units_registry_envelope().model_dump(mode="json", by_alias=True)
    payload["registry"]["units"]["usd"]["kind"] = "future"
    store_root, selected_ref, _raw = _write_selected_units_registry(tmp_path, payload)

    with pytest.raises(ValidationError):
        validate_core_model_json_artifact(
            _UnitsRegistryEnvelope, FileSystemCAS(store_root), selected_ref
        )


def test_data_snapshot_schema_030_requires_owner_lineage(tmp_path) -> None:
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.core.contracts.fabric import (
        DataSnapshot,
        DataSnapshotOwnerBound,
        DataViewRequestRef,
        FabricBridgeDataSnapshotLineage,
    )

    store = FileSystemCAS(tmp_path / "cas")
    data_ref = store.put_json(
        {"rows": []},
        PutOptions(
            kind="fabric.tabular_payload",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.TabularPayload", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    request_ref = store.put_json(
        {"schema_version": "1.0"},
        PutOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    request_ref = DataViewRequestRef.model_validate(request_ref.model_dump(mode="python"))
    schema = SchemaInfo(name="polisyos.core.DataSnapshot", version="0.3.0")
    complete_ref = store.put_json(
        DataSnapshotOwnerBound(
            data_ref=data_ref,
            source_lineage=FabricBridgeDataSnapshotLineage(
                data_view_request_ref=request_ref,
            ),
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=schema,
            inputs=[
                input_ref_from_artifact_ref(request_ref, role="data_view_request_ref"),
                input_ref_from_artifact_ref(data_ref, role="data_ref"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    restored = validate_core_model_json_artifact(DataSnapshot, store, complete_ref)
    assert restored.source_lineage is not None

    incomplete_ref = store.put_json(
        DataSnapshot(data_ref=data_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=schema,
            inputs=[input_ref_from_artifact_ref(data_ref, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(CanonicalProfileRefusalError, match="required_field_missing"):
        validate_core_model_json_artifact(DataSnapshot, store, incomplete_ref)


_NULLABLE_CONTAINER_TERMINAL_VALIDATIONS = 0


class _NullableContainerWireKind(str, Enum):
    OBSERVED = "observed"
    ESTIMATED = "estimated"


class _NullableContainerWireLeaf(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: _NullableContainerWireKind
    row_index: int
    coordinates: tuple[float, float]

    @model_validator(mode="after")
    def validate_terminal(self) -> _NullableContainerWireLeaf:
        global _NULLABLE_CONTAINER_TERMINAL_VALIDATIONS
        _NULLABLE_CONTAINER_TERMINAL_VALIDATIONS += 1
        if self.row_index < 0:
            raise ValueError("nullable container row index must be nonnegative")
        return self


class _NullableModelContainerEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    mapped: Mapping[str, _NullableContainerWireLeaf] | None
    listed: list[_NullableContainerWireLeaf] | None
    tupled: tuple[_NullableContainerWireLeaf, ...] | None
    nested: Mapping[str, list[tuple[_NullableContainerWireLeaf | None, ...]]] | None


def _nullable_model_container_envelope() -> _NullableModelContainerEnvelope:
    def leaf(index: int) -> _NullableContainerWireLeaf:
        return _NullableContainerWireLeaf(
            kind=_NullableContainerWireKind.OBSERVED,
            row_index=index,
            coordinates=(float(index), float(index + 1)),
        )

    return _NullableModelContainerEnvelope(
        mapped={"a": leaf(0)},
        listed=[leaf(1)],
        tupled=(leaf(2),),
        nested={"group": [(leaf(3), None)]},
    )


def _nullable_container_leaf_occurrences(value: object) -> int:
    """Count actual fixture model occurrences, independently of wire markers."""
    if isinstance(value, _NullableContainerWireLeaf):
        return 1
    if isinstance(value, BaseModel):
        return sum(
            _nullable_container_leaf_occurrences(getattr(value, name))
            for name in type(value).model_fields
        )
    if isinstance(value, Mapping):
        return sum(_nullable_container_leaf_occurrences(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return sum(_nullable_container_leaf_occurrences(item) for item in value)
    return 0


def _read_nullable_container_model(model, store, ref, raw, reader_route):
    if reader_route == "bounded":
        bounded = read_core_json_artifact_bounded(
            store,
            ref,
            limits=CoreJsonReadLimits(
                max_bytes=len(raw),
                max_depth=16,
                max_elements=512,
                max_manifest_bytes=4096,
            ),
        )
        return validate_core_model_bounded_read(model, bounded)
    return validate_core_model_json_artifact(model, store, ref)


@pytest.mark.parametrize(
    ("writer_form", "reader_route"),
    [
        pytest.param("python-model", "full", id="full-python-model"),
        pytest.param("json-model-dump", "full", id="full-json-model-dump"),
        pytest.param("python-model", "bounded", id="bounded-python-model"),
        pytest.param("json-model-dump", "bounded", id="bounded-json-model-dump"),
    ],
)
def test_nullable_model_containers_reify_native_types_once_through_selected_core(
    tmp_path, writer_form, reader_route
) -> None:
    global _NULLABLE_CONTAINER_TERMINAL_VALIDATIONS
    source = _nullable_model_container_envelope()
    expected_terminal_validations = _nullable_container_leaf_occurrences(source)
    payload = source if writer_form == "python-model" else source.model_dump(mode="json")
    _store, ref, raw = _profiled_core_json_store(tmp_path, payload, return_selected_profile=True)
    fresh = FileSystemCAS(tmp_path / "typed-cas")
    _NULLABLE_CONTAINER_TERMINAL_VALIDATIONS = 0

    assert ref.manifest_profile_sha256 is not None
    assert read_core_json_artifact_bytes(fresh, ref) == raw
    restored = _read_nullable_container_model(
        _NullableModelContainerEnvelope, fresh, ref, raw, reader_route
    )

    assert restored == source
    assert isinstance(restored.mapped["a"].kind, _NullableContainerWireKind)
    assert isinstance(restored.listed[0].coordinates, tuple)
    assert isinstance(restored.tupled, tuple)
    assert isinstance(restored.nested["group"][0], tuple)
    assert restored.nested["group"][0][1] is None
    assert expected_terminal_validations == _NULLABLE_CONTAINER_TERMINAL_VALIDATIONS


@pytest.mark.parametrize("reader_route", ["full", "bounded"])
def test_nullable_model_containers_keep_required_fields_and_explicit_nulls(
    tmp_path, reader_route
) -> None:
    payload = _nullable_model_container_envelope().model_dump(mode="json")
    for field in _NullableModelContainerEnvelope.model_fields:
        missing = {key: value for key, value in payload.items() if key != field}
        _store, ref, raw = _profiled_core_json_store(
            tmp_path / field, missing, return_selected_profile=True
        )
        with pytest.raises(ValidationError):
            _read_nullable_container_model(
                _NullableModelContainerEnvelope,
                FileSystemCAS(tmp_path / field / "typed-cas"),
                ref,
                raw,
                reader_route,
            )
    nulls = dict.fromkeys(_NullableModelContainerEnvelope.model_fields)
    _store, ref, raw = _profiled_core_json_store(
        tmp_path / "nulls", nulls, return_selected_profile=True
    )
    restored = _read_nullable_container_model(
        _NullableModelContainerEnvelope,
        FileSystemCAS(tmp_path / "nulls" / "typed-cas"),
        ref,
        raw,
        reader_route,
    )
    assert all(getattr(restored, name) is None for name in type(restored).model_fields)


@pytest.mark.parametrize("reader_route", ["full", "bounded"])
@pytest.mark.parametrize(
    "mutation",
    ["enum", "numeric_string", "boolean_index", "tuple_shape", "extra_field", "terminal_rule"],
)
def test_nullable_model_containers_refuse_invalid_present_content(
    tmp_path, mutation, reader_route
) -> None:
    payload = _nullable_model_container_envelope().model_dump(mode="json")
    if mutation == "enum":
        payload["mapped"]["a"]["kind"] = "future_kind"
    elif mutation == "numeric_string":
        payload["nested"]["group"][0][0]["coordinates"][0] = "3.0"
    elif mutation == "boolean_index":
        payload["listed"][0]["row_index"] = True
    elif mutation == "tuple_shape":
        payload["tupled"][0]["coordinates"] = [2.0]
    elif mutation == "extra_field":
        payload["mapped"]["a"]["unexpected"] = "not admitted"
    else:
        payload["nested"]["group"][0][0]["row_index"] = -1
    _store, ref, raw = _profiled_core_json_store(tmp_path, payload, return_selected_profile=True)

    with pytest.raises(ValidationError):
        _read_nullable_container_model(
            _NullableModelContainerEnvelope,
            FileSystemCAS(tmp_path / "typed-cas"),
            ref,
            raw,
            reader_route,
        )


class _NullableAmbiguousModelContainer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    rows: Mapping[str, _SchemaAmbiguousUnionPayload] | None


@pytest.mark.parametrize("reader_route", ["full", "bounded"])
def test_nullable_model_container_keeps_existing_same_shape_union_refusal(
    tmp_path, reader_route
) -> None:
    # The existing ambiguous Decimal-wire case now sits inside a nullable mapping.
    # Null unwrapping must not choose a competing non-null model on its behalf.
    payload = {"rows": {"one": {"selected": {"amount": "7.50"}}}}
    _store, ref, raw = _profiled_core_json_store(tmp_path, payload, return_selected_profile=True)
    with pytest.raises(ValidationError):
        _read_nullable_container_model(
            _NullableAmbiguousModelContainer,
            FileSystemCAS(tmp_path / "typed-cas"),
            ref,
            raw,
            reader_route,
        )


def _v3_reader_seed() -> tuple[bytes, dict[str, object]]:
    # This wire tree is specified independently of the codec under test.
    wire_tree = {
        "native": {"_type": "decimal", "value": "1.0"},
        "raw": {"_type": "mapping", "entries": [["_type", "decimal"], ["value", "1.0"]]},
        "nested": [{"_type": "mapping", "entries": [["_type", None], ["kept", None]]}],
        "escape": {
            "_type": "mapping",
            "entries": [["_type", "mapping"], ["entries", [["_type", "future"]]]],
        },
    }
    wire = json.dumps(wire_tree, sort_keys=True, separators=(",", ":")).encode()
    expected = {
        "native": Decimal("1.0"),
        "raw": {"_type": "decimal", "value": "1.0"},
        "nested": [{"_type": None, "kept": None}],
        "escape": {"_type": "mapping", "entries": [["_type", "future"]]},
    }
    return wire, expected


def _persist_v3_reader_seed(tmp_path, wire: bytes):
    root = tmp_path / "v3-reader-cas"
    ref = FileSystemCAS(root).put_bytes(
        wire,
        PutOptions(
            kind="test.v3.reader",
            media_type="application/json",
            canon=CanonInfo(version="0.3.0", exclude_none=False),
        ),
        return_selected_profile=True,
    )
    return root, ref


def _independent_wire_shape(value: object) -> tuple[int, int]:
    # JSON lexical nodes count containers, member names and values. Container
    # depth is independent of the decoded logical .3 mapping depth.
    if type(value) is dict:
        children = [_independent_wire_shape(child) for child in value.values()]
        return 1 + len(value) + sum(n for n, _ in children), 1 + max(
            (d for _, d in children), default=0
        )
    if type(value) is list:
        children = [_independent_wire_shape(child) for child in value]
        return 1 + sum(n for n, _ in children), 1 + max((d for _, d in children), default=0)
    return 1, 0


def test_v3_nested_selected_readers_preserve_independent_value_types(tmp_path) -> None:
    wire, expected = _v3_reader_seed()
    root, ref = _persist_v3_reader_seed(tmp_path, wire)
    read = read_core_json_artifact(FileSystemCAS(root), ref)
    assert read.value == expected
    assert type(read.value["native"]) is Decimal
    assert type(read.value["raw"]) is dict
    assert type(read.value["escape"]) is dict
    assert read.reader_policy_id == "core-tag-policy@2"
    assert (
        asyncio.run(aload_core_json_artifact(AsyncArtifactStoreAdapter(FileSystemCAS(root)), ref))
        == expected
    )


def test_v3_selected_frames_use_their_profile_instead_of_default_decoder(tmp_path) -> None:
    wire, expected = _v3_reader_seed()
    framed = len(wire).to_bytes(8, "big") + wire
    root, ref = _persist_v3_reader_seed(tmp_path, framed)
    assert load_core_json_frame_records(FileSystemCAS(root), ref) == [expected]


def test_v3_bounded_reader_exact_wire_and_one_over_limits(tmp_path, monkeypatch) -> None:
    wire, expected = _v3_reader_seed()
    root, ref = _persist_v3_reader_seed(tmp_path, wire)
    nodes, depth = _independent_wire_shape(json.loads(wire))
    store = FileSystemCAS(root)
    manifest_size = len(store.get_raw_manifest_bytes(ref))
    exact = CoreJsonReadLimits(len(wire), depth, nodes, manifest_size)
    read = read_core_json_artifact_bounded(store, ref, limits=exact)
    assert read.value == expected
    assert read.profile_read.reader_policy_id == "core-tag-policy@2"
    assert (read.observed_bytes, read.observed_depth, read.observed_elements) == (
        len(wire),
        depth,
        nodes,
    )

    from polisyos.core.artifacts import canonical_profile as profile_owner

    decode_events = []

    def forbidden_decode(*args, **kwargs):
        decode_events.append("materialize")
        raise AssertionError("oversized payload reached the value decoder")

    monkeypatch.setattr(profile_owner, "_decode_core_payload_under_declaration", forbidden_decode)
    for field in ("max_bytes", "max_depth", "max_elements", "max_manifest_bytes"):
        smaller = replace(exact, **{field: getattr(exact, field) - 1})
        with pytest.raises(CanonicalProfileRefusalError):
            read_core_json_artifact_bounded(FileSystemCAS(root), ref, limits=smaller)
        assert decode_events == []


def test_same_payload_selected_v2_and_v3_views_keep_distinct_reader_policies(tmp_path) -> None:
    root = tmp_path / "versions-cas"
    store = FileSystemCAS(root)
    wire = b'{"value":1}'
    refs = [
        store.put_bytes(
            wire,
            PutOptions(
                kind="test.selected.version",
                media_type="application/json",
                canon=CanonInfo(version=version),
            ),
            return_selected_profile=True,
        )
        for version in ("0.2.0", "0.3.0")
    ]
    assert refs[0].artifact_id == refs[1].artifact_id
    assert refs[0].manifest_profile_sha256 != refs[1].manifest_profile_sha256
    for ref, policy in zip(refs, ("core-tag-policy@1", "core-tag-policy@2"), strict=True):
        read = read_core_json_artifact(FileSystemCAS(root), ref)
        assert read.value == {"value": 1}
        assert read.reader_policy_id == policy


def test_v3_selected_float_carrier_retains_negative_zero_and_raw_shape(tmp_path) -> None:
    wire = (
        b'{"native":{"_type":"float_hex","value":"-0x0.0p+0"},'
        b'"raw":{"_type":"mapping","entries":[["_type","float_hex"],'
        b'["value","-0x0.0p+0"]]}}'
    )
    root = tmp_path / "carrier-cas"
    ref = FileSystemCAS(root).put_bytes(
        wire,
        PutOptions(
            kind="test.selected.carrier",
            media_type="application/json",
            canon=CanonInfo(version="0.3.0", forbid_floats=False),
        ),
        return_selected_profile=True,
    )
    value = read_core_json_artifact(FileSystemCAS(root), ref).value
    assert type(value["native"]) is FloatHexRepresentation
    assert value["native"].value == "-0x0.0p+0"
    assert value["raw"] == {"_type": "float_hex", "value": "-0x0.0p+0"}


def test_v3_bounded_reader_has_no_unbounded_backend_fallback(tmp_path) -> None:
    wire, _expected = _v3_reader_seed()
    root, ref = _persist_v3_reader_seed(tmp_path, wire)
    inner = FileSystemCAS(root)
    nodes, depth = _independent_wire_shape(json.loads(wire))
    limits = CoreJsonReadLimits(len(wire), depth, nodes, len(inner.get_raw_manifest_bytes(ref)))
    events = []

    class MissingBoundedBackend:
        open_member_bounded = None

        def __getattr__(self, name):
            return getattr(inner, name)

        def get_bytes(self, selector):
            events.append("unbounded-payload")
            return inner.get_bytes(selector)

        def open_member(self, *args, **kwargs):
            events.append("unbounded-stream")
            return inner.open_member(*args, **kwargs)

    with pytest.raises(CanonicalProfileRefusalError):
        read_core_json_artifact_bounded(MissingBoundedBackend(), ref, limits=limits)
    assert events == []
