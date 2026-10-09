from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from hashlib import sha256

import pytest

from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec as CoreCanonSpec
from polisyos.core.canon import from_canonical_bytes as from_core_canonical_bytes
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
    reader = _MappingManifestReader(fresh, fresh.get_manifest(ref).model_dump(mode="json"))

    loaded = get_json_artifact(reader, ref.artifact_id)

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
    manifest = fresh.get_manifest(str(ref.artifact_id)).model_dump(mode="json")
    reader = _MappingManifestReader(fresh, manifest)

    loaded = load_backtest_report(reader, ref)

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
    reader = _MappingManifestReader(fresh, manifest)

    loaded = get_json_artifact(reader, ref.artifact_id)

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
    reader = _MappingManifestReader(fresh, manifest)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(reader, ref.artifact_id)

    assert reader.manifest_reads == 1
    assert reader.byte_reads == 0
    assert fresh.get_bytes(ref) == exact_bytes


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
    reader = _MappingManifestReader(fresh, manifest)

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        get_json_artifact(reader, ref.artifact_id)

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
    reader = _MappingManifestReader(fresh, fresh.get_manifest(ref).model_dump(mode="json"))

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(reader, ref.artifact_id)

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
    reader = _MappingManifestReader(fresh, fresh.get_manifest(ref).model_dump(mode="json"))

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        get_json_artifact(reader, ref.artifact_id)

    assert reader.manifest_reads == reader.byte_reads == 1
    assert fresh.get_bytes(ref) == exact_bytes
