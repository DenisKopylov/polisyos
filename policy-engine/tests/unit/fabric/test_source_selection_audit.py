from __future__ import annotations

from polisyos.fabric.catalog.source_selection_audit import (
    build_fabric_source_selection_trace,
    normalize_fabric_retrieval_trace,
)


def _source(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_id": "prod-msme-panel",
        "source_family": "production_msme_panel",
        "source_kind": "production_data",
        "source_rights": "government_open_data",
        "dataset_ref": "dataset:prod-msme-panel",
        "dictionary_ref": "dictionary:prod-msme-panel:v1",
        "schema_ref": "schema:prod-msme-panel:v1",
        "field_refs": [
            "field:prod-msme-panel.entity_id",
            "field:prod-msme-panel.msme_survival_rate",
            "field:prod-msme-panel.wartime_credit_support",
        ],
        "unit_refs": ["unit:rate"],
        "geography_refs": ["UA"],
        "time_coverage_refs": ["2024-2026"],
        "quality_refs": ["quality:prod-msme-panel:v1"],
        "missingness_refs": ["missingness:prod-msme-panel:v1"],
        "freshness_refs": ["freshness:prod-msme-panel:2026-03-27"],
        "lineage_refs": ["lineage:prod-msme-panel:v1"],
        "transformation_refs": ["transform:msme-survival-rate:v1"],
        "data_forge_snapshot_refs": ["sha256:" + "4" * 64],
        "derived_features": [
            {
                "feature_ref": "feature:msme_survival_rate",
                "source_facet_refs": ["field:prod-msme-panel.msme_survival_rate"],
                "claim_support_feature_refs": ["claim-feature:rec_1:msme_survival_rate"],
            }
        ],
        "freshness": {"status": "pass", "as_of": "2026-03-27"},
        "coverage": {"status": "pass", "geography": "UA", "population": "msme"},
        "schema_compatibility": {
            "status": "pass",
            "required_fields": ["msme_survival_rate", "wartime_credit_support"],
        },
        "relevance_score": 0.94,
        "relevance_rationale": "Matches the MSME survival outcome and credit support treatment.",
    }
    payload.update(overrides)
    return payload


def _data_forge_binding() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.data_forge_snapshot_binding.v1",
        "bindings": [
            {
                "role": "domain",
                "snapshot_id": "domain-snapshot-R_wave13",
                "snapshot_ref": "sha256:" + "4" * 64,
                "manifest_ref": "cas://sha256/" + "4" * 64,
                "manifest_artifact_id": "sha256:" + "4" * 64,
                "artifact_ids": ["sha256:" + "4" * 64],
                "read_api_surface": "ukraine",
                "read_api_module": "polisyos.data_forge.read_api.ukraine",
                "published_at": "2026-05-15T00:00:00+00:00",
                "freshness_ttl_seconds": 60 * 60 * 24 * 14,
                "quality_gates": [
                    {
                        "name": "domain_publish_quality",
                        "status": "pass",
                        "artifact_id": "sha256:" + "4" * 64,
                    }
                ],
            }
        ],
    }


def _scenario_contract(source_family: str) -> dict[str, object]:
    return {
        "schema_version": "policyos.scenario_evidence_contract.v1",
        "contract_id": "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1",
        "scenario_id": "ukraine_msme_wartime_credit_support",
        "requirements": [
            {
                "requirement_id": (
                    "scenario:ukraine_msme_wartime_credit_support:data:" f"{source_family}"
                ),
                "domain": "data",
                "expected_family": source_family,
                "required_facets": [
                    "dictionary_ref",
                    "schema_ref",
                    "field_refs",
                    "unit_refs",
                    "geography_refs",
                    "time_coverage_refs",
                    "quality_refs",
                    "missingness_refs",
                    "lineage_refs",
                    "transformation_refs",
                ],
                "claim_scope": ["major_recommendations"],
            }
        ],
    }


