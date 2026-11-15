"""Finite WDI-shaped inputs for candidate-only acquisition integration tests.

The transport responses, catalog, trust owners, and values produced here are
test inputs.  Their source labels identify the connector contract; they do not
attest actual World Bank observations, rights, or currentness.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb

from polisyos.core.artifacts import ArtifactRef
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
    catalog_metric_id: str | None = None
    index_base_year: int | None = None


@dataclass(frozen=True, slots=True)
class FixtureWDIRegisteredSourceSemantics:
    """Carry exact test-selected source semantics into one fixture authority entry.

    These refs and scope are external fixture inputs. Their presence declares
    neither empirical truth nor a provider right, currentness, price, or claim.
    """

    source_semantic_definition_ref: ArtifactRef
    source_representation_ref: ArtifactRef
    source_measure_scope: Mapping[str, object] | None
    country_codes: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class FixtureWDIRoleBinding:
    """Bind one explicit profile target slot to its fixture attempt receipts."""

    attempt_ids: tuple[str, ...]
    registered_source_semantics: FixtureWDIRegisteredSourceSemantics | None = None


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
    catalog_metric_id="gdp",
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

CPI_PROFILE = CandidateWDIProfile(
    construct="economic.consumer_price_index",
    indicator_id="FP.CPI.TOTL",
    source_title="Consumer price index (2010 = 100)",
    source_description=(
        "Annual consumer price index level expressed on a 2010=100 base; distinct from the "
        "annual percentage-change indicator FP.CPI.TOTL.ZG."
    ),
    target_slot="global.consumer_price_index",
    raw_unit="index",
    canonical_unit="index",
    transform="identity",
    transform_ref="fabric://units/index-identity/v1",
    population="national_economy",
    fixture_value=457.090971982012,
    source_provenance_class="observed",
    valid_min=0.0,
    country_code="UKR",
    country_id="UA",
    year=2024,
    catalog_metric_id="consumer_price_index",
    index_base_year=2010,
)


def build_fixture_wdi_authority(
    repo_root: Path,
    profile: CandidateWDIProfile,
    *,
    attempt_id: str = "lane01-fixture-wdi-001",
    subsequent_attempt_ids: tuple[str, ...] = (),
) -> tuple[CanonicalAcquisitionAuthority, AcquisitionAuthorityEntry]:
    """Create one fixture WDI entry and resolver using the shared bundle builder."""
    authority, entries = build_fixture_wdi_authority_bundle(
        repo_root,
        (profile,),
        role_bindings={
            profile.target_slot: FixtureWDIRoleBinding(
                attempt_ids=(attempt_id, *subsequent_attempt_ids)
            )
        },
    )
    (entry,) = entries
    return authority, entry


def build_fixture_wdi_authority_bundle(
    repo_root: Path,
    profiles: tuple[CandidateWDIProfile, ...],
    *,
    role_bindings: Mapping[str, FixtureWDIRoleBinding],
    baseline_path: Path | None = None,
) -> tuple[CanonicalAcquisitionAuthority, tuple[AcquisitionAuthorityEntry, ...]]:
    """Build ordered fixture entries over one baseline, provision and resolver.

    ``role_bindings`` is keyed by each explicit profile ``target_slot``. Its
    attempt IDs create fixture receipts, while optional registered semantics
    are passed through exactly from the caller's selected test profile. They
    do not assert source truth, rights, currentness, price, or claim authority.
    When ``baseline_path`` is supplied, this builder adds rows to that existing
    controlled database in place; it never creates a copy or replacement.
    """
    if type(profiles) is not tuple or not profiles:
        raise ValueError("candidate_wdi_profiles_required")
    if any(type(profile) is not CandidateWDIProfile for profile in profiles):
        raise TypeError("candidate_wdi_profile_untyped")
    roles = tuple(profile.target_slot for profile in profiles)
    if len(set(roles)) != len(roles):
        raise ValueError("candidate_wdi_profile_target_slot_duplicate")
    if not isinstance(role_bindings, Mapping) or set(role_bindings) != set(roles):
        raise ValueError("candidate_wdi_role_binding_scope_mismatch")
    selected_bindings: dict[str, FixtureWDIRoleBinding] = {}
    all_attempt_ids: list[str] = []
    for profile in profiles:
        binding = role_bindings[profile.target_slot]
        if type(binding) is not FixtureWDIRoleBinding:
            raise TypeError("candidate_wdi_role_binding_untyped")
        if (
            type(binding.attempt_ids) is not tuple
            or not binding.attempt_ids
            or any(
                type(attempt_id) is not str
                or len(attempt_id) < 2
                or not attempt_id.strip()
                or attempt_id != attempt_id.strip()
                for attempt_id in binding.attempt_ids
            )
        ):
            raise ValueError("candidate_wdi_role_attempt_ids_invalid")
        semantics = binding.registered_source_semantics
        if semantics is not None and type(semantics) is not FixtureWDIRegisteredSourceSemantics:
            raise TypeError("candidate_wdi_registered_source_semantics_untyped")
        selected_bindings[profile.target_slot] = binding
        all_attempt_ids.extend(binding.attempt_ids)
    if len(set(all_attempt_ids)) != len(all_attempt_ids):
        raise ValueError("candidate_wdi_attempt_id_duplicate")

    repo_root.mkdir(parents=True, exist_ok=True)
    if baseline_path is None:
        baseline = _baseline(repo_root)
        baseline_owner_ref = "repo://catalog/catalog.duckdb"
    else:
        supplied_baseline = Path(baseline_path)
        if not supplied_baseline.is_absolute():
            supplied_baseline = repo_root / supplied_baseline
        try:
            baseline = supplied_baseline.resolve(strict=True)
            relative_baseline = baseline.relative_to(repo_root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise ValueError("candidate_wdi_baseline_must_be_existing_repo_file") from exc
        if not baseline.is_file():
            raise ValueError("candidate_wdi_baseline_must_be_existing_repo_file")
        baseline_owner_ref = "repo://" + relative_baseline.as_posix()
    l5_path = _write_l5(repo_root)

    entry_facts: list[tuple[CandidateWDIProfile, str, str, str]] = []
    with duckdb.connect(str(baseline)) as con:
        if baseline_path is not None:
            from polisyos.data_forge.domains.catalog.batch import graph_builder

            graph_builder._init_schema(con)
        for profile in profiles:
            catalog_metric_id = (
                profile.construct
                if profile.catalog_metric_id is None
                else profile.catalog_metric_id
            )
            if not isinstance(catalog_metric_id, str) or not catalog_metric_id.strip():
                raise ValueError("candidate_wdi_catalog_metric_id_missing")
            source_id = "source-lane01-" + profile.target_slot.replace(".", "-")
            distribution_id = source_id + "-json"
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
                    [catalog_metric_id],
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
                    catalog_metric_id,
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
                    catalog_metric_id,
                    "semantic",
                    0.85,
                    "fixture-declared source quantity; no empirical attribution",
                    False,
                    0.0,
                ],
            )
            entry_facts.append((profile, catalog_metric_id, source_id, distribution_id))

    entries: list[AcquisitionAuthorityEntry] = []
    for profile, catalog_metric_id, source_id, distribution_id in entry_facts:
        entry_values: dict[str, object] = {
            "source_lane": "live_fetch",
            "target_variable": profile.target_slot,
            "landing_dataset_id": "acquisition.lane01." + profile.target_slot,
            "landing_distribution_id": "acquisition.lane01." + profile.target_slot + ".json",
            "source_catalog_dataset_id": source_id,
            "source_catalog_distribution_id": distribution_id,
            "upstream_metric_id": catalog_metric_id,
            "catalog_raw_variable": profile.indicator_id,
            "raw_field": "value",
            "raw_unit": profile.raw_unit,
            "canonical_unit": profile.canonical_unit,
            "unit_transform": profile.transform,
            "unit_transform_ref": profile.transform_ref,
            "alignment_method": "semantic",
            "alignment_confidence": 0.8,
            "is_proxy": False,
            "proxy_penalty": 0.0,
            "aggregation_method": "identity",
            "valid_min": profile.valid_min,
            "valid_max": profile.valid_max,
            "evidence_refs": (f"{baseline_owner_ref}#ds_variable_alignments/{source_id}",),
            "schema_contract_ref": "fabric://worldbank.wdi.generic@2.0.0",
            "schema_columns": _entry().schema_columns,
            "l5_family_id": "macro_state",
            "source_provenance_class": profile.source_provenance_class,
            "source_measure_scope": {
                "population": profile.population,
                "denominator": profile.denominator,
                "temporal_granularity": "annual",
                "quantity_kind": profile.quantity_kind,
            },
            "title": profile.source_title,
            "description": profile.source_description,
            "country_codes": (profile.country_code,),
            "temporal_start": str(profile.year),
            "temporal_end": str(profile.year),
        }
        registered = selected_bindings[profile.target_slot].registered_source_semantics
        if registered is not None:
            if (
                not isinstance(registered.source_semantic_definition_ref, ArtifactRef)
                or registered.source_semantic_definition_ref.manifest_profile_sha256 is None
                or not isinstance(registered.source_representation_ref, ArtifactRef)
                or registered.source_representation_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("candidate_wdi_registered_source_refs_unselected")
            entry_values.update(
                source_semantic_definition_ref=registered.source_semantic_definition_ref,
                source_representation_ref=registered.source_representation_ref,
                source_measure_scope=registered.source_measure_scope,
            )
            if registered.country_codes is not None:
                entry_values["country_codes"] = registered.country_codes
        entries.append(build_authority_entry(**entry_values))
    ordered_entries = tuple(entries)
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5_path),
        entries=ordered_entries,
    )
    registry_path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    provisions = []
    receipt_index = 0
    for profile in profiles:
        entry = ordered_entries[roles.index(profile.target_slot)]
        binding = selected_bindings[profile.target_slot]
        for selected_attempt_id in binding.attempt_ids:
            family_receipt = _authority_family_receipt(selected_attempt_id)
            carrier = family_receipt["dry_run_attempts"][0]
            carrier["request_dataset_id"] = profile.indicator_id
            carrier["fetch_request_key"] = FetchRequest(dataset_id=profile.indicator_id).request_key
            receipt_path = "evidence/worldbank-wdi-live-harness.json"
            if receipt_index:
                receipt_path = f"evidence/worldbank-wdi-live-harness-{receipt_index}.json"
            provisions.append(
                _write_family_receipt(
                    repo_root,
                    entry_id=entry.entry_id,
                    attempt_id=selected_attempt_id,
                    receipt=family_receipt,
                    receipt_path=receipt_path,
                )
            )
            receipt_index += 1
    provisions.sort(key=lambda row: (row["entry_id"], row["attempt_id"]))
    _write_provision(
        repo_root,
        baseline=baseline,
        l5_path=l5_path,
        baseline_owner_ref=baseline_owner_ref,
        live_harness_receipts=tuple(provisions),
    )
    return (
        CanonicalAcquisitionAuthority.from_provision(repo_root=repo_root, baseline_path=baseline),
        ordered_entries,
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
