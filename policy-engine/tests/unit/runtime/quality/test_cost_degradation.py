from __future__ import annotations

import pytest

from polisyos.runtime.quality.cost_degradation import (
    COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION,
    CostDegradationTelemetryError,
    build_cost_degradation_telemetry_from_quality_context,
    cost_degradation_scorecard_gates,
    validate_cost_degradation_telemetry,
)
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
                        "provider_call_count": 2,
                        "input_tokens": 1200,
                        "output_tokens": 450,
                        "cost_usd_total": 1.75,
                    },
                }
            ],
        },
        "foundry_method_report": {
            "foundry_method_report_ref": sha("2"),
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "compute_seconds": 42,
                    "estimated_cost_usd": 3.25,
                }
            ],
        },
        "policy_design_case": {
            "case_id": "pdc-cost-1",
            "policy_design_case_ref": sha("3"),
            "search_budget_records": [
                {
                    "search_id": "scholar-screen",
                    "query_count": 7,
                    "actual_cost_usd": 0.4,
                    "evidence_ref": sha("4"),
                }
            ],
            "acquisition_records": [
                {
                    "acquisition_id": "fabric-followup",
                    "status": "limited",
                    "estimated_cost_usd": 0.9,
                    "evidence_ref": sha("5"),
                }
            ],
        },
        "degradation_records": [
            {
                "component": "provider.gateway",
                "phase": "evidence_acquisition",
                "trigger": "provider_brownout",
                "allowed_profiles": ["research"],
                "produced_artifacts": [sha("6")],
                "affected_claims": ["claim://pdc-cost-1/recommendation"],
                "affected_gates": ["runtime_quality.provider_cost"],
                "severity": "medium",
                "override_policy": "warning_limitation_first",
                "downstream_impact": (
                    "Provider telemetry is degraded but evidence quality is unchanged."
                ),
                "provenance_refs": ["event://runtime/degradation/provider-brownout"],
                "typed_blocker": None,
                "actual_profile": "production",
                "blocking_status": "non_blocking",
            }
        ],
    }


def _job_payload() -> dict[str, object]:
    return {
        "run_id": "R_cost_1",
        "job_id": "job-cost-1",
        "submitted_at": "2026-05-22T09:00:00Z",
        "started_at": "2026-05-22T09:00:05Z",
        "finished_at": "2026-05-22T09:02:00Z",
        "progress": {
            "details": {
                "retry_stats": {"attempts": 3, "retries": 2},
                "canary_performance_budget": {
                    "phase_budgets": [
                        {
                            "phase": "control.execution",
                            "observed_duration_ms": 115000,
                            "budget_ms": 300000,
                        }
                    ]
                },
            }
        },
    }


def test_cost_degradation_telemetry_covers_w2c_metric_families() -> None:
    record = build_cost_degradation_telemetry_from_quality_context(
        quality_evidence=_quality_context(),
        job_payload=_job_payload(),
        canary_kind="production",
    )

    validated = validate_cost_degradation_telemetry(record)
    metric_types = {row["metric_type"] for row in validated["observations"]}

    assert validated["schema_version"] == COST_DEGRADATION_TELEMETRY_SCHEMA_VERSION
    assert metric_types >= {
        "provider_call",
        "tokens",
        "search",
        "compute",
        "retry",
        "wall_clock",
        "acquisition",
        "degradation_state",
    }
    assert validated["summary"]["provider_call_count"] == 2
    assert validated["summary"]["token_count"] == 1650
    assert validated["summary"]["retry_count"] == 2
    assert validated["summary"]["warning_count"] >= 1
    assert validated["summary"]["blocking_count"] == 0


def test_cost_degradation_telemetry_is_scorecard_observable_without_silent_blocking() -> None:
    quality_evidence = _quality_context()
    quality_evidence["cost_degradation_telemetry"] = (
        build_cost_degradation_telemetry_from_quality_context(
            quality_evidence=quality_evidence,
            job_payload=_job_payload(),
            canary_kind="production",
        )
    )

    gates = cost_degradation_scorecard_gates(
        quality_evidence=quality_evidence,
        job_payload=_job_payload(),
        canary_kind="production",
    )

    assert [gate["name"] for gate in gates] == [
        "policy_design_w2c_cost_degradation_telemetry"
    ]
    assert gates[0]["status"] == "pass"
    assert gates[0]["blocking"] is False
    assert gates[0]["closeout_effect"] == "observe_only"


def test_cost_degradation_telemetry_rejects_blocking_without_authority_policy() -> None:
    record = build_cost_degradation_telemetry_from_quality_context(
        quality_evidence=_quality_context(),
        job_payload=_job_payload(),
        canary_kind="production",
    )
    record["observations"].append(
        {
            "metric_id": "budget.provider.hard_stop",
            "metric_type": "provider_call",
            "producer": "provider.gateway",
            "observed_value": 99,
            "unit": "call",
            "status": "blocked",
            "closeout_effect": "blocking",
            "owner": "team-runtime-quality",
            "ttl_seconds": 86400,
            "next_action": "Escalate through authority-level budget policy.",
            "evidence_ref": sha("7"),
        }
    )

    with pytest.raises(
        CostDegradationTelemetryError,
        match="cost_degradation_blocking_policy_ref_missing",
    ):
        validate_cost_degradation_telemetry(record)


def test_cost_telemetry_cannot_silently_downgrade_evidence_quality() -> None:
    record = build_cost_degradation_telemetry_from_quality_context(
        quality_evidence=_quality_context(),
        job_payload=_job_payload(),
        canary_kind="production",
    )
    record["observations"][0]["evidence_quality_effect"] = "downgraded"

    with pytest.raises(
        CostDegradationTelemetryError,
        match="cost_degradation_evidence_quality_effect_invalid",
    ):
        validate_cost_degradation_telemetry(record)