def test_source_selection_trace_passes_for_relevant_production_source() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={
            "policy_domain": "wartime_msme_support",
            "query_outcome": "msme_survival_rate",
            "query_treatment": "wartime_credit_support",
        },
        candidate_sources=[
            _source(),
            _source(
                source_id="macro-nearby-panel",
                source_family="macro_indicators",
                relevance_score=0.41,
            ),
        ],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[
            {
                "source_id": "macro-nearby-panel",
                "source_family": "macro_indicators",
                "reason_code": "wrong_population",
                "relevance_rationale": "Macro panel does not identify MSMEs.",
            }
        ],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    assert trace["status"] == "pass"
    assert trace["selected_sources"][0]["source_id"] == "prod-msme-panel"
    assert trace["rejected_sources"][0]["reason_code"] == "wrong_population"
    assert trace["blocking_issue_count"] == 0


def test_source_selection_trace_fails_for_wrong_selected_family() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            _source(source_id="macro-panel", source_family="macro_indicators")
        ],
        selected_source_ids=["macro-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert "selected_source_family_not_admissible" in issue_codes


def test_source_selection_trace_fails_contract_when_generic_bundle_selected() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            _source(
                source_id="production-data-datasets-bundle",
                source_family="datasets",
            )
        ],
        selected_source_ids=["production-data-datasets-bundle"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        scenario_evidence_contract=_scenario_contract("production_msme_panel"),
        production_data_contract_binding_report={
            "scenario_binding_findings": [
                {
                    "requirement_id": (
                        "scenario:ukraine_msme_wartime_credit_support:data:"
                        "production_msme_panel"
                    ),
                    "expected_family": "production_msme_panel",
                    "candidate_ref": None,
                    "status": "blocked",
                    "missing_facets": ["dictionary_ref", "schema_ref", "lineage_refs"],
                }
            ]
        },
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert "source_family_mismatch" in issue_codes
    assert trace["source_family_blockers"][0]["status"] == "failed"
    assert trace["source_family_blockers"][0]["expected_family"] == "production_msme_panel"
    assert trace["selected_contract_binding"] is None
    assert trace["rejected_contract_bindings"][0]["status"] == "blocked"
    assert trace["selected_sources"][0]["selection_status"] == (
        "non_admissible_context_only"
    )
    assert trace["selected_sources"][0]["authority_surface"] == "context_inventory"


def test_normalize_trace_fails_when_fabric_drops_consumed_scenario_contract_id() -> None:
    normalized = normalize_fabric_retrieval_trace(
        {
            "status": "pass",
            "query_intent": {"policy_domain": "wartime_msme_support"},
            "scenario_evidence_contract_id": None,
            "selected_sources": [_source()],
            "rejected_sources": [],
            "production_data_contract_binding_report": {
                "scenario_contract_id": (
                    "scenario-evidence-contract:"
                    "ukraine_msme_wartime_credit_support:v1"
                ),
                "scenario_binding_findings": [
                    {
                        "requirement_id": (
                            "scenario:ukraine_msme_wartime_credit_support:data:"
                            "production_msme_panel"
                        ),
                        "expected_family": "production_msme_panel",
                        "candidate_ref": "prod-msme-panel",
                        "status": "satisfied",
                        "missing_facets": [],
                    }
                ],
            },
        },
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in normalized["issues"]}
    assert normalized["status"] == "fail"
    assert "scenario_evidence_contract_id_dropped" in issue_codes
    assert normalized["scenario_evidence_contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert normalized["fabric_spine_bindings"]["consumed_requirement_ids"] == [
        "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel"
    ]


def test_source_selection_trace_passes_with_contract_index_candidate_and_rejections() -> None:
    candidate_ref = "production_data:curated:credit_program_registry:contract.credit_registry"
    finding = {
        "requirement_id": (
            "scenario:ukraine_msme_wartime_credit_support:data:credit_program_registry"
        ),
        "expected_family": "credit_program_registry",
        "candidate_ref": candidate_ref,
        "status": "satisfied",
        "missing_facets": [],
        "present_facets": [
            "source_rights",
            "dictionary_ref",
            "schema_ref",
            "field_refs",
            "unit_refs",
            "geography_refs",
            "time_coverage_refs",
            "quality_refs",
            "missingness_refs",
            "lineage_refs",
            "transformation_refs",
            "derived_feature_bindings",
            "recency_ref",
            "construct_validity_refs",
            "outlier_refs",
        ],
    }
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            _source(
                source_id=candidate_ref,
                source_family="credit_program_registry",
                source_kind="production_data_contract",
                source_rights="public_sector_reuse",
                dictionary_ref="dictionary:credit-program-registry:v1",
                schema_ref="schema:credit-program-registry:v1",
                field_refs=["field:program_id", "field:credit_amount"],
                unit_refs=["unit:uah"],
                geography_refs=["UA", "oblast"],
                time_coverage_refs=["2024-01-01/2026-05-01"],
                quality_refs=["quality:credit-program-registry:v1"],
                missingness_refs=["missingness:credit-program-registry:v1"],
                freshness_refs=["freshness:credit-program-registry:2026-05-01"],
                lineage_refs=["lineage:ministry-credit-registry:v1"],
                transformation_refs=["transform:credit-program-registry:v1"],
                data_forge_snapshot_refs=["sha256:" + "9" * 64],
                derived_features=[
                    {
                        "feature_ref": "feature:wartime_credit_intensity:v1",
                        "source_facet_refs": ["field:credit_amount"],
                        "claim_support_feature_refs": [
                            "claim-feature:rec_1:wartime_credit_intensity"
                        ],
                    }
                ],
            )
        ],
        selected_source_ids=[candidate_ref],
        rejected_sources=[
            {
                "source_id": "production-data-datasets-bundle",
                "source_family": "datasets",
                "reason_code": "non_admissible_context_only",
                "relevance_rationale": (
                    "Broad manifest bundle remains context inventory, not "
                    "claim-admissible source evidence."
                ),
            }
        ],
        expected_source_families=None,
        scenario_evidence_contract=_scenario_contract("credit_program_registry"),
        production_data_contract_binding_report={
            "scenario_contract_id": (
                "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
            ),
            "scenario_binding_findings": [finding],
        },
        canary_kind="production",
    )

    assert trace["status"] == "pass"
    assert trace["scenario_evidence_contract_id"] == (
        "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
    )
    assert trace["selected_contract_binding"]["candidate_ref"] == candidate_ref
    assert trace["selected_contract_binding"]["status"] == "satisfied"
    assert trace["rejected_contract_bindings"] == []
    assert all(source.get("reason_code") for source in trace["rejected_sources"])
    assert trace["source_family_blockers"] == []
    assert trace["selected_sources"][0]["selection_status"] == (
        "claim_admissible_contract_selected"
    )
    assert trace["selected_sources"][0]["authority_surface"] == (
        "claim_admissible_contract"
    )
    assert trace["fabric_spine_bindings"]["selected_contract_binding_refs"] == [
        candidate_ref
    ]


