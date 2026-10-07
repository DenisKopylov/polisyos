from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.artifacts import ArtifactOwnershipError
from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.artifacts.manifest import SchemaInfo as CoreSchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts.contracts import StorePutOptions
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
from polisyos.ir.model_layer.canon import CanonViolation as IRCanonViolation
from polisyos.ir.model_layer.canon import to_canonical_bytes as ir_to_canonical_bytes


def _nested_list(depth: int) -> object:
    value: object = 0
    for _ in range(depth):
        value = [value]
    return value


class JsonOnlyArtifactStore:
    """Legacy protocol fake without a byte-write capability."""

    def __init__(self) -> None:
        self.put_json_calls = 0

    def put_json(self, obj, opts, canon_spec=None):
        self.put_json_calls += 1
        return {
            "artifact_id": "sha256:" + ("0" * 64),
            "kind": opts.kind,
            "media_type": opts.media_type,
        }


class MalformedProfileArtifactStore:
    """Expose untrusted manifest metadata to the reader contract."""

    def __init__(self, canon):
        self.canon = canon
        self.byte_reads = 0

    def get_manifest(self, artifact_id):
        del artifact_id
        return {"canon": self.canon}

    def get_bytes(self, artifact_id):
        del artifact_id
        self.byte_reads += 1
        return b'{"value":1}'


class JsonMappingManifestArtifactStore:
    """Expose a full JSON-mode manifest mapping while reading bytes from a real CAS."""

    def __init__(self, store, manifest):
        self.store = store
        self.manifest = manifest
        self.byte_reads = 0

    def get_manifest(self, artifact_id):
        del artifact_id
        return self.manifest

    def get_bytes(self, artifact_id):
        self.byte_reads += 1
        return self.store.get_bytes(artifact_id)


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


def test_ir_adapter_preserves_all_write_options_and_selected_input_view(tmp_path) -> None:
    """The Core manifest retains every typed IR-to-CAS option across adaptation."""
    store = FileSystemCAS(tmp_path / "scoped-cas").with_ambient_ownership_enforcement()
    adapter = CoreToIRArtifactStoreAdapter(store)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        store.put_bytes(
            b"shared parent bytes",
            PutOptions(kind="test.parent.default", media_type="text/plain"),
        )
        selected_parent = store.put_bytes(
            b"shared parent bytes",
            PutOptions(kind="test.parent.selected", media_type="text/plain"),
        )
        assert selected_parent.manifest_profile_sha256 is not None

        ref = adapter.put_bytes(
            b'{"value":1}',
            StorePutOptions(
                kind="test.ir-adapter.options",
                media_type="application/json",
                schema={"name": "test.ir-adapter.options", "version": "1.0"},
                producer={"component": "test-suite", "version": "1.0"},
                env={
                    "python": "3.14",
                    "platform": "test",
                    "deps_lock_hash": "sha256:" + "a" * 64,
                },
                inputs=[
                    {
                        "artifact_id": str(selected_parent.artifact_id),
                        "role": "selected_parent",
                        "manifest_profile_sha256": selected_parent.manifest_profile_sha256,
                    }
                ],
                canon={"forbid_floats": False},
                governance={"classification": "internal"},
                tenant_context={"tenant_id": "tenant-a", "cell_id": "cell-a"},
                same_input_closure={
                    "closure_id": "closure-a",
                    "status": "candidate_only",
                    "run_id": "run-a",
                    "job_id": "job-a",
                    "tenant_id": "tenant-a",
                    "cell_id": "cell-a",
                    "evidence_input_refs": [str(selected_parent.artifact_id)],
                },
                authority={
                    "authority_envelope_ref": "envelope://a",
                    "diagnostic_event_ref": "event://a",
                    "manifest_ref": "manifest://a",
                    "payload_sha256": "sha256:" + "b" * 64,
                },
                warnings=[{"code": "retained", "msg": "keep this warning"}],
            ),
        )

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        manifest = store.get_manifest(ref)
        assert manifest.kind == "test.ir-adapter.options"
        assert manifest.media_type == "application/json"
        assert manifest.artifact_schema.name == "test.ir-adapter.options"
        assert manifest.artifact_schema.version == "1.0"
        assert manifest.producer.component == "test-suite"
        assert manifest.env.python == "3.14"
        assert manifest.canon is not None and manifest.canon.forbid_floats is False
        assert manifest.governance.classification == "internal"
        assert manifest.tenant_context.tenant_id == "tenant-a"
        assert manifest.tenant_context.cell_id == "cell-a"
        assert manifest.same_input_closure.closure_id == "closure-a"
        assert manifest.same_input_closure.evidence_input_refs == (
            str(selected_parent.artifact_id),
        )
        assert manifest.authority.authority_envelope_ref == "envelope://a"
        assert manifest.warnings[0].code == "retained"
        assert manifest.warnings[0].msg == "keep this warning"
        assert str(manifest.inputs[0].artifact_id) == str(selected_parent.artifact_id)
        assert manifest.inputs[0].manifest_profile_sha256 == (
            selected_parent.manifest_profile_sha256
        )
        assert store.get_bytes(ref) == b'{"value":1}'


