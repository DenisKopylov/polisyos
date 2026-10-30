from __future__ import annotations

import json
from collections import UserList
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Protocol, get_args, get_origin
from uuid import UUID

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    PlainValidator,
    PrivateAttr,
    RootModel,
    WithJsonSchema,
    model_serializer,
)
from pydantic_core import CoreSchema, core_schema

import polisyos.core.artifacts.ir_adapter as core_ir_adapter
import polisyos.ir.artifacts.contracts as ir_artifact_contracts
import polisyos.ir.model_layer.canon as ir_canon
from polisyos.core.artifacts import (
    ArtifactIntegrityError,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    ensure_ir_artifact_store,
    matches_artifact_store_protocol,
)
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
    ArtifactRef as CoreArtifactRef,
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
from polisyos.core.artifacts.protocol import CoreJSONArtifactStore, resolve_manifest_by_profile
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec as CoreCanonSpec
from polisyos.core.canon import CanonViolation as CoreCanonViolation
from polisyos.core.canon import from_canonical_bytes as from_core_canonical_bytes
from polisyos.core.components.ids import ComponentId
from polisyos.core.contracts.scientist import FailureCardRef
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts.contracts import ArtifactID as IRArtifactID
from polisyos.ir.artifacts.contracts import CanonInfo as IRCanonInfo
from polisyos.ir.artifacts.contracts import InputRef as IRInputRef
from polisyos.ir.artifacts.contracts import SchemaInfo as IRSchemaInfo
from polisyos.ir.artifacts.contracts import StorePutOptions, normalize_artifact_ref
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
from polisyos.ir.model_layer.canon import CanonViolation as IRCanonViolation
from polisyos.ir.model_layer.canon import to_canonical_bytes as to_ir_canonical_bytes

_IR_INCOMPATIBLE_TAG_PAYLOADS = [
    pytest.param(
        {"_type": "float_hex", "value": "0x1.8p+1"},
        id="core-only-float-hex",
    ),
    pytest.param(
        {"_type": "bytes_hex", "value": "00ff"},
        id="core-only-bytes-hex",
    ),
    pytest.param(
        {"_type": "array_digest", "digest": "sha256:abc", "length": 2},
        id="core-only-array-digest",
    ),
    pytest.param(
        {"_type": "float-hex", "value": "0x1.8p+1"},
        id="unknown-synonym",
    ),
    pytest.param(
        {"_type": ["float_hex"], "value": "0x1.8p+1"},
        id="malformed-tag-kind",
    ),
    pytest.param(
        {"nested": {"_type": "float_hex", "value": "0x1.8p+1"}},
        id="nested-core-only-float-hex",
    ),
]


def test_ir_adapter_round_trips_backtest_report(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    report = BacktestReport(report_id="bt.adapter")

    ref = persist_backtest_report(_ensure_ir_artifact_store(ir_store), report)
    loaded = load_backtest_report(_ensure_ir_artifact_store(ir_store), ref)

    assert loaded.report_id == "bt.adapter"
    assert loaded.n_scenarios == 0


def test_adapter_refuses_writer_that_accepts_but_drops_selected_profile() -> None:
    class ProfileDroppingStore:
        def __init__(self) -> None:
            self.calls: list[bool] = []

        def put_bytes(
            self,
            _data: bytes,
            opts: ArtifactWriteOptions,
            *,
            return_selected_profile: bool = False,
        ) -> CoreArtifactRef:
            self.calls.append(return_selected_profile)
            return CoreArtifactRef(
                artifact_id=CoreArtifactID.from_sha256_hex("c" * 64),
                kind=opts.kind,
                media_type=opts.media_type,
            )

    from polisyos.core import artifacts

    store = ProfileDroppingStore()
    adapter = artifacts.CoreToIRArtifactStoreAdapter(store)

    with pytest.raises(ValueError, match="artifact_write_selected_profile_missing"):
        adapter.put_bytes(
            b"payload",
            ArtifactWriteOptions(kind="test.selected-profile-drop", media_type="application/json"),
            return_selected_profile=True,
        )

    assert store.calls == [True]


def test_ensure_ir_artifact_store_preserves_existing_adapter(tmp_path) -> None:
    adapter = CoreToIRArtifactStoreAdapter(FileSystemCAS(tmp_path / ".polisyos"))

    assert ensure_ir_artifact_store(adapter) is adapter


def test_ir_adapter_refuses_selector_objects_with_unrecognized_fields(tmp_path) -> None:
    """Unknown fields on structural refs must not disappear at the Core boundary."""
    store = FileSystemCAS(tmp_path / "strict-selector")
    ref = store.put_bytes(
        b"selector target",
        ArtifactWriteOptions(kind="test.strict-selector", media_type="application/octet-stream"),
    )
    adapter = ensure_ir_artifact_store(store)

    class SelectorWithExtraField:
        def __init__(self) -> None:
            self.artifact_id = ref.artifact_id
            self.kind = ref.kind
            self.media_type = ref.media_type
            self.manifest_profile_sha256 = ref.manifest_profile_sha256
            self.schema_name = "unrecognized-selector-field"

    class PropertySelectorWithExtraField:
        @property
        def artifact_id(self) -> object:
            return ref.artifact_id

        @property
        def kind(self) -> str:
            return ref.kind

        @property
        def media_type(self) -> str:
            return ref.media_type

        @property
        def schema_name(self) -> str:
            return "unrecognized-property-selector-field"

    class SelectorModelWithExcludedExtra(BaseModel):
        model_config = ConfigDict(extra="forbid")

        artifact_id: object
        kind: str
        media_type: str
        manifest_profile_sha256: str | None = None
        schema_name: str = Field(exclude=True)

    class MappingSelectorWithExtraProperty(dict[str, object]):
        @property
        def schema_name(self) -> str:
            return "unrecognized-mapping-property-selector-field"

    @dataclass
    class DataclassSelectorWithExtra:
        artifact_id: object
        kind: str
        media_type: str
        schema_name: str

    class RootOnlyObject:
        root = ref.artifact_id

    class StringDumpObject:
        def model_dump(self, *, mode: str) -> str:
            return str(ref.artifact_id)

    invalid_selectors = (
        SelectorWithExtraField(),
        DataclassSelectorWithExtra(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            media_type=ref.media_type,
            schema_name="unrecognized-dataclass-selector-field",
        ),
        PropertySelectorWithExtraField(),
        SelectorModelWithExcludedExtra(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            media_type=ref.media_type,
            manifest_profile_sha256=ref.manifest_profile_sha256,
            schema_name="hidden-unrecognized-selector-field",
        ),
        {
            "artifact_id": str(ref.artifact_id),
            "kind": ref.kind,
            "media_type": ref.media_type,
            "schema_name": "unrecognized-mapping-selector-field",
        },
        MappingSelectorWithExtraProperty(
            {
                "artifact_id": str(ref.artifact_id),
                "kind": ref.kind,
                "media_type": ref.media_type,
            }
        ),
        {
            "artifact_id": str(ref.artifact_id),
            "kind": ref.kind,
            "media_type": ref.media_type,
            "manifest_profile_sha256": "sha256:not-a-profile",
        },
        {"artifact_id": str(ref.artifact_id), "kind": ref.kind},
        RootOnlyObject(),
        StringDumpObject(),
        object(),
    )
    selector_readers = (
        adapter.get_bytes,
        adapter.has,
        adapter.get_manifest,
        adapter.get_raw_manifest_bytes,
        adapter.get_manifest_bytes,
        adapter.verify,
    )
    for selector in invalid_selectors:
        for read in selector_readers:
            with pytest.raises(TypeError, match="Invalid Core artifact selector"):
                read(selector)

    assert adapter.get_manifest(
        CoreArtifactID.model_validate(str(ref.artifact_id))
    ).artifact_id == (ref.artifact_id)


def test_ir_adapter_projects_core_ref_subclass_to_selected_manifest_view(tmp_path) -> None:
    """A known Core ref subtype retains its selected profile through the IR adapter."""
    store = FileSystemCAS(tmp_path / "core-ref-subclass")
    payload = b"same bytes, two manifest views"
    default_ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="scientist.failure_card",
            media_type="application/json",
            schema=CoreSchemaInfo(name="test.failure-card", version="1"),
        ),
    )
    selected_ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="scientist.failure_card",
            media_type="application/json",
            schema=CoreSchemaInfo(name="test.failure-card", version="2"),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    assert selected_ref.manifest_profile_sha256 != default_ref.manifest_profile_sha256

    subtype_ref = FailureCardRef(
        **selected_ref.model_dump(mode="python"),
        attempt_number=1,
        error_code="candidate",
        source_step="test",
        can_retry=False,
    )
    adapter = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "core-ref-subclass"))

    selected_manifest = adapter.get_manifest(subtype_ref)
    assert selected_manifest.artifact_schema is not None
    assert selected_manifest.artifact_schema.version == "2"
    assert adapter.get_bytes(subtype_ref) == payload


def test_ensure_ir_artifact_store_adapts_dynamic_core_facade_selected_view(
    tmp_path, monkeypatch
) -> None:
    """A delegated Core facade retains typed selected refs at the IR read boundary."""

    class DynamicCoreFacade:
        def __init__(self, target) -> None:
            self._target = target

        def __getattr__(self, name):
            return getattr(self._target, name)

    exact_bytes = b'{"nested":{"value":1}}'
    core_store = FileSystemCAS(tmp_path / "dynamic-core-facade")
    default_ref = core_store.put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.ir-dynamic-selected-view",
            media_type="application/json",
            canon=CoreCanonInfo(max_depth=0),
        ),
    )
    selected_ref = core_store.put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.ir-dynamic-selected-view",
            media_type="application/json",
            canon=CoreCanonInfo(max_depth=8),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    selector = {
        "artifact_id": str(selected_ref.artifact_id),
        "kind": selected_ref.kind,
        "media_type": selected_ref.media_type,
        "manifest_profile_sha256": selected_ref.manifest_profile_sha256,
    }
    observed_selectors = []
    read_raw_manifest_bytes = core_store.get_raw_manifest_bytes

    def record_manifest_selector(value, *, manifest_profile_sha256=None):
        observed_selectors.append(value)
        return read_raw_manifest_bytes(value, manifest_profile_sha256=manifest_profile_sha256)

    monkeypatch.setattr(core_store, "get_raw_manifest_bytes", record_manifest_selector)

    ir_store = ensure_ir_artifact_store(DynamicCoreFacade(core_store))

    assert isinstance(ir_store, CoreToIRArtifactStoreAdapter)
    assert get_json_artifact(ir_store, selector) == {"nested": {"value": 1}}
    assert len(observed_selectors) == 1
    assert isinstance(observed_selectors[0], CoreArtifactRef)
    assert observed_selectors[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256


def test_core_json_store_without_legacy_manifest_alias_reads_selected_raw_view(tmp_path) -> None:
    """The Core JSON reader port alone supports an exact selected-view IR read."""

    class RawOnlyCoreJSONStore:
        def __init__(self, target: FileSystemCAS) -> None:
            self._target = target
            self.raw_selectors: list[object] = []

        def __getattr__(self, name: str):
            if name == "get_manifest_bytes":
                raise AttributeError(name)
            return getattr(self._target, name)

        def get_raw_manifest_bytes(
            self, selector, *, manifest_profile_sha256: str | None = None
        ) -> bytes:
            self.raw_selectors.append(selector)
            return self._target.get_raw_manifest_bytes(
                selector, manifest_profile_sha256=manifest_profile_sha256
            )

    payload = b'{"nested":{"value":1}}'
    core_store = FileSystemCAS(tmp_path / "core-json-raw-only")
    core_store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="test.ir-core-json-raw-only",
            media_type="application/json",
            canon=CoreCanonInfo(max_depth=0),
        ),
    )
    selected_ref = core_store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="test.ir-core-json-raw-only",
            media_type="application/json",
            canon=CoreCanonInfo(max_depth=8),
        ),
    )
    assert selected_ref.manifest_profile_sha256 is not None

    raw_only_store = RawOnlyCoreJSONStore(core_store)
    ir_store = ensure_ir_artifact_store(raw_only_store)

    assert isinstance(ir_store, CoreToIRArtifactStoreAdapter)
    assert get_json_artifact(ir_store, selected_ref) == {"nested": {"value": 1}}
    assert len(raw_only_store.raw_selectors) == 1
    selected = raw_only_store.raw_selectors[0]
    assert isinstance(selected, CoreArtifactRef)
    assert selected.manifest_profile_sha256 == selected_ref.manifest_profile_sha256


