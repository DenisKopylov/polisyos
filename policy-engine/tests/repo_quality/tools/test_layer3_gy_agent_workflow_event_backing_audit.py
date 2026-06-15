from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = (
    REPO_ROOT
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_agent_workflow_event_backing_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_agent_workflow_event_backing_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _component(audit: dict[str, Any], component_id: str) -> dict[str, Any]:
    for row in audit["roles"]:
        if row.get("component_id") == component_id:
            return row
    raise AssertionError(f"missing component {component_id}")


def _probe(audit: dict[str, Any], probe_id: str) -> dict[str, Any]:
    for row in audit["execution_probes"]:
        if row.get("probe_id") == probe_id:
            return row
    raise AssertionError(f"missing probe {probe_id}")


def test_gy_agent_workflow_event_backing_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_agent_workflow_event_backing_rejects_tool_loop_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["nl_pipeline_calls_scientist_tool_loop"] = True
    audit["summary"]["nl_tool_loop_invocation_count"] = 1
    audit["static_probes"]["nl_pipeline_tool_loop_references"]["match_count"] = 1
    _component(audit, "scientist_tool_loop")["nl_route_invoked"] = True

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "nl_tool_loop_invocation_greenwash" in codes
    assert "tool_loop_nl_invocation_greenwash" in codes


def test_gy_agent_workflow_event_backing_rejects_parser_ledger_as_tool_loop() -> None:
    validator = _validator()
    audit = _load_audit()
    _probe(audit, "research_simulated_nl_prompt_tool_ledger")["prompt_tool_tool_names"] = [
        "fake_tool"
    ]
    _component(audit, "prompt_tool_ledger")["g6_asset_backing"] = "tool_loop_backed"
    audit["summary"]["prompt_tool_ledger_is_real_tool_loop_transcript"] = True

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "parser_ledger_tool_loop_laundering" in codes
    assert "prompt_ledger_tool_loop_greenwash" in codes


def test_gy_agent_workflow_event_backing_rejects_g6_projection_as_live_run() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["g6_agent_run_records_bound_to_live_nl_run"] = True
    audit["summary"]["g6_records_bound_to_live_nl_run_count"] = 1
    audit["static_probes"]["committed_g6_agent_run_records"]["classification"] = (
        "runtime_event_backed"
    )
    _component(audit, "g6_agent_run_records")["nl_route_invoked"] = True
    _component(audit, "g6_agent_run_records")["g6_asset_backing"] = "runtime_event_backed"

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "g6_record_laundering" in codes
    assert "g6_records_nl_invocation_greenwash" in codes
    assert "g6_asset_backing_laundering" in codes


def test_gy_agent_workflow_event_backing_rejects_role_artifact_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    _component(audit, "pi_agent")["dedicated_persisted_role_artifact"] = "sha256:" + "1" * 64
    _component(audit, "formalizer")["dedicated_persisted_role_artifact"] = "trinity_bundle_ref"
    audit["summary"]["dedicated_role_event_artifact_count"] = 2

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "role_artifact_greenwash" in codes
    assert "formalizer_role_artifact_greenwash" in codes


def test_gy_agent_workflow_event_backing_rejects_dev_prompt_ledger_collapse() -> None:
    validator = _validator()
    audit = _load_audit()
    _probe(audit, "dev_simulated_nl_variant_steps")["prompt_tool_ledger_ref"] = (
        "sha256:" + "2" * 64
    )
    audit["summary"]["dev_profile_persists_prompt_tool_parser_ledger_to_cas"] = True

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "dev_prompt_ledger_greenwash" in codes


def test_gy_agent_workflow_event_backing_rejects_missing_role_step() -> None:
    validator = _validator()
    audit = _load_audit()
    research = _probe(audit, "research_simulated_nl_prompt_tool_ledger")
    research["steps"] = [
        step
        for step in research["steps"]
        if not (step.get("agent") == "critic" and step.get("action") == "critique")
    ]
    research["step_count"] = len(research["steps"])

    codes = _codes(validator.validate(audit))
    assert "execution_probe_step_count_drift" in codes
    assert "required_role_step_missing" in codes


def test_gy_agent_workflow_event_backing_rejects_missing_pattern_guardrail() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["patterns"] = [
        pattern for pattern in audit["classification"]["patterns"] if pattern != "P25"
    ]
    audit["acceptance_signal"] = [
        item for item in audit["acceptance_signal"] if "ToolLoopResult" not in item
    ]

    codes = _codes(validator.validate(audit))
    assert "pattern_coverage_drift" in codes
    assert "missing_acceptance_guardrail" in codes
