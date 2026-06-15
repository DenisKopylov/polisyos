from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

from polisyos.runtime.quality import layer3_causal_forecast as g2
from polisyos.runtime.quality import layer3_gx_data_home as gx_home
from polisyos.runtime.quality import layer3_promotion_gate as g4
from polisyos.runtime.quality import layer3_proving_ground_conversion as g5
from polisyos.runtime.quality import layer3_substrate_grounding as g1


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_task0a_data_home(repo_root: Path, *, omit_alias: str | None = None) -> None:
    pdc = repo_root / "architecture/policy_design_case"
    _write_json(
        pdc / "layer3_gx_pinned_request.json",
        {
            "schema_version": "policyos.policy_design_case.layer3_gx_pinned_request.v1",
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "request_id": "gx-request:ua-msme-affordable-loans-2022",
            "case_id": "ua-msme-affordable-loans-2022",
            "request_ref": "external-request://layer3-gx/ua-msme-affordable-loans-2022",
            "producer_ref": (
                "external-request://layer3-gx/pinned-request/ua-msme-affordable-loans-2022"
            ),
            "producer_type": "external_request",
            "producer_root_refs": [
                "external-request://layer3-gx/pinned-request/ua-msme-affordable-loans-2022"
            ],
            "authority_purpose": "pinned_route_replay_input_only",
            "expected_consumer_path": ["G1", "G2", "G4", "G5", "G6", "G7"],
            "requested_constructs": [
                {
                    "construct_ref": "credit_access",
                    "role": "cause",
                    "g1_request_shape": "construct_to_metric_binding",
                    "g2_variable_ref": "policy.credit_access",
                    "broad_query_terms": ["credit access", "affordable loans"],
                },
                {
                    "construct_ref": "firm_survival",
                    "role": "effect",
                    "g1_request_shape": "scenario_family_to_source_contract",
                    "g2_variable_ref": "firm.survival",
                    "broad_query_terms": ["firm survival", "business continuity"],
                },
                {
                    "construct_ref": "credit_program_enrollment",
                    "role": "demand_context",
                    "g1_request_shape": "acquisition_gap_probe",
                    "g2_variable_ref": "policy.credit_program_enrollment",
                    "broad_query_terms": ["program enrollment", "loan participation"],
                },
            ],
            "g1_requests": [
                {
                    "request_id": "g1-request:construct-to-metric-binding:credit_access",
                    "request_shape": "construct_to_metric_binding",
                    "construct_bundle_id": "ukrainian_msme_credit_constructs",
                    "construct_ref": "credit_access",
                    "scenario_family_ref": "ua_msme_credit_support",
                    "metric_intent": "ground credit access substrate data",
                },
                {
                    "request_id": "g1-request:scenario-family-to-source-contract:firm_survival",
                    "request_shape": "scenario_family_to_source_contract",
                    "construct_bundle_id": "ukrainian_msme_credit_constructs",
                    "construct_ref": "firm_survival",
                    "scenario_family_ref": "ua_msme_credit_support",
                    "metric_intent": "test firm survival source contract availability",
                },
            ],
            "g2_request": {
                "request_id": "g2-request:default-causal-forecast-method-search",
                "source_contract_refs": ["source-contract://ua-msme/credit-access-firm-survival"],
                "cause": "policy.credit_access",
                "effect": "firm.survival",
                "target_context_id": "UA",
                "limit": 8,
                "method_task_tags": [
                    "causal_effect_estimation",
                    "forecasting",
                    "uncertainty",
                    "validation",
                ],
                "data_modality": "panel",
                "treatment_structure": "binary_or_intensity_credit_access",
                "outcome_type": "firm_survival",
                "required_diagnostics": [
                    "identification",
                    "transportability",
                    "uncertainty",
                ],
            },
            "g4_promotion_requests": [
                {
                    "request_id": "g4-request:ua-msme-source-data",
                    "candidate_ref": "candidate://ua-msme/affordable-loans",
                    "candidate_source": "layer3_gx_pinned_request",
                    "incoming_projection_status": "shadow",
                    "promotion_scope": {
                        "claim_families": ["source_data"],
                        "requested_boundary": "declared_scope",
                    },
                    "required_contract_families": ["g1_source_contract"],
                    "source_design_record": {
                        "payload_status": "unresolved",
                        "ref": "pdc://layer2/s2/ua-msme/design-record-v0",
                    },
                }
            ],
            "may_not_use_for": [
                "claim_authority",
                "policy_recommendation",
                "corpus_supply_fact",
            ],
        },
    )
    aliases = [
        {
            "row_id": f"gx-alias:{construct}",
            "concept_ref": construct,
            "aliases": aliases,
            "resolution_status": "unverified",
            "asserts_corpus_supply": False,
            "corpus_row_refs": [],
        }
        for construct, aliases in {
            "credit_access": ["credit access", "affordable loans"],
            "firm_survival": ["firm survival", "business continuity"],
            "credit_program_enrollment": ["program enrollment", "loan participation"],
        }.items()
        if construct != omit_alias
    ]
    _write_json(
        pdc / "layer3_gx_concept_alias_seed_rows.json",
        {
            "schema_version": ("policyos.policy_design_case.layer3_gx_concept_alias_seed_rows.v1"),
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "producer_ref": (
                "external-request://layer3-gx/concept-alias-seeds/ua-msme-affordable-loans-2022"
            ),
            "producer_type": "external_request",
            "alias_rows": aliases,
        },
    )
    _write_json(
        pdc / "layer3_gx_scope_seed_rows.json",
        {
            "schema_version": "policyos.policy_design_case.layer3_gx_scope_seed_rows.v1",
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "producer_ref": ("external-request://layer3-gx/scope/ua-msme-affordable-loans-2022"),
            "producer_type": "external_request",
            "scope_rows": [
                {"scope_key": "entity_type", "value": "firm"},
                {"scope_key": "population", "value": "msme"},
                {"scope_key": "geography", "value": "UA"},
                {"scope_key": "modality", "value": "panel"},
                {"scope_key": "source_family_alias", "value": "production_msme_panel"},
                {
                    "scope_key": "validity_limit",
                    "value": "demand_seed_only_no_supply_assertion",
                },
            ],
        },
    )
    _write_json(
        pdc / "layer3_gx_demand_pull_request.json",
        {
            "schema_version": ("policyos.policy_design_case.layer3_gx_demand_pull_request.v1"),
            "rule_version": "policyos.layer3.gx.data_home.v1",
            "request_id": "gx-demand-pull:ua-msme-affordable-loans-2022",
            "case_id": "ua-msme-affordable-loans-2022",
            "producer_ref": (
                "external-request://layer3-gx/demand-pull/ua-msme-affordable-loans-2022"
            ),
            "producer_type": "external_request",
            "source": "docs/plans/active/layer3-slices/GX-universal-free-growth-runtime-hardening.md#task-0a",
            "timestamp": "2026-06-12T00:00:00Z",
            "accountable_principal_ref": "principal://deniskopylov",
            "request_source_ref": "user://deniskopylov/task-0a",
            "replay_key": "layer3-gx-demand-pull:ua-msme-affordable-loans-2022:v1",
            "consumer_path": ["G5", "G6", "G7"],
            "demand_refs": ["demand-act://layer3-gx/ua-msme-affordable-loans-2022"],
            "attempted_grounding_path_refs": ["layer3-gx://pinned-route/g5/demand-pull"],
        },
    )


