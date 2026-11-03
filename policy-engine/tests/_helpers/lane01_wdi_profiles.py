"""Finite WDI-shaped inputs for candidate-only acquisition integration tests.

The transport responses, catalog, trust owners, and values produced here are
test inputs.  Their source labels identify the connector contract; they do not
attest actual World Bank observations, rights, or currentness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb

from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionAuthorityEntry,
    CanonicalAcquisitionAuthority,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.ir.connectors import FetchRequest
from tests._helpers.acquisition_production import (
    _authority_family_receipt,
    _baseline,
    _entry,
    _raw_body,
    _sha,
    _write_family_receipt,
    _write_l5,
    _write_provision,
)


@dataclass(frozen=True, slots=True)
class CandidateWDIProfile:
    """Declare source semantics separately from any claim of observation authority."""

    construct: str
    indicator_id: str
    source_title: str
    source_description: str
    target_slot: str
    raw_unit: str
    canonical_unit: str
    transform: str
    transform_ref: str
    population: str
    fixture_value: float
    source_provenance_class: Literal["observed", "proxy", "derived", "model_output"]
    denominator: str | None = None
    quantity_kind: Literal["unconstrained", "share_of_denominator"] = "unconstrained"
    valid_min: float | None = None
    valid_max: float | None = None
    country_code: str = "USA"
    country_id: str = "US"
    year: int = 2024


GDP_PROFILE = CandidateWDIProfile(
    construct="economic.gdp",
    indicator_id="NY.GDP.MKTP.CD",
    source_title="GDP (current US$)",
    source_description="Nominal GDP for a country and calendar year, in current US dollars.",
    target_slot="global.gdp",
    raw_unit="usd",
    canonical_unit="usd",
    transform="identity",
    transform_ref="fabric://units/usd-identity/v1",
    population="national_economy",
    fixture_value=80.0,
    source_provenance_class="observed",
    valid_min=0.0,
)

UNEMPLOYMENT_PROFILE = CandidateWDIProfile(
    construct="labor.unemployment_rate",
    indicator_id="SL.UEM.TOTL.ZS",
    source_title="Unemployment, total (% of total labor force) (modeled ILO estimate)",
    source_description="Annual modeled unemployment share of the total labor force.",
    target_slot="global.unemployment_rate",
    raw_unit="percent",
    canonical_unit="ratio",
    transform="fixed_multiplicative",
    transform_ref="fabric://units/fixed-multiplicative/v1",
    population="total_labor_force",
    fixture_value=17.5,
    source_provenance_class="model_output",
    denominator="total_labor_force",
    quantity_kind="share_of_denominator",
    valid_min=0.0,
    valid_max=1.0,
)


def build_fixture_wdi_authority(
    repo_root: Path,
    profile: CandidateWDIProfile,
    *,
    attempt_id: str = "lane01-fixture-wdi-001",
) -> tuple[CanonicalAcquisitionAuthority, AcquisitionAuthorityEntry]:
    """Create a separate source-owned test catalog, provision, and real resolver.

    The test catalog's CC-BY fixture is supplied by the test owner and never
    establishes rights to an external data release. The response remains a
    generated fixture even though the existing WDI connector interprets it.
    """

    repo_root.mkdir(parents=True, exist_ok=True)
    baseline = _baseline(repo_root)
    l5_path = _write_l5(repo_root)
    source_id = "source-lane01-" + profile.target_slot.replace(".", "-")
    distribution_id = source_id + "-json"
    with duckdb.connect(str(baseline)) as con:
        con.execute(
            """INSERT INTO ds_datasets
            (id, source, agency, title, description, access_license,
             execution_tier, polisyos_metrics, preferred_distribution_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                source_id,
                "worldbank",
                "controlled test source",
                profile.source_title,
                profile.source_description,
                "CC-BY-4.0",
                "transport_ready",
                [profile.construct],
                distribution_id,
            ],
        )
        con.execute(
            """INSERT INTO ds_distributions
            (id, dataset_id, connector_type, profile_id, source_locator,
             parser_supported, machine_readable, quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                distribution_id,
                source_id,
                "worldbank.wdi",
                "worldbank_wdi",
                profile.indicator_id,
                True,
                True,
                0.9,
            ],
        )
        con.execute(
            """INSERT INTO ds_metric_bindings
            (metric_id, dataset_id, distribution_id, connector_id, profile_id,
             request_dataset_id, confidence, metric_inference_confidence,
             default_filters, execution_tier, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                profile.construct,
                source_id,
                distribution_id,
                "worldbank.wdi",
                "worldbank_wdi",
                profile.indicator_id,
                0.87,
                0.95,
                "{}",
                "transport_ready",
                "worldbank",
            ],
        )
        con.execute(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                source_id,
                profile.indicator_id,
                profile.construct,
                "semantic",
                0.85,
                "fixture-declared source quantity; no empirical attribution",
                False,
                0.0,
            ],
        )

    entry = build_authority_entry(
        source_lane="live_fetch",
        target_variable=profile.target_slot,
        landing_dataset_id="acquisition.lane01." + profile.target_slot,
        landing_distribution_id="acquisition.lane01." + profile.target_slot + ".json",
        source_catalog_dataset_id=source_id,
        source_catalog_distribution_id=distribution_id,
        upstream_metric_id=profile.construct,
        catalog_raw_variable=profile.indicator_id,
        raw_field="value",
        raw_unit=profile.raw_unit,
        canonical_unit=profile.canonical_unit,
        unit_transform=profile.transform,
        unit_transform_ref=profile.transform_ref,
        alignment_method="semantic",
        alignment_confidence=0.8,
        is_proxy=False,
        proxy_penalty=0.0,
        aggregation_method="identity",
        valid_min=profile.valid_min,
        valid_max=profile.valid_max,
        evidence_refs=(f"repo://catalog/catalog.duckdb#ds_variable_alignments/{source_id}",),
        schema_contract_ref="fabric://worldbank.wdi.generic@2.0.0",
        schema_columns=_entry().schema_columns,
        l5_family_id="macro_state",
        source_provenance_class=profile.source_provenance_class,
        source_measure_scope={
            "population": profile.population,
            "denominator": profile.denominator,
            "temporal_granularity": "annual",
            "quantity_kind": profile.quantity_kind,
        },
        title=profile.source_title,
        description=profile.source_description,
        country_codes=(profile.country_code,),
        temporal_start=str(profile.year),
        temporal_end=str(profile.year),
    )
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5_path),
        entries=(entry,),
    )
    registry_path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    family_receipt = _authority_family_receipt(attempt_id)
    carrier = family_receipt["dry_run_attempts"][0]
    carrier["request_dataset_id"] = profile.indicator_id
    carrier["fetch_request_key"] = FetchRequest(dataset_id=profile.indicator_id).request_key
    provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=attempt_id,
        receipt=family_receipt,
    )
    _write_provision(
        repo_root,
        baseline=baseline,
        l5_path=l5_path,
        baseline_owner_ref="repo://catalog/catalog.duckdb",
        live_harness_receipts=(provision,),
    )
    return (
        CanonicalAcquisitionAuthority.from_provision(repo_root=repo_root, baseline_path=baseline),
        entry,
    )


def fixture_wdi_response(profile: CandidateWDIProfile, *, value: float | None = None) -> bytes:
    """Return one generated WDI-shaped HTTP response for the declared period."""

    payload = json.loads(
        _raw_body(
            [
                {
                    "country_code": profile.country_code,
                    "country_name": "Controlled fixture country",
                    "indicator_id": profile.indicator_id,
                    "indicator_name": profile.source_title,
                    "year": profile.year,
                    "value": profile.fixture_value if value is None else value,
                    "unit": profile.raw_unit,
                    "decimal": 1,
                }
            ]
        )
    )
    payload[1][0]["country"]["id"] = profile.country_id
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
