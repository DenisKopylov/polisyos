from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from polisyos.runtime.quality.production_data_contract_index import (
    PRODUCTION_DATA_CONTRACT_INDEX_SCHEMA_VERSION,
    ProductionDataContractIndex,
)
from polisyos.runtime.quality.scenario_evidence_contract import (
    DATA_REQUIRED_FACETS,
    ScenarioEvidenceRequirement,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_contract_index_maps_curated_source_binding_to_scenario_family(
    tmp_path: Path,
) -> None:
    root = _production_root(
        tmp_path,
        contracts=[
            _complete_contract(
                contract_id="contract.credit_registry",
                source_family="credit_program_registry",
            )
        ],
        bindings=[
            {
                "binding_id": "binding.credit_registry",
                "contract_id": "contract.credit_registry",
                "scenario_source_family": "credit_program_registry",
                "connector_id": "ministry.credit_registry",
                "dataset_id": "wartime_credit_programs",
            }
        ],
    )

    report = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(_requirement("credit_program_registry"))
    )

    assert report["schema_version"] == PRODUCTION_DATA_CONTRACT_INDEX_SCHEMA_VERSION
    finding = report["scenario_binding_findings"][0]
    assert finding["requirement_id"] == (
        "scenario:ukraine_msme_wartime_credit_support:data:credit_program_registry"
    )
    assert finding["status"] == "satisfied"
    assert finding["candidate_ref"] == (
        "production_data:curated:credit_program_registry:contract.credit_registry"
    )
    assert finding["missing_facets"] == []
    assert finding["claim_bindability_status"] == "claim_bound"


def test_contract_index_reports_missing_dictionary_schema_and_lineage(
    tmp_path: Path,
) -> None:
    contract = _complete_contract(
        contract_id="contract.credit_registry",
        source_family="credit_program_registry",
    )
    for key in ("dictionary_ref", "schema_ref", "lineage_refs"):
        contract.pop(key)
    root = _production_root(
        tmp_path,
        contracts=[contract],
        bindings=[
            {
                "binding_id": "binding.credit_registry",
                "contract_id": "contract.credit_registry",
                "source_family": "credit_program_registry",
            }
        ],
    )

    finding = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(_requirement("credit_program_registry"))
    )["scenario_binding_findings"][0]

    assert finding["status"] == "failed"
    assert set(finding["missing_facets"]) >= {
        "dictionary_ref",
        "schema_ref",
        "lineage_refs",
    }
    assert finding["claim_bindability_status"] == "blocked"


def test_contract_index_reports_recency_construct_validity_missingness_and_outliers(
    tmp_path: Path,
) -> None:
    contract = _complete_contract(
        contract_id="contract.credit_registry",
        source_family="credit_program_registry",
    )
    for key in ("freshness_ref", "construct_validity_refs", "outlier_refs"):
        contract.pop(key)
    contract["missingness"] = {"status": "fail", "max_missing_rate": 0.34}
    contract["outlier_profile"] = {"status": "fail", "max_outlier_ratio": 0.22}
    root = _production_root(
        tmp_path,
        contracts=[contract],
        bindings=[
            {
                "binding_id": "binding.credit_registry",
                "contract_id": "contract.credit_registry",
                "scenario_source_family": "credit_program_registry",
                "connector_id": "ministry.credit_registry",
                "dataset_id": "wartime_credit_programs",
            }
        ],
    )

    finding = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(_requirement("credit_program_registry"))
    )["scenario_binding_findings"][0]

    limitation_codes = {item["code"] for item in finding["claim_bound_limitations"]}
    assert finding["status"] == "failed"
    assert set(finding["missing_facets"]) >= {
        "freshness_ref",
        "construct_validity_refs",
        "outlier_refs",
    }
    assert limitation_codes >= {
        "freshness_evidence_missing",
        "construct_validity_metric_missing",
        "production_data_missingness_high",
        "production_data_outlier_ratio_high",
    }
    assert all(
        item["claim_scope"] == ["major_recommendations"]
        for item in finding["claim_bound_limitations"]
    )
    assert all(item["degrade_reason"] for item in finding["claim_bound_limitations"])


