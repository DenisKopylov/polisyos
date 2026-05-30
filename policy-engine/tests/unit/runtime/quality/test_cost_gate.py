from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

from polisyos.runtime.quality.closeout_reader import (
    CloseoutModuleReaderSpec,
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.cost_degradation import (
    build_cost_degradation_telemetry_from_quality_context,
)
from polisyos.runtime.quality.cost_gate import (
    RUN_COST_GATE_SCHEMA_VERSION,
    build_run_cost_gate_report,
    cost_gate_scorecard_gates,
    validate_run_cost_gate_report,
)
from polisyos.runtime.quality.performance_budget import (
    build_canary_performance_budget,
    run_cost_budget_policy_from_performance_budget,
)
from polisyos.runtime.quality.scorecard import build_quality_scorecard
from tests._helpers.hds_quality import sha


def _quality_context() -> dict[str, object]:
    return {
        "provider_model_quality_ledger": {
            "provider_model_quality_ledger_ref": sha("1"),
            "entries": [
                {
                    "provider": "gateway",
                    "model_id": "policy-reasoner",
                    "metrics": {
                        "provider_call_count": 3,
                        "input_tokens": 1_700,
                        "output_tokens": 500,
                        "cost_usd_total": 6.25,
                    },
                }
            ],
        },
        "foundry_method_report": {
            "foundry_method_report_ref": sha("2"),
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "compute_seconds": 180,
                    "estimated_cost_usd": 4.5,
                }
            ],
        },
        "policy_design_case": {
            "case_id": "pdc-w10d-cost",
            "run_id": "R_w10d_cost",
            "authority_level": "production",
            "public_impact": "high",
            "policy_design_case_ref": sha("3"),
            "search_budget_records": [
                {
                    "search_id": "scholar-screen",
                    "query_count": 6,
                    "actual_cost_usd": 0.4,
                    "evidence_ref": sha("4"),
                }
            ],
            "acquisition_records": [
                {
                    "acquisition_id": "fabric-followup",
                    "status": "limited",
                    "estimated_cost_usd": 1.5,
                    "evidence_ref": sha("5"),
                }
            ],
        },
    }


def _job_payload() -> dict[str, object]:
    return {
        "run_id": "R_w10d_cost",
        "job_id": "job-w10d-cost",
        "submitted_at": "2026-05-22T09:00:00Z",
        "started_at": "2026-05-22T09:00:03Z",
        "finished_at": "2026-05-22T09:02:20Z",
        "progress": {"details": {"retry_stats": {"attempts": 4, "retries": 3}}},
    }


def _budget_policy() -> dict[str, object]:
    return {
        "policy_id": "run-cost-policy.production.v1",
        "policy_ref": "policy://runtime/run-cost/production/v1",
        "owner": "team-runtime-quality",
        "ttl_seconds": 86_400,
        "limits": [
            {
                "dimension": "provider_api_calls",
                "budget": 2,
                "unit": "call",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/provider-calls/v1",
            },
            {
                "dimension": "tokens",
                "budget": 2_000,
                "unit": "token",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/tokens/v1",
            },
            {
                "dimension": "compute_dollars",
                "budget": 5.0,
                "unit": "usd",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/dollars/v1",
            },
            {
                "dimension": "embedding_searches",
                "budget": 5,
                "unit": "query",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/search/v1",
            },
            {
                "dimension": "wall_clock_seconds",
                "budget": 120,
                "unit": "second",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/wall-clock/v1",
            },
            {
                "dimension": "retries",
                "budget": 1,
                "unit": "retry",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/retry/v1",
            },
            {
                "dimension": "acquisition_dollars",
                "budget": 1.0,
                "unit": "usd",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/acquisition/v1",
            },
        ],
    }


def test_production_authority_over_budget_emits_typed_cost_blockers() -> None:
    quality_evidence = _quality_context()
    quality_evidence["cost_degradation_telemetry"] = (
        build_cost_degradation_telemetry_from_quality_context(
            quality_evidence=quality_evidence,
            job_payload=_job_payload(),
            canary_kind="production",
        )
    )

    report = build_run_cost_gate_report(
        quality_evidence=quality_evidence,
        job_payload=_job_payload(),
        canary_kind="production",
        budget_policy=_budget_policy(),
    )
    validated = validate_run_cost_gate_report(report)

    assert validated["schema_version"] == RUN_COST_GATE_SCHEMA_VERSION
    assert validated["status"] == "blocked"
    assert validated["summary"]["blocked_count"] >= 5
    blocker_dimensions = {blocker["dimension"] for blocker in validated["blockers"]}
    assert blocker_dimensions >= {
        "provider_api_calls",
        "tokens",
        "compute_dollars",
        "embedding_searches",
        "wall_clock_seconds",
        "retries",
        "acquisition_dollars",
    }
    assert all(blocker["status"] == "blocked" for blocker in validated["blockers"])
    assert all(
        blocker["authority_policy_ref"].startswith("policy://")
        for blocker in validated["blockers"]
    )
    assert validated["deficit_crosswalk"][0]["closeout_effect"] == "closeout_blocked"


