from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from typing import Any

from tests.unit.runtime.quality.test_policy_design_case_false_passes import (
    _policy_design_case,
    _scorecard_blocking_codes_for_case,
    sha,
)


def test_pdd_017_blocks_missing_dormant_capability_inventory() -> None:
    case = _phase28_3_case()
    case.pop("dormant_capability_inventory")

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_dormant_capability_inventory_missing" in codes


def test_pdd_017_blocks_unexplained_dormant_capability_breakpoint() -> None:
    case = _phase28_3_case()
    inventory = deepcopy(case["dormant_capability_inventory"])
    inventory["capabilities"][0].pop("current_break_point")
    case["dormant_capability_inventory"] = inventory

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_dormant_capability_inventory_incomplete" in codes


def test_pdd_018_blocks_skipped_node_without_causality_explanation() -> None:
    case = _phase28_3_case()
    ledger = deepcopy(case["skip_causality_ledger"])
    ledger["skipped_nodes"][0].pop("reason_code")
    ledger["skipped_nodes"][0].pop("downstream_impact")
    case["skip_causality_ledger"] = ledger

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_skip_causality_explanation_missing" in codes


def test_pdd_045_blocks_stale_evidence_without_policy_time_semantics() -> None:
    case = _phase28_3_case()
    semantics = deepcopy(case["freshness_policy_time_semantics"])
    semantics["evidence_time_bindings"][0]["freshness_status"] = "stale"
    semantics["evidence_time_bindings"][0].pop("policy_time")
    case["freshness_policy_time_semantics"] = semantics

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_policy_time_metadata_missing" in codes
    assert "policy_design_freshness_policy_time_stale" in codes


def test_phase_28_3_records_block_failed_top_level_status() -> None:
    case = _phase28_3_case()
    case["dormant_capability_inventory"]["status"] = "fail"
    case["skip_causality_ledger"]["status"] = "fail"
    case["freshness_policy_time_semantics"]["status"] = "fail"

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_dormant_capability_inventory_status_not_pass" in codes
    assert "policy_design_skip_causality_ledger_status_not_pass" in codes
    assert "policy_design_freshness_policy_time_semantics_status_not_pass" in codes


def _phase28_3_case() -> dict[str, Any]:
    case = _policy_design_case()
    case["dormant_capability_inventory"] = _dormant_capability_inventory()
    case["skip_causality_ledger"] = _skip_causality_ledger()
    case["freshness_policy_time_semantics"] = _freshness_policy_time_semantics()
    return case


def _dormant_capability_inventory() -> dict[str, Any]:
    return {
        "schema_version": (
            "policyos.runtime.policy_design_case.dormant_capability_inventory.v1"
        ),
        "record_id": "dormant-capability-inventory-rec-1",
        "record_family": "capability_mode_and_fallback_selection.v1",
        "status": "pass",
        "capabilities": [
            {
                "capability": "lex_legal_kg",
                "available": True,
                "invoked": True,
                "input_contract": "normative_applicability_request.v1",
                "output_artifact": "normative_applicability_report",
                "consumer": "policy_design_case.legal_authority_and_competence",
                "current_break_point": "none",
            },
            {
                "capability": "fabric_dataset_catalog_graph",
                "available": True,
                "invoked": True,
                "input_contract": "data_need_contract.v1",
                "output_artifact": "fabric_source_selection_audit",
                "consumer": "policy_design_case.data_source_semantic_lineage",
                "current_break_point": "none",
            },
            {
                "capability": "foundry_method_catalog_expectations",
                "available": True,
                "invoked": True,
                "input_contract": "method_selection_request.v1",
                "output_artifact": "foundry_method_report",
                "consumer": "policy_design_case.method_selection_and_validity",
                "current_break_point": "none",
            },
            {
                "capability": "scientist_workflow_nodes",
                "available": True,
                "invoked": True,
                "input_contract": "scientist_workflow_plan.v1",
                "output_artifact": "scientist_node_events",
                "consumer": "policy_design_case.claim_argument_evidence_case",
                "current_break_point": "none",
            },
        ],
        "evidence_ref": sha("1"),
        "runtime_event_ref": "event://policy-design-case/pdd-017/dormant-capabilities",
        "next_diagnostic_command": (
            "uv run pytest tests/unit/runtime/quality/"
            "test_policy_design_case_observability_static_audit.py -q"
        ),
    }


def _skip_causality_ledger() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.skip_causality_ledger.v1",
        "record_id": "skip-causality-ledger-rec-1",
        "record_family": "capability_mode_and_fallback_selection.v1",
        "status": "pass",
        "projection_preserves_reason_fields": True,
        "skipped_nodes": [
            {
                "node_id": "scientist.legal_conflict_deep_dive",
                "reason_code": "prerequisite_not_applicable",
                "missing_input": "legal_conflict_candidate",
                "prerequisite_status": "no_conflict_detected",
                "downstream_impact": "deep-dive node skipped; final claim keeps no-conflict ref",
                "profile_policy": "production skips require reason and blocker visibility",
                "raw_node_outcome_ref": sha("2"),
                "progress_event_ref": "event://runtime/progress/scientist/skip/1",
                "node_event_ref": "event://scientist/node/legal_conflict_deep_dive/skip",
            }
        ],
        "evidence_ref": sha("2"),
        "runtime_event_ref": "event://policy-design-case/pdd-018/skip-causality",
        "next_diagnostic_command": (
            "uv run pytest tests/unit/runtime/quality/"
            "test_policy_design_case_observability_static_audit.py -q"
        ),
    }


def _freshness_policy_time_semantics() -> dict[str, Any]:
    return {
        "schema_version": (
            "policyos.runtime.policy_design_case.freshness_policy_time_semantics.v1"
        ),
        "record_id": "freshness-policy-time-rec-1",
        "record_family": "numeric_time_and_geography_semantics.v1",
        "status": "pass",
        "policy_time": "2026-05-15",
        "evidence_time_bindings": [
            {
                "evidence_kind": "legal",
                "policy_time": "2026-05-15",
                "evidence_as_of": "2026-05-14",
                "freshness_status": "pass",
                "acceptable_recency_window_days": 30,
                "evidence_ref": sha("3"),
            },
            {
                "evidence_kind": "data",
                "policy_time": "2026-05-15",
                "evidence_as_of": "2026-05-15",
                "freshness_status": "pass",
                "acceptable_recency_window_days": 90,
                "evidence_ref": sha("4"),
            },
            {
                "evidence_kind": "benchmark",
                "policy_time": "2026-05-15",
                "evidence_as_of": "2026-05-10",
                "freshness_status": "pass",
                "acceptable_recency_window_days": 180,
                "evidence_ref": sha("5"),
            },
            {
                "evidence_kind": "decision",
                "policy_time": "2026-05-15",
                "evidence_as_of": "2026-05-17",
                "freshness_status": "pass",
                "acceptable_recency_window_days": 30,
                "evidence_ref": sha("6"),
            },
        ],
        "continuous_governance_triggers": [
            {
                "trigger_id": "reissue-when-source-stale",
                "trigger": "source_freshness_expired",
                "action": "reissue_or_withdraw",
            }
        ],
        "final_artifact_date_assumptions": [
            {
                "artifact": "public_policy_brief",
                "assumption": "Evidence remains current at publication time.",
                "evidence_ref": sha("7"),
            }
        ],
        "evidence_ref": sha("3"),
        "runtime_event_ref": "event://policy-design-case/pdd-045/freshness-policy-time",
        "next_diagnostic_command": (
            "uv run pytest tests/unit/runtime/quality/"
            "test_policy_design_case_observability_static_audit.py -q"
        ),
    }
