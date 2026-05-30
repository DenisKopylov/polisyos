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
    assert report["capability_reality_status"] == "implemented"
    assert report["requirement_source"] == "compiled_data_requirement_spec"
    assert report["compiled_data_requirement_specs"][0]["required_data_families"] == [
        "credit_program_registry"
    ]
    assert "source_contract_binding" in report["runtime_authority_envelope"]["authoritative_for"]
    assert "scenario_source_family_admissibility" not in report[
        "runtime_authority_envelope"
    ]["authoritative_for"]
    assert "scenario_family_authority_lookup" in report[
        "runtime_authority_envelope"
    ]["may_not_use_for"]
    assert "legal_authority" in report["runtime_authority_envelope"]["may_not_use_for"]
    assert report["compatibility_projection"]["scenario_family_authority_status"] == (
        "sunset_projection_only"
    )
    finding = report["scenario_binding_findings"][0]
    binding = report["source_contract_bindings"][0]
    assert finding["requirement_id"] == (
        "scenario:ukraine_msme_wartime_credit_support:data:credit_program_registry"
    )
    assert finding["status"] == "satisfied"
    assert finding["binding_status"] == "selected"
    assert binding["binding_status"] == "selected"
    assert binding["data_requirement_id"] == finding["requirement_id"]
    assert finding["candidate_ref"] == (
        "production_data:curated:credit_program_registry:contract.credit_registry"
    )
    assert finding["missing_facets"] == []
    assert finding["claim_bindability_status"] == "claim_bound"


def test_contract_index_requires_source_contract_backing_for_scenario_family(
    tmp_path: Path,
) -> None:
    contract = _complete_contract(
        contract_id="contract.credit_registry",
        source_family="credit_program_registry",
    )
    contract.pop("source_contract_ref")
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

    assert finding["status"] == "failed"
    assert finding["blocker_code"] == "source_contract_missing"
    assert "source_contract_ref" in finding["missing_facets"]
    assert finding["claim_bindability_status"] == "blocked"
    assert finding["source_contract_validation"]["status"] == "missing"


