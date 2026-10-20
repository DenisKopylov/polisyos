"""Behavioral checks for canonical source-to-forecast profile binding."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.contracts import ForecastProfileMemberV1
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection,
    CanonicalAcquisitionObservation,
    ObservationProvenanceClass,
)
from polisyos.ir import ArtifactRefModel
from polisyos.runtime.quality.forecast_profile_binding import (
    join_profile_member_to_observed_series,
    validate_profile_projection_binding,
)
from polisyos.runtime.quality.generation_cycle import (
    ValueDataProfile,
    ValueOwnerRow,
    _derived_value_data_modalities,
    _value_owner_row,
    gy_content_hash,
)


def _observation(
    *,
    observation_id: str,
    dataset_id: str,
    unit_id: str = "UA",
    period_id: int,
    value: float,
) -> CanonicalAcquisitionObservation:
    return CanonicalAcquisitionObservation(
        observation_id=observation_id,
        dataset_id=dataset_id,
        raw_variable="metric",
        canonical_var="metric",
        country_code=unit_id,
        year=period_id,
        value=value,
        condition_json='{"unit":"USD"}',
        acquisition_method="controlled_fixture",
        source_watermark="controlled_fixture",
        dataset_version="fixture-v1",
        observation_class=ObservationProvenanceClass.OBSERVED,
    )


def _projection(
    observations: tuple[CanonicalAcquisitionObservation, ...],
) -> ActivatedAcquisitionObservationProjection:
    return ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=CoreArtifactRef(
            artifact_id=ArtifactID("sha256:" + "1" * 64),
            kind="epoch.activated_overlay_admission_receipt",
            media_type="application/json",
        ),
        receipt_content_sha256="sha256:" + "2" * 64,
        passport_ref=CoreArtifactRef(
            artifact_id=ArtifactID("sha256:" + "3" * 64),
            kind="epoch.acquisition_passport_snapshot",
            media_type="application/json",
        ),
        passport_content_sha256="sha256:" + "4" * 64,
        variable_id="metric",
        epoch_id=1,
        passport_id="controlled-candidate-passport",
        admission_content_sha256="sha256:" + "5" * 64,
        observations=observations,
    )


def _profile(
    observations: tuple[CanonicalAcquisitionObservation, ...],
    *,
    unit_id: str = "UA",
) -> ValueDataProfile:
    by_period: dict[int, list[tuple[float, str, str, str]]] = {}
    for observation in observations:
        assert observation.year is not None
        by_period.setdefault(observation.year, []).append(
            (
                observation.value,
                observation.dataset_id,
                observation.observation_id,
                "USD",
            )
        )
    rows = tuple(
        _value_owner_row(
            outcome="metric",
            unit_id=unit_id,
            period_id=period_id,
            source_rows=tuple(by_period[period_id]),
        )
        for period_id in sorted(by_period)
    )
    assert len(rows) >= 4
    return _profile_from_rows(rows)


def _profile_from_rows(rows: tuple[ValueOwnerRow, ...]) -> ValueDataProfile:
    rows_payload = tuple(row.model_dump(mode="json") for row in rows)
    payload = {
        "schema_version": "policyos.runtime.value_data_profile.v2",
        "outcome": "metric",
        "measurement_unit": "USD",
        "rows": rows_payload,
        "owner_row_count": len(rows),
        "unit_count": len({row.unit_id for row in rows}),
        "period_count": len({row.period_id for row in rows}),
        "available_data_modalities": _derived_value_data_modalities(rows),
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": "controlled://candidate-only-profile-fixture",
        "owner_rows_content_hash": gy_content_hash(rows_payload),
    }
    return ValueDataProfile.model_validate({**payload, "content_hash": gy_content_hash(payload)})


def _observations() -> tuple[CanonicalAcquisitionObservation, ...]:
    return tuple(
        _observation(
            observation_id=f"obs-{period_id}-{source_index}",
            dataset_id=f"dataset-{source_index}",
            period_id=period_id,
            value=float(period_id + (1 if source_index == 0 else 3)),
        )
        for period_id in range(4)
        for source_index in range(2)
    )


def _ref(artifact_id: str, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=f"sha256:{artifact_id * 64}",
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )


def test_canonical_aggregated_profile_binds_full_multirow_projection() -> None:
    observations = _observations()
    projection = _projection(observations)
    profile = _profile(observations)

    selected = validate_profile_projection_binding(
        profile=profile,
        projection_payload=projection.model_dump(mode="json"),
    )
    receipt, joined_values = join_profile_member_to_observed_series(
        profile=profile,
        profile_ref=_ref("1", "runtime.value_data_profile"),
        source_projection_ref=_ref("2", "runtime.value_owner_source_projection"),
        projection=selected,
        observed_source_ref=_ref("3", "fabric.data_snapshot"),
        observed_data_ref=_ref("4", "test.observed_data"),
        target_metric="metric",
        unit_id="UA",
        observed_values=[float(period_id + 2) for period_id in range(4)],
    )

    assert len(profile.rows[0].source_row_content_hashes) == 2
    assert profile.rows[0].outcome_value == pytest.approx(2.0)
    assert joined_values == (2.0, 3.0, 4.0, 5.0)
    assert receipt.source_projection_ref.kind == "runtime.value_owner_source_projection"
    assert receipt.source_projection_content_sha256 == projection.projection_content_sha256
    assert receipt.row_count == 4
    assert receipt.authority_scope == "predictive_only"
    assert receipt.source_relation_status == "not_established"
    assert ForecastProfileMemberV1.model_validate(receipt.model_dump(mode="json")) == receipt
    malformed_count = receipt.model_dump(mode="json")
    malformed_count["row_count"] = True
    with pytest.raises(ValueError, match="row_count"):
        ForecastProfileMemberV1.model_validate(malformed_count)


def test_projection_order_is_normalized_but_profile_hash_tuple_order_is_not() -> None:
    observations = _observations()
    profile = _profile(observations)
    reversed_projection = _projection(tuple(reversed(observations)))

    validate_profile_projection_binding(
        profile=profile,
        projection_payload=reversed_projection.model_dump(mode="json"),
    )

    original_row = profile.rows[0]
    reversed_hashes = tuple(reversed(original_row.source_row_content_hashes))
    row_payload = original_row.model_dump(mode="json")
    row_payload["source_row_content_hashes"] = reversed_hashes
    row_payload.pop("row_content_hash")
    forged_row = ValueOwnerRow(
        **row_payload,
        row_content_hash=gy_content_hash(row_payload),
    )
    rows = (forged_row, *profile.rows[1:])
    forged_profile = _profile_from_rows(rows)

    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=forged_profile,
            projection_payload=_projection(observations).model_dump(mode="json"),
        )


def test_binding_refuses_removed_altered_and_foreign_source_rows() -> None:
    observations = _observations()
    profile = _profile(observations)

    removed_projection = _projection(observations[1:])
    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=profile,
            projection_payload=removed_projection.model_dump(mode="json"),
        )

    altered = (
        _observation(
            observation_id="obs-0-0",
            dataset_id="dataset-0",
            period_id=0,
            value=99.0,
        ),
        *observations[1:],
    )
    altered_projection = _projection(tuple(altered))
    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=profile,
            projection_payload=altered_projection.model_dump(mode="json"),
        )

    foreign_rows = tuple(
        _observation(
            observation_id=f"foreign-{period_id}-{source_index}",
            dataset_id=f"foreign-dataset-{source_index}",
            unit_id="PL",
            period_id=period_id,
            value=float(period_id + (1 if source_index == 0 else 3)),
        )
        for period_id in range(4)
        for source_index in range(2)
    )
    foreign_profile = _profile(foreign_rows, unit_id="UA")
    with pytest.raises(ValueError, match="source_row_binding_mismatch"):
        validate_profile_projection_binding(
            profile=foreign_profile,
            projection_payload=_projection(foreign_rows).model_dump(mode="json"),
        )


def test_runtime_intake_enforces_canonical_single_row_single_dataset_shape() -> None:
    observations = _observations()
    profile = _profile(observations)
    projection = _projection(observations)

    # The generic tuple primitive remains useful for candidate-only math and
    # still recomputes a valid multirow aggregate.
    validate_profile_projection_binding(
        profile=profile,
        projection_payload=projection.model_dump(mode="json"),
    )

    # Runtime's actual EMP-01 producer refuses every duplicate unit-period,
    # even when the submitted aggregate is content-consistent.
    with pytest.raises(ValueError, match="source_row_binding_ambiguous"):
        validate_profile_projection_binding(
            profile=profile,
            projection_payload=projection.model_dump(mode="json"),
            require_canonical_owner_profile_shape=True,
        )

    single_row_periods = tuple(
        _observation(
            observation_id=f"single-{period_id}",
            dataset_id="one-owner-dataset",
            period_id=period_id,
            value=float(period_id),
        )
        for period_id in range(4)
    )
    valid_single_dataset_profile = _profile(single_row_periods)
    validate_profile_projection_binding(
        profile=valid_single_dataset_profile,
        projection_payload=_projection(single_row_periods).model_dump(mode="json"),
        require_canonical_owner_profile_shape=True,
    )

    split_dataset_periods = tuple(
        _observation(
            observation_id=f"split-{period_id}",
            dataset_id=("dataset-a" if period_id < 2 else "dataset-b"),
            period_id=period_id,
            value=float(period_id),
        )
        for period_id in range(4)
    )
    split_dataset_profile = _profile(split_dataset_periods)

    # Without the Runtime producer contract this remains a deterministic
    # candidate tuple; at the served intake the loader's dataset rule applies.
    validate_profile_projection_binding(
        profile=split_dataset_profile,
        projection_payload=_projection(split_dataset_periods).model_dump(mode="json"),
    )
    with pytest.raises(ValueError, match="source_dataset_ambiguous"):
        validate_profile_projection_binding(
            profile=split_dataset_profile,
            projection_payload=_projection(split_dataset_periods).model_dump(mode="json"),
            require_canonical_owner_profile_shape=True,
        )
