from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts.contracts import CanonInfo as IRCanonInfo
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

    ref = persist_backtest_report(ir_store, report)
    loaded = load_backtest_report(ir_store, ref)

    assert loaded.report_id == "bt.adapter"
    assert loaded.n_scenarios == 0


def test_ensure_ir_artifact_store_preserves_existing_adapter(tmp_path) -> None:
    adapter = CoreToIRArtifactStoreAdapter(FileSystemCAS(tmp_path / ".polisyos"))

    assert ensure_ir_artifact_store(adapter) is adapter


def test_ir_adapter_persists_decimal_bytes_that_the_ir_reader_accepts(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    payload = {"amount": Decimal("12.30")}

    ref = put_json_artifact(
        ir_store,
        payload,
        kind="test.ir-canon-profile",
        schema_name="test.ir-canon-profile",
        schema_version="1.0",
    )

    assert core_store.get_bytes(ref["artifact_id"]) == (
        b'{"amount":{"_type":"decimal","value":"12.30"}}'
    )
    assert get_json_artifact(ir_store, ref["artifact_id"]) == payload


@pytest.mark.parametrize("payload", _IR_INCOMPATIBLE_TAG_PAYLOADS)
def test_ir_adapter_rejects_incompatible_tags_before_persisting(tmp_path, payload) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        put_json_artifact(
            ir_store,
            payload,
            kind="test.ir-canon-profile",
            schema_name="test.ir-canon-profile",
            schema_version="1.0",
        )

    assert core_store.iter_artifact_ids() == []


class _MappingManifestReader:
    """Expose a real persisted manifest Mapping and count reader-side effects."""

    def __init__(self, store, manifest) -> None:
        self.store = store
        self.manifest = manifest
        self.manifest_reads = 0
        self.byte_reads = 0

    def get_manifest(self, artifact_id):
        self.manifest_reads += 1
        return self.manifest

    def get_bytes(self, artifact_id):
        self.byte_reads += 1
        return self.store.get_bytes(artifact_id)


def test_ir_reader_accepts_complete_json_manifest_mapping_without_byte_mutation(tmp_path) -> None:
    """The existing G producer and a Mapping reader agree on exact Decimal bytes."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    payload = {"amount": Decimal("12.30")}
    ref = CoreArtifactRef.model_validate(
        put_json_artifact(
            ir_store,
            payload,
            kind="test.ir-reader-mapping",
            schema_name="test.ir-reader-mapping",
            schema_version="1.0",
        )
    )
    persisted_bytes = core_store.get_bytes(ref.artifact_id)
    read_store = FileSystemCAS(tmp_path / ".polisyos")
    manifest = read_store.get_manifest(ref.artifact_id).model_dump(mode="json")
    expected_manifest = deepcopy(manifest)
    reader = _MappingManifestReader(read_store, manifest)

    assert get_json_artifact(reader, ref.artifact_id) == payload
    assert reader.manifest_reads == reader.byte_reads == 1
    assert manifest == expected_manifest
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
        ir_store,
        payload,
        kind="test.ir-reader-depth",
        schema_name="test.ir-reader-depth",
        schema_version="1.0",
        canon_spec=IRCanonSpec(max_depth=129),
    )
    read_store = FileSystemCAS(tmp_path / ".polisyos")
    manifest = read_store.get_manifest(ref["artifact_id"]).model_dump(mode="json")
    expected_manifest = deepcopy(manifest)
    reader = _MappingManifestReader(read_store, manifest)

    assert get_json_artifact(reader, ref["artifact_id"]) == payload
    assert reader.manifest_reads == reader.byte_reads == 1
    assert manifest == expected_manifest


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
        ir_store,
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
    expected_manifest = deepcopy(manifest)
    reader = _MappingManifestReader(read_store, manifest)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(reader, ref["artifact_id"])
    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0
    assert manifest == expected_manifest


@pytest.mark.parametrize("missing_field", tuple(IRCanonInfo.model_fields))
def test_ir_reader_requires_every_persisted_profile_field_before_bytes(
    tmp_path, missing_field: str
) -> None:
    """Defaults cannot fill an omitted field in the persisted profile ABI."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    ref = put_json_artifact(
        ir_store,
        {"amount": Decimal("12.30")},
        kind="test.ir-reader-complete-profile",
        schema_name="test.ir-reader-complete-profile",
        schema_version="1.0",
    )
    read_store = FileSystemCAS(tmp_path / ".polisyos")
    manifest = read_store.get_manifest(ref["artifact_id"]).model_dump(mode="json")
    manifest["canon"].pop(missing_field)
    expected_manifest = deepcopy(manifest)
    reader = _MappingManifestReader(read_store, manifest)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(reader, ref["artifact_id"])
    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0
    assert manifest == expected_manifest
