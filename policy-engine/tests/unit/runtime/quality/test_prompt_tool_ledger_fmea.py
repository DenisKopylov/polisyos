from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.runtime.quality import prompt_tool_ledger as prompt_tool_ledger_module
from polisyos.runtime.quality.closeout_reader import (
    CloseoutModuleReaderSpec,
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    PROMPT_TOOL_LEDGER_REF_KEY,
    PromptToolParserAuthorityLedger,
    RepairDecisionFMEAAnnotation,
    build_prompt_tool_ledger_from_model_variant,
    serialize_prompt_tool_ledger,
    validate_prompt_tool_parser_authority,
)
from tests._helpers.hds_quality import (
    complete_quality_evidence,
    runtime_cas_refs,
    scorecard_for,
    sha,
)
from tests.unit.runtime.quality.test_prompt_tool_ledger import _authority_step


def test_repair_decisions_without_fmea_refs_cannot_pass_authority_validation() -> None:
    step = _authority_step()
    repair_decisions = []
    for decision in step["repair_decisions"]:
        row = dict(decision)
        row.pop("fmea_annotation", None)
        repair_decisions.append(row)
    step["repair_decisions"] = repair_decisions
    payload = {
        "run_id": "R_prompt_tool_fmea_missing",
        "job_id": "job-prompt-tool-fmea-missing",
        "model_variant_id": "qwen_1",
        "steps": [step],
    }

    ledger = PromptToolParserAuthorityLedger.model_validate(payload)
    validation = validate_prompt_tool_parser_authority(ledger)

    assert validation.satisfied is False
    assert "prompt_tool_repair_fmea_refs_missing" in validation.missing_codes
    assert ledger.summary["status"] == "fail"
    assert ledger.summary["repair_fmea_unannotated_count"] == 1


def test_fmea_annotation_requires_w10f_repair_refs() -> None:
    with pytest.raises(ValidationError, match="cause"):
        RepairDecisionFMEAAnnotation.model_validate(
            {
                "failure_mode": "parser_contract_repair",
                "severity": 6,
                "occurrence": 2,
                "detectability": 3,
                "owner": "team-runtime-ops",
                "controls": ["strict parser validation"],
            }
        )


def test_builder_emits_repair_machinery_failure_surface_with_w10f_refs() -> None:
    ledger = build_prompt_tool_ledger_from_model_variant(
        run_id="R_prompt_tool_fmea",
        job_id="job-prompt-tool-fmea",
        variant={
            "model_variant_id": "qwen_1",
            "provider": "gateway",
            "model": "qwen",
            "schema_healing_count": 1,
        },
        rendered_input_refs=[sha("a")],
        output_refs=[sha("b")],
        authority_handoff_refs=[sha("c")],
    )

    decision = ledger.steps[0].repair_decisions[0]
    assert decision.fmea_annotation is not None
    assert decision.fmea_annotation.cause == "model_output_failed_parser_contract"
    assert decision.fmea_annotation.recommended_mitigation == (
        "Keep strict parser validation and preserve repaired output as candidate-only "
        "until authority handoff validation passes."
    )
    assert decision.fmea_annotation.residual_risk == (
        "Parser healing may mask prompt or tool drift; audit the repair ref before "
        "reuse in production authority runs."
    )

    failures = prompt_tool_ledger_module.prompt_tool_repair_machinery_failures(ledger)
    assert failures == [
        {
            "failure_id": (
                "prompt_tool_repair:qwen_1:model_variant:model_variant_output:1:"
                "schema_healing_applied"
            ),
            "step_id": "qwen_1:model_variant:model_variant_output:1",
            "decision": "schema_healing_applied",
            "status": "applied",
            "repair_ref": sha("c"),
            "failure_mode": "parser_contract_repair",
            "severity": 6,
            "cause": "model_output_failed_parser_contract",
            "recommended_mitigation": (
                "Keep strict parser validation and preserve repaired output as "
                "candidate-only until authority handoff validation passes."
            ),
            "residual_risk": (
                "Parser healing may mask prompt or tool drift; audit the repair ref "
                "before reuse in production authority runs."
            ),
            "risk_priority_number": 36,
            "authority_effect": "accepted_mitigation",
            "evidence_ref": sha("c"),
            "owner": "team-runtime-ops",
            "surface": "prompt_tool_repair_fmea",
        }
    ]


def test_repair_machinery_failures_surface_in_scorecard_operator_payload() -> None:
    ledger = build_prompt_tool_ledger_from_model_variant(
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        variant={
            "model_variant_id": "qwen_1",
            "provider": "gateway",
            "model": "qwen",
            "schema_healing_count": 1,
        },
        rendered_input_refs=[sha("a")],
        output_refs=[sha("b")],
        authority_handoff_refs=[runtime_cas_refs()[PROMPT_TOOL_LEDGER_REF_KEY]],
    )
    ledger_payload = serialize_prompt_tool_ledger(ledger)
    ledger_payload[PROMPT_TOOL_LEDGER_REF_KEY] = runtime_cas_refs()[PROMPT_TOOL_LEDGER_REF_KEY]
    evidence = complete_quality_evidence()
    evidence["prompt_tool_ledger"] = ledger_payload

    scorecard = scorecard_for(quality_evidence=evidence)

    gates = {gate["code"]: gate for gate in scorecard["quality_gates"]}
    assert gates["prompt_tool_repair_decision_fmea_observed"]["status"] == "warn"
    assert gates["prompt_tool_repair_decision_fmea_observed"]["blocking"] is False
    assert scorecard["operator_machinery_failures"][0]["failure_mode"] == (
        "parser_contract_repair"
    )
    assert scorecard["operator_machinery_failures"][0]["cause"] == (
        "model_output_failed_parser_contract"
    )
    assert scorecard["soft_gate_telemetry"]["repair_decision_fmea"][
        "machinery_failures"
    ][0]["recommended_mitigation"].startswith("Keep strict parser validation")


def test_repair_machinery_failures_surface_as_closeout_limitations() -> None:
    ledger = build_prompt_tool_ledger_from_model_variant(
        run_id="R_prompt_tool_fmea_closeout",
        job_id="job-prompt-tool-fmea-closeout",
        variant={
            "model_variant_id": "qwen_1",
            "provider": "gateway",
            "model": "qwen",
            "schema_healing_count": 1,
        },
        rendered_input_refs=[sha("a")],
        output_refs=[sha("b")],
        authority_handoff_refs=[sha("c")],
    )
    closeout_record = prompt_tool_ledger_module.prompt_tool_repair_fmea_closeout_record(ledger)

    verdict = build_can_i_closeout_verdict(
        run_id="R_prompt_tool_fmea_closeout",
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
    assert verdict["can_closeout"] is True
    assert verdict["limitations"][0]["limitation_id"] == (
        "prompt_tool_repair_decision_machinery_failure"
    )
    assert verdict["limitations"][0]["message"] == (
        "Prompt/tool repair decision schema_healing_applied surfaced as "
        "parser_contract_repair machinery failure."
    )