@pytest.mark.parametrize(
    ("raw_result", "expected_error", "message"),
    [
        pytest.param(
            "malformed",
            IRCanonViolation,
            "unsupported_ir_canon_profile",
            id="malformed-raw-profile",
        ),
        pytest.param("non-bytes", TypeError, "must return bytes", id="non-bytes-raw-result"),
        pytest.param("raises", OSError, "raw reader failure", id="raw-reader-error"),
    ],
)
def test_ir_adapter_does_not_fallback_from_required_raw_reader(
    tmp_path, raw_result: str, expected_error: type[Exception], message: str
) -> None:
    """A present raw capability is authoritative even if a legacy alias disagrees."""

    class DivergentCoreJSONStore:
        def __init__(self, target: FileSystemCAS) -> None:
            self._target = target
            self.raw_result = raw_result
            self.raw_reads = 0
            self.legacy_alias_reads = 0
            self.payload_reads = 0

        def __getattr__(self, name: str):
            return getattr(self._target, name)

        def get_raw_manifest_bytes(
            self, selector, *, manifest_profile_sha256: str | None = None
        ) -> object:
            self.raw_reads += 1
            if self.raw_result == "raises":
                raise OSError("raw reader failure")
            raw = self._target.get_raw_manifest_bytes(
                selector, manifest_profile_sha256=manifest_profile_sha256
            )
            if self.raw_result == "non-bytes":
                return "not bytes"
            manifest = json.loads(raw)
            manifest["canon"] = {}
            return json.dumps(manifest, separators=(",", ":")).encode()

        def get_manifest_bytes(self, selector) -> bytes:
            self.legacy_alias_reads += 1
            return self._target.get_raw_manifest_bytes(selector)

        def get_bytes(self, selector) -> bytes:
            self.payload_reads += 1
            return self._target.get_bytes(selector)

    core_store = FileSystemCAS(tmp_path / "malformed-raw-profile")
    ref = core_store.put_bytes(
        b'{"value":1}',
        ArtifactWriteOptions(
            kind="test.ir-malformed-required-raw-profile",
            media_type="application/json",
            canon=CoreCanonInfo(),
        ),
    )
    conflicting_store = DivergentCoreJSONStore(core_store)

    with pytest.raises(expected_error, match=message):
        get_json_artifact(ensure_ir_artifact_store(conflicting_store), ref)

    assert conflicting_store.raw_reads == 1
    assert conflicting_store.legacy_alias_reads == 0
    assert conflicting_store.payload_reads == 0


def test_runtime_protocol_bridge_derives_inherited_and_annotated_members() -> None:
    """Dynamic facades satisfy the complete inherited source Protocol, not a local list."""

    class ParentSurface(Protocol):
        label: str

        def parent_call(self) -> None: ...

    class CompleteSurface(ParentSurface, Protocol):
        def child_call(self) -> None: ...

    class DynamicFacade:
        label = "present"

        def __getattr__(self, name: str):
            if name in {"parent_call", "child_call"}:
                return lambda: None
            raise AttributeError(name)

    class MissingInheritedCall(DynamicFacade):
        def __getattr__(self, name: str):
            if name == "parent_call":
                raise AttributeError(name)
            return super().__getattr__(name)

    assert matches_artifact_store_protocol(DynamicFacade(), CompleteSurface)
    assert not matches_artifact_store_protocol(MissingInheritedCall(), CompleteSurface)


def test_static_ir_adapter_cannot_launder_missing_core_json_reader(tmp_path) -> None:
    """A Core-shaped IR adapter does not invent its owner's raw-manifest capability."""

    class BaseOnlyFacade:
        def __init__(self, target: object) -> None:
            self._target = target

        def __getattr__(self, name: str):
            if name == "get_raw_manifest_bytes":
                raise AttributeError(name)
            return getattr(self._target, name)

    owner = FileSystemCAS(tmp_path / "base-only-adapter")
    ref = owner.put_bytes(
        b'{"value":1}',
        ArtifactWriteOptions(
            kind="test.ir-core-base-only",
            media_type="application/json",
            canon=CoreCanonInfo(),
        ),
    )
    adapter = CoreToIRArtifactStoreAdapter(BaseOnlyFacade(owner))

    # Legacy full-store adapter advertises this forwarding method structurally.
    # Its real owner lacks the port; the matcher and actual read still refuse.
    # This pre-existing behavior is a bounded residual outside narrow-reader admission.
    from polisyos.core.artifacts import RawManifestBytesReader

    assert isinstance(adapter, RawManifestBytesReader)
    assert not matches_artifact_store_protocol(adapter, CoreJSONArtifactStore)
    with pytest.raises(TypeError, match="must expose get_raw_manifest_bytes"):
        get_json_artifact(adapter, ref)


def test_ir_adapter_selected_core_methods_keep_bytes_options_and_exact_profile(tmp_path) -> None:
    """The shared adapter exposes Core writes and resolves a profile without default metadata."""
    store = FileSystemCAS(tmp_path / "profile-addressed-cas")
    adapter = ensure_ir_artifact_store(store)
    source = store.put_bytes(
        b'{"source":"lineage"}',
        ArtifactWriteOptions(kind="test.ir-profile-source", media_type="application/json"),
    )
    exact_bytes = b'{"nested":{"value":1}}'
    write_options = ArtifactWriteOptions(
        kind="test.ir-profile-default",
        media_type="application/json",
        schema=CoreSchemaInfo(name="test.ir-profile-default", version="1"),
        producer=ProducerInfo(component="polisyos.tests.ir_adapter", version="1"),
        env=EnvInfo(python="3.14", platform="test", deps_lock_hash="lock-hash"),
        inputs=[CoreInputRef(artifact_id=source.artifact_id, role="source")],
        canon=CoreCanonInfo(max_depth=0),
        governance=ArtifactGovernanceInfo(classification="internal"),
        tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a"),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id="closure-a",
            status="closed",
            closure_sha256="1" * 64,
            run_id="run-a",
            job_id="job-a",
            tenant_id="tenant-a",
            cell_id="cell-a",
            evidence_input_refs=(str(source.artifact_id),),
        ),
        authority=ArtifactAuthorityInfo(
            authority_envelope_ref="sha256:" + "2" * 64,
            diagnostic_event_ref="sha256:" + "3" * 64,
            manifest_ref="cas-manifest://sha256:" + "4" * 64,
            payload_sha256=sha256(exact_bytes).hexdigest(),
        ),
        warnings=[WarningRecord(code="retained", msg="keep this warning")],
    )
    default_ref = adapter.put_bytes(exact_bytes, write_options)
    selected_ref = adapter.put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.ir-profile-selected",
            media_type="application/json",
            schema=CoreSchemaInfo(name="test.ir-profile-selected", version="2"),
            canon=CoreCanonInfo(max_depth=8),
        ),
    )

    assert default_ref.artifact_id == selected_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    assert adapter.has(selected_ref)
    assert adapter.verify(selected_ref).ok
    assert adapter.get_bytes(selected_ref) == exact_bytes

    selected_manifest = resolve_manifest_by_profile(
        adapter,
        selected_ref.artifact_id,
        selected_ref.manifest_profile_sha256,
    )
    assert selected_manifest.kind == "test.ir-profile-selected"
    assert selected_manifest.artifact_schema == CoreSchemaInfo(
        name="test.ir-profile-selected", version="2"
    )
    assert selected_manifest.canon.max_depth == 8

    default_manifest = store.get_manifest(default_ref)
    assert default_manifest.kind == write_options.kind
    assert default_manifest.media_type == write_options.media_type
    assert default_manifest.artifact_schema == write_options.schema
    assert default_manifest.producer == write_options.producer
    assert default_manifest.env == write_options.env
    assert default_manifest.inputs == write_options.inputs
    assert default_manifest.canon == write_options.canon
    assert default_manifest.governance == write_options.governance
    assert default_manifest.tenant_context == write_options.tenant_context
    assert default_manifest.same_input_closure == write_options.same_input_closure
    assert default_manifest.authority == write_options.authority
    assert default_manifest.warnings == write_options.warnings


def test_profileless_authority_link_keeps_legacy_manifest_hash_shape(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "profileless-authority-link")
    legacy_authority = ArtifactAuthorityInfo(
        authority_envelope_ref="sha256:" + "2" * 64,
        diagnostic_event_ref="sha256:" + "3" * 64,
        manifest_ref="cas-manifest://sha256:" + "4" * 64,
        payload_sha256="5" * 64,
    )
    ref = store.put_bytes(
        b'{"legacy":"authority-link"}',
        ArtifactWriteOptions(
            kind="test.profileless-authority-link",
            media_type="application/json",
            authority=legacy_authority,
        ),
    )

    stored_manifest = from_core_canonical_bytes(store.get_manifest_bytes(ref))

    assert "authority_envelope_manifest_profile_sha256" not in stored_manifest["authority"]
    assert store.get_manifest(ref).authority == legacy_authority
    assert store.verify(ref).ok


def test_profile_resolver_refuses_malformed_unknown_and_content_mismatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "profile-resolution-negative")
    payload = b'{"value":"verified"}'
    ref = store.put_bytes(
        payload,
        ArtifactWriteOptions(kind="test.ir-profile-resolution", media_type="application/json"),
    )
    assert ref.manifest_profile_sha256 is None

    with pytest.raises(ValueError, match="manifest_profile_sha256"):
        resolve_manifest_by_profile(store, ref.artifact_id, "sha256:not-a-digest")
    with pytest.raises(FileNotFoundError):
        resolve_manifest_by_profile(store, ref.artifact_id, "sha256:" + "f" * 64)

    blob_path, _manifest_path = store._paths(ref.artifact_id)
    blob_path.write_bytes(b'{"value":"tampered"}')
    profile = store.get_manifest(ref).integrity.sha256
    assert profile == ref.artifact_id.hex
    from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle

    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        resolve_manifest_by_profile(
            store,
            ref.artifact_id,
            ManifestLifecycle.profile_sha256(store.get_manifest(ref)),
        )