def test_ir_adapter_preserves_foreign_selected_input_for_core_admission(tmp_path) -> None:
    """A foreign selected input remains visible to Core's ownership rejection."""
    store = FileSystemCAS(tmp_path / "scoped-cas").with_ambient_ownership_enforcement()
    adapter = CoreToIRArtifactStoreAdapter(store)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        store.put_bytes(
            b"foreign parent bytes",
            PutOptions(kind="test.foreign-parent.default", media_type="text/plain"),
        )
        foreign_parent = store.put_bytes(
            b"foreign parent bytes",
            PutOptions(kind="test.foreign-parent.selected", media_type="text/plain"),
        )

    assert foreign_parent.manifest_profile_sha256 is not None
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
        with pytest.raises(ArtifactOwnershipError, match="write input:foreign_parent"):
            adapter.put_bytes(
                b"child with foreign selected input",
                StorePutOptions(
                    kind="test.foreign-child",
                    media_type="application/octet-stream",
                    inputs=[
                        {
                            "artifact_id": str(foreign_parent.artifact_id),
                            "role": "foreign_parent",
                            "manifest_profile_sha256": foreign_parent.manifest_profile_sha256,
                        }
                    ],
                ),
            )
        assert store.iter_artifact_ids() == []


def test_ir_adapter_refuses_a_canon_profile_that_does_not_match_its_bytes(tmp_path) -> None:
    """A mismatched Core canon declaration cannot accompany IR-profile bytes."""
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    adapter = CoreToIRArtifactStoreAdapter(core_store)

    with pytest.raises(ValueError, match="ir_canon_profile_mismatch"):
        adapter.put_json(
            {"score": 0.25},
            PutOptions(
                kind="test.ir-canon-profile",
                media_type="application/json",
                canon=CoreCanonInfo(forbid_floats=True),
            ),
            canon_spec=IRCanonSpec(forbid_floats=False),
        )

    assert core_store.iter_artifact_ids() == []


@pytest.mark.parametrize("payload", _IR_INCOMPATIBLE_TAG_PAYLOADS)
def test_ir_json_helper_rejects_core_only_tags_before_raw_core_persistence(
    tmp_path, payload
) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")

    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        put_json_artifact(
            core_store,
            payload,
            kind="test.ir-canon-profile",
            schema_name="test.ir-canon-profile",
            schema_version="1.0",
        )

    assert core_store.iter_artifact_ids() == []


