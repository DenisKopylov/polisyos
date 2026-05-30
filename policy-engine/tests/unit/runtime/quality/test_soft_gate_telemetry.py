from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime, timedelta

from polisyos.core.contracts.bounded_liveness import BoundedLivenessConfig
from polisyos.runtime.quality.human_review import build_human_review_calibration_report
from polisyos.runtime.quality.prompt_tool_ledger import PromptToolParserAuthorityLedger
from polisyos.runtime.quality.soft_gate_telemetry import (
    SOFT_GATE_TELEMETRY_SCHEMA_VERSION,
    build_soft_gate_telemetry_report,
    warning_lifecycle_summaries,
)
from tests._helpers.hds_quality import sha


def _warn_gate(**overrides: object) -> dict[str, object]:
    gate = {
        "name": "provider_model_quality_ledger_passed",
        "stage": "llm",
        "code": "provider_model_quality_requires_review",
        "status": "warn",
        "layer": "llm_provider_quality",
        "phase": "provider_model_quality",
        "message": "Provider/model quality drift requires review.",
        "evidence_ref": "quality_evidence/provider_model_quality_ledger.json",
        "next_action": "Review drift evidence before approving the production model choice.",
        "blocking": False,
    }
    gate.update(overrides)
    return gate


def test_warning_lifecycle_summaries_track_owner_ttl_and_expiry() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
    warnings = warning_lifecycle_summaries(
        [
            _warn_gate(first_observed_at=(now - timedelta(hours=50)).isoformat()),
            _warn_gate(
                code="semantic_binding_review_needed",
                layer="semantic_binding",
                owner="team-policy-semantics",
                first_observed_at=(now - timedelta(hours=4)).isoformat(),
            ),
        ],
        generated_at=now,
        ttl_seconds=48 * 60 * 60,
        escalation_after_seconds=24 * 60 * 60,
    )

    expired = warnings[0]
    assert expired["owner"] == "team-runtime-ops"
    assert expired["ttl_seconds"] == 48 * 60 * 60
    assert expired["lifecycle_status"] == "expired"
    assert expired["closeout_effect"] == "expired_warning_blocks_serious_closeout"
    assert expired["publication_effect"] == "publication_requires_resolution_or_accepted_deficit"
    assert expired["accepted_deficit_policy"] == "owner_review_required"

    active = warnings[1]
    assert active["owner"] == "team-policy-semantics"
    assert active["lifecycle_status"] == "active"
    assert active["closeout_effect"] == "advisory_until_ttl_or_serious_closeout"


def test_soft_gate_telemetry_exposes_liveness_hooks_and_advisory_review_boundary() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
    liveness = BoundedLivenessConfig(
        config_id="bounded-liveness.test.v1",
        owner="team-runtime-quality",
        version="2026-05-22",
        default_deadline_s=60.0,
        default_retry_ceiling=3,
        producer_deadline_overrides_s={"scholar.deep_research_job": 15.0},
        producer_retry_ceiling_overrides={"scholar.deep_research_job": 1},
    ).resolve(
        "scholar.deep_research_job",
        requested_deadline_s=30.0,
        requested_retries=5,
    )
    review_report = build_human_review_calibration_report(
        review_events=[
            {
                "review_id": "review-fast-override",
                "flow": "override",
                "outcome": "override",
                "expected_outcome": "reject",
                "reviewer_identity": "producer@example.test",
                "producer_identity": "producer@example.test",
                "reviewer_independent": False,
                "separation_of_duty_attested": False,
                "time_spent_seconds": 20,
                "dissent": False,
                "change_requests": [],
                "approved_without_change": True,
                "decision_ref": sha("6"),
                "completed_at": "2026-05-22T10:00:00+00:00",
                "override_correct": False,
            }
        ],
        run_id="R_soft_gate",
        job_id="job-soft-gate",
        now=now,
    )

    report = build_soft_gate_telemetry_report(
        run_id="R_soft_gate",
        job_id="job-soft-gate",
        gates=[_warn_gate()],
        bounded_liveness_resolutions=[liveness],
        human_review_calibration=review_report,
        generated_at=now,
    )

    assert report["schema_version"] == SOFT_GATE_TELEMETRY_SCHEMA_VERSION
    assert report["bounded_liveness_hooks"] == [
        {
            "producer_key": "scholar.deep_research_job",
            "deadline_s": 15.0,
            "retry_ceiling": 1,
            "escalation": "runtime_escalation",
            "config_id": "bounded-liveness.test.v1",
            "config_version": "2026-05-22",
            "owner": "team-runtime-quality",
            "feature_flag": "universal_pdc_bounded_liveness",
            "status": "armed",
            "notes": [
                "requested_deadline_clamped_to_governed_ceiling",
                "requested_retries_clamped_to_governed_ceiling",
            ],
        }
    ]
    review = report["advisory_review_telemetry"]
    assert review["posture"] == "advisory"
    assert review["blocking_permitted"] is False
    assert "current_run_closeout_block" in review["authority_boundary"]["may_not_use_for"]


