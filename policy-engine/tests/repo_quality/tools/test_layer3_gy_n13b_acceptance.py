from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from polisyos.core import artifacts
from tools.quality.validation import layer3_gy_n13b_acceptance as acceptance

_fixture_path = Path(__file__).with_name("_layer3_gy_n13b_acceptance_fixtures.py")
_fixture_spec = importlib.util.spec_from_file_location(
    "_layer3_gy_n13b_acceptance_fixtures",
    _fixture_path,
)
if _fixture_spec is None or _fixture_spec.loader is None:
    raise RuntimeError("layer3_gy_n13b_acceptance_fixture_module_unresolved")
_fixture_module = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_module)
_fixture_catalog = _fixture_module._fixture_catalog
_fixture_census = _fixture_module._fixture_census
_add_local_cpi = _fixture_module._add_local_cpi
_fixture_live_terminal = _fixture_module._fixture_live_terminal


def test_acceptance_selector_covers_both_denominators_and_derives_one_pair(
    tmp_path: Path,
) -> None:
    selection = acceptance.derive_acceptance_input_selection(
        catalog_path=_fixture_catalog(tmp_path / "catalog.duckdb"),
        census_path=_fixture_census(tmp_path / "census.json"),
        r1_paid_success_elapsed_seconds=6.945391583998571,
    )

    assert selection.all_local_series_group_count == 2
    assert selection.local_monetary_denominator_count == 2
    assert selection.eligible_local_nominal_count == 1
    assert selection.selected_nominal is not None
    assert selection.selected_nominal.dataset_id == "gdp-dataset"
    assert selection.selected_nominal_points[0].year == 2018
    assert selection.inflation_binding_denominator_count == 3
    assert selection.eligible_deflator_count == 1
    assert selection.selected_deflator is not None
    assert selection.selected_deflator.request_dataset_id == "FP.CPI.TOTL"
    assert selection.request_start_year == 2010
    assert selection.request_end_year == 2020
    assert selection.request_page_size == 11
    assert selection.derived_timeout_cap_seconds == 14.0
    assert selection.execution_selection is not None
    assert selection.execution_selection.live_family_denominator == (
        "new.connector",
        "worldbank.wdi",
    )
    new_family = next(
        row for row in selection.deflator_denominator if row.connector_id == "new.connector"
    )
    assert "executor_connector_unimplemented" in new_family.rejection_codes


def test_acceptance_selection_rejects_pinned_terminal_and_carrier_labels(
    tmp_path: Path,
) -> None:
    selection = acceptance.derive_acceptance_input_selection(
        catalog_path=_fixture_catalog(tmp_path / "catalog.duckdb"),
        census_path=_fixture_census(tmp_path / "census.json"),
        r1_paid_success_elapsed_seconds=6.945391583998571,
    )
    payload = selection.model_dump(mode="python")
    payload["disposition"] = "acceptance_inputs_inadmissible"
    with pytest.raises(ValueError, match="acceptance disposition"):
        acceptance.AcceptanceInputSelection.model_validate(payload)

    assert selection.selected_deflator is not None
    carrier = selection.selected_deflator.model_dump(mode="python")
    carrier["rejection_codes"] = ("archived_carrier",)
    carrier["eligible"] = False
    with pytest.raises(ValueError, match="rejection codes"):
        acceptance.DeflatorCarrierDisposition.model_validate(carrier)


