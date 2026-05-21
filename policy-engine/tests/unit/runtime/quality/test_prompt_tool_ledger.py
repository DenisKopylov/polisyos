from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality.prompt_tool_ledger import (
    SCHEMA_VERSION,
    PromptToolParserAuthorityLedger,
    persist_prompt_tool_ledger,
    validate_prompt_tool_parser_authority,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_job_payload,
    complete_quality_evidence,
    scorecard_for,
    sha,
)


def _authority_step() -> dict[str, object]:
    return {
        "step_id": "formalizer:variant-qwen:1",
        "step_kind": "formalizer",
        "authority_scopes": ["evidence", "claims", "scorecard", "approval"],
        "prompt": {
            "template_id": "scientist.formalizer",
            "template_version": "2026.05.15",
            "template_ref": sha("a"),
            "rendered_prompt_ref": sha("b"),
            "rendered_input_refs": [sha("c"), sha("d")],
            "template_variables_fingerprint": "sha256:" + "1" * 64,
        },
        "model_provider": {
            "provider": "gateway",
            "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            "model_fingerprint": "qwen3-2026-05-15",
            "provider_config_ref": sha("e"),
            "temperature": 0.0,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        },
        "tool_allowlist": ["scholar_search"],
        "tool_schemas": [
            {
                "tool_name": "scholar_search",
                "schema_ref": sha("f"),
                "schema_fingerprint": "sha256:" + "2" * 64,
            }
        ],
        "tool_call_refs": [
            {
                "tool_name": "scholar_search",
                "call_ref": sha("3"),
                "output_ref": sha("4"),
                "status": "pass",
            }
        ],
        "output_refs": [sha("5")],
        "parser_contract": {
            "parser_id": "trinity_bundle_parser",
            "parser_version": "1.0",
            "contract_ref": sha("6"),
            "input_schema_ref": sha("7"),
            "output_schema_ref": sha("8"),
        },
        "validation_refs": [
            {
                "validator_id": "trinity_schema_validator",
                "status": "pass",
                "validation_ref": sha("9"),
            }
        ],
        "repair_decisions": [
            {
                "decision": "schema_healing_not_required",
                "status": "not_applicable",
                "reason": "Strict parser validation passed.",
            }
        ],
        "authority_handoff_refs": [
            {
                "scope": "claims",
                "handoff_ref": sha("0"),
                "consumer": "scientist.claim_ledger",
                "status": "pass",
            }
        ],
    }


def test_prompt_tool_ledger_persists_prompt_tool_parser_authority(tmp_path) -> None:
    ledger = PromptToolParserAuthorityLedger.model_validate(
        {
            "run_id": "R_prompt_tool",
            "job_id": "job-prompt-tool",
            "model_variant_id": "qwen_1",
            "steps": [_authority_step()],
        }
    )

    validation = validate_prompt_tool_parser_authority(ledger)
    assert validation.satisfied is True
    assert validation.missing_codes == ()
    assert ledger.steps[0].prompt.prompt_fingerprint.startswith("sha256:")

    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_prompt_tool_ledger(ledger, store=store)
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["steps"][0]["prompt"]["template_id"] == "scientist.formalizer"
    assert payload["steps"][0]["prompt"]["rendered_input_refs"] == [sha("c"), sha("d")]
    assert payload["steps"][0]["tool_allowlist"] == ["scholar_search"]
    assert payload["steps"][0]["tool_schemas"][0]["schema_fingerprint"] == (
        "sha256:" + "2" * 64
    )
    assert payload["steps"][0]["parser_contract"]["contract_ref"] == sha("6")
    assert payload["steps"][0]["validation_refs"][0]["validation_ref"] == sha("9")
    assert payload["steps"][0]["authority_handoff_refs"][0]["handoff_ref"] == sha("0")


def test_prompt_tool_ledger_records_system_confounded_findings() -> None:
    ledger = PromptToolParserAuthorityLedger.model_validate(
        {
            "run_id": "R_prompt_tool",
            "job_id": "job-prompt-tool",
            "model_variant_id": "qwen_1",
            "steps": [_authority_step()],
            "findings": [
                {
                    "code": "prompt_tool_failure_system_confounded",
                    "severity": "warn",
                    "failure_reason": (
                        "Prompt/tool validation failed while upstream evidence-spine "
                        "closure was already blocked."
                    ),
                    "step_id": "formalizer:variant-qwen:1",
                    "validator_ref": sha("9"),
                    "upstream_spine_blocker_refs": [
                        "quality_evidence/semantic_binding_ledger.json#/issues/0"
                    ],
                }
            ],
        }
    )

    assert ledger.summary["finding_count"] == 1
    assert ledger.findings[0].step_id == "formalizer:variant-qwen:1"
    assert ledger.findings[0].validator_ref == sha("9")
    assert ledger.summary["upstream_spine_blocker_refs"] == [
        "quality_evidence/semantic_binding_ledger.json#/issues/0"
    ]


def test_provider_ledger_presence_alone_cannot_satisfy_prompt_tool_parser_authority() -> None:
    evidence = complete_quality_evidence()
    evidence.pop("prompt_tool_ledger", None)

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
    )
    gates = {gate["name"]: gate for gate in scorecard["quality_gates"]}

    assert gates["provider_model_quality_ledger_passed"]["status"] == "pass"
    assert gates["prompt_tool_parser_authority_ledger_present"]["status"] == "fail"
    assert (
        gates["prompt_tool_parser_authority_ledger_present"]["code"]
        == "prompt_tool_parser_authority_ledger_missing"
    )
    assert "prompt_tool_parser_authority_ledger_missing" in blocking_codes(scorecard)
