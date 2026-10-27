"""Behavioral controls for the selected HTE snapshot's shared owner row intake."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection,
    CanonicalAcquisitionObservation,
    ObservationProvenanceClass,
)
from polisyos.runtime.quality import generation_cycle as gc
from polisyos.runtime.quality.hte_source_projection import (
    HTESourceProjectionError,
    _profile_rows_from_projection,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def _selected_projection(
    units: Sequence[object],
    *,
    duplicate_cell: bool = False,
    mixed_datasets: bool = False,
) -> ActivatedAcquisitionObservationProjection:
    """Build typed candidate bytes; no active-owner issuance is claimed."""
    observations = [
        CanonicalAcquisitionObservation(
            observation_id=f"candidate-row-{index}",
            dataset_id="candidate-source-other" if mixed_datasets and index == 3 else "source",
            raw_variable="raw.outcome",
            canonical_var="outcome.effect",
            country_code="UA",
            year=1990 + index,
            value=float(index + 1),
            condition_json=json.dumps({"unit": unit}),
            acquisition_method="controlled_candidate_fixture",
            source_watermark="fixture:1",
            dataset_version="fixture:1",
            observation_class=ObservationProvenanceClass.OBSERVED,
        )
        for index, unit in enumerate(units)
    ]
    if duplicate_cell:
        observations.append(
            observations[0].model_copy(
                update={"observation_id": "candidate-row-same-cell", "value": 101.0}
            )
        )
    ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="epoch.acquisition_passport_snapshot",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "2" * 64,
    )
    return ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=ref.model_copy(update={"kind": "epoch.activated_overlay_admission"}),
        receipt_content_sha256="sha256:" + "3" * 64,
        passport_ref=ref,
        passport_content_sha256="sha256:" + "4" * 64,
        variable_id="outcome.effect",
        epoch_id=1,
        passport_id="candidate-passport",
        admission_content_sha256="sha256:" + "5" * 64,
        observations=observations,
    )


def _canonical_source_rows(
    projection: ActivatedAcquisitionObservationProjection,
) -> tuple[tuple[str, int, float, str, str, object], ...]:
    rows: list[tuple[str, int, float, str, str, object]] = []
    for selected in projection.observations:
        observation = selected.observation
        assert observation.year is not None
        rows.append(
            (
                observation.country_code,
                observation.year,
                observation.value,
                observation.dataset_id,
                observation.observation_id,
                observation.condition_json,
            )
        )
    return tuple(rows)


def test_hte_projection_reuses_declared_unit_normalization_and_owner_rows() -> None:
    """Whitespace in an explicit unit does not become a distinct invented unit."""
    projection = _selected_projection((" m ", "m", " m", "m "))
    canonical = gc._value_owner_rows_from_source_rows(
        outcome=projection.variable_id,
        raw_rows=_canonical_source_rows(projection),
        owner_access_ref="candidate:row-content-control",
        registered_measurement_units_by_id={},
    )
    assert canonical is not None
    canonical_rows, canonical_unit = canonical
    joined_rows = _profile_rows_from_projection(projection)
    assert joined_rows == canonical_rows
    assert canonical_unit == "m"
    assert tuple(row.measurement_unit for row in joined_rows) == ("m",) * 4
    assert tuple(row.outcome_value for row in joined_rows) == (1.0, 2.0, 3.0, 4.0)


@pytest.mark.parametrize(
    ("units", "duplicate_cell", "mixed_datasets", "reason"),
    [
        (("m",) * 4, True, False, "value_owner_unit_binding_ambiguous"),
        (("m", "cm", "m", "m"), False, False, "value_owner_measurement_unit_conflicting"),
        (("m", "", "m", "m"), False, False, "value_owner_measurement_unit_missing"),
        (("m", 5, "m", "m"), False, False, "value_owner_measurement_unit_wrong_unit_type"),
        (("m",) * 4, False, True, "value_owner_unit_binding_ambiguous"),
    ],
)
def test_hte_projection_preserves_canonical_owner_refusals_as_typed_join_limits(
    units: Sequence[object],
    duplicate_cell: bool,
    mixed_datasets: bool,
    reason: str,
) -> None:
    """Counterfeit source rows cannot become an averaged or unit-mixed profile."""
    projection = _selected_projection(
        units,
        duplicate_cell=duplicate_cell,
        mixed_datasets=mixed_datasets,
    )
    expected_code = f"acquire_data:{reason}"
    with pytest.raises(gc.ValueOwnerAccessError) as canonical:
        gc._value_owner_rows_from_source_rows(
            outcome=projection.variable_id,
            raw_rows=_canonical_source_rows(projection),
            owner_access_ref="candidate:row-content-control",
            registered_measurement_units_by_id={},
        )
    assert canonical.value.code == expected_code
    with pytest.raises(HTESourceProjectionError) as joined:
        _profile_rows_from_projection(projection)
    assert joined.value.reason_code == expected_code