def test_source_selection_trace_requires_selected_source_diagnostics() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            {
                "source_id": "prod-msme-panel",
                "source_family": "production_msme_panel",
                "source_kind": "production_data",
            }
        ],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert "selected_source_missing_freshness" in issue_codes
    assert "selected_source_missing_coverage" in issue_codes
    assert "selected_source_missing_schema_compatibility" in issue_codes
    assert "selected_source_missing_relevance_rationale" in issue_codes


def test_source_selection_trace_rejects_fixture_fallback_in_production() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            _source(
                source_id="fixture-msme-panel",
                source_family="fixture_msme_panel",
                source_kind="fixture",
            )
        ],
        selected_source_ids=["fixture-msme-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert "fixture_or_mock_source_selected" in issue_codes


def test_source_selection_trace_respects_explicit_fixture_flag_in_production() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            _source(
                source_id="prod-msme-panel",
                source_family="production_msme_panel",
                source_kind="production_data",
                fixture_or_mock=True,
            )
        ],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert trace["selected_sources"][0]["fixture_or_mock"] is True
    assert "fixture_or_mock_source_selected" in issue_codes


def test_source_selection_trace_requires_rejection_reason_codes() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[_source()],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[{"source_id": "nearby-source"}],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert "rejected_source_missing_reason_code" in issue_codes


def test_source_selection_trace_requires_reason_for_unselected_plausible_candidate() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[
            _source(),
            _source(
                source_id="nearby-production-source",
                source_family="production_msme_panel",
                relevance_score=0.88,
            ),
        ],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert "plausible_rejected_source_missing_reason_code" in issue_codes
    assert any(
        source["source_id"] == "nearby-production-source"
        for source in trace["rejected_sources"]
    )


