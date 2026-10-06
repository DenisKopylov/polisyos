from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    ensure_ir_artifact_store,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
from polisyos.ir.model_layer.canon import CanonViolation as IRCanonViolation


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
