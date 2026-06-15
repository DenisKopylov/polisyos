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
    / "layer3_gy_foundry_breadth_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_foundry_breadth_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _smoke(audit: dict[str, Any], family: str) -> dict[str, Any]:
    for row in audit["direct_smokes"]:
        if row.get("top_family") == family:
            return row
    raise AssertionError(f"missing smoke family {family}")


def test_gy_foundry_breadth_audit_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


def test_gy_foundry_breadth_audit_rejects_missing_family_smoke() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["direct_smokes"] = [
        row for row in audit["direct_smokes"] if row.get("top_family") != "survey"
    ]
    audit["summary"]["direct_smoke_family_count"] = 5
    audit["summary"]["direct_smoke_pass_count"] = 5

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "direct_smoke_family_drift" in codes


def test_gy_foundry_breadth_audit_rejects_direct_smoke_failure() -> None:
    validator = _validator()
    audit = _load_audit()
    row = _smoke(audit, "econometrics")
    row["status"] = "fail"
    row["output_hash"] = "n/a"
    audit["summary"]["direct_smoke_pass_count"] = 5
    audit["summary"]["direct_smoke_fail_count"] = 1

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "direct_smoke_not_pass" in codes
    assert "bad_output_hash" in codes


def test_gy_foundry_breadth_audit_rejects_dag_consumption_greenwash() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["gap_class"] = "wired_and_works"
    audit["classification"]["method_outputs_dag_consumed"] = True
    audit["summary"]["dag_consumed_method_outputs_count"] = 6
    audit["dag_consumption_truth"]["method_execution_nodes"] = {
        "compile_foundry": "ok",
        "run_simulation": "ok",
    }
    _smoke(audit, "causal")["evidence_kind"] = "dag_consumed"
    _smoke(audit, "causal")["dag_consumed_on_pinned_route"] = True

    codes = _codes(validator.validate(audit))
    assert "classification_drift" in codes
    assert "summary_semantics_drift" in codes
    assert "method_execution_node_greenwash" in codes
    assert "direct_smoke_laundered" in codes
    assert "dag_consumption_greenwash" in codes


def test_gy_foundry_breadth_audit_rejects_route_filter_collapse() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["summary"]["broad_live_tag_envelope_count"] = 172
    audit["route_relevance"]["broad_live_tag_envelope"]["count"] = 172
    audit["route_relevance"]["pinned_legacy_filter"]["by_top_family"]["bayesian"] = 19

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "route_envelope_collapsed" in codes
    assert "pinned_route_filter_drift" in codes
    assert "pinned_filter_overexpanded" in codes


def test_gy_foundry_breadth_audit_rejects_missing_pattern_guardrail() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["patterns"] = [
        pattern for pattern in audit["classification"]["patterns"] if pattern != "P14"
    ]
    audit["acceptance_signal"] = [
        item
        for item in audit["acceptance_signal"]
        if "gap_class remains producer_without_consumer" not in item
    ]

    codes = _codes(validator.validate(audit))
    assert "pattern_coverage_drift" in codes
    assert "missing_acceptance_guardrail" in codes


def test_gy_foundry_breadth_audit_rejects_agent_scope_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["methodology"]["agents_used"] = True

    assert "agent_scope_drift" in _codes(validator.validate(audit))
