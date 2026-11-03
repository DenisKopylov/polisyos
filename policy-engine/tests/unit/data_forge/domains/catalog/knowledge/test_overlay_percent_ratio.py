"""Percent scaling preserves observations without asserting measurement authority."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.catalog.knowledge import overlay


def _binding(*, raw_unit: str = "percent", canonical_unit: str = "ratio"):
    return overlay.build_metric_field_binding(
        dataset_id="test.unemployment",
        distribution_id="test.unemployment.json",
        raw_field="value",
        canonical_variable="global.unemployment_rate",
        raw_unit=raw_unit,
        canonical_unit=canonical_unit,
        unit_transform="fixed_multiplicative",
        unit_transform_ref="fabric://units/fixed-multiplicative/v1",
        alignment_method="semantic",
        alignment_confidence=0.8,
        is_proxy=False,
        proxy_penalty=0.0,
        evidence_refs=("repo://test/declared-unemployment-measurement",),
        valid_min=0.0,
        valid_max=1.0,
    )


def _derive(binding: object, value: float, *, raw_unit: str = "percent"):
    body = json.dumps(
        [
            {
                "value": value,
                "country_code": "USA",
                "year": 2024,
                "condition_json": {
                    "unit": raw_unit,
                    "numerator": "unemployed_persons",
                    "denominator": "total_labor_force",
                    "time_role": "annual_estimate",
                },
            }
        ]
    ).encode()
    return overlay.derive_canonical_observations(
        body,
        passport=SimpleNamespace(
            epoch_id=1,
            source_watermark="sha256:" + "1" * 64,
            dataset_version="test-only",
            observation_class=overlay.ObservationProvenanceClass.OBSERVED,
        ),
        registration=SimpleNamespace(catalog_dataset_id="test.unemployment", field_binding=binding),
    )


@pytest.mark.parametrize(("source", "expected"), [(0.0, 0.0), (17.5, 0.175), (100.0, 1.0)])
def test_percent_to_ratio_keeps_scoped_observation(source: float, expected: float) -> None:
    (row,) = _derive(_binding(), source)
    assert row.value == pytest.approx(expected)
    assert (row.country_code, row.year) == ("USA", 2024)
    assert json.loads(row.condition_json) == {
        "unit": "ratio",
        "numerator": "unemployed_persons",
        "denominator": "total_labor_force",
        "time_role": "annual_estimate",
    }
    assert row.unit_transform_evidence is not None
    assert row.unit_transform_evidence.multiplier == "0.01"


@pytest.mark.parametrize("source", [-0.1, 100.1])
def test_profile_bounds_reject_invalid_unemployment_percent(source: float) -> None:
    with pytest.raises(overlay.OverlayAdmissionError, match=r"observation_.*_valid_range"):
        _derive(_binding(), source)


def test_other_dimensionless_conversions_and_wrong_raw_unit_remain_rejected() -> None:
    with pytest.raises(overlay.OverlayAdmissionError, match="dimensionless_not_admissible"):
        _derive(_binding(raw_unit="index"), 17.5, raw_unit="index")
    with pytest.raises(overlay.OverlayAdmissionError, match="raw_condition_unit_binding_mismatch"):
        _derive(_binding(), 17.5, raw_unit="index")
