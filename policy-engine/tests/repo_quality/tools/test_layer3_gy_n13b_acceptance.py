from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from tools.quality.validation import layer3_gy_n13b_acceptance as acceptance


def _fixture_catalog(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE ds_datasets (
          id VARCHAR, source VARCHAR, agency VARCHAR, title VARCHAR,
          description VARCHAR, access_license VARCHAR, license VARCHAR,
          access_auth_required BOOLEAN, temporal_start VARCHAR,
          temporal_end VARCHAR, themes VARCHAR[]
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ds_distributions (
          id VARCHAR, dataset_id VARCHAR, source_locator VARCHAR, url VARCHAR,
          parser_supported BOOLEAN, quality_score DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ds_metric_bindings (
          metric_id VARCHAR, dataset_id VARCHAR, distribution_id VARCHAR,
          connector_id VARCHAR, profile_id VARCHAR, request_dataset_id VARCHAR,
          confidence DOUBLE, execution_tier VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ds_variable_alignments (
          dataset_id VARCHAR, raw_variable VARCHAR, canonical_var VARCHAR,
          method VARCHAR, confidence DOUBLE, is_proxy BOOLEAN, proxy_penalty DOUBLE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ds_observations (
          observation_id VARCHAR, dataset_id VARCHAR, raw_variable VARCHAR,
          canonical_var VARCHAR, country_code VARCHAR, year INTEGER, value DOUBLE,
          source_watermark VARCHAR, dataset_version VARCHAR,
          acquisition_method VARCHAR
        )
        """
    )
    datasets = (
        (
            "gdp-dataset",
            "worldbank",
            "WB",
            "GDP (current US$)",
            "Gross domestic product in current United States dollars.",
            "CC-BY-4.0",
            None,
            False,
            "1960",
            "2025",
            ["World Development Indicators"],
        ),
        (
            "income-dataset",
            "worldbank",
            "WB",
            "Adjusted income per capita (current US$)",
            "Proxy income in current United States dollars.",
            "CC-BY-4.0",
            None,
            False,
            "1960",
            "2025",
            ["World Development Indicators"],
        ),
        (
            "cpi-dataset",
            "worldbank",
            "WB",
            "Consumer price index (2010 = 100)",
            "Index of consumer prices with a 2010 reference period.",
            "CC-BY-4.0",
            None,
            False,
            "1960",
            "2025",
            ["World Development Indicators"],
        ),
        (
            "archived-deflator",
            "worldbank",
            "WB",
            "Consumer price index (2000 = 100)",
            "Archived consumer price index.",
            "CC-BY-4.0",
            None,
            False,
            "1960",
            "2010",
            ["WDI Database Archives"],
        ),
        (
            "new-family-cpi",
            "new-source",
            "NEW",
            "Consumer price index (2015 = 100)",
            "Index of consumer prices.",
            "CC-BY-4.0",
            None,
            False,
            "1960",
            "2025",
            ["World Development Indicators"],
        ),
    )
    con.executemany("INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", datasets)
    distributions = (
        ("gdp-dist", "gdp-dataset", "fixture:gdp", "https://example/gdp", True, 1.0),
        ("income-dist", "income-dataset", "fixture:income", "https://example/income", True, 1.0),
        ("cpi-dist", "cpi-dataset", "fixture:cpi", "https://example/cpi", True, 1.0),
        (
            "archived-deflator-dist",
            "archived-deflator",
            "fixture:archive",
            "https://example/archive",
            True,
            1.0,
        ),
        (
            "new-family-cpi-dist",
            "new-family-cpi",
            "fixture:new",
            "https://example/new",
            True,
            1.0,
        ),
    )
    con.executemany("INSERT INTO ds_distributions VALUES (?, ?, ?, ?, ?, ?)", distributions)
    bindings = (
        (
            "gdp",
            "gdp-dataset",
            "gdp-dist",
            "worldbank.wdi",
            "worldbank_wdi",
            "NY.GDP.MKTP.CD",
            0.87,
            "transport_ready",
        ),
        (
            "avg_income",
            "income-dataset",
            "income-dist",
            "worldbank.wdi",
            "worldbank_wdi",
            "NY.ADJ.NNTY.PC.CD",
            0.87,
            "transport_ready",
        ),
        (
            "inflation",
            "cpi-dataset",
            "cpi-dist",
            "worldbank.wdi",
            "worldbank_wdi",
            "FP.CPI.TOTL",
            0.87,
            "transport_ready",
        ),
        (
            "inflation",
            "archived-deflator",
            "archived-deflator-dist",
            "worldbank.wdi",
            "worldbank_wdi",
            "FP.FPI.TOTL",
            0.87,
            "transport_ready",
        ),
        (
            "inflation",
            "new-family-cpi",
            "new-family-cpi-dist",
            "new.connector",
            "new_profile",
            "CPI",
            0.87,
            "transport_ready",
        ),
    )
    con.executemany("INSERT INTO ds_metric_bindings VALUES (?, ?, ?, ?, ?, ?, ?, ?)", bindings)
    con.executemany(
        "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            ("gdp-dataset", "NY.GDP.MKTP.CD", "gdp", "exact", 0.95, False, 0.0),
            (
                "income-dataset",
                "NY.ADJ.NNTY.PC.CD",
                "avg_income",
                "exact",
                0.9,
                True,
                0.1,
            ),
        ),
    )
    observations = []
    for year, value in ((2018, 100.0), (2019, 110.0), (2020, 120.0)):
        observations.extend(
            (
                (
                    f"gdp-{year}",
                    "gdp-dataset",
                    "NY.GDP.MKTP.CD",
                    "gdp",
                    "UA",
                    year,
                    value,
                    "fixture-watermark",
                    "fixture-version",
                    "fixture-loader",
                ),
                (
                    f"income-{year}",
                    "income-dataset",
                    "NY.ADJ.NNTY.PC.CD",
                    "avg_income",
                    "UA",
                    year,
                    value / 10,
                    "fixture-watermark",
                    "fixture-version",
                    "fixture-loader",
                ),
            )
        )
    con.executemany(
        "INSERT INTO ds_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", observations
    )
    con.close()
    return path


def _fixture_census(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "family_scorecards": [
                    {
                        "connector_id": "worldbank.wdi",
                        "family_liveness_state": "live_characterized",
                        "dry_run_passed": True,
                        "liveness_counts": {"alive_schema_unverified": 1},
                    },
                    {
                        "connector_id": "new.connector",
                        "family_liveness_state": "live_characterized",
                        "dry_run_passed": True,
                        "liveness_counts": {"alive_schema_unverified": 1},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


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