def test_ir_write_round_trips_selected_lineage_profile_through_fresh_core_reader(tmp_path) -> None:
    root = tmp_path / "selected-lineage-cas"
    producer = FileSystemCAS(root)
    source_payload = b'{"source":"same content"}'
    source_kind = "test.ir-selected-lineage-source"
    default_ref = producer.put_bytes(
        source_payload,
        ArtifactWriteOptions(
            kind=source_kind,
            media_type="application/json",
            schema=CoreSchemaInfo(name=source_kind, version="1.0"),
            canon=CoreCanonInfo(max_depth=0),
        ),
    )
    selected_ref = producer.put_bytes(
        source_payload,
        ArtifactWriteOptions(
            kind=source_kind,
            media_type="application/json",
            schema=CoreSchemaInfo(name=source_kind, version="2.0"),
            canon=CoreCanonInfo(max_depth=8),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None

    output_ref_payload = put_json_artifact(
        _ensure_ir_artifact_store(producer),
        {"result": "linked"},
        kind="test.ir-selected-lineage-output",
        schema_name="test.ir-selected-lineage-output",
        schema_version="1.0",
        inputs=[
            {
                "artifact_id": str(selected_ref.artifact_id),
                "role": "selected_source",
                "manifest_profile_sha256": selected_ref.manifest_profile_sha256,
            }
        ],
    )

    fresh_reader = FileSystemCAS(root)
    output_ref = CoreArtifactRef.model_validate(output_ref_payload)
    output_manifest = fresh_reader.get_manifest(output_ref)
    assert len(output_manifest.inputs) == 1
    assert output_manifest.inputs[0].role == "selected_source"
    assert output_manifest.inputs[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    exact_source_ref = CoreArtifactRef(
        artifact_id=selected_ref.artifact_id,
        kind=source_kind,
        media_type="application/json",
        manifest_profile_sha256=output_manifest.inputs[0].manifest_profile_sha256,
    )
    assert fresh_reader.get_manifest(exact_source_ref).artifact_schema.version == "2.0"
    assert fresh_reader.get_bytes(exact_source_ref) == source_payload


@pytest.mark.parametrize(
    "representation",
    ["typed-options", "mapping-of-models", "mapping-of-plain-maps"],
)
def test_ir_adapter_mapping_write_options_preserve_every_core_option_field(
    tmp_path, representation
) -> None:
    """Typed and mapping metadata survive adapter projection into selected CAS bytes."""
    store = FileSystemCAS(tmp_path / ".polisyos")
    adapter = ensure_ir_artifact_store(store)
    source_ref = store.put_bytes(
        b'{"source":"typed-input"}',
        ArtifactWriteOptions(
            kind="test.ir-typed-model-options-source",
            media_type="application/json",
        ),
        return_selected_profile=True,
    )
    assert source_ref.manifest_profile_sha256 is not None

    payload = {"value": "typed-model-options"}
    canon_spec = IRCanonSpec()
    ir_canon_info = IRCanonInfo.from_spec(canon_spec)
    expected_payload_bytes = to_ir_canonical_bytes(payload, canon_spec)
    options = StorePutOptions(
        kind="test.ir-typed-model-options",
        media_type="application/json",
        schema=IRSchemaInfo(name="test.ir-typed-model-options", version="2"),
        producer=ProducerInfo(component="polisyos.tests.ir_adapter", version="1"),
        env=EnvInfo(python="3.14", platform="test", deps_lock_hash="lock-hash"),
        inputs=[
            IRInputRef(
                artifact_id=IRArtifactID(str(source_ref.artifact_id)),
                role="source",
                manifest_profile_sha256=source_ref.manifest_profile_sha256,
            )
        ],
        canon=ir_canon_info,
        governance=ArtifactGovernanceInfo(classification="internal"),
        tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a"),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id="closure-a",
            status="closed",
            closure_sha256="1" * 64,
            run_id="run-a",
            job_id="job-a",
            tenant_id="tenant-a",
            cell_id="cell-a",
            evidence_input_refs=(str(source_ref.artifact_id),),
        ),
        authority=ArtifactAuthorityInfo(
            authority_envelope_ref="sha256:" + "2" * 64,
            diagnostic_event_ref="sha256:" + "3" * 64,
            manifest_ref="cas-manifest://sha256:" + "4" * 64,
            payload_sha256=sha256(expected_payload_bytes).hexdigest(),
        ),
        warnings=[WarningRecord(code="retained", msg="keep this warning")],
    )

    def plain_projection(value):
        if isinstance(value, BaseModel):
            return plain_projection(value.model_dump(mode="python"))
        if isinstance(value, Mapping):
            return {key: plain_projection(item) for key, item in value.items()}
        if isinstance(value, list):
            return [plain_projection(item) for item in value]
        if isinstance(value, tuple):
            return tuple(plain_projection(item) for item in value)
        return value

    if representation == "typed-options":
        supplied_options = options
    elif representation == "mapping-of-models":
        supplied_options = MappingProxyType(dict(vars(options)))
    else:
        supplied_options = MappingProxyType(
            {name: plain_projection(value) for name, value in vars(options).items()}
        )
    assert isinstance(supplied_options, (StorePutOptions, Mapping))

    selected_ref = adapter.put_json(
        payload,
        supplied_options,
        canon_spec,
        return_selected_profile=True,
    )
    assert selected_ref.manifest_profile_sha256 is not None
    assert adapter.has(selected_ref)
    assert adapter.get_bytes(selected_ref) == expected_payload_bytes
    assert store.get_bytes(selected_ref) == expected_payload_bytes
    assert adapter.verify(selected_ref).ok

    selected_manifest_bytes = adapter.get_manifest_bytes(selected_ref)
    assert adapter.get_raw_manifest_bytes(selected_ref) == selected_manifest_bytes
    assert store.get_manifest_bytes(selected_ref) == selected_manifest_bytes
    raw_manifest = json.loads(selected_manifest_bytes)
    assert raw_manifest["schema"] == {
        "name": "test.ir-typed-model-options",
        "version": "2",
    }
    selected_manifest = resolve_manifest_by_profile(
        store, selected_ref.artifact_id, selected_ref.manifest_profile_sha256
    )
    assert selected_manifest == adapter.get_manifest(selected_ref)
    assert selected_manifest.kind == options.kind
    assert selected_manifest.media_type == "application/json"
    assert selected_manifest.artifact_schema == CoreSchemaInfo(
        name="test.ir-typed-model-options", version="2"
    )
    assert selected_manifest.producer == options.producer
    assert selected_manifest.env == options.env
    assert selected_manifest.inputs == [
        CoreInputRef(
            artifact_id=CoreArtifactID(str(source_ref.artifact_id)),
            role="source",
            manifest_profile_sha256=source_ref.manifest_profile_sha256,
        )
    ]
    assert selected_manifest.canon == CoreCanonInfo.model_validate(
        ir_canon_info.model_dump(mode="python")
    )
    assert selected_manifest.governance == options.governance
    assert selected_manifest.tenant_context == options.tenant_context
    assert selected_manifest.same_input_closure == options.same_input_closure
    assert selected_manifest.authority == options.authority
    assert selected_manifest.warnings == options.warnings


def _invalid_canon_field_value(annotation: object, value: object) -> object:
    """Derive a strictly invalid representative from a live canon field declaration."""
    if annotation is bool:
        return "false"
    if annotation is int:
        return float(str(value))
    if annotation is str:
        return b"not-a-string"
    if get_origin(annotation) is tuple and get_args(annotation) == (str, str):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise AssertionError("Canon separators must be a two-item sequence")
        return (value[0], 1) if isinstance(value, tuple) else [value[0], 1]
    raise AssertionError(f"Add an explicit malformed value for canon field type {annotation!r}")


def _registered_ir_tag_cases() -> dict[str, tuple[object, IRCanonSpec, dict[str, object]]]:
    """Build one actual typed value and encoded map for every registered IR tag."""
    values: dict[str, object] = {
        "datetime": datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
        "date": date(2026, 10, 14),
        "decimal": Decimal("12.30"),
        "bytes": b"\x00\xff",
        "float": 1.5,
    }
    cases: dict[str, tuple[object, IRCanonSpec, dict[str, object]]] = {}
    for tag, value in values.items():
        spec = IRCanonSpec(forbid_floats=tag != "float")
        encoded_tag = json.loads(to_ir_canonical_bytes(value, spec))
        assert encoded_tag.get("_type") == tag
        cases[tag] = (value, spec, encoded_tag)
    assert set(cases) == ir_canon._CANONICAL_TYPES
    return cases


def test_ir_adapter_strictly_validates_every_canon_mapping_field_before_persisting(
    tmp_path,
) -> None:
    """Every supplied canon field rejects lax Pydantic coercion before CAS writes."""
    core_fields = CoreCanonInfo.model_fields
    assert set(core_fields) == set(IRCanonInfo.model_fields)
    assert {name: field.annotation for name, field in core_fields.items()} == {
        name: field.annotation for name, field in IRCanonInfo.model_fields.items()
    }

    for field_name, field in core_fields.items():
        malformed_profile = CoreCanonInfo().model_dump(mode="json")
        malformed_profile[field_name] = _invalid_canon_field_value(
            field.annotation,
            malformed_profile[field_name],
        )
        store = FileSystemCAS(tmp_path / f"invalid-canon-{field_name}")
        options = {
            "kind": f"test.invalid-canon-{field_name}",
            "media_type": "application/json",
            "canon": malformed_profile,
        }

        with pytest.raises(TypeError, match="Invalid adapter option 'canon'"):
            ensure_ir_artifact_store(store).put_json(
                {"value": "must-not-be-persisted"},
                options,
                canon_spec=IRCanonSpec(),
            )

        assert store.iter_artifact_ids() == []


def test_ir_adapter_strictly_revalidates_every_typed_canon_option_form(tmp_path) -> None:
    """Every live CanonInfo field rejects compromised instances through each carrier."""
    core_fields = CoreCanonInfo.model_fields
    ir_fields = IRCanonInfo.model_fields
    assert set(core_fields) == set(ir_fields)
    assert {name: field.annotation for name, field in core_fields.items()} == {
        name: field.annotation for name, field in ir_fields.items()
    }

    for model_type in (CoreCanonInfo, IRCanonInfo):
        for field_name, field in model_type.model_fields.items():
            valid_payload = model_type().model_dump(mode="python")
            malformed = _invalid_canon_field_value(field.annotation, valid_payload[field_name])
            for constructor in ("model_copy", "model_construct"):
                if constructor == "model_copy":
                    canon = model_type().model_copy(update={field_name: malformed})
                else:
                    malformed_payload = dict(valid_payload)
                    malformed_payload[field_name] = malformed
                    canon = model_type.model_construct(**malformed_payload)

                for carrier in ("mapping", "ir_typed", "core_typed"):
                    case_id = f"{model_type.__name__}-{field_name}-{constructor}-{carrier}"
                    if carrier == "mapping":
                        options = {
                            "kind": f"test.invalid-typed-canon-{case_id}",
                            "media_type": "application/json",
                            "canon": canon,
                        }
                    elif carrier == "ir_typed":
                        options = StorePutOptions(
                            kind=f"test.invalid-typed-canon-{case_id}",
                            media_type="application/json",
                            canon=canon,
                        )
                    else:
                        options = ArtifactWriteOptions(
                            kind=f"test.invalid-typed-canon-{case_id}",
                            media_type="application/json",
                            canon=canon,
                        )

                    store = FileSystemCAS(tmp_path / case_id)
                    with pytest.raises(TypeError, match="Invalid adapter option 'canon'"):
                        ensure_ir_artifact_store(store).put_json(
                            {"value": "must-not-be-persisted"},
                            options,
                            canon_spec=IRCanonSpec(),
                        )
                    assert store.iter_artifact_ids() == [], case_id

    for carrier in ("mapping", "ir_typed", "core_typed"):
        canon = CoreCanonInfo().model_copy(update={"unmodeled_field": "must-be-refused"})
        case_id = f"typed-canon-unmodeled-{carrier}"
        if carrier == "mapping":
            options = {
                "kind": f"test.invalid-typed-canon-{case_id}",
                "media_type": "application/json",
                "canon": canon,
            }
        elif carrier == "ir_typed":
            options = StorePutOptions(
                kind=f"test.invalid-typed-canon-{case_id}",
                media_type="application/json",
                canon=canon,
            )
        else:
            options = ArtifactWriteOptions(
                kind=f"test.invalid-typed-canon-{case_id}",
                media_type="application/json",
                canon=canon,
            )
        store = FileSystemCAS(tmp_path / case_id)
        with pytest.raises(TypeError, match="unexpected field"):
            ensure_ir_artifact_store(store).put_json(
                {"value": "must-not-be-persisted"},
                options,
                canon_spec=IRCanonSpec(),
            )
        assert store.iter_artifact_ids() == [], case_id


def test_ir_adapter_accepts_absent_canon_for_each_typed_write_option_form(tmp_path) -> None:
    """A legally absent canon option still selects the explicit profile without coercion."""
    spec = IRCanonSpec(forbid_floats=False, exclude_none=False)
    options_by_carrier = {
        "mapping-absent": {
            "kind": "test.ir-canon-absent-mapping",
            "media_type": "application/json",
        },
        "mapping-none": {
            "kind": "test.ir-canon-none-mapping",
            "media_type": "application/json",
            "canon": None,
        },
        "ir-typed-none": StorePutOptions(
            kind="test.ir-canon-none-ir-typed",
            media_type="application/json",
            canon=None,
        ),
        "core-typed-none": ArtifactWriteOptions(
            kind="test.ir-canon-none-core-typed",
            media_type="application/json",
            canon=None,
        ),
    }

    for carrier, options in options_by_carrier.items():
        store = FileSystemCAS(tmp_path / carrier)
        selected = ensure_ir_artifact_store(store).put_json(
            {"present": None, "number": 1.5}, options, canon_spec=spec
        )
        assert store.get_manifest(selected).canon == CoreCanonInfo.from_spec(spec)
        assert get_json_artifact(
            ensure_ir_artifact_store(FileSystemCAS(tmp_path / carrier)), selected
        ) == {
            "present": None,
            "number": 1.5,
        }


def test_ir_adapter_accepts_non_none_core_typed_write_options_and_fresh_reader(tmp_path) -> None:
    """A valid Core typed profile persists and reopens with exact selected IR bytes."""
    root = tmp_path / ".polisyos"
    store = FileSystemCAS(root)
    adapter = ensure_ir_artifact_store(store)
    spec = IRCanonSpec(
        forbid_floats=False,
        forbid_nan_inf=False,
        exclude_none=False,
        sort_keys=False,
        separators=(", ", ": "),
        ensure_ascii=True,
    )
    selected_profile = CoreCanonInfo.from_spec(spec)
    options = ArtifactWriteOptions(
        kind="test.ir-core-typed-profile-positive",
        media_type="application/json",
        canon=selected_profile,
    )
    payload = {
        "amount": Decimal("12.30"),
        "present": None,
        "unicode": "é",
        "float": 1.5,
    }

    selected_ref = adapter.put_json(
        payload,
        options,
        canon_spec=spec,
        return_selected_profile=True,
    )

    exact_bytes = store.get_bytes(selected_ref)
    assert selected_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(selected_ref).canon == selected_profile
    assert exact_bytes == to_ir_canonical_bytes(payload, spec)

    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(root))
    decoded = get_json_artifact(fresh_reader, selected_ref)
    assert decoded == payload
    assert to_ir_canonical_bytes(decoded, spec) == exact_bytes


def test_ir_adapter_accepts_exact_json_mode_canon_mapping_and_fresh_reader(tmp_path) -> None:
    """The shared separator normalization preserves the exact accepted JSON mapping form."""
    root = tmp_path / ".polisyos"
    store = FileSystemCAS(root)
    adapter = ensure_ir_artifact_store(store)
    spec = IRCanonSpec(
        forbid_floats=False,
        forbid_nan_inf=False,
        exclude_none=False,
        sort_keys=False,
        separators=(", ", ": "),
        ensure_ascii=True,
    )
    profile_mapping = IRCanonInfo.from_spec(spec).model_dump(mode="json")
    assert profile_mapping["separators"] == [", ", ": "]

    selected_ref = adapter.put_json(
        {"amount": Decimal("12.30"), "present": None, "unicode": "é", "float": 1.5},
        {
            "kind": "test.ir-json-mode-canon-option",
            "media_type": "application/json",
            "canon": profile_mapping,
        },
        canon_spec=spec,
        return_selected_profile=True,
    )

    assert store.get_manifest(selected_ref).canon == CoreCanonInfo.from_spec(spec)
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(root))
    assert get_json_artifact(fresh_reader, selected_ref) == {
        "amount": Decimal("12.30"),
        "present": None,
        "unicode": "é",
        "float": 1.5,
    }


def test_ir_adapter_round_trips_every_registered_ir_tag_through_fresh_cas_reader(tmp_path) -> None:
    """Every registered IR typed tag survives the actual writer and fresh selected reader."""
    root = tmp_path / ".polisyos"
    store = FileSystemCAS(root)
    adapter = ensure_ir_artifact_store(store)
    cases = _registered_ir_tag_cases()
    payload = {tag: case[0] for tag, case in cases.items()}
    spec = IRCanonSpec(forbid_floats=False)
    selected_ref = adapter.put_json(
        payload,
        StorePutOptions(
            kind="test.ir-all-registered-canon-tags",
            media_type="application/json",
            canon=IRCanonInfo.from_spec(spec),
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )

    encoded = json.loads(store.get_bytes(selected_ref))
    assert {value.get("_type") for value in encoded.values()} == ir_canon._CANONICAL_TYPES
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(root))
    assert get_json_artifact(fresh_reader, selected_ref) == payload


