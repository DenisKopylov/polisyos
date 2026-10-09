from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from hashlib import sha256
from types import MappingProxyType

import pytest
from pydantic import BaseModel, ConfigDict, Field

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
)
from polisyos.core.artifacts.manifest import (
    ArtifactAuthorityInfo,
    ArtifactGovernanceInfo,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    EnvInfo,
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
from polisyos.core.artifacts.protocol import resolve_manifest_by_profile
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec as CoreCanonSpec
from polisyos.core.canon import from_canonical_bytes as from_core_canonical_bytes
from polisyos.core.contracts.scientist import FailureCardRef
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts.contracts import CanonInfo as IRCanonInfo
from polisyos.ir.artifacts.contracts import normalize_artifact_ref
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
from polisyos.ir.model_layer.canon import CanonViolation as IRCanonViolation

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

    class RootOnlyObject:
        root = ref.artifact_id

    class StringDumpObject:
        def model_dump(self, *, mode: str) -> str:
            return str(ref.artifact_id)

    for selector in (
        SelectorWithExtraField(),
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
    ):
        with pytest.raises(TypeError, match="Invalid Core artifact selector"):
            adapter.get_manifest(selector)

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
    read_manifest_bytes = core_store.get_manifest_bytes

    def record_manifest_selector(value):
        observed_selectors.append(value)
        return read_manifest_bytes(value)

    monkeypatch.setattr(core_store, "get_manifest_bytes", record_manifest_selector)

    ir_store = ensure_ir_artifact_store(DynamicCoreFacade(core_store))

    assert isinstance(ir_store, CoreToIRArtifactStoreAdapter)
    assert get_json_artifact(ir_store, selector) == {"nested": {"value": 1}}
    assert len(observed_selectors) == 1
    assert isinstance(observed_selectors[0], CoreArtifactRef)
    assert observed_selectors[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256


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


def test_ir_adapter_mapping_write_options_preserve_every_core_option_field(tmp_path) -> None:
    """A Mapping write projects every declared Core option into the durable manifest."""
    exact_bytes = b'{"value":"mapping-options"}'
    core_id = CoreArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + sha256(exact_bytes).hexdigest(),
            "kind": "test.ir-mapping-options",
            "media_type": "application/json",
        }
    ).artifact_id
    options = ArtifactWriteOptions(
        kind="test.ir-mapping-options",
        media_type="application/json",
        schema=CoreSchemaInfo(name="test.ir-mapping-options", version="1"),
        producer=ProducerInfo(component="polisyos.tests.ir_adapter", version="1"),
        env=EnvInfo(python="3.14", platform="test", deps_lock_hash="lock-hash"),
        inputs=[CoreInputRef(artifact_id=core_id, role="source")],
        canon=CoreCanonInfo(),
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
            evidence_input_refs=(str(core_id),),
        ),
        authority=ArtifactAuthorityInfo(
            authority_envelope_ref="sha256:" + "2" * 64,
            diagnostic_event_ref="sha256:" + "3" * 64,
            manifest_ref="cas-manifest://sha256:" + "4" * 64,
            payload_sha256=sha256(exact_bytes).hexdigest(),
        ),
        warnings=[WarningRecord(code="retained", msg="keep this warning")],
    )

    def model_payload(value):
        if value is None:
            return None
        if isinstance(value, list):
            return [model_payload(item) for item in value]
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="python")
        return value

    mapping_options = MappingProxyType(
        {name: model_payload(value) for name, value in vars(options).items()}
    )
    assert isinstance(mapping_options, Mapping)

    store = FileSystemCAS(tmp_path / ".polisyos")
    ref = ensure_ir_artifact_store(store).put_json({"value": "mapping-options"}, mapping_options)
    manifest = store.get_manifest(ref)

    assert manifest.kind == options.kind
    assert manifest.media_type == options.media_type
    assert manifest.artifact_schema == options.schema
    assert manifest.producer == options.producer
    assert manifest.env == options.env
    assert manifest.inputs == options.inputs
    assert manifest.canon == options.canon
    assert manifest.governance == options.governance
    assert manifest.tenant_context == options.tenant_context
    assert manifest.same_input_closure == options.same_input_closure
    assert manifest.authority == options.authority
    assert manifest.warnings == options.warnings


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
    ],
)
def test_ir_adapter_refuses_malformed_supplied_mapping_options(tmp_path, invalid_options) -> None:
    """Supplied malformed option values cannot disappear into adapter defaults."""
    store = FileSystemCAS(tmp_path / ".polisyos")

    with pytest.raises((TypeError, ValueError)):
        ensure_ir_artifact_store(store).put_json({"value": 1}, invalid_options)

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
        {"version": "0.3.0"},
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


