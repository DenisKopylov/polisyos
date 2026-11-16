"""Pure candidate SQL projection contracts, not SQL execution or authority proof."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.contracts import (
    REGISTERED_SQL_MEASUREMENT_LIMITATIONS,
    ModelInputScope,
    RegisteredSQLMeasurementSourceSelection,
    SelectedVariableBindingRef,
    VariableRepresentationRef,
    VariableSemanticDefinitionRef,
    load_scoped_measurement_occurrence,
    replay_registered_sql_measurement_occurrence,
    scoped_measurement_occurrence_manifest_inputs,
)


def _ref(kind: str, fill: str) -> dict[str, str]:
    return {
        "artifact_id": "sha256:" + fill * 64,
        "kind": kind,
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "f" * 64,
    }


def _source(path: str = "0.value") -> RegisteredSQLMeasurementSourceSelection:
    return RegisteredSQLMeasurementSourceSelection(
        registered_sql_admission_ref=SelectedVariableBindingRef(
            **_ref("fabric.registered_sql_admission_binding", "1")
        ),
        capture_ref=SelectedVariableBindingRef(**_ref("fabric.registered_sql_capture", "2")),
        snapshot_ref=SelectedVariableBindingRef(**_ref("fabric.data_snapshot", "3")),
        payload_ref=SelectedVariableBindingRef(**_ref("fabric.tabular_payload", "4")),
        source_path=path,
        declared_source_definition_ref=VariableSemanticDefinitionRef(
            **_ref("catalog.variable_semantic_definition", "5")
        ),
        declared_source_representation_ref=VariableRepresentationRef(
            **_ref("catalog.variable_representation", "6")
        ),
        declared_release="test-only-declared-release",
        source_scope=ModelInputScope(
            population_ref="population:test",
            geography_ref="geography:test",
            jurisdiction_ref="jurisdiction:test",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
        canonical_variable="fixture.amount",
        canonical_unit="amount",
    )


def test_sql_projection_binds_the_selected_path_even_when_values_are_equal() -> None:
    payload = [{"value": 12.5, "alias": 12.5}]
    selected = replay_registered_sql_measurement_occurrence(payload, source_selection=_source())
    alternate = replay_registered_sql_measurement_occurrence(
        payload, source_selection=_source("0.alias")
    )

    assert selected.canonical_value == alternate.canonical_value == "12.5"
    assert selected.observation_id != alternate.observation_id
    assert selected.observation_content_sha256 != alternate.observation_content_sha256
    assert selected.source_selection.source_meaning_provenance == "consumer_asserted"
    assert selected.source_selection.source_release_provenance == "consumer_asserted"
    assert selected.source_selection.source_scope_provenance == "consumer_asserted"
    assert selected.source_selection.source_currentness == "not_established"
    assert selected.source_selection.limitation_codes == REGISTERED_SQL_MEASUREMENT_LIMITATIONS
    assert "source_passport_ref" not in selected.model_dump(mode="json")
    assert "epoch_id" not in selected.model_dump(mode="json")
    edges = scoped_measurement_occurrence_manifest_inputs(selected)
    assert [edge.role for edge in edges] == [
        "sql.admission",
        "sql.capture",
        "sql.snapshot",
        "source.payload:0.value",
        "source.definition",
        "source.representation",
    ]
    assert edges[3].manifest_profile_sha256 == _source().payload_ref.manifest_profile_sha256


@pytest.mark.parametrize("value", [None, True, "12.5", [12.5], {"value": 12.5}])
def test_sql_projection_refuses_non_scalar_or_coerced_values(value: object) -> None:
    with pytest.raises(ValueError, match="registered_sql_measurement_scalar_required"):
        replay_registered_sql_measurement_occurrence([{"value": value}], source_selection=_source())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_sql_projection_refuses_nonfinite_values(value: float) -> None:
    with pytest.raises(ValueError, match="registered_sql_measurement_value_not_finite"):
        replay_registered_sql_measurement_occurrence([{"value": value}], source_selection=_source())


@pytest.mark.parametrize("path", ["value", "00.value", "-1.value", "0..value", "0.value.more"])
def test_sql_projection_requires_an_explicit_flat_row_and_column(path: str) -> None:
    with pytest.raises(ValidationError, match="registered_sql_measurement_source_path_invalid"):
        _source(path)


def test_sql_projection_revalidates_unvalidated_candidate_limit_grafts() -> None:
    source = _source().model_copy(update={"limitation_codes": ()})
    with pytest.raises(ValidationError, match="registered_sql_measurement_limitations_required"):
        replay_registered_sql_measurement_occurrence([{"value": 12.5}], source_selection=source)


def test_sql_projection_does_not_default_a_missing_cell() -> None:
    with pytest.raises(ValueError, match="registered_sql_measurement_source_path_missing"):
        replay_registered_sql_measurement_occurrence([{"alias": 12.5}], source_selection=_source())


@pytest.mark.parametrize("version", ["1.0", "2.0"])
def test_occurrence_versions_preserve_selected_wire_and_cold_readback(
    tmp_path: Path, version: str
) -> None:
    """Check the real CAS codec only; source-owner replay has separate semantic tests."""
    from tests.unit.core.contracts.test_variable_binding import _correspondence_case

    legacy = _correspondence_case().occurrence
    sql = replay_registered_sql_measurement_occurrence(
        [{"value": 12.5}], source_selection=_source()
    )
    occurrence = legacy if version == "1.0" else sql
    wire = to_canonical_bytes(occurrence)
    store = FileSystemCAS(tmp_path / "cas")
    inputs = list(scoped_measurement_occurrence_manifest_inputs(occurrence))
    options = PutOptions(
        kind=occurrence.ARTIFACT_KIND,
        media_type=occurrence.ARTIFACT_MEDIA_TYPE,
        schema=SchemaInfo(name=occurrence.ARTIFACT_SCHEMA_NAME, version=version),
        inputs=inputs,
    )
    ref = store.put_json(occurrence, options, return_selected_profile=True)
    assert store.get_bytes(ref) == wire
    reader = FileSystemCAS.open_existing_read_only(store.root)
    actual = load_scoped_measurement_occurrence(reader, ref)
    assert type(actual) is type(occurrence)
    assert actual == occurrence
    assert to_canonical_bytes(actual) == wire
    assert reader.get_manifest(ref).inputs == inputs

    # A second view of identical bytes must not relabel either payload version.
    unsupported = store.put_bytes(
        wire,
        PutOptions(
            kind=occurrence.ARTIFACT_KIND,
            media_type=occurrence.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=occurrence.ARTIFACT_SCHEMA_NAME, version="9.9"),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    assert unsupported.artifact_id == ref.artifact_id
    with pytest.raises(ValueError, match=r"^scoped_measurement_occurrence_schema_not_established$"):
        load_scoped_measurement_occurrence(reader, unsupported)
    assert to_canonical_bytes(load_scoped_measurement_occurrence(reader, ref)) == wire