def _write_task7_skg_canonical_fixture(repo_root: Path) -> None:
    graph_dir = (
        repo_root
        / "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/graph"
    )
    graph_dir.mkdir(parents=True)
    db_path = graph_dir / "scholar_knowledge.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE ac_skg_variables (
                canonical_name VARCHAR,
                normalized_name VARCHAR,
                display_name VARCHAR,
                parent_name VARCHAR,
                approved_canonical_name VARCHAR,
                approved_parent_name VARCHAR,
                is_approved_canonical BOOLEAN,
                resolution_method VARCHAR,
                resolution_confidence DOUBLE,
                mention_count INTEGER,
                first_seen_ts TIMESTAMP
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_variables VALUES (
                'policy.credit_access',
                'credit access',
                'Credit access',
                'policy',
                'policy.credit_access',
                'policy',
                TRUE,
                'measurement_canonicalizer',
                0.94,
                17,
                now()
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_context_attributes (
                attr_id VARCHAR,
                openalex_id VARCHAR,
                canonical_name VARCHAR,
                attribute_value DOUBLE,
                value_qualitative VARCHAR,
                unit VARCHAR,
                country_code VARCHAR,
                time_period VARCHAR,
                measurement_method VARCHAR,
                confidence DOUBLE,
                evidence_span_count INTEGER,
                skg_version INTEGER
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_context_attributes VALUES (
                'ctx-credit-access-ua',
                'work-credit-access',
                'policy.credit_access',
                NULL,
                'observed in Ukraine MSME credit access literature',
                NULL,
                'UA',
                '2022',
                'skg_context_extraction',
                0.8,
                3,
                1
            )
            """
        )
    finally:
        con.close()


def test_task0a_data_home_feeds_g1_g2_g4_g5_without_python_defaults(
    tmp_path: Path,
) -> None:
    _write_task0a_data_home(tmp_path)

    data_home = gx_home.load_layer3_gx_data_home(tmp_path)

    assert data_home.status == "ready"
    assert data_home.pinned_request.case_id == "ua-msme-affordable-loans-2022"
    assert data_home.pinned_request.authority_purpose == "pinned_route_replay_input_only"
    assert set(data_home.expected_consumer_path) >= {"G1", "G2", "G4", "G5"}
    assert {row.concept_ref for row in data_home.concept_alias_rows} >= {
        "credit_access",
        "firm_survival",
        "credit_program_enrollment",
    }
    assert {row.resolution_status for row in data_home.concept_alias_rows} == {"unverified"}
    assert all(not row.asserts_corpus_supply for row in data_home.concept_alias_rows)
    assert {row.scope_key for row in data_home.scope_rows} >= {
        "entity_type",
        "population",
        "geography",
        "modality",
        "source_family_alias",
        "validity_limit",
    }
    assert {
        (record["producer_ref"], record["producer_type"]) for record in data_home.producer_records
    } >= {
        (
            "external-request://layer3-gx/pinned-request/ua-msme-affordable-loans-2022",
            "external_request",
        ),
        (
            "external-request://layer3-gx/scope/ua-msme-affordable-loans-2022",
            "external_request",
        ),
        (
            "external-request://layer3-gx/demand-pull/ua-msme-affordable-loans-2022",
            "external_request",
        ),
    }

    g1_requests = g1._default_requests(tmp_path)
    assert [request.construct_ref for request in g1_requests] == [
        "credit_access",
        "firm_survival",
    ]
    g2_request = g2._default_g2_method_request(tmp_path)
    assert g2_request.cause == "policy.credit_access"
    assert g2_request.effect == "firm.survival"
    g4_requests = g4.build_g4_promotion_requests_from_gx_data_home(tmp_path)
    assert g4_requests[0].case_id == "ua-msme-affordable-loans-2022"
    g5_demand = g5.build_g5_demand_pull_request_from_gx_data_home(tmp_path)
    assert g5_demand.status == "pass"
    assert g5_demand.s12_demand_act_refs == (
        "demand-act://layer3-gx/ua-msme-affordable-loans-2022",
    )


def test_task7_concept_alias_graph_is_data_owned_and_unverified_by_default(
    tmp_path: Path,
) -> None:
    _write_task0a_data_home(tmp_path)

    artifact = gx_home.build_layer3_gx_concept_alias_graph_artifact(tmp_path)

    assert (
        artifact["schema_version"] == "policyos.policy_design_case.layer3_gx_concept_alias_graph.v1"
    )
    rows = artifact["graph_rows"]
    row_by_concept = {row["concept_ref"]: row for row in rows}
    credit = row_by_concept["credit_access"]
    required_fields = {
        "concept_ref",
        "aliases",
        "metric_ids",
        "variable_names",
        "source_layer_refs",
        "jurisdiction_constraints",
        "validity_limits",
        "producer_owner",
        "producer_type",
        "verification_status",
        "resolved_corpus_row_refs",
        "rule_version",
    }
    assert required_fields <= set(credit)
    assert credit["aliases"] == ["credit access", "affordable loans"]
    assert credit["metric_ids"] == ["credit_access"]
    assert credit["variable_names"] == ["policy.credit_access"]
    assert credit["source_layer_refs"] == [gx_home.L1_DCAT_REF]
    assert credit["jurisdiction_constraints"] == ["UA"]
    assert credit["validity_limits"] == ["demand_seed_only_no_supply_assertion"]
    assert credit["producer_type"] == "external_request"
    assert credit["verification_status"] == "unverified"
    assert credit["resolved_corpus_row_refs"] == []

    _write_json(tmp_path / gx_home.CONCEPT_ALIAS_GRAPH_PATH, artifact)
    graph = gx_home.load_layer3_gx_concept_alias_graph(tmp_path)

    assert graph.status == "ready"
    assert graph.issue_codes == ()
    assert {row.concept_ref for row in graph.graph_rows} >= {
        "credit_access",
        "firm_survival",
        "credit_program_enrollment",
    }


def test_task7_concept_alias_graph_prefers_measured_skg_canonical_rows(
    tmp_path: Path,
) -> None:
    _write_task0a_data_home(tmp_path)
    _write_task7_skg_canonical_fixture(tmp_path)

    artifact = gx_home.build_layer3_gx_concept_alias_graph_artifact(tmp_path)

    rows = {row["concept_ref"]: row for row in artifact["graph_rows"]}
    credit = rows["credit_access"]
    firm = rows["firm_survival"]

    assert credit["producer_type"] == "measurement"
    assert credit["verification_status"] == "measured"
    assert "credit access" in credit["aliases"]
    assert credit["variable_names"] == ["policy.credit_access"]
    assert {
        "duckdb://production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/graph/scholar_knowledge.duckdb#ac_skg_variables/policy.credit_access",
        "duckdb://production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/graph/scholar_knowledge.duckdb#ac_skg_context_attributes/ctx-credit-access-ua",
    } <= set(credit["resolved_corpus_row_refs"])
    assert {
        "duckdb://production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/graph/scholar_knowledge.duckdb#ac_skg_variables",
        "duckdb://production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/graph/scholar_knowledge.duckdb#ac_skg_context_attributes",
    } <= set(credit["source_layer_refs"])

    assert firm["producer_type"] == "external_request"
    assert firm["verification_status"] == "unverified"
    assert firm["resolved_corpus_row_refs"] == []


def test_task7_measured_alias_graph_rows_require_resolution_refs(
    tmp_path: Path,
) -> None:
    _write_task0a_data_home(tmp_path)
    artifact = gx_home.build_layer3_gx_concept_alias_graph_artifact(tmp_path)
    artifact["graph_rows"][0]["producer_type"] = "measurement"
    artifact["graph_rows"][0]["verification_status"] = "measured"
    artifact["graph_rows"][0]["resolved_corpus_row_refs"] = []
    _write_json(tmp_path / gx_home.CONCEPT_ALIAS_GRAPH_PATH, artifact)

    graph = gx_home.load_layer3_gx_concept_alias_graph(tmp_path)

    assert graph.status == "typed_blocker"
    assert "layer3_gx_concept_alias_measured_resolution_missing" in graph.issue_codes


def test_task7_unverified_alias_graph_rows_may_not_carry_resolution_refs(
    tmp_path: Path,
) -> None:
    _write_task0a_data_home(tmp_path)
    artifact = gx_home.build_layer3_gx_concept_alias_graph_artifact(tmp_path)
    artifact["graph_rows"][0]["resolved_corpus_row_refs"] = [
        "duckdb://production_data/test.duckdb#ac_skg_variables/policy.credit_access"
    ]
    _write_json(tmp_path / gx_home.CONCEPT_ALIAS_GRAPH_PATH, artifact)

    graph = gx_home.load_layer3_gx_concept_alias_graph(tmp_path)

    assert graph.status == "typed_blocker"
    assert "layer3_gx_concept_alias_unverified_resolution_refs" in graph.issue_codes


def test_task0a_missing_alias_row_blocks_without_code_fallback(tmp_path: Path) -> None:
    _write_task0a_data_home(tmp_path, omit_alias="firm_survival")

    data_home = gx_home.load_layer3_gx_data_home(tmp_path)

    assert data_home.status == "typed_blocker"
    assert "layer3_gx_pinned_construct_alias_missing" in data_home.issue_codes
    assert g1._default_requests(tmp_path) == ()
    with pytest.raises(gx_home.Layer3GXDataHomeBlockedError):
        g2._default_g2_method_request(tmp_path)
    assert g4.build_g4_promotion_requests_from_gx_data_home(tmp_path) == ()
    g5_demand = g5.build_g5_demand_pull_request_from_gx_data_home(tmp_path)
    assert g5_demand.status == "fail"
    assert "layer3_gx_pinned_construct_alias_missing" in g5_demand.issue_codes