def test_ir_adapter_rejects_nonconformant_registered_ir_tag_mappings_before_persisting(
    tmp_path,
) -> None:
    """Malformed recognized tags and unknown tag members never cross the CAS boundary."""
    cases = _registered_ir_tag_cases()
    case_number = 0
    for tag, (_value, spec, tag_payload) in cases.items():
        malformed_tags: list[tuple[str, dict[str, object]]] = []
        for field_name, field_value in tag_payload.items():
            if field_name == "_type":
                continue
            if not isinstance(field_value, str):
                raise AssertionError(
                    f"Add a source-aware mutation for {tag}.{field_name}: {field_value!r}"
                )
            malformed = json.loads(json.dumps(tag_payload))
            malformed[field_name] = field_value + "~noncanonical"
            malformed_tags.append((field_name, malformed))
        if not malformed_tags:
            raise AssertionError(f"Registered IR tag {tag!r} has no exercised payload fields")

        unknown_member = json.loads(json.dumps(tag_payload))
        unknown_member["unmodeled_member"] = "retained-by-encoder-only"
        malformed_tags.append(("unmodeled-member", unknown_member))

        for mutation, malformed_tag in malformed_tags:
            for nested in (False, True):
                payload = {"nested": malformed_tag} if nested else malformed_tag
                store = FileSystemCAS(tmp_path / f"malformed-ir-tag-{case_number}")
                options = StorePutOptions(
                    kind=f"test.ir-malformed-tag-{tag}-{mutation}-{nested}",
                    media_type="application/json",
                    canon=IRCanonInfo.from_spec(spec),
                )

                with pytest.raises(
                    IRCanonViolation,
                    match="canon_profile_payload_nonconformant",
                ):
                    ensure_ir_artifact_store(store).put_json(
                        payload,
                        options,
                        canon_spec=spec,
                    )

                assert store.iter_artifact_ids() == []
                case_number += 1


def test_ir_adapter_refuses_float_tag_mapping_when_profile_forbids_floats(tmp_path) -> None:
    """A recognized float mapping cannot bypass the selected forbid-floats rule."""
    float_tag = _registered_ir_tag_cases()["float"][2]
    for nested in (False, True):
        root = tmp_path / f"forbidden-float-tag-{nested}"
        store = FileSystemCAS(root)
        payload = {"nested": float_tag} if nested else float_tag
        spec = IRCanonSpec()
        options = StorePutOptions(
            kind=f"test.ir-forbidden-float-tag-{nested}",
            media_type="application/json",
            canon=IRCanonInfo.from_spec(spec),
        )

        with pytest.raises(IRCanonViolation, match="canon_profile_payload_nonconformant"):
            ensure_ir_artifact_store(store).put_json(payload, options, canon_spec=spec)

        assert store.iter_artifact_ids() == []


@pytest.mark.parametrize(
    "invalid_options",
    [
        {"kind": "test.invalid-mapping", "media_type": "application/json", "warnings": "bad"},
        {
            "kind": "test.invalid-mapping",
            "media_type": "application/json",
            "warnings": [object()],
        },
        {
            "kind": "test.invalid-mapping",
            "media_type": "application/json",
            "unexpected": "silently discarded today",
        },
        {"kind": 1, "media_type": "application/json"},
        {
            "kind": "test.invalid-mapping",
            "media_type": "application/json",
            "canon": {"max_depth": 128},
        },
        {
            "kind": "test.invalid-mapping",
            "media_type": "application/json",
            "schema": {"name": "missing-required-version"},
        },
        {
            "kind": "test.invalid-mapping",
            "media_type": "application/json",
            "inputs": [
                {
                    "artifact_id": "sha256:" + "a" * 64,
                    "role": "source",
                    "unexpected": "preserve strict metadata validation",
                }
            ],
        },
    ],
)
def test_ir_adapter_refuses_malformed_supplied_mapping_options(tmp_path, invalid_options) -> None:
    """Supplied malformed option values cannot disappear into adapter defaults."""
    store = FileSystemCAS(tmp_path / ".polisyos")

    with pytest.raises((TypeError, ValueError)):
        ensure_ir_artifact_store(store).put_json({"value": 1}, invalid_options)

    assert store.iter_artifact_ids() == []


@pytest.mark.parametrize(
    "nested_edge",
    [
        "producer.component",
        "producer.git",
        "inputs.artifact_id",
        "governance.retention",
        "governance.encryption",
    ],
)
@pytest.mark.parametrize("construction", ["model_construct", "mutated_nested_model"])
@pytest.mark.parametrize("carrier", ["mapping", "ir_typed", "core_typed"])
def test_ir_adapter_refuses_invalid_nested_model_options_before_persisting(
    tmp_path, nested_edge, construction, carrier
) -> None:
    """Every declared nested metadata-model edge is revalidated before CAS publication."""
    if nested_edge == "producer.component":
        if construction == "model_construct":
            component = ComponentId.model_construct(root="invalid-component")
        else:
            component = ComponentId("polisyos.tests@1.0.0")
            object.__setattr__(component, "root", "invalid-component")
        option_name = "producer"
        option_value = ProducerInfo(
            component=component,
            version="1.0.0",
            git=None,
        )
    elif nested_edge == "producer.git":
        if construction == "model_construct":
            git = GitInfo.model_construct(commit=None, dirty=False)
        else:
            git = GitInfo(commit="a" * 40, dirty=False)
            object.__setattr__(git, "commit", None)
        option_name = "producer"
        option_value = ProducerInfo(
            component="polisyos.tests@1.0.0",
            version="1.0.0",
            git=git,
        )
    elif nested_edge == "inputs.artifact_id":
        if construction == "model_construct":
            artifact_id = CoreArtifactID.model_construct(root="invalid-artifact-id")
        else:
            artifact_id = CoreArtifactID("sha256:" + "a" * 64)
            object.__setattr__(artifact_id, "root", "invalid-artifact-id")
        option_name = "inputs"
        option_value = [CoreInputRef(artifact_id=artifact_id, role="source")]
    elif nested_edge == "governance.retention":
        if construction == "model_construct":
            retention = ArtifactRetentionPolicyInfo.model_construct(
                scope="candidate", retention_days=-1
            )
        else:
            retention = ArtifactRetentionPolicyInfo(scope="candidate", retention_days=1)
            object.__setattr__(retention, "retention_days", -1)
        option_name = "governance"
        option_value = ArtifactGovernanceInfo(retention=retention)
    else:
        if construction == "model_construct":
            encryption = ArtifactEncryptionPolicyInfo.model_construct(
                mode="none", enforced="not-a-boolean", verified=False
            )
        else:
            encryption = ArtifactEncryptionPolicyInfo(mode="none", enforced=True, verified=False)
            object.__setattr__(encryption, "enforced", "not-a-boolean")
        option_name = "governance"
        option_value = ArtifactGovernanceInfo(encryption=encryption)

    values = {
        "kind": f"test.invalid-nested-model-{nested_edge}-{construction}-{carrier}",
        "media_type": "application/json",
        option_name: option_value,
    }
    if carrier == "mapping":
        options = MappingProxyType(values)
    elif carrier == "ir_typed":
        options = StorePutOptions(**values)
    else:
        options = ArtifactWriteOptions(**values)

    store = FileSystemCAS(tmp_path / f"{nested_edge}-{construction}-{carrier}")
    with pytest.raises(TypeError, match=f"Invalid adapter option '{option_name}'"):
        ensure_ir_artifact_store(store).put_json({"value": "must-not-be-persisted"}, options)

    assert store.iter_artifact_ids() == []


