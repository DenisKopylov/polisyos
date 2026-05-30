from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

# ruff: noqa: S101
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality.rule_evolution import build_rule_evolution_registry
from polisyos.runtime.quality.rule_replay_engine import (
    C33_RULE_CHANGE_CLASS_TABLE,
    RULE_REPLAY_COMPARISON_SCHEMA_VERSION,
    RULE_REPLAY_EXECUTION_SCHEMA_VERSION,
    build_rule_replay_comparison_report,
    persist_rule_replay_comparison_report,
    replay_under_new_rules,
    replay_under_original_rules,
)
from polisyos.scientist.methods.research_dag.builder import ResearchDAGBuilder
from polisyos.scientist.methods.research_dag.models import (
    ResearchDAGArtifact,
    ResearchNodeType,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _registry(
    *,
    version: str,
    threshold: float,
    requirement_id: str = "req.credit_support",
    previous_registry: dict[str, Any] | None = None,
    change_class: str | None = None,
) -> dict[str, Any]:
    return build_rule_evolution_registry(
        registry_id=f"rule-registry-{version}",
        version=version,
        effective_at=f"{version}-01T00:00:00+00:00".replace(".", "-"),
        previous_registry=previous_registry,
        rule_refs=[
            {
                "requirement_id": requirement_id,
                "logic": {
                    "predicate": "liquidity_gap_ratio",
                    "field": "liquidity_gap_ratio",
                    "operator": ">=",
                    "threshold": threshold,
                },
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
                "rule_version": version,
                "public_revalidation_effect": change_class,
                "provenance_ref": _sha("a"),
            }
        ],
        taxonomy_refs=[
            {
                "taxonomy_id": "taxonomy.policy_obligation",
                "version": version,
                "ref": _sha("b"),
            }
        ],
        alias_remaps=(
            [
                {
                    "from_requirement_id": "req.credit_support",
                    "to_requirement_id": requirement_id,
                    "reason": "Tightened admissibility threshold.",
                }
            ]
            if previous_registry and requirement_id != "req.credit_support"
            else []
        ),
        evidence_ref=_sha("c" if previous_registry is None else "d"),
        runtime_event_ref=f"event://rule-evolution/{version}",
    )


def _research_dag() -> ResearchDAGArtifact:
    builder = ResearchDAGBuilder(
        run_id="run-rule-replay-1",
        workflow_id="policy_design_case_replay",
    )
    builder.add_node(
        node_type=ResearchNodeType.QUESTION,
        producer="test",
        summary="Closed PDC replay question.",
    )
    builder.add_node(
        node_type=ResearchNodeType.SYNTHESIS,
        producer="runtime-quality",
        summary="Claim closed under admissibility rule.",
        claim_ids=["claim_credit_gap"],
    )
    return builder.artifact()


def _closed_case() -> dict[str, Any]:
    registry = _registry(version="2026.05", threshold=0.2)
    logic_hash = registry["rule_refs"][0]["logic_hash"]
    return {
        "case_id": "pdc-closed-credit-001",
        "case_status": "closed",
        "closed_at": "2026-05-24T10:00:00+00:00",
        "rule_evolution_registry": registry,
        "research_dag": _research_dag(),
        "claims": [
            {
                "claim_id": "claim_credit_gap",
                "scenario_requirement_refs": ["req.credit_support"],
                "facts": {"liquidity_gap_ratio": 0.25},
            }
        ],
        "closed_semantic_outputs": [
            {
                "claim_id": "claim_credit_gap",
                "requirement_id": "req.credit_support",
                "current_requirement_id": "req.credit_support",
                "rule_id": "req.credit_support",
                "logic_hash": logic_hash,
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
                "evaluation_status": "admissible",
                "passed": True,
                "observed_value": 0.25,
                "operator": ">=",
                "threshold": 0.2,
                "reason": "observed_value_satisfies_threshold",
            }
        ],
    }


def _stricter_change_record(old_registry: dict[str, Any]) -> dict[str, Any]:
    new_registry = _registry(
        version="2026.07",
        threshold=0.35,
        requirement_id="req.credit_support.v2",
        previous_registry=old_registry,
        change_class="stricter_admissibility",
    )
    return {
        "change_id": "rule-change-2026-07-credit-support",
        "change_class": "stricter_admissibility",
        "changed_at": "2026-07-01T00:00:00+00:00",
        "from_rule_registry": old_registry,
        "to_rule_registry": new_registry,
        "affected_requirement_ids": [
            "req.credit_support",
            "req.credit_support.v2",
        ],
        "public_rationale": "Production threshold tightened after evidence review.",
    }


def test_replay_under_original_rules_reproduces_closed_semantic_outputs() -> None:
    closed_case = _closed_case()
    change_record = _stricter_change_record(closed_case["rule_evolution_registry"])

    replay = replay_under_original_rules(
        closed_case,
        change_record,
        replay_time="2026-07-02T00:00:00+00:00",
    )

    assert replay["schema_version"] == RULE_REPLAY_EXECUTION_SCHEMA_VERSION
    assert replay["replay_mode"] == "original_rules"
    assert replay["semantic_replay_status"] == "match"
    assert replay["reproduces_closed_outputs"] is True
    assert replay["semantic_outputs"] == closed_case["closed_semantic_outputs"]
    assert replay["research_replay"]["steps"][-1]["claim_ids"] == ["claim_credit_gap"]
    assert replay["rule_evolution_replay_context"]["replay_mode"] == "original_logic"


def test_original_replay_fails_closed_when_closed_outputs_do_not_match() -> None:
    closed_case = _closed_case()
    closed_case["closed_semantic_outputs"] = deepcopy(
        closed_case["closed_semantic_outputs"]
    )
    closed_case["closed_semantic_outputs"][0]["evaluation_status"] = "blocked"
    change_record = _stricter_change_record(closed_case["rule_evolution_registry"])

    replay = replay_under_original_rules(
        closed_case,
        change_record,
        replay_time="2026-07-02T00:00:00+00:00",
    )

    assert replay["semantic_replay_status"] == "mismatch"
    assert replay["reproduces_closed_outputs"] is False
    assert {issue["code"] for issue in replay["issues"]} == {
        "closed_rule_replay_output_mismatch"
    }


def test_replay_under_new_rules_exposes_changed_admissibility() -> None:
    closed_case = _closed_case()
    change_record = _stricter_change_record(closed_case["rule_evolution_registry"])

    replay = replay_under_new_rules(
        closed_case,
        change_record,
        replay_time="2026-07-02T00:00:00+00:00",
    )

    assert replay["schema_version"] == RULE_REPLAY_EXECUTION_SCHEMA_VERSION
    assert replay["replay_mode"] == "new_rules"
    assert replay["semantic_replay_status"] == "changed_from_closed_outputs"
    assert replay["semantic_outputs"][0]["requirement_id"] == "req.credit_support"
    assert replay["semantic_outputs"][0]["current_requirement_id"] == (
        "req.credit_support.v2"
    )
    assert replay["semantic_outputs"][0]["evaluation_status"] == "blocked"
    assert replay["semantic_outputs"][0]["threshold"] == 0.35


def test_comparison_report_triggers_mandatory_revalidation_and_claim_lifecycle(
    tmp_path: Path,
) -> None:
    closed_case = _closed_case()
    change_record = _stricter_change_record(closed_case["rule_evolution_registry"])

    report = build_rule_replay_comparison_report(
        closed_case,
        change_record,
        replay_time="2026-07-02T00:00:00+00:00",
    )

    assert report["schema_version"] == RULE_REPLAY_COMPARISON_SCHEMA_VERSION
    assert report["status"] == "mandatory_revalidation_required"
    assert report["comparison"]["changed_claim_ids"] == ["claim_credit_gap"]
    assert report["comparison"]["changed_requirement_ids"] == ["req.credit_support"]
    assert report["revalidation_trigger"]["change_class"] == "stricter_admissibility"
    assert report["revalidation_trigger"]["mandatory_revalidation"] is True
    assert report["revalidation_trigger"]["public_effect"] == "mandatory_revalidation"
    assert report["public_comparison_report"]["silent_upgrade_allowed"] is False
    assert report["public_comparison_report"]["closed_case_historical_meaning"] == (
        "preserved"
    )

    lifecycle_report = report["lifecycle_reissue_report"]
    assert lifecycle_report["public_revision_state"]["affected_claim_ids"] == [
        "claim_credit_gap"
    ]
    assert lifecycle_report["public_revision_state"]["unaffected_claim_ids"] == []
    assert lifecycle_report["claim_revision_states"][0]["lifecycle_action"] == (
        "partial_reissue"
    )
    assert lifecycle_report["claim_revision_states"][0]["public_revision_status"] == (
        "revalidation_required"
    )

    store = FileSystemCAS(tmp_path / "cas")
    ref = persist_rule_replay_comparison_report(report, store=store)
    assert from_canonical_bytes(store.get_bytes(ref.artifact_id)) == report


def test_c33_change_class_table_distinguishes_notice_from_mandatory_revalidation() -> None:
    assert C33_RULE_CHANGE_CLASS_TABLE["editorial"]["mandatory_revalidation"] is False
    assert C33_RULE_CHANGE_CLASS_TABLE["editorial"]["public_effect"] == "no_notice"
    assert (
        C33_RULE_CHANGE_CLASS_TABLE["schema_compatible"]["public_effect"]
        == "internal_migration"
    )
    assert (
        C33_RULE_CHANGE_CLASS_TABLE["stricter_admissibility"][
            "mandatory_revalidation"
        ]
        is True
    )
    assert (
        C33_RULE_CHANGE_CLASS_TABLE["new_blocker"]["public_effect"]
        == "mandatory_revalidation"
    )