def test_contract_index_satisfies_all_public_golden_scenario_source_families(
    tmp_path: Path,
) -> None:
    families = [
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    ]
    root = _production_root(
        tmp_path,
        contracts=[
            _complete_contract(
                contract_id=f"contract.{family}",
                source_family=family,
            )
            for family in families
        ],
        bindings=[
            {
                "binding_id": f"binding.{family}",
                "contract_id": f"contract.{family}",
                "scenario_source_family": family,
                "connector_id": f"ua.{family}",
                "dataset_id": f"{family}.202605",
                "claim_bindability_refs": [f"claim-bindability:{family}:v1"],
            }
            for family in families
        ],
    )

    report = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(*[_requirement(family) for family in families])
    )

    findings = {
        finding["expected_family"]: finding
        for finding in report["scenario_binding_findings"]
    }
    assert report["summary"] == {
        "requirements": 3,
        "satisfied": 3,
        "failed": 0,
        "blocked": 0,
    }
    assert set(findings) == set(families)
    for family in families:
        assert findings[family]["status"] == "satisfied"
        assert findings[family]["missing_facets"] == []
        assert findings[family]["claim_bindability_status"] == "claim_bound"
        assert {
            "dataset_identity",
            "source_family",
            "dictionary_ref",
            "schema_ref",
            "field_refs",
            "unit_refs",
            "geography_refs",
            "time_coverage_refs",
            "freshness_ref",
            "lineage_refs",
            "transformation_refs",
            "quality_assertion_refs",
            "missingness_refs",
            "outlier_refs",
            "construct_validity_refs",
            "claim_bindability_refs",
        } <= set(findings[family]["present_facets"])


def test_contract_index_blocks_cloud_curated_macro_contracts_for_public_golden(
    tmp_path: Path,
) -> None:
    root = _production_root(
        tmp_path,
        contracts=[
            {
                "contract_id": "us.macro.gdp_nominal",
                "source_family": "datasets",
                "field_refs": ["gdp_nominal"],
                "schema_ref": "schema:us-macro:gdp",
            },
            {
                "contract_id": "us.macro.unemployment_rate",
                "source_family": "datasets",
                "field_refs": ["unemployment_rate"],
                "schema_ref": "schema:us-macro:unemployment",
            },
            {
                "contract_id": "agent.income.salary",
                "source_family": "agent_income",
                "field_refs": ["salary"],
                "schema_ref": "schema:agent-income:salary",
            },
        ],
        bindings=[
            {
                "binding_id": "binding.gdp",
                "contract_id": "us.macro.gdp_nominal",
                "source_family": "datasets",
            },
            {
                "binding_id": "binding.unemployment",
                "contract_id": "us.macro.unemployment_rate",
                "source_family": "datasets",
            },
            {
                "binding_id": "binding.salary",
                "contract_id": "agent.income.salary",
                "source_family": "agent_income",
            },
        ],
    )

    report = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(
            _requirement("production_msme_panel"),
            _requirement("credit_program_registry"),
            _requirement("regional_displacement_indicators"),
        )
    )

    assert report["summary"] == {
        "requirements": 3,
        "satisfied": 0,
        "failed": 0,
        "blocked": 3,
    }
    assert report["missing_scenario_source_families"] == [
        "credit_program_registry",
        "production_msme_panel",
        "regional_displacement_indicators",
    ]
    for finding in report["scenario_binding_findings"]:
        assert finding["status"] == "blocked"
        assert finding["blocker_code"] == "scenario_source_family_absent"
        assert finding["candidate_ref"] is None
        assert {
            "dataset_identity",
            "source_family",
            "dictionary_ref",
            "schema_ref",
            "field_refs",
            "unit_refs",
            "geography_refs",
            "time_coverage_refs",
            "freshness_ref",
            "lineage_refs",
            "transformation_refs",
            "quality_assertion_refs",
            "missingness_refs",
            "outlier_refs",
            "construct_validity_refs",
            "claim_bindability_refs",
        } <= set(finding["missing_facets"])
        assert finding["rejected_candidate_source_families"] == [
            "agent_income",
            "datasets",
        ]