def test_ir_adapter_refuses_canon_spec_mismatch_before_persisting(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    options = StorePutOptions(
        kind="test.ir-canon-spec-mismatch",
        media_type="application/json",
        canon=IRCanonInfo(exclude_none=True).model_dump(mode="python"),
    )

    with pytest.raises(IRCanonViolation, match="canon metadata must match"):
        ensure_ir_artifact_store(store).put_json(
            {"present": None},
            options,
            canon_spec=IRCanonSpec(exclude_none=False),
        )

    assert store.iter_artifact_ids() == []


def test_ir_adapter_accepts_typed_ir_canon_info_option(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    spec = IRCanonSpec(exclude_none=False)
    options = StorePutOptions(
        kind="test.ir-canon-typed-option",
        media_type="application/json",
        canon=IRCanonInfo.from_spec(spec),
    )

    ref = ensure_ir_artifact_store(store).put_json({"present": None}, options, canon_spec=spec)

    assert store.get_bytes(ref) == b'{"present":null}'
    assert store.get_manifest(ref).canon.exclude_none is False


def test_file_system_put_json_refuses_canon_spec_mismatch_before_persisting(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    options = ArtifactWriteOptions(
        kind="test.core-canon-spec-mismatch",
        media_type="application/json",
        canon=CoreCanonInfo(exclude_none=True),
    )

    with pytest.raises(CoreCanonViolation, match="canon metadata must match"):
        store.put_json(
            {"present": None},
            options,
            canon_spec=CoreCanonSpec(exclude_none=False),
        )

    assert store.iter_artifact_ids() == []


def test_ir_adapter_persists_decimal_bytes_that_the_ir_reader_accepts(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    payload = {"amount": Decimal("12.30")}

    ref = put_json_artifact(
        _ensure_ir_artifact_store(ir_store),
        payload,
        kind="test.ir-canon-profile",
        schema_name="test.ir-canon-profile",
        schema_version="1.0",
    )

    assert core_store.get_bytes(ref["artifact_id"]) == (
        b'{"amount":{"_type":"decimal","value":"12.30"}}'
    )
    assert get_json_artifact(_ensure_ir_artifact_store(ir_store), ref["artifact_id"]) == payload


@pytest.mark.parametrize("payload", _IR_INCOMPATIBLE_TAG_PAYLOADS)
def test_ir_adapter_rejects_incompatible_tags_before_persisting(tmp_path, payload) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        put_json_artifact(
            _ensure_ir_artifact_store(ir_store),
            payload,
            kind="test.ir-canon-profile",
            schema_name="test.ir-canon-profile",
            schema_version="1.0",
        )

    assert core_store.iter_artifact_ids() == []


class _RawManifestReader:
    """Expose raw manifest JSON and count reader-side effects in IR boundary tests."""

    def __init__(self, store, manifest: bytes | Mapping[str, object]) -> None:
        self.store = store
        self.raw_manifest = (
            manifest
            if isinstance(manifest, bytes)
            else json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
        )
        self.manifest_reads = 0
        self.byte_reads = 0

    def get_manifest_bytes(self, artifact_id):
        self.manifest_reads += 1
        return self.raw_manifest

    def get_bytes(self, artifact_id):
        self.byte_reads += 1
        return ensure_ir_artifact_store(self.store).get_bytes(artifact_id)


def _observe_selected_core_reads(
    core_store: FileSystemCAS, monkeypatch: pytest.MonkeyPatch
) -> tuple[CoreToIRArtifactStoreAdapter, dict[str, list[object]]]:
    """Return the real typed Core-to-IR adapter and record its exact selectors."""
    observed: dict[str, list[object]] = {
        "get_raw_manifest_bytes": [],
        "get_manifest": [],
        "get_bytes": [],
    }
    for method_name in observed:
        reader = getattr(core_store, method_name)

        def record(selector, *, name=method_name, read=reader, **kwargs):
            observed[name].append(selector)
            return read(selector, **kwargs)

        monkeypatch.setattr(core_store, method_name, record)
    ir_store = ensure_ir_artifact_store(core_store)
    assert isinstance(ir_store, CoreToIRArtifactStoreAdapter)
    return ir_store, observed


def _assert_exact_selected_core_read_selectors(
    observed: dict[str, list[object]], selected_ref: CoreArtifactRef
) -> None:
    """Require every observed read family to retain the complete selected ref."""
    expected = normalize_artifact_ref(selected_ref)
    assert expected["manifest_profile_sha256"] == selected_ref.manifest_profile_sha256
    for method_name in ("get_raw_manifest_bytes", "get_manifest", "get_bytes"):
        selectors = observed[method_name]
        assert selectors, f"No selected-view {method_name} calls were observed"
        for selector in selectors:
            assert normalize_artifact_ref(selector) == expected, method_name


def test_ir_reader_accepts_raw_canonical_manifest_bytes_without_byte_mutation(tmp_path) -> None:
    """The existing G producer and a raw-byte reader agree on exact Decimal bytes."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    payload = {"amount": Decimal("12.30")}
    ref = CoreArtifactRef.model_validate(
        put_json_artifact(
            _ensure_ir_artifact_store(ir_store),
            payload,
            kind="test.ir-reader-mapping",
            schema_name="test.ir-reader-mapping",
            schema_version="1.0",
        )
    )
    persisted_bytes = core_store.get_bytes(ref.artifact_id)
    read_store = FileSystemCAS(tmp_path / ".polisyos")
    manifest = read_store.get_manifest_bytes(ref)
    reader = _RawManifestReader(read_store, manifest)

    assert get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id) == payload
    assert reader.manifest_reads == reader.byte_reads == 1
    assert read_store.get_manifest_bytes(ref) == manifest
    assert persisted_bytes == b'{"amount":{"_type":"decimal","value":"12.30"}}'
    assert core_store.get_bytes(ref.artifact_id) == persisted_bytes


def test_ir_raw_only_reader_refuses_unresolvable_profiled_selector_before_payload(tmp_path) -> None:
    """ID-only raw reads remain supported; a full selected view cannot be downgraded."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = _ensure_ir_artifact_store(core_store)
    ref_payload = put_json_artifact(
        ir_store,
        {"amount": Decimal("12.30")},
        kind="test.ir-reader-selected-ref",
        schema_name="test.ir-reader-selected-ref",
        schema_version="1.0",
        return_selected_profile=True,
    )
    ref = CoreArtifactRef.model_validate(ref_payload)
    manifest = core_store.get_manifest_bytes(ref)
    reader = _RawManifestReader(core_store, manifest)

    with pytest.raises(IRCanonViolation, match="ir_artifact_selected_manifest_unavailable"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref)
    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0


def test_ir_reader_uses_nondefault_persisted_depth_through_existing_g_producer(tmp_path) -> None:
    """A depth-129 Mapping is read using the persisted supported profile."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    payload = 0
    for _ in range(129):
        payload = [payload]
    ref = put_json_artifact(
        _ensure_ir_artifact_store(ir_store),
        payload,
        kind="test.ir-reader-depth",
        schema_name="test.ir-reader-depth",
        schema_version="1.0",
        canon_spec=IRCanonSpec(max_depth=129),
    )
    read_store = FileSystemCAS(tmp_path / ".polisyos")
    manifest = read_store.get_manifest_bytes(ref["artifact_id"])
    reader = _RawManifestReader(read_store, manifest)

    assert get_json_artifact(_ensure_ir_artifact_store(reader), ref["artifact_id"]) == payload
    assert reader.manifest_reads == reader.byte_reads == 1
    assert read_store.get_manifest_bytes(ref["artifact_id"]) == manifest


@pytest.mark.parametrize(
    "profile_updates",
    [
        {"name": "polisyos.canon.future"},
        {"version": "0.4.0"},
        {"forbid_floats": "false"},
        {"max_depth": "129"},
        {"max_depth": True},
        {"max_depth": -1},
        {"separators": [","]},
        {"separators": [",", 1]},
        {"unexpected": "field"},
        None,
    ],
)
def test_ir_reader_refuses_fake_mapping_profiles_before_payload_bytes(
    tmp_path, profile_updates
) -> None:
    """Changing only a real manifest's profile cannot silently authorize a read."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    ref = put_json_artifact(
        _ensure_ir_artifact_store(ir_store),
        {"amount": Decimal("12.30")},
        kind="test.ir-reader-negative",
        schema_name="test.ir-reader-negative",
        schema_version="1.0",
    )
    read_store = FileSystemCAS(tmp_path / ".polisyos")
    manifest = read_store.get_manifest(ref["artifact_id"]).model_dump(mode="json")
    if profile_updates is None:
        manifest["canon"] = None
    else:
        manifest["canon"].update(profile_updates)
    reader = _RawManifestReader(read_store, manifest)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref["artifact_id"])
    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0


@pytest.mark.parametrize("missing_field", tuple(IRCanonInfo.model_fields))
def test_ir_reader_requires_every_persisted_profile_field_before_bytes(
    tmp_path, missing_field: str
) -> None:
    """Defaults cannot fill an omitted field in the persisted profile ABI."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    ref = put_json_artifact(
        _ensure_ir_artifact_store(ir_store),
        {"amount": Decimal("12.30")},
        kind="test.ir-reader-complete-profile",
        schema_name="test.ir-reader-complete-profile",
        schema_version="1.0",
    )
    read_store = FileSystemCAS(tmp_path / ".polisyos")
    manifest = read_store.get_manifest(ref["artifact_id"]).model_dump(mode="json")
    manifest["canon"].pop(missing_field)
    reader = _RawManifestReader(read_store, manifest)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref["artifact_id"])
    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0


def test_current_core_native_tags_round_trip_through_fresh_profiled_ir_reader(
    tmp_path, monkeypatch
) -> None:
    """Actual Core native tag emissions resolve as an exact IR selected view."""
    root = tmp_path / ".polisyos"
    payload = {
        "bytes": b"\x00\xff",
        "date": date(2026, 10, 14),
        "datetime": datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
        "decimal": Decimal("12.30"),
        "float": 1.5,
    }
    selected_ref = FileSystemCAS(root).put_json(
        payload,
        ArtifactWriteOptions(kind="test.core-native-tags-to-ir", media_type="application/json"),
        canon_spec=CoreCanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert selected_ref.manifest_profile_sha256 is not None
    fresh = FileSystemCAS(root)
    exact_bytes = fresh.get_bytes(selected_ref)
    assert exact_bytes == (
        b'{"bytes":{"_type":"bytes","data":"AP8=","encoding":"base64"},'
        b'"date":{"_type":"date","iso":"2026-10-14"},'
        b'"datetime":{"_type":"datetime","iso_utc":"2026-10-14T12:00:00Z"},'
        b'"decimal":{"_type":"decimal","value":"12.30"},'
        b'"float":{"_type":"float","repr":"1.5"}}'
    )
    assert selected_ref.artifact_id.hex == sha256(exact_bytes).hexdigest()
    assert fresh.get_manifest(selected_ref).canon == CoreCanonInfo(forbid_floats=False)
    ir_store, observed = _observe_selected_core_reads(fresh, monkeypatch)

    loaded = get_json_artifact(ir_store, selected_ref)

    assert loaded == payload
    assert isinstance(loaded["bytes"], bytes)
    assert type(loaded["date"]) is date
    assert isinstance(loaded["datetime"], datetime)
    assert isinstance(loaded["decimal"], Decimal)
    assert isinstance(loaded["float"], float)
    assert fresh.get_bytes(selected_ref) == exact_bytes
    _assert_exact_selected_core_read_selectors(observed, selected_ref)


def test_default_ir_artifact_reopens_as_typed_backtest_report(tmp_path) -> None:
    """The actual typed consumer reads a default artifact after a fresh CAS reopen."""
    root = tmp_path / ".polisyos"
    report = BacktestReport(report_id="bt.g-compatible.fresh")
    ref = persist_backtest_report(ensure_ir_artifact_store(FileSystemCAS(root)), report)
    fresh = FileSystemCAS(root)
    exact_bytes = fresh.get_bytes(str(ref.artifact_id))
    fresh_ir_store = _ensure_ir_artifact_store(fresh)
    assert ref.manifest_profile_sha256 is not None
    selected_manifest = fresh_ir_store.get_manifest(ref)
    assert selected_manifest.canon == CoreCanonInfo.from_spec(CoreCanonSpec(forbid_floats=False))

    loaded = load_backtest_report(fresh_ir_store, ref)

    assert isinstance(loaded, BacktestReport)
    assert loaded.report_id == report.report_id
    assert loaded.n_scenarios == 0
    assert fresh.get_bytes(str(ref.artifact_id)) == exact_bytes


def test_nondefault_current_core_options_keep_shared_ir_values(tmp_path) -> None:
    """Reader parsing accepts stored formatting options without re-encoding the artifact."""
    root = tmp_path / ".polisyos"
    spec = CoreCanonSpec(
        forbid_floats=False,
        exclude_none=False,
        sort_keys=False,
        separators=(", ", ": "),
        ensure_ascii=True,
    )
    payload = {"label": "\u0434", "value": 1.5, "empty": None}
    ref = FileSystemCAS(root).put_json(
        payload,
        ArtifactWriteOptions(kind="test.core-options-to-ir", media_type="application/json"),
        canon_spec=spec,
    )
    fresh = FileSystemCAS(root)
    exact_bytes = fresh.get_bytes(ref)
    assert exact_bytes == (
        b'{"label": "\\u0434", "value": {"_type": "float", "repr": "1.5"}, "empty": null}'
    )
    manifest = fresh.get_manifest(ref).model_dump(mode="json")
    assert manifest["canon"]["separators"] == [", ", ": "]
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))

    loaded = get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id)

    assert loaded == payload
    assert isinstance(loaded["value"], float)
    assert reader.manifest_reads == reader.byte_reads == 1
    assert fresh.get_bytes(ref) == exact_bytes


def test_profileless_historical_cas_artifact_is_refused_before_bytes(tmp_path) -> None:
    """A real profile-less CAS manifest remains an explicitly unsupported history case."""
    root = tmp_path / ".polisyos"
    exact_bytes = b'{"amount":{"_type":"decimal","value":"12.30"}}'
    ref = FileSystemCAS(root).put_bytes(
        exact_bytes,
        ArtifactWriteOptions(kind="test.profileless-history", media_type="application/json"),
    )
    fresh = FileSystemCAS(root)
    manifest = fresh.get_manifest(ref).model_dump(mode="json")
    assert manifest["canon"] is None
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id)

    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0
    assert fresh.get_bytes(ref) == exact_bytes


@pytest.mark.parametrize("missing_field", tuple(IRCanonInfo.model_fields))
def test_real_raw_manifest_profile_omission_is_not_filled_from_core_defaults(
    tmp_path, missing_field: str
) -> None:
    """The IR reader sees raw persisted omissions before Core model defaults can fill them."""
    root = tmp_path / ".polisyos"
    producer = ensure_ir_artifact_store(FileSystemCAS(root))
    ref = put_json_artifact(
        _ensure_ir_artifact_store(producer),
        {"amount": Decimal("12.30")},
        kind="test.ir-raw-profile-omission",
        schema_name="test.ir-raw-profile-omission",
        schema_version="1.0",
    )
    artifact_id = CoreArtifactRef.model_validate(ref).artifact_id
    owner = FileSystemCAS(root)
    sidecar = owner._manifest_path_for_ref(artifact_id, None)
    manifest = json.loads(sidecar.read_bytes())
    manifest["canon"].pop(missing_field)
    sidecar.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")

    fresh = FileSystemCAS(root)
    # Core's typed view demonstrates why the IR reader must consume the raw bytes:
    # Pydantic supplies the omitted field's default here.
    assert missing_field in fresh.get_manifest(artifact_id).canon.model_dump()
    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(ensure_ir_artifact_store(fresh), artifact_id)


def test_ir_reader_rejects_raw_numeric_float_under_forbid_floats_profile(tmp_path) -> None:
    """A shaped manifest cannot make noncanonical raw numeric floats conform."""
    root = tmp_path / ".polisyos"
    exact_bytes = b'{"amount":1.5}'
    ref = FileSystemCAS(root).put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.ir-raw-numeric-float",
            media_type="application/json",
            canon=CoreCanonInfo(forbid_floats=True),
        ),
    )

    with pytest.raises(IRCanonViolation, match="do_not_conform"):
        get_json_artifact(ensure_ir_artifact_store(FileSystemCAS(root)), ref)


def test_ir_reader_rejects_noncanonical_raw_json_bytes(tmp_path) -> None:
    """JSON parseability alone does not establish the persisted canonical byte profile."""
    root = tmp_path / ".polisyos"
    exact_bytes = b'{"value": 1}'
    ref = FileSystemCAS(root).put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.ir-noncanonical-raw-json",
            media_type="application/json",
            canon=CoreCanonInfo(),
        ),
    )

    with pytest.raises(IRCanonViolation, match="do_not_conform"):
        get_json_artifact(ensure_ir_artifact_store(FileSystemCAS(root)), ref)


def test_ir_reader_refuses_malformed_raw_profile_before_payload_bytes(
    tmp_path, monkeypatch
) -> None:
    """A malformed profile cannot fall through Core validation into IR defaults."""
    root = tmp_path / ".polisyos"
    producer = FileSystemCAS(root)
    ref = producer.put_json(
        {"value": 1},
        ArtifactWriteOptions(
            kind="test.ir-malformed-raw-profile",
            media_type="application/json",
            canon=CoreCanonInfo(),
        ),
    )
    sidecar = producer._manifest_path_for_ref(ref.artifact_id, None)
    manifest = json.loads(sidecar.read_bytes())
    manifest["canon"]["max_depth"] = "not-an-integer"
    sidecar.write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    reader = FileSystemCAS(root)

    def reject_payload_read(*_args, **_kwargs):
        pytest.fail("payload bytes were read before the malformed profile was refused")

    monkeypatch.setattr(reader, "get_bytes", reject_payload_read)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(ensure_ir_artifact_store(reader), ref.artifact_id)


def test_ir_reader_preserves_selected_manifest_view_through_manifest_and_blob_reads(
    tmp_path, monkeypatch
) -> None:
    """A selected profile is not silently reduced to its primary ArtifactID view."""
    root = tmp_path / ".polisyos"
    exact_bytes = b'{"nested":{"value":1}}'
    store = FileSystemCAS(root)
    default_ref = store.put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.ir-selected-view",
            media_type="application/json",
            canon=CoreCanonInfo(max_depth=0),
        ),
    )
    selected_ref = store.put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.ir-selected-view",
            media_type="application/json",
            canon=CoreCanonInfo(max_depth=8),
        ),
    )
    assert selected_ref.artifact_id == default_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    normalized_ref = normalize_artifact_ref(selected_ref)
    assert normalized_ref["manifest_profile_sha256"] == selected_ref.manifest_profile_sha256

    core_store = FileSystemCAS(root)
    ir_store = ensure_ir_artifact_store(core_store)
    selectors: list[tuple[str, object]] = []
    get_raw_manifest_bytes = core_store.get_raw_manifest_bytes
    get_bytes = core_store.get_bytes

    def record_manifest_selector(selector, *, manifest_profile_sha256=None):
        selectors.append(("raw-manifest", selector))
        return get_raw_manifest_bytes(selector, manifest_profile_sha256=manifest_profile_sha256)

    def record_blob_selector(selector):
        selectors.append(("blob", selector))
        return get_bytes(selector)

    monkeypatch.setattr(core_store, "get_raw_manifest_bytes", record_manifest_selector)
    monkeypatch.setattr(core_store, "get_bytes", record_blob_selector)

    loaded = get_json_artifact(_ensure_ir_artifact_store(ir_store), selected_ref)
    loaded_from_normalized_ref = get_json_artifact(
        _ensure_ir_artifact_store(ir_store), normalized_ref
    )

    assert loaded == {"nested": {"value": 1}}
    assert loaded_from_normalized_ref == loaded
    assert selectors == [
        ("raw-manifest", selected_ref),
        ("blob", selected_ref),
        ("raw-manifest", selected_ref),
        ("blob", selected_ref),
    ]


def test_ir_reader_gets_raw_profile_from_cache_durable_owner(tmp_path, monkeypatch) -> None:
    """A cache forwards raw sidecars from the durable owner instead of rebuilding them."""
    remote = FileSystemCAS(tmp_path / "remote")
    local = FileSystemCAS(tmp_path / "local")
    cache = CachingArtifactStore(remote=remote, local=local, write_through=True)
    ir_store = ensure_ir_artifact_store(cache)
    payload = {"amount": Decimal("8.10")}
    ref = put_json_artifact(
        _ensure_ir_artifact_store(ir_store),
        payload,
        kind="test.ir-cache-raw-profile",
        schema_name="test.ir-cache-raw-profile",
        schema_version="1.0",
    )
    remote_raw_manifest = remote.get_raw_manifest_bytes(ref["artifact_id"])

    def reject_local_raw_manifest(*_args, **_kwargs):
        pytest.fail("raw profile read bypassed the durable owner")

    monkeypatch.setattr(local, "get_raw_manifest_bytes", reject_local_raw_manifest)

    assert get_json_artifact(_ensure_ir_artifact_store(ir_store), ref) == payload
    assert remote.get_raw_manifest_bytes(ref["artifact_id"]) == remote_raw_manifest


@pytest.mark.parametrize(
    ("exact_bytes", "decoded_core_value"),
    [
        (b'{"_type":"float_hex","value":"0x1.8p+1"}', 3.0),
        (b'{"_type":"bytes_hex","value":"00ff"}', b"\x00\xff"),
    ],
    ids=["float-hex-alias", "bytes-hex-alias"],
)
def test_core_decoder_aliases_outside_ir_are_refused_for_fresh_profiled_view(
    tmp_path, exact_bytes, decoded_core_value, monkeypatch
) -> None:
    """Core's alternate float/bytes spellings do not widen IR's selected-view tag law."""
    root = tmp_path / ".polisyos"
    selected_ref = FileSystemCAS(root).put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.core-decoder-aliases-outside-ir",
            media_type="application/json",
            canon=CoreCanonInfo(),
        ),
        return_selected_profile=True,
    )
    assert selected_ref.manifest_profile_sha256 is not None
    fresh = FileSystemCAS(root)
    assert fresh.get_bytes(selected_ref) == exact_bytes
    assert from_core_canonical_bytes(exact_bytes) == decoded_core_value
    selected_manifest = fresh.get_manifest(selected_ref)
    assert selected_manifest.canon is not None
    assert selected_manifest.canon.name == IRCanonInfo().name
    assert selected_manifest.canon.version == IRCanonInfo().version
    ir_store, observed = _observe_selected_core_reads(fresh, monkeypatch)

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        get_json_artifact(ir_store, selected_ref)

    assert fresh.get_bytes(selected_ref) == exact_bytes
    _assert_exact_selected_core_read_selectors(observed, selected_ref)


def test_core_put_json_preserves_array_digest_mapping_but_raw_ir_reader_refuses_it(
    tmp_path,
) -> None:
    """Core preserves a caller-supplied typed mapping; IR keeps its narrower decoder law."""
    root = tmp_path / ".polisyos"
    payload = {"_type": "array_digest", "digest": "sha256:abc", "length": 2}
    ref = FileSystemCAS(root).put_json(
        payload,
        ArtifactWriteOptions(
            kind="test.core-array-digest-mapping",
            media_type="application/json",
        ),
    )
    fresh = FileSystemCAS(root)
    exact_bytes = b'{"_type":"array_digest","digest":"sha256:abc","length":2}'
    assert fresh.get_bytes(ref) == exact_bytes
    assert from_core_canonical_bytes(exact_bytes) == payload
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id)

    assert reader.manifest_reads == reader.byte_reads == 1
    assert fresh.get_bytes(ref) == exact_bytes


@pytest.mark.parametrize(
    "profile",
    [CoreCanonInfo(name="polisyos.canon.future"), CoreCanonInfo(version="0.4.0")],
)
def test_actual_persisted_mismatched_profile_refuses_before_bytes(tmp_path, profile) -> None:
    """Current Core metadata cannot make an unsupported profile readable by declaration."""
    root = tmp_path / ".polisyos"
    ref = FileSystemCAS(root).put_bytes(
        b'{"value":1}',
        ArtifactWriteOptions(
            kind="test.persisted-profile-mismatch", media_type="application/json", canon=profile
        ),
    )
    fresh = FileSystemCAS(root)
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id)

    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0


def test_raw_core_bypass_with_shaped_profile_cannot_authorize_core_only_tag(tmp_path) -> None:
    """A complete shaped IR-looking profile cannot authorize an extended Core-only tag."""
    root = tmp_path / ".polisyos"
    exact_bytes = b'{"_type":"float_hex","value":"0x1.8p+1"}'
    ref = FileSystemCAS(root).put_bytes(
        exact_bytes,
        ArtifactWriteOptions(
            kind="test.raw-core-bypass",
            media_type="application/json",
            canon=CoreCanonInfo(),
        ),
    )
    fresh = FileSystemCAS(root)
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id)

    assert reader.manifest_reads == reader.byte_reads == 1
    assert fresh.get_bytes(ref) == exact_bytes


def test_annotated_artifact_id_roots_cross_ir_adapter_and_refuse_other_root_semantics(
    tmp_path,
) -> None:
    """Admit exact schema-only strings and refuse metadata subclasses with runtime hooks."""
    core_store = FileSystemCAS(tmp_path / "artifact-id-root-bridge")
    ir_store = ensure_ir_artifact_store(core_store)
    payload = {"source": "IR producer, Core CAS, both readers"}
    selected_ref = put_json_artifact(
        ir_store,
        payload,
        kind="test.artifactid-root-bridge",
        schema_name="test.artifactid-root-bridge",
        schema_version="1",
        return_selected_profile=True,
    )
    assert selected_ref["manifest_profile_sha256"]

    core_id = CoreArtifactID.model_validate(selected_ref["artifact_id"])
    ir_id = IRArtifactID.model_validate(selected_ref["artifact_id"])
    assert get_json_artifact(ir_store, core_id) == payload
    assert ir_store.get_bytes(ir_id) == to_ir_canonical_bytes(payload, IRCanonSpec())

    def return_non_text(_value: object) -> int:
        return 7

    class AnnotatedIntegerRoot(RootModel[Annotated[int, WithJsonSchema({"type": "integer"})]]):
        pass

    unsupported_model_dump_calls: list[str] = []

    class RuntimeValidatorStringRoot(RootModel[Annotated[str, PlainValidator(return_non_text)]]):
        def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
            unsupported_model_dump_calls.append(mode)
            return super().model_dump(mode=mode)

    non_string = AnnotatedIntegerRoot(7)
    custom_validator = RuntimeValidatorStringRoot("arbitrary")
    assert custom_validator.root == 7

    with pytest.raises(TypeError, match="Invalid Core artifact selector"):
        ir_store.get_bytes(non_string)
    with pytest.raises(IRCanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(ir_store, non_string)

    with pytest.raises(TypeError, match="Invalid Core artifact selector"):
        ir_store.get_bytes(custom_validator)
    assert unsupported_model_dump_calls == []
    with pytest.raises(IRCanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(ir_store, custom_validator)
    assert unsupported_model_dump_calls == []

    target_wire_id = str(core_id)
    source_wire_id = str(CoreArtifactID.from_sha256_hex(sha256(b"unpersisted source").hexdigest()))
    assert source_wire_id != target_wire_id

    class RewritingWithJsonSchema(WithJsonSchema):
        def __get_pydantic_core_schema__(
            self, source_type: Any, handler: GetCoreSchemaHandler
        ) -> CoreSchema:
            return core_schema.no_info_after_validator_function(
                lambda _value: target_wire_id,
                handler(source_type),
            )

    validation_metadata = {
        "type": "string",
        "pattern": "^[0-9A-Fa-f]{64}$",
        "minLength": 64,
        "maxLength": 64,
    }
    serialization_metadata = {
        "type": "string",
        "pattern": "^[0-9a-f]{64}$",
        "minLength": 64,
        "maxLength": 64,
    }

    class RewrittenCoreArtifactID(
        RootModel[
            Annotated[
                str,
                RewritingWithJsonSchema(validation_metadata, mode="validation"),
                RewritingWithJsonSchema(serialization_metadata, mode="serialization"),
            ]
        ]
    ):
        pass

    class RewrittenIRArtifactID(
        RootModel[
            Annotated[
                str,
                RewritingWithJsonSchema(validation_metadata, mode="validation"),
                RewritingWithJsonSchema(serialization_metadata, mode="serialization"),
            ]
        ]
    ):
        pass

    rewritten_core_id = RewrittenCoreArtifactID(source_wire_id)
    rewritten_ir_id = RewrittenIRArtifactID(source_wire_id)
    assert rewritten_core_id.root == rewritten_ir_id.root == target_wire_id
    assert rewritten_core_id.root != source_wire_id
    assert (
        RewrittenCoreArtifactID.model_json_schema(mode="validation")["pattern"]
        == validation_metadata["pattern"]
    )
    assert (
        RewrittenCoreArtifactID.model_json_schema(mode="serialization")["pattern"]
        == serialization_metadata["pattern"]
    )
    assert core_ir_adapter._is_string_root_model(rewritten_core_id) is False
    assert ir_artifact_contracts._is_string_root_model(rewritten_ir_id) is False

    with pytest.raises(TypeError, match="Invalid Core artifact selector"):
        ir_store.get_bytes(rewritten_core_id)
    with pytest.raises(IRCanonViolation, match="ir_artifact_view_selector_invalid"):
        get_json_artifact(ir_store, rewritten_ir_id)


@pytest.mark.parametrize("selector_shape", ["ordinary", "model_dump"])
def test_adapter_rejects_classvar_rogue_before_bytes(tmp_path: Path, selector_shape: str) -> None:
    """Forged ClassVar annotations cannot hide actual selector instance values."""
    payload = b"selector target"
    target = FileSystemCAS(tmp_path / f"classvar-reject-{selector_shape}")
    ref = target.put_bytes(
        payload,
        ArtifactWriteOptions(kind="test.classvar-selector", media_type="application/octet-stream"),
    )

    class SelectorBase:
        __annotations__ = {"rogue": "ClassVar[str]"}

        def __init__(self, *, rogue: bool) -> None:
            self.artifact_id = ref.artifact_id
            self.kind = ref.kind
            self.media_type = ref.media_type
            self.manifest_profile_sha256 = ref.manifest_profile_sha256
            if rogue:
                self.rogue = "unexpected"

    class ModelDumpSelector(SelectorBase):
        def model_dump(self, *, mode: str) -> dict[str, object]:
            del self.rogue
            return {
                "artifact_id": self.artifact_id,
                "kind": self.kind,
                "media_type": self.media_type,
                "manifest_profile_sha256": self.manifest_profile_sha256,
            }

    class CountingCoreStore:
        def __init__(self) -> None:
            self.payload_reads = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def get_bytes(self, selector: object) -> bytes:
            self.payload_reads += 1
            return target.get_bytes(selector)

    reader = CountingCoreStore()
    adapter = CoreToIRArtifactStoreAdapter(reader)
    selector_type = ModelDumpSelector if selector_shape == "model_dump" else SelectorBase

    selector = selector_type(rogue=True)
    with pytest.raises(TypeError, match="Invalid Core artifact selector"):
        adapter.get_bytes(selector)

    assert reader.payload_reads == 0
    if selector_shape == "model_dump":
        assert selector.rogue == "unexpected"


@pytest.mark.parametrize("selector_shape", ["ordinary", "model_dump"])
def test_adapter_accepts_classvar_only_selector(tmp_path: Path, selector_shape: str) -> None:
    """A genuine ClassVar-only declaration is excluded from selector fields."""
    payload = b"selector target"
    target = FileSystemCAS(tmp_path / f"classvar-accept-{selector_shape}")
    ref = target.put_bytes(
        payload,
        ArtifactWriteOptions(kind="test.classvar-selector", media_type="application/octet-stream"),
    )

    class SelectorBase:
        __annotations__ = {"rogue": "ClassVar[str]"}

        def __init__(self) -> None:
            self.artifact_id = ref.artifact_id
            self.kind = ref.kind
            self.media_type = ref.media_type
            self.manifest_profile_sha256 = ref.manifest_profile_sha256

    class ModelDumpSelector(SelectorBase):
        def model_dump(self, *, mode: str) -> dict[str, object]:
            return {
                "artifact_id": self.artifact_id,
                "kind": self.kind,
                "media_type": self.media_type,
                "manifest_profile_sha256": self.manifest_profile_sha256,
            }

    class CountingCoreStore:
        def __init__(self) -> None:
            self.payload_reads = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def get_bytes(self, selector: object) -> bytes:
            self.payload_reads += 1
            return target.get_bytes(selector)

    reader = CountingCoreStore()
    adapter = CoreToIRArtifactStoreAdapter(reader)
    selector_type = ModelDumpSelector if selector_shape == "model_dump" else SelectorBase

    assert adapter.get_bytes(selector_type()) == payload
    assert reader.payload_reads == 1


def test_adapter_accepts_foreign_ir_artifact_id_with_computed_hex_property(
    tmp_path: Path,
) -> None:
    """A typed scalar root keeps its utility properties outside the selector payload."""
    payload = b"typed scalar root"
    target = FileSystemCAS(tmp_path / "foreign-ir-artifact-id")
    stored = target.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="test.foreign-ir-artifact-id", media_type="application/octet-stream"
        ),
    )
    selector = IRArtifactID(str(stored.artifact_id))

    assert selector.hex == stored.artifact_id.hex
    assert CoreToIRArtifactStoreAdapter(target).get_bytes(selector) == payload


def test_adapter_rejects_unknown_stored_foreign_root_before_model_dump(
    tmp_path: Path,
) -> None:
    """An unknown scalar-root value cannot be erased by a caller projection."""
    payload = b"typed scalar root"
    target = FileSystemCAS(tmp_path / "foreign-ir-artifact-id-rogue")
    stored = target.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="test.foreign-ir-artifact-id", media_type="application/octet-stream"
        ),
    )
    projection_calls: list[str] = []

    class MutatingIRArtifactID(IRArtifactID):
        def model_dump(self, *, mode: str = "python") -> str:
            projection_calls.append(mode)
            object.__getattribute__(self, "__dict__").pop("rogue", None)
            return self.root

    selector = MutatingIRArtifactID(str(stored.artifact_id))
    object.__setattr__(selector, "rogue", "unexpected")

    class CountingReader:
        def __init__(self) -> None:
            self.payload_reads = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def get_bytes(self, value: object) -> bytes:
            self.payload_reads += 1
            return target.get_bytes(value)

    reader = CountingReader()
    adapter = CoreToIRArtifactStoreAdapter(reader)
    with pytest.raises(TypeError, match="Invalid Core artifact selector"):
        adapter.get_bytes(selector)

    assert reader.payload_reads == 0
    assert projection_calls == []
    assert object.__getattribute__(selector, "__dict__")["rogue"] == "unexpected"


@pytest.mark.parametrize("stored_root_is_valid", [True, False])
def test_adapter_rejects_scalar_root_projection_substitution_before_bytes(
    tmp_path: Path, stored_root_is_valid: bool
) -> None:
    payload = b"scalar root projection"
    target = FileSystemCAS(tmp_path / "scalar-root-projection")
    stored = target.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind="test.scalar-root-projection", media_type="application/octet-stream"
        ),
    )
    alternate_hex = "0" * 64 if stored.artifact_id.hex != "0" * 64 else "1" * 64
    alternate_id = "sha256:" + alternate_hex
    projection_calls: list[str] = []

    class SubstitutingIRArtifactID(IRArtifactID):
        def model_dump(self, *, mode: str = "python") -> str:
            projection_calls.append(mode)
            return alternate_id

    selector = SubstitutingIRArtifactID(str(stored.artifact_id))
    stored_root = str(stored.artifact_id) if stored_root_is_valid else "not-an-artifact-id"
    if not stored_root_is_valid:
        object.__setattr__(selector, "root", stored_root)

    class CountingReader:
        def __init__(self) -> None:
            self.payload_reads = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def get_bytes(self, value: object) -> bytes:
            self.payload_reads += 1
            return target.get_bytes(value)

    reader = CountingReader()
    adapter = CoreToIRArtifactStoreAdapter(reader)
    with pytest.raises(TypeError, match="Invalid Core artifact selector"):
        adapter.get_bytes(selector)

    assert reader.payload_reads == 0
    assert projection_calls == (["python"] if stored_root_is_valid else [])
    assert object.__getattribute__(selector, "__dict__")["root"] == stored_root


def test_adapter_rejects_fake_scalar_root_markers_with_rogue_property_before_bytes(
    tmp_path: Path,
) -> None:
    payload = b"fake scalar root"
    target = FileSystemCAS(tmp_path / "fake-scalar-root")
    stored = target.put_bytes(
        payload,
        ArtifactWriteOptions(kind="test.fake-scalar-root", media_type="application/octet-stream"),
    )
    projection_calls: list[str] = []

    class FakeRootField:
        annotation = str

    class FakeRootSelector:
        __pydantic_root_model__ = True
        model_fields: ClassVar[dict[str, object]] = {"root": FakeRootField()}

        @property
        def root(self) -> str:
            return str(stored.artifact_id)

        @property
        def rogue(self) -> str:
            return "unexpected"

        def model_dump(self, *, mode: str = "python") -> str:
            projection_calls.append(mode)
            return str(stored.artifact_id)

    class CountingReader:
        def __init__(self) -> None:
            self.payload_reads = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def get_bytes(self, value: object) -> bytes:
            self.payload_reads += 1
            return target.get_bytes(value)

    reader = CountingReader()
    with pytest.raises(TypeError, match="Invalid Core artifact selector"):
        CoreToIRArtifactStoreAdapter(reader).get_bytes(FakeRootSelector())

    assert reader.payload_reads == 0
    assert projection_calls == []


def test_selected_write_reconciles_manifest_against_frozen_core_options(
    tmp_path: Path,
) -> None:
    target = FileSystemCAS(tmp_path / "selected-options-reconciliation")

    class MutatingStore:
        put_calls = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def put_bytes(
            self,
            data: bytes,
            opts: ArtifactWriteOptions,
            *,
            return_selected_profile: bool = False,
        ) -> CoreArtifactRef:
            self.put_calls += 1
            assert return_selected_profile is True
            assert opts.tenant_context is not None
            opts.tenant_context.tenant_id = "tenant-mutated-by-store"
            return target.put_bytes(
                data,
                opts,
                return_selected_profile=return_selected_profile,
            )

    store = MutatingStore()
    options = ArtifactWriteOptions(
        kind="test.selected-options-reconciliation",
        media_type="application/json",
        schema=CoreSchemaInfo(name="test.selected-options-reconciliation", version="1.0"),
        tenant_context=ArtifactTenantContextInfo(
            tenant_id="tenant-frozen-before-emission",
            cell_id="cell-selected-options",
        ),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id="closure-selected-options",
            status="candidate_only",
            run_id="run-selected-options",
            job_id="job-selected-options",
            tenant_id="tenant-frozen-before-emission",
            cell_id="cell-selected-options",
        ),
    )

    with pytest.raises(
        ValueError,
        match="artifact_write_selected_manifest_options_mismatch",
    ):
        CoreToIRArtifactStoreAdapter(store).put_bytes(
            b'{"selected":true}',
            options,
            return_selected_profile=True,
        )

    assert store.put_calls == 1


def test_selected_write_preserves_existing_sequence_and_model_subclass_carriers(
    tmp_path: Path,
) -> None:
    """Core's existing Sequence and raw BaseModel carrier law survives IR admission."""

    class CompatibleInputRef(CoreInputRef):
        pass

    store = FileSystemCAS(tmp_path / "sequence-carrier-compatibility")
    source_id = CoreArtifactID.from_sha256_hex(sha256(b"sequence carrier source").hexdigest())
    options = ArtifactWriteOptions(
        kind="test.sequence-carrier-compatibility",
        media_type="application/json",
        inputs=UserList([CompatibleInputRef(artifact_id=source_id, role="source")]),
        warnings=UserList([WarningRecord(code="retained", msg="sequence carrier")]),
    )

    selected_ref = CoreToIRArtifactStoreAdapter(store).put_bytes(
        b'{"sequence":"retained"}',
        options,
        return_selected_profile=True,
    )

    assert selected_ref.manifest_profile_sha256 is not None
    manifest = FileSystemCAS(tmp_path / "sequence-carrier-compatibility").get_manifest(selected_ref)
    assert manifest.inputs is not None
    assert manifest.inputs[0].artifact_id == source_id
    assert manifest.inputs[0].role == "source"
    assert manifest.warnings is not None
    assert [warning.code for warning in manifest.warnings] == ["retained"]


def test_selected_write_rejects_declared_extra_input_fields_without_model_dump(
    tmp_path: Path,
) -> None:
    """Declared subclass data cannot hide behind a projection or reach CAS."""

    model_dump_calls: list[str] = []

    class LyingInputRef(CoreInputRef):
        private_owner_note: str

        def model_dump(self, *, mode: str = "python", **kwargs: object) -> dict[str, object]:
            model_dump_calls.append(mode)
            return {
                "artifact_id": str(self.artifact_id),
                "role": self.role,
                "manifest_profile_sha256": self.manifest_profile_sha256,
            }

    target = FileSystemCAS(tmp_path / "extra-input-subclass")
    source_id = CoreArtifactID.from_sha256_hex(sha256(b"extra carrier source").hexdigest())

    class CountingStore:
        put_calls = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def put_bytes(
            self,
            data: bytes,
            opts: ArtifactWriteOptions,
            *,
            return_selected_profile: bool = False,
        ) -> CoreArtifactRef:
            self.put_calls += 1
            return target.put_bytes(
                data,
                opts,
                return_selected_profile=return_selected_profile,
            )

    store = CountingStore()
    options = ArtifactWriteOptions(
        kind="test.extra-input-subclass",
        media_type="application/json",
        inputs=UserList(
            [
                LyingInputRef(
                    artifact_id=source_id,
                    role="source",
                    private_owner_note="must not be projected away",
                )
            ]
        ),
    )

    with pytest.raises(TypeError, match="Invalid owned artifact write options"):
        CoreToIRArtifactStoreAdapter(store).put_bytes(
            b'{"sequence":"rejected"}',
            options,
            return_selected_profile=True,
        )

    assert store.put_calls == 0
    assert model_dump_calls == []


def test_selected_write_preserves_core_native_json_values_in_warning_data(
    tmp_path: Path,
) -> None:
    """Selected IR writes retain Core's real manifest serialization for native values."""

    class Signal(Enum):
        READY = "ready"

    payload = b'{"native":"values"}'
    options = ArtifactWriteOptions(
        kind="test.core-native-warning-values",
        media_type="application/json",
        warnings=[
            WarningRecord(
                code="native-values",
                msg="preserve Core JSON values",
                data={
                    "date": date(2026, 10, 24),
                    "datetime": datetime(2026, 10, 24, 12, 30, tzinfo=UTC),
                    "decimal": Decimal("1234.50"),
                    "enum": Signal.READY,
                    "bytes": b"valid utf-8",
                    "uuid": UUID("f2e38d50-80ee-4a1e-98be-153cdf026030"),
                },
            )
        ],
    )

    direct_store = FileSystemCAS(tmp_path / "direct-core-native-values")
    routed_store = FileSystemCAS(tmp_path / "ir-core-native-values")
    direct_ref = direct_store.put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    routed_ref = CoreToIRArtifactStoreAdapter(routed_store).put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )

    direct_manifest = direct_store.get_manifest(direct_ref)
    routed_manifest = routed_store.get_manifest(routed_ref)
    assert direct_ref.manifest_profile_sha256 is not None
    assert routed_ref.manifest_profile_sha256 == direct_ref.manifest_profile_sha256
    assert direct_manifest.warnings is not None
    assert routed_manifest.warnings is not None
    assert routed_manifest.warnings[0].model_dump(mode="json") == (
        direct_manifest.warnings[0].model_dump(mode="json")
    )
    assert routed_manifest.warnings[0].data == {
        "date": "2026-10-24",
        "datetime": "2026-10-24T12:30:00Z",
        "decimal": "1234.50",
        "enum": "ready",
        "bytes": "valid utf-8",
        "uuid": "f2e38d50-80ee-4a1e-98be-153cdf026030",
    }


@pytest.mark.parametrize(
    "typed_options",
    [
        pytest.param(
            {"schema": {"name": date(2026, 10, 24), "version": "1.0"}},
            id="schema-name-date",
        ),
        pytest.param(
            {"tenant_context": {"tenant_id": UUID("f2e38d50-80ee-4a1e-98be-153cdf026030")}},
            id="tenant-id-uuid",
        ),
    ],
)
def test_selected_write_rejects_native_values_in_typed_string_fields_before_cas(
    tmp_path: Path,
    typed_options: dict[str, object],
) -> None:
    """Native JSON values cannot be serialized into a typed string slot before validation."""
    store = FileSystemCAS(tmp_path / "typed-native-rejection")
    options = {
        "kind": "test.typed-native-rejection",
        "media_type": "application/json",
        **typed_options,
    }

    with pytest.raises(TypeError, match="Invalid owned artifact write options"):
        CoreToIRArtifactStoreAdapter(store).put_bytes(
            b'{"typed":"value"}',
            options,
            return_selected_profile=True,
        )

    assert list(store.iter_artifact_ids()) == []


def test_selected_write_rejects_unknown_warning_value_before_core_cas(
    tmp_path: Path,
) -> None:
    """Unknown warning leaves fail through trusted serialization without duck dumps."""

    class LyingSerializer:
        calls = 0

        def model_dump(self, **kwargs: object) -> dict[str, str]:
            self.calls += 1
            return {"laundered": "value"}

    value = LyingSerializer()
    store = FileSystemCAS(tmp_path / "unknown-warning-value")
    options = ArtifactWriteOptions(
        kind="test.unknown-warning-value",
        media_type="application/json",
        warnings=[
            WarningRecord(
                code="unknown-value",
                msg="reject unsupported terminal value",
                data={"value": value},
            )
        ],
    )

    with pytest.raises(TypeError, match="Invalid owned artifact write options"):
        CoreToIRArtifactStoreAdapter(store).put_bytes(
            b'{"unknown":"value"}',
            options,
            return_selected_profile=True,
        )

    assert value.calls == 0
    assert list(store.iter_artifact_ids()) == []


def test_selected_write_preserves_nested_model_aliases_exclusions_and_snapshot(
    tmp_path: Path,
) -> None:
    class NestedPayload(BaseModel):
        public: str = Field(serialization_alias="wire_name")
        private: str = Field(exclude=True)

    payload = b'{"nested":"model"}'
    nested = NestedPayload(public="before", private="sensitive")
    options = ArtifactWriteOptions(
        kind="test.nested-model-wire-semantics",
        media_type="application/json",
        warnings=[
            WarningRecord(
                code="nested-model",
                msg="preserve nested Pydantic JSON semantics",
                data={"nested": nested},
            )
        ],
    )
    direct_store = FileSystemCAS(tmp_path / "direct-nested-model-wire-semantics")
    routed_target = FileSystemCAS(tmp_path / "routed-nested-model-wire-semantics")

    class MutatingStore:
        def __getattr__(self, name: str) -> object:
            return getattr(routed_target, name)

        def put_bytes(
            self,
            data: bytes,
            write_options: ArtifactWriteOptions,
            *,
            return_selected_profile: bool = False,
        ) -> CoreArtifactRef:
            nested.public = "changed after owner preflight"
            nested.private = "changed secret"
            return routed_target.put_bytes(
                data,
                write_options,
                return_selected_profile=return_selected_profile,
            )

    direct_ref = direct_store.put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    routed_ref = CoreToIRArtifactStoreAdapter(MutatingStore()).put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    direct_manifest = direct_store.get_manifest(direct_ref)
    routed_manifest = routed_target.get_manifest(routed_ref)

    assert nested.public == "changed after owner preflight"
    assert direct_ref.manifest_profile_sha256 is not None
    assert routed_ref.manifest_profile_sha256 == direct_ref.manifest_profile_sha256
    assert direct_manifest.warnings is not None
    assert routed_manifest.warnings is not None
    expected_data = {"nested": {"wire_name": "before"}}
    assert direct_manifest.warnings[0].data == expected_data
    assert routed_manifest.warnings[0].data == expected_data
    assert direct_store.get_bytes(direct_ref) == payload
    assert routed_target.get_bytes(routed_ref) == payload


def test_selected_write_preserves_nested_model_serializer_without_duck_dump(
    tmp_path: Path,
) -> None:
    class SerializedPayload(BaseModel):
        value: str
        untrusted_dump_calls: ClassVar[int] = 0
        untrusted_copy_calls: ClassVar[int] = 0
        untrusted_deepcopy_calls: ClassVar[int] = 0

        @model_serializer(mode="plain")
        def serialize_payload(self) -> dict[str, str]:
            return {"declared_wire_value": self.value}

        def model_dump(self, **kwargs: object) -> dict[str, str]:
            type(self).untrusted_dump_calls += 1
            return {"laundered": "value"}

        def __copy__(self) -> SerializedPayload:
            type(self).untrusted_copy_calls += 1
            return type(self)(value="copied")

        def __deepcopy__(self, memo: dict[int, object]) -> SerializedPayload:
            type(self).untrusted_deepcopy_calls += 1
            return type(self)(value="deepcopied")

    payload = b'{"custom":"serializer"}'
    options = ArtifactWriteOptions(
        kind="test.nested-model-serializer",
        media_type="application/json",
        warnings=[
            WarningRecord(
                code="nested-serializer",
                msg="preserve registered Pydantic serializer",
                data={"nested": SerializedPayload(value="retained")},
            )
        ],
    )
    direct_store = FileSystemCAS(tmp_path / "direct-nested-model-serializer")
    routed_store = FileSystemCAS(tmp_path / "routed-nested-model-serializer")

    direct_ref = direct_store.put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    SerializedPayload.untrusted_copy_calls = 0
    SerializedPayload.untrusted_deepcopy_calls = 0
    routed_ref = CoreToIRArtifactStoreAdapter(routed_store).put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    direct_manifest = direct_store.get_manifest(direct_ref)
    routed_manifest = routed_store.get_manifest(routed_ref)

    assert SerializedPayload.untrusted_dump_calls == 0
    assert SerializedPayload.untrusted_copy_calls == 0
    assert SerializedPayload.untrusted_deepcopy_calls == 0
    assert direct_ref.manifest_profile_sha256 is not None
    assert routed_ref.manifest_profile_sha256 == direct_ref.manifest_profile_sha256
    assert direct_manifest.warnings is not None
    assert routed_manifest.warnings is not None
    expected_data = {"nested": {"declared_wire_value": "retained"}}
    assert direct_manifest.warnings[0].data == expected_data
    assert routed_manifest.warnings[0].data == expected_data
    assert direct_store.get_bytes(direct_ref) == payload
    assert routed_store.get_bytes(routed_ref) == payload


def test_selected_write_preserves_core_serializable_nested_mapping_keys(
    tmp_path: Path,
) -> None:
    payload = b'{"mapping":"keys"}'
    options = ArtifactWriteOptions(
        kind="test.nested-mapping-keys",
        media_type="application/json",
        warnings=[
            WarningRecord(
                code="nested-mapping",
                msg="preserve Pydantic JSON key conversion",
                data={"nested": {1: "one", "2": "two"}},
            )
        ],
    )
    direct_store = FileSystemCAS(tmp_path / "direct-nested-mapping-keys")
    routed_store = FileSystemCAS(tmp_path / "routed-nested-mapping-keys")

    direct_ref = direct_store.put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    routed_ref = CoreToIRArtifactStoreAdapter(routed_store).put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    direct_manifest = direct_store.get_manifest(direct_ref)
    routed_manifest = routed_store.get_manifest(routed_ref)

    assert direct_ref.manifest_profile_sha256 is not None
    assert routed_ref.manifest_profile_sha256 == direct_ref.manifest_profile_sha256
    assert direct_manifest.warnings is not None
    assert routed_manifest.warnings is not None
    expected_data = {"nested": {"1": "one", "2": "two"}}
    assert direct_manifest.warnings[0].data == expected_data
    assert routed_manifest.warnings[0].data == expected_data
    assert direct_store.get_bytes(direct_ref) == payload
    assert routed_store.get_bytes(routed_ref) == payload


def test_selected_write_preserves_nested_model_extras_and_private_serializer_state(
    tmp_path: Path,
) -> None:
    class ContextPayload(BaseModel):
        model_config = ConfigDict(extra="allow")
        public: str
        _private_state: str = PrivateAttr()

        @model_serializer(mode="plain")
        def serialize_payload(self) -> dict[str, str]:
            return {
                "public": self.public,
                "extension": self.extension,
                "private_state": self._private_state,
            }

    nested = ContextPayload.model_validate({"public": "retained", "extension": "declared-extra"})
    nested._private_state = "declared-private"
    payload = b'{"private":"state"}'
    options = ArtifactWriteOptions(
        kind="test.nested-model-private-state",
        media_type="application/json",
        warnings=[
            WarningRecord(
                code="nested-private-state",
                msg="preserve Pydantic extra and private serializer inputs",
                data={"nested": nested},
            )
        ],
    )
    direct_store = FileSystemCAS(tmp_path / "direct-nested-model-private-state")
    routed_store = FileSystemCAS(tmp_path / "routed-nested-model-private-state")

    direct_ref = direct_store.put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    routed_ref = CoreToIRArtifactStoreAdapter(routed_store).put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    direct_manifest = direct_store.get_manifest(direct_ref)
    routed_manifest = routed_store.get_manifest(routed_ref)

    assert direct_ref.manifest_profile_sha256 is not None
    assert routed_ref.manifest_profile_sha256 == direct_ref.manifest_profile_sha256
    assert direct_manifest.warnings is not None
    assert routed_manifest.warnings is not None
    expected_data = {
        "nested": {
            "public": "retained",
            "extension": "declared-extra",
            "private_state": "declared-private",
        }
    }
    assert direct_manifest.warnings[0].data == expected_data
    assert routed_manifest.warnings[0].data == expected_data
    assert direct_store.get_bytes(direct_ref) == payload
    assert routed_store.get_bytes(routed_ref) == payload


def test_selected_write_preserves_core_root_model_bridges(tmp_path: Path) -> None:
    """Declared ArtifactID and ComponentId RootModels retain Core validation."""
    payload = b'{"roots":"typed"}'
    component = ComponentId("polisyos.tests@1.0.0")
    source_id = CoreArtifactID.from_sha256_hex(sha256(b"typed root bridge source").hexdigest())
    options = ArtifactWriteOptions(
        kind="test.core-root-model-bridges",
        media_type="application/json",
        producer=ProducerInfo(component=component, version="1.0.0"),
        inputs=[CoreInputRef(artifact_id=source_id, role="source")],
    )
    direct_store = FileSystemCAS(tmp_path / "direct-core-root-model-bridges")
    routed_store = FileSystemCAS(tmp_path / "routed-core-root-model-bridges")

    direct_ref = direct_store.put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    routed_ref = CoreToIRArtifactStoreAdapter(routed_store).put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )

    assert direct_ref.manifest_profile_sha256 is not None
    assert routed_ref.manifest_profile_sha256 == direct_ref.manifest_profile_sha256
    direct_manifest = direct_store.get_manifest(direct_ref)
    routed_manifest = routed_store.get_manifest(routed_ref)
    assert direct_manifest.producer is not None
    assert routed_manifest.producer is not None
    assert direct_manifest.producer.component == component
    assert routed_manifest.producer.component == component
    assert direct_manifest.inputs is not None
    assert routed_manifest.inputs is not None
    assert direct_manifest.inputs[0].artifact_id == source_id
    assert routed_manifest.inputs[0].artifact_id == source_id