def test_current_core_default_put_json_round_trips_through_fresh_ir_reader(tmp_path) -> None:
    """The current Core producer's shared tag subset remains a readable IR value."""
    root = tmp_path / ".polisyos"
    payload = {"amount": Decimal("12.30")}
    ref = FileSystemCAS(root).put_json(
        payload,
        ArtifactWriteOptions(kind="test.core-default-to-ir", media_type="application/json"),
    )
    fresh = FileSystemCAS(root)
    exact_bytes = fresh.get_bytes(ref)
    assert exact_bytes == b'{"amount":{"_type":"decimal","value":"12.30"}}'
    assert ref.artifact_id.hex == sha256(exact_bytes).hexdigest()
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))

    loaded = get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id)

    assert loaded == payload
    assert isinstance(loaded["amount"], Decimal)
    assert reader.manifest_reads == reader.byte_reads == 1
    assert fresh.get_bytes(ref) == exact_bytes


def test_default_ir_artifact_reopens_as_typed_backtest_report(tmp_path) -> None:
    """The actual typed consumer reads a default artifact after a fresh CAS reopen."""
    root = tmp_path / ".polisyos"
    report = BacktestReport(report_id="bt.g-compatible.fresh")
    ref = persist_backtest_report(ensure_ir_artifact_store(FileSystemCAS(root)), report)
    fresh = FileSystemCAS(root)
    exact_bytes = fresh.get_bytes(str(ref.artifact_id))
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(str(ref.artifact_id)))

    loaded = load_backtest_report(_ensure_ir_artifact_store(reader), ref)

    assert isinstance(loaded, BacktestReport)
    assert loaded.report_id == report.report_id
    assert loaded.n_scenarios == 0
    assert reader.manifest_reads == reader.byte_reads == 1
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
    get_manifest_bytes = core_store.get_manifest_bytes
    get_bytes = core_store.get_bytes

    def record_manifest_selector(selector):
        selectors.append(("manifest", selector))
        return get_manifest_bytes(selector)

    def record_blob_selector(selector):
        selectors.append(("blob", selector))
        return get_bytes(selector)

    monkeypatch.setattr(core_store, "get_manifest_bytes", record_manifest_selector)
    monkeypatch.setattr(core_store, "get_bytes", record_blob_selector)

    loaded = get_json_artifact(_ensure_ir_artifact_store(ir_store), selected_ref)
    loaded_from_normalized_ref = get_json_artifact(
        _ensure_ir_artifact_store(ir_store), normalized_ref
    )

    assert loaded == {"nested": {"value": 1}}
    assert loaded_from_normalized_ref == loaded
    assert selectors == [
        ("manifest", selected_ref),
        ("blob", selected_ref),
        ("manifest", selected_ref),
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
    remote_raw_manifest = remote.get_manifest_bytes(ref["artifact_id"])

    def reject_local_raw_manifest(*_args, **_kwargs):
        pytest.fail("raw profile read bypassed the durable owner")

    monkeypatch.setattr(local, "get_manifest_bytes", reject_local_raw_manifest)

    assert get_json_artifact(_ensure_ir_artifact_store(ir_store), ref) == payload
    assert remote.get_manifest_bytes(ref["artifact_id"]) == remote_raw_manifest


@pytest.mark.parametrize(
    ("payload", "exact_bytes"),
    [
        (
            {"_type": "float_hex", "value": "0x1.8p+1"},
            b'{"_type":"float_hex","value":"0x1.8p+1"}',
        ),
        ({"_type": "bytes_hex", "value": "00ff"}, b'{"_type":"bytes_hex","value":"00ff"}'),
        (
            {"_type": "array_digest", "digest": "sha256:abc", "length": 2},
            b'{"_type":"array_digest","digest":"sha256:abc","length":2}',
        ),
    ],
)
def test_current_core_only_tags_are_refused_by_fresh_ir_reader(
    tmp_path, payload, exact_bytes
) -> None:
    """Matching profile names do not widen the historical IR decoder's typed-tag ABI."""
    root = tmp_path / ".polisyos"
    ref = FileSystemCAS(root).put_json(
        payload,
        ArtifactWriteOptions(kind="test.core-only-tags", media_type="application/json"),
    )
    fresh = FileSystemCAS(root)
    assert fresh.get_bytes(ref) == exact_bytes
    assert from_core_canonical_bytes(exact_bytes) is not None
    manifest = fresh.get_manifest(ref).model_dump(mode="json")
    assert manifest["canon"]["name"] == IRCanonInfo().name
    assert manifest["canon"]["version"] == IRCanonInfo().version
    reader = _RawManifestReader(fresh, fresh.get_manifest_bytes(ref))

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        get_json_artifact(_ensure_ir_artifact_store(reader), ref.artifact_id)

    assert reader.manifest_reads == reader.byte_reads == 1
    assert fresh.get_bytes(ref) == exact_bytes


@pytest.mark.parametrize(
    "profile",
    [CoreCanonInfo(name="polisyos.canon.future"), CoreCanonInfo(version="0.3.0")],
)
def test_actual_persisted_mismatched_profile_refuses_before_bytes(tmp_path, profile) -> None:
    """Current Core metadata cannot make an unsupported profile readable by declaration."""
    root = tmp_path / ".polisyos"
    ref = FileSystemCAS(root).put_json(
        {"value": 1},
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
