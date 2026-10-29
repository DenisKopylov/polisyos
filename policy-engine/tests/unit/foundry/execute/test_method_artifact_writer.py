"""Behavioral producer and pre-materialization controls for the real .3 cohort."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, model_serializer

from polisyos.common import canonical
from polisyos.core.artifacts import PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.canon.canon_json import _CANONICAL_TYPES
from polisyos.foundry.execute import read_method_artifact_output_bounded
from polisyos.foundry.execute._internal import graph
from tests._helpers.method_artifact_writer import (
    capture_fixture,
    cas_content,
    local_store,
    produce,
    raw_identity,
    selected_ref,
)


def test_real_sidecar_roundtrip_literal_tags_and_writer_disabled_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    raw = {
        "literal": {"_type": "decimal", "value": "7"},
        "nested": [{"_type": "map", "value": [["_type", "decimal"]]}, None, 1.25],
        "null": None,
    }
    ref = selected_ref(produce(store, capture, occurrence, {"sidecar": raw}))
    assert store.get_manifest(ref).canon.version == "0.3.0"
    assert capture.sidecar_bytes_used == len(store.get_bytes(ref))
    assert capture.sidecar_refs_used == 1
    # Independent fresh reader, with future writes disabled, retains literal tags and nulls.
    monkeypatch.setattr(
        graph,
        "put_core_json_artifact_bounded",
        lambda *a, **k: pytest.fail("writer invoked on read"),
    )
    opened = type(store).open_existing_read_only(tmp_path / "cas")
    read = read_method_artifact_output_bounded(opened, ref, max_bytes=64 * 1024)
    assert raw_identity(read.value["payload"]) == raw_identity(raw)
    assert read.profile_read.reader_policy_id == "core-tag-policy@2"


def test_default_legacy_bytes_and_public_json_writer_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store, "legacy")
    ref = selected_ref(produce(store, capture, occurrence, {"sidecar": {"answer": 4}}))
    assert store.get_manifest(ref).canon.version == "0.2.0"
    assert store.get_bytes(ref) == to_canonical_bytes(
        {
            "schema_version": "1.0",
            "occurrence_id": occurrence.occurrence_id,
            "invocation_id": occurrence.invocation_id,
            "node_id": occurrence.node_id,
            "artifact_key": "sidecar",
            "payload": {"answer": 4},
        },
        CanonSpec(forbid_floats=False),
    )
    before = cas_content(tmp_path / "cas")
    with pytest.raises(Exception, match="writer|unsupported"):
        store.put_json(
            {"answer": 4},
            PutOptions(kind="other", media_type="application/json"),
            canon_spec=CanonSpec(version="0.3.0"),
        )
    assert cas_content(tmp_path / "cas") == before


@pytest.mark.parametrize("raw", [{"too_large": "x" * 1_000_000}, {"nodes": [0] * 8000}])
def test_physical_overbudget_before_json_materialization_or_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: dict[str, Any]
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    before = cas_content(tmp_path / "cas")
    calls = []
    original = canonical.json.dumps

    def observed(*args: Any, **kwargs: Any) -> str:
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(canonical.json, "dumps", observed)
    rows = produce(store, capture, occurrence, {"sidecar": raw})
    assert rows[0][0].status == "unavailable"
    assert calls == []
    assert cas_content(tmp_path / "cas") == before
    assert (capture.sidecar_refs_used, capture.sidecar_bytes_used) == (0, 0)


def test_unsupported_model_never_runs_serializer_or_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    calls = []

    class CallbackModel(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: int = 1

        @model_serializer
        def serialize(self) -> dict[str, int]:
            calls.append(True)
            return {"value": self.value}

    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    before = cas_content(tmp_path / "cas")
    rows = produce(
        store,
        capture,
        occurrence,
        {"nested": {"value": CallbackModel()}, "native": {"value": Decimal("2")}},
    )
    assert [item.status for item in rows[0]] == ["unavailable", "unavailable"]
    assert calls == [] and cas_content(tmp_path / "cas") == before
    assert capture.sidecar_refs_used == 0


def test_mixed_results_keep_unavailable_and_actual_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    rows = produce(store, capture, occurrence, {"good": {"answer": 1}, "bad": {"value": object()}})
    assert {row.artifact_key: row.status for row in rows[0]} == {
        "bad": "unavailable",
        "good": "captured",
    }
    assert rows[1] == "captured"  # This is inventory completeness, not all-artifact success.
    good = next(row for row in rows[0] if row.status == "captured")
    assert capture.sidecar_refs_used == 1
    assert capture.sidecar_bytes_used == len(store.get_bytes(good.artifact_ref))


@pytest.mark.parametrize("value", [(1, 2), -0.0])
def test_native_values_outside_lossless_json_domain_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: Any
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    before = cas_content(tmp_path / "cas")
    rows = produce(store, capture, occurrence, {"sidecar": {"value": value}})
    assert rows[0][0].status == "unavailable"
    assert cas_content(tmp_path / "cas") == before


@pytest.mark.parametrize(
    "marker", [*sorted(_CANONICAL_TYPES), "mapping", "unknown", None, False, 0, [], {}, ["future"]]
)
def test_nested_adversarial_tag_domain_uses_type_sensitive_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: Any
) -> None:
    monkeypatch.setenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "false")
    store = local_store(tmp_path / "cas")
    capture, occurrence = capture_fixture(store)
    raw = {
        "_type": marker,
        "nested": [True, 1, 1.0, None, {"_type": "mapping", "entries": [["_type", marker]]}],
    }
    ref = selected_ref(produce(store, capture, occurrence, {"sidecar": raw}))
    value = read_method_artifact_output_bounded(store, ref, max_bytes=65536).value["payload"]
    assert raw_identity(value) == raw_identity(raw)
