"""Real selected-CAS round trips for native Phase D.4 replay parameters."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.backtesting.phase_d4_source import (
    PHASE_D4_REPLAY_SOURCE_ARTIFACT_KIND,
    PHASE_D4_REPLAY_SOURCE_SCHEMA_NAME,
    PHASE_D4_SELECTION_INPUT_ROLE,
    PhaseD4ReplayError,
    PhaseD4ReplaySource,
    load_selected_phase_d4_replay_source,
    persist_phase_d4_replay_source,
)


def _source(store: FileSystemCAS, **updates: object) -> PhaseD4ReplaySource:
    """Provide genuine selected views; these bytes assert no candidate authority."""
    candidate = store.put_json(
        {"candidate": "codec-fixture"},
        PutOptions(kind="scientist.test_candidate", media_type="application/json"),
        return_selected_profile=True,
    )
    selection = store.put_json(
        {"selection": "codec-fixture"},
        PutOptions(
            kind="scientist.test_selection",
            media_type="application/json",
            inputs=[input_ref_from_artifact_ref(candidate, role="candidate")],
        ),
        return_selected_profile=True,
    )
    return PhaseD4ReplaySource.model_validate(
        {
            "captured_at": datetime(2026, 10, 31, tzinfo=UTC),
            "run_id": "R_decimal_replay",
            "loop_id": "loop-decimal-replay",
            "candidate_ref": candidate,
            "selection_evaluation_ref": selection,
            **updates,
        }
    )


@pytest.mark.parametrize(
    "value",
    [
        Decimal("0.5"),
        Decimal("0.123456789012345678901234567890123456789"),
        Decimal("1e-10000"),
        Decimal("1e10000"),
    ],
)
def test_selected_cas_round_trip_preserves_native_decimal(tmp_path, value: Decimal) -> None:
    store = FileSystemCAS(tmp_path)
    source = _source(
        store,
        params={
            "baseline_policy_value": value,
            "strategic_response_summary": {
                "nested": [value, str(value), None, {"retained_null": None}],
            },
        },
    )
    ref = persist_phase_d4_replay_source(store, source)
    # A fresh owner has no in-memory source model or producer conversion cache.
    fresh_store = FileSystemCAS(tmp_path)
    loaded, manifest = load_selected_phase_d4_replay_source(fresh_store, ref)
    native = loaded.params["baseline_policy_value"]
    nested = loaded.params["strategic_response_summary"]["nested"]
    assert type(native) is Decimal
    assert native == value
    assert type(nested[0]) is Decimal
    assert nested[0] == value
    assert type(nested[1]) is str
    assert nested[1] == str(value)
    assert nested[2] is None
    assert nested[3] == {"retained_null": None}
    assert loaded == source
    assert manifest.artifact_schema.version == loaded.schema_version == "1.1"
    assert manifest.canon.exclude_none is False


def test_decimal_and_same_text_string_have_distinct_source_bytes(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    numeric = _source(store, params={"baseline_policy_value": Decimal("0.5")})
    textual = _source(store, params={"baseline_policy_value": "0.5"})
    numeric_ref = persist_phase_d4_replay_source(store, numeric)
    textual_ref = persist_phase_d4_replay_source(store, textual)
    assert numeric_ref.artifact_id != textual_ref.artifact_id
    numeric_read, _ = load_selected_phase_d4_replay_source(FileSystemCAS(tmp_path), numeric_ref)
    textual_read, _ = load_selected_phase_d4_replay_source(FileSystemCAS(tmp_path), textual_ref)
    assert type(numeric_read.params["baseline_policy_value"]) is Decimal
    assert type(textual_read.params["baseline_policy_value"]) is str


@pytest.mark.parametrize(
    "value",
    [Decimal("NaN"), Decimal("Infinity"), float("inf"), float("nan"), object()],
)
def test_replay_source_rejects_nonfinite_or_unsupported_nested_values(tmp_path, value) -> None:
    with pytest.raises(ValidationError, match="phase_d4_replay_source_"):
        _source(FileSystemCAS(tmp_path), params={"strategic_response_summary": {"value": value}})


def test_legacy_source_remains_readable_without_decimal_coercion(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    source = _source(
        store, schema_version="1.0", params={"baseline_policy_value": "0.5", "policy_value": 1}
    )
    # The historical writer projected JSON, including an ISO timestamp string.
    ref = store.put_json(
        source.model_dump(mode="json"),
        PutOptions(
            kind=PHASE_D4_REPLAY_SOURCE_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=PHASE_D4_REPLAY_SOURCE_SCHEMA_NAME, version="1.0"),
            producer=ProducerInfo(
                component="polisyos.scientist.methods.backtesting.phase_d4_source",
                version="1.0",
            ),
            inputs=[
                input_ref_from_artifact_ref(source.candidate_ref, role="candidate"),
                input_ref_from_artifact_ref(
                    source.selection_evaluation_ref, role=PHASE_D4_SELECTION_INPUT_ROLE
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    loaded, _ = load_selected_phase_d4_replay_source(FileSystemCAS(tmp_path), ref)
    assert loaded == source
    assert loaded.params == {"baseline_policy_value": "0.5", "policy_value": 1}
    with pytest.raises(ValidationError, match="decimal_requires_v1_1"):
        _source(store, schema_version="1.0", params={"baseline_policy_value": Decimal("0.5")})


def test_reader_rejects_body_manifest_schema_version_mismatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    source = _source(store, params={"baseline_policy_value": Decimal("0.5")})
    ref = persist_phase_d4_replay_source(store, source)
    manifest = store.get_manifest(ref)
    wrong_ref = store.put_json(
        source.model_dump(mode="python"),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(name=PHASE_D4_REPLAY_SOURCE_SCHEMA_NAME, version="1.0"),
            producer=manifest.producer,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    assert wrong_ref.artifact_id == ref.artifact_id
    assert wrong_ref.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert load_core_json_artifact(store, wrong_ref)["schema_version"] == "1.1"
    with pytest.raises(PhaseD4ReplayError, match="schema_version_mismatch"):
        load_selected_phase_d4_replay_source(FileSystemCAS(tmp_path), wrong_ref)
