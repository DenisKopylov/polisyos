from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    DEFAULT_L5_MEASUREMENT_REGISTRY,
    AcquisitionAuthorityEntry,
    AcquisitionAuthorityError,
    AuthoritySchemaColumn,
    CanonicalAcquisitionAuthority,
    LicenseDisposition,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_l5(repo_root: Path) -> Path:
    path = repo_root / DEFAULT_L5_MEASUREMENT_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "coverage_rules": {"macro_state": 0.95},
                "proxy_mappings": {},
                "trust_tiers": {
                    "authoritative_high_coverage": {
                        "tier": "authoritative_high_coverage",
                        "min_coverage": 0.85,
                        "max_coverage": 1.0,
                        "trust_cap": 1.0,
                        "trust_multiplier": 1.0,
                    },
                    "administrative_noisy": {
                        "tier": "administrative_noisy",
                        "min_coverage": 0.0,
                        "max_coverage": 1.0,
                        "trust_cap": 0.7,
                        "trust_multiplier": 0.85,
                    },
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _baseline(repo_root: Path, *, license_id: str = "CC-BY-4.0") -> Path:
    root = repo_root / "catalog"
    graph = build_slice0_fixture_catalog_graph(root)
    graph.close()
    path = root / "catalog.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            INSERT INTO ds_datasets (
                id, source, agency, title, description, access_license,
                execution_tier, polisyos_metrics, preferred_distribution_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance",
                "worldbank",
                "World Bank",
                "Cash surplus/deficit (% of GDP)",
                "Government cash balance as a share of GDP.",
                license_id,
                "transport_ready",
                ["gov_balance"],
                "source-worldbank-balance-json",
            ],
        )
        con.execute(
            """
            INSERT INTO ds_distributions (
                id, dataset_id, connector_type, profile_id, source_locator,
                parser_supported, machine_readable, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance-json",
                "source-worldbank-balance",
                "worldbank.wdi",
                "worldbank_wdi",
                "GC.BAL.CASH.GD.ZS",
                True,
                True,
                0.9,
            ],
        )
        con.execute(
            """
            INSERT INTO ds_metric_bindings (
                metric_id, dataset_id, distribution_id, connector_id, profile_id,
                request_dataset_id, confidence, metric_inference_confidence,
                default_filters, execution_tier, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "gov_balance",
                "source-worldbank-balance",
                "source-worldbank-balance-json",
                "worldbank.wdi",
                "worldbank_wdi",
                "GC.BAL.CASH.GD.ZS",
                0.87,
                0.95,
                "{}",
                "transport_ready",
                "worldbank",
            ],
        )
        con.execute(
            """
            INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance",
                "GC.BAL.CASH.GD.ZS",
                "gov_balance",
                "exact",
                0.85,
                "Cash surplus/deficit % GDP;source=worldbank",
                False,
                0.0,
            ],
        )
    finally:
        con.close()
    return path


def _entry():
    return build_authority_entry(
        source_lane="live_fetch",
        target_variable="government.balance",
        landing_dataset_id="acquisition.worldbank.government_balance",
        landing_distribution_id="acquisition.worldbank.government_balance.json",
        source_catalog_dataset_id="source-worldbank-balance",
        source_catalog_distribution_id="source-worldbank-balance-json",
        upstream_metric_id="gov_balance",
        catalog_raw_variable="GC.BAL.CASH.GD.ZS",
        raw_field="value",
        raw_unit="percent_gdp",
        canonical_unit="percent_gdp",
        unit_transform="identity",
        unit_transform_ref="fabric://units/percent-gdp-identity/v1",
        alignment_method="meta_analytic",
        alignment_confidence=0.8,
        is_proxy=False,
        proxy_penalty=0.0,
        aggregation_method="identity",
        valid_min=-100.0,
        valid_max=100.0,
        evidence_refs=(
            "duckdb://production_data/dataset_catalog.duckdb#/gov_balance",
        ),
        schema_contract_ref="fabric://worldbank.wdi.generic@2.0.0",
        schema_columns=(
            AuthoritySchemaColumn(
                name="country_code", logical_types=("string",), nullable=False
            ),
            AuthoritySchemaColumn(
                name="value", logical_types=("null", "number"), nullable=True
            ),
            AuthoritySchemaColumn(
                name="year", logical_types=("integer",), nullable=False
            ),
        ),
        l5_family_id="macro_state",
        title="Acquired government balance",
        description="Owner-validated World Bank government balance observations.",
        country_codes=("UA",),
        temporal_start="2020",
        temporal_end="2024",
    )


def _resolver(
    repo_root: Path,
    *,
    license_id: str = "CC-BY-4.0",
    authority_entry: AcquisitionAuthorityEntry | None = None,
):
    baseline = _baseline(repo_root, license_id=license_id)
    l5 = _write_l5(repo_root)
    entry = authority_entry or _entry()
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5),
        entries=(entry,),
    )
    path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return CanonicalAcquisitionAuthority(repo_root=repo_root, baseline_path=baseline), entry


def test_authority_resolves_catalog_license_l5_and_registration(tmp_path: Path) -> None:
    resolver, entry = _resolver(tmp_path)

    resolved = resolver.resolve(entry.entry_id)

    assert resolved.license_disposition is LicenseDisposition.ADMISSIBLE_OPEN
    assert resolved.registration.connector_id == "worldbank.wdi"
    assert resolved.registration.request_dataset_id == "GC.BAL.CASH.GD.ZS"
    assert resolved.field_binding.canonical_variable == "government.balance"
    assert resolved.l5_trust.family_id == "macro_state"
    assert resolved.l5_trust.trust_cap == 1.0
    assert resolved.effective_authority_score == 0.8


def test_authority_rejects_catalog_license_and_owner_byte_drift(tmp_path: Path) -> None:
    restricted, entry = _resolver(tmp_path / "restricted", license_id="all-rights-reserved")
    with pytest.raises(AcquisitionAuthorityError, match="license_not_admissible"):
        restricted.resolve(entry.entry_id)

    resolver, entry = _resolver(tmp_path / "l5-drift")
    resolver.l5_path.write_text("{}", encoding="utf-8")
    with pytest.raises(
        AcquisitionAuthorityError,
        match="l5_measurement_registry_content_drift",
    ):
        resolver.resolve(entry.entry_id)


def test_authority_rejects_self_authored_and_invented_exact_edges() -> None:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["evidence_refs"] = ("self://invented",)
    with pytest.raises(ValidationError, match="cannot be self-authored"):
        build_authority_entry(**values)

    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values.update(
        {
            "alignment_method": "exact",
            "alignment_confidence": 0.0,
        }
    )
    with pytest.raises(ValidationError, match="exact authority alignment"):
        build_authority_entry(**values)


def test_authority_rejects_landing_identifier_collision_with_epoch_zero(
    tmp_path: Path,
) -> None:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["landing_dataset_id"] = "source-worldbank-balance"
    collision = build_authority_entry(**values)
    resolver, entry = _resolver(tmp_path, authority_entry=collision)

    with pytest.raises(
        AcquisitionAuthorityError,
        match="landing_identifier_collides_with_epoch_zero",
    ):
        resolver.resolve(entry.entry_id)