def test_direct_core_json_writer_remains_an_ir_profile_bypass(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    payload = {"_type": "float_hex", "value": "0x1.8p+1"}

    ref = core_store.put_json(
        payload,
        PutOptions(kind="test.core-canon-profile", media_type="application/json"),
    )

    assert core_store.iter_artifact_ids() == [ref.artifact_id]
    with pytest.raises(IRCanonViolation, match="Unknown canonical _type"):
        get_json_artifact(core_store, ref.artifact_id)


def test_ir_json_helper_preserves_exact_bytes_through_raw_core_store(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    payload = {"amount": Decimal("12.30")}

    ref = put_json_artifact(
        core_store,
        payload,
        kind="test.ir-canon-profile",
        schema_name="test.ir-canon-profile",
        schema_version="1.0",
    )

    assert core_store.get_bytes(ref["artifact_id"]) == (
        b'{"amount":{"_type":"decimal","value":"12.30"}}'
    )
    manifest = core_store.get_manifest(ref["artifact_id"])
    assert manifest.canon is not None
    assert manifest.canon.version == "0.2.0"
    assert manifest.canon.forbid_floats is True
    assert get_json_artifact(core_store, ref["artifact_id"]) == payload


def test_ir_json_helper_preserves_explicit_finite_float_profile(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    payload = {"score": 0.25}

    ref = put_json_artifact(
        core_store,
        payload,
        kind="test.ir-canon-profile",
        schema_name="test.ir-canon-profile",
        schema_version="1.0",
        canon_spec=IRCanonSpec(forbid_floats=False),
    )

    assert core_store.get_bytes(ref["artifact_id"]) == (
        b'{"score":{"_type":"float","repr":"0.25"}}'
    )
    manifest = core_store.get_manifest(ref["artifact_id"])
    assert manifest.canon is not None
    assert manifest.canon.forbid_floats is False
    assert get_json_artifact(core_store, ref["artifact_id"]) == payload


def test_ir_json_reader_uses_the_persisted_profile_depth(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ir_store = ensure_ir_artifact_store(core_store)
    payload = _nested_list(129)

    ref = put_json_artifact(
        core_store,
        payload,
        kind="test.ir-depth-profile",
        schema_name="test.ir-depth-profile",
        schema_version="1.0",
        canon_spec=IRCanonSpec(max_depth=129),
    )

    manifest = core_store.get_manifest(ref["artifact_id"])
    assert manifest.canon is not None and manifest.canon.max_depth == 129
    assert get_json_artifact(ir_store, ref["artifact_id"]) == payload


def test_ir_json_reader_accepts_unmodified_json_mode_manifest_mapping(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    payload = {"mapping_exact_probe": True, "value": 1729}

    ref_payload = put_json_artifact(
        core_store,
        payload,
        kind="test.ir-canon-json-mapping",
        schema_name="test.ir-canon-json-mapping",
        schema_version="1.0",
    )
    artifact_ref = CoreArtifactRef.model_validate(ref_payload)
    manifest = core_store.get_manifest(artifact_ref.artifact_id)
    original_json_manifest = manifest.model_dump(mode="json")
    mapping_store = JsonMappingManifestArtifactStore(core_store, original_json_manifest)

    assert isinstance(artifact_ref, CoreArtifactRef)
    assert original_json_manifest["artifact_id"] == str(artifact_ref.artifact_id)
    assert original_json_manifest["canon"]["separators"] == [",", ":"]
    assert mapping_store.manifest == original_json_manifest
    assert get_json_artifact(mapping_store, artifact_ref.artifact_id) == payload
    assert mapping_store.manifest == original_json_manifest
    assert mapping_store.byte_reads == 1


@pytest.mark.parametrize(
    "separators",
    [
        pytest.param([":"], id="one-item-list"),
        pytest.param([",", ":", ";"], id="three-item-list"),
        pytest.param([",", 1], id="non-string-item"),
        pytest.param([True, ":"], id="bool-item"),
    ],
)
def test_ir_json_reader_rejects_malformed_json_mapping_separators_before_bytes(separators):
    canon = CoreCanonInfo().model_dump(mode="json")
    canon["separators"] = separators
    store = MalformedProfileArtifactStore(canon)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(store, "sha256:" + "a" * 64)
    assert store.byte_reads == 0


@pytest.mark.parametrize(
    "profile_updates",
    [
        pytest.param({"name": "polisyos.canon.future"}, id="unsupported-name"),
        pytest.param({"version": "0.3.0"}, id="unsupported-version"),
    ],
)
def test_ir_json_reader_rejects_unsupported_json_mapping_profiles_before_bytes(profile_updates):
    canon = CoreCanonInfo().model_dump(mode="json")
    canon.update(profile_updates)
    store = MalformedProfileArtifactStore(canon)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(store, "sha256:" + "a" * 64)
    assert store.byte_reads == 0


@pytest.mark.parametrize(
    "profile_updates",
    [
        pytest.param({"forbid_floats": "false"}, id="wrong-parameter-type"),
        pytest.param({"max_depth": "129"}, id="wrong-depth-type"),
        pytest.param({"unexpected": "value"}, id="extra-field"),
    ],
)
def test_ir_json_reader_keeps_other_json_mapping_profile_fields_strict_before_bytes(
    profile_updates,
):
    canon = CoreCanonInfo().model_dump(mode="json")
    canon.update(profile_updates)
    store = MalformedProfileArtifactStore(canon)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(store, "sha256:" + "a" * 64)
    assert store.byte_reads == 0


def test_ir_json_reader_rejects_profileless_json_mapping_before_bytes() -> None:
    store = MalformedProfileArtifactStore(None)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(store, "sha256:" + "a" * 64)
    assert store.byte_reads == 0


def test_ir_json_reader_obeys_a_too_low_persisted_profile_depth(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    payload = _nested_list(129)
    canonical_bytes = ir_to_canonical_bytes(payload, IRCanonSpec(max_depth=129))

    ref = core_store.put_bytes(
        canonical_bytes,
        PutOptions(
            kind="test.ir-depth-profile-mismatch",
            media_type="application/json",
            canon=CoreCanonInfo(max_depth=128),
        ),
    )

    manifest = core_store.get_manifest(ref)
    assert manifest.canon is not None and manifest.canon.max_depth == 128
    with pytest.raises(IRCanonViolation, match="max_depth=128"):
        get_json_artifact(core_store, ref.artifact_id)


def test_ir_json_reader_rejects_unprofiled_bytes_even_with_legacy_markers(
    tmp_path, monkeypatch
) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    payload_bytes = b'{"legacy":true}'
    ref = core_store.put_bytes(
        payload_bytes,
        PutOptions(
            kind="ir.legacy-json",
            media_type="application/json",
            schema=CoreSchemaInfo(name="polisyos.ir.legacy-json", version="1.0"),
        ),
    )

    manifest = core_store.get_manifest(ref)
    assert manifest.canon is None
    assert manifest.kind == "ir.legacy-json"
    assert manifest.artifact_schema == CoreSchemaInfo(name="polisyos.ir.legacy-json", version="1.0")
    assert core_store.get_bytes(ref) == payload_bytes

    get_bytes = core_store.get_bytes
    byte_reads = 0

    def track_get_bytes(artifact_id):
        nonlocal byte_reads
        byte_reads += 1
        return get_bytes(artifact_id)

    monkeypatch.setattr(core_store, "get_bytes", track_get_bytes)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(core_store, ref.artifact_id)
    assert byte_reads == 0


@pytest.mark.parametrize(
    "canon",
    [
        CoreCanonInfo(name="polisyos.canon.future"),
        CoreCanonInfo(version="0.3.0"),
        CoreCanonInfo(max_depth=-1),
    ],
)
def test_ir_json_reader_rejects_unsupported_persisted_profiles(
    tmp_path, canon, monkeypatch
) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")
    ref = core_store.put_bytes(
        b'{"value":1}',
        PutOptions(
            kind="test.ir-unsupported-profile",
            media_type="application/json",
            canon=canon,
        ),
    )
    get_bytes = core_store.get_bytes
    byte_reads = 0

    def track_get_bytes(artifact_id):
        nonlocal byte_reads
        byte_reads += 1
        return get_bytes(artifact_id)

    monkeypatch.setattr(core_store, "get_bytes", track_get_bytes)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(core_store, ref.artifact_id)
    assert byte_reads == 0


@pytest.mark.parametrize("canon", [{"max_depth": "129"}, {"max_depth": 129}])
def test_ir_json_reader_rejects_malformed_profile_parameters(canon) -> None:
    store = MalformedProfileArtifactStore(canon)

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        get_json_artifact(store, "sha256:" + "a" * 64)
    assert store.byte_reads == 0


@pytest.mark.parametrize(
    "canon_spec",
    [
        IRCanonSpec(name="polisyos.canon.future"),
        IRCanonSpec(version="0.3.0"),
        IRCanonSpec(max_depth=True),
    ],
)
def test_ir_json_writer_refuses_unsupported_profile_identity_before_persisting(
    tmp_path, canon_spec
) -> None:
    core_store = FileSystemCAS(tmp_path / ".polisyos")

    with pytest.raises(IRCanonViolation, match="unsupported_ir_canon_profile"):
        put_json_artifact(
            core_store,
            {"value": 1},
            kind="test.ir-unsupported-profile",
            schema_name="test.ir-unsupported-profile",
            schema_version="1.0",
            canon_spec=canon_spec,
        )

    assert core_store.iter_artifact_ids() == []


def test_ir_json_helper_refuses_json_only_store_without_fallback() -> None:
    store = JsonOnlyArtifactStore()

    with pytest.raises(TypeError, match="put_bytes"):
        put_json_artifact(
            store,
            {"value": 1},
            kind="test.ir-canon-profile",
            schema_name="test.ir-canon-profile",
            schema_version="1.0",
        )

    assert store.put_json_calls == 0


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