def test_contract_index_reports_openlineage_facets_as_missing_facets(
    tmp_path: Path,
) -> None:
    contract = _complete_contract(
        contract_id="contract.production_msme_panel",
        source_family="production_msme_panel",
    )
    for key in (
        "dataset_identity",
        "freshness_ref",
        "quality_assertion_refs",
        "claim_bindability_refs",
    ):
        contract.pop(key)
    root = _production_root(
        tmp_path,
        contracts=[contract],
        bindings=[
            {
                "binding_id": "binding.msme",
                "contract_id": "contract.production_msme_panel",
                "scenario_source_family": "production_msme_panel",
            }
        ],
    )

    finding = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(_requirement("production_msme_panel"))
    )["scenario_binding_findings"][0]

    assert finding["status"] == "failed"
    assert set(finding["missing_facets"]) >= {
        "dataset_identity",
        "freshness_ref",
        "quality_assertion_refs",
        "claim_bindability_refs",
    }
    assert "data-quality" not in json.dumps(finding["missing_facets"]).casefold()


def _production_root(
    tmp_path: Path,
    *,
    contracts: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
) -> Path:
    root = tmp_path / "production_data"
    curated = root / "canonical/local_data_20260501/policy_engine_data/curated"
    curated.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0",
        "generated_at": "2026-05-01T00:00:00Z",
        "bundles": {
            "curated": {
                "role": "fabric_curated_catalog",
                "version_id": "local_data_20260501",
                "readiness": "ready",
                "path": "canonical/local_data_20260501/policy_engine_data/curated",
                "required_files": ["data_contracts.json", "source_bindings.json"],
            },
            "datasets": {
                "role": "dataset_catalog_snapshot",
                "version_id": "datasets_v1",
                "readiness": "ready",
                "source_family": "datasets",
                "path": "datasets_v1",
            },
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (curated / "data_contracts.json").write_text(
        json.dumps({"schema_version": "1.0", "contracts": contracts}),
        encoding="utf-8",
    )
    (curated / "source_bindings.json").write_text(
        json.dumps({"schema_version": "1.0", "bindings": bindings}),
        encoding="utf-8",
    )
    return root


def _complete_contract(*, contract_id: str, source_family: str) -> dict[str, Any]:
    return {
        "contract_id": contract_id,
        "dataset_identity": f"dataset:{source_family}:202605",
        "source_family": source_family,
        "source_rights": "public_sector_reuse",
        "dictionary_ref": "sha256:" + "d" * 64,
        "schema_ref": "sha256:" + "s" * 64,
        "field_refs": ["program_id", "firm_id", "region", "credit_amount"],
        "unit_refs": ["uah", "firm"],
        "geography_refs": ["UA", "oblast"],
        "time_coverage_refs": ["2024-01-01/2026-05-01"],
        "quality_refs": ["quality:credit-program-registry:v1"],
        "missingness_refs": ["missingness:credit-program-registry:v1"],
        "lineage_refs": ["lineage:ministry-credit-registry:v1"],
        "transformation_refs": ["transform:normalize-credit-program-registry:v1"],
        "derived_feature_bindings": ["feature:wartime_credit_intensity:v1"],
        "freshness_ref": "freshness:2026-05-01",
        "recency_ref": "as_of:2026-05-01",
        "quality_assertion_refs": [f"quality-assertion:{source_family}:v1"],
        "construct_validity_refs": ["construct:credit-program-eligibility:v1"],
        "outlier_refs": ["outliers:credit-program-registry:v1"],
        "claim_bindability_refs": [f"claim-bindability:{source_family}:v1"],
    }


def _requirement(source_family: str) -> ScenarioEvidenceRequirement:
    return ScenarioEvidenceRequirement(
        requirement_id=(
            "scenario:ukraine_msme_wartime_credit_support:data:" f"{source_family}"
        ),
        domain="data",
        expected_family=source_family,
        required_facets=DATA_REQUIRED_FACETS,
        claim_scope=("major_recommendations",),
        jurisdiction="UA",
        temporal_scope="2026",
        authority_scope=("UA", "wartime_msme_support"),
        instrument_type="wartime_credit_support",
        beneficiary_class="msme",
        rights_scope="public_policy_research",
        producer_owner="team-fabric",
        reader_owner="team-runtime-quality",
    )


def _scenario_contract(*requirements: ScenarioEvidenceRequirement) -> dict[str, Any]:
    return {
        "schema_version": "policyos.scenario_evidence_contract.v1",
        "contract_id": "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1",
        "scenario_id": "ukraine_msme_wartime_credit_support",
        "requirements": [requirement.to_dict() for requirement in requirements],
    }
