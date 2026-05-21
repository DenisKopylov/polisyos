from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from polisyos.core.contracts.skip_blockers import (
    SKIP_BLOCKER_REQUIRED_FIELDS,
    SkipBlockerContractError,
    build_skip_blocker_record,
    deserialize_skip_blocker_record,
    serialize_skip_blocker_record,
)
from tests._helpers.hds_quality import blocking_codes, complete_job_payload, scorecard_for


def _workflow_report_with_skipped_node(
    *,
    alias: str,
    node_id: str,
    skip_blocker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "alias": alias,
        "node_id": node_id,
        "status": "skip",
        "duration_ms": 0,
    }
    if skip_blocker is not None:
        node["skip_blocker"] = skip_blocker
    return {
        "schema_version": "1.0",
        "workflow_id": "phase_2_5_skip_semantics",
        "run_id": "R_hds_red_control",
        "error_policy": "continue",
        "status": "ok",
        "nodes": [node],
    }


def _complete_skip_blocker(
    *,
    node_id: str = "scientist.node_run_causal_queries@1.0.0",
) -> dict[str, Any]:
    return build_skip_blocker_record(
        node_id=node_id,
        alias="run_causal_queries",
        node_kind="causal",
        reason="No params.causal_query; skip causal query execution.",
        missing_input="params.causal_query",
        owner="team-scientist",
        phase="causal_query_execution",
        downstream_impact="Causal query evidence cannot support policy claims.",
        allowed_profile="dev",
        closeout_blocking_policy="blocks_serious_closeout",
        scorecard_blocking_policy="blocks_scorecard_pass",
        approval_blocking_policy="blocks_approval_ready",
        public_export_blocking_policy="blocks_public_export",
    ).model_dump(mode="json")


def test_skip_blocker_contract_requires_phase_2_5_fields() -> None:
    payload = _complete_skip_blocker()

    assert set(SKIP_BLOCKER_REQUIRED_FIELDS) <= set(payload)

    for field in SKIP_BLOCKER_REQUIRED_FIELDS:
        incomplete = deepcopy(payload)
        incomplete.pop(field)

        with pytest.raises(SkipBlockerContractError) as error:
            deserialize_skip_blocker_record(incomplete)

        assert error.value.code == "skip_blocker_required_field_missing"
        assert error.value.field == field

    record = deserialize_skip_blocker_record(payload)
    assert deserialize_skip_blocker_record(serialize_skip_blocker_record(record)) == record


@pytest.mark.parametrize(
    ("alias", "node_id"),
    [
        ("run_causal_queries", "scientist.node_run_causal_queries@1.0.0"),
        ("run_transportability", "scientist.node_run_transportability@1.0.0"),
        ("run_normative_arbitration", "scientist.node_run_normative_arbitration@1.0.0"),
        ("run_governance", "scientist.node_run_governance@1.0.0"),
        ("evaluator", "scientist.evaluator_report@1.0.0"),
        ("build_decision_packet", "scientist.node_build_decision_packet@1.5.0"),
    ],
)
def test_scorecard_blocks_completed_summary_for_skipped_analytic_node_without_blocker(
    alias: str,
    node_id: str,
) -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "workflow_report": _workflow_report_with_skipped_node(
                    alias=alias,
                    node_id=node_id,
                )
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert "skipped_analytic_node_blocker_missing" in blocking_codes(scorecard)


def test_scorecard_blocks_skipped_analytic_node_with_serious_blocker_semantics() -> None:
    blocker = _complete_skip_blocker()
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "workflow_report": _workflow_report_with_skipped_node(
                    alias="run_causal_queries",
                    node_id="scientist.node_run_causal_queries@1.0.0",
                    skip_blocker=blocker,
                )
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert "skipped_analytic_node_blocks_scorecard" in blocking_codes(scorecard)