def test_complexity_budget_reads_existing_telemetry_and_requests_prune_or_merge() -> None:
    now = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)
    prompt_ledger = PromptToolParserAuthorityLedger.model_validate(
        {
            "run_id": "R_soft_gate",
            "job_id": "job-soft-gate",
            "steps": [
                {
                    "step_id": "qwen_1:formalizer:1",
                    "step_kind": "formalizer",
                    "authority_scopes": ["evidence", "claims", "scorecard", "approval"],
                    "prompt": {
                        "template_id": "scientist.formalizer",
                        "template_version": "2026.05.22",
                        "rendered_input_refs": [sha("1")],
                    },
                    "model_provider": {"provider": "gateway", "model": "qwen"},
                    "tool_allowlist": ["scholar_search", "fabric_lookup"],
                    "tool_schemas": [
                        {"tool_name": "scholar_search", "schema_ref": sha("2")},
                        {"tool_name": "fabric_lookup", "schema_ref": sha("3")},
                    ],
                    "tool_call_refs": [
                        {
                            "tool_name": "scholar_search",
                            "call_ref": sha("4"),
                            "output_ref": sha("5"),
                            "status": "pass",
                        },
                        {
                            "tool_name": "fabric_lookup",
                            "call_ref": sha("6"),
                            "output_ref": sha("7"),
                            "status": "pass",
                        },
                    ],
                    "output_refs": [sha("8")],
                    "parser_contract": {
                        "parser_id": "strict_parser",
                        "parser_version": "1.0",
                        "contract_ref": sha("9"),
                        "input_schema_ref": sha("a"),
                        "output_schema_ref": sha("b"),
                    },
                    "validation_refs": [
                        {
                            "validator_id": "strict_parser",
                            "status": "pass",
                            "validation_ref": sha("c"),
                        }
                    ],
                    "repair_decisions": [
                        {
                            "decision": "schema_healing_applied",
                            "status": "applied",
                            "reason": "Runtime variant reported schema healing.",
                            "repair_ref": sha("d"),
                            "fmea_annotation": {
                                "failure_mode": "parser_contract_repair",
                                "severity": 6,
                                "cause": "model_output_failed_parser_contract",
                                "recommended_mitigation": (
                                    "Keep strict parser validation and preserve "
                                    "repaired output as candidate-only until "
                                    "authority handoff validation passes."
                                ),
                                "residual_risk": (
                                    "Parser healing may mask prompt or tool drift; "
                                    "audit the repair ref before reuse in production "
                                    "authority runs."
                                ),
                                "occurrence": 2,
                                "detectability": 3,
                                "owner": "team-runtime-ops",
                                "controls": ["strict parser validation"],
                                "evidence_ref": sha("d"),
                            },
                        }
                    ],
                    "authority_handoff_refs": [
                        {
                            "scope": "claims",
                            "handoff_ref": sha("e"),
                            "consumer": "scientist.claim_ledger",
                            "status": "pass",
                        }
                    ],
                }
            ],
        }
    )
    review_report = build_human_review_calibration_report(
        review_events=[
            {
                "review_id": "review-1",
                "outcome": "approve",
                "expected_outcome": "approve",
                "reviewer_identity": "reviewer@example.test",
                "burden_minutes": 12,
            }
        ],
        run_id="R_soft_gate",
        job_id="job-soft-gate",
        now=now,
    )

    report = build_soft_gate_telemetry_report(
        run_id="R_soft_gate",
        job_id="job-soft-gate",
        gates=[_warn_gate(), _warn_gate(code="second_warning", layer="semantic_binding")],
        prompt_tool_ledger=prompt_ledger,
        human_review_calibration=review_report,
        run_cost_ledgers=[
            {
                "total_actual_cost_usd": 42.5,
                "elapsed_seconds": 900,
                "human_review_hours": 1.25,
            }
        ],
        complexity_budget={"max_warning_count": 1, "max_tool_count": 1},
        generated_at=now,
    )

    complexity = report["complexity_budget_telemetry"]
    assert complexity["input_source"] == "runtime_telemetry"
    assert complexity["status"] == "advisory_over_budget"
    assert complexity["measurements"] == {
        "gate_count": 2,
        "warning_count": 2,
        "repair_decision_count": 1,
        "repair_fmea_annotation_count": 1,
        "tool_count": 2,
        "review_count": 1,
        "total_actual_cost_usd": 42.5,
        "elapsed_seconds": 900.0,
        "human_review_hours": 1.25,
    }
    assert {
        "soft_gate_warning_prune_or_merge",
        "prompt_tool_allowlist_prune_or_merge",
    } <= {item["decision"] for item in complexity["prune_or_merge_decisions"]}
