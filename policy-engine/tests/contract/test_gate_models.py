from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from polisyos.ir.governance.gate import GateContext, GateDecision, GateRequest, GateVerdict


def test_gate_request_roundtrip() -> None:
    context = GateContext(
        workflow_id="scientist_default",
        node_alias="run_governance",
        phase="POSTFLIGHT_GOV",
        iteration=1,
        policy_summary="Policy with 1 intervention(s)",
        simulation_results={"gdp_change": 1},
        issue_summary={"requested_items": 2},
        artifact_refs={"causal_report_ref": "sha256:" + ("a" * 64)},
        selected_replay_refs={},
        transport_summary={"status": "identified", "transport_mode": "transport_formula"},
        replay_summary={"readiness": "partial"},
    )
    request = GateRequest(
        request_id="abc123",
        run_id="R_test",
        reason="manual review required",
        context=context,
    )

    dumped = request.model_dump(mode="json")
    restored = GateRequest.model_validate(dumped)

    assert restored.request_id == "abc123"
    assert restored.schema_version == "1.2"
    assert restored.context.node_alias == "run_governance"
    assert restored.context.selected_replay_refs == {}
    assert restored.context.policy_summary == "Policy with 1 intervention(s)"
    assert restored.context.replay_summary == {"readiness": "partial"}


def test_gate_request_reads_legacy_v1_1_without_claiming_selected_views() -> None:
    request = GateRequest.model_validate(
        {
            "schema_version": "1.1",
            "request_id": "legacy-request",
            "run_id": "R_legacy",
            "reason": "historical request",
            "context": {
                "workflow_id": "scientist_default",
                "node_alias": "run_governance",
                "phase": "POSTFLIGHT_GOV",
            },
        }
    )

    assert request.schema_version == "1.1"
    assert request.context.selected_replay_refs is None
    assert "selected_replay_refs" not in request.model_dump(mode="json")["context"]


def test_gate_request_v1_2_requires_selected_replay_views() -> None:
    with pytest.raises(ValidationError, match="requires selected_replay_refs"):
        GateRequest(
            schema_version="1.2",
            request_id="missing-views",
            run_id="R_test",
            reason="manual review required",
            context=GateContext(
                workflow_id="scientist_default",
                node_alias="run_governance",
                phase="POSTFLIGHT_GOV",
            ),
        )


@pytest.mark.parametrize(
    ("schema_version", "has_selected_replay_refs", "selected_replay_refs", "expected_valid"),
    [
        ("1.2", False, None, False),
        ("1.2", True, None, False),
        ("1.2", True, {}, True),
        ("1.1", False, None, True),
        (None, False, None, False),
        (None, True, {}, True),
    ],
    ids=[
        "current-missing",
        "current-null",
        "current-empty",
        "legacy-missing",
        "default-version-missing",
        "default-version-empty",
    ],
)
def test_gate_request_json_schema_matches_pydantic_versioned_view_requirement(
    schema_version: str | None,
    has_selected_replay_refs: bool,
    selected_replay_refs: dict[str, object] | None,
    expected_valid: bool,
) -> None:
    context: dict[str, object] = {
        "workflow_id": "scientist_default",
        "node_alias": "run_governance",
        "phase": "POSTFLIGHT_GOV",
    }
    if has_selected_replay_refs:
        context["selected_replay_refs"] = selected_replay_refs
    payload: dict[str, object] = {
        "request_id": "request-schema-parity",
        "run_id": "R_test",
        "reason": "manual review required",
        "context": context,
    }
    if schema_version is not None:
        payload["schema_version"] = schema_version

    schema = GateRequest.model_json_schema(mode="validation")
    schema_valid = Draft202012Validator(schema).is_valid(payload)
    try:
        GateRequest.model_validate(payload)
    except ValidationError:
        model_valid = False
    else:
        model_valid = True

    assert model_valid is expected_valid
    assert schema_valid is expected_valid


def test_gate_context_iteration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        GateContext(
            workflow_id="scientist_default",
            node_alias="run_governance",
            phase="POSTFLIGHT_GOV",
            iteration=0,
        )


def test_gate_decision_requires_typed_verdict() -> None:
    decision = GateDecision(
        request_id="abc123",
        run_id="R_test",
        verdict=GateVerdict.REJECT,
        approver_id="ops.admin",
        reason_codes=["LEGAL_BLOCKER"],
    )
    assert decision.verdict == GateVerdict.REJECT