def test_contract_index_validates_source_contract_snapshot_and_exports_lineage_facets(
    tmp_path: Path,
) -> None:
    root = _production_root(
        tmp_path,
        contracts=[
            _complete_contract(
                contract_id="contract.credit_registry",
                source_family="credit_program_registry",
                source_contract_ref="source-contract:credit.registry:v1",
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
        source_contracts=[
            _source_contract_record(
                source_contract_id="source-contract:credit.registry:v1",
                version="1.1.0",
                status="active",
            )
        ],
    )

    finding = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(_requirement("credit_program_registry"))
    )["scenario_binding_findings"][0]

    assert finding["status"] == "satisfied"
    assert finding["missing_facets"] == []
    assert finding["source_contract_validation"] == {
        "status": "pass",
        "source_contract_id": "source-contract:credit.registry:v1",
        "source_contract_ref": "source-contract:credit.registry:v1",
        "source_contract_version": "1.1.0",
        "source_contract_status": "active",
        "content_hash": "sha256:" + "c" * 64,
    }
    assert finding["selected_refs"] == [
        "production_data:curated:credit_program_registry:contract.credit_registry"
    ]
    assert finding["rejected_refs"] == []
    assert finding["limitation_refs"] == []
    openlineage = finding["openlineage_facets"]
    assert openlineage["dataset"]["namespace"] == "fabric.production_data"
    assert openlineage["dataset"]["name"] == "credit_program_registry"
    assert openlineage["dataset"]["facets"]["sourceContract"]["sourceContractId"] == (
        "source-contract:credit.registry:v1"
    )
    assert openlineage["dataset"]["facets"]["schema"]["schemaRef"].startswith("sha256:")
    assert openlineage["dataset"]["facets"]["dataQuality"]["qualityAssertionRefs"] == [
        "quality-assertion:credit_program_registry:v1"
    ]
    assert openlineage["dataset"]["facets"]["lineage"]["lineageRefs"] == [
        "lineage:ministry-credit-registry:v1"
    ]


def test_contract_index_blocks_inactive_source_contract_snapshot(
    tmp_path: Path,
) -> None:
    root = _production_root(
        tmp_path,
        contracts=[
            _complete_contract(
                contract_id="contract.credit_registry",
                source_family="credit_program_registry",
                source_contract_ref="source-contract:credit.registry:v1",
            )
        ],
        bindings=[
            {
                "binding_id": "binding.credit_registry",
                "contract_id": "contract.credit_registry",
                "scenario_source_family": "credit_program_registry",
            }
        ],
        source_contracts=[
            _source_contract_record(
                source_contract_id="source-contract:credit.registry:v1",
                version="1.1.0",
                status="sunset",
            )
        ],
    )

    finding = ProductionDataContractIndex.load(root).build_scenario_binding_report(
        _scenario_contract(_requirement("credit_program_registry"))
    )["scenario_binding_findings"][0]

    assert finding["status"] == "failed"
    assert finding["blocker_code"] == "source_contract_not_active"
    assert finding["source_contract_validation"]["status"] == "blocked"
    assert finding["rejected_refs"] == [
        "production_data:curated:credit_program_registry:contract.credit_registry"
    ]


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
        assert finding["binding_status"] == "blocked"
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
    rejected = [
        binding
        for binding in report["source_contract_bindings"]
        if binding["binding_status"] == "context_only"
    ]
    assert {binding["source_family"] for binding in rejected} == {"agent_income", "datasets"}


def test_contract_index_can_bind_directly_against_compiled_data_requirement_specs(
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
    spec = _data_requirement_spec("credit_program_registry")

    report = ProductionDataContractIndex.load(root).build_data_requirement_binding_report(
        [spec]
    )

    assert report["requirement_source"] == "compiled_data_requirement_spec"
    assert report["summary"] == {
        "requirements": 1,
        "satisfied": 1,
        "failed": 0,
        "blocked": 0,
    }
    assert report["scenario_binding_findings"][0]["requirement_id"] == (
        "data-requirement:claim-credit:credit_program_registry"
    )
    assert report["source_contract_bindings"][0]["binding_status"] == "selected"


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
    source_contracts: list[dict[str, Any]] | None = None,
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
                "required_files": [
                    "data_contracts.json",
                    "source_bindings.json",
                    "source_contracts_v2.json",
                ],
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
    (curated / "source_contracts_v2.json").write_text(
        json.dumps(
            {
                "schema_version": "fabric.source_contract.v2",
                "contracts": {
                    row["id"]: row for row in source_contracts or _default_source_contracts()
                },
            }
        ),
        encoding="utf-8",
    )
    return root


def _complete_contract(
    *,
    contract_id: str,
    source_family: str,
    source_contract_ref: str | None = None,
) -> dict[str, Any]:
    return {
        "contract_id": contract_id,
        "dataset_identity": f"dataset:{source_family}:202605",
        "source_family": source_family,
        "source_contract_ref": source_contract_ref or f"source-contract:{source_family}:v1",
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


def _default_source_contracts() -> list[dict[str, Any]]:
    return [
        _source_contract_record(
            source_contract_id="source-contract:credit_program_registry:v1",
            version="1.1.0",
            status="active",
        ),
        _source_contract_record(
            source_contract_id="source-contract:production_msme_panel:v1",
            version="1.1.0",
            status="active",
        ),
        _source_contract_record(
            source_contract_id="source-contract:regional_displacement_indicators:v1",
            version="1.1.0",
            status="active",
        ),
    ]


def _source_contract_record(
    *,
    source_contract_id: str,
    version: str,
    status: str,
) -> dict[str, Any]:
    return {
        "id": source_contract_id,
        "version": version,
        "status": status,
        "content_hash": "sha256:" + "c" * 64,
        "contract": {
            "id": source_contract_id,
            "version": version,
            "status": status,
        },
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


def _data_requirement_spec(source_family: str) -> dict[str, Any]:
    return {
        "schema_version": "policyos.data_requirement_spec.v1",
        "requirement_id": f"data-requirement:claim-credit:{source_family}",
        "claim_id": "claim-credit",
        "claim_family": "causal",
        "claim_type": "causal",
        "claim_use": "decision_support",
        "required_data_families": [source_family],
        "scope": {
            "population": "msmes",
            "geography": "state_or_region",
            "time": "annual",
            "time_role": "observation_time",
        },
        "recency_horizon": "P90D",
        "lineage_strictness": "strict",
        "quality_minima": {
            "min_quality_score": 0.8,
            "min_completeness": 0.95,
        },
        "missingness_tolerance": 0.05,
        "transformation_tolerance": "traceable",
        "admissibility_predicates": [
            "source_family_matches_compiled_requirement",
            "source_contract_active",
        ],
        "mandatory_facets": [
            "source_contract_ref",
            *DATA_REQUIRED_FACETS,
            "freshness_ref",
            "quality_assertion_refs",
            "construct_validity_refs",
            "outlier_refs",
            "claim_bindability_refs",
        ],
        "facet_refs": ["facet:instrument"],
        "obligation_refs": ["obl:data"],
        "concept_spine_refs": ["concept:msme"],
        "authority_profile_refs": ["authority:production"],
    }


def _scenario_contract(*requirements: ScenarioEvidenceRequirement) -> dict[str, Any]:
    return {
        "schema_version": "policyos.scenario_evidence_contract.v1",
        "contract_id": "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1",
        "scenario_id": "ukraine_msme_wartime_credit_support",
        "requirements": [requirement.to_dict() for requirement in requirements],
    }
