"""Compact public World Bank input for a generic annual GDP candidate check.

The bytes below are a bounded response captured from the public World Bank API.
They provide candidate-only software input; they do not establish source rights,
currentness, causal validity, or production authority. The provider-reported
``lastupdated`` value is retained as source metadata and is not a freshness claim.

The canonical binding already maps ``economic.gdp`` to ``global.gdp`` with USD
units and annual source time. This fixture uses the selected model period as one
year and keeps the source values in USD with an identity transform. It contains
no quarterly projection or annual-to-quarter conversion.

The captured API rows have an empty ``unit`` field. The fixture's USD unit
assignment follows the indicator label and canonical capability binding rather
than copying that empty field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final

SOURCE_ENDPOINT: Final = "https://api.worldbank.org/v2/country/USA/indicator/NY.GDP.MKTP.CD"
SOURCE_QUERY: Final = "date=2023:2024&format=json&per_page=2"
SOURCE_RESPONSE_BYTES: Final[bytes] = (
    b'[{"page":1,"pages":1,"per_page":2,"total":2,"sourceid":"2",'
    b'"lastupdated":"2026-10-08"},[{"indicator":{"id":"NY.GDP.MKTP.CD",'
    b'"value":"GDP (current US$)"},"country":{"id":"US",'
    b'"value":"United States"},"countryiso3code":"USA","date":"2024",'
    b'"value":29298013000000,"unit":"","obs_status":"","decimal":0},'
    b'{"indicator":{"id":"NY.GDP.MKTP.CD","value":"GDP (current US$)"},'
    b'"country":{"id":"US","value":"United States"},"countryiso3code":"USA",'
    b'"date":"2023","value":27811517000000,"unit":"","obs_status":"",'
    b'"decimal":0}]]'
)

CONNECTOR_ID: Final = "worldbank.wdi"
PROFILE_ID: Final = "worldbank_wdi"
SOURCE_CONTRACT_ID: Final = "worldbank.wdi.generic"
DATASET_ID: Final = "NY.GDP.MKTP.CD"
CONSTRUCT_ID: Final = "economic.gdp"
TARGET_WORLD_SLOT: Final = "global.gdp"
CANONICAL_UNIT_ID: Final = "usd"
TEMPORAL_GRANULARITY: Final = "annual"
UNIT_TRANSFORM: Final = "identity"
UNIT_ASSIGNMENT_BASIS: Final = (
    "GDP (current US$) indicator label plus the canonical annual WDI capability binding; "
    "the upstream API row unit field is blank"
)
SOFTWARE_FIXTURE_BOUNDARY: Final[dict[str, object]] = {
    "status": "candidate_unverified",
    "authoritative_for": [],
    "may_not_use_for": [
        "claim_evidence_closeout",
        "production_claim_evidence",
        "source_currentness",
        "causal_validity",
    ],
    "source_release": "not_established",
    "source_rights": "not_established",
    "source_currentness": "not_established",
    "claim_evidence_use_allowed": False,
}

SOURCE_CONTRACT_PATH: Final = (
    "src/polisyos/fabric/connectors/sources/_contracts/world_bank_contracts.py"
)
CAPABILITY_BINDING_PATH: Final = (
    "architecture/policy_design_case/layer2_s3_governed_capability_rows.json"
)
TARGET_SLOT_PATH: Final = "src/polisyos/ir/kernel/slots.py"
TIME_SEMANTICS_PATH: Final = "src/polisyos/ir/kernel/time_semantics.py"

# These are compiler/model inputs for the generic annual route, not an E02 case id.
COMPILER_SCOPE_INPUT: Final[dict[str, object]] = {
    "profile_id": "scope:usa-economic-gdp-2023-2024:v1",
    "jurisdiction": "USA",
    "population": "national_economy",
    "entity_scope": "country",
    "time_window": {"start": "2023-01-01", "end": "2024-12-31"},
    "time_role": "observation_time",
    "granularity": "annual",
    "required_constructs": [CONSTRUCT_ID],
}
MODEL_TIME_INPUT: Final[dict[str, object]] = {
    "frequency": "Y",
    "start_date": "2023-01-01",
    "step_count": 2,
}
GENERIC_WDI_PAGE_SIZE: Final = 1000

EXPECTED_2023_TO_2024_CHANGE_USD: Final = 1_486_496_000_000


@dataclass(frozen=True, slots=True)
class WdiAnnualObservation:
    """One annual nominal GDP observation from the preserved API response."""

    country_code: str
    indicator_id: str
    indicator_label: str
    year: int
    value_usd: int
    raw_unit_field: str


def load_wdi_observations() -> tuple[WdiAnnualObservation, ...]:
    """Parse the preserved response without importing PolicyOS runtime code."""
    envelope = json.loads(SOURCE_RESPONSE_BYTES)
    if not isinstance(envelope, list) or len(envelope) != 2:
        raise ValueError("world_bank_response_shape_invalid")
    rows = envelope[1]
    if not isinstance(rows, list):
        raise ValueError("world_bank_response_rows_invalid")

    observations: list[WdiAnnualObservation] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("world_bank_response_row_invalid")
        indicator = row.get("indicator")
        if not isinstance(indicator, dict):
            raise ValueError("world_bank_response_indicator_invalid")
        value = row.get("value")
        if type(value) is not int:
            raise ValueError("world_bank_response_value_invalid")
        observations.append(
            WdiAnnualObservation(
                country_code=str(row["countryiso3code"]),
                indicator_id=str(indicator["id"]),
                indicator_label=str(indicator["value"]),
                year=int(row["date"]),
                value_usd=value,
                raw_unit_field=str(row["unit"]),
            )
        )
    return tuple(observations)


def wdi_response_for_year(year: int, *, page_size: int = GENERIC_WDI_PAGE_SIZE) -> bytes:
    """Project one captured annual row into the connector's one-year response shape.

    The returned bytes are derived from the preserved two-year public response;
    they are test input for the generic connector and do not imply a fresh fetch.
    """
    if type(year) is not int:
        raise TypeError("world_bank_year_must_be_int")
    if type(page_size) is not int or page_size < 1:
        raise ValueError("world_bank_page_size_invalid")
    envelope = json.loads(SOURCE_RESPONSE_BYTES)
    if not isinstance(envelope, list) or len(envelope) != 2:
        raise ValueError("world_bank_response_shape_invalid")
    metadata, rows = envelope
    if not isinstance(metadata, dict) or not isinstance(rows, list):
        raise ValueError("world_bank_response_shape_invalid")
    matches = [row for row in rows if isinstance(row, dict) and str(row.get("date")) == str(year)]
    if len(matches) != 1:
        raise ValueError("world_bank_year_not_unique_in_capture")
    one_year_metadata = {
        **metadata,
        "page": 1,
        "pages": 1,
        "per_page": page_size,
        "total": 1,
    }
    return json.dumps(
        [one_year_metadata, matches],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def observed_annual_change_usd() -> int:
    """Return the observed 2023-to-2024 change in nominal annual GDP, in USD."""
    values = {observation.year: observation.value_usd for observation in load_wdi_observations()}
    return values[2024] - values[2023]