def test_source_selection_trace_links_materialization_refs_and_fixture_flags() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[_source()],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
        materialization_refs={
            "data_snapshot_ref": "sha256:" + "1" * 64,
            "input_bindings_ref": "sha256:" + "2" * 64,
            "registry_bundle_ref": "sha256:" + "3" * 64,
            "quality_report_ref": "sha256:" + "4" * 64,
        },
        production_data_evidence_context={
            "root": "/data/production_data",
            "bundles": {"datasets": {"version_id": "datasets_full_20260327"}},
        },
    )

    selected = trace["selected_sources"][0]
    assert trace["status"] == "pass"
    assert selected["fixture_or_mock"] is False
    assert selected["diagnostics"]["freshness"]["status"] == "pass"
    assert trace["materialization_refs"]["data_snapshot_ref"].startswith("sha256:")
    assert trace["production_data_evidence_context"]["root"] == "/data/production_data"


def test_source_selection_trace_emits_wave13_source_facets_and_data_forge_refs() -> None:
    trace = build_fabric_source_selection_trace(
        query_intent={
            "policy_domain": "wartime_msme_support",
            "query_outcome": "msme_survival_rate",
            "query_treatment": "wartime_credit_support",
        },
        candidate_sources=[_source()],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[
            {
                "source_id": "macro-panel",
                "source_family": "macro_indicators",
                "reason_code": "wrong_population",
            }
        ],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
        data_forge_snapshot_binding=_data_forge_binding(),
    )

    selected = trace["selected_sources"][0]
    facets = selected["source_facets"]
    assert trace["status"] == "pass"
    assert "sha256:" + "4" * 64 in trace["data_forge_snapshot_refs"]
    assert facets["source_family"] == "production_msme_panel"
    assert facets["source_rights"] == "government_open_data"
    assert facets["dictionary_ref"] == "dictionary:prod-msme-panel:v1"
    assert facets["field_refs"] == [
        "field:prod-msme-panel.entity_id",
        "field:prod-msme-panel.msme_survival_rate",
        "field:prod-msme-panel.wartime_credit_support",
    ]
    assert selected["derived_features"][0]["source_facet_refs"] == [
        "field:prod-msme-panel.msme_survival_rate"
    ]
    assert selected["derived_features"][0]["claim_support_feature_refs"] == [
        "claim-feature:rec_1:msme_survival_rate"
    ]


def test_source_selection_trace_requires_wave13_facets_for_selected_source() -> None:
    source = _source(
        source_rights="",
        dictionary_ref="",
        schema_ref="",
        field_refs=[],
        missingness_refs=[],
        lineage_refs=[],
        transformation_refs=[],
        data_forge_snapshot_refs=[],
        derived_features=[],
        schema_compatibility={"status": "pass"},
    )

    trace = build_fabric_source_selection_trace(
        query_intent={"policy_domain": "wartime_msme_support"},
        candidate_sources=[source],
        selected_source_ids=["prod-msme-panel"],
        rejected_sources=[],
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in trace["issues"]}
    assert trace["status"] == "fail"
    assert {
        "selected_source_missing_source_rights",
        "selected_source_missing_dictionary_ref",
        "selected_source_missing_schema_ref",
        "selected_source_missing_field_refs",
        "selected_source_missing_missingness_refs",
        "selected_source_missing_lineage_refs",
        "selected_source_missing_transformation_refs",
        "selected_source_missing_data_forge_snapshot_refs",
        "selected_source_missing_derived_feature_bindings",
    } <= issue_codes


def test_normalize_trace_refuses_raw_pass_for_fixture_source() -> None:
    normalized = normalize_fabric_retrieval_trace(
        {
            "status": "pass",
            "query_intent": {"policy_domain": "wartime_msme_support"},
            "selected_sources": [
                _source(
                    source_id="mock-msme-source",
                    source_family="mock_msme_panel",
                    source_kind="mock",
                )
            ],
            "rejected_sources": [],
        },
        expected_source_families=["production_msme_panel"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in normalized["issues"]}
    assert normalized["status"] == "fail"
    assert "fixture_or_mock_source_selected" in issue_codes