def test_selected_write_preserves_custom_root_model_serializer_in_warning_any(
    tmp_path: Path,
) -> None:
    """RootModel Any values use their registered Core serializer, not raw roots."""

    class SerializedRoot(RootModel[str]):
        dump_calls: ClassVar[int] = 0
        copy_calls: ClassVar[int] = 0
        deepcopy_calls: ClassVar[int] = 0
        _secret: str = PrivateAttr(default="retained-private")

        @model_serializer(mode="plain")
        def serialize_root(self) -> dict[str, str]:
            return {"wire_value": self.root, "private": self._secret}

        def model_dump(self, **kwargs: object) -> dict[str, str]:
            type(self).dump_calls += 1
            return {"laundered": "value"}

        def __copy__(self) -> SerializedRoot:
            type(self).copy_calls += 1
            return type(self)("copied")

        def __deepcopy__(self, memo: dict[int, object]) -> SerializedRoot:
            type(self).deepcopy_calls += 1
            return type(self)("deepcopied")

    payload = b'{"roots":"warning"}'
    options = ArtifactWriteOptions(
        kind="test.warning-root-model-any",
        media_type="application/json",
        warnings=[
            WarningRecord(
                code="root-model-any",
                msg="use the declared serializer",
                data={"nested": SerializedRoot("retained")},
            )
        ],
    )
    direct_store = FileSystemCAS(tmp_path / "direct-warning-root-model-any")
    routed_store = FileSystemCAS(tmp_path / "routed-warning-root-model-any")

    direct_ref = direct_store.put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )
    SerializedRoot.copy_calls = 0
    SerializedRoot.deepcopy_calls = 0
    routed_ref = CoreToIRArtifactStoreAdapter(routed_store).put_bytes(
        payload,
        options,
        return_selected_profile=True,
    )

    assert SerializedRoot.dump_calls == 0
    assert SerializedRoot.copy_calls == 0
    assert SerializedRoot.deepcopy_calls == 0
    assert direct_ref.manifest_profile_sha256 is not None
    assert routed_ref.manifest_profile_sha256 == direct_ref.manifest_profile_sha256
    direct_manifest = direct_store.get_manifest(direct_ref)
    routed_manifest = routed_store.get_manifest(routed_ref)
    assert direct_manifest.warnings is not None
    assert routed_manifest.warnings is not None
    expected_data = {"nested": {"wire_value": "retained", "private": "retained-private"}}
    assert direct_manifest.warnings[0].data == expected_data
    assert routed_manifest.warnings[0].data == expected_data
    assert direct_store.get_bytes(direct_ref) == payload
    assert routed_store.get_bytes(routed_ref) == payload