def test_research_authority_over_budget_is_limitation_not_blocker() -> None:
    quality_evidence = deepcopy(_quality_context())
    case = quality_evidence["policy_design_case"]
    assert isinstance(case, dict)
    case["authority_level"] = "research"

    report = build_run_cost_gate_report(
        quality_evidence=quality_evidence,
        job_payload=_job_payload(),
        canary_kind="research",
        budget_policy=_budget_policy(),
    )
    validated = validate_run_cost_gate_report(report)

    assert validated["status"] == "limited"
    assert validated["summary"]["blocked_count"] == 0
    assert validated["summary"]["limitation_count"] > 0
    assert validated["blockers"] == []
    assert {issue["severity"] for issue in validated["issues"]} == {"limitation"}
    assert {
        row["closeout_effect"] for row in validated["deficit_crosswalk"]
    } == {"publish_with_limitation"}


def test_cost_gate_scorecard_gate_blocks_production_authority_only() -> None:
    quality_evidence = _quality_context()
    quality_evidence["run_cost_gate"] = build_run_cost_gate_report(
        quality_evidence=quality_evidence,
        job_payload=_job_payload(),
        canary_kind="production",
        budget_policy=_budget_policy(),
    )

    gates = cost_gate_scorecard_gates(
        quality_evidence=quality_evidence,
        job_payload=_job_payload(),
        canary_kind="production",
    )

    assert [gate["name"] for gate in gates] == ["policy_design_w10d_run_cost_gate"]
    assert gates[0]["status"] == "fail"
    assert gates[0]["blocking"] is True
    assert gates[0]["closeout_effect"] == "blocking"

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-w10d-cost",
        run_id="R_w10d_cost",
        execution_status="completed",
        job_payload=_job_payload(),
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert "run_cost_authority_budget_blocking" in {
        failure["code"] for failure in scorecard["blocking_quality_failures"]
    }


def test_closeout_reader_consumes_run_cost_gate_blockers() -> None:
    report = build_run_cost_gate_report(
        quality_evidence=_quality_context(),
        job_payload=_job_payload(),
        canary_kind="production",
        budget_policy=_budget_policy(),
    )

    verdict = build_can_i_closeout_verdict(
        run_id="R_w10d_cost",
        module_readers=(
            CloseoutModuleReaderSpec(
                module_id="run_cost_gate",
                reader_contract="polisyos.runtime.quality.cost_gate",
                owner="team-runtime-quality",
                stubbed=False,
            ),
        ),
        module_records={"run_cost_gate": report},
    )

    assert verdict["status"] == "blocked"
    assert verdict["can_closeout"] is False
    assert verdict["summary"]["blocker_count"] >= 1
    assert "run_cost_budget_exceeded" in {
        blocker["upstream_issue_code"] for blocker in verdict["blockers"]
    }


def test_performance_budget_exports_wall_clock_run_cost_policy() -> None:
    performance_budget = build_canary_performance_budget(
        canary_kind="production",
        job_payload=_job_payload(),
        budget_overrides_ms={"control.job_total": 60_000},
    )

    policy = run_cost_budget_policy_from_performance_budget(
        performance_budget,
        policy_ref="policy://runtime/run-cost/performance-budget/v1",
        authority_policy_ref="policy://runtime/run-cost/wall-clock/v1",
    )

    assert policy["policy_ref"] == "policy://runtime/run-cost/performance-budget/v1"
    assert policy["limits"] == [
        {
            "dimension": "wall_clock_seconds",
            "budget": 60.0,
            "unit": "second",
            "closeout_effect": "blocking",
            "authority_policy_ref": "policy://runtime/run-cost/wall-clock/v1",
            "owner": "team-runtime-quality",
            "ttl_seconds": 604800,
            "next_action": (
                "Investigate canary performance budget wall-clock overrun before "
                "production-authority closeout."
            ),
            "evidence_ref": "quality_evidence/canary_performance_budget.json",
        }
    ]