def test_local_fallback_covers_every_role_series_and_defers_parameters_to_family(
    tmp_path: Path,
) -> None:
    catalog = _fixture_catalog(tmp_path / "catalog.duckdb")
    _add_local_cpi(catalog)
    selection = acceptance.derive_acceptance_input_selection(
        catalog_path=catalog,
        census_path=_fixture_census(tmp_path / "census.json"),
        r1_paid_success_elapsed_seconds=6.945391583998571,
    )
    fallback = acceptance.derive_acceptance_fallback_selection(
        input_selection=selection,
        live_execution=_fixture_live_terminal(
            selection, tmp_path / "acceptance-live-journal.jsonl"
        ),
        catalog_path=catalog,
    )

    assert fallback.all_local_series_group_count == 3
    assert fallback.local_index_denominator_count == 1
    assert fallback.eligible_local_deflator_count == 1
    assert fallback.selected_deflator is not None
    assert fallback.selected_deflator.raw_variable == "FP.CPI.TOTL"
    assert fallback.exact_overlap_years == (2018, 2019, 2020)
    assert fallback.recipe_base_year is None
    assert fallback.recipe_base_year_selection == "lower_median_common_year"

    pinned = fallback.model_dump(mode="python")
    pinned["recipe_base_year"] = 2018
    with pytest.raises(ValueError, match="resolved by the derivation owner"):
        acceptance.AcceptanceFallbackSelection.model_validate(pinned)


def test_acceptance_case_materializes_once_then_runs_two_cached_consumers(
    tmp_path: Path,
) -> None:
    catalog = _fixture_catalog(tmp_path / "catalog.duckdb")
    _add_local_cpi(catalog)
    selection = acceptance.derive_acceptance_input_selection(
        catalog_path=catalog,
        census_path=_fixture_census(tmp_path / "census.json"),
        r1_paid_success_elapsed_seconds=6.945391583998571,
    )
    fallback = acceptance.derive_acceptance_fallback_selection(
        input_selection=selection,
        live_execution=_fixture_live_terminal(
            selection, tmp_path / "acceptance-live-journal.jsonl"
        ),
        catalog_path=catalog,
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas")

    receipt = acceptance.materialize_acceptance_case(
        input_selection=selection,
        fallback_selection=fallback,
        store=store,
    )

    assert receipt.first_materialization_cache_hit is False
    assert receipt.second_materialization_cache_hit is True
    assert receipt.transform_family_id == "price_index_exact_year_rebase"
    assert {item.role for item in receipt.recipe.inputs} == {"amount", "index"}
    assert {item.name: item.value for item in receipt.recipe.parameters} == {"reference_year": 2019}
    assert receipt.recipe.output_basis.attribute("reference_year") == "2019"
    assert {item.name for item in receipt.recipe.assumptions} == {
        "formula",
        "index_choice_rule",
        "reference_year",
        "year_join",
    }
    assert receipt.certificate.observation_class == "derived"
    assert receipt.certificate.effective_authority <= min(
        item.effective_score for item in receipt.certificate.input_authorities
    )
    assert {row.consumer_method_id for row in receipt.consumers} == {
        "forecasting.univariate.exponential_smoothing@1.0.0",
        "forecasting.univariate.theta@1.0.0",
    }
    assert receipt.basis_mismatch_refusal_code == "basis_mismatch"
    assert receipt.basis_mismatch_refusal_reason == "no_certified_transform"
    assert receipt.model_output_observation_rejection_codes == ("model_output_not_observation",)
    acceptance.verify_persisted_acceptance_case(store, receipt)


def test_acceptance_metric_role_is_steered_by_owner_config_only(tmp_path: Path) -> None:
    catalog = _fixture_catalog(tmp_path / "catalog.duckdb")
    registry_text = acceptance.DEFAULT_DERIVATION_FAMILY_REGISTRY.read_text(encoding="utf-8")
    assert registry_text.count('owner_metric_id = "inflation"') == 1
    registry_path = tmp_path / "derivation_family_registry.toml"
    registry_path.write_text(
        registry_text.replace(
            'owner_metric_id = "inflation"',
            'owner_metric_id = "gdp"',
        ),
        encoding="utf-8",
    )

    selection = acceptance.derive_acceptance_input_selection(
        catalog_path=catalog,
        census_path=_fixture_census(tmp_path / "census.json"),
        r1_paid_success_elapsed_seconds=6.945391583998571,
        family_registry_path=registry_path,
    )

    assert {row.metric_id for row in selection.deflator_denominator} == {"gdp"}
    assert selection.eligible_deflator_count == 0
    assert selection.disposition == "acceptance_inputs_inadmissible"