def test_selected_write_rejects_foreign_root_model_in_typed_string_field_before_cas(
    tmp_path: Path,
) -> None:
    """A foreign string RootModel cannot be projected into an owned str field."""

    class ForeignString(RootModel[str]):
        pass

    options = {
        "kind": "test.typed-foreign-root-model",
        "media_type": "application/json",
        "schema": {"name": ForeignString("must-not-coerce"), "version": "1.0"},
    }
    with pytest.raises(TypeError, match="Invalid adapter option 'schema'"):
        core_ir_adapter._coerce_write_options(options)

    target = FileSystemCAS(tmp_path / "typed-foreign-root-model")

    class CountingStore:
        put_calls = 0

        def __getattr__(self, name: str) -> object:
            return getattr(target, name)

        def put_bytes(
            self,
            data: bytes,
            write_options: ArtifactWriteOptions,
            *,
            return_selected_profile: bool = False,
        ) -> CoreArtifactRef:
            self.put_calls += 1
            return target.put_bytes(
                data,
                write_options,
                return_selected_profile=return_selected_profile,
            )

    store = CountingStore()
    with pytest.raises(TypeError, match="Invalid owned artifact write options"):
        CoreToIRArtifactStoreAdapter(store).put_bytes(
            b'{"typed":"root"}',
            options,
            return_selected_profile=True,
        )
    assert store.put_calls == 0
    assert list(target.iter_artifact_ids()) == []


def test_actual_persisted_supported_v3_generic_profile_uses_qualified_reader(tmp_path) -> None:
    """Generic read qualification accepts explicit .3 without enabling an owned writer."""
    root = tmp_path / "generic-v3-profile"
    ref = FileSystemCAS(root).put_bytes(
        b'{"value":1}',
        ArtifactWriteOptions(
            kind="test.persisted-supported-profile",
            media_type="application/json",
            canon=CoreCanonInfo(version="0.3.0"),
        ),
    )
    fresh = FileSystemCAS(root)
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))
    assert get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id) == {"value": 1}
    assert reader.manifest_reads == reader.byte_reads == 1
