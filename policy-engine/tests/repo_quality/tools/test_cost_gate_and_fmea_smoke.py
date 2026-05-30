from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from polisyos.runtime.quality.closeout_reader import (
    CloseoutModuleReaderSpec,
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.cost_gate import (
    build_run_cost_gate_report,
    cost_gate_scorecard_gates,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    PROMPT_TOOL_LEDGER_REF_KEY,
    build_prompt_tool_ledger_from_model_variant,
    prompt_tool_repair_fmea_closeout_record,
    serialize_prompt_tool_ledger,
)
from polisyos.scientist.evals.challenge_factory import (
    evaluate_r14_adversarial_probe_fixture,
)
from tests._helpers.hds_quality import (
    complete_quality_evidence,
    runtime_cas_refs,
    scorecard_for,
    sha,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
R14_FIXTURE_ROOT = (
    REPO_ROOT / "tests" / "fixtures" / "policy_design_case" / "w10c_adversarial_probes"
)


def _job_payload() -> dict[str, object]:
    return {
        "run_id": "R_w10_i10_smoke",
        "job_id": "job-w10-i10-smoke",
        "submitted_at": "2026-05-24T09:00:00Z",
        "started_at": "2026-05-24T09:00:02Z",
        "finished_at": "2026-05-24T09:02:10Z",
        "progress": {"details": {"retry_stats": {"attempts": 4, "retries": 3}}},
    }


def _cost_evidence() -> dict[str, object]:
    return {
        "provider_model_quality_ledger": {
            "provider_model_quality_ledger_ref": sha("1"),
            "entries": [
                {
                    "provider": "gateway",
                    "model_id": "policy-reasoner",
                    "metrics": {
                        "provider_call_count": 4,
                        "input_tokens": 1_800,
                        "output_tokens": 900,
                        "cost_usd_total": 7.5,
                    },
                }
            ],
        },
        "policy_design_case": {
            "case_id": "pdc-w10-i10-smoke",
            "run_id": "R_w10_i10_smoke",
            "authority_level": "production",
            "policy_design_case_ref": sha("2"),
            "search_budget_records": [
                {
                    "search_id": "scholar-screen",
                    "query_count": 8,
                    "actual_cost_usd": 0.5,
                    "evidence_ref": sha("3"),
                }
            ],
            "acquisition_records": [
                {
                    "acquisition_id": "fabric-followup",
                    "status": "limited",
                    "estimated_cost_usd": 1.25,
                    "evidence_ref": sha("4"),
                }
            ],
        },
    }


def _blocking_budget_policy() -> dict[str, object]:
    return {
        "policy_ref": "policy://runtime/run-cost/i10-smoke/v1",
        "owner": "team-runtime-quality",
        "ttl_seconds": 86_400,
        "limits": [
            {
                "dimension": "provider_api_calls",
                "budget": 1,
                "unit": "call",
                "closeout_effect": "blocking",
                "authority_policy_ref": "policy://runtime/run-cost/provider-calls/v1",
            },
            {
                "dimension": "wall_clock_seconds",
                "budget": 60,
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
        ],
    }


def test_i10_cost_gate_fmea_and_r14_smoke_closes_wave_10_exit_gate() -> None:
    cost_report = build_run_cost_gate_report(
        quality_evidence=_cost_evidence(),
        job_payload=_job_payload(),
        canary_kind="production",
        budget_policy=_blocking_budget_policy(),
    )

    assert cost_report["status"] == "blocked"
    assert cost_report["closeout_effect"] == "blocking"
    assert {blocker["code"] for blocker in cost_report["blockers"]} == {
        "run_cost_budget_exceeded"
    }
    assert {
        blocker["dimension"] for blocker in cost_report["blockers"]
    } >= {"provider_api_calls", "wall_clock_seconds", "retries"}

    cost_gates = cost_gate_scorecard_gates(
        quality_evidence={"run_cost_gate": cost_report},
        job_payload=_job_payload(),
        canary_kind="production",
    )
    assert cost_gates[0]["code"] == "run_cost_authority_budget_blocking"
    assert cost_gates[0]["blocking"] is True

    ledger = build_prompt_tool_ledger_from_model_variant(
        run_id="R_w10_i10_smoke",
        job_id="job-w10-i10-smoke",
        variant={
            "model_variant_id": "qwen_i10",
            "provider": "gateway",
            "model": "qwen",
            "schema_healing_count": 1,
        },
        rendered_input_refs=[sha("a")],
        output_refs=[sha("b")],
        authority_handoff_refs=[runtime_cas_refs()[PROMPT_TOOL_LEDGER_REF_KEY]],
    )
    ledger_payload = serialize_prompt_tool_ledger(ledger)
    ledger_payload[PROMPT_TOOL_LEDGER_REF_KEY] = runtime_cas_refs()[
        PROMPT_TOOL_LEDGER_REF_KEY
    ]

    quality_evidence = complete_quality_evidence()
    quality_evidence["run_cost_gate"] = cost_report
    quality_evidence["prompt_tool_ledger"] = ledger_payload
    scorecard = scorecard_for(
        job_payload=_job_payload(),
        quality_evidence=quality_evidence,
    )

    blocking_codes = {
        failure["code"] for failure in scorecard["blocking_quality_failures"]
    }
    assert "run_cost_authority_budget_blocking" in blocking_codes
    gates_by_code = {gate["code"]: gate for gate in scorecard["quality_gates"]}
    assert gates_by_code["prompt_tool_repair_decision_fmea_observed"]["status"] == "warn"
    assert scorecard["operator_machinery_failures"][0]["failure_mode"] == (
        "parser_contract_repair"
    )
    assert scorecard["operator_machinery_failures"][0]["recommended_mitigation"].startswith(
        "Keep strict parser validation"
    )

    closeout_record = prompt_tool_repair_fmea_closeout_record(ledger_payload)
    verdict = build_can_i_closeout_verdict(
        run_id="R_w10_i10_smoke",
        module_readers=(
            CloseoutModuleReaderSpec(
                module_id="prompt_tool_repair_fmea",
                reader_contract="polisyos.runtime.quality.prompt_tool_ledger#repair_fmea",
                owner="team-runtime-ops",
                required=False,
                stubbed=False,
                next_wave_target="W10.F",
            ),
        ),
        module_records={"prompt_tool_repair_fmea": closeout_record},
    )
    assert verdict["status"] == "closed_with_limitations"
    assert verdict["limitations"][0]["limitation_id"] == (
        "prompt_tool_repair_decision_machinery_failure"
    )

    fixture = json.loads(
        (R14_FIXTURE_ROOT / "authority_spoofing_fake_envelope.json").read_text(
            encoding="utf-8"
        )
    )
    probe_result = evaluate_r14_adversarial_probe_fixture(fixture)

    assert fixture["structural_pass_claimed"] is True
    assert probe_result.structural_status == "pass"
    assert probe_result.status == "semantic_fail"
    assert "r14_authority_spoofing_rejected" in probe_result.failure_codes
